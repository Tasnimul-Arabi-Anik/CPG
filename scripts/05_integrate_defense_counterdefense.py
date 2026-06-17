#!/usr/bin/env python3
"""Integrate host defense systems and phage anti-defense candidates."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable


HOST_DEFENSE_COLUMNS = [
    "host_genome_id",
    "defense_system_id",
    "defense_system",
    "defense_type",
    "defense_subtype",
    "gene_count",
    "genes",
    "contig_id",
    "start",
    "end",
    "evidence_source",
    "confidence",
    "notes",
]

PHAGE_ANTIDEFENSE_COLUMNS = [
    "phage_genome_id",
    "candidate_id",
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

COMPATIBILITY_COLUMNS = [
    "phage_genome_id",
    "record_type",
    "species_cluster_id",
    "representative_id",
    "host_genome_id",
    "host_link_status",
    "K_type",
    "O_type",
    "ST",
    "host_defense_system_count",
    "host_defense_types",
    "host_defense_systems",
    "phage_antidefense_count",
    "phage_antidefense_classes",
    "phage_antidefense_targets",
    "matched_counterdefense_count",
    "matched_counterdefense_targets",
    "receptor_metadata_available",
    "defense_metadata_available",
    "counterdefense_metadata_available",
    "compatibility_feature_status",
    "notes",
]

REPORT_COLUMNS = ["severity", "item", "message"]

HOST_ID_ALIASES = ["host_genome_id", "genome_id", "sample", "Sample", "sample_id", "assembly", "host", "isolate", "Isolate"]
PHAGE_ID_ALIASES = ["phage_genome_id", "genome_id", "sample", "Sample", "phage_id", "contig_id", "isolate"]

HOST_DEFENSE_ALIASES = {
    "defense_system": ["defense_system", "system", "system_name", "name", "Defense system", "defence_system"],
    "defense_type": ["defense_type", "system_type", "type", "Defense type", "category"],
    "defense_subtype": ["defense_subtype", "subtype", "system_subtype", "subtype_name"],
    "gene_count": ["gene_count", "genes_count", "n_genes", "protein_count"],
    "genes": ["genes", "gene_names", "proteins", "protein_ids", "gene_ids"],
    "contig_id": ["contig_id", "contig", "sequence", "replicon"],
    "start": ["start", "start_pos", "begin"],
    "end": ["end", "end_pos", "stop"],
    "evidence_source": ["evidence_source", "tool", "source", "program"],
    "confidence": ["confidence", "score", "system_confidence"],
}

PHAGE_ANTIDEFENSE_ALIASES = {
    "candidate_id": ["candidate_id", "antidefense_candidate_id", "feature_id", "hit_id"],
    "annotation_gene_id": ["annotation_gene_id", "gene", "gene_id_full"],
    "gene_id": ["gene_id", "locus_tag", "protein_id"],
    "gene_cluster_id": ["gene_cluster_id", "cluster_id"],
    "product": ["product", "annotation", "description", "hit_name"],
    "antidefense_class": ["antidefense_class", "anti_defense_class", "class", "category"],
    "target_defense_system": ["target_defense_system", "target", "defense_target", "system_target"],
    "evidence_type": ["evidence_type", "evidence", "method"],
    "evidence_source": ["evidence_source", "tool", "source", "database"],
    "confidence_score": ["confidence_score", "score", "probability"],
}

ANTIDEFENSE_PATTERNS = [
    ("anti_crispr", "CRISPR-Cas", re.compile(r"anti[-_ ]?crispr|\bacr\b|acr[IFV][0-9]", re.I)),
    ("anti_restriction_modification", "restriction-modification", re.compile(r"anti[-_ ]?restriction|restriction alleviation|ocr protein|ard[ab]|methyltransferase|DNA methylase|dam methylase|modification methylase", re.I)),
    ("dna_modification", "restriction-modification", re.compile(r"mom protein|DNA modification|hydroxymethyl|glucosyltransferase|methyltransferase|DNA methylase", re.I)),
    ("nuclease_inhibitor", "nuclease-based defense", re.compile(r"nuclease inhibitor|anti[-_ ]?nuclease|inhibitor of nuclease", re.I)),
    ("recombination_repair", "abortive infection or DNA damage defense", re.compile(r"recombinase|rec[abfor]|single[-_ ]strand annealing|rad52", re.I)),
    ("general_counterdefense", "unknown", re.compile(r"anti[-_ ]?defen[cs]e|counter[-_ ]?defen[cs]e|defense inhibitor", re.I)),
]

DEFENSE_NORMALIZATION = [
    ("CRISPR-Cas", re.compile(r"crispr|cas", re.I)),
    ("restriction-modification", re.compile(r"restriction|methylation|methyltransferase|rm system|type i rm|type ii rm|type iii rm", re.I)),
    ("BREX", re.compile(r"brex", re.I)),
    ("DISARM", re.compile(r"disarm", re.I)),
    ("Abi", re.compile(r"abortive|\babi\b", re.I)),
    ("toxin-antitoxin", re.compile(r"toxin|antitoxin|TA system", re.I)),
    ("retrons", re.compile(r"retron", re.I)),
    ("nuclease-based defense", re.compile(r"nuclease|dnd|wadjet|zorya|septu", re.I)),
]


class StageError(Exception):
    """Raised when required inputs are invalid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build host defense, phage anti-defense, and compatibility feature "
            "tables from host links, annotations, and optional PADLOC/DefenseFinder-like outputs."
        )
    )
    parser.add_argument("--host-metadata", required=True, help="Stage 5 host_metadata.tsv.")
    parser.add_argument("--phage-host-links", required=True, help="Stage 5 phage_host_links.tsv.")
    parser.add_argument("--annotations", required=True, help="Stage 3 phage_annotations.tsv.")
    parser.add_argument("--host-defense-input", default="", help="Optional PADLOC/DefenseFinder-style host defense TSV.")
    parser.add_argument("--phage-antidefense-input", default="", help="Optional phage anti-defense TSV.")
    parser.add_argument("--host-defense-output", required=True, help="Output normalized host defense systems TSV.")
    parser.add_argument("--phage-antidefense-output", required=True, help="Output normalized phage anti-defense candidates TSV.")
    parser.add_argument("--compatibility-output", required=True, help="Output compatibility feature TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def normalize(value: str | None) -> str:
    return "" if value is None else value.strip()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(f"Required input does not exist: {path}")
    with path.open(newline="") as handle:
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


def add_report(report: list[dict[str, str]], severity: str, item: str, message: str) -> None:
    report.append({"severity": severity, "item": item, "message": message})


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


def normalized_defense_type(defense_system: str, defense_type: str, subtype: str) -> str:
    text = " ".join([defense_system, defense_type, subtype])
    for label, pattern in DEFENSE_NORMALIZATION:
        if pattern.search(text):
            return label
    return defense_type or defense_system or "unknown"


def normalize_host_defense(path_text: str, known_hosts: set[str], report: list[dict[str, str]]) -> list[dict[str, str]]:
    if is_missing(path_text):
        add_report(report, "info", "host_defense", "No host defense table supplied; host defense output contains headers only.")
        return []
    path = Path(path_text)
    if not path.exists():
        add_report(report, "warning", "host_defense", f"Host defense table does not exist: {path}; continuing without it.")
        return []
    fieldnames, rows = read_tsv(path)
    if not fieldnames:
        add_report(report, "warning", "host_defense", f"Host defense table has no header: {path}.")
        return []

    normalized_rows: list[dict[str, str]] = []
    skipped_no_host = 0
    unknown_host = 0
    for index, row in enumerate(rows, start=1):
        host_id = first_value(row, HOST_ID_ALIASES)
        if is_missing(host_id):
            skipped_no_host += 1
            continue
        if known_hosts and host_id not in known_hosts:
            unknown_host += 1
        defense_system = first_value(row, HOST_DEFENSE_ALIASES["defense_system"])
        defense_subtype = first_value(row, HOST_DEFENSE_ALIASES["defense_subtype"])
        defense_type = normalized_defense_type(
            defense_system,
            first_value(row, HOST_DEFENSE_ALIASES["defense_type"]),
            defense_subtype,
        )
        normalized_rows.append(
            {
                "host_genome_id": host_id,
                "defense_system_id": row.get("defense_system_id", "") or f"host_defense_{len(normalized_rows) + 1:06d}",
                "defense_system": defense_system or defense_type,
                "defense_type": defense_type,
                "defense_subtype": defense_subtype,
                "gene_count": first_value(row, HOST_DEFENSE_ALIASES["gene_count"]),
                "genes": first_value(row, HOST_DEFENSE_ALIASES["genes"]),
                "contig_id": first_value(row, HOST_DEFENSE_ALIASES["contig_id"]),
                "start": first_value(row, HOST_DEFENSE_ALIASES["start"]),
                "end": first_value(row, HOST_DEFENSE_ALIASES["end"]),
                "evidence_source": first_value(row, HOST_DEFENSE_ALIASES["evidence_source"]) or str(path),
                "confidence": first_value(row, HOST_DEFENSE_ALIASES["confidence"]),
                "notes": "host not present in host_metadata" if host_id not in known_hosts else "OK",
            }
        )
    if skipped_no_host:
        add_report(report, "warning", "host_defense", f"Skipped {skipped_no_host} rows without host genome IDs.")
    if unknown_host:
        add_report(report, "warning", "host_defense", f"Loaded {unknown_host} defense rows for hosts absent from host_metadata.")
    add_report(report, "info", "host_defense", f"Loaded {len(normalized_rows)} normalized host defense rows from {path}.")
    return normalized_rows


def normalize_explicit_antidefense(path_text: str, report: list[dict[str, str]]) -> list[dict[str, str]]:
    if is_missing(path_text):
        add_report(report, "info", "phage_antidefense", "No explicit phage anti-defense table supplied; annotation inference will be used.")
        return []
    path = Path(path_text)
    if not path.exists():
        add_report(report, "warning", "phage_antidefense", f"Phage anti-defense table does not exist: {path}; continuing without it.")
        return []
    fieldnames, rows = read_tsv(path)
    if not fieldnames:
        add_report(report, "warning", "phage_antidefense", f"Phage anti-defense table has no header: {path}.")
        return []

    normalized_rows = []
    skipped = 0
    for row in rows:
        phage_id = first_value(row, PHAGE_ID_ALIASES)
        annotation_gene_id = first_value(row, PHAGE_ANTIDEFENSE_ALIASES["annotation_gene_id"])
        if is_missing(phage_id) and not is_missing(annotation_gene_id) and "|" in annotation_gene_id:
            phage_id = annotation_gene_id.split("|", 1)[0]
        if is_missing(phage_id):
            skipped += 1
            continue
        product = first_value(row, PHAGE_ANTIDEFENSE_ALIASES["product"])
        anti_class = first_value(row, PHAGE_ANTIDEFENSE_ALIASES["antidefense_class"])
        target = first_value(row, PHAGE_ANTIDEFENSE_ALIASES["target_defense_system"])
        if is_missing(anti_class) or is_missing(target):
            inferred_class, inferred_target = infer_antidefense_class(product)
            anti_class = anti_class or inferred_class
            target = target or inferred_target
        normalized_rows.append(
            {
                "phage_genome_id": phage_id,
                "candidate_id": first_value(row, PHAGE_ANTIDEFENSE_ALIASES["candidate_id"]) or f"explicit_antidefense_{len(normalized_rows) + 1:06d}",
                "annotation_gene_id": annotation_gene_id,
                "gene_id": first_value(row, PHAGE_ANTIDEFENSE_ALIASES["gene_id"]),
                "gene_cluster_id": first_value(row, PHAGE_ANTIDEFENSE_ALIASES["gene_cluster_id"]),
                "product": product,
                "antidefense_class": anti_class or "unknown_counterdefense",
                "target_defense_system": target or "unknown",
                "evidence_type": first_value(row, PHAGE_ANTIDEFENSE_ALIASES["evidence_type"]) or "explicit_table",
                "evidence_source": first_value(row, PHAGE_ANTIDEFENSE_ALIASES["evidence_source"]) or str(path),
                "confidence_score": first_value(row, PHAGE_ANTIDEFENSE_ALIASES["confidence_score"]) or "",
                "notes": "OK",
            }
        )
    if skipped:
        add_report(report, "warning", "phage_antidefense", f"Skipped {skipped} explicit anti-defense rows without phage IDs.")
    add_report(report, "info", "phage_antidefense", f"Loaded {len(normalized_rows)} explicit phage anti-defense rows from {path}.")
    return normalized_rows


def infer_antidefense_class(text: str) -> tuple[str, str]:
    for anti_class, target, pattern in ANTIDEFENSE_PATTERNS:
        if pattern.search(text):
            return anti_class, target
    return "", ""


def infer_antidefense_from_annotations(annotations: list[dict[str, str]]) -> list[dict[str, str]]:
    inferred = []
    for row in annotations:
        product = row.get("product", "")
        text = " ".join([product, row.get("functional_category", ""), row.get("module_hint", "")])
        anti_class, target = infer_antidefense_class(text)
        if not anti_class:
            continue
        inferred.append(
            {
                "phage_genome_id": row.get("genome_id", ""),
                "candidate_id": f"inferred_antidefense_{len(inferred) + 1:06d}",
                "annotation_gene_id": row.get("annotation_gene_id", ""),
                "gene_id": row.get("gene_id", ""),
                "gene_cluster_id": row.get("gene_cluster_id", ""),
                "product": product,
                "antidefense_class": anti_class,
                "target_defense_system": target,
                "evidence_type": "annotation_keyword_inference",
                "evidence_source": row.get("tool", "annotation"),
                "confidence_score": "0.500",
                "notes": "inferred from annotation text; requires validation",
            }
        )
    return inferred


def merge_antidefense_rows(explicit_rows: list[dict[str, str]], inferred_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen_keys = set()
    merged = []
    for row in explicit_rows + inferred_rows:
        key = (
            row.get("phage_genome_id", ""),
            row.get("annotation_gene_id", ""),
            row.get("antidefense_class", ""),
            row.get("target_defense_system", ""),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if not row.get("candidate_id"):
            row["candidate_id"] = f"antidefense_{len(merged) + 1:06d}"
        merged.append(row)
    return merged


def split_semicolon(value: str) -> list[str]:
    if is_missing(value):
        return []
    return [item.strip() for item in re.split(r"[;,]", value) if item.strip()]


def build_compatibility_features(
    links: list[dict[str, str]],
    host_defense: list[dict[str, str]],
    phage_antidefense: list[dict[str, str]],
) -> list[dict[str, str]]:
    defense_by_host: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in host_defense:
        defense_by_host[row.get("host_genome_id", "")].append(row)

    anti_by_phage: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in phage_antidefense:
        anti_by_phage[row.get("phage_genome_id", "")].append(row)

    compatibility_rows = []
    for link in links:
        host_id = link.get("host_genome_id", "")
        phage_id = link.get("phage_genome_id", "")
        host_rows = defense_by_host.get(host_id, [])
        anti_rows = anti_by_phage.get(phage_id, [])
        host_types = sorted({row.get("defense_type", "") for row in host_rows if not is_missing(row.get("defense_type"))})
        host_systems = sorted({row.get("defense_system", "") for row in host_rows if not is_missing(row.get("defense_system"))})
        anti_classes = sorted({row.get("antidefense_class", "") for row in anti_rows if not is_missing(row.get("antidefense_class"))})
        anti_targets = sorted({row.get("target_defense_system", "") for row in anti_rows if not is_missing(row.get("target_defense_system"))})
        matched_targets = sorted({target for target in anti_targets if target in host_types or target in host_systems})
        receptor_metadata = any(not is_missing(link.get(column, "")) for column in ["K_type", "O_type"])
        defense_metadata = bool(host_rows)
        counterdefense_metadata = bool(anti_rows)
        if defense_metadata and counterdefense_metadata:
            status = "receptor_defense_counterdefense_features_available" if receptor_metadata else "defense_counterdefense_features_available_no_receptor_metadata"
        elif defense_metadata:
            status = "host_defense_only"
        elif counterdefense_metadata:
            status = "phage_counterdefense_only"
        else:
            status = "no_defense_counterdefense_features"
        compatibility_rows.append(
            {
                "phage_genome_id": phage_id,
                "record_type": link.get("record_type", ""),
                "species_cluster_id": link.get("species_cluster_id", ""),
                "representative_id": link.get("representative_id", ""),
                "host_genome_id": host_id,
                "host_link_status": link.get("host_link_status", ""),
                "K_type": link.get("K_type", ""),
                "O_type": link.get("O_type", ""),
                "ST": link.get("ST", ""),
                "host_defense_system_count": str(len(host_rows)),
                "host_defense_types": ";".join(host_types),
                "host_defense_systems": ";".join(host_systems),
                "phage_antidefense_count": str(len(anti_rows)),
                "phage_antidefense_classes": ";".join(anti_classes),
                "phage_antidefense_targets": ";".join(anti_targets),
                "matched_counterdefense_count": str(len(matched_targets)),
                "matched_counterdefense_targets": ";".join(matched_targets),
                "receptor_metadata_available": str(receptor_metadata).lower(),
                "defense_metadata_available": str(defense_metadata).lower(),
                "counterdefense_metadata_available": str(counterdefense_metadata).lower(),
                "compatibility_feature_status": status,
                "notes": "OK",
            }
        )
    return compatibility_rows


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []

    try:
        _, host_metadata = read_tsv(Path(args.host_metadata))
        _, links = read_tsv(Path(args.phage_host_links))
        _, annotations = read_tsv(Path(args.annotations))
        known_hosts = {row.get("host_genome_id", "") for row in host_metadata if not is_missing(row.get("host_genome_id"))}
        add_report(report, "info", "inputs", f"Loaded {len(host_metadata)} host rows, {len(links)} phage-host links, and {len(annotations)} annotations.")

        host_defense = normalize_host_defense(args.host_defense_input, known_hosts, report)
        explicit_anti = normalize_explicit_antidefense(args.phage_antidefense_input, report)
        inferred_anti = infer_antidefense_from_annotations(annotations)
        if inferred_anti:
            add_report(report, "info", "phage_antidefense", f"Inferred {len(inferred_anti)} phage anti-defense candidates from annotation text.")
        phage_antidefense = merge_antidefense_rows(explicit_anti, inferred_anti)
        compatibility = build_compatibility_features(links, host_defense, phage_antidefense)
        add_report(report, "info", "compatibility", f"Built {len(compatibility)} compatibility feature rows.")

        write_tsv(Path(args.host_defense_output), HOST_DEFENSE_COLUMNS, host_defense)
        write_tsv(Path(args.phage_antidefense_output), PHAGE_ANTIDEFENSE_COLUMNS, phage_antidefense)
        write_tsv(Path(args.compatibility_output), COMPATIBILITY_COLUMNS, compatibility)
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    except StageError:
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        return 1

    error_count = sum(1 for row in report if row["severity"] == "error")
    print(
        f"Integrated {len(host_defense)} host defense rows, "
        f"{len(phage_antidefense)} phage anti-defense rows, and "
        f"{len(compatibility)} compatibility rows."
    )
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
