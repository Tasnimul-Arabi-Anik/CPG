#!/usr/bin/env python3
"""Map Phold/Foldseek receptor-like CDS rows to production annotation IDs.

Phold and Pharokka use CDS identifiers that differ from the current production
Prodigal annotation IDs. This script performs only the project-specific glue:
it maps reviewed Foldseek receptor-like CDS rows to production annotation rows
by same-phage coordinate overlap and writes a normalizer-ready structural
evidence TSV. It does not run Phold, Foldseek, or infer receptor specificity.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

RECEPTOR_FEATURES = {"tail_fiber", "tailspike", "receptor_binding", "depolymerase", "baseplate"}
OUTPUT_COLUMNS = [
    "annotation_gene_id",
    "structural_hit_id",
    "structural_hit_name",
    "tm_score",
    "probability",
    "evidence_source",
    "notes",
    "phage_id",
    "phold_cds_id",
    "feature_type",
    "annotation_confidence",
    "evalue",
    "query_coverage",
    "target_coverage",
    "prostt5_confidence",
    "source_file",
]
UNMAPPED_COLUMNS = [
    "phage_id",
    "phold_cds_id",
    "feature_type",
    "mapping_status",
    "mapping_reason",
    "phold_start",
    "phold_end",
    "phold_strand",
    "candidate_annotation_gene_ids",
]
REPORT_COLUMNS = ["metric", "value", "status", "notes"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phold-hits", default="results/production/phold_assay_phage_relevant_hits.tsv")
    parser.add_argument("--annotation-manifest", default="results/production/annotations/phage_annotations.tsv")
    parser.add_argument("--min-overlap", type=float, default=0.9)
    parser.add_argument("--output", default="data/metadata/production_evidence/phold_foldseek_receptor_structural_input.tsv")
    parser.add_argument("--unmapped-output", default="data/metadata/production_evidence/phold_foldseek_receptor_structural_unmapped.tsv")
    parser.add_argument("--report-output", default="data/metadata/production_evidence/phold_foldseek_receptor_structural_report.tsv")
    return parser.parse_args()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{k: "" if v is None else v for k, v in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def to_int(value: str) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def interval_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    a0, a1 = sorted((a_start, a_end))
    b0, b1 = sorted((b_start, b_end))
    overlap = max(0, min(a1, b1) - max(a0, b0) + 1)
    return overlap / max(1, min(a1 - a0 + 1, b1 - b0 + 1))


def load_annotations(path: Path) -> dict[str, list[dict[str, str]]]:
    annotations: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_tsv(path):
        if row.get("record_type") != "phage":
            continue
        if not row.get("annotation_gene_id"):
            continue
        if to_int(row.get("start", "")) is None or to_int(row.get("end", "")) is None:
            continue
        annotations[row.get("genome_id", "")].append(row)
    return annotations


def load_per_cds_row(cache: dict[str, dict[str, dict[str, str]]], source_file: str, cds_id: str) -> dict[str, str]:
    if source_file not in cache:
        cache[source_file] = {row.get("cds_id", ""): row for row in read_tsv(Path(source_file))}
    return cache[source_file].get(cds_id, {})


def candidate_matches(
    annotations: list[dict[str, str]],
    start: int,
    end: int,
    strand: str,
    min_overlap: float,
) -> list[dict[str, str]]:
    matches = []
    for row in annotations:
        ann_start = to_int(row.get("start", ""))
        ann_end = to_int(row.get("end", ""))
        if ann_start is None or ann_end is None:
            continue
        if strand and row.get("strand") and strand != row.get("strand"):
            continue
        if interval_overlap(start, end, ann_start, ann_end) >= min_overlap:
            matches.append(row)
    return matches


def build_rows(args: argparse.Namespace) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    annotations = load_annotations(Path(args.annotation_manifest))
    per_cds_cache: dict[str, dict[str, dict[str, str]]] = {}
    mapped: list[dict[str, str]] = []
    unmapped: list[dict[str, str]] = []
    counts: Counter[str] = Counter()

    for hit in read_tsv(Path(args.phold_hits)):
        counts["input_rows"] += 1
        if hit.get("feature_type") not in RECEPTOR_FEATURES:
            continue
        counts["receptor_like_rows"] += 1
        if hit.get("annotation_method") != "foldseek":
            counts["carried_pharokka_rows"] += 1
            continue
        counts["foldseek_receptor_like_rows"] += 1
        per_cds = load_per_cds_row(per_cds_cache, hit.get("source_file", ""), hit.get("cds_id", ""))
        start = to_int(per_cds.get("start", ""))
        end = to_int(per_cds.get("end", ""))
        strand = per_cds.get("strand", "")
        if start is None or end is None:
            counts["missing_coordinate_rows"] += 1
            unmapped.append(unmapped_row(hit, "missing_coordinates", "Phold per-CDS row has no usable coordinates.", "", "", ""))
            continue
        matches = candidate_matches(annotations.get(hit.get("phage_id", ""), []), start, end, strand, args.min_overlap)
        if len(matches) != 1:
            status = "no_coordinate_match" if not matches else "ambiguous_coordinate_match"
            counts[status] += 1
            unmapped.append(
                unmapped_row(
                    hit,
                    status,
                    f"Expected exactly one production annotation overlap at min_overlap={args.min_overlap}.",
                    str(start),
                    str(end),
                    strand,
                    ";".join(row.get("annotation_gene_id", "") for row in matches) or "NA",
                )
            )
            continue
        ann = matches[0]
        counts["mapped_rows"] += 1
        mapped.append(
            {
                "annotation_gene_id": ann.get("annotation_gene_id", ""),
                "structural_hit_id": per_cds.get("tophit_protein") or f"{hit.get('annotation_source') or 'foldseek'}:{hit.get('product')}",
                "structural_hit_name": hit.get("product", ""),
                "tm_score": "",
                "probability": "",
                "evidence_source": "Phold/Foldseek receptor-like structural annotation mapped by coordinate overlap",
                "notes": (
                    "Computational structural/remote-homology candidate only; not capsule specificity or functional validation; "
                    f"phold_cds_id={hit.get('cds_id')}; feature_type={hit.get('feature_type')}; "
                    f"annotation_confidence={hit.get('annotation_confidence')}; evalue={hit.get('evalue')}; "
                    f"query_coverage={hit.get('query_coverage')}; target_coverage={hit.get('target_coverage')}; "
                    f"prostt5_confidence={hit.get('prostt5_confidence')}"
                ),
                "phage_id": hit.get("phage_id", ""),
                "phold_cds_id": hit.get("cds_id", ""),
                "feature_type": hit.get("feature_type", ""),
                "annotation_confidence": hit.get("annotation_confidence", ""),
                "evalue": hit.get("evalue", ""),
                "query_coverage": hit.get("query_coverage", ""),
                "target_coverage": hit.get("target_coverage", ""),
                "prostt5_confidence": hit.get("prostt5_confidence", ""),
                "source_file": hit.get("source_file", ""),
            }
        )

    report = [
        {"metric": "input_rows", "value": str(counts["input_rows"]), "status": "info", "notes": str(Path(args.phold_hits))},
        {"metric": "receptor_like_rows", "value": str(counts["receptor_like_rows"]), "status": "info", "notes": "Phold rows with receptor-like feature labels."},
        {"metric": "carried_pharokka_rows", "value": str(counts["carried_pharokka_rows"]), "status": "info", "notes": "Excluded because they are Pharokka-carried annotations, not Foldseek structural evidence."},
        {"metric": "foldseek_receptor_like_rows", "value": str(counts["foldseek_receptor_like_rows"]), "status": "info", "notes": "Rows eligible for structural evidence mapping."},
        {"metric": "mapped_rows", "value": str(counts["mapped_rows"]), "status": "pass", "notes": "Rows mapped to exactly one production annotation ID."},
        {"metric": "unmapped_rows", "value": str(len(unmapped)), "status": "warning" if unmapped else "pass", "notes": "Unmapped rows are excluded from accepted structural evidence."},
    ]
    return mapped, unmapped, report


def unmapped_row(hit: dict[str, str], status: str, reason: str, start: str, end: str, strand: str, candidates: str = "NA") -> dict[str, str]:
    return {
        "phage_id": hit.get("phage_id", ""),
        "phold_cds_id": hit.get("cds_id", ""),
        "feature_type": hit.get("feature_type", ""),
        "mapping_status": status,
        "mapping_reason": reason,
        "phold_start": start,
        "phold_end": end,
        "phold_strand": strand,
        "candidate_annotation_gene_ids": candidates,
    }


def main() -> int:
    args = parse_args()
    mapped, unmapped, report = build_rows(args)
    write_tsv(Path(args.output), OUTPUT_COLUMNS, mapped)
    write_tsv(Path(args.unmapped_output), UNMAPPED_COLUMNS, unmapped)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Phold/Foldseek structural evidence mapping complete: mapped_rows={len(mapped)}; unmapped_rows={len(unmapped)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
