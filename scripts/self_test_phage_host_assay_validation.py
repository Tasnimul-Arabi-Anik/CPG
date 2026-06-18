#!/usr/bin/env python3
"""Self-test phage-host assay and relationship validation scenarios."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from typing import Iterable

import validate_phage_host_assays as validator


TEST_COLUMNS = [
    "test_id",
    "scenario",
    "expected_blocking_count",
    "observed_blocking_count",
    "expected_message_contains",
    "observed_messages",
    "status",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for phage-host assay validation.")
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


def table_text(columns: list[str], rows: list[dict[str, str]]) -> str:
    lines = ["\t".join(columns)]
    for row in rows:
        lines.append("\t".join(row.get(column, "") for column in columns))
    return "\n".join(lines) + "\n"


def base_assay_row(**updates: str) -> dict[str, str]:
    row = {
        "interaction_id": "int_1",
        "phage_id": "phage_1",
        "host_id": "host_1",
        "study_id": "study_1",
        "panel_id": "panel_1",
        "assay_type": "plaque",
        "tested": "true",
        "adsorption_result": "NA",
        "spot_result": "NA",
        "plaque_result": "positive",
        "productive_infection_result": "positive",
        "eop": "0.5",
        "eop_reference_host": "host_1",
        "growth_inhibition_result": "NA",
        "moi": "NA",
        "temperature_c": "37",
        "medium": "LB",
        "replicate_count": "2",
        "outcome_tier": "productive_infection_confirmed",
        "evidence_tier": "curated_assay",
        "reference": "self_test_reference",
        "notes": "self-test valid row",
    }
    row.update(updates)
    return row


def base_relationship_row(**updates: str) -> dict[str, str]:
    row = {
        "relationship_id": "rel_1",
        "phage_id": "phage_1",
        "host_id": "host_1",
        "relationship_type": "tested_assay_host",
        "relationship_status": "reviewed",
        "relationship_evidence": "self_test_assay_panel",
        "source_reference": "self_test_reference",
        "confidence": "high",
        "notes": "self-test relationship row",
    }
    row.update(updates)
    return row


def canonical_files(tmpdir: Path) -> tuple[Path, Path]:
    manifest = tmpdir / "results/qc/phage_genome_manifest.tsv"
    hosts = tmpdir / "results/host_features/host_metadata.tsv"
    write_text(manifest, "record_type\tgenome_id\nphage\tphage_1\nhost_genome\thost_1\n")
    write_text(hosts, "host_genome_id\nhost_1\n")
    return manifest, hosts


def run_case(
    tmpdir: Path,
    test_id: str,
    scenario: str,
    assay_rows: list[dict[str, str]],
    relationship_rows: list[dict[str, str]],
    expected_blocking_count: int,
    expected_message_contains: str = "",
) -> dict[str, str]:
    case_dir = tmpdir / test_id
    assays = case_dir / "data/metadata/phage_host_assays.tsv"
    relationships = case_dir / "data/metadata/phage_host_relationships.tsv"
    write_text(assays, table_text(validator.ASSAY_COLUMNS, assay_rows))
    write_text(relationships, table_text(validator.RELATIONSHIP_COLUMNS, relationship_rows))
    manifest, hosts = canonical_files(case_dir)
    assay_issues, relationship_issues, _ = validator.validate_inputs(case_dir, assays, relationships, manifest, hosts)
    issues = assay_issues + relationship_issues
    blocking = [issue for issue in issues if issue["blocking_issue"] == "true"]
    messages = "; ".join(issue["message"] for issue in issues)
    blocking_ok = len(blocking) == expected_blocking_count
    message_ok = True if not expected_message_contains else expected_message_contains in messages
    passed = blocking_ok and message_ok
    notes = []
    if not blocking_ok:
        notes.append("blocking_count_mismatch")
    if not message_ok:
        notes.append("message_mismatch")
    return {
        "test_id": test_id,
        "scenario": scenario,
        "expected_blocking_count": str(expected_blocking_count),
        "observed_blocking_count": str(len(blocking)),
        "expected_message_contains": expected_message_contains or "NA",
        "observed_messages": messages or "NA",
        "status": "pass" if passed else "fail",
        "notes": ";".join(notes) if notes else "NA",
    }


def run_tests() -> list[dict[str, str]]:
    with tempfile.TemporaryDirectory(prefix="phage-host-assay-validation-") as tmp:
        tmpdir = Path(tmp)
        return [
            run_case(tmpdir, "header_only", "header-only assay and relationship tables are schema-valid", [], [], 0, "Header-only assay table"),
            run_case(tmpdir, "valid_positive", "plaque/EOP-supported productive infection passes", [base_assay_row()], [base_relationship_row()], 0),
            run_case(
                tmpdir,
                "valid_negative",
                "tested negative plaque result passes",
                [
                    base_assay_row(
                        interaction_id="int_2",
                        plaque_result="negative",
                        productive_infection_result="negative",
                        eop="0",
                        outcome_tier="tested_negative",
                    )
                ],
                [base_relationship_row(relationship_id="rel_2")],
                0,
            ),
            run_case(
                tmpdir,
                "untested_negative_blocked",
                "tested=false cannot encode a negative result",
                [base_assay_row(interaction_id="int_3", tested="false", plaque_result="negative", productive_infection_result="negative", outcome_tier="tested_negative")],
                [base_relationship_row(relationship_id="rel_3")],
                5,
                "tested=false",
            ),
            run_case(
                tmpdir,
                "spot_only_productive_blocked",
                "productive infection cannot be inferred from spot clearing alone",
                [
                    base_assay_row(
                        interaction_id="int_4",
                        assay_type="spot",
                        spot_result="positive",
                        plaque_result="NA",
                        productive_infection_result="positive",
                        eop="NA",
                        outcome_tier="initial_interaction",
                    )
                ],
                [base_relationship_row(relationship_id="rel_4")],
                1,
                "spot clearing alone",
            ),
            run_case(
                tmpdir,
                "negative_eop_blocked",
                "negative EOP is malformed",
                [base_assay_row(interaction_id="int_5", eop="-0.1")],
                [base_relationship_row(relationship_id="rel_5")],
                1,
                "EOP must be numeric and non-negative",
            ),
            run_case(
                tmpdir,
                "duplicate_assay_blocked",
                "duplicate interaction and study-panel-assay rows are blocking",
                [base_assay_row(interaction_id="int_6"), base_assay_row(interaction_id="int_6")],
                [base_relationship_row(relationship_id="rel_6")],
                2,
                "Duplicate interaction_id",
            ),
            run_case(
                tmpdir,
                "unknown_ids_blocked",
                "unknown phage and host identifiers are blocking",
                [base_assay_row(interaction_id="int_7", phage_id="missing_phage", host_id="missing_host")],
                [base_relationship_row(relationship_id="rel_7", phage_id="missing_phage", host_id="missing_host")],
                4,
                "Unknown phage_id",
            ),
            run_case(
                tmpdir,
                "bad_relationship_type_blocked",
                "relationship type must be controlled",
                [base_assay_row(interaction_id="int_8")],
                [base_relationship_row(relationship_id="rel_8", relationship_type="susceptible_host")],
                1,
                "Invalid relationship_type",
            ),
        ]


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {
            "severity": "info",
            "item": "phage_host_assay_validation_self_test",
            "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}",
        }
    ]
    if failed:
        report.append({"severity": "error", "item": "phage_host_assay_validation_self_test", "message": "One or more self-tests failed."})
    else:
        report.append({"severity": "info", "item": "phage_host_assay_validation_self_test", "message": "All self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Phage-host assay validation self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
