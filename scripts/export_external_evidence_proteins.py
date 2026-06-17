#!/usr/bin/env python3
"""Export normalized phage proteins for external domain and structural evidence runs."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable


MANIFEST_COLUMNS = [
    "annotation_gene_id",
    "genome_id",
    "gene_id",
    "product",
    "protein_length_aa",
    "functional_category",
    "module_hint",
    "candidate_priority",
    "candidate_reason",
    "sequence_source",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
RBP_PATTERN = re.compile(
    r"receptor[- ]?binding|tail ?fiber|tail ?spike|tailspike|baseplate|host[- ]?range|adhesin",
    re.I,
)
DEPOLYMERASE_PATTERN = re.compile(
    r"depolymerase|capsul(?:e|ar)|polysaccharide|glycosidase|glycanase|(?:^|[_\s-])lyase(?:$|[_\s-])|hyaluronidase|pectate|sialidase",
    re.I,
)
EXCLUSION_PATTERN = re.compile(r"terminase|capsid|portal|holin|endolysin|integrase|polymerase|helicase", re.I)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export reviewed normalized protein sequences for external HMM/profile, "
            "Foldseek, Phold, or related RBP/depolymerase evidence runs."
        )
    )
    parser.add_argument("--annotations", required=True, help="Normalized phage annotation TSV.")
    parser.add_argument("--all-proteins-output", required=True, help="Output FASTA for all proteins with sequences.")
    parser.add_argument("--candidate-proteins-output", required=True, help="Output FASTA for RBP/depolymerase-prioritized proteins.")
    parser.add_argument("--manifest-output", required=True, help="Output protein export manifest TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def fasta_header(row: dict[str, str]) -> str:
    annotation_gene_id = row.get("annotation_gene_id", "") or row.get("gene_id", "")
    genome_id = row.get("genome_id", "")
    product = row.get("product", "")
    return f"{annotation_gene_id} genome={genome_id} product={product}".replace("\n", " ")


def wrap_sequence(sequence: str, width: int = 80) -> str:
    return "\n".join(sequence[index : index + width] for index in range(0, len(sequence), width))


def write_fasta(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for row in rows:
        sequence = row.get("protein_sequence", "")
        if is_missing(sequence):
            continue
        lines.append(">" + fasta_header(row))
        lines.append(wrap_sequence(sequence))
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def candidate_status(row: dict[str, str]) -> tuple[str, str]:
    text = " ".join(
        [
            row.get("product", ""),
            row.get("functional_category", ""),
            row.get("module_hint", ""),
            row.get("phrog_category", ""),
        ]
    )
    if EXCLUSION_PATTERN.search(text):
        return "background", "excluded_by_core_phage_or_replication_keyword"
    reasons = []
    if RBP_PATTERN.search(text):
        reasons.append("rbp_tail_receptor_keyword")
    if DEPOLYMERASE_PATTERN.search(text):
        reasons.append("depolymerase_capsule_glycan_keyword")
    if row.get("module_hint", "").lower() in {"rbp_depolymerase", "tail_fiber", "tailspike"}:
        reasons.append("module_hint")
    if row.get("functional_category", "").lower() in {"rbp_depolymerase", "structural"} and reasons:
        reasons.append("functional_category_context")
    if reasons:
        return "rbp_depolymerase_priority", ";".join(dict.fromkeys(reasons))
    return "background", "no_rbp_depolymerase_priority_signal"


def build_manifest(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    manifest = []
    for row in rows:
        if is_missing(row.get("protein_sequence")):
            continue
        priority, reason = candidate_status(row)
        manifest.append(
            {
                "annotation_gene_id": row.get("annotation_gene_id", "") or row.get("gene_id", ""),
                "genome_id": row.get("genome_id", ""),
                "gene_id": row.get("gene_id", ""),
                "product": row.get("product", ""),
                "protein_length_aa": row.get("protein_length_aa", ""),
                "functional_category": row.get("functional_category", ""),
                "module_hint": row.get("module_hint", ""),
                "candidate_priority": priority,
                "candidate_reason": reason,
                "sequence_source": row.get("tool", "") or row.get("evidence", "") or "normalized_annotation_table",
                "notes": (
                    "Protein export for external domain/profile and structure-informed evidence runs; "
                    "priority labels are run-target hints, not domain or structural evidence."
                ),
            }
        )
    return manifest


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []
    annotation_path = Path(args.annotations)
    fields, rows = read_tsv(annotation_path)
    required = ["genome_id", "product", "protein_sequence"]
    missing = [column for column in required if column not in fields]
    if missing:
        write_tsv(Path(args.manifest_output), MANIFEST_COLUMNS, [])
        write_tsv(
            Path(args.report_output),
            REPORT_COLUMNS,
            [{"severity": "error", "item": "protein_export", "message": "Missing annotation columns: " + ";".join(missing)}],
        )
        Path(args.all_proteins_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.all_proteins_output).write_text("", encoding="utf-8")
        Path(args.candidate_proteins_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.candidate_proteins_output).write_text("", encoding="utf-8")
        return 1

    protein_rows = [row for row in rows if not is_missing(row.get("protein_sequence"))]
    manifest_rows = build_manifest(protein_rows)
    candidate_ids = {
        row["annotation_gene_id"]
        for row in manifest_rows
        if row.get("candidate_priority") == "rbp_depolymerase_priority"
    }
    candidate_rows = [
        row
        for row in protein_rows
        if (row.get("annotation_gene_id", "") or row.get("gene_id", "")) in candidate_ids
    ]

    write_fasta(Path(args.all_proteins_output), protein_rows)
    write_fasta(Path(args.candidate_proteins_output), candidate_rows)
    write_tsv(Path(args.manifest_output), MANIFEST_COLUMNS, manifest_rows)
    report.append(
        {
            "severity": "info",
            "item": "protein_export",
            "message": (
                f"annotation_rows={len(rows)}; protein_rows={len(protein_rows)}; "
                f"candidate_proteins={len(candidate_rows)}"
            ),
        }
    )
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
