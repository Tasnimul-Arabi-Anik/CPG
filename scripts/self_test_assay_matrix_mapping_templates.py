#!/usr/bin/env python3
"""Self-test assay matrix source-ID mapping template generation."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from typing import Iterable

import create_assay_matrix_mapping_templates as templates
import normalize_assay_matrix as normalizer


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for assay matrix mapping template generation.")
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


def write_config(path: Path, matrix: Path, phage_map: Path, host_map: Path, output: Path, report: Path, enabled: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "sources:",
                "  - source_id: fixture_matrix",
                f"    enabled: {'true' if enabled else 'false'}",
                f"    matrix_path: {matrix.as_posix()}",
                "    delimiter: comma",
                "    host_id_column: auto_first_column",
                f"    phage_id_map: {phage_map.as_posix()}",
                f"    host_id_map: {host_map.as_posix()}",
                f"    output_path: {output.as_posix()}",
                f"    report_output: {report.as_posix()}",
                "    use_source_ids_as_canonical: false",
                "    study_id: fixture_study",
                "    panel_id: fixture_panel",
                "    assay_type: spot",
                "    evidence_tier: supplementary_matrix",
                "    reference: fixture_reference",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


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


def run_template(config: Path, root: Path, report: Path, update: bool = False) -> int:
    args = argparse.Namespace(
        config=config.as_posix(),
        report_output=report.as_posix(),
        root=root.as_posix(),
        only_source="fixture_matrix",
        include_disabled=True,
        update_maps=update,
        phage_manifest="results/seed/qc/phage_genome_manifest.tsv",
        host_metadata="results/seed/host_features/host_metadata.tsv",
    )
    return templates.run(args)


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="assay-matrix-map-templates-") as tmp:
        root = Path(tmp)
        matrix = root / "source" / "matrix.csv"
        config = root / "config" / "assay_matrix_sources.yaml"
        phage_map = root / "data" / "metadata" / "assay_source_exports" / "phage_map.tsv"
        host_map = root / "data" / "metadata" / "assay_source_exports" / "host_map.tsv"
        output = root / "data" / "metadata" / "assay_source_exports" / "reviewed.tsv"
        matrix_report = root / "results" / "qc" / "matrix_report.tsv"
        template_report = root / "results" / "qc" / "template_report.tsv"
        phage_manifest = root / "results" / "seed" / "qc" / "phage_genome_manifest.tsv"
        host_metadata = root / "results" / "seed" / "host_features" / "host_metadata.tsv"

        write_csv(matrix, [["", "phageA", "phageB"], ["hostA", "1", "0"], ["hostB", "", "1"]])
        write_tsv(
            phage_manifest,
            ["record_type", "genome_id"],
            [
                {"record_type": "phage", "genome_id": "phageA"},
                {"record_type": "phage", "genome_id": "canonical_phage_B"},
                {"record_type": "host", "genome_id": "hostA"},
            ],
        )
        write_tsv(host_metadata, ["host_genome_id"], [{"host_genome_id": "hostA"}])
        write_tsv(
            phage_map,
            ["source_id", "canonical_id", "review_status", "notes"],
            [{"source_id": "phageA", "canonical_id": "phageA", "review_status": "reviewed", "notes": "fixture reviewed"}],
        )
        write_tsv(
            host_map,
            ["source_id", "canonical_id", "review_status", "notes"],
            [{"source_id": "hostA", "canonical_id": "hostA", "review_status": "reviewed", "notes": "fixture reviewed"}],
        )
        write_config(config, matrix, phage_map, host_map, output, matrix_report)

        rc = run_template(config, root, template_report, update=False)
        report_rows = read_rows(template_report)
        observed = "ok" if rc == 0 and len(report_rows) == 5 and len(read_rows(host_map)) == 1 else "bad_output"
        tests.append(result("report_only", "report-only mode does not modify mapping files", "ok", observed))

        rc = run_template(config, root, template_report, update=True)
        phage_rows = read_rows(phage_map)
        host_rows = read_rows(host_map)
        pending_phage = [row for row in phage_rows if row["source_id"] == "phageB" and row["review_status"] == "pending"]
        pending_host = [row for row in host_rows if row["source_id"] == "hostB" and row["review_status"] == "pending"]
        observed = "ok" if rc == 0 and len(pending_phage) == 1 and len(host_rows) == 2 and pending_host else "bad_output"
        tests.append(result("update_adds_pending", "update mode appends missing source IDs as pending rows", "ok", observed))

        norm_rc = normalizer.run(config, root, only_source="fixture_matrix")
        assay_rows = read_rows(output)
        observed = "ok" if norm_rc == 0 and len(assay_rows) == 1 and assay_rows[0]["phage_id"] == "phageA" and assay_rows[0]["host_id"] == "hostA" else "bad_output"
        tests.append(result("pending_rows_skipped", "normalizer ignores pending rows until review_status is reviewed", "ok", observed))

        for path in (phage_map, host_map):
            rows = read_rows(path)
            for row in rows:
                if row["source_id"] in {"phageB", "hostB"}:
                    row["review_status"] = "reviewed"
                    if row["source_id"] == "hostB":
                        row["canonical_id"] = "canonical_host_B"
                    if row["source_id"] == "phageB" and not row["canonical_id"]:
                        row["canonical_id"] = "canonical_phage_B"
            write_tsv(path, ["source_id", "canonical_id", "review_status", "notes"], rows)
        norm_rc = normalizer.run(config, root, only_source="fixture_matrix")
        assay_rows = read_rows(output)
        observed = "ok" if norm_rc == 0 and len(assay_rows) == 3 else "bad_output"
        tests.append(result("reviewed_rows_enabled", "reviewed mapping rows are used by normalizer", "ok", observed))

        write_tsv(
            phage_map,
            ["source_id", "canonical_id", "review_status", "notes"],
            [
                {"source_id": "phageA", "canonical_id": "phageA", "review_status": "reviewed", "notes": "fixture"},
                {"source_id": "phageA", "canonical_id": "phageA", "review_status": "reviewed", "notes": "duplicate"},
            ],
        )
        try:
            run_template(config, root, template_report, update=False)
        except templates.MappingTemplateError:
            observed = "ok"
        else:
            observed = "no_error"
        tests.append(result("duplicate_source_mapping_fails", "duplicate source IDs in mapping file are blocking", "ok", observed))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {
            "severity": "info",
            "item": "assay_matrix_mapping_template_self_test",
            "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}",
        }
    ]
    if failed:
        report.append({"severity": "error", "item": "assay_matrix_mapping_template_self_test", "message": "One or more mapping-template self-tests failed."})
    else:
        report.append({"severity": "info", "item": "assay_matrix_mapping_template_self_test", "message": "All mapping-template self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Assay matrix mapping template self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
