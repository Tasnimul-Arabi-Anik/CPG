#!/usr/bin/env python3
"""Normalize reviewed RBP/depolymerase domain and structural evidence outputs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


DOMAIN_COLUMNS = [
    "annotation_gene_id",
    "domain_id",
    "domain_name",
    "start_aa",
    "end_aa",
    "evalue",
    "evidence_source",
    "notes",
]
STRUCTURAL_COLUMNS = [
    "annotation_gene_id",
    "structural_hit_id",
    "structural_hit_name",
    "tm_score",
    "probability",
    "evidence_source",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize reviewed external RBP/depolymerase evidence into the TSV "
            "schemas consumed by Stage 4. This script does not run HMMER, Phold, or Foldseek."
        )
    )
    parser.add_argument("--domain-input", default="", help="Optional reviewed domain/profile result file.")
    parser.add_argument(
        "--domain-format",
        default="generic_tsv",
        choices=["generic_tsv", "hmmer_domtblout"],
        help="Format for --domain-input.",
    )
    parser.add_argument("--structural-input", default="", help="Optional reviewed structural result file.")
    parser.add_argument(
        "--structural-format",
        default="generic_tsv",
        choices=["generic_tsv", "foldseek_tsv", "phold_tsv"],
        help="Format for --structural-input.",
    )
    parser.add_argument("--domain-output", required=True, help="Output normalized domain evidence TSV.")
    parser.add_argument("--structural-output", required=True, help="Output normalized structural evidence TSV.")
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


def first_value(row: dict[str, str], aliases: list[str]) -> str:
    for alias in aliases:
        if alias in row and not is_missing(row[alias]):
            return row[alias]
    lowered = {key.lower().replace(" ", "_"): value for key, value in row.items()}
    for alias in aliases:
        key = alias.lower().replace(" ", "_")
        if key in lowered and not is_missing(lowered[key]):
            return lowered[key]
    return ""


def normalize_domain_generic(path: Path) -> list[dict[str, str]]:
    _, rows = read_tsv(path)
    output = []
    for row in rows:
        annotation_gene_id = first_value(row, ["annotation_gene_id", "target_name", "target", "protein_id", "query", "qseqid"])
        domain_id = first_value(row, ["domain_id", "hmm_id", "profile_id", "query_name", "domain", "sseqid"])
        domain_name = first_value(row, ["domain_name", "hmm_name", "profile_name", "query_description", "description", "hit_name"])
        if is_missing(annotation_gene_id) or is_missing(domain_id):
            continue
        output.append(
            {
                "annotation_gene_id": annotation_gene_id,
                "domain_id": domain_id,
                "domain_name": domain_name or domain_id,
                "start_aa": first_value(row, ["start_aa", "ali_from", "qstart", "start"]),
                "end_aa": first_value(row, ["end_aa", "ali_to", "qend", "end"]),
                "evalue": first_value(row, ["evalue", "i_evalue", "E-value", "eval"]),
                "evidence_source": first_value(row, ["evidence_source", "tool", "source"]) or str(path),
                "notes": first_value(row, ["notes"]) or "normalized reviewed domain evidence",
            }
        )
    return output


def normalize_domain_hmmer_domtblout(path: Path) -> list[dict[str, str]]:
    output = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(maxsplit=22)
            if len(parts) < 22:
                continue
            target_name = parts[0]
            query_name = parts[3]
            i_evalue = parts[12]
            ali_from = parts[17]
            ali_to = parts[18]
            description = parts[22] if len(parts) > 22 else query_name
            output.append(
                {
                    "annotation_gene_id": target_name,
                    "domain_id": query_name,
                    "domain_name": description or query_name,
                    "start_aa": ali_from,
                    "end_aa": ali_to,
                    "evalue": i_evalue,
                    "evidence_source": f"hmmer_domtblout:{path}",
                    "notes": "normalized reviewed HMMER domtblout evidence; assumes target name is annotation_gene_id",
                }
            )
    return output


def normalize_structural_generic(path: Path) -> list[dict[str, str]]:
    _, rows = read_tsv(path)
    output = []
    for row in rows:
        annotation_gene_id = first_value(row, ["annotation_gene_id", "query", "qseqid", "protein_id", "target_name"])
        hit_id = first_value(row, ["structural_hit_id", "target", "sseqid", "hit_id", "template", "fold"])
        hit_name = first_value(row, ["structural_hit_name", "target_name", "hit_name", "description", "template_name"])
        if is_missing(annotation_gene_id) or is_missing(hit_id):
            continue
        output.append(
            {
                "annotation_gene_id": annotation_gene_id,
                "structural_hit_id": hit_id,
                "structural_hit_name": hit_name or hit_id,
                "tm_score": first_value(row, ["tm_score", "alntmscore", "qtmscore", "ttmscore"]),
                "probability": first_value(row, ["probability", "prob", "confidence", "score"]),
                "evidence_source": first_value(row, ["evidence_source", "tool", "source"]) or str(path),
                "notes": first_value(row, ["notes"]) or "normalized reviewed structural evidence",
            }
        )
    return output


def normalize_structural_foldseek(path: Path) -> list[dict[str, str]]:
    return normalize_structural_generic(path)


def normalize_structural_phold(path: Path) -> list[dict[str, str]]:
    return normalize_structural_generic(path)


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []
    domain_rows: list[dict[str, str]] = []
    structural_rows: list[dict[str, str]] = []

    if not is_missing(args.domain_input):
        domain_path = Path(args.domain_input)
        if args.domain_format == "hmmer_domtblout":
            domain_rows = normalize_domain_hmmer_domtblout(domain_path)
        else:
            domain_rows = normalize_domain_generic(domain_path)
        report.append({"severity": "info", "item": "domain_evidence", "message": f"normalized_rows={len(domain_rows)}; input={domain_path}"})
    else:
        report.append({"severity": "info", "item": "domain_evidence", "message": "no domain input supplied; wrote header-only output"})

    if not is_missing(args.structural_input):
        structural_path = Path(args.structural_input)
        if args.structural_format == "foldseek_tsv":
            structural_rows = normalize_structural_foldseek(structural_path)
        elif args.structural_format == "phold_tsv":
            structural_rows = normalize_structural_phold(structural_path)
        else:
            structural_rows = normalize_structural_generic(structural_path)
        report.append({"severity": "info", "item": "structural_evidence", "message": f"normalized_rows={len(structural_rows)}; input={structural_path}"})
    else:
        report.append({"severity": "info", "item": "structural_evidence", "message": "no structural input supplied; wrote header-only output"})

    write_tsv(Path(args.domain_output), DOMAIN_COLUMNS, domain_rows)
    write_tsv(Path(args.structural_output), STRUCTURAL_COLUMNS, structural_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
