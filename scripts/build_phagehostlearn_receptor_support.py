#!/usr/bin/env python3
"""Normalize PhageHostLearn RBPbase/Locibase bridge metadata.

This script converts reviewed local PhageHostLearn support files into small,
tracked bridge-evidence tables. RBPbase/Locibase metadata are not production
K/O typing or structure-informed RBP evidence; they only exercise seed H1b
spot-interaction screening paths.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable

PHAGE_COLUMNS = [
    "phage_genome_id",
    "source_phage_id",
    "support_source",
    "receptor_support_status",
    "protein_count",
    "protein_count_bin",
    "max_xgb_score",
    "max_xgb_score_bin",
    "protein_ids",
    "source_file_sha256",
    "notes",
]

HOST_COLUMNS = [
    "host_genome_id",
    "source_host_id",
    "support_source",
    "receptor_support_status",
    "locus_protein_count",
    "locus_protein_count_bin",
    "locus_fingerprint_sha256",
    "source_file_sha256",
    "notes",
]

REPORT_COLUMNS = ["severity", "item", "message"]
REVIEWED = {"reviewed", "accepted", "pass"}
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize PhageHostLearn RBPbase/Locibase bridge metadata.")
    parser.add_argument("--rbpbase", required=True, help="Reviewed local RBPbase.csv.")
    parser.add_argument("--locibase", required=True, help="Reviewed local Locibase.json.")
    parser.add_argument("--locibase-invitro", default="", help="Optional reviewed local Locibase_invitro.json.")
    parser.add_argument("--phage-map", required=True, help="Source-to-canonical phage ID map TSV.")
    parser.add_argument("--host-map", required=True, help="Source-to-canonical host ID map TSV.")
    parser.add_argument("--phage-output", required=True, help="Output phage bridge-metadata TSV.")
    parser.add_argument("--host-output", required=True, help="Output host bridge-metadata TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def normalize(value: str | None) -> str:
    return "" if value is None else value.strip()


def count_bin(value: int) -> str:
    if value <= 0:
        return "0"
    if value == 1:
        return "1"
    return "2plus"


def score_bin(value: float | None) -> str:
    if value is None:
        return "no_score"
    if value >= 0.9:
        return "xgb_score_ge_0_9"
    if value >= 0.5:
        return "xgb_score_0_5_to_0_9"
    return "xgb_score_lt_0_5"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        return fieldnames, [{key: normalize(value) for key, value in row.items()} for row in reader]


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def reviewed_map(path: Path) -> dict[str, str]:
    fields, rows = read_tsv(path)
    required = {"source_id", "canonical_id", "review_status"}
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(f"{path} missing required columns: {', '.join(missing)}")
    mapping: dict[str, str] = {}
    duplicates: set[str] = set()
    for row in rows:
        source_id = row.get("source_id", "")
        canonical_id = row.get("canonical_id", "")
        status = row.get("review_status", "").lower()
        if is_missing(source_id) or is_missing(canonical_id) or status not in REVIEWED:
            continue
        if source_id in mapping and mapping[source_id] != canonical_id:
            duplicates.add(source_id)
        mapping[source_id] = canonical_id
    if duplicates:
        raise ValueError(f"Ambiguous reviewed source-ID mapping in {path}: {', '.join(sorted(duplicates)[:10])}")
    return mapping


def parse_score(value: str) -> float | None:
    if is_missing(value):
        return None
    try:
        score = float(value)
    except ValueError:
        return None
    return score if math.isfinite(score) else None


def normalize_rbpbase(path: Path, mapping: dict[str, str], file_hash: str) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"phage_ID", "protein_ID", "xgb_score"}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"{path} missing required columns: {', '.join(missing)}")
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in reader:
            source_id = normalize(row.get("phage_ID"))
            if source_id in mapping:
                grouped[source_id].append({key: normalize(value) for key, value in row.items()})

    rows: list[dict[str, str]] = []
    for source_id, evidence_rows in sorted(grouped.items()):
        scores = [parse_score(row.get("xgb_score", "")) for row in evidence_rows]
        present_scores = [score for score in scores if score is not None]
        max_score = max(present_scores) if present_scores else None
        protein_ids = sorted({row.get("protein_ID", "") for row in evidence_rows if not is_missing(row.get("protein_ID"))})
        rows.append(
            {
                "phage_genome_id": mapping[source_id],
                "source_phage_id": source_id,
                "support_source": "PhageHostLearn_RBPbase",
                "receptor_support_status": "seed_rbpbase_support",
                "protein_count": str(len(evidence_rows)),
                "protein_count_bin": count_bin(len(evidence_rows)),
                "max_xgb_score": "" if max_score is None else f"{max_score:.6f}",
                "max_xgb_score_bin": score_bin(max_score),
                "protein_ids": ";".join(protein_ids),
                "source_file_sha256": file_hash,
                "notes": "Seed RBPbase bridge metadata from PhageHostLearn; not production structural/domain annotation and not functional receptor-specificity proof.",
            }
        )
    return rows


def load_locibase(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object keyed by source host ID: {path}")
    parsed: dict[str, list[str]] = {}
    for key, value in data.items():
        if not isinstance(value, list):
            raise ValueError(f"Expected list of locus proteins for {key} in {path}")
        parsed[normalize(key)] = [normalize(item) for item in value if isinstance(item, str) and not is_missing(item)]
    return parsed


def fingerprint(sequences: list[str]) -> str:
    digest = hashlib.sha256()
    for sequence in sorted(sequences):
        digest.update(sequence.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def normalize_locibase(locibase: Path, locibase_invitro: Path | None, mapping: dict[str, str]) -> list[dict[str, str]]:
    sources: list[tuple[str, Path, dict[str, list[str]], str]] = []
    sources.append(("Locibase", locibase, load_locibase(locibase), sha256(locibase)))
    if locibase_invitro and locibase_invitro.exists():
        sources.append(("Locibase_invitro", locibase_invitro, load_locibase(locibase_invitro), sha256(locibase_invitro)))

    grouped: dict[str, list[tuple[str, list[str], str]]] = defaultdict(list)
    for source_name, _path, data, file_hash in sources:
        for source_id, sequences in data.items():
            if source_id in mapping:
                grouped[source_id].append((source_name, sequences, file_hash))

    rows: list[dict[str, str]] = []
    for source_id, source_rows in sorted(grouped.items()):
        combined: list[str] = []
        source_names: list[str] = []
        source_hashes: list[str] = []
        for source_name, sequences, file_hash in source_rows:
            source_names.append(source_name)
            source_hashes.append(f"{source_name}:{file_hash}")
            combined.extend(sequences)
        rows.append(
            {
                "host_genome_id": mapping[source_id],
                "source_host_id": source_id,
                "support_source": ";".join(sorted(set(source_names))),
                "receptor_support_status": "seed_locibase_locus_support",
                "locus_protein_count": str(len(combined)),
                "locus_protein_count_bin": count_bin(len(combined)),
                "locus_fingerprint_sha256": fingerprint(combined) if combined else "",
                "source_file_sha256": ";".join(sorted(set(source_hashes))),
                "notes": "Seed Locibase locus bridge metadata from PhageHostLearn; not Kaptive/Kleborate K/O/ST typing and not functional receptor proof.",
            }
        )
    return rows


def main() -> int:
    args = parse_args()
    rbpbase = Path(args.rbpbase)
    locibase = Path(args.locibase)
    locibase_invitro = Path(args.locibase_invitro) if args.locibase_invitro else None
    phage_map = reviewed_map(Path(args.phage_map))
    host_map = reviewed_map(Path(args.host_map))

    phage_rows = normalize_rbpbase(rbpbase, phage_map, sha256(rbpbase))
    host_rows = normalize_locibase(locibase, locibase_invitro, host_map)
    report = [
        {"severity": "info", "item": "phage_bridge_metadata", "message": f"normalized_rows={len(phage_rows)}; reviewed_phage_map_rows={len(phage_map)}"},
        {"severity": "info", "item": "host_bridge_metadata", "message": f"normalized_rows={len(host_rows)}; reviewed_host_map_rows={len(host_map)}"},
        {"severity": "warning", "item": "claim_boundary", "message": "RBPbase/Locibase metadata are seed bridge metadata, not production K/O typing, structural annotation, or functional proof."},
    ]
    write_tsv(Path(args.phage_output), PHAGE_COLUMNS, phage_rows)
    write_tsv(Path(args.host_output), HOST_COLUMNS, host_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Normalized {len(phage_rows)} phage bridge-metadata rows and {len(host_rows)} host bridge-metadata rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
