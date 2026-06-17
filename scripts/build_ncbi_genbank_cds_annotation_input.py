#!/usr/bin/env python3
"""Build Stage 3 annotation input from NCBI GenBank CDS records."""

from __future__ import annotations

import argparse
import csv
import re
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import urlopen


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
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch GenBank flatfiles for accession-backed manifest rows and write "
            "Stage 3 annotation input. This script writes annotation evidence only; "
            "it does not write FASTA files and does not modify data/raw."
        )
    )
    parser.add_argument("--manifest", required=True, help="Source manifest TSV with genome_id and accession columns.")
    parser.add_argument("--base-input", default="", help="Optional existing annotation TSV to prepend.")
    parser.add_argument("--output", required=True, help="Output combined annotation TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--retmax", type=int, default=0, help="Optional maximum manifest rows to process; 0 means all.")
    parser.add_argument("--sleep-seconds", type=float, default=0.34, help="Delay between NCBI EFetch calls.")
    parser.add_argument("--email", default="", help="Optional email parameter for NCBI E-utilities.")
    parser.add_argument("--api-key", default="", help="Optional NCBI API key.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return reader.fieldnames or [], [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
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


def fetch_genbank(accession: str, args: argparse.Namespace) -> str:
    params = {
        "db": "nuccore",
        "id": accession,
        "rettype": "gbwithparts",
        "retmode": "text",
    }
    if args.email:
        params["email"] = args.email
    if args.api_key:
        params["api_key"] = args.api_key
    url = f"{EUTILS}/efetch.fcgi?{urlencode(params)}"
    with urlopen(url, timeout=90) as response:
        text = response.read().decode("utf-8")
    if args.sleep_seconds > 0:
        time.sleep(args.sleep_seconds)
    return text


def contig_id(text: str, fallback: str) -> str:
    match = re.search(r"^VERSION\s+(\S+)", text, flags=re.M)
    if match:
        return match.group(1)
    match = re.search(r"^ACCESSION\s+(\S+)", text, flags=re.M)
    return match.group(1) if match else fallback


def cds_blocks(text: str) -> list[list[str]]:
    lines = text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []
    in_features = False
    for line in lines:
        if line.startswith("FEATURES"):
            in_features = True
            continue
        if in_features and line.startswith("ORIGIN"):
            break
        if not in_features:
            continue
        if line.startswith("     ") and len(line) > 20 and line[5:21].strip():
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append(current)
    return [block for block in blocks if block[0][5:21].strip() == "CDS"]


def location_from(block: list[str]) -> str:
    parts = [block[0][21:].strip()]
    for line in block[1:]:
        text = line[21:].strip() if len(line) > 21 else line.strip()
        if text.startswith("/"):
            break
        if text:
            parts.append(text)
    return "".join(parts)


def qualifier_from(block: list[str], key: str) -> str:
    pattern = f"/{key}="
    collecting = False
    pieces: list[str] = []
    for line in block[1:]:
        text = line[21:].rstrip() if len(line) > 21 else line.strip()
        stripped = text.strip()
        if stripped.startswith("/") and not stripped.startswith(pattern):
            if collecting:
                break
        if stripped.startswith(pattern):
            collecting = True
            pieces.append(stripped[len(pattern):])
            continue
        if collecting:
            pieces.append(stripped)
    if not pieces:
        return ""
    value = "".join(pieces).strip()
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    return re.sub(r"\s+", "", value) if key == "translation" else re.sub(r"\s+", " ", value).strip()


def coordinates(location: str) -> tuple[str, str, str]:
    numbers = [int(value) for value in re.findall(r"\d+", location)]
    if not numbers:
        return "", "", ""
    strand = "-" if "complement" in location else "+"
    return str(min(numbers)), str(max(numbers)), strand


def parse_genbank(genome_id: str, accession: str, text: str) -> list[dict[str, str]]:
    parsed: list[dict[str, str]] = []
    cid = contig_id(text, accession)
    for index, block in enumerate(cds_blocks(text), start=1):
        location = location_from(block)
        start, end, strand = coordinates(location)
        product = qualifier_from(block, "product") or "hypothetical protein"
        translation = qualifier_from(block, "translation")
        locus = qualifier_from(block, "locus_tag") or qualifier_from(block, "gene") or qualifier_from(block, "protein_id") or f"{accession}_cds_{index:05d}"
        parsed.append(
            {
                "genome_id": genome_id,
                "gene_id": locus,
                "contig_id": cid,
                "start": start,
                "end": end,
                "strand": strand,
                "product": product,
                "protein_id": qualifier_from(block, "protein_id"),
                "protein_sequence": translation,
                "protein_length_aa": str(len(translation)) if translation else "",
                "phrog_id": "",
                "phrog_category": "",
                "functional_category": category_for(product),
                "evidence": f"NCBI GenBank CDS product fetched by accession {accession}; no raw FASTA written",
                "tool": "build_ncbi_genbank_cds_annotation_input.py",
            }
        )
    return parsed




def row_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("genome_id", ""),
        row.get("gene_id", ""),
        row.get("protein_id", ""),
        row.get("contig_id", ""),
    )


def deduplicate_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    seen: set[tuple[str, str, str, str]] = set()
    output: list[dict[str, str]] = []
    duplicates = 0
    for row in rows:
        key = row_key(row)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        output.append(row)
    return output, duplicates


def manifest_records(path: Path, retmax: int) -> list[dict[str, str]]:
    fieldnames, rows = read_tsv(path)
    missing = [column for column in ["genome_id", "accession"] if column not in fieldnames]
    if missing:
        raise ValueError("Manifest missing columns: " + ";".join(missing))
    records = [row for row in rows if not is_missing(row.get("genome_id")) and not is_missing(row.get("accession"))]
    return records[:retmax] if retmax > 0 else records


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []
    rows: list[dict[str, str]] = []
    if args.base_input:
        _, base_rows = read_tsv(Path(args.base_input))
        rows.extend(base_rows)
        report.append({"severity": "info", "item": "base_input", "message": f"Loaded {len(base_rows)} existing annotation rows from {args.base_input}."})
    try:
        records = manifest_records(Path(args.manifest), args.retmax)
        report.append({"severity": "info", "item": "manifest", "message": f"Loaded {len(records)} accession-backed manifest rows."})
        for record in records:
            accession = record["accession"]
            genome_id = record["genome_id"]
            text = fetch_genbank(accession, args)
            parsed = parse_genbank(genome_id, accession, text)
            rows.extend(parsed)
            severity = "info" if parsed else "warning"
            report.append({"severity": severity, "item": genome_id, "message": f"Fetched {accession} and parsed {len(parsed)} CDS rows."})
    except Exception as exc:  # noqa: BLE001 - report network/parser failures in TSV form
        report.append({"severity": "error", "item": "ncbi_genbank_cds", "message": str(exc)})
    rows, duplicates = deduplicate_rows(rows)
    if duplicates:
        report.append({"severity": "info", "item": "deduplicate_rows", "message": f"Removed {duplicates} duplicate annotation row(s)."})
    write_tsv(Path(args.output), COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    errors = sum(1 for row in report if row["severity"] == "error")
    print(f"NCBI GenBank CDS annotation input complete: {len(rows)} rows, {errors} errors.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
