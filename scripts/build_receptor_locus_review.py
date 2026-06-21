#!/usr/bin/env python3
"""Build a compact review table for pilot receptor-binding/depolymerase loci.

This script only joins and ranks existing pilot outputs from established tools.
It does not predict receptor function or capsule specificity.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from urllib.parse import unquote

RECEPTOR_FEATURES = {"depolymerase", "receptor_binding", "tailspike", "tail_fiber", "baseplate"}

COLUMNS = [
    "review_rank",
    "priority_tier",
    "priority_reason",
    "phage_id",
    "spot_positive_fraction",
    "tested_host_count",
    "locus_id",
    "feature_type",
    "evidence_class",
    "pharokka_gene_id",
    "pharokka_product",
    "prodigal_candidate_id",
    "prodigal_gene_id",
    "prodigal_product",
    "phold_cds_id",
    "phold_product",
    "annotation_method",
    "annotation_confidence",
    "evalue",
    "query_coverage",
    "target_coverage",
    "synteny_context",
    "review_action",
    "claim_boundary",
]

SUMMARY_COLUMNS = ["metric", "value", "interpretation"]

SCALE_DECISION_COLUMNS = ["decision_item", "status", "evidence", "decision", "claim_boundary"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a receptor-locus review table from pilot evidence outputs.")
    parser.add_argument("--pharokka-comparison", default="results/pilot/pharokka_rbp_evidence_comparison.tsv")
    parser.add_argument("--overlap", default="results/pilot/pharokka_prodigal_rbp_overlap.tsv")
    parser.add_argument("--phold-hits", default="results/pilot/phold_relevant_hits.tsv")
    parser.add_argument("--pharokka-output-dir", default="results/pilot/pharokka_output")
    parser.add_argument("--output", default="results/pilot/receptor_locus_review.tsv")
    parser.add_argument("--summary-output", default="results/pilot/receptor_locus_review_summary.tsv")
    parser.add_argument("--scale-decision-output", default="results/pilot/receptor_locus_scale_decision.tsv")
    parser.add_argument("--report-output", default="PILOT_REPORT.md")
    return parser.parse_args()


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{k: "" if v is None else v for k, v in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def parse_gff_attrs(attrs: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in attrs.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            parsed[key] = unquote(value)
    return parsed


def load_pharokka_context(output_dir: Path, phage_id: str) -> dict[str, str]:
    gff = output_dir / phage_id / f"{phage_id}.gff"
    if not gff.exists():
        return {}
    cds_rows: list[tuple[str, str]] = []
    with gff.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 9 or parts[2] != "CDS":
                continue
            attrs = parse_gff_attrs(parts[8])
            gene_id = attrs.get("ID") or attrs.get("locus_tag") or ""
            product = attrs.get("product") or attrs.get("Name") or ""
            if gene_id:
                cds_rows.append((gene_id, product))
    contexts: dict[str, str] = {}
    for idx, (gene_id, _product) in enumerate(cds_rows):
        start = max(0, idx - 2)
        end = min(len(cds_rows), idx + 3)
        parts = []
        for j in range(start, end):
            marker = "*" if j == idx else ""
            parts.append(f"{marker}{cds_rows[j][0]}:{cds_rows[j][1]}{marker}")
        contexts[gene_id] = " | ".join(parts)
    return contexts


def add_report(path: Path, summary: list[dict[str, str]], decisions: list[dict[str, str]]) -> None:
    values = {row["metric"]: row["value"] for row in summary}
    scale_status = next(
        (row["status"] for row in decisions if row["decision_item"] == "scale_established_annotation_to_105_assay_phages"),
        "defer",
    )
    section = f"""

## Receptor Locus Review Set

A compact review table was built from the 30-phage pilot outputs: `results/pilot/receptor_locus_review.tsv`. It contains {values.get('total_review_rows', '0')} priority rows: {values.get('non_pharokka_foldseek_receptor_like_rows', '0')} non-Pharokka Foldseek receptor-like rows and {values.get('concordant_pharokka_rbpbase_receptor_like_rows', '0')} concordant Pharokka/RBPbase receptor-like coordinate overlaps. These rows are manual-review targets, not validated receptor-specificity calls.

Scale decision: `{scale_status}` in `results/pilot/receptor_locus_scale_decision.tsv`. The current evidence supports scaling the same established Pharokka plus Phold/Foldseek commands to all 105 assay phages as an annotation-production step, but not using the 30-phage pilot as complete model evidence.
"""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    marker = "\n## Receptor Locus Review Set\n"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + section
    else:
        text = text.rstrip() + section
    path.write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")


def main() -> int:
    args = parse_args()
    comparison = read_tsv(Path(args.pharokka_comparison))
    overlap = read_tsv(Path(args.overlap))
    phold_hits = read_tsv(Path(args.phold_hits))
    phage_meta = {row["phage_id"]: row for row in comparison}
    context_cache: dict[str, dict[str, str]] = {}

    def synteny_context(phage_id: str, gene_id: str) -> str:
        if not gene_id:
            return ""
        if phage_id not in context_cache:
            context_cache[phage_id] = load_pharokka_context(Path(args.pharokka_output_dir), phage_id)
        return context_cache[phage_id].get(gene_id, "")

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for hit in phold_hits:
        method = hit.get("annotation_method", "").lower()
        feature = hit.get("feature_type", "")
        if method == "pharokka" or feature not in RECEPTOR_FEATURES:
            continue
        key = (hit.get("phage_id", ""), hit.get("cds_id", ""), feature)
        if key in seen:
            continue
        seen.add(key)
        meta = phage_meta.get(hit.get("phage_id", ""), {})
        rows.append(
            {
                "priority_tier": "1",
                "priority_reason": "non_pharokka_foldseek_receptor_like",
                "phage_id": hit.get("phage_id", ""),
                "spot_positive_fraction": meta.get("spot_positive_fraction", ""),
                "tested_host_count": meta.get("tested_host_count", ""),
                "locus_id": hit.get("cds_id", ""),
                "feature_type": feature,
                "evidence_class": "Phold/Foldseek structural annotation of Pharokka hypothetical protein",
                "phold_cds_id": hit.get("cds_id", ""),
                "phold_product": hit.get("product", ""),
                "annotation_method": hit.get("annotation_method", ""),
                "annotation_confidence": hit.get("annotation_confidence", ""),
                "evalue": hit.get("evalue", ""),
                "query_coverage": hit.get("query_coverage", ""),
                "target_coverage": hit.get("target_coverage", ""),
                "synteny_context": synteny_context(hit.get("phage_id", ""), hit.get("cds_id", "")),
                "review_action": "Manually inspect product, coverage, e-value, neighboring tail genes, and whether the hit overlaps any RBPbase candidate.",
                "claim_boundary": "Candidate receptor-like structural annotation only; not capsule specificity or functional validation.",
            }
        )

    for item in overlap:
        if item.get("relationship") != "coordinate_overlap_receptor_like":
            continue
        phage_id = item.get("phage_id", "")
        meta = phage_meta.get(phage_id, {})
        key = (phage_id, item.get("pharokka_gene_id", ""), item.get("prodigal_candidate_id", ""))
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "priority_tier": "2",
                "priority_reason": "concordant_pharokka_rbpbase_receptor_like_overlap",
                "phage_id": phage_id,
                "spot_positive_fraction": meta.get("spot_positive_fraction", ""),
                "tested_host_count": meta.get("tested_host_count", ""),
                "locus_id": item.get("pharokka_gene_id", "") or item.get("prodigal_gene_id", ""),
                "feature_type": item.get("pharokka_feature_types", ""),
                "evidence_class": "Coordinate concordance between Pharokka receptor-like product and RBPbase candidate",
                "pharokka_gene_id": item.get("pharokka_gene_id", ""),
                "pharokka_product": item.get("pharokka_product", ""),
                "prodigal_candidate_id": item.get("prodigal_candidate_id", ""),
                "prodigal_gene_id": item.get("prodigal_gene_id", ""),
                "prodigal_product": item.get("prodigal_product", ""),
                "synteny_context": synteny_context(phage_id, item.get("pharokka_gene_id", "")),
                "review_action": "Manually inspect locus boundaries and domain/structural evidence before using as production RBP evidence.",
                "claim_boundary": "Concordant candidate only; not host-range or capsule-binding validation.",
            }
        )

    rows.sort(
        key=lambda row: (
            int(row.get("priority_tier") or 99),
            row.get("phage_id", ""),
            row.get("locus_id", ""),
            row.get("feature_type", ""),
        )
    )
    for idx, row in enumerate(rows, start=1):
        row["review_rank"] = str(idx)

    scale_status = "proceed_operationally" if len(rows) >= 20 and sum(1 for row in rows if row["priority_reason"] == "non_pharokka_foldseek_receptor_like") >= 1 else "defer"
    scale_evidence = (
        f"30-phage pilot completed; {len(rows)} priority review rows; "
        f"{sum(1 for row in rows if row['priority_reason'] == 'non_pharokka_foldseek_receptor_like')} non-Pharokka Foldseek receptor-like rows; "
        f"{sum(1 for row in rows if row['priority_reason'] == 'concordant_pharokka_rbpbase_receptor_like_overlap')} concordant Pharokka/RBPbase overlaps"
    )
    decisions = [
        {
            "decision_item": "scale_established_annotation_to_105_assay_phages",
            "status": scale_status,
            "evidence": scale_evidence,
            "decision": "Run the same established Pharokka and Phold/Foldseek commands on the full 105 assay-phage set, preserving exact commands and versions.",
            "claim_boundary": "Scale-up creates production annotation evidence; it does not validate receptor specificity or host-range prediction by itself.",
        },
        {
            "decision_item": "use_pilot_review_rows_for_modeling",
            "status": "blocked",
            "evidence": "Review rows cover 30 selected phages only and include candidate annotations rather than accepted full-set features.",
            "decision": "Do not use pilot review rows as model features. Wait for full 105-phage production evidence and feature-coverage audit.",
            "claim_boundary": "No RBP-versus-taxonomy or host-range model claim from pilot review rows.",
        },
    ]

    summary = [
        {
            "metric": "total_review_rows",
            "value": str(len(rows)),
            "interpretation": "Locus-level rows requiring manual review before full-set scaling or production evidence import.",
        },
        {
            "metric": "non_pharokka_foldseek_receptor_like_rows",
            "value": str(sum(1 for row in rows if row["priority_reason"] == "non_pharokka_foldseek_receptor_like")),
            "interpretation": "Potential remote structural receptor-like calls not simply carried forward from Pharokka annotations.",
        },
        {
            "metric": "concordant_pharokka_rbpbase_receptor_like_rows",
            "value": str(sum(1 for row in rows if row["priority_reason"] == "concordant_pharokka_rbpbase_receptor_like_overlap")),
            "interpretation": "RBPbase candidates whose coordinates overlap a Pharokka receptor-like product annotation.",
        },
        {
            "metric": "unique_phages_in_review_set",
            "value": str(len({row["phage_id"] for row in rows})),
            "interpretation": "Selected pilot phages represented in priority review rows.",
        },
    ]

    write_tsv(Path(args.output), COLUMNS, rows)
    write_tsv(Path(args.summary_output), SUMMARY_COLUMNS, summary)
    write_tsv(Path(args.scale_decision_output), SCALE_DECISION_COLUMNS, decisions)
    add_report(Path(args.report_output), summary, decisions)
    print(f"Receptor locus review rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
