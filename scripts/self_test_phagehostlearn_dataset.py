#!/usr/bin/env python3
"""Self-test the consolidated PhageHostLearn dataset audit."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from typing import Iterable

import audit_phagehostlearn_dataset as audit
from validate_phage_host_assays import ASSAY_COLUMNS


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for the PhageHostLearn dataset audit.")
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


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
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


def source_row(source_id: str, entity_type: str, reviewed: bool) -> dict[str, str]:
    status = "reviewed" if reviewed else "pending_entity_review"
    if entity_type == "phage":
        return {
            "accession": "NA",
            "genome_id": f"phage_{source_id}",
            "host_species": "Klebsiella pneumoniae species complex",
            "host_strain": "NA",
            "country": "NA",
            "year": "NA",
            "genome_length": "10",
            "gc_percent": "50",
            "raw_sequence_path": "NA",
            "notes": f"source_id={source_id}; review_status={status}; zip_member=phages/{source_id}.fasta",
        }
    return {
        "genome_id": f"host_{source_id}",
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
        "notes": f"source_id={source_id}; review_status={status}; host_archive_member=fasta_files/{source_id}.fasta",
    }


def make_fixture(root: Path, structural_error: bool = False, assay_rows: bool = True) -> argparse.Namespace:
    data = root / "data" / "metadata"
    ext = data / "external" / "phagehostlearn"
    phage_export = data / "source_exports" / "phages.tsv"
    host_export = data / "source_exports" / "hosts.tsv"
    phage_map = data / "assay_source_exports" / "phage_map.tsv"
    host_map = data / "assay_source_exports" / "host_map.tsv"
    assay_export = data / "assay_source_exports" / "assays.tsv"
    matrix = ext / "matrix.csv"
    file_manifest = ext / "manifest.tsv"
    rbpbase = ext / "RBPbase.csv"
    locibase = ext / "Locibase.json"
    locibase_invitro = ext / "Locibase_invitro.json"

    write_tsv(file_manifest, ["file_id", "expected_path", "expected_size_bytes", "expected_md5", "expected_sha256"], [])
    write_csv(matrix, ["host_id", "p1", "p2"], [{"host_id": "h1", "p1": "1", "p2": "0"}, {"host_id": "h2", "p1": "", "p2": "1"}])
    write_tsv(
        phage_export,
        ["accession", "genome_id", "host_species", "host_strain", "country", "year", "genome_length", "gc_percent", "raw_sequence_path", "notes"],
        [source_row("p1", "phage", True), source_row("p2", "phage", True), source_row("p3", "phage", False)],
    )
    write_tsv(
        host_export,
        ["genome_id", "accession", "host_species", "host_strain", "country", "year", "K_type", "O_type", "ST", "AMR_markers", "virulence_markers", "raw_sequence_path", "notes"],
        [source_row("h1", "host", True), source_row("h2", "host", True), source_row("h3", "host", False)],
    )
    bad_canonical = "missing_phage" if structural_error else "phage_p1"
    write_tsv(phage_map, ["source_id", "canonical_id", "review_status", "notes"], [
        {"source_id": "p1", "canonical_id": bad_canonical, "review_status": "reviewed", "notes": "fixture"},
        {"source_id": "p2", "canonical_id": "phage_p2", "review_status": "reviewed", "notes": "fixture"},
        {"source_id": "p3", "canonical_id": "phage_p3", "review_status": "pending", "notes": "fixture"},
    ])
    write_tsv(host_map, ["source_id", "canonical_id", "review_status", "notes"], [
        {"source_id": "h1", "canonical_id": "host_h1", "review_status": "reviewed", "notes": "fixture"},
        {"source_id": "h2", "canonical_id": "host_h2", "review_status": "reviewed", "notes": "fixture"},
        {"source_id": "h3", "canonical_id": "host_h3", "review_status": "pending", "notes": "fixture"},
    ])
    assay_data = []
    if assay_rows:
        base = {
            "study_id": "fixture",
            "panel_id": "panel",
            "assay_type": "spot",
            "tested": "true",
            "adsorption_result": "not_measured",
            "plaque_result": "not_measured",
            "productive_infection_result": "not_measured",
            "eop": "NA",
            "eop_reference_host": "NA",
            "growth_inhibition_result": "not_measured",
            "moi": "NA",
            "temperature_c": "NA",
            "medium": "NA",
            "replicate_count": "NA",
            "evidence_tier": "supplementary_matrix",
            "reference": "fixture",
            "notes": "fixture",
        }
        assay_data = [
            {**base, "interaction_id": "i1", "phage_id": "phage_p1", "host_id": "host_h1", "spot_result": "positive", "outcome_tier": "initial_interaction"},
            {**base, "interaction_id": "i2", "phage_id": "phage_p2", "host_id": "host_h1", "spot_result": "negative", "outcome_tier": "tested_negative"},
            {**base, "interaction_id": "i3", "phage_id": "phage_p2", "host_id": "host_h2", "spot_result": "positive", "outcome_tier": "initial_interaction"},
        ]
    write_tsv(assay_export, ASSAY_COLUMNS, assay_data)
    write_csv(rbpbase, ["phage_ID", "protein_ID", "protein_sequence", "dna_sequence", "xgb_score"], [{"phage_ID": "p1", "protein_ID": "p1_gp1", "protein_sequence": "MA", "dna_sequence": "ATGGCA", "xgb_score": "0.9"}])
    locibase.write_text('{"h1": ["MA"]}', encoding="utf-8")
    locibase_invitro.write_text('{}', encoding="utf-8")

    return argparse.Namespace(
        file_manifest=file_manifest.as_posix(),
        matrix=matrix.as_posix(),
        phage_archive=(ext / "phages.zip").as_posix(),
        host_archive=(ext / "hosts.zip").as_posix(),
        rbpbase=rbpbase.as_posix(),
        locibase=locibase.as_posix(),
        locibase_invitro=locibase_invitro.as_posix(),
        phage_export=phage_export.as_posix(),
        host_export=host_export.as_posix(),
        phage_map=phage_map.as_posix(),
        host_map=host_map.as_posix(),
        assay_export=assay_export.as_posix(),
        audit_output=(root / "results" / "audit.tsv").as_posix(),
        report_output=(root / "results" / "report.tsv").as_posix(),
        root=root.as_posix(),
    )


def blocking_count(path: Path) -> int:
    return sum(1 for row in read_rows(path) if row["blocking_for_assay_import"] == "true")


def real_benchmark_parity() -> tuple[str, str]:
    root = Path.cwd()
    assay_export = root / "data" / "metadata" / "assay_source_exports" / "reviewed_klebsiella_phage_host_assays.tsv"
    matrix = root / "data" / "metadata" / "external" / "phagehostlearn" / "phage_host_interactions.csv"
    phage_export = root / "data" / "metadata" / "source_exports" / "phagehostlearn_2024_phages.tsv"
    host_export = root / "data" / "metadata" / "source_exports" / "phagehostlearn_2024_hosts.tsv"
    if not all(path.exists() for path in (assay_export, phage_export, host_export)):
        return "skipped", "reviewed benchmark export files are not available in this checkout"
    phage_map = root / "data" / "metadata" / "assay_source_exports" / "phagehostlearn_2024_phage_id_map.tsv"
    host_map = root / "data" / "metadata" / "assay_source_exports" / "phagehostlearn_2024_host_id_map.tsv"
    if not all(path.exists() for path in (phage_map, host_map)):
        return "skipped", "real benchmark mapping files are not available in this checkout"
    _phage_fields, phage_rows = audit.read_tsv(phage_export, required=True)
    _host_fields, host_rows = audit.read_tsv(host_export, required=True)
    _phage_map_fields, phage_map_rows = audit.read_tsv(phage_map, required=True)
    _host_map_fields, host_map_rows = audit.read_tsv(host_map, required=True)
    phage_ids = {row.get("genome_id", "") for row in phage_rows if row.get("genome_id")}
    host_ids = {row.get("genome_id", "") for row in host_rows if row.get("genome_id")}
    stats = audit.assay_stats(assay_export, phage_ids, host_ids)
    exact_export_ok = (
        stats["rows"] == 10006
        and stats["positive"] == 333
        and stats["negative"] == 9673
        and stats["tested_false"] == 0
        and stats["productive_measured"] == 0
        and stats["unresolved_phage_ids"] == 0
        and stats["unresolved_host_ids"] == 0
        and stats["duplicate_interaction_ids"] == 0
    )
    if not matrix.exists():
        summary = "; ".join(f"{key}={value}" for key, value in stats.items()) + "; raw_matrix=not_tracked_in_clean_checkout"
        return ("ok" if exact_export_ok else "bad_output"), summary
    phage_sources = audit.reviewed_map_source_ids(phage_map_rows, set(audit.export_by_source(phage_rows)), phage_ids)
    host_sources = audit.reviewed_map_source_ids(host_map_rows, set(audit.export_by_source(host_rows)), host_ids)
    _matrix_phages, _matrix_hosts, matrix_counts = audit.read_matrix(matrix, phage_sources, host_sources)
    parity_ok, summary = audit.assay_matrix_parity(stats, matrix_counts)
    exact_ok = exact_export_ok and matrix_counts["blank"] > 0
    return ("ok" if parity_ok and exact_ok else "bad_output"), summary


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="phagehostlearn-dataset-") as tmp:
        root = Path(tmp)

        args = make_fixture(root, structural_error=False, assay_rows=True)
        rc = audit.run(args)
        rows = read_rows(Path(args.audit_output))
        observed = "ok" if rc == 0 and blocking_count(Path(args.audit_output)) == 0 and any(row["check_id"] == "PHLDS006" and row["status"] == "partial_reviewed_subset" for row in rows) and any(row["check_id"] == "PHLDS008" and row["status"] == "pass" for row in rows) and any(row["check_id"] == "PHLDS009" and row["status"] == "pass" for row in rows) else "bad_output"
        tests.append(result("partial_reviewed_subset_ready", "partial reviewed subset preserves assay rows", "ok", observed))

        args = make_fixture(root, structural_error=True, assay_rows=True)
        rc = audit.run(args)
        rows = read_rows(Path(args.audit_output))
        observed = "ok" if rc == 0 and any(row["check_id"] == "PHLDS006" and row["status"] == "fail_structural_map" and row["blocking_for_assay_import"] == "true" for row in rows) else "bad_output"
        tests.append(result("structural_map_blocks", "unresolved canonical IDs block assay import", "ok", observed))

        args = make_fixture(root, structural_error=False, assay_rows=False)
        rc = audit.run(args)
        rows = read_rows(Path(args.audit_output))
        observed = "ok" if rc == 0 and any(row["check_id"] == "PHLDS008" and row["status"] == "blocked_no_importable_assays" for row in rows) and any(row["check_id"] == "PHLDS009" and row["status"] == "fail_parity_mismatch" for row in rows) else "bad_output"
        tests.append(result("header_only_assay_blocks", "header-only assay export remains blocked", "ok", observed))

    observed, notes = real_benchmark_parity()
    tests.append(result("real_benchmark_parity", "reviewed benchmark export matches 10,006 explicit matrix cells", "ok", observed, notes))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [{"severity": "info", "item": "phagehostlearn_dataset_self_test", "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}"}]
    if failed:
        report.append({"severity": "error", "item": "phagehostlearn_dataset_self_test", "message": "One or more dataset audit self-tests failed."})
    else:
        report.append({"severity": "info", "item": "phagehostlearn_dataset_self_test", "message": "All dataset audit self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"PhageHostLearn dataset self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
