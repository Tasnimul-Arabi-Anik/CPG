#!/usr/bin/env python3
"""Shared workflow configuration loading for direct runner, validation, and Snakemake."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class WorkflowConfigError(Exception):
    """Raised when workflow configuration resolution fails."""


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise WorkflowConfigError("PyYAML is required to read workflow configuration.") from exc
    if not path.exists():
        raise WorkflowConfigError(f"Workflow config does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise WorkflowConfigError(f"Workflow config must contain a YAML mapping: {path}")
    return data


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if key == "extends":
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _resolve_config(path: Path, seen: set[Path]) -> dict[str, Any]:
    resolved_path = path.resolve()
    if resolved_path in seen:
        chain = " -> ".join(str(item) for item in [*seen, resolved_path])
        raise WorkflowConfigError(f"Circular workflow config extends chain: {chain}")
    seen.add(resolved_path)
    data = _load_yaml(resolved_path)
    parent_text = data.get("extends", "")
    if parent_text:
        parent_path = Path(str(parent_text))
        if not parent_path.is_absolute():
            parent_path = resolved_path.parent / parent_path
        parent = _resolve_config(parent_path, seen)
        return deep_merge(parent, data)
    return {key: value for key, value in data.items() if key != "extends"}


def _substitute(value: Any, context: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _substitute(child, context) for key, child in value.items()}
    if isinstance(value, list):
        return [_substitute(child, context) for child in value]
    if isinstance(value, str):
        try:
            return value.format(**context)
        except KeyError as exc:
            missing = exc.args[0]
            raise WorkflowConfigError(f"Unknown workflow config placeholder {{{missing}}} in value: {value}") from exc
    return value


def load_workflow_config(path: str | Path, root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root).resolve()
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = root_path / config_path
    resolved = _resolve_config(config_path, set())
    paths = resolved.get("paths", {}) if isinstance(resolved.get("paths", {}), dict) else {}
    profile = resolved.get("profile", {}) if isinstance(resolved.get("profile", {}), dict) else {}
    context = {
        "results_dir": str(paths.get("results_dir", "results")),
        "logs_dir": str(paths.get("logs_dir", "logs")),
        "profile_name": str(profile.get("name", "default")),
        "evidence_class": str(profile.get("evidence_class", "unspecified")),
    }
    resolved = _substitute(resolved, context)
    resolved.setdefault("profile", {})
    if isinstance(resolved["profile"], dict):
        resolved["profile"].setdefault("name", context["profile_name"])
        resolved["profile"].setdefault("evidence_class", context["evidence_class"])
    return resolved


def resolved_config_sha256(config: dict[str, Any]) -> str:
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
