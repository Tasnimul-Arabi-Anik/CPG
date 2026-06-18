#!/usr/bin/env python3
"""Self-test PhageHostLearn host archive audit."""

from __future__ import annotations

import argparse
import csv
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

import audit_phagehostlearn_host_archive as audit


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for PhageHostLearn host archive audit.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report-output", required=True)
    return parser.parse_args()


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def result(test_id: str, scenario: str, expected: str, observed: str, notes: str = "NA") -> dict[str, str]:
    passed = expected == observed
    return {
        "test_id": test_id,
        "scenario": scenario,
        "expected_status": expected,
        "observed_status": observed,
        "status": "pass" if passed else "fail",
        "notes": "NA" if passed else notes,
    }


def host_row(source_id: str) -> dict[str, str]:
    return {
        "genome_id": f"phagehostlearn_2024_host_{source_id}",
        "accession": "NA",
        "host_species": "Klebsiella pneumoniae species complex",
        "host_strain": source_id,
        "country": "NA",
        "year": "NA",
        "K_type": "NA",
        "O_type": "NA",
        "ST": "NA",
        "AMR_markers": "NA",
        "virulence_markers": "NA",
        "raw_sequence_path": "NA",
        "notes": f"source_id={source_id}; review_status=pending_entity_review",
    }


def run_audit(root: Path, host_rows: list[dict[str, str]], archive: Path | None) -> tuple[int, list[dict[str, str]]]:
    host_export = root / "hosts.tsv"
    audit_output = root / "audit.tsv"
    report_output = root / "report.tsv"
    columns = ["genome_id", "accession", "host_species", "host_strain", "country", "year", "K_type", "O_type", "ST", "AMR_markers", "virulence_markers", "raw_sequence_path", "notes"]
    write_tsv(host_export, columns, host_rows)
    args = argparse.Namespace(
        host_export=host_export.as_posix(),
        archive=(archive or root / "missing.zip").as_posix(),
        audit_output=audit_output.as_posix(),
        report_output=report_output.as_posix(),
        root=root.as_posix(),
    )
    rc = audit.run(args)
    return rc, read_rows(audit_output)


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="phagehostlearn-host-archive-") as tmp:
        root = Path(tmp)
        archive = root / "klebsiella_genomes.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("fasta_files/hostA.fasta", ">hostA\nACGT\n")
            handle.writestr("fasta_files/hostB.fasta", ">hostB\nACGT\n")
            handle.writestr("fasta_files/hostA.fasta.ndb", "index")
            handle.writestr("__MACOSX/fasta_files/._hostA.fasta", "mac")
        rc, rows = run_audit(root, [host_row("hostA"), host_row("hostB"), host_row("hostC")], archive)
        counts = {status: sum(1 for row in rows if row["status"] == status) for status in {row["status"] for row in rows}}
        observed = f"present={counts.get('sequence_member_present', 0)};missing={counts.get('sequence_member_missing', 0)};rc={rc}"
        tests.append(result("archive_membership", "host export rows are matched against FASTA members", "present=2;missing=1;rc=0", observed))

        rc, rows = run_audit(root, [host_row("hostA")], None)
        observed = rows[0]["status"] + ":" + rows[0]["severity"] + f":rc={rc}"
        tests.append(result("archive_missing_warns", "missing archive is a warning-only review blocker", "archive_missing:warning:rc=0", observed))

        dup_archive = root / "duplicate.zip"
        with zipfile.ZipFile(dup_archive, "w") as handle:
            handle.writestr("fasta_files/a/hostA.fasta", ">hostA\nACGT\n")
            handle.writestr("fasta_files/b/hostA.fasta", ">hostA\nACGT\n")
        rc, rows = run_audit(root, [host_row("hostA")], dup_archive)
        observed = rows[0]["status"] + ":" + rows[0]["severity"] + f":rc={rc}"
        tests.append(result("duplicate_member_fails", "duplicate FASTA basename is blocking", "duplicate_archive_member:error:rc=1", observed))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [{"severity": "info", "item": "phagehostlearn_host_archive_self_test", "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}"}]
    if failed:
        report.append({"severity": "error", "item": "phagehostlearn_host_archive_self_test", "message": "One or more host archive self-tests failed."})
    else:
        report.append({"severity": "info", "item": "phagehostlearn_host_archive_self_test", "message": "All host archive self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"PhageHostLearn host archive self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
