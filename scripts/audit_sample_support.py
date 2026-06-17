#!/usr/bin/env python3
"""Audit minimum sample support for H1-H6 before downstream hypothesis tests."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


HYPOTHESIS_COLUMNS = [
    "hypothesis",
    "support_status",
    "sample_rows",
    "cultured_phage_rows",
    "prophage_rows",
    "host_rows",
    "k_typed_rows",
    "o_typed_rows",
    "st_typed_rows",
    "phage_rows_with_host_metadata",
    "required_minima",
    "missing_support",
    "next_action",
]
SUMMARY_COLUMNS = [
    "metric",
    "value",
    "threshold",
    "status",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}

HYPOTHESIS_REQUIREMENTS = {
    "H1": ["min_cultured_phages", "min_host_genomes", "min_k_typed_records", "min_o_typed_records"],
    "H2": ["min_prophages", "min_host_genomes", "min_k_typed_records"],
    "H3": ["min_cultured_phages", "min_phage_rows_with_host_metadata"],
    "H4": ["min_cultured_phages", "min_host_genomes", "min_k_typed_records"],
    "H5": ["min_host_genomes", "min_prophages", "min_st_typed_records"],
    "H6": ["min_cultured_phages"],
}

DEFAULT_THRESHOLDS = {
    "min_total_records": 1,
    "min_cultured_phages": 1,
    "min_host_genomes": 1,
    "min_prophages": 1,
    "min_k_typed_records": 1,
    "min_o_typed_records": 1,
    "min_st_typed_records": 1,
    "min_phage_rows_with_host_metadata": 1,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit minimum sample support for H1-H6.")
    parser.add_argument("--samples", required=True, help="Built sample table TSV.")
    parser.add_argument("--thresholds", required=True, help="Threshold YAML file.")
    parser.add_argument("--hypothesis-output", required=True, help="Output H1-H6 sample support TSV.")
    parser.add_argument("--summary-output", required=True, help="Output sample support metric summary TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def load_thresholds(path: Path) -> dict[str, int]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise SystemExit("PyYAML is required for sample support auditing.") from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    configured = data.get("sample_support", {}) if isinstance(data, dict) else {}
    thresholds = dict(DEFAULT_THRESHOLDS)
    if isinstance(configured, dict):
        for key, value in configured.items():
            if key in thresholds:
                try:
                    thresholds[key] = int(value)
                except (TypeError, ValueError):
                    pass
    return thresholds


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def record_type(row: dict[str, str]) -> str:
    return row.get("record_type", "").strip().lower()


def has_any(row: dict[str, str], columns: Iterable[str]) -> bool:
    return any(not is_missing(row.get(column, "")) for column in columns)


def metrics(rows: list[dict[str, str]]) -> dict[str, int]:
    cultured = [row for row in rows if record_type(row) in {"phage", "cultured_phage"}]
    prophages = [row for row in rows if record_type(row) == "prophage"]
    hosts = [row for row in rows if record_type(row) == "host"]
    return {
        "min_total_records": len(rows),
        "min_cultured_phages": len(cultured),
        "min_host_genomes": len(hosts),
        "min_prophages": len(prophages),
        "min_k_typed_records": sum(1 for row in rows if not is_missing(row.get("K_type", ""))),
        "min_o_typed_records": sum(1 for row in rows if not is_missing(row.get("O_type", ""))),
        "min_st_typed_records": sum(1 for row in rows if not is_missing(row.get("ST", ""))),
        "min_phage_rows_with_host_metadata": sum(1 for row in cultured if has_any(row, ["isolation_host", "host_species", "host_strain"])),
    }


def metric_label(metric: str) -> str:
    return metric.removeprefix("min_")


def main() -> None:
    args = parse_args()
    _, rows = read_tsv(Path(args.samples))
    thresholds = load_thresholds(Path(args.thresholds))
    observed = metrics(rows)

    summary_rows: list[dict[str, str]] = []
    for metric, threshold in thresholds.items():
        value = observed.get(metric, 0)
        status = "pass" if value >= threshold else "fail"
        summary_rows.append({
            "metric": metric,
            "value": str(value),
            "threshold": str(threshold),
            "status": status,
            "notes": f"Observed {metric_label(metric)} count {value}; required minimum {threshold}.",
        })

    hypothesis_rows: list[dict[str, str]] = []
    for hypothesis, required_metrics in HYPOTHESIS_REQUIREMENTS.items():
        missing = [metric for metric in required_metrics if observed.get(metric, 0) < thresholds.get(metric, 0)]
        status = "ready_minimum_sample_support" if not missing else "blocked_minimum_sample_support"
        required_text = ";".join(f"{metric}>={thresholds.get(metric, 0)}" for metric in required_metrics)
        missing_text = ";".join(f"{metric}:{observed.get(metric, 0)}/{thresholds.get(metric, 0)}" for metric in missing) if missing else "NA"
        action = "No action required for minimum sample support." if not missing else "Populate/enable source exports until missing support metrics meet configured thresholds."
        hypothesis_rows.append({
            "hypothesis": hypothesis,
            "support_status": status,
            "sample_rows": str(len(rows)),
            "cultured_phage_rows": str(observed["min_cultured_phages"]),
            "prophage_rows": str(observed["min_prophages"]),
            "host_rows": str(observed["min_host_genomes"]),
            "k_typed_rows": str(observed["min_k_typed_records"]),
            "o_typed_rows": str(observed["min_o_typed_records"]),
            "st_typed_rows": str(observed["min_st_typed_records"]),
            "phage_rows_with_host_metadata": str(observed["min_phage_rows_with_host_metadata"]),
            "required_minima": required_text,
            "missing_support": missing_text,
            "next_action": action,
        })

    blocked = [row for row in hypothesis_rows if row["support_status"].startswith("blocked")]
    report_rows = [
        {"severity": "info", "item": "sample_support", "message": f"sample_rows={len(rows)}; hypotheses={len(hypothesis_rows)}; blocked={len(blocked)}"},
    ]
    if blocked:
        report_rows.append({"severity": "warning", "item": "sample_support", "message": "One or more hypotheses lack minimum sample support."})
    write_tsv(Path(args.hypothesis_output), HYPOTHESIS_COLUMNS, hypothesis_rows)
    write_tsv(Path(args.summary_output), SUMMARY_COLUMNS, summary_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report_rows)
    print(f"Audited sample support for {len(hypothesis_rows)} hypotheses from {len(rows)} rows.")


if __name__ == "__main__":
    main()
