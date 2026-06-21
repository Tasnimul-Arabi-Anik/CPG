#!/usr/bin/env python3
"""Build a pairwise receptor-layer feature matrix for tested spot assays.

This joins observed spot-test outcomes with host K/O/ST features, phage-side
receptor feature coverage, and phage cluster labels. It does not fit a model or
claim receptor specificity.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

MISSING = {"", "NA", "N/A", "na", "n/a", "unknown", "Unknown", "none", "None"}
MATRIX_COLUMNS = [
    "interaction_id",
    "phage_id",
    "host_id",
    "study_id",
    "panel_id",
    "assay_type",
    "spot_result",
    "spot_positive_binary",
    "productive_infection_result",
    "outcome_tier",
    "host_K_locus",
    "host_K_type",
    "host_K_confidence",
    "host_O_locus",
    "host_O_type",
    "host_O_confidence",
    "host_species",
    "host_ST",
    "phage_species_cluster_id",
    "phage_representative_id",
    "pharokka_receptor_like_rows",
    "phold_receptor_like_feature_rows",
    "phold_non_pharokka_receptor_like_rows",
    "rbpbase_candidate_count",
    "rbpbase_high_confidence_count",
    "rbpbase_source_candidate_count",
    "rbpbase_boundary_reviewed_missing_count",
    "rbpbase_boundary_reviewed_high_score_missing_count",
    "rbpbase_boundary_reviewed_candidate_count",
    "phage_side_receptor_feature_state",
    "host_receptor_feature_state",
    "taxonomy_baseline_state",
    "pair_feature_state",
    "split_group_phage",
    "split_group_host",
    "split_group_phage_cluster",
    "split_group_host_ST",
    "split_group_study_panel",
    "claim_boundary",
]
SUMMARY_COLUMNS = ["metric", "value", "interpretation"]
READINESS_COLUMNS = ["readiness_item", "status", "evidence", "next_action", "claim_boundary"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build pairwise receptor-layer feature matrix for tested spot assays.")
    parser.add_argument("--assays", default="data/metadata/assay_source_exports/reviewed_klebsiella_phage_host_assays.tsv")
    parser.add_argument("--kaptive", default="data/metadata/production_evidence/kaptive_ko_typing.tsv")
    parser.add_argument("--kleborate", default="data/metadata/production_evidence/kleborate_host_features.tsv")
    parser.add_argument("--phage-features", default="results/production/receptor_features/assay_phage_receptor_feature_coverage.tsv")
    parser.add_argument("--clusters", default="results/production/clusters/phage_clusters.tsv")
    parser.add_argument("--candidates", default="results/production/rbp_depolymerase/candidates.tsv")
    parser.add_argument("--matrix-output", default="results/production/model_inputs/receptor_layer_pairwise_features.tsv")
    parser.add_argument("--summary-output", default="results/production/model_inputs/receptor_layer_pairwise_feature_summary.tsv")
    parser.add_argument("--readiness-output", default="results/production/model_inputs/receptor_layer_pairwise_model_readiness.tsv")
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


def present(value: str) -> bool:
    return value not in MISSING


def first_nonmissing(values: list[str]) -> str:
    for value in values:
        if present(value):
            return value
    return "NA"


def build_report(path: Path, summary: list[dict[str, str]], readiness: list[dict[str, str]], args: argparse.Namespace) -> None:
    values = {row["metric"]: row["value"] for row in summary}
    model_state = next((row["status"] for row in readiness if row["readiness_item"] == "receptor_layer_pairwise_matrix"), "unknown")
    section = f"""\n\n## Receptor-Layer Pairwise Feature Matrix\n\nA tested-pair feature matrix was built from reviewed PhageHostLearn spot assays, host K/O/ST evidence, full-set phage receptor-feature coverage, and phage species-cluster labels. Exact RBPbase CDS matches and boundary-reviewed RBPbase candidates are retained as separate feature columns. Matrix: `{args.matrix_output}`. Rows: {values.get('tested_spot_pairs', '0')}; spot-positive: {values.get('spot_positive_pairs', '0')}; spot-negative: {values.get('spot_negative_pairs', '0')}. Pair rows with complete host receptor features and phage receptor features: {values.get('pairs_complete_for_receptor_features', '0')}. Pair rows with a phage cluster/taxonomy baseline label: {values.get('pairs_with_taxonomy_baseline', '0')}.\n\nReadiness: `{model_state}`. This matrix is the receptor-layer modeling input. Cold-phage, cold-host, cold-cluster, and study/panel grouping columns are included to prevent naive random-pair leakage.\n\nClaim boundary: this matrix prepares an H1 receptor-layer test. It does not claim RBP/depolymerase features outperform taxonomy, and it does not address productive infection or defense/counter-defense compatibility.\n"""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    marker = "\n## Receptor-Layer Pairwise Feature Matrix\n"
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
    assays = read_tsv(Path(args.assays))
    kaptive = {row["host_genome_id"]: row for row in read_tsv(Path(args.kaptive))}
    kleborate = {row["host_genome_id"]: row for row in read_tsv(Path(args.kleborate))}
    phage_features = {row["phage_id"]: row for row in read_tsv(Path(args.phage_features))}
    cluster_rows = read_tsv(Path(args.clusters), required=False)
    candidates = read_tsv(Path(args.candidates), required=False)

    cluster_by_phage: dict[str, str] = {}
    representative_by_phage: dict[str, str] = {}
    for row in cluster_rows:
        phage = row.get("genome_id", "")
        if not phage:
            continue
        cluster_by_phage.setdefault(phage, row.get("cluster_id", ""))
        representative_by_phage.setdefault(phage, row.get("representative_id", ""))
    for row in candidates:
        phage = row.get("genome_id", "")
        if not phage:
            continue
        cluster_by_phage.setdefault(phage, row.get("species_cluster_id", ""))
        representative_by_phage.setdefault(phage, row.get("representative_id", ""))

    rows: list[dict[str, str]] = []
    for assay in assays:
        if assay.get("tested", "").lower() != "true" or assay.get("assay_type") != "spot":
            continue
        phage = assay.get("phage_id", "")
        host = assay.get("host_id", "")
        k = kaptive.get(host, {})
        kb = kleborate.get(host, {})
        pf = phage_features.get(phage, {})
        spot = assay.get("spot_result", "")
        spot_binary = "1" if spot == "positive" else "0" if spot == "negative" else "NA"
        host_receptor_ready = present(k.get("K_locus", "")) and present(k.get("O_locus", ""))
        phage_receptor_ready = pf.get("phage_side_receptor_feature_state") in {"assessed_positive", "assessed_zero_detected"}
        taxonomy_ready = present(cluster_by_phage.get(phage, ""))
        if host_receptor_ready and phage_receptor_ready and spot_binary in {"0", "1"}:
            pair_state = "complete_for_receptor_layer"
        else:
            pair_state = "incomplete"
        host_st = kb.get("ST", "")
        cluster = cluster_by_phage.get(phage, "NA") or "NA"
        rows.append(
            {
                "interaction_id": assay.get("interaction_id", ""),
                "phage_id": phage,
                "host_id": host,
                "study_id": assay.get("study_id", ""),
                "panel_id": assay.get("panel_id", ""),
                "assay_type": assay.get("assay_type", ""),
                "spot_result": spot,
                "spot_positive_binary": spot_binary,
                "productive_infection_result": assay.get("productive_infection_result", ""),
                "outcome_tier": assay.get("outcome_tier", ""),
                "host_K_locus": k.get("K_locus", "NA") or "NA",
                "host_K_type": k.get("K_type", "NA") or "NA",
                "host_K_confidence": k.get("K_confidence", "NA") or "NA",
                "host_O_locus": k.get("O_locus", "NA") or "NA",
                "host_O_type": k.get("O_type", "NA") or "NA",
                "host_O_confidence": k.get("O_confidence", "NA") or "NA",
                "host_species": kb.get("species", "NA") or "NA",
                "host_ST": host_st or "NA",
                "phage_species_cluster_id": cluster,
                "phage_representative_id": representative_by_phage.get(phage, "NA") or "NA",
                "pharokka_receptor_like_rows": pf.get("pharokka_receptor_like_rows", "0"),
                "phold_receptor_like_feature_rows": pf.get("phold_receptor_like_rows", "0"),
                "phold_non_pharokka_receptor_like_rows": pf.get("phold_non_pharokka_receptor_like_rows", "0"),
                "rbpbase_candidate_count": pf.get("rbpbase_candidate_count", "0"),
                "rbpbase_high_confidence_count": pf.get("rbpbase_high_confidence_count", "0"),
                "rbpbase_source_candidate_count": pf.get("rbpbase_source_candidate_count", "0"),
                "rbpbase_boundary_reviewed_missing_count": pf.get("rbpbase_boundary_reviewed_missing_count", "0"),
                "rbpbase_boundary_reviewed_high_score_missing_count": pf.get("rbpbase_boundary_reviewed_high_score_missing_count", "0"),
                "rbpbase_boundary_reviewed_candidate_count": pf.get("rbpbase_boundary_reviewed_candidate_count", pf.get("rbpbase_candidate_count", "0")),
                "phage_side_receptor_feature_state": pf.get("phage_side_receptor_feature_state", "not_assessed"),
                "host_receptor_feature_state": "available" if host_receptor_ready else "missing_KO",
                "taxonomy_baseline_state": "available" if taxonomy_ready else "missing_cluster_label",
                "pair_feature_state": pair_state,
                "split_group_phage": phage,
                "split_group_host": host,
                "split_group_phage_cluster": cluster,
                "split_group_host_ST": host_st or "NA",
                "split_group_study_panel": f"{assay.get('study_id', '')}|{assay.get('panel_id', '')}",
                "claim_boundary": "Model input row only; not evidence that receptor features predict host range better than taxonomy.",
            }
        )

    outcome_counts = Counter(row["spot_result"] for row in rows)
    pair_states = Counter(row["pair_feature_state"] for row in rows)
    host_feature_pairs = sum(1 for row in rows if row["host_receptor_feature_state"] == "available")
    phage_feature_pairs = sum(1 for row in rows if row["phage_side_receptor_feature_state"] in {"assessed_positive", "assessed_zero_detected"})
    taxonomy_pairs = sum(1 for row in rows if row["taxonomy_baseline_state"] == "available")
    summary = [
        {"metric": "tested_spot_pairs", "value": str(len(rows)), "interpretation": "Reviewed tested spot-assay phage-host pairs included in the feature matrix."},
        {"metric": "spot_positive_pairs", "value": str(outcome_counts.get("positive", 0)), "interpretation": "Spot-positive initial interaction rows."},
        {"metric": "spot_negative_pairs", "value": str(outcome_counts.get("negative", 0)), "interpretation": "Tested spot-negative rows; not untested blanks."},
        {"metric": "unique_phages", "value": str(len({row["phage_id"] for row in rows})), "interpretation": "Unique assay phages in matrix."},
        {"metric": "unique_hosts", "value": str(len({row["host_id"] for row in rows})), "interpretation": "Unique assay hosts in matrix."},
        {"metric": "pairs_with_host_KO", "value": str(host_feature_pairs), "interpretation": "Pair rows whose host has K and O locus evidence."},
        {"metric": "pairs_with_phage_receptor_features", "value": str(phage_feature_pairs), "interpretation": "Pair rows whose phage has assessed receptor-feature evidence."},
        {"metric": "pairs_with_taxonomy_baseline", "value": str(taxonomy_pairs), "interpretation": "Pair rows whose phage has a species-cluster/taxonomy baseline label."},
        {"metric": "pairs_complete_for_receptor_features", "value": str(pair_states.get("complete_for_receptor_layer", 0)), "interpretation": "Pair rows with spot outcome, host K/O, and assessed phage receptor features."},
        {"metric": "pairs_missing_taxonomy_baseline", "value": str(len(rows) - taxonomy_pairs), "interpretation": "Pair rows missing a phage species-cluster baseline label; keep missingness explicit."},
    ]
    ready = pair_states.get("complete_for_receptor_layer", 0) == len(rows) and len(rows) > 0
    readiness = [
        {
            "readiness_item": "receptor_layer_pairwise_matrix",
            "status": "matrix_available_for_receptor_layer_modeling" if ready else "matrix_incomplete",
            "evidence": f"{pair_states.get('complete_for_receptor_layer', 0)}/{len(rows)} pairs have spot outcome, host K/O, and phage receptor features; {taxonomy_pairs}/{len(rows)} have phage cluster baseline labels.",
            "next_action": "Run or refresh grouped baseline comparisons: taxonomy/cluster-only, receptor-feature-only, host-K/O-only, and combined receptor features. Use cold-phage, cold-host, cold-cluster, and study/panel-aware splits.",
            "claim_boundary": "No final H1 claim until grouped model comparison, robustness checks, leakage checks, and manuscript-grade baselines are run.",
        },
        {
            "readiness_item": "defense_counterdefense_pairwise_matrix",
            "status": "blocked_no_defense_features_no_productive_infection",
            "evidence": "Current matrix is spot-test initial interaction only and lacks accepted defense/counter-defense features.",
            "next_action": "Keep H4 blocked until productive-infection labels or a justified initial-interaction-only defense question is defined with accepted defense features.",
            "claim_boundary": "No defense/counter-defense compatibility claim.",
        },
    ]

    write_tsv(Path(args.matrix_output), MATRIX_COLUMNS, rows)
    write_tsv(Path(args.summary_output), SUMMARY_COLUMNS, summary)
    write_tsv(Path(args.readiness_output), READINESS_COLUMNS, readiness)
    build_report(Path(args.report_output), summary, readiness, args)
    print(f"Pairwise receptor feature matrix rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
