#!/usr/bin/env python3
"""Audit whether tracked source manifests still match authoritative source exports."""

from __future__ import annotations

import argparse
import csv
import hashlib
import tempfile
from pathlib import Path
from typing import Iterable

import yaml  # type: ignore

import import_source_manifests


DRIFT_COLUMNS = [
    "import_id",
    "enabled",
    "input_path",
    "output_path",
    "input_checksum",
    "current_output_checksum",
    "regenerated_output_checksum",
    "status",
    "severity",
    "message",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


class DriftAuditError(Exception):
    """Raised for source manifest drift audit failures."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit source manifest drift from source exports.")
    parser.add_argument("--config", required=True, help="Source import config YAML.")
    parser.add_argument("--drift-output", required=True, help="Per-import drift audit TSV.")
    parser.add_argument("--report-output", required=True, help="Summary report TSV.")
    parser.add_argument("--root", default=".", help="Repository root.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: object) -> bool:
    return normalize(value) in MISSING


def bool_value(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = normalize(value).lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return default


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def checksum(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def load_config(path: Path) -> dict:
    if not path.exists():
        raise DriftAuditError(f"Source import config does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise DriftAuditError(f"Source import config must be a YAML mapping: {path}")
    imports = data.get("imports", [])
    if not isinstance(imports, list):
        raise DriftAuditError("Source import config field 'imports' must be a list")
    return data


def audit(config_path: Path, root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], int]:
    config = load_config(config_path)
    rows: list[dict[str, str]] = []
    errors = 0
    with tempfile.TemporaryDirectory(prefix="source-manifest-drift-") as tmp:
        tmpdir = Path(tmp)
        regen_config = {"imports": []}
        output_by_import: dict[str, Path] = {}
        for index, spec in enumerate(config.get("imports", []), start=1):
            if not isinstance(spec, dict):
                rows.append({
                    "import_id": f"import_{index}",
                    "enabled": "NA",
                    "input_path": display_path(root, config_path),
                    "output_path": "NA",
                    "input_checksum": "",
                    "current_output_checksum": "",
                    "regenerated_output_checksum": "",
                    "status": "invalid_import_spec",
                    "severity": "error",
                    "message": "Import entry is not a mapping.",
                })
                errors += 1
                continue
            import_id = normalize(spec.get("import_id")) or f"import_{index}"
            enabled = bool_value(spec.get("enabled"), False)
            input_text = normalize(spec.get("input_path"))
            output_text = normalize(spec.get("output_path"))
            if not enabled:
                rows.append({
                    "import_id": import_id,
                    "enabled": "false",
                    "input_path": input_text,
                    "output_path": output_text,
                    "input_checksum": checksum(resolve(root, input_text)) if not is_missing(input_text) else "",
                    "current_output_checksum": checksum(resolve(root, output_text)) if not is_missing(output_text) else "",
                    "regenerated_output_checksum": "",
                    "status": "disabled_not_checked",
                    "severity": "info",
                    "message": "Import disabled; drift audit skipped.",
                })
                continue
            regen_output = tmpdir / f"{import_id}.tsv"
            rewritten = dict(spec)
            rewritten["output_path"] = regen_output.as_posix()
            rewritten["overwrite"] = True
            regen_config["imports"].append(rewritten)
            output_by_import[import_id] = regen_output

        regen_config_path = tmpdir / "source_imports.regenerated.yaml"
        regen_config_path.write_text(yaml.safe_dump(regen_config, sort_keys=False), encoding="utf-8")
        regen_report = tmpdir / "source_import_report.tsv"
        if regen_config["imports"]:
            import_errors, _warnings = import_source_manifests.run_imports(regen_config_path, regen_report)
            if import_errors:
                errors += import_errors

        for spec in config.get("imports", []):
            if not isinstance(spec, dict) or not bool_value(spec.get("enabled"), False):
                continue
            import_id = normalize(spec.get("import_id"))
            input_text = normalize(spec.get("input_path"))
            output_text = normalize(spec.get("output_path"))
            input_path = resolve(root, input_text)
            output_path = resolve(root, output_text)
            regen_output = output_by_import[import_id]
            input_hash = checksum(input_path)
            current_hash = checksum(output_path)
            regen_hash = checksum(regen_output)
            if not output_path.exists():
                status = "manifest_missing"
                severity = "error"
                message = "Configured output manifest does not exist."
            elif current_hash != regen_hash:
                status = "manifest_drift"
                severity = "error"
                message = "Configured source manifest differs from regeneration from source export."
            else:
                status = "in_sync"
                severity = "info"
                message = "Configured source manifest matches regenerated export output."
            if severity == "error":
                errors += 1
            rows.append({
                "import_id": import_id,
                "enabled": "true",
                "input_path": display_path(root, input_path),
                "output_path": display_path(root, output_path),
                "input_checksum": input_hash,
                "current_output_checksum": current_hash,
                "regenerated_output_checksum": regen_hash,
                "status": status,
                "severity": severity,
                "message": message,
            })
    report = [{"severity": "info", "item": "source_manifest_drift", "message": f"audited_imports={len(rows)}; errors={errors}"}]
    for status in sorted({row["status"] for row in rows}):
        count = sum(1 for row in rows if row["status"] == status)
        severity = "error" if any(row["status"] == status and row["severity"] == "error" for row in rows) else "info"
        report.append({"severity": severity, "item": status, "message": f"{count} row(s)."})
    return rows, report, errors


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    config_path = resolve(root, args.config)
    try:
        rows, report, errors = audit(config_path, root)
    except DriftAuditError as exc:
        rows = []
        report = [{"severity": "error", "item": "source_manifest_drift", "message": str(exc)}]
        errors = 1
    write_tsv(Path(args.drift_output), DRIFT_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Source manifest drift audit complete: rows={len(rows)}; errors={errors}.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
