#!/usr/bin/env python3
"""Create a column dictionary for reviewed source export templates."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import Iterable


DICTIONARY_COLUMNS = [
    "source_id",
    "query_id",
    "record_layer",
    "target_database",
    "template_path",
    "expected_export_path",
    "column_name",
    "column_role",
    "required_for_identity",
    "recommended_for_layer",
    "description",
    "expected_format",
    "missing_value_policy",
    "validation_notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}

COLUMN_DEFINITIONS = {
    "record_type": ("Record class used by downstream branching.", "One of phage, prophage, metagenomic_viral_contig, or host.", "Required in normalized manifests; exports may use source defaults."),
    "genome_id": ("Stable project genome or contig identifier.", "Short stable string unique within the source export.", "Required when no accession/raw_sequence_path can identify the row."),
    "accession": ("Public accession for genome, contig, assembly, or sequence record.", "NCBI/ENA/DDBJ/INPHARED/literature accession string; semicolon-delimit multiple values.", "Use NA when absent; required for accession-backed retrieval or provenance."),
    "source": ("Source database, study, environment, or collection label.", "Short controlled/free-text source label.", "Use NA when unknown."),
    "isolation_host": ("Reported host used for phage isolation or viral-contig association.", "Free text host organism/strain/sample host.", "Use NA when absent."),
    "host_species": ("Klebsiella host species or species-complex member.", "Scientific name or species-complex label.", "Use NA when absent; keep original source wording when uncertain."),
    "host_strain": ("Host strain or isolate identifier.", "Free text strain/isolate ID.", "Use NA when absent."),
    "country": ("Country or broad geographic region.", "Country name, ISO code, or source-provided region.", "Use NA when absent."),
    "year": ("Isolation, collection, sequencing, or publication year.", "Four-digit year when available.", "Use NA when absent or ambiguous."),
    "phage_lifestyle": ("Phage lifestyle metadata or prediction.", "virulent, temperate, ambiguous, or NA.", "Use NA when not curated; do not infer without evidence."),
    "genome_length": ("Genome length in base pairs.", "Integer base-pair length.", "Use NA when not available; sequence QC will compute when local sequence exists."),
    "gc_percent": ("Genome GC percentage.", "Numeric percent, e.g. 52.4.", "Use NA when not available; sequence QC will compute when local sequence exists."),
    "K_type": ("Capsule K type or K-locus call for the host background.", "K number, KL locus, or source/Kaptive call.", "Use NA when absent; preserve uncertainty in notes."),
    "O_type": ("O antigen or O-locus call for the host background.", "O type, OL locus, or source/Kaptive call.", "Use NA when absent; preserve uncertainty in notes."),
    "ST": ("Multilocus sequence type for host background.", "ST number or source MLST call.", "Use NA when absent."),
    "AMR_markers": ("Antimicrobial resistance markers for host genomes.", "Semicolon-delimited gene/allele markers.", "Use NA when absent or not assessed."),
    "virulence_markers": ("Virulence loci or markers for host genomes.", "Semicolon-delimited markers such as ybt, iuc, iro, rmpA/rmpA2.", "Use NA when absent or not assessed."),
    "raw_sequence_path": ("Local FASTA/GenBank path for the genome/contig/prophage sequence.", "Relative or absolute filesystem path.", "Leave blank only when raw_sequence_path is not configured as an identity column; do not point to unreviewed raw downloads."),
    "notes": ("Free-text provenance, DOI/PMID, snapshot date, coordinates, uncertainty, and curation decisions.", "Free text; semicolon-separated details are acceptable.", "Use NA only when no additional notes exist."),
}

RECOMMENDED_BY_LAYER = {
    "cultured_phages": {"accession", "genome_id", "host_species", "country", "year", "genome_length", "gc_percent", "notes"},
    "literature_curated_phages": {"accession", "genome_id", "host_species", "host_strain", "country", "year", "phage_lifestyle", "notes"},
    "prophages": {"genome_id", "accession", "host_species", "host_strain", "K_type", "O_type", "ST", "raw_sequence_path", "notes"},
    "metagenomic_discovery": {"genome_id", "source", "isolation_host", "country", "year", "genome_length", "gc_percent", "raw_sequence_path", "notes"},
    "host_genomes": {"genome_id", "accession", "host_species", "host_strain", "country", "year", "K_type", "O_type", "ST", "AMR_markers", "virulence_markers", "raw_sequence_path", "notes"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a dictionary for reviewed source-export template columns.")
    parser.add_argument("--template-manifest", required=True, help="Source export template manifest TSV.")
    parser.add_argument("--dictionary-output", required=True, help="Output source export column dictionary TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def split_list(value: str) -> list[str]:
    if is_missing(value):
        return []
    return [item.strip() for item in value.replace(",", ";").split(";") if item.strip()]


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def definition(column: str) -> tuple[str, str, str]:
    return COLUMN_DEFINITIONS.get(column, ("Source-specific metadata column.", "Free text unless documented by the source.", "Use NA when absent."))


def column_role(column: str, identity: set[str]) -> str:
    if column in identity:
        return "identity"
    if column in {"K_type", "O_type", "ST", "AMR_markers", "virulence_markers"}:
        return "host_feature"
    if column in {"genome_length", "gc_percent", "raw_sequence_path"}:
        return "sequence_or_qc"
    if column in {"source", "notes", "country", "year"}:
        return "provenance"
    return "metadata"


def validation_notes(column: str, identity: set[str], layer: str) -> str:
    notes = []
    if column in identity:
        notes.append("must be populated enough to identify/import rows")
    if column == "raw_sequence_path":
        notes.append("path is checked later by sequence acquisition/QC stages")
    if column in {"genome_length", "year"}:
        notes.append("should be numeric when present")
    if column == "gc_percent":
        notes.append("should be numeric percent when present")
    if column in {"K_type", "O_type", "ST"}:
        notes.append("used for host association/modeling when populated")
    if layer == "metagenomic_discovery":
        notes.append("discovery-layer rows remain separate from primary atlas unless explicitly merged")
    return "; ".join(notes) if notes else "checked for presence only when configured as expected/identity column"


def build_dictionary(template_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = []
    for template in template_rows:
        headers = split_list(template.get("header_columns", ""))
        identity = set(split_list(template.get("identity_columns_required", "")))
        layer = template.get("record_layer", "")
        recommended = RECOMMENDED_BY_LAYER.get(layer, set())
        for column in headers:
            desc, fmt, missing_policy = definition(column)
            rows.append(
                {
                    "source_id": template.get("source_id", ""),
                    "query_id": template.get("query_id", ""),
                    "record_layer": layer,
                    "target_database": template.get("target_database", ""),
                    "template_path": template.get("template_path", ""),
                    "expected_export_path": template.get("expected_export_path", ""),
                    "column_name": column,
                    "column_role": column_role(column, identity),
                    "required_for_identity": str(column in identity).lower(),
                    "recommended_for_layer": str(column in recommended).lower(),
                    "description": desc,
                    "expected_format": fmt,
                    "missing_value_policy": missing_policy,
                    "validation_notes": validation_notes(column, identity, layer),
                }
            )
    return rows


def main() -> int:
    args = parse_args()
    fieldnames, template_rows = read_tsv(Path(args.template_manifest))
    required = {"source_id", "query_id", "record_layer", "target_database", "template_path", "expected_export_path", "header_columns", "identity_columns_required"}
    missing = sorted(required - set(fieldnames))
    report = []
    if missing:
        write_tsv(Path(args.dictionary_output), DICTIONARY_COLUMNS, [])
        write_tsv(Path(args.report_output), REPORT_COLUMNS, [{"severity": "error", "item": "source_export_dictionary", "message": "missing template manifest columns: " + ";".join(missing)}])
        print("Source export dictionary failed: missing template manifest columns.")
        return 1
    rows = build_dictionary(template_rows)
    column_counts = Counter(row["column_name"] for row in rows)
    identity_rows = sum(1 for row in rows if row["required_for_identity"] == "true")
    report.append({"severity": "info", "item": "source_export_dictionary", "message": f"sources={len(template_rows)}; dictionary_rows={len(rows)}; unique_columns={len(column_counts)}; identity_rows={identity_rows}"})
    write_tsv(Path(args.dictionary_output), DICTIONARY_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Wrote {len(rows)} source export dictionary rows for {len(template_rows)} source templates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
