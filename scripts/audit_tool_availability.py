#!/usr/bin/env python3
"""Audit configured command-line tools for reproducible workflow execution."""

from __future__ import annotations

import argparse
import csv
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Iterable


AVAILABILITY_COLUMNS = [
    "tool_id",
    "stage",
    "purpose",
    "command",
    "required_for_current_workflow",
    "availability_status",
    "executable_path",
    "version_command",
    "version_status",
    "version_output",
    "install_hint",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]


class ToolAuditError(Exception):
    """Raised for invalid tool audit configuration."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit configured tool availability.")
    parser.add_argument("--tools-config", required=True, help="Tool YAML config, usually config/tools.yaml.")
    parser.add_argument("--availability-output", required=True, help="Output tool availability TSV.")
    parser.add_argument("--report-output", required=True, help="Output audit report TSV.")
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise ToolAuditError("PyYAML is required to read tool configuration.") from exc
    if not path.exists():
        raise ToolAuditError(f"Tool config does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ToolAuditError("Tool config must contain a YAML mapping.")
    return data


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def bool_value(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = normalize(value).lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return default


def configured_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [normalize(item) for item in value if normalize(item)]
    return [part for part in shlex.split(str(value)) if part]


def report_row(severity: str, item: str, message: str) -> dict[str, str]:
    return {"severity": severity, "item": item, "message": message}


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def tool_specs(config: dict) -> list[dict]:
    audit = config.get("tool_audit", {})
    tools = audit.get("tools", []) if isinstance(audit, dict) else []
    if tools:
        if not isinstance(tools, list):
            raise ToolAuditError("tool_audit.tools must be a list")
        return [tool for tool in tools if isinstance(tool, dict)]
    return derive_planned_tool_specs(config)


def derive_planned_tool_specs(config: dict) -> list[dict]:
    planned = config.get("planned_tools", {})
    if not isinstance(planned, dict):
        return []
    derived: list[dict] = []
    for stage, values in sorted(planned.items()):
        if not isinstance(values, dict):
            continue
        for purpose, command in sorted(values.items()):
            command_text = normalize(command)
            if not command_text:
                continue
            derived.append(
                {
                    "tool_id": command_text,
                    "stage": stage,
                    "purpose": purpose,
                    "command": command_text,
                    "required_for_current_workflow": False,
                    "notes": "Derived from planned_tools; add explicit tool_audit entry for version command and install hint.",
                }
            )
    return derived


def run_version(command: str, version_args: list[str], timeout: int) -> tuple[str, str]:
    if not command or not version_args:
        return "not_checked", ""
    try:
        result = subprocess.run(
            [command, *version_args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "failed", str(exc)
    output = " ".join((result.stdout or "").strip().split())
    if len(output) > 500:
        output = output[:497] + "..."
    return ("ok" if result.returncode == 0 else "failed", output)


def audit_tool(tool: dict, default_timeout: int) -> tuple[dict[str, str], dict[str, str]]:
    tool_id = normalize(tool.get("tool_id")) or normalize(tool.get("command")) or "unnamed_tool"
    command = normalize(tool.get("command"))
    required = bool_value(tool.get("required_for_current_workflow"), False)
    version_args = configured_list(tool.get("version_args"))
    timeout = int(tool.get("version_timeout_seconds", default_timeout) or default_timeout)
    executable_path = shutil.which(command) if command else None

    if not command:
        availability_status = "not_configured"
    elif executable_path:
        availability_status = "available"
    else:
        availability_status = "missing"

    version_status = "not_checked"
    version_output = ""
    version_command = ""
    if executable_path and version_args:
        version_command = " ".join([command, *version_args])
        version_status, version_output = run_version(command, version_args, timeout)

    row = {
        "tool_id": tool_id,
        "stage": normalize(tool.get("stage")),
        "purpose": normalize(tool.get("purpose")),
        "command": command,
        "required_for_current_workflow": str(required).lower(),
        "availability_status": availability_status,
        "executable_path": executable_path or "",
        "version_command": version_command,
        "version_status": version_status,
        "version_output": version_output,
        "install_hint": normalize(tool.get("install_hint")),
        "notes": normalize(tool.get("notes")),
    }

    if availability_status == "available":
        severity = "info"
        message = "tool command is available"
    elif required:
        severity = "error"
        message = f"required tool command is {availability_status}"
    else:
        severity = "warning"
        message = f"optional/planned tool command is {availability_status}"
    return row, report_row(severity, tool_id, message)


def main() -> int:
    args = parse_args()
    try:
        config = load_yaml(Path(args.tools_config))
        audit = config.get("tool_audit", {}) if isinstance(config.get("tool_audit", {}), dict) else {}
        default_timeout = int(audit.get("default_version_timeout_seconds", 10) or 10)
        specs = tool_specs(config)
        rows: list[dict[str, str]] = []
        report: list[dict[str, str]] = []
        if not specs:
            report.append(report_row("warning", "tool_audit", "No tools configured for audit."))
        for spec in specs:
            row, message = audit_tool(spec, default_timeout)
            rows.append(row)
            report.append(message)
        write_tsv(Path(args.availability_output), AVAILABILITY_COLUMNS, rows)
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        errors = sum(1 for row in report if row["severity"] == "error")
        warnings = sum(1 for row in report if row["severity"] == "warning")
        print(f"Tool audit complete: {len(rows)} tools, {errors} errors, {warnings} warnings.")
        return 1 if errors else 0
    except ToolAuditError as exc:
        report = [report_row("error", "tool_audit", str(exc))]
        write_tsv(Path(args.availability_output), AVAILABILITY_COLUMNS, [])
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        print(f"Tool audit failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
