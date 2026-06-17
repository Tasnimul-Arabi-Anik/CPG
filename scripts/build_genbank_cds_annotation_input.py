#!/usr/bin/env python3
"""Build a Stage 3 annotation-input TSV from local GenBank CDS features."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable

COLUMNS = [
    "genome_id",
    "gene_id",
    "contig_id",
    "start",
    "end",
    "strand",
    "product",
    "protein_id",
    "protein_sequence",
    "protein_length_aa",
    "phrog_id",
    "phrog_category",
    "functional_category",
    "evidence",
    "tool",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse local GenBank CDS features into the Stage 3 annotation-input schema.")
    parser.add_argument(
        "--record",
        action="append",
        required=True,
        help=(
            "Record spec formatted as genome_id=PATH or genome_id=PATH:start-end. "
            "Use coordinate windows for prophage intervals. May be repeated."
        ),
    )
    parser.add_argument("--output", required=True, help="Output annotation-input TSV.")
    parser.add_argument("--report-output", required=True, help="Output parser report TSV.")
    return parser.parse_args()


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="	")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def category_for(product: str) -> str:
    text = product.lower()
    if any(term in text for term in ["depolymerase", "tailspike", "tail spike", "tail fiber", "tail fibre", "receptor-binding", "receptor binding", "capsule", "polysaccharide"]):
        return "rbp_depolymerase"
    if any(term in text for term in ["tail", "baseplate", "capsid", "terminase", "portal"]):
        return "structural"
    if any(term in text for term in ["integrase", "repressor", "excisionase"]):
        return "lysogeny"
    if any(term in text for term in ["lysin", "endolysin", "holin", "spanin", "amidase"]):
        return "lysis"
    if any(term in text for term in ["polymerase", "helicase", "primase", "replication"]):
        return "replication"
    if any(term in text for term in ["methyltransferase", "restriction", "anti-crispr", "nuclease", "endonuclease", "exonuclease"]):
        return "defense_counterdefense"
    if "hypothetical" in text or "unknown" in text or "uncharacterized" in text:
        return "unknown"
    return "other"


def parse_record_spec(spec: str) -> tuple[str, Path, int | None, int | None]:
    if "=" not in spec:
        raise ValueError("record spec must contain genome_id=PATH")
    genome_id, path_part = spec.split("=", 1)
    region_start = region_end = None
    match = re.match(r"(.+):(\d+)-(\d+)$", path_part)
    if match:
        path_text, start_text, end_text = match.groups()
        region_start = int(start_text)
        region_end = int(end_text)
    else:
        path_text = path_part
    if not genome_id.strip():
        raise ValueError("record spec has empty genome_id")
    return genome_id.strip(), Path(path_text), region_start, region_end


def qualifier(feature: object, key: str) -> str:
    values = getattr(feature, "qualifiers", {}).get(key, [])
    return values[0] if values else ""


def feature_span(feature: object) -> tuple[int, int, str]:
    location = getattr(feature, "location")
    start = int(location.start) + 1
    end = int(location.end)
    strand = "+" if location.strand == 1 else "-" if location.strand == -1 else ""
    return start, end, strand


def parse_genbank_record(genome_id: str, path: Path, region_start: int | None, region_end: int | None) -> list[dict[str, str]]:
    try:
        from Bio import SeqIO  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Biopython is required to parse GenBank files. Install the project environment from environment.yml.") from exc
    rows: list[dict[str, str]] = []
    for record in SeqIO.parse(str(path), "genbank"):
        counter = 0
        for feature in record.features:
            if feature.type != "CDS":
                continue
            start, end, strand = feature_span(feature)
            if region_start is not None and region_end is not None and (end < region_start or start > region_end):
                continue
            counter += 1
            product = qualifier(feature, "product") or "hypothetical protein"
            translation = qualifier(feature, "translation")
            locus = qualifier(feature, "locus_tag") or qualifier(feature, "gene") or qualifier(feature, "protein_id") or f"cds_{counter:05d}"
            rows.append(
                {
                    "genome_id": genome_id,
                    "gene_id": locus,
                    "contig_id": record.id,
                    "start": str(start if region_start is None else max(start, region_start) - region_start + 1),
                    "end": str(end if region_start is None else min(end, region_end) - region_start + 1),
                    "strand": strand,
                    "product": product,
                    "protein_id": qualifier(feature, "protein_id"),
                    "protein_sequence": translation,
                    "protein_length_aa": str(len(translation)) if translation else "",
                    "phrog_id": "",
                    "phrog_category": "",
                    "functional_category": category_for(product),
                    "evidence": "NCBI GenBank CDS product; coordinates parsed from local gbff",
                    "tool": "build_genbank_cds_annotation_input.py",
                    "notes": f"Local GenBank bridge annotation parsed from {path}; genome_id={genome_id}; region={region_start or 'full'}-{region_end or 'full'}; not standardized Pharokka/PHROGs annotation.",
                }
            )
    return rows


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []
    rows: list[dict[str, str]] = []
    for spec in args.record:
        try:
            genome_id, path, region_start, region_end = parse_record_spec(spec)
            if not path.exists():
                raise FileNotFoundError(path)
            parsed = parse_genbank_record(genome_id, path, region_start, region_end)
            rows.extend(parsed)
            report.append({"severity": "info", "item": genome_id, "message": f"Parsed {len(parsed)} CDS rows from {path}."})
        except Exception as exc:  # noqa: BLE001 - report all curation parser errors in TSV form
            report.append({"severity": "error", "item": spec, "message": str(exc)})
    write_tsv(Path(args.output), COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    errors = sum(1 for row in report if row["severity"] == "error")
    print(f"GenBank CDS annotation input complete: {len(rows)} rows, {errors} errors.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
