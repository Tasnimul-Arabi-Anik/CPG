#!/usr/bin/env python3
"""Summarize phage-side receptor feature coverage for assay phages.

This joins existing outputs from established tools and reviewed evidence tables.
It does not predict receptor specificity or host range.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

RECEPTOR_TYPES = {"tail_fiber", "tailspike", "receptor_binding", "depolymerase", "baseplate"}
COVERAGE_COLUMNS = [
    "phage_id",
    "study_id",
    "panel_id",
    "tested_host_count",
    "spot_positive_host_count",
    "spot_negative_host_count",
    "spot_positive_fraction",
    "pharokka_status",
    "pharokka_keyword_rows",
    "pharokka_receptor_like_rows",
    "pharokka_tail_fiber_rows",
    "pharokka_tailspike_rows",
    "pharokka_receptor_binding_rows",
    "pharokka_depolymerase_rows",
    "pharokka_baseplate_rows",
    "phold_status",
    "phold_prediction_rows",
    "phold_receptor_like_rows",
    "phold_non_pharokka_receptor_like_rows",
    "phold_tail_fiber_rows",
    "phold_tailspike_rows",
    "phold_receptor_binding_rows",
    "phold_depolymerase_rows",
    "phold_baseplate_rows",
    "rbpbase_candidate_count",
    "rbpbase_high_confidence_count",
    "rbpbase_source_candidate_count",
    "rbpbase_boundary_reviewed_missing_count",
    "rbpbase_boundary_reviewed_high_score_missing_count",
    "rbpbase_boundary_reviewed_candidate_count",
    "phage_side_receptor_feature_state",
    "model_use_state",
    "claim_boundary",
]
SUMMARY_COLUMNS = ["metric", "value", "interpretation"]
READINESS_COLUMNS = ["readiness_item", "status", "evidence", "next_action", "claim_boundary"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize assay-phage receptor feature coverage.")
    parser.add_argument("--host-range", default="results/pilot/host_range_summary.tsv")
    parser.add_argument("--pharokka-run", default="results/production/pharokka_assay_phage_run_summary.tsv")
    parser.add_argument("--pharokka-annotations", default="results/production/pharokka_assay_phage_annotation_summary.tsv")
    parser.add_argument("--phold-run", default="results/production/phold_assay_phage_run_summary.tsv")
    parser.add_argument("--phold-hits", default="results/production/phold_assay_phage_relevant_hits.tsv")
    parser.add_argument("--rbp-candidates", default="results/production/rbp_depolymerase/candidates.tsv")
    parser.add_argument("--rbpbase-support", default="data/metadata/external_evidence/phagehostlearn_rbpbase_receptor_support.tsv")
    parser.add_argument("--missing-rbpbase-review", default="results/production/receptor_features/missing_rbpbase_review/missing_rbpbase_boundary_review.tsv")
    parser.add_argument("--host-defense", default="data/metadata/production_evidence/host_defense_systems.tsv")
    parser.add_argument("--phage-antidefense", default="data/metadata/production_evidence/phage_antidefense_candidates.tsv")
    parser.add_argument("--assays", default="results/production/metadata/phage_host_assays.tsv")
    parser.add_argument("--coverage-output", default="results/production/receptor_features/assay_phage_receptor_feature_coverage.tsv")
    parser.add_argument("--summary-output", default="results/production/receptor_features/assay_phage_receptor_feature_summary.tsv")
    parser.add_argument("--readiness-output", default="results/production/receptor_features/assay_phage_receptor_model_readiness.tsv")
    parser.add_argument("--report-output", default="PILOT_REPORT.md")
    return parser.parse_args()


def read_tsv(path: Path, required: bool = True) -> list[dict[str, str]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{k: "" if v is None else v for k, v in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def to_int(value: str) -> int:
    try:
        return int(float(value or 0))
    except ValueError:
        return 0


def build_report(path: Path, summary: list[dict[str, str]], readiness: list[dict[str, str]], args: argparse.Namespace) -> None:
    values = {row["metric"]: row["value"] for row in summary}
    phage_ready = next((row for row in readiness if row["readiness_item"] == "phage_side_receptor_features"), {})
    model_ready = next((row for row in readiness if row["readiness_item"] == "receptor_layer_model"), {})
    section = f"""\n\n## Assay-Phage Receptor Feature Coverage\n\nPhage-side receptor feature coverage was summarized from full-set RBPbase candidate rows, Pharokka annotations, and Phold/Foldseek structural annotations. Coverage table: `{args.coverage_output}`. Summary table: `{args.summary_output}`. Assay phages covered by Pharokka and Phold: {values.get('phages_with_full_pharokka_and_phold', '0')}/{values.get('assay_phages', '0')}. Phages with any receptor-like evidence across RBPbase, Pharokka, or Phold: {values.get('phages_with_any_receptor_like_evidence', '0')}/{values.get('assay_phages', '0')}. RBPbase exact Prodigal matches: {values.get('total_rbpbase_candidate_rows', '0')}; boundary-reviewed RBPbase candidates: {values.get('total_rbpbase_boundary_reviewed_candidate_rows', '0')}; Phold receptor-like CDS rows: {values.get('total_phold_receptor_like_cds_rows', '0')}; feature-level receptor-like rows: {values.get('total_phold_receptor_like_feature_rows', '0')}; non-Pharokka Phold receptor-like rows: {values.get('total_phold_non_pharokka_receptor_like_rows', '0')}.\n\nReadiness: phage-side receptor features are `{phage_ready.get('status', 'unknown')}`; receptor-layer modeling is `{model_ready.get('status', 'unknown')}`. The downstream pairwise matrix and grouped H1 model comparison should be refreshed after receptor-feature coverage changes.\n\nClaim boundary: this audit measures feature coverage. It does not claim that any feature binds a capsule, degrades capsule, or predicts host range better than taxonomy.\n"""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    marker = "\n## Assay-Phage Receptor Feature Coverage\n"
    if marker in text:
        before, rest = text.split(marker, 1)
        after = ""
        next_marker = rest.find("\n## ")
        if next_marker != -1:
            after = rest[next_marker:]
        text = before.rstrip() + section + after
    else:
        text = text.rstrip() + section
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    host_range = read_tsv(Path(args.host_range))
    pharokka_run = read_tsv(Path(args.pharokka_run))
    pharokka_annotations = read_tsv(Path(args.pharokka_annotations))
    phold_run = read_tsv(Path(args.phold_run))
    phold_hits = read_tsv(Path(args.phold_hits))
    rbp_candidates = read_tsv(Path(args.rbp_candidates), required=False)
    rbpbase_support = read_tsv(Path(args.rbpbase_support), required=False)
    missing_rbpbase_review = read_tsv(Path(args.missing_rbpbase_review), required=False)
    host_defense = read_tsv(Path(args.host_defense), required=False)
    phage_antidefense = read_tsv(Path(args.phage_antidefense), required=False)
    assays = read_tsv(Path(args.assays), required=False)

    host_defense_hosts = {row.get("host_genome_id", "") for row in host_defense if row.get("host_genome_id", "")}
    phage_antidefense_phages = {row.get("phage_genome_id", "") for row in phage_antidefense if row.get("phage_genome_id", "")}
    productive_measured = sum(
        1
        for row in assays
        if row.get("productive_infection_result", "") in {"positive", "negative", "equivocal"}
    )

    pharokka_status = {row["phage_id"]: row.get("status", "") for row in pharokka_run}
    phold_status = {row["phage_id"]: row.get("status", "") for row in phold_run}
    phold_prediction_rows = {row["phage_id"]: row.get("prediction_rows", "0") for row in phold_run}
    phold_non_pharokka = {row["phage_id"]: row.get("non_pharokka_receptor_like_rows", "0") for row in phold_run}

    pharokka_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in pharokka_annotations:
        phage = row.get("phage_id", "")
        feature = row.get("feature_type", "")
        if phage:
            pharokka_counts[phage]["keyword_rows"] += 1
            pharokka_counts[phage][feature] += 1
            if feature in RECEPTOR_TYPES:
                pharokka_counts[phage]["receptor_like"] += 1

    phold_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in phold_hits:
        phage = row.get("phage_id", "")
        feature = row.get("feature_type", "")
        if phage:
            phold_counts[phage][feature] += 1
            if feature in RECEPTOR_TYPES:
                phold_counts[phage]["receptor_like"] += 1

    rbp_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rbp_candidates:
        phage = row.get("genome_id", "")
        if phage:
            rbp_counts[phage]["candidate_count"] += 1
            if row.get("is_high_confidence", "").lower() == "true" or row.get("confidence_label", "").lower() == "high":
                rbp_counts[phage]["high_confidence_count"] += 1

    rbpbase_source_counts: dict[str, int] = defaultdict(int)
    for row in rbpbase_support:
        phage = row.get("phage_genome_id", "")
        if phage:
            rbpbase_source_counts[phage] += to_int(row.get("protein_count", "0"))

    rbpbase_boundary_missing_counts: dict[str, Counter[str]] = defaultdict(Counter)
    boundary_reviewed_statuses = {"near_identical_same_phage_hit", "strong_same_phage_hit"}
    for row in missing_rbpbase_review:
        phage = row.get("phage_id", "")
        if not phage or row.get("same_phage_hit_status", "") not in boundary_reviewed_statuses:
            continue
        rbpbase_boundary_missing_counts[phage]["missing_count"] += 1
        try:
            score = float(row.get("xgb_score", "0") or 0)
        except ValueError:
            score = 0.0
        if score >= 0.9:
            rbpbase_boundary_missing_counts[phage]["high_score_missing_count"] += 1

    rows: list[dict[str, str]] = []
    for assay in sorted(host_range, key=lambda row: row.get("phage_id", "")):
        phage = assay.get("phage_id", "")
        pharokka_ready = pharokka_status.get(phage, "") in {"completed", "skipped_existing"}
        phold_ready = phold_status.get(phage, "") in {"completed", "skipped_existing"}
        rbpbase_boundary_reviewed_count = (
            rbp_counts[phage]["candidate_count"]
            + rbpbase_boundary_missing_counts[phage]["missing_count"]
        )
        receptor_total = (
            pharokka_counts[phage]["receptor_like"]
            + phold_counts[phage]["receptor_like"]
            + rbpbase_boundary_reviewed_count
        )
        if not (pharokka_ready and phold_ready):
            state = "not_assessed"
        elif receptor_total > 0:
            state = "assessed_positive"
        else:
            state = "assessed_zero_detected"
        rows.append(
            {
                "phage_id": phage,
                "study_id": assay.get("study_id", ""),
                "panel_id": assay.get("panel_id", ""),
                "tested_host_count": assay.get("tested_host_count", ""),
                "spot_positive_host_count": assay.get("spot_positive_host_count", ""),
                "spot_negative_host_count": assay.get("spot_negative_host_count", ""),
                "spot_positive_fraction": assay.get("spot_positive_fraction", ""),
                "pharokka_status": pharokka_status.get(phage, "missing"),
                "pharokka_keyword_rows": str(pharokka_counts[phage]["keyword_rows"]),
                "pharokka_receptor_like_rows": str(pharokka_counts[phage]["receptor_like"]),
                "pharokka_tail_fiber_rows": str(pharokka_counts[phage]["tail_fiber"]),
                "pharokka_tailspike_rows": str(pharokka_counts[phage]["tailspike"]),
                "pharokka_receptor_binding_rows": str(pharokka_counts[phage]["receptor_binding"]),
                "pharokka_depolymerase_rows": str(pharokka_counts[phage]["depolymerase"]),
                "pharokka_baseplate_rows": str(pharokka_counts[phage]["baseplate"]),
                "phold_status": phold_status.get(phage, "missing"),
                "phold_prediction_rows": phold_prediction_rows.get(phage, "0"),
                "phold_receptor_like_rows": str(phold_counts[phage]["receptor_like"]),
                "phold_non_pharokka_receptor_like_rows": phold_non_pharokka.get(phage, "0"),
                "phold_tail_fiber_rows": str(phold_counts[phage]["tail_fiber"]),
                "phold_tailspike_rows": str(phold_counts[phage]["tailspike"]),
                "phold_receptor_binding_rows": str(phold_counts[phage]["receptor_binding"]),
                "phold_depolymerase_rows": str(phold_counts[phage]["depolymerase"]),
                "phold_baseplate_rows": str(phold_counts[phage]["baseplate"]),
                "rbpbase_candidate_count": str(rbp_counts[phage]["candidate_count"]),
                "rbpbase_high_confidence_count": str(rbp_counts[phage]["high_confidence_count"]),
                "rbpbase_source_candidate_count": str(rbpbase_source_counts[phage]),
                "rbpbase_boundary_reviewed_missing_count": str(rbpbase_boundary_missing_counts[phage]["missing_count"]),
                "rbpbase_boundary_reviewed_high_score_missing_count": str(rbpbase_boundary_missing_counts[phage]["high_score_missing_count"]),
                "rbpbase_boundary_reviewed_candidate_count": str(rbpbase_boundary_reviewed_count),
                "phage_side_receptor_feature_state": state,
                "model_use_state": "feature_available_for_audit_not_claim_ready" if state == "assessed_positive" else "review_before_modeling",
                "claim_boundary": "Feature coverage only; not receptor specificity, capsule binding, or host-range prediction.",
            }
        )

    assay_phages = len(rows)
    full_pharokka_phold = sum(1 for row in rows if row["pharokka_status"] in {"completed", "skipped_existing"} and row["phold_status"] in {"completed", "skipped_existing"})
    any_receptor = sum(1 for row in rows if row["phage_side_receptor_feature_state"] == "assessed_positive")
    summary = [
        {"metric": "assay_phages", "value": str(assay_phages), "interpretation": "Phages with tested spot-assay panel breadth rows."},
        {"metric": "phages_with_full_pharokka_and_phold", "value": str(full_pharokka_phold), "interpretation": "Assay phages with completed/reused full-set Pharokka and Phold/Foldseek outputs."},
        {"metric": "phages_with_any_receptor_like_evidence", "value": str(any_receptor), "interpretation": "Phages with at least one RBPbase, Pharokka, or Phold receptor-like candidate row."},
        {"metric": "phages_assessed_zero_detected", "value": str(sum(1 for row in rows if row["phage_side_receptor_feature_state"] == "assessed_zero_detected")), "interpretation": "Phages fully assessed by current phage-side tools but with no receptor-like candidate rows."},
        {"metric": "total_rbpbase_candidate_rows", "value": str(sum(to_int(row["rbpbase_candidate_count"]) for row in rows)), "interpretation": "Exact current Prodigal CDS matches to RBPbase candidates across assay phages."},
        {"metric": "total_rbpbase_source_candidate_rows", "value": str(sum(to_int(row["rbpbase_source_candidate_count"]) for row in rows)), "interpretation": "Original PhageHostLearn RBPbase candidate proteins across assay phages."},
        {"metric": "total_rbpbase_boundary_reviewed_missing_rows", "value": str(sum(to_int(row["rbpbase_boundary_reviewed_missing_count"]) for row in rows)), "interpretation": "RBPbase candidates missing exact CDS matches but recovered as near-identical or strong same-phage BLASTP hits."},
        {"metric": "total_rbpbase_boundary_reviewed_candidate_rows", "value": str(sum(to_int(row["rbpbase_boundary_reviewed_candidate_count"]) for row in rows)), "interpretation": "Exact RBPbase CDS matches plus boundary-reviewed missing RBPbase candidates."},
        {"metric": "total_pharokka_receptor_like_rows", "value": str(sum(to_int(row["pharokka_receptor_like_rows"]) for row in rows)), "interpretation": "Pharokka receptor-like keyword rows across assay phages."},
        {"metric": "total_phold_receptor_like_cds_rows", "value": str(sum(to_int(row.get("receptor_like_rows", "0")) for row in phold_run)), "interpretation": "Phold per-CDS rows with any receptor-like keyword, including carried-forward Pharokka rows."},
        {"metric": "total_phold_receptor_like_feature_rows", "value": str(sum(to_int(row["phold_receptor_like_rows"]) for row in rows)), "interpretation": "Feature-level receptor-like rows in the filtered Phold relevant-hit table; one CDS may contribute more than one feature label."},
        {"metric": "total_phold_non_pharokka_receptor_like_rows", "value": str(sum(to_int(row["phold_non_pharokka_receptor_like_rows"]) for row in rows)), "interpretation": "Phold/Foldseek receptor-like rows newly assigned by non-Pharokka methods."},
    ]

    readiness = [
        {
            "readiness_item": "phage_side_receptor_features",
            "status": "available_for_feature_audit" if full_pharokka_phold == assay_phages else "incomplete",
            "evidence": f"{full_pharokka_phold}/{assay_phages} assay phages have full-set Pharokka and Phold/Foldseek outputs; {any_receptor}/{assay_phages} have receptor-like evidence.",
            "next_action": "Integrate host K/O and taxonomy/genome-similarity baselines, then build grouped receptor-layer model inputs.",
            "claim_boundary": "Phage-side features alone do not prove host range or receptor specificity.",
        },
        {
            "readiness_item": "receptor_layer_model",
            "status": "feature_coverage_available_for_pairwise_modeling",
            "evidence": "Spot outcomes and phage-side receptor features are available; downstream pairwise matrix and grouped model scripts consume this coverage table.",
            "next_action": "Refresh the pairwise feature matrix and grouped H1 model comparison after any receptor-feature coverage change.",
            "claim_boundary": "No claim that RBP/depolymerase features outperform taxonomy unless grouped model comparison and robustness checks support it.",
        },
        {
            "readiness_item": "defense_counterdefense_model",
            "status": (
                "blocked_no_productive_infection_labels"
                if productive_measured == 0 and host_defense_hosts and phage_antidefense_phages
                else "blocked_no_productive_infection_and_incomplete_counterdefense_evidence"
            ),
            "evidence": (
                f"host_defense_hosts={len(host_defense_hosts)}; "
                f"accepted_phage_counterdefense_phages={len(phage_antidefense_phages)}; "
                f"productive_infection_outcomes={productive_measured}. Current assay endpoint is spot-test initial interaction."
            ),
            "next_action": "Curate productive-infection, plaque, propagation, or EOP outcomes before testing defense/counter-defense compatibility; expand accepted phage counter-defense evidence for H3/H4 coverage.",
            "claim_boundary": "No defense/counter-defense host-range claim from spot outcomes alone.",
        },
    ]

    write_tsv(Path(args.coverage_output), COVERAGE_COLUMNS, rows)
    write_tsv(Path(args.summary_output), SUMMARY_COLUMNS, summary)
    write_tsv(Path(args.readiness_output), READINESS_COLUMNS, readiness)
    build_report(Path(args.report_output), summary, readiness, args)
    print(f"Receptor feature coverage rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
