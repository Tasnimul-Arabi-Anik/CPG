#!/usr/bin/env python3
"""Self-test reviewed source export validation scenarios."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from typing import Iterable

import validate_source_exports


TEST_COLUMNS = [
    "test_id",
    "scenario",
    "expected_status",
    "observed_status",
    "expected_blocking",
    "observed_blocking",
    "expected_issue_contains",
    "observed_issues",
    "status",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for reviewed source export validation.")
    parser.add_argument("--output", required=True, help="Output self-test result TSV.")
    parser.add_argument("--report-output", required=True, help="Output self-test report TSV.")
    return parser.parse_args()


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="	")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def scenario_query(tmpdir: Path, export_name: str) -> dict[str, str]:
    return {
        "query_id": export_name,
        "source_id": "self_test_source",
        "record_layer": "cultured_phages",
        "target_database": "self_test",
        "expected_export_path": (tmpdir / f"{export_name}.tsv").as_posix(),
        "expected_columns": "accession;genome_id;host_species;year;genome_length;gc_percent;phage_lifestyle;notes",
        "identity_columns_required": "accession;genome_id",
    }


def check_case(
    tmpdir: Path,
    test_id: str,
    scenario: str,
    export_body: str,
    expected_status: str,
    expected_blocking: str,
    expected_issue_contains: str = "",
) -> dict[str, str]:
    query = scenario_query(tmpdir, test_id)
    write_text(Path(query["expected_export_path"]), export_body)
    observed = validate_source_exports.validate_one(tmpdir, query, {})
    observed_issues = observed.get("row_format_issues", "") or observed.get("duplicate_identity_values", "") or observed.get("provenance_warnings", "")
    status_ok = observed.get("validation_status") == expected_status
    blocking_ok = observed.get("blocking_issue") == expected_blocking
    issue_ok = True if not expected_issue_contains else expected_issue_contains in observed_issues
    passed = status_ok and blocking_ok and issue_ok
    notes = []
    if not status_ok:
        notes.append("status_mismatch")
    if not blocking_ok:
        notes.append("blocking_mismatch")
    if not issue_ok:
        notes.append("issue_mismatch")
    return {
        "test_id": test_id,
        "scenario": scenario,
        "expected_status": expected_status,
        "observed_status": observed.get("validation_status", ""),
        "expected_blocking": expected_blocking,
        "observed_blocking": observed.get("blocking_issue", ""),
        "expected_issue_contains": expected_issue_contains or "NA",
        "observed_issues": observed_issues or "NA",
        "status": "pass" if passed else "fail",
        "notes": ";".join(notes) if notes else "NA",
    }


def run_tests() -> list[dict[str, str]]:
    header = "accession\tgenome_id\thost_species\tyear\tgenome_length\tgc_percent\tphage_lifestyle\tnotes\n"
    with tempfile.TemporaryDirectory(prefix="source-export-validator-") as tmp:
        tmpdir = Path(tmp)
        return [
            check_case(
                tmpdir,
                "valid_export",
                "well-formed populated reviewed export passes",
                header + "ACC1\tgenome_1\tKlebsiella pneumoniae\t2024\t120000\t52.4\tvirulent\treviewed fixture\n",
                "export_ready",
                "false",
            ),
            check_case(
                tmpdir,
                "invalid_year",
                "malformed year is blocking",
                header + "ACC2\tgenome_2\tKlebsiella pneumoniae\t2024-01\t120000\t52.4\tvirulent\treviewed fixture\n",
                "export_row_format_invalid",
                "true",
                "year:2024-01",
            ),
            check_case(
                tmpdir,
                "invalid_gc",
                "out-of-range GC percent is blocking",
                header + "ACC3\tgenome_3\tKlebsiella pneumoniae\t2024\t120000\t150\tvirulent\treviewed fixture\n",
                "export_row_format_invalid",
                "true",
                "gc_percent:150",
            ),
            check_case(
                tmpdir,
                "invalid_lifestyle",
                "unsupported lifestyle label is blocking",
                header + "ACC4\tgenome_4\tKlebsiella pneumoniae\t2024\t120000\t52.4\tunknown-ish\treviewed fixture\n",
                "export_row_format_invalid",
                "true",
                "phage_lifestyle:unknown-ish",
            ),
            check_case(
                tmpdir,
                "missing_identity",
                "row missing all identity values is blocking",
                header + "\t\tKlebsiella pneumoniae\t2024\t120000\t52.4\tvirulent\treviewed fixture\n",
                "export_rows_missing_identity",
                "true",
            ),
            check_case(
                tmpdir,
                "missing_notes",
                "missing notes is a warning but not blocking",
                header + "ACC5\tgenome_5\tKlebsiella pneumoniae\t2024\t120000\t52.4\tvirulent\t\n",
                "export_ready",
                "false",
                "notes_missing",
            ),
        ]


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {"severity": "info", "item": "source_export_validation_self_test", "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}"}
    ]
    if failed:
        report.append({"severity": "error", "item": "source_export_validation_self_test", "message": "One or more validator self-tests failed."})
    else:
        report.append({"severity": "info", "item": "source_export_validation_self_test", "message": "All validator self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Source export validation self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
