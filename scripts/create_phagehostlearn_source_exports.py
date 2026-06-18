#!/usr/bin/env python3
"""Create reviewed-source export templates for PhageHostLearn benchmark entities."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

import create_assay_matrix_mapping_templates as map_templates
import normalize_assay_matrix as matrix


PHAGE_EXPORT_COLUMNS = [
    "accession",
    "genome_id",
    "host_species",
    "host_strain",
    "country",
    "year",
    "genome_length",
    "gc_percent",
    "raw_sequence_path",
    "notes",
]
HOST_EXPORT_COLUMNS = [
    "genome_id",
    "accession",
    "host_species",
    "host_strain",
    "country",
    "year",
    "K_type",
    "O_type",
    "ST",
    "AMR_markers",
    "virulence_markers",
    "raw_sequence_path",
    "notes",
]
MAP_COLUMNS = ["source_id", "canonical_id", "review_status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
BASES = set("ACGTURYKMSWBDHVNacgturykmswbdhvn")


class PhageHostLearnExportError(Exception):
    """Raised when PhageHostLearn export construction cannot proceed safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create PhageHostLearn benchmark source exports and pending ID maps.")
    parser.add_argument("--matrix", required=True, help="Reviewed phage_host_interactions.csv path.")
    parser.add_argument("--phage-zip", default="", help="Optional reviewed phages_genomes.zip path for phage length/GC inventory.")
    parser.add_argument("--phage-export-output", required=True, help="Output source export for benchmark phages.")
    parser.add_argument("--host-export-output", required=True, help="Output source export for benchmark hosts.")
    parser.add_argument("--phage-map-output", required=True, help="Output phage source-to-canonical ID map.")
    parser.add_argument("--host-map-output", required=True, help="Output host source-to-canonical ID map.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for relative paths.")
    parser.add_argument("--study-id", default="phagehostlearn_2024", help="Stable benchmark source/study ID.")
    parser.add_argument("--source-reference", default="https://doi.org/10.5281/zenodo.11061100; https://doi.org/10.1038/s41467-024-48675-6", help="Source reference stored in notes.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: object) -> bool:
    return normalize(value) in MISSING


def safe_id(prefix: str, source_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_id).strip("_")
    return f"{prefix}_{cleaned}"


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def write_tsv_atomic(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", dir=path.parent, delete=False) as handle:
        tmp = Path(handle.name)
        fieldnames = list(columns)
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})
    tmp.replace(path)


def read_matrix_ids(path: Path) -> tuple[list[str], list[str], int, int, int]:
    fieldnames, rows = matrix.read_table(path, matrix.delimiter_for(path, "comma"))
    if not fieldnames:
        raise PhageHostLearnExportError("interaction matrix has no header")
    host_column = fieldnames[0]
    phage_ids = sorted({normalize(column) for column in fieldnames[1:] if not is_missing(column)})
    host_ids = sorted({normalize(row.get(host_column)) for row in rows if not is_missing(row.get(host_column))})
    tested = 0
    positive = 0
    negative = 0
    for row in rows:
        for column in fieldnames[1:]:
            value = normalize(row.get(column))
            if value in {"1", "1.0"}:
                tested += 1
                positive += 1
            elif value in {"0", "0.0"}:
                tested += 1
                negative += 1
    return phage_ids, host_ids, tested, positive, negative


def fasta_stats(text: str) -> tuple[int, str, int]:
    seqs: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current:
                seqs.append("".join(current))
                current = []
            continue
        current.append("".join(ch for ch in line if ch in BASES))
    if current:
        seqs.append("".join(current))
    sequence = "".join(seqs).upper()
    length = len(sequence)
    if length == 0:
        return 0, "NA", len(seqs)
    gc = 100 * (sequence.count("G") + sequence.count("C")) / length
    return length, f"{gc:.3f}", len(seqs)


def load_phage_zip_inventory(path: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    inventory: dict[str, dict[str, str]] = {}
    warnings: list[str] = []
    if not path.exists():
        return inventory, [f"phage zip not found: {path}"]
    zip_md5 = hashlib.md5(path.read_bytes()).hexdigest()
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename).name
            if not name or name.startswith("._") or info.filename.startswith("__MACOSX/"):
                continue
            if Path(name).suffix.lower() not in {".fa", ".fna", ".fasta"}:
                warnings.append(f"ignored non-FASTA member: {info.filename}")
                continue
            source_id = Path(name).stem
            with archive.open(info) as handle:
                text = handle.read().decode("utf-8", errors="replace")
            length, gc, sequence_count = fasta_stats(text)
            if source_id in inventory:
                warnings.append(f"duplicate phage source_id in zip; keeping first: {source_id}")
                continue
            inventory[source_id] = {
                "zip_member": info.filename,
                "zip_md5": zip_md5,
                "member_size_bytes": str(info.file_size),
                "genome_length": str(length) if length else "NA",
                "gc_percent": gc,
                "sequence_count": str(sequence_count),
            }
    return inventory, warnings


def phage_rows(phage_ids: list[str], inventory: dict[str, dict[str, str]], study_id: str, source_reference: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source_id in phage_ids:
        inv = inventory.get(source_id, {})
        genome_id = safe_id(f"{study_id}_phage", source_id)
        zip_member = inv.get("zip_member", "NA")
        expected_path = f"data/raw/external/phagehostlearn/phages_genomes/{source_id}.fasta" if zip_member != "NA" else ""
        notes = [
            f"source_id={source_id}",
            f"source_study={study_id}",
            f"source_reference={source_reference}",
            "benchmark_entity=true",
            "review_status=pending_entity_review",
            "spot-test benchmark phage; not yet enabled in source catalog",
            f"zip_member={zip_member}",
            f"zip_md5={inv.get('zip_md5', 'NA')}",
            f"member_size_bytes={inv.get('member_size_bytes', 'NA')}",
            f"sequence_count={inv.get('sequence_count', 'NA')}",
        ]
        rows.append(
            {
                "accession": "NA",
                "genome_id": genome_id,
                "host_species": "Klebsiella pneumoniae species complex",
                "host_strain": "NA",
                "country": "NA",
                "year": "NA",
                "genome_length": inv.get("genome_length", "NA"),
                "gc_percent": inv.get("gc_percent", "NA"),
                "raw_sequence_path": expected_path,
                "notes": "; ".join(notes),
            }
        )
    return rows


def host_rows(host_ids: list[str], study_id: str, source_reference: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source_id in host_ids:
        genome_id = safe_id(f"{study_id}_host", source_id)
        notes = [
            f"source_id={source_id}",
            f"source_study={study_id}",
            f"source_reference={source_reference}",
            "benchmark_entity=true",
            "review_status=pending_entity_review",
            "host genome sequence is expected in Zenodo klebsiella_genomes.zip but was not unpacked into this repository",
            "K/O/ST and assembly accession require review before enabling",
        ]
        rows.append(
            {
                "genome_id": genome_id,
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
                "raw_sequence_path": "",
                "notes": "; ".join(notes),
            }
        )
    return rows


def map_rows(source_ids: list[str], prefix: str, study_id: str, entity_type: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source_id in source_ids:
        rows.append(
            {
                "source_id": source_id,
                "canonical_id": safe_id(prefix, source_id),
                "review_status": "pending",
                "notes": f"generated_from={study_id}; entity_type={entity_type}; reviewer_must_set_review_status_to_reviewed_to_enable; canonical entity row generated in disabled PhageHostLearn source export",
            }
        )
    return rows


def validate_path_collisions(paths: list[Path]) -> None:
    seen: dict[Path, str] = {}
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            raise PhageHostLearnExportError(f"path collision: {path} and {seen[resolved]}")
        seen[resolved] = path.as_posix()


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    matrix_path = resolve(root, args.matrix)
    phage_zip_path = resolve(root, args.phage_zip) if normalize(args.phage_zip) else Path()
    outputs = [
        resolve(root, args.phage_export_output),
        resolve(root, args.host_export_output),
        resolve(root, args.phage_map_output),
        resolve(root, args.host_map_output),
        resolve(root, args.report_output),
    ]
    validate_path_collisions(outputs)
    if not matrix_path.exists():
        raise PhageHostLearnExportError(f"matrix does not exist: {matrix_path}")
    phage_ids, host_ids, tested, positive, negative = read_matrix_ids(matrix_path)
    inventory, warnings = load_phage_zip_inventory(phage_zip_path) if str(phage_zip_path) else ({}, ["phage zip not configured"])
    phages = phage_rows(phage_ids, inventory, args.study_id, args.source_reference)
    hosts = host_rows(host_ids, args.study_id, args.source_reference)
    phage_map = map_rows(phage_ids, f"{args.study_id}_phage", args.study_id, "phage")
    host_map = map_rows(host_ids, f"{args.study_id}_host", args.study_id, "host")
    report = [
        {"severity": "info", "item": "matrix", "message": f"phage_source_ids={len(phage_ids)}; host_source_ids={len(host_ids)}; tested_cells={tested}; positives={positive}; negatives={negative}"},
        {"severity": "info", "item": "phage_zip", "message": f"inventory_rows={len(inventory)}; matched_matrix_phages={sum(1 for pid in phage_ids if pid in inventory)}"},
        {"severity": "info", "item": "exports", "message": f"phage_export_rows={len(phages)}; host_export_rows={len(hosts)}; map_rows={len(phage_map) + len(host_map)}"},
    ]
    report.extend({"severity": "warning", "item": "phage_zip", "message": warning} for warning in warnings[:100])
    missing_inventory = [pid for pid in phage_ids if pid not in inventory]
    if missing_inventory:
        report.append({"severity": "warning", "item": "missing_phage_inventory", "message": ";".join(missing_inventory[:50])})
    write_tsv_atomic(resolve(root, args.phage_export_output), PHAGE_EXPORT_COLUMNS, phages)
    write_tsv_atomic(resolve(root, args.host_export_output), HOST_EXPORT_COLUMNS, hosts)
    write_tsv_atomic(resolve(root, args.phage_map_output), MAP_COLUMNS, phage_map)
    write_tsv_atomic(resolve(root, args.host_map_output), MAP_COLUMNS, host_map)
    write_tsv_atomic(resolve(root, args.report_output), REPORT_COLUMNS, report)
    print(f"PhageHostLearn source exports complete: phages={len(phages)}; hosts={len(hosts)}; tested_cells={tested}.")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except PhageHostLearnExportError as exc:
        print(f"PhageHostLearn source export failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
