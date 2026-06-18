#!/usr/bin/env python3
"""Self-test reviewed-row filtering in source manifest imports."""

from __future__ import annotations

import argparse
import csv
import os
import tempfile
from pathlib import Path
from typing import Iterable

import import_source_manifests as importer


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for source manifest import behavior.")
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


def write_config(path: Path, export: Path, manifest: Path, review_statuses: str) -> None:
    path.write_text(
        "\n".join(
            [
                "imports:",
                "  - import_id: reviewed_filter_fixture",
                "    enabled: true",
                f"    input_path: {export.as_posix()}",
                f"    output_path: {manifest.as_posix()}",
                "    delimiter: tab",
                "    overwrite: true",
                "    source_label: fixture",
                "    record_type_default: phage",
                "    require_klebsiella: true",
                "    require_phage_keyword: true",
                f"    required_note_review_statuses: {review_statuses}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def run_import(config: Path, report: Path, root: Path) -> tuple[int, int]:
    old_cwd = Path.cwd()
    try:
        os.chdir(root)
        return importer.run_imports(config, report)
    finally:
        os.chdir(old_cwd)


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="source-manifest-import-") as tmp:
        root = Path(tmp)
        export = root / "source_exports" / "phages.tsv"
        manifest = root / "source_manifests" / "phages.tsv"
        report = root / "results" / "source_import_report.tsv"
        config = root / "source_imports.yaml"
        write_tsv(
            export,
            ["genome_id", "host_species", "raw_sequence_path", "notes"],
            [
                {
                    "genome_id": "reviewed_phage",
                    "host_species": "Klebsiella pneumoniae",
                    "raw_sequence_path": "NA",
                    "notes": "source_id=reviewed_phage; review_status=reviewed; phage source identity reviewed",
                },
                {
                    "genome_id": "pending_phage",
                    "host_species": "Klebsiella pneumoniae",
                    "raw_sequence_path": "NA",
                    "notes": "source_id=pending_phage; review_status=pending_entity_review",
                },
            ],
        )
        write_config(config, export, manifest, "[reviewed, accepted, approved]")
        errors, warnings = run_import(config, report, root)
        rows = read_rows(manifest)
        report_rows = read_rows(report)
        skipped = [row for row in report_rows if row["field"] == "skipped_review_status"]
        observed = f"errors={errors};warnings={warnings};rows={len(rows)};genome_id={rows[0]['genome_id'] if rows else 'NA'};skipped={len(skipped)}"
        tests.append(result("review_status_filter", "only reviewed note-status rows enter the source manifest", "errors=0;warnings=1;rows=1;genome_id=reviewed_phage;skipped=1", observed))

        write_config(config, export, manifest, "{nested: invalid}")
        try:
            run_import(config, report, root)
            observed = "no_error"
        except importer.ImportErrorConfig:
            observed = "raised"
        tests.append(result("invalid_review_status_config", "invalid review-status filter config is blocking", "raised", observed))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {
            "severity": "info",
            "item": "source_manifest_import_self_test",
            "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}",
        }
    ]
    if failed:
        report.append({"severity": "error", "item": "source_manifest_import_self_test", "message": "One or more source manifest import self-tests failed."})
    else:
        report.append({"severity": "info", "item": "source_manifest_import_self_test", "message": "All source manifest import self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Source manifest import self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
