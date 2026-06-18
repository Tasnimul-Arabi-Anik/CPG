#!/usr/bin/env python3
"""Self-test reviewed phage-host assay source import."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from typing import Iterable

import import_phage_host_assays as importer
from validate_phage_host_assays import ASSAY_COLUMNS, RELATIONSHIP_COLUMNS


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for phage-host assay source import.")
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


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_config(path: Path, source: Path, enabled: bool = True, defaults: dict[str, str] | None = None) -> None:
    defaults = defaults or {}
    lines = [
        "imports:",
        "  - import_id: fixture_assays",
        f"    enabled: {'true' if enabled else 'false'}",
        f"    input_path: {source.as_posix()}",
        "    delimiter: tab",
        "    derive_relationships: true",
        f"    study_id_default: {defaults.get('study_id_default', 'fixture_study')}",
        f"    panel_id_default: {defaults.get('panel_id_default', 'fixture_panel')}",
        f"    assay_type_default: {defaults.get('assay_type_default', 'spot')}",
        f"    evidence_tier_default: {defaults.get('evidence_tier_default', 'supplementary_matrix')}",
        f"    reference_default: {defaults.get('reference_default', 'fixture_reference')}",
        f"    outcome_tier_default: {defaults.get('outcome_tier_default', 'initial_interaction')}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def run_import(root: Path, config: Path, assays: Path, relationships: Path, report: Path) -> int:
    try:
        assay_rows, relationship_rows, reports, errors = importer.import_assays(config, assays, relationships, root)
    except importer.AssayImportError:
        return 1
    importer.write_tsv_atomic(report, importer.REPORT_COLUMNS, reports)
    if not errors:
        importer.write_tsv_atomic(assays, ASSAY_COLUMNS, assay_rows)
        importer.write_tsv_atomic(relationships, RELATIONSHIP_COLUMNS, relationship_rows)
    return errors


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="phage-host-assay-import-") as tmp:
        root = Path(tmp)
        export_dir = root / "data" / "metadata" / "assay_source_exports"
        export_dir.mkdir(parents=True)
        out_dir = root / "results" / "seed" / "metadata"
        report_dir = root / "results" / "seed" / "qc"
        config = root / "config" / "assay_imports.yaml"
        config.parent.mkdir()

        header_source = export_dir / "header.tsv"
        write_tsv(header_source, ASSAY_COLUMNS, [])
        assays = out_dir / "phage_host_assays.tsv"
        relationships = out_dir / "phage_host_relationships.tsv"
        report = report_dir / "assay_import_report.tsv"
        write_config(config, header_source)
        errors = run_import(root, config, assays, relationships, report)
        observed = "ok" if errors == 0 and len(read_rows(assays)) == 0 and len(read_rows(relationships)) == 0 else "bad_output"
        tests.append(result("header_only", "header-only reviewed export imports as schema-only canonical tables", "ok", observed))

        populated = export_dir / "populated.tsv"
        write_tsv(
            populated,
            ["interaction_id", "phage_id", "host_id", "tested", "spot_result", "reference"],
            [
                {"interaction_id": "i1", "phage_id": "phage_A", "host_id": "host_A", "tested": "true", "spot_result": "positive", "reference": "fixture_ref"},
                {"interaction_id": "i2", "phage_id": "phage_A", "host_id": "host_B", "tested": "true", "spot_result": "negative", "reference": "fixture_ref"},
            ],
        )
        write_config(config, populated)
        errors = run_import(root, config, assays, relationships, report)
        assay_rows = read_rows(assays)
        relationship_rows = read_rows(relationships)
        observed = "ok" if errors == 0 and len(assay_rows) == 2 and len(relationship_rows) == 2 and assay_rows[0]["study_id"] == "fixture_study" else "bad_output"
        tests.append(result("populated_rows", "populated source export creates assay and tested-host relationship rows", "ok", observed))

        previous_assays = assays.read_text(encoding="utf-8")
        previous_relationships = relationships.read_text(encoding="utf-8")
        malformed = export_dir / "malformed.tsv"
        write_tsv(
            malformed,
            ["interaction_id", "phage_id", "host_id", "tested", "spot_result", "reference"],
            [{"interaction_id": "bad1", "phage_id": "phage_A", "host_id": "host_A", "tested": "maybe", "spot_result": "positive", "reference": "fixture_ref"}],
        )
        write_config(config, malformed)
        errors = run_import(root, config, assays, relationships, report)
        preserved = assays.read_text(encoding="utf-8") == previous_assays and relationships.read_text(encoding="utf-8") == previous_relationships
        observed = "ok" if errors and preserved else "bad_output"
        tests.append(result("malformed_preserves_outputs", "malformed source rows fail without rewriting existing canonical outputs", "ok", observed))

        collision_config = root / "config" / "collision.yaml"
        write_config(collision_config, assays)
        try:
            _assay_rows, _relationship_rows, _reports, errors = importer.import_assays(collision_config, assays, relationships, root)
        except Exception as exc:  # pragma: no cover - defensive report surface
            observed = f"exception:{type(exc).__name__}"
        else:
            observed = "ok" if errors else "no_error"
        tests.append(result("path_collision", "input path cannot equal canonical assay output path", "ok", observed))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {
            "severity": "info",
            "item": "phage_host_assay_import_self_test",
            "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}",
        }
    ]
    if failed:
        report.append({"severity": "error", "item": "phage_host_assay_import_self_test", "message": "One or more assay import self-tests failed."})
    else:
        report.append({"severity": "info", "item": "phage_host_assay_import_self_test", "message": "All assay import self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Phage-host assay import self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
