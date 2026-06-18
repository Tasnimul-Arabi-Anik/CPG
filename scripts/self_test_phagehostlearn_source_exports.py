#!/usr/bin/env python3
"""Self-test PhageHostLearn benchmark source export builder."""

from __future__ import annotations

import argparse
import csv
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

import create_phagehostlearn_source_exports as builder


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for PhageHostLearn source export builder.")
    parser.add_argument("--output", required=True, help="Output self-test result TSV.")
    parser.add_argument("--report-output", required=True, help="Output self-test report TSV.")
    return parser.parse_args()


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def write_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerows(rows)


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


def make_args(root: Path, matrix: Path, zip_path: Path, out: Path) -> argparse.Namespace:
    return argparse.Namespace(
        matrix=matrix.as_posix(),
        phage_zip=zip_path.as_posix(),
        phage_export_output=(out / "phages.tsv").as_posix(),
        host_export_output=(out / "hosts.tsv").as_posix(),
        phage_map_output=(out / "phage_map.tsv").as_posix(),
        host_map_output=(out / "host_map.tsv").as_posix(),
        report_output=(out / "report.tsv").as_posix(),
        root=root.as_posix(),
        study_id="fixture_study",
        source_reference="fixture_reference",
    )


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="phagehostlearn-source-export-") as tmp:
        root = Path(tmp)
        matrix = root / "source" / "matrix.csv"
        zip_path = root / "source" / "phages.zip"
        out = root / "out"
        write_csv(matrix, [["", "phageA", "phageB"], ["hostA", "1", "0"], ["hostB", "", "1"]])
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("phages_genomes/phageA.fasta", ">phageA\nACGTACGT\n")
            archive.writestr("__MACOSX/phages_genomes/._phageA.fasta", "ignored")
            archive.writestr("phages_genomes/phageB.fasta", ">phageB\nGCGC\n")
        rc = builder.run(make_args(root, matrix, zip_path, out))
        phages = read_rows(out / "phages.tsv")
        hosts = read_rows(out / "hosts.tsv")
        phage_map = read_rows(out / "phage_map.tsv")
        host_map = read_rows(out / "host_map.tsv")
        report = read_rows(out / "report.tsv")
        observed = "ok" if rc == 0 and len(phages) == 2 and len(hosts) == 2 and len(phage_map) == 2 and len(host_map) == 2 else "bad_counts"
        tests.append(result("exports_created", "matrix source IDs create phage, host, and map exports", "ok", observed))
        observed = "ok" if phages[0]["genome_id"].startswith("fixture_study_phage_") and hosts[0]["genome_id"].startswith("fixture_study_host_") else "bad_ids"
        tests.append(result("canonical_ids_prefilled", "exports use deterministic benchmark canonical IDs", "ok", observed))
        observed = "ok" if {row["review_status"] for row in phage_map + host_map} == {"pending"} else "bad_review_status"
        tests.append(result("maps_pending", "generated source-ID maps remain pending until review", "ok", observed))
        observed = "ok" if phages[0]["genome_length"] in {"8", "4"} and phages[0]["gc_percent"] != "NA" else "bad_fasta_stats"
        tests.append(result("phage_zip_stats", "phage zip FASTA members provide length and GC metadata", "ok", observed))
        observed = "ok" if any(row["item"] == "matrix" and "tested_cells=3" in row["message"] for row in report) else "bad_report"
        tests.append(result("report_counts", "report records tested cell counts", "ok", observed))
        bad_args = make_args(root, matrix, zip_path, out)
        bad_args.report_output = bad_args.phage_export_output
        try:
            builder.run(bad_args)
        except builder.PhageHostLearnExportError:
            observed = "ok"
        else:
            observed = "no_error"
        tests.append(result("path_collision_fails", "output path collisions are rejected", "ok", observed))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {
            "severity": "info",
            "item": "phagehostlearn_source_export_self_test",
            "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}",
        }
    ]
    if failed:
        report.append({"severity": "error", "item": "phagehostlearn_source_export_self_test", "message": "One or more PhageHostLearn export self-tests failed."})
    else:
        report.append({"severity": "info", "item": "phagehostlearn_source_export_self_test", "message": "All PhageHostLearn export self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"PhageHostLearn source export self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
