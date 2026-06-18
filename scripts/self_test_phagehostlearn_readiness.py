#!/usr/bin/env python3
"""Self-test PhageHostLearn readiness audit."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from typing import Iterable

import audit_phagehostlearn_readiness as audit
from validate_phage_host_assays import ASSAY_COLUMNS


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for PhageHostLearn readiness audit.")
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


def write_configs(root: Path, enabled: bool = False) -> tuple[Path, Path]:
    imports = root / "config" / "source_imports.yaml"
    catalog = root / "config" / "source_catalog.yaml"
    imports.parent.mkdir(parents=True, exist_ok=True)
    enabled_text = "true" if enabled else "false"
    imports.write_text(
        f"""imports:\n  - import_id: phagehostlearn_2024_phages\n    enabled: {enabled_text}\n  - import_id: phagehostlearn_2024_hosts\n    enabled: {enabled_text}\n""",
        encoding="utf-8",
    )
    catalog.write_text(
        f"""sources:\n  - source_id: phagehostlearn_2024_phages\n    enabled: {enabled_text}\n  - source_id: phagehostlearn_2024_hosts\n    enabled: {enabled_text}\n""",
        encoding="utf-8",
    )
    return imports, catalog


def make_fixture(root: Path, reviewed: bool = False, enabled: bool = False, assay_rows: bool = False) -> argparse.Namespace:
    data = root / "data" / "metadata"
    phage_export = data / "source_exports" / "phages.tsv"
    host_export = data / "source_exports" / "hosts.tsv"
    phage_map = data / "assay_source_exports" / "phage_map.tsv"
    host_map = data / "assay_source_exports" / "host_map.tsv"
    assay_export = data / "assay_source_exports" / "assays.tsv"
    review_status = "reviewed" if reviewed else "pending"
    write_tsv(
        phage_export,
        ["accession", "genome_id", "host_species", "host_strain", "country", "year", "genome_length", "gc_percent", "raw_sequence_path", "notes"],
        [{"accession": "NA", "genome_id": "phage_A", "host_species": "Klebsiella pneumoniae species complex", "host_strain": "NA", "country": "NA", "year": "NA", "genome_length": "10", "gc_percent": "50", "raw_sequence_path": "data/raw/external/phagehostlearn/phage_A.fasta", "notes": "source_id=phageA; review_status=pending_entity_review"}],
    )
    write_tsv(
        host_export,
        ["genome_id", "accession", "host_species", "host_strain", "country", "year", "K_type", "O_type", "ST", "AMR_markers", "virulence_markers", "raw_sequence_path", "notes"],
        [{"genome_id": "host_A", "accession": "NA", "host_species": "Klebsiella pneumoniae species complex", "host_strain": "hostA", "country": "NA", "year": "NA", "K_type": "K1", "O_type": "O1", "ST": "ST1", "AMR_markers": "NA", "virulence_markers": "NA", "raw_sequence_path": "data/raw/external/phagehostlearn/host_A.fna", "notes": "source_id=hostA; review_status=pending_entity_review"}],
    )
    write_tsv(phage_map, ["source_id", "canonical_id", "review_status", "notes"], [{"source_id": "phageA", "canonical_id": "phage_A", "review_status": review_status, "notes": "fixture"}])
    write_tsv(host_map, ["source_id", "canonical_id", "review_status", "notes"], [{"source_id": "hostA", "canonical_id": "host_A", "review_status": review_status, "notes": "fixture"}])
    assay_data = []
    if assay_rows:
        assay_data = [{
            "interaction_id": "i1",
            "phage_id": "phage_A",
            "host_id": "host_A",
            "study_id": "fixture",
            "panel_id": "panel",
            "assay_type": "spot",
            "tested": "true",
            "adsorption_result": "not_measured",
            "spot_result": "positive",
            "plaque_result": "not_measured",
            "productive_infection_result": "not_measured",
            "eop": "NA",
            "eop_reference_host": "NA",
            "growth_inhibition_result": "not_measured",
            "moi": "NA",
            "temperature_c": "NA",
            "medium": "NA",
            "replicate_count": "NA",
            "outcome_tier": "initial_interaction",
            "evidence_tier": "supplementary_matrix",
            "reference": "fixture",
            "notes": "fixture",
        }]
    write_tsv(assay_export, ASSAY_COLUMNS, assay_data)
    source_imports, source_catalog = write_configs(root, enabled=enabled)
    return argparse.Namespace(
        phage_export=phage_export.as_posix(),
        host_export=host_export.as_posix(),
        phage_map=phage_map.as_posix(),
        host_map=host_map.as_posix(),
        assay_export=assay_export.as_posix(),
        source_imports=source_imports.as_posix(),
        source_catalog=source_catalog.as_posix(),
        readiness_output=(root / "results" / "readiness.tsv").as_posix(),
        report_output=(root / "results" / "report.tsv").as_posix(),
        root=root.as_posix(),
    )


def blocking_count(path: Path) -> int:
    return sum(1 for row in read_rows(path) if row["blocking_for_assay_import"] == "true")


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="phagehostlearn-readiness-") as tmp:
        root = Path(tmp)
        args = make_fixture(root, reviewed=False, enabled=False, assay_rows=False)
        rc = audit.run(args)
        rows = read_rows(Path(args.readiness_output))
        observed = "ok" if rc == 0 and blocking_count(Path(args.readiness_output)) >= 3 and any(row["status"] == "blocked_pending_review" for row in rows) else "bad_output"
        tests.append(result("pending_maps_block", "pending maps block assay import", "ok", observed))

        args = make_fixture(root, reviewed=False, enabled=True, assay_rows=False)
        rc = audit.run(args)
        rows = read_rows(Path(args.readiness_output))
        observed = "ok" if rc == 0 and any(row["check_id"] == "PHL005" and row["status"] == "fail_enabled_before_review" for row in rows) else "bad_output"
        tests.append(result("early_enablement_fails", "enabled sources with pending maps are blocking", "ok", observed))

        args = make_fixture(root, reviewed=True, enabled=True, assay_rows=True)
        rc = audit.run(args)
        rows = read_rows(Path(args.readiness_output))
        observed = "ok" if rc == 0 and blocking_count(Path(args.readiness_output)) == 0 and any(row["check_id"] == "PHL006" and row["status"] == "pass" for row in rows) else "bad_output"
        tests.append(result("reviewed_assay_ready", "reviewed maps plus assay rows pass readiness", "ok", observed))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [{"severity": "info", "item": "phagehostlearn_readiness_self_test", "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}"}]
    if failed:
        report.append({"severity": "error", "item": "phagehostlearn_readiness_self_test", "message": "One or more readiness self-tests failed."})
    else:
        report.append({"severity": "info", "item": "phagehostlearn_readiness_self_test", "message": "All readiness self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"PhageHostLearn readiness self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
