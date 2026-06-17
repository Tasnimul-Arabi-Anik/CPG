#!/usr/bin/env python3
"""Self-test source work-order acceptance and intake lint scenarios."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from typing import Iterable

import check_source_work_order_acceptance as acceptance


TEST_COLUMNS = [
    "test_id",
    "scenario",
    "expected_acceptance_status",
    "observed_acceptance_status",
    "expected_blocking",
    "observed_blocking",
    "expected_issue_contains",
    "observed_raw_sequence_path_issues",
    "observed_provenance_note_issues",
    "status",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
EXPORT_HEADER = "accession\tgenome_id\thost_species\thost_strain\traw_sequence_path\tnotes\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for source work-order acceptance lint fields.")
    parser.add_argument("--output", required=True, help="Output self-test result TSV.")
    parser.add_argument("--report-output", required=True, help="Output self-test report TSV.")
    return parser.parse_args()


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def work_order(tmpdir: Path, export_name: str, minimum_rows: str = "1") -> dict[str, str]:
    return {
        "work_order_id": export_name,
        "source_id": "self_test_source",
        "expected_export_path": (tmpdir / f"{export_name}.tsv").as_posix(),
        "minimum_rows_to_add": minimum_rows,
        "required_fields": "genome_id;accession;raw_sequence_path;host_species;host_strain",
    }


def check_case(
    tmpdir: Path,
    test_id: str,
    scenario: str,
    export_body: str,
    expected_acceptance_status: str,
    expected_blocking: str,
    expected_issue_contains: str = "",
) -> dict[str, str]:
    work = work_order(tmpdir, test_id)
    write_text(Path(work["expected_export_path"]), export_body)
    observed = acceptance.check_one(tmpdir, work)
    raw_issues = observed.get("raw_sequence_path_issues", "")
    note_issues = observed.get("provenance_note_issues", "")
    observed_issues = ";".join(value for value in [raw_issues, note_issues] if value and value != "NA")
    status_ok = observed.get("acceptance_status") == expected_acceptance_status
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
        "expected_acceptance_status": expected_acceptance_status,
        "observed_acceptance_status": observed.get("acceptance_status", ""),
        "expected_blocking": expected_blocking,
        "observed_blocking": observed.get("blocking_issue", ""),
        "expected_issue_contains": expected_issue_contains or "NA",
        "observed_raw_sequence_path_issues": raw_issues or "NA",
        "observed_provenance_note_issues": note_issues or "NA",
        "status": "pass" if passed else "fail",
        "notes": ";".join(notes) if notes else "NA",
    }


def run_tests() -> list[dict[str, str]]:
    with tempfile.TemporaryDirectory(prefix="source-work-order-acceptance-") as tmp:
        tmpdir = Path(tmp)
        fasta = tmpdir / "fixtures" / "phage_1.fna"
        write_text(fasta, ">phage_1\nATGC\n")
        return [
            check_case(
                tmpdir,
                "accepted_existing_path",
                "accepted row with existing local raw_sequence_path and provenance notes",
                EXPORT_HEADER + f"ACC1\tphage_1\tKlebsiella pneumoniae\tKP1\t{fasta.as_posix()}\treviewed fixture\n",
                "accepted",
                "false",
            ),
            check_case(
                tmpdir,
                "accepted_missing_path_lint",
                "accepted row still reports missing local raw_sequence_path lint",
                EXPORT_HEADER + "ACC2\tphage_2\tKlebsiella pneumoniae\tKP2\tmissing/phage_2.fna\treviewed fixture\n",
                "accepted",
                "false",
                "missing_or_not_file",
            ),
            check_case(
                tmpdir,
                "accepted_missing_notes_lint",
                "accepted row still reports missing provenance notes lint",
                EXPORT_HEADER + f"ACC3\tphage_3\tKlebsiella pneumoniae\tKP3\t{fasta.as_posix()}\t\n",
                "accepted",
                "false",
                "notes_missing",
            ),
            check_case(
                tmpdir,
                "insufficient_required_values",
                "row missing required host strain remains blocking",
                EXPORT_HEADER + f"ACC4\tphage_4\tKlebsiella pneumoniae\t\t{fasta.as_posix()}\treviewed fixture\n",
                "insufficient_reviewed_rows",
                "true",
            ),
            check_case(
                tmpdir,
                "empty_export",
                "header-only export remains blocking for the work order",
                EXPORT_HEADER,
                "export_empty",
                "true",
            ),
        ]


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {"severity": "info", "item": "source_work_order_acceptance_self_test", "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}"}
    ]
    if failed:
        report.append({"severity": "error", "item": "source_work_order_acceptance_self_test", "message": "One or more acceptance self-tests failed."})
    else:
        report.append({"severity": "info", "item": "source_work_order_acceptance_self_test", "message": "All acceptance self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Source work-order acceptance self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
