#!/usr/bin/env python3
"""Self-test PhageHostLearn map-review audit."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from typing import Iterable

import audit_phagehostlearn_map_review as audit


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for the PhageHostLearn map-review audit.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report-output", required=True)
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


def make_fixture(
    root: Path,
    entity_review_status: str = "pending_entity_review",
    map_review_status: str = "pending",
    canonical_mismatch: bool = False,
    matrix_missing: bool = False,
) -> argparse.Namespace:
    data = root / "data"
    support = data / "support.tsv"
    phage_export = data / "phages.tsv"
    host_export = data / "hosts.tsv"
    phage_map = data / "phage_map.tsv"
    host_map = data / "host_map.tsv"
    review = root / "results" / "review.tsv"
    report = root / "results" / "report.tsv"
    phage_canonical = "phage_A"
    map_phage_canonical = "phage_B" if canonical_mismatch else phage_canonical
    support_status = "matrix_input_missing" if matrix_missing else "matrix_present_rbpbase_supported"
    host_support_status = "matrix_input_missing" if matrix_missing else "matrix_present_locibase_supported"
    matrix_present = "false" if matrix_missing else "true"
    write_tsv(
        support,
        [
            "entity_type", "source_id", "canonical_id", "matrix_present", "matrix_tested_cells", "matrix_positive_cells", "matrix_negative_cells",
            "source_export_present", "source_export_review_status", "id_map_present", "id_map_review_status", "rbpbase_rows", "rbpbase_protein_count",
            "locibase_entry_count", "locibase_invitro_entry_count", "metadata_support_status", "blocking_for_assay_import", "notes",
        ],
        [
            {"entity_type": "phage", "source_id": "phageA", "canonical_id": map_phage_canonical, "matrix_present": matrix_present, "matrix_tested_cells": "2", "matrix_positive_cells": "1", "matrix_negative_cells": "1", "source_export_present": "true", "source_export_review_status": entity_review_status, "id_map_present": "true", "id_map_review_status": map_review_status, "rbpbase_rows": "1", "rbpbase_protein_count": "1", "locibase_entry_count": "NA", "locibase_invitro_entry_count": "NA", "metadata_support_status": support_status, "blocking_for_assay_import": "true", "notes": "fixture"},
            {"entity_type": "host", "source_id": "host1", "canonical_id": "host_1", "matrix_present": matrix_present, "matrix_tested_cells": "2", "matrix_positive_cells": "1", "matrix_negative_cells": "1", "source_export_present": "true", "source_export_review_status": entity_review_status, "id_map_present": "true", "id_map_review_status": map_review_status, "rbpbase_rows": "NA", "rbpbase_protein_count": "NA", "locibase_entry_count": "2", "locibase_invitro_entry_count": "0", "metadata_support_status": host_support_status, "blocking_for_assay_import": "true", "notes": "fixture"},
        ],
    )
    write_tsv(
        phage_export,
        ["accession", "genome_id", "host_species", "host_strain", "country", "year", "genome_length", "gc_percent", "raw_sequence_path", "notes"],
        [{"accession": "NA", "genome_id": phage_canonical, "host_species": "Klebsiella pneumoniae species complex", "host_strain": "NA", "country": "NA", "year": "NA", "genome_length": "10", "gc_percent": "50", "raw_sequence_path": "NA", "notes": f"source_id=phageA; review_status={entity_review_status}"}],
    )
    write_tsv(
        host_export,
        ["genome_id", "accession", "host_species", "host_strain", "country", "year", "K_type", "O_type", "ST", "AMR_markers", "virulence_markers", "raw_sequence_path", "notes"],
        [{"genome_id": "host_1", "accession": "NA", "host_species": "Klebsiella pneumoniae species complex", "host_strain": "host1", "country": "NA", "year": "NA", "K_type": "NA", "O_type": "NA", "ST": "NA", "AMR_markers": "NA", "virulence_markers": "NA", "raw_sequence_path": "NA", "notes": f"source_id=host1; review_status={entity_review_status}"}],
    )
    write_tsv(phage_map, ["source_id", "canonical_id", "review_status", "notes"], [{"source_id": "phageA", "canonical_id": map_phage_canonical, "review_status": map_review_status, "notes": "fixture"}])
    write_tsv(host_map, ["source_id", "canonical_id", "review_status", "notes"], [{"source_id": "host1", "canonical_id": "host_1", "review_status": map_review_status, "notes": "fixture"}])
    return argparse.Namespace(
        metadata_support=support.as_posix(),
        phage_export=phage_export.as_posix(),
        host_export=host_export.as_posix(),
        phage_map=phage_map.as_posix(),
        host_map=host_map.as_posix(),
        review_output=review.as_posix(),
        report_output=report.as_posix(),
        root=root.as_posix(),
    )


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="phagehostlearn-map-review-") as tmp:
        root = Path(tmp)
        args = make_fixture(root, entity_review_status="pending_entity_review", map_review_status="pending")
        rc = audit.run(args)
        rows = read_rows(Path(args.review_output))
        observed = rows[0]["review_recommendation"] if rc == 0 else "failed"
        tests.append(result("pending_entity_review_blocks", "pending source export entity review blocks map approval", "pending_entity_review", observed))

        args = make_fixture(root, entity_review_status="reviewed", map_review_status="pending")
        rc = audit.run(args)
        rows = read_rows(Path(args.review_output))
        observed = rows[0]["review_recommendation"] if rc == 0 else "failed"
        tests.append(result("ready_for_manual_review", "reviewed entity plus pending map becomes manually reviewable", "ready_for_manual_map_review", observed))

        args = make_fixture(root, entity_review_status="reviewed", map_review_status="reviewed")
        rc = audit.run(args)
        rows = read_rows(Path(args.review_output))
        observed = rows[0]["review_recommendation"] if rc == 0 else "failed"
        tests.append(result("reviewed_ready", "reviewed map row is usable by matrix normalizer", "reviewed_ready_for_assay_normalization", observed))

        args = make_fixture(root, entity_review_status="reviewed", map_review_status="pending", canonical_mismatch=True)
        rc = audit.run(args)
        rows = read_rows(Path(args.review_output))
        observed = rows[0]["review_recommendation"] if rc == 0 else "failed"
        tests.append(result("canonical_mismatch_blocks", "canonical mismatch blocks review", "canonical_mismatch", observed))

        args = make_fixture(root, entity_review_status="reviewed", map_review_status="pending", matrix_missing=True)
        rc = audit.run(args)
        rows = read_rows(Path(args.review_output))
        observed = rows[0]["review_recommendation"] if rc == 0 else "failed"
        tests.append(result("missing_matrix_blocks", "missing matrix input blocks review recommendation", "waiting_matrix_input", observed))

        args = make_fixture(root, entity_review_status="reviewed", map_review_status="pending")
        args.report_output = args.review_output
        try:
            audit.run(args)
        except audit.MapReviewAuditError:
            observed = "ok"
        else:
            observed = "no_error"
        tests.append(result("path_collision_fails", "review and report outputs cannot collide", "ok", observed))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [{"severity": "info", "item": "phagehostlearn_map_review_self_test", "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}"}]
    if failed:
        report.append({"severity": "error", "item": "phagehostlearn_map_review_self_test", "message": "One or more map-review self-tests failed."})
    else:
        report.append({"severity": "info", "item": "phagehostlearn_map_review_self_test", "message": "All map-review self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"PhageHostLearn map review self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
