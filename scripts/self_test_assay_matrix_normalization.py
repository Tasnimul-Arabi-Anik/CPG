#!/usr/bin/env python3
"""Self-test phage-host assay matrix normalization."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from typing import Iterable

import normalize_assay_matrix as normalizer
from validate_phage_host_assays import ASSAY_COLUMNS


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for assay matrix normalization.")
    parser.add_argument("--output", required=True, help="Output self-test result TSV.")
    parser.add_argument("--report-output", required=True, help="Output self-test report TSV.")
    return parser.parse_args()


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


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


def write_config(
    path: Path,
    matrix: Path,
    output: Path,
    report: Path,
    phage_map: Path,
    host_map: Path,
    extra: list[str] | None = None,
) -> None:
    lines = [
        "sources:",
        "  - source_id: fixture_matrix",
        "    enabled: true",
        f"    matrix_path: {matrix.as_posix()}",
        "    delimiter: comma",
        "    host_id_column: auto_first_column",
        f"    phage_id_map: {phage_map.as_posix()}",
        f"    host_id_map: {host_map.as_posix()}",
        f"    output_path: {output.as_posix()}",
        f"    report_output: {report.as_posix()}",
        "    study_id: fixture_study",
        "    panel_id: fixture_panel",
        "    assay_type: spot",
        "    evidence_tier: supplementary_matrix",
        "    reference: fixture_reference",
        "    positive_outcome_tier: initial_interaction",
        "    negative_outcome_tier: tested_negative",
    ]
    if extra:
        lines.extend(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_config(config: Path, root: Path) -> int:
    return normalizer.run(config, root)


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="assay-matrix-normalization-") as tmp:
        root = Path(tmp)
        source_dir = root / "source"
        out_dir = root / "data" / "metadata" / "assay_source_exports"
        report_dir = root / "results" / "qc"
        config = root / "config" / "assay_matrix_sources.yaml"
        matrix = source_dir / "matrix.csv"
        phage_map = source_dir / "phage_map.tsv"
        host_map = source_dir / "host_map.tsv"
        output = out_dir / "reviewed.tsv"
        report = report_dir / "report.tsv"

        write_csv(matrix, [["", "phageA", "phageB"], ["hostA", "1.0", "0.0"], ["hostB", "", "1.0"]])
        write_tsv(
            phage_map,
            ["source_id", "canonical_id", "review_status", "notes"],
            [
                {"source_id": "phageA", "canonical_id": "canonical_phage_A", "review_status": "reviewed", "notes": "fixture"},
                {"source_id": "phageB", "canonical_id": "canonical_phage_B", "review_status": "reviewed", "notes": "fixture"},
            ],
        )
        write_tsv(
            host_map,
            ["source_id", "canonical_id", "review_status", "notes"],
            [
                {"source_id": "hostA", "canonical_id": "canonical_host_A", "review_status": "reviewed", "notes": "fixture"},
                {"source_id": "hostB", "canonical_id": "canonical_host_B", "review_status": "reviewed", "notes": "fixture"},
            ],
        )
        write_config(config, matrix, output, report, phage_map, host_map)
        rc = run_config(config, root)
        rows = read_rows(output)
        observed = "ok" if rc == 0 and len(rows) == 3 and rows[0]["phage_id"] == "canonical_phage_A" and rows[1]["spot_result"] == "negative" else "bad_output"
        tests.append(result("mapped_matrix_rows", "mapped 1/0 matrix cells become canonical spot-test assay rows", "ok", observed))

        write_tsv(host_map, ["source_id", "canonical_id", "review_status", "notes"], [{"source_id": "hostA", "canonical_id": "canonical_host_A", "review_status": "reviewed", "notes": "fixture"}])
        write_config(config, matrix, output, report, phage_map, host_map)
        rc = run_config(config, root)
        rows = read_rows(output)
        report_rows = read_rows(report)
        unresolved_warnings = [row for row in report_rows if row["field"] == "entity_mapping" and row["severity"] == "warning"]
        observed = "ok" if rc == 0 and len(rows) == 2 and len(unresolved_warnings) == 1 else "bad_output"
        tests.append(result("unresolved_entities_skipped", "unmapped tested cells are reported and skipped without entering the export", "ok", observed))

        previous = output.read_text(encoding="utf-8")
        write_csv(matrix, [["", "phageA"], ["hostA", "maybe"]])
        write_config(config, matrix, output, report, phage_map, host_map)
        rc = run_config(config, root)
        preserved = output.read_text(encoding="utf-8") == previous
        observed = "ok" if rc != 0 and preserved else "bad_output"
        tests.append(result("malformed_value_preserves_output", "malformed matrix values fail without rewriting prior output", "ok", observed))

        write_csv(matrix, [["", "phageA"], ["hostA", "1"]])
        write_tsv(
            phage_map,
            ["source_id", "canonical_id", "review_status", "notes"],
            [
                {"source_id": "phageA", "canonical_id": "canonical_phage_A", "review_status": "reviewed", "notes": "fixture"},
                {"source_id": "phageA", "canonical_id": "different_phage_A", "review_status": "reviewed", "notes": "fixture"},
            ],
        )
        write_config(config, matrix, output, report, phage_map, host_map)
        rc = run_config(config, root)
        observed = "ok" if rc != 0 else "no_error"
        tests.append(result("ambiguous_mapping_fails", "a source identifier mapping to multiple canonical IDs is blocking", "ok", observed))

        write_tsv(phage_map, ["source_id", "canonical_id", "review_status", "notes"], [{"source_id": "phageA", "canonical_id": "canonical_phage_A", "review_status": "reviewed", "notes": "fixture"}])
        write_config(config, matrix, matrix, report, phage_map, host_map)
        rc = run_config(config, root)
        observed = "ok" if rc != 0 else "no_error"
        tests.append(result("path_collision_fails", "matrix input cannot collide with canonical output path", "ok", observed))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {
            "severity": "info",
            "item": "assay_matrix_normalization_self_test",
            "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}",
        }
    ]
    if failed:
        report.append({"severity": "error", "item": "assay_matrix_normalization_self_test", "message": "One or more assay matrix normalization self-tests failed."})
    else:
        report.append({"severity": "info", "item": "assay_matrix_normalization_self_test", "message": "All assay matrix normalization self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Assay matrix normalization self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
