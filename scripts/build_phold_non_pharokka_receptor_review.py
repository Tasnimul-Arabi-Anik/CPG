#!/usr/bin/env python3
"""Build a review table for Phold-only receptor-like assay-phage CDSs.

This script joins existing Phold/Foldseek output tables. It does not predict
receptor specificity or capsule binding.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter
from pathlib import Path

RECEPTOR_FEATURES = {"depolymerase", "receptor_binding", "tailspike", "tail_fiber", "baseplate"}
SPECIFIC_FEATURES = {"depolymerase", "receptor_binding", "tailspike", "tail_fiber"}

COLUMNS = [
    "review_rank",
    "review_priority",
    "evidence_tier",
    "evidence_tier_reason",
    "phage_id",
    "study_id",
    "panel_id",
    "tested_host_count",
    "spot_positive_host_count",
    "spot_positive_fraction",
    "cds_id",
    "contig_id",
    "start",
    "end",
    "strand",
    "feature_type",
    "function",
    "product",
    "annotation_method",
    "annotation_confidence",
    "evalue",
    "query_coverage",
    "target_coverage",
    "prostt5_confidence",
    "annotation_source",
    "source_file",
    "prediction_context_available",
    "local_prediction_context",
    "coverage_tier",
    "specificity_tier",
    "review_action",
    "claim_boundary",
]

SUMMARY_COLUMNS = ["metric", "value", "interpretation"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phold-hits",
        default="results/production/phold_assay_phage_relevant_hits.tsv",
        help="Full-set Phold relevant-hit table from run_phold_pilot.py.",
    )
    parser.add_argument(
        "--phage-coverage",
        default="results/production/receptor_features/assay_phage_receptor_feature_coverage.tsv",
        help="Assay-phage receptor feature coverage table.",
    )
    parser.add_argument(
        "--output",
        default="results/production/receptor_features/phold_non_pharokka_receptor_review.tsv",
    )
    parser.add_argument(
        "--summary-output",
        default="results/production/receptor_features/phold_non_pharokka_receptor_review_summary.tsv",
    )
    parser.add_argument("--report-output", default="PILOT_REPORT.md")
    parser.add_argument("--context-window", type=int, default=2)
    return parser.parse_args()


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: "" if value is None else value for key, value in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def parse_float(value: str) -> float | None:
    if value in {"", "NA", "na", "None", "none"}:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def coverage_tier(query_coverage: str, target_coverage: str) -> str:
    qcov = parse_float(query_coverage)
    tcov = parse_float(target_coverage)
    if qcov is None or tcov is None:
        return "coverage_not_reported"
    if qcov >= 0.7 and tcov >= 0.7:
        return "high_bidirectional_coverage"
    if qcov >= 0.7 or tcov >= 0.7:
        return "partial_coverage"
    return "low_coverage"


def specificity_tier(feature_type: str, product: str) -> str:
    product_l = product.lower()
    if feature_type in {"depolymerase", "receptor_binding", "tailspike"}:
        return "specific_receptor_like_label"
    if feature_type == "tail_fiber" and "chaperone" not in product_l:
        return "specific_receptor_like_label"
    if feature_type == "tail_fiber":
        return "tail_fiber_related_but_chaperone_like"
    if feature_type == "baseplate":
        return "structural_context_label"
    return "generic_receptor_like_keyword"


def evidence_tier(row: dict[str, str]) -> tuple[str, str, str]:
    confidence = row.get("annotation_confidence", "").lower()
    feature = row.get("feature_type", "")
    cov_tier = coverage_tier(row.get("query_coverage", ""), row.get("target_coverage", ""))
    spec_tier = specificity_tier(feature, row.get("product", ""))
    evalue = parse_float(row.get("evalue", ""))
    strong_evalue = evalue is not None and evalue <= 1e-10

    if confidence == "high" and cov_tier == "high_bidirectional_coverage" and feature in SPECIFIC_FEATURES:
        return (
            "high_priority_candidate",
            "High Phold confidence, high bidirectional coverage, and specific receptor-like label.",
            "1",
        )
    if confidence in {"high", "medium"} and feature in SPECIFIC_FEATURES and (cov_tier != "low_coverage" or strong_evalue):
        return (
            "medium_priority_candidate",
            "Specific receptor-like label with medium/high Phold confidence and at least partial coverage or strong E-value.",
            "2",
        )
    if feature == "baseplate" and confidence in {"high", "medium"} and (cov_tier != "low_coverage" or strong_evalue):
        return (
            "context_candidate",
            "Baseplate structural hit may mark receptor-module context but is not a specific RBP/depolymerase label.",
            "3",
        )
    return (
        "low_priority_candidate",
        "Low confidence, weak coverage, generic label, or context-only evidence; retain for transparency, not claim support.",
        "4",
    )


def load_prediction_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return read_tsv(path)


def build_context(prediction_rows: list[dict[str, str]], cds_id: str, window: int) -> tuple[str, dict[str, str]]:
    if not prediction_rows:
        return "", {}
    index = next((idx for idx, row in enumerate(prediction_rows) if row.get("cds_id") == cds_id), None)
    if index is None:
        return "", {}
    start = max(0, index - window)
    end = min(len(prediction_rows), index + window + 1)
    parts: list[str] = []
    for idx in range(start, end):
        row = prediction_rows[idx]
        marker = "*" if idx == index else ""
        label = ":".join(
            [
                row.get("cds_id", ""),
                row.get("function", ""),
                row.get("product", ""),
                row.get("annotation_method", ""),
                row.get("annotation_confidence", ""),
            ]
        )
        parts.append(f"{marker}{label}{marker}")
    return " | ".join(parts), prediction_rows[index]


def add_report(path: Path, summary: list[dict[str, str]]) -> None:
    values = {row["metric"]: row["value"] for row in summary}
    section = f"""

## Phold Non-Pharokka Receptor Review

A focused full-set review table was built for Phold/Foldseek receptor-like CDSs that were not already annotated by Pharokka: `results/production/receptor_features/phold_non_pharokka_receptor_review.tsv`. It contains {values.get('review_rows', '0')} CDS rows across {values.get('phages_with_review_rows', '0')} assay phages. Feature counts are tail fiber {values.get('tail_fiber_rows', '0')}, tailspike {values.get('tailspike_rows', '0')}, baseplate {values.get('baseplate_rows', '0')}, receptor-binding {values.get('receptor_binding_rows', '0')}, and depolymerase {values.get('depolymerase_rows', '0')}. Confidence counts are high {values.get('high_confidence_rows', '0')}, medium {values.get('medium_confidence_rows', '0')}, and low {values.get('low_confidence_rows', '0')}. High-priority manual-review candidates: {values.get('high_priority_candidate_rows', '0')}.

Claim boundary: these rows are structural remote-homology review targets only. They do not demonstrate capsule specificity, depolymerase activity, productive infection, or receptor-feature superiority over genome-similarity baselines.
"""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    marker = "\n## Phold Non-Pharokka Receptor Review\n"
    if marker in text:
        before, rest = text.split(marker, 1)
        after = ""
        next_marker = rest.find("\n## ")
        if next_marker != -1:
            after = rest[next_marker:]
        text = before.rstrip() + section + after
    else:
        insert_before = "\n## Assay-Phage Receptor Feature Coverage\n"
        if insert_before in text:
            before, after = text.split(insert_before, 1)
            text = before.rstrip() + section + insert_before + after
        else:
            text = text.rstrip() + section
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def build_summary(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    feature_counts = Counter(row["feature_type"] for row in rows)
    confidence_counts = Counter(row["annotation_confidence"].lower() for row in rows)
    tier_counts = Counter(row["evidence_tier"] for row in rows)
    phage_count = len({row["phage_id"] for row in rows})
    return [
        {
            "metric": "review_rows",
            "value": str(len(rows)),
            "interpretation": "Non-Pharokka Phold/Foldseek receptor-like CDS rows retained for manual review.",
        },
        {
            "metric": "phages_with_review_rows",
            "value": str(phage_count),
            "interpretation": "Assay phages containing at least one reviewed non-Pharokka receptor-like Phold hit.",
        },
        *[
            {
                "metric": f"{feature}_rows",
                "value": str(feature_counts.get(feature, 0)),
                "interpretation": f"Rows classified as {feature} by receptor-like keyword filtering.",
            }
            for feature in ["tail_fiber", "tailspike", "baseplate", "receptor_binding", "depolymerase"]
        ],
        *[
            {
                "metric": f"{confidence}_confidence_rows",
                "value": str(confidence_counts.get(confidence, 0)),
                "interpretation": f"Rows with Phold annotation_confidence={confidence}.",
            }
            for confidence in ["high", "medium", "low"]
        ],
        *[
            {
                "metric": f"{tier}_rows",
                "value": str(tier_counts.get(tier, 0)),
                "interpretation": f"Rows assigned evidence_tier={tier}.",
            }
            for tier in [
                "high_priority_candidate",
                "medium_priority_candidate",
                "context_candidate",
                "low_priority_candidate",
            ]
        ],
    ]


def main() -> int:
    args = parse_args()
    phold_hits = read_tsv(Path(args.phold_hits))
    coverage_rows = read_tsv(Path(args.phage_coverage))
    coverage_by_phage = {row["phage_id"]: row for row in coverage_rows}
    context_cache: dict[str, list[dict[str, str]]] = {}

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
        source_file = Path(hit.get("source_file", ""))
        if str(source_file) not in context_cache:
            context_cache[str(source_file)] = load_prediction_rows(source_file)
        local_context, prediction_row = build_context(context_cache[str(source_file)], hit.get("cds_id", ""), args.context_window)
        tier, reason, priority = evidence_tier(hit)
        coverage = coverage_by_phage.get(hit.get("phage_id", ""), {})
        rows.append(
            {
                "review_priority": priority,
                "evidence_tier": tier,
                "evidence_tier_reason": reason,
                "phage_id": hit.get("phage_id", ""),
                "study_id": coverage.get("study_id", ""),
                "panel_id": coverage.get("panel_id", ""),
                "tested_host_count": coverage.get("tested_host_count", ""),
                "spot_positive_host_count": coverage.get("spot_positive_host_count", ""),
                "spot_positive_fraction": coverage.get("spot_positive_fraction", ""),
                "cds_id": hit.get("cds_id", ""),
                "contig_id": prediction_row.get("contig_id", ""),
                "start": prediction_row.get("start", ""),
                "end": prediction_row.get("end", ""),
                "strand": prediction_row.get("strand", ""),
                "feature_type": feature,
                "function": hit.get("function", ""),
                "product": hit.get("product", ""),
                "annotation_method": hit.get("annotation_method", ""),
                "annotation_confidence": hit.get("annotation_confidence", ""),
                "evalue": hit.get("evalue", ""),
                "query_coverage": hit.get("query_coverage", ""),
                "target_coverage": hit.get("target_coverage", ""),
                "prostt5_confidence": hit.get("prostt5_confidence", ""),
                "annotation_source": hit.get("annotation_source", ""),
                "source_file": hit.get("source_file", ""),
                "prediction_context_available": "true" if local_context else "false",
                "local_prediction_context": local_context,
                "coverage_tier": coverage_tier(hit.get("query_coverage", ""), hit.get("target_coverage", "")),
                "specificity_tier": specificity_tier(feature, hit.get("product", "")),
                "review_action": "Manual review: inspect Foldseek confidence, coverage, product specificity, neighboring tail-module context, and overlap with published RBPbase features before accepting as RBP/depolymerase evidence.",
                "claim_boundary": "Computational Phold/Foldseek receptor-like annotation only; not capsule specificity, depolymerase activity, productive infection, or model superiority evidence.",
            }
        )

    rows.sort(
        key=lambda row: (
            int(row["review_priority"]),
            row["phage_id"],
            row["cds_id"],
            row["feature_type"],
        )
    )
    for idx, row in enumerate(rows, start=1):
        row["review_rank"] = str(idx)

    summary = build_summary(rows)
    write_tsv(Path(args.output), COLUMNS, rows)
    write_tsv(Path(args.summary_output), SUMMARY_COLUMNS, summary)
    add_report(Path(args.report_output), summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
