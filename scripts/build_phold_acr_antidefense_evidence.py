#!/usr/bin/env python3
"""Normalize Phold ACR subdatabase hits as explicit phage anti-CRISPR evidence."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


OUTPUT_COLUMNS = [
    "phage_genome_id",
    "annotation_gene_id",
    "gene_id",
    "gene_cluster_id",
    "product",
    "antidefense_class",
    "target_defense_system",
    "evidence_type",
    "evidence_source",
    "confidence_score",
    "notes",
]

REPORT_COLUMNS = ["metric", "value"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a reviewed phage anti-defense TSV from Phold ACR subdatabase "
            "hits. This normalizes existing Phold/Foldseek evidence; it does not "
            "perform a new anti-defense search."
        )
    )
    parser.add_argument("--phold-root", required=True, help="Directory containing per-phage Phold outputs.")
    parser.add_argument("--annotations", required=True, help="Sequence-backed CDS annotation TSV.")
    parser.add_argument("--output", required=True, help="Output phage anti-defense TSV.")
    parser.add_argument("--report-output", required=True, help="Output normalization report TSV.")
    parser.add_argument("--min-query-coverage", type=float, default=0.35, help="Minimum Phold/Foldseek query coverage.")
    parser.add_argument("--min-target-coverage", type=float, default=0.35, help="Minimum Phold/Foldseek target coverage.")
    parser.add_argument("--min-prostt5-confidence", type=float, default=50.0, help="Minimum Phold ProstT5 confidence.")
    return parser.parse_args()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return reader.fieldnames or [], [dict(row) for row in reader]


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def as_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def annotation_key(phage_id: str, start: str, end: str, strand: str) -> tuple[str, int, int, str]:
    start_i = int(float(start))
    end_i = int(float(end))
    return phage_id, min(start_i, end_i), max(start_i, end_i), strand


def phage_id_from_hit_path(path: Path) -> str:
    for parent in path.parents:
        if parent.name.startswith("phagehostlearn_2024_phage_"):
            return parent.name
    return ""


def acr_target(anti_type: str) -> str:
    cleaned = anti_type.strip().replace('"', "")
    if cleaned:
        return f"CRISPR-Cas Type {cleaned}"
    return "CRISPR-Cas"


def main() -> int:
    args = parse_args()
    phold_root = Path(args.phold_root)
    annotations_path = Path(args.annotations)
    output = Path(args.output)
    report_output = Path(args.report_output)

    _, annotations = read_tsv(annotations_path)
    annotation_by_coord: dict[tuple[str, int, int, str], dict[str, str]] = {}
    for row in annotations:
        if not row.get("genome_id") or not row.get("start") or not row.get("end"):
            continue
        try:
            annotation_by_coord[annotation_key(row["genome_id"], row["start"], row["end"], row.get("strand", ""))] = row
        except ValueError:
            continue

    output_rows: list[dict[str, str]] = []
    files = sorted(phold_root.glob("*/sub_db_tophits/acr_cds_predictions.tsv"))
    data_rows = 0
    filtered_rows = 0
    unmapped_rows = 0
    assessed_phages = set()
    detected_phages = set()

    for path in files:
        phage_id = phage_id_from_hit_path(path)
        if phage_id:
            assessed_phages.add(phage_id)
        _columns, rows = read_tsv(path)
        for hit in rows:
            data_rows += 1
            if as_float(hit.get("qCov", "")) < args.min_query_coverage:
                filtered_rows += 1
                continue
            if as_float(hit.get("tCov", "")) < args.min_target_coverage:
                filtered_rows += 1
                continue
            if as_float(hit.get("prostt5_confidence", "")) < args.min_prostt5_confidence:
                filtered_rows += 1
                continue
            try:
                ann = annotation_by_coord[annotation_key(phage_id, hit.get("start", ""), hit.get("end", ""), hit.get("strand", ""))]
            except (KeyError, ValueError):
                unmapped_rows += 1
                continue
            detected_phages.add(phage_id)
            family = hit.get("Family", "anti-CRISPR").strip() or "anti-CRISPR"
            anti_type = hit.get("Anti_type", "").strip()
            output_rows.append(
                {
                    "phage_genome_id": phage_id,
                    "annotation_gene_id": ann.get("protein_id", ""),
                    "gene_id": ann.get("gene_id", ""),
                    "gene_cluster_id": "",
                    "product": f"Phold ACR hit: {family}",
                    "antidefense_class": "anti_crispr",
                    "target_defense_system": acr_target(anti_type),
                    "evidence_type": "phold_acr_structural_hit",
                    "evidence_source": "Phold 1.2.5 ACR subdatabase; Foldseek v10.941cd33; phold_db acrs_plddt_over_70_metadata.tsv",
                    "confidence_score": f"{as_float(hit.get('prostt5_confidence', '')):.3f}",
                    "notes": (
                        f"anti_CRISPR_id={hit.get('anti_CRISPR_id', '')}; "
                        f"family={family}; anti_type={anti_type or 'NA'}; "
                        f"classify={hit.get('classify', '')}; accession={hit.get('Accession', '')}; "
                        f"bitscore={hit.get('bitscore', '')}; evalue={hit.get('evalue', '')}; "
                        f"qCov={hit.get('qCov', '')}; tCov={hit.get('tCov', '')}; "
                        "computational anti-CRISPR candidate; does not prove productive infection or defense escape"
                    ),
                }
            )

    output_rows.sort(key=lambda row: (row["phage_genome_id"], row["gene_id"], row["product"]))
    write_tsv(output, OUTPUT_COLUMNS, output_rows)
    write_tsv(
        report_output,
        REPORT_COLUMNS,
        [
            {"metric": "phold_acr_files", "value": str(len(files))},
            {"metric": "assessed_phages", "value": str(len(assessed_phages))},
            {"metric": "raw_acr_rows", "value": str(data_rows)},
            {"metric": "accepted_acr_rows", "value": str(len(output_rows))},
            {"metric": "detected_phages", "value": str(len(detected_phages))},
            {"metric": "filtered_rows", "value": str(filtered_rows)},
            {"metric": "unmapped_rows", "value": str(unmapped_rows)},
            {"metric": "min_query_coverage", "value": f"{args.min_query_coverage:.3f}"},
            {"metric": "min_target_coverage", "value": f"{args.min_target_coverage:.3f}"},
            {"metric": "min_prostt5_confidence", "value": f"{args.min_prostt5_confidence:.3f}"},
        ],
    )
    print(f"Normalized {len(output_rows)} Phold ACR anti-defense candidates across {len(detected_phages)} phages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
