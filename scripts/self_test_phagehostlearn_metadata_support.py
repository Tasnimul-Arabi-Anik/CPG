#!/usr/bin/env python3
"""Self-test PhageHostLearn metadata support audit."""

from __future__ import annotations

import argparse
import csv
import json
import tempfile
from pathlib import Path
from typing import Iterable

import audit_phagehostlearn_metadata_support as audit


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for the PhageHostLearn metadata support audit.")
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


def make_fixture(root: Path, reviewed: bool = False, include_metadata: bool = True) -> argparse.Namespace:
    data = root / "data"
    matrix = data / "phage_host_interactions.csv"
    rbpbase = data / "RBPbase.csv"
    locibase = data / "Locibase.json"
    locibase_invitro = data / "Locibase_invitro.json"
    phage_export = data / "phage_export.tsv"
    host_export = data / "host_export.tsv"
    phage_map = data / "phage_map.tsv"
    host_map = data / "host_map.tsv"
    support = root / "results" / "support.tsv"
    report = root / "results" / "report.tsv"
    write_csv(matrix, [["", "phageA", "phageB"], ["host1", "1", "0"], ["host2", "", "1"]])
    if include_metadata:
        write_csv(
            rbpbase,
            [
                ["phage_ID", "protein_ID", "protein_sequence", "dna_sequence", "xgb_score"],
                ["phageA", "rbp1", "M", "ATG", "0.9"],
                ["phageA", "rbp2", "M", "ATG", "0.8"],
                ["phageExtra", "rbpX", "M", "ATG", "0.7"],
            ],
        )
        locibase.write_text(json.dumps({"host1": ["locusA", "locusB"]}), encoding="utf-8")
        locibase_invitro.write_text(json.dumps({"host2": ["locusC"]}), encoding="utf-8")
    else:
        for optional_path in [rbpbase, locibase, locibase_invitro]:
            if optional_path.exists():
                optional_path.unlink()
    review_status = "reviewed" if reviewed else "pending"
    write_tsv(
        phage_export,
        ["accession", "genome_id", "host_species", "host_strain", "country", "year", "genome_length", "gc_percent", "raw_sequence_path", "notes"],
        [
            {"accession": "NA", "genome_id": "phage_A", "host_species": "Klebsiella pneumoniae species complex", "host_strain": "NA", "country": "NA", "year": "NA", "genome_length": "10", "gc_percent": "50", "raw_sequence_path": "NA", "notes": "source_id=phageA; review_status=pending_entity_review"},
            {"accession": "NA", "genome_id": "phage_B", "host_species": "Klebsiella pneumoniae species complex", "host_strain": "NA", "country": "NA", "year": "NA", "genome_length": "10", "gc_percent": "50", "raw_sequence_path": "NA", "notes": "source_id=phageB; review_status=pending_entity_review"},
        ],
    )
    write_tsv(
        host_export,
        ["genome_id", "accession", "host_species", "host_strain", "country", "year", "K_type", "O_type", "ST", "AMR_markers", "virulence_markers", "raw_sequence_path", "notes"],
        [
            {"genome_id": "host_1", "accession": "NA", "host_species": "Klebsiella pneumoniae species complex", "host_strain": "host1", "country": "NA", "year": "NA", "K_type": "NA", "O_type": "NA", "ST": "NA", "AMR_markers": "NA", "virulence_markers": "NA", "raw_sequence_path": "NA", "notes": "source_id=host1; review_status=pending_entity_review"},
            {"genome_id": "host_2", "accession": "NA", "host_species": "Klebsiella pneumoniae species complex", "host_strain": "host2", "country": "NA", "year": "NA", "K_type": "NA", "O_type": "NA", "ST": "NA", "AMR_markers": "NA", "virulence_markers": "NA", "raw_sequence_path": "NA", "notes": "source_id=host2; review_status=pending_entity_review"},
        ],
    )
    write_tsv(
        phage_map,
        ["source_id", "canonical_id", "review_status", "notes"],
        [
            {"source_id": "phageA", "canonical_id": "phage_A", "review_status": review_status, "notes": "fixture"},
            {"source_id": "phageB", "canonical_id": "phage_B", "review_status": review_status, "notes": "fixture"},
        ],
    )
    write_tsv(
        host_map,
        ["source_id", "canonical_id", "review_status", "notes"],
        [
            {"source_id": "host1", "canonical_id": "host_1", "review_status": review_status, "notes": "fixture"},
            {"source_id": "host2", "canonical_id": "host_2", "review_status": review_status, "notes": "fixture"},
        ],
    )
    return argparse.Namespace(
        matrix=matrix.as_posix(),
        rbpbase=rbpbase.as_posix(),
        locibase=locibase.as_posix(),
        locibase_invitro=locibase_invitro.as_posix(),
        phage_export=phage_export.as_posix(),
        host_export=host_export.as_posix(),
        phage_map=phage_map.as_posix(),
        host_map=host_map.as_posix(),
        support_output=support.as_posix(),
        report_output=report.as_posix(),
        root=root.as_posix(),
    )


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="phagehostlearn-support-") as tmp:
        root = Path(tmp)
        args = make_fixture(root, reviewed=False, include_metadata=True)
        rc = audit.run(args)
        rows = read_rows(Path(args.support_output))
        phage_a = next(row for row in rows if row["source_id"] == "phageA")
        phage_b = next(row for row in rows if row["source_id"] == "phageB")
        host_2 = next(row for row in rows if row["source_id"] == "host2")
        observed = "ok" if rc == 0 and phage_a["rbpbase_rows"] == "2" and phage_b["metadata_support_status"] == "matrix_present_no_rbpbase_support" else "bad_phage_support"
        tests.append(result("rbpbase_overlap", "RBPbase rows are counted by matrix phage ID", "ok", observed))
        observed = "ok" if host_2["locibase_invitro_entry_count"] == "1" and host_2["metadata_support_status"] == "matrix_present_locibase_supported" else "bad_host_support"
        tests.append(result("locibase_overlap", "Locibase and invitro Locibase rows are counted by matrix host ID", "ok", observed))
        observed = "ok" if sum(1 for row in rows if row["blocking_for_assay_import"] == "true") == 4 else "bad_blocking_count"
        tests.append(result("pending_maps_block", "pending source-to-canonical maps block assay import", "ok", observed))

        reviewed_args = make_fixture(root, reviewed=True, include_metadata=True)
        rc = audit.run(reviewed_args)
        rows = read_rows(Path(reviewed_args.support_output))
        observed = "ok" if rc == 0 and sum(1 for row in rows if row["blocking_for_assay_import"] == "true") == 0 else "unexpected_blocking"
        tests.append(result("reviewed_maps_unblock", "reviewed maps remove assay-import blockers", "ok", observed))

        missing_args = make_fixture(root, reviewed=True, include_metadata=False)
        rc = audit.run(missing_args)
        rows = read_rows(Path(missing_args.support_output))
        report = read_rows(Path(missing_args.report_output))
        observed = "ok" if rc == 0 and any(row["item"] == "rbpbase" and row["severity"] == "warning" for row in report) and any(row["metadata_support_status"].endswith("_input_missing") for row in rows) else "missing_inputs_not_reported"
        tests.append(result("missing_optional_inputs_warn", "missing RBPbase/Locibase files warn without failing clean checkout runs", "ok", observed))

        bad_json_args = make_fixture(root, reviewed=True, include_metadata=True)
        Path(bad_json_args.locibase).write_text("{bad json", encoding="utf-8")
        try:
            audit.run(bad_json_args)
        except audit.PhageHostLearnSupportError:
            observed = "ok"
        else:
            observed = "no_failure"
        tests.append(result("malformed_locibase_fails", "malformed Locibase JSON is blocking when supplied", "ok", observed))

        collision_args = make_fixture(root, reviewed=True, include_metadata=True)
        collision_args.report_output = collision_args.support_output
        try:
            audit.run(collision_args)
        except audit.PhageHostLearnSupportError:
            observed = "ok"
        else:
            observed = "no_error"
        tests.append(result("path_collision_fails", "support and report outputs cannot collide", "ok", observed))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [{"severity": "info", "item": "phagehostlearn_metadata_support_self_test", "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}"}]
    if failed:
        report.append({"severity": "error", "item": "phagehostlearn_metadata_support_self_test", "message": "One or more metadata-support self-tests failed."})
    else:
        report.append({"severity": "info", "item": "phagehostlearn_metadata_support_self_test", "message": "All metadata-support self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"PhageHostLearn metadata support self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
