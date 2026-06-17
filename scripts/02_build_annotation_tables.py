#!/usr/bin/env python3
"""Normalize phage gene annotations and build a simple pangenome matrix."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable


INPUT_COLUMNS = [
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

ANNOTATION_COLUMNS = [
    "genome_id",
    "record_type",
    "species_cluster_id",
    "representative_id",
    "gene_id",
    "annotation_gene_id",
    "contig_id",
    "start",
    "end",
    "strand",
    "protein_id",
    "product",
    "phrog_id",
    "phrog_category",
    "functional_category",
    "module_hint",
    "evidence",
    "tool",
    "protein_length_aa",
    "gene_cluster_id",
    "gene_cluster_key",
    "gene_cluster_source",
    "notes",
]

GENE_CLUSTER_COLUMNS = [
    "gene_cluster_id",
    "gene_cluster_key",
    "gene_cluster_source",
    "gene_count",
    "genome_count",
    "species_cluster_count",
    "member_gene_ids",
    "member_genome_ids",
    "member_species_cluster_ids",
    "representative_product",
    "phrog_id",
    "phrog_category",
    "functional_category",
    "module_hint",
    "notes",
]

PANGENOME_BASE_COLUMNS = [
    "gene_cluster_id",
    "gene_cluster_key",
    "gene_cluster_source",
    "genome_count",
    "gene_count",
]

REPORT_COLUMNS = ["severity", "item", "message"]

MODULE_PATTERNS = [
    ("rbp_depolymerase", re.compile(r"depolymerase|tail ?spike|tail ?fiber|receptor[- ]?binding|capsule|polysaccharide", re.I)),
    ("tail_structural", re.compile(r"tail|baseplate|tape measure|sheath", re.I)),
    ("head_structural", re.compile(r"capsid|portal|head|terminase|prohead", re.I)),
    ("lysis", re.compile(r"lysin|endolysin|holin|spanin|amidase|peptidoglycan", re.I)),
    ("replication", re.compile(r"polymerase|helicase|primase|replication|ssb|sliding clamp", re.I)),
    ("lysogeny", re.compile(r"integrase|excisionase|repressor|partition|lysogen", re.I)),
    ("defense_counterdefense", re.compile(r"anti[- ]?crispr|methyltransferase|restriction|nuclease inhibitor|dnd|mom|dam|modification", re.I)),
    ("hypothetical", re.compile(r"hypothetical|unknown|uncharacteri[sz]ed", re.I)),
]


class StageError(Exception):
    """Raised when required inputs are invalid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build normalized phage annotation, gene-cluster, and pangenome "
            "tables from optional Pharokka/PHROGs-style annotation input."
        )
    )
    parser.add_argument("--manifest", required=True, help="Stage 1 manifest TSV.")
    parser.add_argument("--clusters", required=True, help="Stage 2 phage cluster TSV.")
    parser.add_argument(
        "--annotation-input",
        default="",
        help="Optional gene annotation TSV. If absent, empty schema-valid outputs are written.",
    )
    parser.add_argument("--annotations-output", required=True, help="Normalized gene annotation TSV.")
    parser.add_argument("--gene-clusters-output", required=True, help="Gene-cluster summary TSV.")
    parser.add_argument("--pangenome-output", required=True, help="Wide gene-cluster by genome matrix TSV.")
    parser.add_argument("--report-output", required=True, help="Annotation/pangenome validation report TSV.")
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


def safe_slug(value: str, fallback: str) -> str:
    if is_missing(value):
        value = fallback
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:80] or fallback


def parse_int(value: str) -> int | None:
    if is_missing(value):
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def infer_module_hint(product: str, phrog_category: str, functional_category: str) -> str:
    text = " ".join([product, phrog_category, functional_category])
    for label, pattern in MODULE_PATTERNS:
        if pattern.search(text):
            return label
    return "other"


def protein_length(row: dict[str, str]) -> str:
    explicit = row.get("protein_length_aa", "")
    parsed = parse_int(explicit)
    if parsed is not None and parsed >= 0:
        return str(parsed)
    sequence = row.get("protein_sequence", "")
    if not is_missing(sequence):
        sequence = re.sub(r"\s+", "", sequence)
        return str(len(sequence))
    return ""


def make_gene_cluster_key(row: dict[str, str]) -> tuple[str, str]:
    phrog_id = row.get("phrog_id", "")
    product = row.get("product", "")
    protein_sequence = row.get("protein_sequence", "")

    if not is_missing(phrog_id):
        return f"phrog:{phrog_id}", "phrog_id"
    if not is_missing(product) and not re.search(r"hypothetical|unknown|uncharacteri[sz]ed", product, re.I):
        return f"product:{safe_slug(product, 'product')}", "product"
    if not is_missing(protein_sequence):
        digest = hashlib.sha256(re.sub(r"\s+", "", protein_sequence).encode("utf-8")).hexdigest()[:16]
        return f"protein_sha256:{digest}", "protein_sequence_hash"
    return f"singleton:{row['annotation_gene_id']}", "singleton_missing_annotation"


def load_manifest(path: Path) -> dict[str, dict[str, str]]:
    _, rows = read_tsv(path)
    return {row.get("genome_id", ""): row for row in rows if not is_missing(row.get("genome_id"))}


def load_clusters(path: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    _, rows = read_tsv(path)
    clusters_by_genome = {
        row.get("genome_id", ""): row for row in rows if not is_missing(row.get("genome_id"))
    }
    genome_order = sorted(clusters_by_genome)
    return clusters_by_genome, genome_order


def load_annotation_input(
    annotation_input: str,
    report: list[dict[str, str]],
) -> tuple[list[str], list[dict[str, str]]]:
    if is_missing(annotation_input):
        add_report(
            report,
            "info",
            "annotation_input",
            "No annotation input supplied; empty schema-valid annotation and pangenome outputs were emitted.",
        )
        return [], []

    path = Path(annotation_input)
    if not path.exists():
        add_report(
            report,
            "warning",
            "annotation_input",
            f"Annotation input does not exist: {path}; empty schema-valid outputs were emitted.",
        )
        return [], []

    fieldnames, rows = read_tsv(path)
    missing = [column for column in ["genome_id", "gene_id", "product"] if column not in fieldnames]
    if missing:
        add_report(
            report,
            "error",
            "annotation_input",
            "Annotation input missing required columns: " + ", ".join(missing),
        )
        raise StageError("Invalid annotation input schema")
    add_report(report, "info", "annotation_input", f"Loaded {len(rows)} annotation rows from {path}.")
    return fieldnames, rows


def normalize_annotations(
    raw_rows: list[dict[str, str]],
    manifest_by_genome: dict[str, dict[str, str]],
    clusters_by_genome: dict[str, dict[str, str]],
    report: list[dict[str, str]],
) -> list[dict[str, str]]:
    annotations: list[dict[str, str]] = []
    seen_annotation_gene_ids: set[str] = set()
    skipped_unknown = 0
    duplicate_gene_ids = 0

    for index, row in enumerate(raw_rows, start=2):
        genome_id = row.get("genome_id", "")
        gene_id = row.get("gene_id", "")
        if is_missing(genome_id) or is_missing(gene_id):
            add_report(report, "warning", f"annotation_row_{index}", "Skipped row with missing genome_id or gene_id.")
            continue
        if genome_id not in clusters_by_genome:
            skipped_unknown += 1
            continue

        annotation_gene_id = f"{genome_id}|{gene_id}"
        if annotation_gene_id in seen_annotation_gene_ids:
            duplicate_gene_ids += 1
            annotation_gene_id = f"{annotation_gene_id}|duplicate_{index}"
        seen_annotation_gene_ids.add(annotation_gene_id)

        cluster_row = clusters_by_genome[genome_id]
        manifest_row = manifest_by_genome.get(genome_id, {})
        product = row.get("product", "") or "hypothetical protein"
        phrog_category = row.get("phrog_category", "")
        functional_category = row.get("functional_category", "")
        module_hint = row.get("module_hint", "") or infer_module_hint(product, phrog_category, functional_category)

        prepared = dict(row)
        prepared["annotation_gene_id"] = annotation_gene_id
        gene_cluster_key, gene_cluster_source = make_gene_cluster_key(prepared)

        annotations.append(
            {
                "genome_id": genome_id,
                "record_type": manifest_row.get("record_type", cluster_row.get("record_type", "")),
                "species_cluster_id": cluster_row.get("cluster_id", ""),
                "representative_id": cluster_row.get("representative_id", ""),
                "gene_id": gene_id,
                "annotation_gene_id": annotation_gene_id,
                "contig_id": row.get("contig_id", ""),
                "start": row.get("start", ""),
                "end": row.get("end", ""),
                "strand": row.get("strand", ""),
                "protein_id": row.get("protein_id", ""),
                "product": product,
                "phrog_id": row.get("phrog_id", ""),
                "phrog_category": phrog_category,
                "functional_category": functional_category,
                "module_hint": module_hint,
                "evidence": row.get("evidence", ""),
                "tool": row.get("tool", ""),
                "protein_length_aa": protein_length(row),
                "gene_cluster_id": "",
                "gene_cluster_key": gene_cluster_key,
                "gene_cluster_source": gene_cluster_source,
                "notes": "OK",
            }
        )

    if skipped_unknown:
        add_report(
            report,
            "warning",
            "annotation_input",
            f"Skipped {skipped_unknown} annotation rows whose genome_id was not present in Stage 2 clusters.",
        )
    if duplicate_gene_ids:
        add_report(
            report,
            "warning",
            "annotation_input",
            f"Resolved {duplicate_gene_ids} duplicate genome_id/gene_id combinations by appending row numbers.",
        )
    return annotations


def build_gene_clusters(
    annotations: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in annotations:
        grouped[row["gene_cluster_key"]].append(row)

    cluster_rows: list[dict[str, str]] = []
    key_to_id: dict[str, str] = {}

    for index, key in enumerate(sorted(grouped), start=1):
        gene_cluster_id = f"gene_cluster_{index:06d}"
        key_to_id[key] = gene_cluster_id
        members = sorted(grouped[key], key=lambda row: row["annotation_gene_id"])
        genomes = sorted({row["genome_id"] for row in members})
        species_clusters = sorted({row["species_cluster_id"] for row in members if not is_missing(row["species_cluster_id"])})
        products = [row["product"] for row in members if not is_missing(row["product"])]
        representative_product = products[0] if products else "hypothetical protein"
        first = members[0]
        cluster_rows.append(
            {
                "gene_cluster_id": gene_cluster_id,
                "gene_cluster_key": key,
                "gene_cluster_source": first.get("gene_cluster_source", ""),
                "gene_count": str(len(members)),
                "genome_count": str(len(genomes)),
                "species_cluster_count": str(len(species_clusters)),
                "member_gene_ids": ";".join(row["annotation_gene_id"] for row in members),
                "member_genome_ids": ";".join(genomes),
                "member_species_cluster_ids": ";".join(species_clusters),
                "representative_product": representative_product,
                "phrog_id": first.get("phrog_id", ""),
                "phrog_category": first.get("phrog_category", ""),
                "functional_category": first.get("functional_category", ""),
                "module_hint": first.get("module_hint", ""),
                "notes": "OK",
            }
        )

    for row in annotations:
        row["gene_cluster_id"] = key_to_id[row["gene_cluster_key"]]
    return annotations, cluster_rows


def build_pangenome_matrix(
    annotations: list[dict[str, str]],
    gene_clusters: list[dict[str, str]],
    genome_order: list[str],
) -> tuple[list[str], list[dict[str, str]]]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in annotations:
        counts[(row["gene_cluster_id"], row["genome_id"])] += 1

    matrix_rows: list[dict[str, str]] = []
    for cluster in gene_clusters:
        row = {
            "gene_cluster_id": cluster["gene_cluster_id"],
            "gene_cluster_key": cluster["gene_cluster_key"],
            "gene_cluster_source": cluster["gene_cluster_source"],
            "genome_count": cluster["genome_count"],
            "gene_count": cluster["gene_count"],
        }
        for genome_id in genome_order:
            row[genome_id] = str(counts.get((cluster["gene_cluster_id"], genome_id), 0))
        matrix_rows.append(row)
    return PANGENOME_BASE_COLUMNS + genome_order, matrix_rows


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []

    try:
        manifest_by_genome = load_manifest(Path(args.manifest))
        clusters_by_genome, genome_order = load_clusters(Path(args.clusters))
        add_report(report, "info", "clusters", f"Loaded {len(genome_order)} eligible clustered genomes.")
        _, raw_annotations = load_annotation_input(args.annotation_input, report)
        annotations = normalize_annotations(raw_annotations, manifest_by_genome, clusters_by_genome, report)
        annotations, gene_clusters = build_gene_clusters(annotations)
        pangenome_columns, pangenome_rows = build_pangenome_matrix(annotations, gene_clusters, genome_order)

        add_report(
            report,
            "info",
            "annotations",
            f"Normalized {len(annotations)} gene annotations into {len(gene_clusters)} gene clusters.",
        )

        write_tsv(Path(args.annotations_output), ANNOTATION_COLUMNS, annotations)
        write_tsv(Path(args.gene_clusters_output), GENE_CLUSTER_COLUMNS, gene_clusters)
        write_tsv(Path(args.pangenome_output), pangenome_columns, pangenome_rows)
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    except StageError:
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        return 1

    error_count = sum(1 for row in report if row["severity"] == "error")
    print(
        f"Built annotation tables for {len(genome_order)} genomes: "
        f"{len(annotations)} genes, {len(gene_clusters)} gene clusters."
    )
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
