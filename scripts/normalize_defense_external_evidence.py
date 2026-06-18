#!/usr/bin/env python3
"""Normalize reviewed host-defense and phage anti-defense evidence TSVs."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable


HOST_DEFENSE_COLUMNS = [
    "system",
    "type",
    "sample",
    "genome_id",
    "host_genome_id",
    "subtype",
    "gene_count",
    "genes",
    "contig",
    "start",
    "end",
    "evidence_source",
    "notes",
]
PHAGE_ANTIDEFENSE_COLUMNS = [
    "antidefense_class",
    "phage_genome_id",
    "annotation_gene_id",
    "gene_id",
    "product",
    "target_defense_system",
    "evidence_type",
    "confidence_score",
    "evidence_source",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}

HOST_ALIASES = {
    "host_genome_id": ["host_genome_id", "genome_id", "sample", "sample_id", "assembly", "isolate", "replicon", "seqid"],
    "system": ["system", "defense_system", "defence_system", "system_name", "name", "sys_id", "system_id"],
    "type": ["type", "defense_type", "defence_type", "system_type", "category"],
    "subtype": ["subtype", "defense_subtype", "system_subtype", "subtype_name"],
    "gene_count": ["gene_count", "genes_count", "n_genes", "protein_count", "components"],
    "genes": ["genes", "gene_names", "gene_ids", "proteins", "protein_ids", "targets", "target_name"],
    "contig": ["contig", "contig_id", "sequence", "replicon", "seqid"],
    "start": ["start", "start_pos", "begin", "start_position"],
    "end": ["end", "end_pos", "stop", "stop_position"],
    "evidence_source": ["evidence_source", "tool", "source", "program", "database"],
    "notes": ["notes", "note", "comment", "comments"],
}

PHAGE_ALIASES = {
    "antidefense_class": ["antidefense_class", "anti_defense_class", "counterdefense_class", "class", "category"],
    "phage_genome_id": ["phage_genome_id", "genome_id", "phage_id", "sample", "sample_id", "contig_id", "query_genome_id"],
    "annotation_gene_id": ["annotation_gene_id", "gene", "gene_id_full", "query", "qseqid", "protein_id"],
    "gene_id": ["gene_id", "locus_tag", "protein_id", "target_name", "query"],
    "product": ["product", "annotation", "description", "hit_name", "target", "sseqid", "profile_name"],
    "target_defense_system": ["target_defense_system", "target", "defense_target", "system_target", "target_system"],
    "evidence_type": ["evidence_type", "evidence", "method", "hit_type"],
    "confidence_score": ["confidence_score", "score", "probability", "evalue", "i_evalue", "bitscore"],
    "evidence_source": ["evidence_source", "tool", "source", "database"],
    "notes": ["notes", "note", "comment", "comments"],
}

DEFENSE_TYPE_PATTERNS = [
    ("CRISPR-Cas", re.compile(r"crispr|\bcas\b", re.I)),
    ("restriction-modification", re.compile(r"restriction|methylation|methyltransferase|rm system|type [ivx]+ rm", re.I)),
    ("BREX", re.compile(r"brex", re.I)),
    ("DISARM", re.compile(r"disarm", re.I)),
    ("Abi", re.compile(r"abortive|\babi\b", re.I)),
    ("toxin-antitoxin", re.compile(r"toxin|antitoxin|TA system", re.I)),
    ("retrons", re.compile(r"retron", re.I)),
    ("nuclease-based defense", re.compile(r"nuclease|dnd|wadjet|zorya|septu", re.I)),
]

ANTIDEFENSE_PATTERNS = [
    ("anti_crispr", "CRISPR-Cas", re.compile(r"anti[-_ ]?crispr|\bacr\b|acr[IFV][0-9]", re.I)),
    ("anti_restriction_modification", "restriction-modification", re.compile(r"anti[-_ ]?restriction|restriction alleviation|ocr protein|ard[ab]|methyltransferase|DNA methylase|modification methylase", re.I)),
    ("dna_modification", "restriction-modification", re.compile(r"mom protein|DNA modification|hydroxymethyl|glucosyltransferase|methyltransferase|DNA methylase", re.I)),
    ("nuclease_inhibitor", "nuclease-based defense", re.compile(r"nuclease inhibitor|anti[-_ ]?nuclease|inhibitor of nuclease", re.I)),
    ("recombination_repair", "abortive infection or DNA damage defense", re.compile(r"recombinase|rec[abfor]|single[-_ ]strand annealing|rad52", re.I)),
    ("general_counterdefense", "unknown", re.compile(r"anti[-_ ]?defen[cs]e|counter[-_ ]?defen[cs]e|defense inhibitor", re.I)),
]


class NormalizeError(Exception):
    """Raised for invalid normalizer inputs."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize reviewed DefenseFinder/PADLOC-style host-defense outputs and "
            "reviewed phage anti-defense hit tables into the Stage 6 optional-input schemas. "
            "This script does not run external tools."
        )
    )
    parser.add_argument("--host-defense-input", default="", help="Optional reviewed host-defense result TSV.")
    parser.add_argument(
        "--host-defense-format",
        default="generic_tsv",
        choices=["generic_tsv", "defensefinder_tsv", "padloc_tsv"],
        help="Format label for --host-defense-input. Current parsers use alias-based TSV normalization.",
    )
    parser.add_argument("--phage-antidefense-input", default="", help="Optional reviewed phage anti-defense result TSV.")
    parser.add_argument(
        "--phage-antidefense-format",
        default="generic_tsv",
        choices=["generic_tsv", "reviewed_hits_tsv"],
        help="Format label for --phage-antidefense-input. Current parsers use alias-based TSV normalization.",
    )
    parser.add_argument("--host-defense-output", default="", help="Optional output host defense evidence TSV.")
    parser.add_argument("--phage-antidefense-output", default="", help="Optional output phage anti-defense evidence TSV.")
    parser.add_argument("--report-output", required=True, help="Output normalization report TSV.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise NormalizeError(f"Input does not exist: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def first_value(row: dict[str, str], aliases: list[str]) -> str:
    for alias in aliases:
        if alias in row and not is_missing(row[alias]):
            return row[alias]
    lowered = {key.lower().replace(" ", "_").replace(".", "_"): value for key, value in row.items()}
    for alias in aliases:
        key = alias.lower().replace(" ", "_").replace(".", "_")
        if key in lowered and not is_missing(lowered[key]):
            return lowered[key]
    return ""


def infer_defense_type(system: str, type_value: str, subtype: str) -> str:
    text = " ".join([system, type_value, subtype])
    for label, pattern in DEFENSE_TYPE_PATTERNS:
        if pattern.search(text):
            return label
    return type_value or system or "unknown"


def infer_antidefense(product: str, anti_class: str, target: str) -> tuple[str, str]:
    if not is_missing(anti_class) and not is_missing(target):
        return anti_class, target
    for inferred_class, inferred_target, pattern in ANTIDEFENSE_PATTERNS:
        if pattern.search(product):
            return anti_class or inferred_class, target or inferred_target
    return anti_class or "unknown_counterdefense", target or "unknown"


def normalize_host_defense(path_text: str, format_name: str) -> tuple[list[dict[str, str]], dict[str, str]]:
    if is_missing(path_text):
        return [], {"severity": "info", "item": "host_defense", "message": "no host defense input supplied; wrote header-only output"}
    path = Path(path_text)
    _, rows = read_tsv(path)
    output: list[dict[str, str]] = []
    skipped = 0
    for row in rows:
        host_id = first_value(row, HOST_ALIASES["host_genome_id"])
        system = first_value(row, HOST_ALIASES["system"])
        subtype = first_value(row, HOST_ALIASES["subtype"])
        type_value = infer_defense_type(system, first_value(row, HOST_ALIASES["type"]), subtype)
        if is_missing(host_id) or is_missing(system) or is_missing(type_value):
            skipped += 1
            continue
        notes = first_value(row, HOST_ALIASES["notes"]) or f"normalized reviewed {format_name} host-defense evidence"
        output.append(
            {
                "system": system,
                "type": type_value,
                "sample": host_id,
                "genome_id": host_id,
                "host_genome_id": host_id,
                "subtype": subtype,
                "gene_count": first_value(row, HOST_ALIASES["gene_count"]),
                "genes": first_value(row, HOST_ALIASES["genes"]),
                "contig": first_value(row, HOST_ALIASES["contig"]),
                "start": first_value(row, HOST_ALIASES["start"]),
                "end": first_value(row, HOST_ALIASES["end"]),
                "evidence_source": first_value(row, HOST_ALIASES["evidence_source"]) or f"{format_name}:{path}",
                "notes": notes,
            }
        )
    message = f"normalized_rows={len(output)}; skipped_rows={skipped}; input={path}; format={format_name}"
    return output, {"severity": "info", "item": "host_defense", "message": message}


def derive_phage_id(row: dict[str, str], annotation_gene_id: str) -> str:
    phage_id = first_value(row, PHAGE_ALIASES["phage_genome_id"])
    if not is_missing(phage_id):
        return phage_id
    if "|" in annotation_gene_id:
        return annotation_gene_id.split("|", 1)[0]
    return ""


def normalize_phage_antidefense(path_text: str, format_name: str) -> tuple[list[dict[str, str]], dict[str, str]]:
    if is_missing(path_text):
        return [], {"severity": "info", "item": "phage_antidefense", "message": "no phage anti-defense input supplied; wrote header-only output"}
    path = Path(path_text)
    _, rows = read_tsv(path)
    output: list[dict[str, str]] = []
    skipped = 0
    for row in rows:
        annotation_gene_id = first_value(row, PHAGE_ALIASES["annotation_gene_id"])
        phage_id = derive_phage_id(row, annotation_gene_id)
        product = first_value(row, PHAGE_ALIASES["product"])
        anti_class, target = infer_antidefense(
            product,
            first_value(row, PHAGE_ALIASES["antidefense_class"]),
            first_value(row, PHAGE_ALIASES["target_defense_system"]),
        )
        if is_missing(phage_id) and is_missing(annotation_gene_id):
            skipped += 1
            continue
        notes = first_value(row, PHAGE_ALIASES["notes"]) or f"normalized reviewed {format_name} phage anti-defense evidence"
        output.append(
            {
                "antidefense_class": anti_class,
                "phage_genome_id": phage_id,
                "annotation_gene_id": annotation_gene_id,
                "gene_id": first_value(row, PHAGE_ALIASES["gene_id"]),
                "product": product,
                "target_defense_system": target,
                "evidence_type": first_value(row, PHAGE_ALIASES["evidence_type"]) or format_name,
                "confidence_score": first_value(row, PHAGE_ALIASES["confidence_score"]),
                "evidence_source": first_value(row, PHAGE_ALIASES["evidence_source"]) or f"{format_name}:{path}",
                "notes": notes,
            }
        )
    message = f"normalized_rows={len(output)}; skipped_rows={skipped}; input={path}; format={format_name}"
    return output, {"severity": "info", "item": "phage_antidefense", "message": message}


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []
    host_output_requested = not is_missing(args.host_defense_output)
    anti_output_requested = not is_missing(args.phage_antidefense_output)
    host_input_supplied = not is_missing(args.host_defense_input)
    anti_input_supplied = not is_missing(args.phage_antidefense_input)

    try:
        if not host_output_requested and not anti_output_requested:
            raise NormalizeError("At least one output path must be supplied.")
        host_rows, host_report = normalize_host_defense(args.host_defense_input, args.host_defense_format)
        anti_rows, anti_report = normalize_phage_antidefense(args.phage_antidefense_input, args.phage_antidefense_format)
        report.extend([host_report, anti_report])
        if host_input_supplied and not host_output_requested:
            report.append({"severity": "error", "item": "host_defense", "message": "host defense input was supplied but --host-defense-output is missing"})
        if anti_input_supplied and not anti_output_requested:
            report.append({"severity": "error", "item": "phage_antidefense", "message": "phage anti-defense input was supplied but --phage-antidefense-output is missing"})
        if host_output_requested:
            write_tsv(Path(args.host_defense_output), HOST_DEFENSE_COLUMNS, host_rows)
        if anti_output_requested:
            write_tsv(Path(args.phage_antidefense_output), PHAGE_ANTIDEFENSE_COLUMNS, anti_rows)
    except NormalizeError as exc:
        report.append({"severity": "error", "item": "normalization", "message": str(exc)})
        if host_output_requested:
            write_tsv(Path(args.host_defense_output), HOST_DEFENSE_COLUMNS, [])
        if anti_output_requested:
            write_tsv(Path(args.phage_antidefense_output), PHAGE_ANTIDEFENSE_COLUMNS, [])
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    errors = sum(1 for row in report if row.get("severity") == "error")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
