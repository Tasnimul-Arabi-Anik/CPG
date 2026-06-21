#!/usr/bin/env python3
"""Run grouped receptor-layer baseline comparisons for spot outcomes.

This is a dependency-light, interpretable rate-baseline comparison. It avoids
random pair-level splits and does not claim biological causality.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import random
from collections import Counter, defaultdict
from pathlib import Path

MODEL_COLUMNS = [
    "hypothesis",
    "split_strategy",
    "fold",
    "model_name",
    "feature_key",
    "train_rows",
    "test_rows",
    "test_positive_rows",
    "test_negative_rows",
    "average_precision",
    "roc_auc",
    "balanced_accuracy_at_train_prevalence",
    "brier_score",
    "train_prevalence",
    "notes",
]
SUMMARY_COLUMNS = [
    "hypothesis",
    "split_strategy",
    "model_name",
    "folds_evaluated",
    "mean_average_precision",
    "mean_roc_auc",
    "mean_balanced_accuracy_at_train_prevalence",
    "mean_brier_score",
    "interpretation",
]
PREDICTION_COLUMNS = [
    "interaction_id",
    "phage_id",
    "host_id",
    "study_id",
    "panel_id",
    "split_strategy",
    "fold",
    "held_out_group",
    "true_label",
    "predicted_score",
    "model_id",
    "baseline_id",
    "support_state",
    "training_support_rows",
    "intermediate_support_rows",
    "nearest_phage_count",
    "used_global_prevalence",
    "claim_boundary",
]
SUPPORT_DIAGNOSTIC_COLUMNS = [
    "hypothesis",
    "split_strategy",
    "fold",
    "model_name",
    "test_rows",
    "direct_support_rows",
    "intermediate_fallback_rows",
    "global_fallback_rows",
    "global_model_rows",
    "missing_similarity_rows",
    "median_training_support_rows",
    "mean_training_support_rows",
    "min_training_support_rows",
    "max_training_support_rows",
    "notes",
]
POOLED_COLUMNS = [
    "hypothesis",
    "split_strategy",
    "model_name",
    "prediction_rows",
    "positive_rows",
    "negative_rows",
    "pooled_average_precision",
    "pooled_roc_auc",
    "pooled_balanced_accuracy_at_global_prevalence",
    "pooled_brier_score",
    "interpretation",
]
ABLATION_COLUMNS = [
    "hypothesis",
    "split_strategy",
    "contrast_name",
    "model_name",
    "baseline_model",
    "metric",
    "model_value",
    "baseline_value",
    "delta",
    "interpretation",
]
GROUP_BOOTSTRAP_COLUMNS = [
    "hypothesis",
    "split_strategy",
    "contrast_name",
    "model_name",
    "baseline_model",
    "metric",
    "held_out_groups",
    "observed_model_value",
    "observed_baseline_value",
    "observed_delta",
    "bootstrap_iterations",
    "valid_bootstrap_iterations",
    "bootstrap_ci95_low",
    "bootstrap_ci95_high",
    "interpretation",
]
DELTA_COLUMNS = [
    "hypothesis",
    "split_strategy",
    "model_name",
    "baseline_model",
    "metric",
    "metric_direction",
    "folds_compared",
    "mean_model",
    "mean_baseline",
    "mean_improvement_delta",
    "bootstrap_ci95_low",
    "bootstrap_ci95_high",
    "sign_flip_p_value_one_sided",
    "interpretation",
]
READINESS_COLUMNS = ["readiness_item", "status", "evidence", "next_action", "claim_boundary"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run grouped receptor-layer model comparisons from pairwise feature matrix.")
    parser.add_argument("--matrix", default="results/production/model_inputs/receptor_layer_pairwise_features.tsv")
    parser.add_argument("--genome-similarity", default="data/metadata/production_evidence/phage_genome_similarity.tsv")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--smoothing", type=float, default=5.0)
    parser.add_argument("--similarity-top-k", type=int, default=5)
    parser.add_argument("--model-output", default="results/production/models/receptor_layer_model_comparison.tsv")
    parser.add_argument("--summary-output", default="results/production/models/receptor_layer_model_summary.tsv")
    parser.add_argument("--prediction-output", default="results/production/models/receptor_layer_out_of_fold_predictions.tsv")
    parser.add_argument("--pooled-summary-output", default="results/production/models/receptor_layer_model_pooled_summary.tsv")
    parser.add_argument("--support-diagnostics-output", default="results/production/models/receptor_layer_support_diagnostics.tsv")
    parser.add_argument("--ablation-output", default="results/production/models/receptor_layer_feature_source_ablation.tsv")
    parser.add_argument("--group-bootstrap-output", default="results/production/models/receptor_layer_group_bootstrap_delta.tsv")
    parser.add_argument("--delta-output", default="results/production/models/receptor_layer_model_delta_summary.tsv")
    parser.add_argument("--readiness-output", default="results/production/models/receptor_layer_model_readiness.tsv")
    parser.add_argument("--report-output", default="results/production/models/receptor_layer_model_report.md")
    parser.add_argument("--bootstrap-iterations", type=int, default=1000)
    parser.add_argument("--group-bootstrap-iterations", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260621)
    return parser.parse_args()


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{k: "" if v is None else v for k, v in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def to_float(value: str) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


def load_similarity_scores(path: Path) -> dict[str, dict[str, float]]:
    scores: dict[str, dict[str, float]] = defaultdict(dict)
    if not path.exists():
        return scores
    for row in read_tsv(path):
        left = row.get("genome_id_1", "")
        right = row.get("genome_id_2", "")
        if not left or not right:
            continue
        identity = to_float(row.get("identity_percent", "0"))
        coverage = to_float(row.get("coverage_percent", "0"))
        score = max(0.0, identity * coverage / 100.0)
        scores[left][right] = max(scores[left].get(right, 0.0), score)
        scores[right][left] = max(scores[right].get(left, 0.0), score)
    return scores


def host_ko_key(row: dict[str, str]) -> str:
    return "K=" + (row.get("host_K_locus", "NA") or "NA") + "|O=" + (row.get("host_O_locus", "NA") or "NA")


def train_phage_rates(
    rows: list[dict[str, str]], smoothing: float
) -> tuple[dict[str, float], dict[tuple[str, str], float], float, dict[str, int], dict[tuple[str, str], int]]:
    positives = sum(to_int(row["spot_positive_binary"]) for row in rows)
    total = len(rows)
    prevalence = positives / total if total else 0.0
    phage_counts: dict[str, Counter[int]] = defaultdict(Counter)
    phage_ko_counts: dict[tuple[str, str], Counter[int]] = defaultdict(Counter)
    for row in rows:
        label = to_int(row["spot_positive_binary"])
        phage = row["phage_id"]
        phage_counts[phage][label] += 1
        phage_ko_counts[(phage, host_ko_key(row))][label] += 1
    phage_rates = {}
    phage_support = {}
    for phage, counter in phage_counts.items():
        n = counter[0] + counter[1]
        phage_support[phage] = n
        phage_rates[phage] = (counter[1] + smoothing * prevalence) / (n + smoothing) if n else prevalence
    phage_ko_rates = {}
    phage_ko_support = {}
    for key, counter in phage_ko_counts.items():
        n = counter[0] + counter[1]
        phage_ko_support[key] = n
        phage_ko_rates[key] = (counter[1] + smoothing * prevalence) / (n + smoothing) if n else prevalence
    return phage_rates, phage_ko_rates, prevalence, phage_support, phage_ko_support


def nearest_training_phages(
    test_phage: str,
    train_phages: set[str],
    similarity_scores: dict[str, dict[str, float]],
    top_k: int,
) -> list[tuple[str, float]]:
    ranked: list[tuple[str, float]] = []
    for phage in train_phages:
        score = 100.0 if phage == test_phage else similarity_scores.get(test_phage, {}).get(phage, 0.0)
        if score > 0:
            ranked.append((phage, score))
    ranked.sort(key=lambda item: (-item[1], item[0]))
    return ranked[: max(1, top_k)]


def weighted_rate(phage_weights: list[tuple[str, float]], rates: dict[str, float], fallback: float) -> float:
    score, _support = weighted_rate_with_support(phage_weights, rates, {}, fallback)
    return score


def weighted_rate_with_support(
    phage_weights: list[tuple[str, float]],
    rates: dict[str, float],
    support_counts: dict[str, int],
    fallback: float,
) -> tuple[float, int]:
    numerator = 0.0
    denominator = 0.0
    support = 0
    for phage, weight in phage_weights:
        if phage not in rates:
            continue
        numerator += rates[phage] * weight
        denominator += weight
        support += support_counts.get(phage, 0)
    return (numerator / denominator if denominator else fallback), support


def weighted_ko_rate(
    phage_weights: list[tuple[str, float]],
    host_key: str,
    rates: dict[tuple[str, str], float],
    fallback: float,
) -> float:
    score, _support = weighted_ko_rate_with_support(phage_weights, host_key, rates, {}, fallback)
    return score


def weighted_ko_rate_with_support(
    phage_weights: list[tuple[str, float]],
    host_key: str,
    rates: dict[tuple[str, str], float],
    support_counts: dict[tuple[str, str], int],
    fallback: float,
) -> tuple[float, int]:
    numerator = 0.0
    denominator = 0.0
    support = 0
    for phage, weight in phage_weights:
        key = (phage, host_key)
        if key not in rates:
            continue
        numerator += rates[key] * weight
        denominator += weight
        support += support_counts.get(key, 0)
    return (numerator / denominator if denominator else fallback), support


def predict_genome_similarity(
    train_rows: list[dict[str, str]],
    test_rows: list[dict[str, str]],
    model_name: str,
    similarity_scores: dict[str, dict[str, float]],
    smoothing: float,
    top_k: int,
) -> tuple[list[float], float, list[dict[str, str]]]:
    phage_rates, phage_ko_rates, prevalence, phage_support, phage_ko_support = train_phage_rates(train_rows, smoothing)
    train_phages = set(phage_rates)
    scores: list[float] = []
    details: list[dict[str, str]] = []
    for row in test_rows:
        nearest = nearest_training_phages(row["phage_id"], train_phages, similarity_scores, top_k)
        phage_rate, phage_support_rows = weighted_rate_with_support(nearest, phage_rates, phage_support, prevalence)
        nearest_count = sum(1 for phage, _weight in nearest if phage in phage_rates)
        if model_name == "genome_similarity_nearest_phage_rate":
            scores.append(phage_rate)
            support_state = "nearest_phage_rate" if phage_support_rows else "global_prevalence_fallback"
            details.append(
                {
                    "support_state": support_state,
                    "training_support_rows": str(phage_support_rows),
                    "intermediate_support_rows": "0",
                    "nearest_phage_count": str(nearest_count),
                    "used_global_prevalence": "true" if not phage_support_rows else "false",
                }
            )
        elif model_name == "genome_similarity_nearest_phage_host_KO_rate":
            ko_rate, ko_support_rows = weighted_ko_rate_with_support(nearest, host_ko_key(row), phage_ko_rates, phage_ko_support, phage_rate)
            scores.append(ko_rate)
            if ko_support_rows:
                support_state = "nearest_phage_host_KO_rate"
                used_global = "false"
                intermediate_support = str(phage_support_rows)
            elif phage_support_rows:
                support_state = "nearest_phage_rate_fallback"
                used_global = "false"
                intermediate_support = str(phage_support_rows)
            else:
                support_state = "global_prevalence_fallback"
                used_global = "true"
                intermediate_support = "0"
            details.append(
                {
                    "support_state": support_state,
                    "training_support_rows": str(ko_support_rows),
                    "intermediate_support_rows": intermediate_support,
                    "nearest_phage_count": str(nearest_count),
                    "used_global_prevalence": used_global,
                }
            )
        else:
            raise ValueError(model_name)
    return scores, prevalence, details


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


def bin_count(value: str) -> str:
    count = to_int(value)
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    if count <= 4:
        return "2_4"
    return "5_plus"


def receptor_signature(row: dict[str, str], rbpbase_field: str = "rbpbase_candidate_count") -> str:
    return "|".join(
        [
            "pharokka=" + bin_count(row.get("pharokka_receptor_like_rows", "0")),
            "phold=" + bin_count(row.get("phold_receptor_like_feature_rows", "0")),
            "phold_new=" + bin_count(row.get("phold_non_pharokka_receptor_like_rows", "0")),
            "rbpbase=" + bin_count(row.get(rbpbase_field, "0")),
        ]
    )


def module_identity_signature(row: dict[str, str], source: str = "domain_structural") -> str:
    if source == "domain":
        return row.get("rbp_domain_module_signature", "domain:none") or "domain:none"
    if source == "structural":
        return row.get("rbp_structural_module_signature", "structural:none") or "structural:none"
    if source == "domain_structural":
        return row.get("rbp_domain_structural_module_signature", "domain:none|structural:none") or "domain:none|structural:none"
    raise ValueError(source)


def source_receptor_signature(row: dict[str, str], source: str) -> str:
    if source == "rbpbase":
        return "rbpbase=" + bin_count(row.get("rbpbase_candidate_count", "0"))
    if source == "rbpbase_boundary_reviewed":
        return "rbpbase_boundary_reviewed=" + bin_count(row.get("rbpbase_boundary_reviewed_candidate_count", "0"))
    if source == "pharokka":
        return "pharokka=" + bin_count(row.get("pharokka_receptor_like_rows", "0"))
    if source == "phold":
        return "|".join(
            [
                "phold=" + bin_count(row.get("phold_receptor_like_feature_rows", "0")),
                "phold_new=" + bin_count(row.get("phold_non_pharokka_receptor_like_rows", "0")),
            ]
        )
    if source == "phold_new":
        return "phold_new=" + bin_count(row.get("phold_non_pharokka_receptor_like_rows", "0"))
    if source == "pharokka_phold":
        return "|".join(
            [
                "pharokka=" + bin_count(row.get("pharokka_receptor_like_rows", "0")),
                "phold=" + bin_count(row.get("phold_receptor_like_feature_rows", "0")),
                "phold_new=" + bin_count(row.get("phold_non_pharokka_receptor_like_rows", "0")),
            ]
        )
    raise ValueError(source)


def plus_host_ko(signature: str, row: dict[str, str]) -> str:
    return signature + "|" + host_ko_key(row)


def feature_key(row: dict[str, str], model_name: str) -> str:
    if model_name == "global_prevalence":
        return "global"
    if model_name == "phage_marginal_rate":
        return row.get("phage_id", "NA") or "NA"
    if model_name == "host_marginal_rate":
        return row.get("host_id", "NA") or "NA"
    if model_name == "taxonomy_cluster_rate":
        return row.get("phage_species_cluster_id", "NA") or "NA"
    if model_name == "host_K_type_rate":
        return "K=" + (row.get("host_K_locus", "NA") or "NA")
    if model_name == "host_KO_rate":
        return host_ko_key(row)
    if model_name == "rbpbase_plus_host_KO_rate":
        return plus_host_ko(source_receptor_signature(row, "rbpbase"), row)
    if model_name == "rbpbase_boundary_reviewed_plus_host_KO_rate":
        return plus_host_ko(source_receptor_signature(row, "rbpbase_boundary_reviewed"), row)
    if model_name == "pharokka_plus_host_KO_rate":
        return plus_host_ko(source_receptor_signature(row, "pharokka"), row)
    if model_name == "phold_plus_host_KO_rate":
        return plus_host_ko(source_receptor_signature(row, "phold"), row)
    if model_name == "phold_new_plus_host_KO_rate":
        return plus_host_ko(source_receptor_signature(row, "phold_new"), row)
    if model_name == "pharokka_phold_plus_host_KO_rate":
        return plus_host_ko(source_receptor_signature(row, "pharokka_phold"), row)
    if model_name == "domain_module_plus_host_KO_rate":
        return plus_host_ko(module_identity_signature(row, "domain"), row)
    if model_name == "structural_module_plus_host_KO_rate":
        return plus_host_ko(module_identity_signature(row, "structural"), row)
    if model_name == "domain_structural_module_signature_rate":
        return module_identity_signature(row, "domain_structural")
    if model_name == "domain_structural_module_plus_host_KO_rate":
        return plus_host_ko(module_identity_signature(row, "domain_structural"), row)
    if model_name == "receptor_signature_rate":
        return receptor_signature(row)
    if model_name == "receptor_plus_host_KO_rate":
        return plus_host_ko(receptor_signature(row), row)
    if model_name == "receptor_boundary_reviewed_plus_host_KO_rate":
        return plus_host_ko(receptor_signature(row, "rbpbase_boundary_reviewed_candidate_count"), row)
    if model_name == "combined_receptor_host_taxonomy_rate":
        return plus_host_ko(receptor_signature(row), row) + "|cluster=" + (row.get("phage_species_cluster_id", "NA") or "NA")
    if model_name == "combined_receptor_boundary_reviewed_host_taxonomy_rate":
        return plus_host_ko(receptor_signature(row, "rbpbase_boundary_reviewed_candidate_count"), row) + "|cluster=" + (row.get("phage_species_cluster_id", "NA") or "NA")
    raise ValueError(model_name)


def group_key(row: dict[str, str], split_strategy: str) -> str:
    if split_strategy == "cold_phage":
        return row["split_group_phage"]
    if split_strategy == "cold_host":
        return row["split_group_host"]
    if split_strategy == "cold_K_locus":
        return row.get("host_K_locus", "NA") or "NA"
    if split_strategy == "cold_phage_cluster":
        cluster = row.get("split_group_phage_cluster", "NA") or "NA"
        return cluster if cluster != "NA" else "missing_cluster:" + row["split_group_phage"]
    raise ValueError(split_strategy)


def make_group_folds(rows: list[dict[str, str]], split_strategy: str, n_folds: int) -> list[set[str]]:
    group_counts: dict[str, Counter[int]] = defaultdict(Counter)
    for row in rows:
        group_counts[group_key(row, split_strategy)][to_int(row["spot_positive_binary"])] += 1
    groups = sorted(group_counts, key=lambda g: (-group_counts[g][1], -(group_counts[g][0] + group_counts[g][1]), g))
    folds = [set() for _ in range(n_folds)]
    fold_pos = [0 for _ in range(n_folds)]
    fold_total = [0 for _ in range(n_folds)]
    for group in groups:
        idx = min(range(n_folds), key=lambda i: (fold_pos[i], fold_total[i], i))
        folds[idx].add(group)
        fold_pos[idx] += group_counts[group][1]
        fold_total[idx] += group_counts[group][0] + group_counts[group][1]
    return folds


def train_rate_model(rows: list[dict[str, str]], model_name: str, smoothing: float) -> tuple[dict[str, float], float, dict[str, int]]:
    positives = sum(to_int(row["spot_positive_binary"]) for row in rows)
    total = len(rows)
    prevalence = positives / total if total else 0.0
    counts: dict[str, Counter[int]] = defaultdict(Counter)
    for row in rows:
        counts[feature_key(row, model_name)][to_int(row["spot_positive_binary"])] += 1
    rates = {}
    support = {}
    for key, counter in counts.items():
        n = counter[0] + counter[1]
        support[key] = n
        rates[key] = (counter[1] + smoothing * prevalence) / (n + smoothing) if n else prevalence
    return rates, prevalence, support


def predict(rows: list[dict[str, str]], model_name: str, rates: dict[str, float], fallback: float) -> list[float]:
    return [rates.get(feature_key(row, model_name), fallback) for row in rows]


def predict_with_details(
    rows: list[dict[str, str]],
    model_name: str,
    rates: dict[str, float],
    support_counts: dict[str, int],
    fallback: float,
) -> tuple[list[float], list[dict[str, str]]]:
    scores: list[float] = []
    details: list[dict[str, str]] = []
    for row in rows:
        key = feature_key(row, model_name)
        support = support_counts.get(key, 0)
        if model_name == "global_prevalence":
            score = fallback
            support_state = "global_prevalence_model"
            used_global = "true"
        elif support:
            score = rates[key]
            support_state = "trained_feature_key"
            used_global = "false"
        else:
            score = fallback
            support_state = "global_prevalence_fallback"
            used_global = "true"
        scores.append(score)
        details.append(
            {
                "support_state": support_state,
                "training_support_rows": str(support),
                "intermediate_support_rows": "0",
                "nearest_phage_count": "0",
                "used_global_prevalence": used_global,
            }
        )
    return scores, details


def average_precision(y: list[int], scores: list[float]) -> str:
    positives = sum(y)
    if positives == 0:
        return "NA"
    order = sorted(range(len(y)), key=lambda i: -scores[i])
    true_positive = 0
    false_positive = 0
    previous_recall = 0.0
    ap = 0.0
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and scores[order[j]] == scores[order[i]]:
            j += 1
        group_positives = sum(y[order[k]] for k in range(i, j))
        true_positive += group_positives
        false_positive += (j - i) - group_positives
        recall = true_positive / positives
        precision = true_positive / (true_positive + false_positive)
        ap += (recall - previous_recall) * precision
        previous_recall = recall
        i = j
    return f"{ap:.6f}"


def average_precision_value(y: list[int], scores: list[float]) -> float | None:
    value = average_precision(y, scores)
    if value == "NA":
        return None
    return float(value)


def roc_auc(y: list[int], scores: list[float]) -> str:
    positives = sum(y)
    negatives = len(y) - positives
    if positives == 0 or negatives == 0:
        return "NA"
    order = sorted(range(len(y)), key=lambda i: (scores[i], i))
    rank_sum = 0.0
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and scores[order[j]] == scores[order[i]]:
            j += 1
        avg_rank = (i + 1 + j) / 2
        for k in range(i, j):
            if y[order[k]] == 1:
                rank_sum += avg_rank
        i = j
    auc = (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)
    return f"{auc:.6f}"


def balanced_accuracy(y: list[int], scores: list[float], threshold: float) -> str:
    positives = sum(y)
    negatives = len(y) - positives
    if positives == 0 or negatives == 0:
        return "NA"
    tp = sum(1 for label, score in zip(y, scores) if label == 1 and score >= threshold)
    tn = sum(1 for label, score in zip(y, scores) if label == 0 and score < threshold)
    return f"{((tp / positives) + (tn / negatives)) / 2:.6f}"


def brier_score(y: list[int], scores: list[float]) -> str:
    if not y:
        return "NA"
    return f"{sum((label - score) ** 2 for label, score in zip(y, scores)) / len(y):.6f}"


def mean_metric(rows: list[dict[str, str]], key: str) -> str:
    values = [float(row[key]) for row in rows if row.get(key) not in {"", "NA"}]
    return f"{sum(values) / len(values):.6f}" if values else "NA"


def median_number(values: list[int]) -> str:
    if not values:
        return "NA"
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return f"{ordered[midpoint]:.3f}"
    return f"{((ordered[midpoint - 1] + ordered[midpoint]) / 2):.3f}"


def mean_number(values: list[int]) -> str:
    return f"{(sum(values) / len(values)):.3f}" if values else "NA"


def summarize_support_details(
    split: str,
    fold_idx: int,
    model_name: str,
    details: list[dict[str, str]],
) -> dict[str, str]:
    states = Counter(detail.get("support_state", "") for detail in details)
    support_values = [to_int(detail.get("training_support_rows", "0")) for detail in details]
    direct_states = {"trained_feature_key", "nearest_phage_rate", "nearest_phage_host_KO_rate"}
    direct_rows = sum(states[state] for state in direct_states)
    intermediate_rows = states["nearest_phage_rate_fallback"]
    global_fallback_rows = states["global_prevalence_fallback"]
    global_model_rows = states["global_prevalence_model"]
    missing_similarity_rows = global_fallback_rows if model_name.startswith("genome_similarity_") else 0
    if model_name == "global_prevalence":
        notes = "Global prevalence is the intended model, not an accidental fallback."
    elif model_name.startswith("genome_similarity_"):
        notes = "Direct support means nearest-phage rate or nearest-phage+host-K/O support; intermediate fallback means host-K/O support was absent but nearest-phage marginal support was available."
    else:
        notes = "Direct support means exact training feature key was observed; global fallback means the test feature key was unseen in training."
    return {
        "hypothesis": "H1_spot_interaction_receptor_layer",
        "split_strategy": split,
        "fold": str(fold_idx),
        "model_name": model_name,
        "test_rows": str(len(details)),
        "direct_support_rows": str(direct_rows),
        "intermediate_fallback_rows": str(intermediate_rows),
        "global_fallback_rows": str(global_fallback_rows),
        "global_model_rows": str(global_model_rows),
        "missing_similarity_rows": str(missing_similarity_rows),
        "median_training_support_rows": median_number(support_values),
        "mean_training_support_rows": mean_number(support_values),
        "min_training_support_rows": str(min(support_values)) if support_values else "NA",
        "max_training_support_rows": str(max(support_values)) if support_values else "NA",
        "notes": notes,
    }


def build_pooled_summary(prediction_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in prediction_rows:
        grouped[(row["split_strategy"], row["model_id"])].append(row)
    pooled: list[dict[str, str]] = []
    for (split, model_name), rows in sorted(grouped.items()):
        y = [to_int(row["true_label"]) for row in rows]
        scores = [to_float(row["predicted_score"]) for row in rows]
        prevalence = sum(y) / len(y) if y else 0.0
        pooled.append(
            {
                "hypothesis": "H1_spot_interaction_receptor_layer",
                "split_strategy": split,
                "model_name": model_name,
                "prediction_rows": str(len(rows)),
                "positive_rows": str(sum(y)),
                "negative_rows": str(len(y) - sum(y)),
                "pooled_average_precision": average_precision(y, scores),
                "pooled_roc_auc": roc_auc(y, scores),
                "pooled_balanced_accuracy_at_global_prevalence": balanced_accuracy(y, scores, prevalence),
                "pooled_brier_score": brier_score(y, scores),
                "interpretation": "Pooled out-of-fold metric from grouped splits; spot-test initial interaction only.",
            }
        )
    return pooled


def build_ablation_summary(pooled_summary: list[dict[str, str]]) -> list[dict[str, str]]:
    by_key = {(row["split_strategy"], row["model_name"]): row for row in pooled_summary}
    contrasts = [
        ("rbpbase_increment_over_host_KO", "rbpbase_plus_host_KO_rate", "host_KO_rate"),
        ("boundary_reviewed_rbpbase_increment_over_exact_rbpbase", "rbpbase_boundary_reviewed_plus_host_KO_rate", "rbpbase_plus_host_KO_rate"),
        ("boundary_reviewed_rbpbase_increment_over_host_KO", "rbpbase_boundary_reviewed_plus_host_KO_rate", "host_KO_rate"),
        ("pharokka_increment_over_rbpbase", "pharokka_plus_host_KO_rate", "rbpbase_plus_host_KO_rate"),
        ("phold_increment_over_rbpbase", "phold_plus_host_KO_rate", "rbpbase_plus_host_KO_rate"),
        ("phold_new_increment_over_rbpbase", "phold_new_plus_host_KO_rate", "rbpbase_plus_host_KO_rate"),
        ("pharokka_phold_increment_over_rbpbase", "pharokka_phold_plus_host_KO_rate", "rbpbase_plus_host_KO_rate"),
        ("domain_module_increment_over_rbpbase", "domain_module_plus_host_KO_rate", "rbpbase_plus_host_KO_rate"),
        ("structural_module_increment_over_rbpbase", "structural_module_plus_host_KO_rate", "rbpbase_plus_host_KO_rate"),
        ("domain_structural_module_increment_over_rbpbase", "domain_structural_module_plus_host_KO_rate", "rbpbase_plus_host_KO_rate"),
        ("domain_structural_module_vs_genome_similarity", "domain_structural_module_plus_host_KO_rate", "genome_similarity_nearest_phage_host_KO_rate"),
        ("union_increment_over_rbpbase", "receptor_plus_host_KO_rate", "rbpbase_plus_host_KO_rate"),
        ("boundary_reviewed_union_increment_over_exact_union", "receptor_boundary_reviewed_plus_host_KO_rate", "receptor_plus_host_KO_rate"),
        ("boundary_reviewed_union_vs_genome_similarity", "receptor_boundary_reviewed_plus_host_KO_rate", "genome_similarity_nearest_phage_host_KO_rate"),
        ("primary_receptor_union_vs_genome_similarity", "receptor_plus_host_KO_rate", "genome_similarity_nearest_phage_host_KO_rate"),
    ]
    rows: list[dict[str, str]] = []
    for split in sorted({row["split_strategy"] for row in pooled_summary}):
        for contrast_name, model_name, baseline_name in contrasts:
            model = by_key.get((split, model_name))
            baseline = by_key.get((split, baseline_name))
            if not model or not baseline:
                continue
            model_value = to_float(model.get("pooled_average_precision", "NA"))
            baseline_value = to_float(baseline.get("pooled_average_precision", "NA"))
            delta = model_value - baseline_value
            if delta > 0:
                interpretation = "Model has higher pooled AP than baseline in this exploratory split."
            elif delta < 0:
                interpretation = "Model has lower pooled AP than baseline in this exploratory split."
            else:
                interpretation = "Model and baseline have equal pooled AP in this exploratory split."
            rows.append(
                {
                    "hypothesis": "H1_spot_interaction_receptor_layer",
                    "split_strategy": split,
                    "contrast_name": contrast_name,
                    "model_name": model_name,
                    "baseline_model": baseline_name,
                    "metric": "pooled_average_precision",
                    "model_value": f"{model_value:.6f}",
                    "baseline_value": f"{baseline_value:.6f}",
                    "delta": f"{delta:.6f}",
                    "interpretation": interpretation,
                }
            )
    return rows


def build_group_bootstrap_summary(
    prediction_rows: list[dict[str, str]],
    ablation_summary: list[dict[str, str]],
    iterations: int,
    seed: int,
) -> list[dict[str, str]]:
    by_split_model: dict[tuple[str, str], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in prediction_rows:
        by_split_model[(row["split_strategy"], row["model_id"])][row["interaction_id"]] = row
    rows: list[dict[str, str]] = []
    for idx, contrast in enumerate(ablation_summary):
        split = contrast["split_strategy"]
        model_name = contrast["model_name"]
        baseline_name = contrast["baseline_model"]
        model_predictions = by_split_model.get((split, model_name), {})
        baseline_predictions = by_split_model.get((split, baseline_name), {})
        common_ids = sorted(set(model_predictions) & set(baseline_predictions))
        grouped: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
        for interaction_id in common_ids:
            model_row = model_predictions[interaction_id]
            baseline_row = baseline_predictions[interaction_id]
            group = model_row["held_out_group"]
            label = to_int(model_row["true_label"])
            grouped[group].append((label, to_float(model_row["predicted_score"]), to_float(baseline_row["predicted_score"])))
        groups = sorted(grouped)
        all_values = [value for group in groups for value in grouped[group]]
        labels = [value[0] for value in all_values]
        model_scores = [value[1] for value in all_values]
        baseline_scores = [value[2] for value in all_values]
        observed_model = average_precision_value(labels, model_scores)
        observed_baseline = average_precision_value(labels, baseline_scores)
        if observed_model is None or observed_baseline is None or not groups:
            rows.append(
                {
                    "hypothesis": "H1_spot_interaction_receptor_layer",
                    "split_strategy": split,
                    "contrast_name": contrast["contrast_name"],
                    "model_name": model_name,
                    "baseline_model": baseline_name,
                    "metric": "pooled_average_precision",
                    "held_out_groups": str(len(groups)),
                    "observed_model_value": "NA",
                    "observed_baseline_value": "NA",
                    "observed_delta": "NA",
                    "bootstrap_iterations": str(iterations),
                    "valid_bootstrap_iterations": "0",
                    "bootstrap_ci95_low": "NA",
                    "bootstrap_ci95_high": "NA",
                    "interpretation": "Not evaluable because observed pooled AP could not be computed.",
                }
            )
            continue
        rng = random.Random(seed + idx)
        deltas: list[float] = []
        for _ in range(iterations):
            sampled_groups = [groups[rng.randrange(len(groups))] for _ in groups]
            sampled_values = [value for group in sampled_groups for value in grouped[group]]
            sampled_labels = [value[0] for value in sampled_values]
            if sum(sampled_labels) == 0:
                continue
            sampled_model = average_precision_value(sampled_labels, [value[1] for value in sampled_values])
            sampled_baseline = average_precision_value(sampled_labels, [value[2] for value in sampled_values])
            if sampled_model is None or sampled_baseline is None:
                continue
            deltas.append(sampled_model - sampled_baseline)
        ci_low = f"{percentile(deltas, 0.025):.6f}" if deltas else "NA"
        ci_high = f"{percentile(deltas, 0.975):.6f}" if deltas else "NA"
        observed_delta = observed_model - observed_baseline
        if not deltas:
            interpretation = "No valid bootstrap samples with positives; do not interpret uncertainty."
        elif ci_low != "NA" and float(ci_low) > 0:
            interpretation = "Group-bootstrap CI is above zero; still exploratory and benchmark-specific."
        elif ci_high != "NA" and float(ci_high) < 0:
            interpretation = "Group-bootstrap CI is below zero; model underperforms baseline in this benchmark split."
        else:
            interpretation = "Group-bootstrap CI overlaps zero; no robust AP difference in this exploratory split."
        rows.append(
            {
                "hypothesis": "H1_spot_interaction_receptor_layer",
                "split_strategy": split,
                "contrast_name": contrast["contrast_name"],
                "model_name": model_name,
                "baseline_model": baseline_name,
                "metric": "pooled_average_precision",
                "held_out_groups": str(len(groups)),
                "observed_model_value": f"{observed_model:.6f}",
                "observed_baseline_value": f"{observed_baseline:.6f}",
                "observed_delta": f"{observed_delta:.6f}",
                "bootstrap_iterations": str(iterations),
                "valid_bootstrap_iterations": str(len(deltas)),
                "bootstrap_ci95_low": ci_low,
                "bootstrap_ci95_high": ci_high,
                "interpretation": interpretation,
            }
        )
    return rows


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[idx]


def bootstrap_ci(values: list[float], iterations: int, seed: int) -> tuple[str, str]:
    if not values:
        return "NA", "NA"
    if len(values) == 1 or iterations <= 0:
        observed = values[0]
        return f"{observed:.6f}", f"{observed:.6f}"
    rng = random.Random(seed)
    n = len(values)
    boot = [mean([values[rng.randrange(n)] for _ in range(n)]) for _ in range(iterations)]
    return f"{percentile(boot, 0.025):.6f}", f"{percentile(boot, 0.975):.6f}"


def sign_flip_p_value(values: list[float]) -> str:
    if not values:
        return "NA"
    observed = mean(values)
    n = len(values)
    if n <= 12:
        signed_means = []
        for signs in itertools.product((-1, 1), repeat=n):
            signed_means.append(mean([value * sign for value, sign in zip(values, signs)]))
    else:
        rng = random.Random(20260621 + n)
        signed_means = [
            mean([value * (1 if rng.random() >= 0.5 else -1) for value in values])
            for _ in range(10000)
        ]
    p_value = sum(1 for value in signed_means if value >= observed) / len(signed_means)
    return f"{p_value:.6f}"


def build_delta_summary(
    model_rows: list[dict[str, str]],
    bootstrap_iterations: int,
    seed: int,
    baseline_model: str = "global_prevalence",
) -> list[dict[str, str]]:
    metrics = [
        ("average_precision", "higher_is_better"),
        ("roc_auc", "higher_is_better"),
        ("balanced_accuracy_at_train_prevalence", "higher_is_better"),
        ("brier_score", "lower_is_better"),
    ]
    by_key = {
        (row["split_strategy"], row["fold"], row["model_name"]): row
        for row in model_rows
    }
    models = sorted({row["model_name"] for row in model_rows if row["model_name"] != baseline_model})
    splits = sorted({row["split_strategy"] for row in model_rows})
    delta_rows: list[dict[str, str]] = []
    for split in splits:
        folds = sorted({row["fold"] for row in model_rows if row["split_strategy"] == split}, key=lambda value: int(value))
        for model_name in models:
            for metric, direction in metrics:
                improvements: list[float] = []
                model_values: list[float] = []
                baseline_values: list[float] = []
                for fold in folds:
                    model_row = by_key.get((split, fold, model_name))
                    baseline_row = by_key.get((split, fold, baseline_model))
                    if not model_row or not baseline_row:
                        continue
                    model_value = model_row.get(metric, "NA")
                    baseline_value = baseline_row.get(metric, "NA")
                    if model_value in {"", "NA"} or baseline_value in {"", "NA"}:
                        continue
                    model_float = float(model_value)
                    baseline_float = float(baseline_value)
                    model_values.append(model_float)
                    baseline_values.append(baseline_float)
                    if direction == "higher_is_better":
                        improvements.append(model_float - baseline_float)
                    else:
                        improvements.append(baseline_float - model_float)
                ci_low, ci_high = bootstrap_ci(improvements, bootstrap_iterations, seed + len(delta_rows))
                observed = mean(improvements) if improvements else 0.0
                if not improvements:
                    interpretation = "Not evaluable because no paired fold metrics were available."
                elif observed > 0 and ci_low != "NA" and float(ci_low) > 0:
                    interpretation = "Fold-level improvement over global prevalence is positive with bootstrap CI above zero; still exploratory."
                elif observed > 0:
                    interpretation = "Mean fold-level improvement over global prevalence is positive but uncertainty includes weak or null improvement."
                else:
                    interpretation = "No positive fold-level improvement over global prevalence."
                delta_rows.append(
                    {
                        "hypothesis": "H1_spot_interaction_receptor_layer",
                        "split_strategy": split,
                        "model_name": model_name,
                        "baseline_model": baseline_model,
                        "metric": metric,
                        "metric_direction": direction,
                        "folds_compared": str(len(improvements)),
                        "mean_model": f"{mean(model_values):.6f}" if model_values else "NA",
                        "mean_baseline": f"{mean(baseline_values):.6f}" if baseline_values else "NA",
                        "mean_improvement_delta": f"{observed:.6f}" if improvements else "NA",
                        "bootstrap_ci95_low": ci_low,
                        "bootstrap_ci95_high": ci_high,
                        "sign_flip_p_value_one_sided": sign_flip_p_value(improvements),
                        "interpretation": interpretation,
                    }
                )
    return delta_rows



def genome_similarity_label(path: Path) -> str:
    text = str(path).lower()
    if "skani" in text:
        return "skani"
    if "fastani" in text:
        return "fastANI"
    if "mash" in text:
        return "Mash"
    if "blastn" in text or "phage_genome_similarity" in text:
        return "BLASTN"
    try:
        with path.open(encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            first = next(reader, {})
        method = first.get("method", "").lower()
    except Exception:
        method = ""
    if "skani" in method:
        return "skani"
    if "fastani" in method:
        return "fastANI"
    if "mash" in method:
        return "Mash"
    if "blastn" in method:
        return "BLASTN"
    return "genome-similarity"

def build_report(path: Path, summary: list[dict[str, str]], pooled_summary: list[dict[str, str]], ablation_summary: list[dict[str, str]], group_bootstrap_summary: list[dict[str, str]], delta_summary: list[dict[str, str]], support_diagnostics: list[dict[str, str]], args: argparse.Namespace) -> None:
    similarity_label = genome_similarity_label(Path(args.genome_similarity))
    best_by_split: dict[str, dict[str, str]] = {}
    for row in pooled_summary:
        if row["pooled_average_precision"] == "NA":
            continue
        current = best_by_split.get(row["split_strategy"])
        if current is None or float(row["pooled_average_precision"]) > float(current["pooled_average_precision"]):
            best_by_split[row["split_strategy"]] = row
    best_text = "; ".join(
        f"{split}: {row['model_name']} pooled_AP={row['pooled_average_precision']}"
        for split, row in sorted(best_by_split.items())
    ) or "no evaluable pooled predictions"
    delta_highlights = [
        row for row in delta_summary
        if row["metric"] == "average_precision" and row["mean_improvement_delta"] not in {"", "NA"}
    ]
    delta_text = "; ".join(
        f"{row['split_strategy']} {row['model_name']} AP_delta={row['mean_improvement_delta']} "
        f"CI95=[{row['bootstrap_ci95_low']}, {row['bootstrap_ci95_high']}] "
        f"p={row['sign_flip_p_value_one_sided']}"
        for row in sorted(delta_highlights, key=lambda r: (r["split_strategy"], -float(r["mean_improvement_delta"])))[:6]
    ) or "no evaluable AP deltas"
    summary_by_key = {(row["split_strategy"], row["model_name"]): row for row in pooled_summary}
    receptor_vs_genome_bits = []
    for split in ["cold_phage", "cold_phage_cluster", "cold_K_locus", "cold_host"]:
        receptor_row = summary_by_key.get((split, "receptor_plus_host_KO_rate"))
        genome_row = summary_by_key.get((split, "genome_similarity_nearest_phage_host_KO_rate"))
        if not receptor_row or not genome_row:
            continue
        receptor_ap = receptor_row.get("pooled_average_precision", "NA")
        genome_ap = genome_row.get("pooled_average_precision", "NA")
        receptor_vs_genome_bits.append(
            f"{split}: receptor+K/O AP={receptor_ap}, {similarity_label}-nearest-phage+K/O AP={genome_ap}"
        )
    receptor_vs_genome_text = "; ".join(receptor_vs_genome_bits) or "not evaluable"
    ablation_bits = []
    for row in ablation_summary:
        if row["split_strategy"] == "cold_phage_cluster" and row["contrast_name"] in {
            "phold_increment_over_rbpbase",
            "pharokka_phold_increment_over_rbpbase",
            "domain_module_increment_over_rbpbase",
            "structural_module_increment_over_rbpbase",
            "domain_structural_module_increment_over_rbpbase",
            "domain_structural_module_vs_genome_similarity",
            "union_increment_over_rbpbase",
            "boundary_reviewed_rbpbase_increment_over_exact_rbpbase",
            "boundary_reviewed_union_increment_over_exact_union",
            "boundary_reviewed_union_vs_genome_similarity",
            "primary_receptor_union_vs_genome_similarity",
        }:
            ablation_bits.append(
                f"{row['contrast_name']}: delta_AP={row['delta']} "
                f"({row['model_name']} {row['model_value']} vs {row['baseline_model']} {row['baseline_value']})"
            )
    ablation_text = "; ".join(ablation_bits) or "not evaluable"
    bootstrap_bits = []
    for row in group_bootstrap_summary:
        if row["contrast_name"] == "primary_receptor_union_vs_genome_similarity" and row["split_strategy"] in {"cold_phage_cluster", "cold_K_locus"}:
            bootstrap_bits.append(
                f"{row['split_strategy']}: delta_AP={row['observed_delta']} "
                f"groupCI95=[{row['bootstrap_ci95_low']}, {row['bootstrap_ci95_high']}]"
            )
    bootstrap_text = "; ".join(bootstrap_bits) or "not evaluable"
    cold_k_support_bits = []
    for row in support_diagnostics:
        if row["split_strategy"] == "cold_K_locus" and row["model_name"] in {"receptor_plus_host_KO_rate", "genome_similarity_nearest_phage_host_KO_rate"}:
            cold_k_support_bits.append(
                f"fold {row['fold']} {row['model_name']}: direct={row['direct_support_rows']}, "
                f"intermediate={row['intermediate_fallback_rows']}, global_fallback={row['global_fallback_rows']}, "
                f"median_support={row['median_training_support_rows']}"
            )
    cold_k_support_text = "; ".join(cold_k_support_bits) or "not available"
    section = f"""\n\n## H1 Receptor-Layer Model Comparison\n\nA grouped, interpretable rate-baseline comparison was run from `results/production/model_inputs/receptor_layer_pairwise_features.tsv`. Fold-level metrics: `{args.model_output}`. Out-of-fold predictions: `{args.prediction_output}`. Prediction support diagnostics: `{args.support_diagnostics_output}`. Mean-fold summary metrics: `{args.summary_output}`. Pooled out-of-fold summary metrics: `{args.pooled_summary_output}`. Fold-level deltas versus global prevalence: `{args.delta_output}`. Split strategies: cold phage, cold host, cold K-locus, and cold phage cluster. Models compared: global prevalence, phage marginal rate, host marginal rate, K-type/K/O rates, phage cluster/taxonomy rate, {similarity_label} nearest-phage genome-similarity rates, exact and boundary-reviewed RBPbase rates, receptor-feature count signatures, PHROGs/MMseqs and Phold/Foldseek module-identity signatures, receptor plus host K/O rates, genome similarity plus host K/O rate, and combined receptor plus host K/O plus phage cluster rates. Frozen H1 contract: `docs/h1_receptor_layer_analysis_contract.md`. Best pooled average precision by split: {best_text}. Fold-level diagnostic average-precision deltas versus global prevalence: {delta_text}. Primary pooled receptor-versus-genome baseline comparison: {receptor_vs_genome_text}. Feature-source ablation table: `{args.ablation_output}`. Group-resampling AP delta table: `{args.group_bootstrap_output}`. Cold-cluster receptor-source contrasts: {ablation_text}. Primary group-bootstrap contrasts: {bootstrap_text}. Cold-K fallback/support diagnostics: {cold_k_support_text}.\n\nClaim boundary: this is an initial quantitative H1 test on spot-test interaction outcomes only. It is not evidence of productive infection and does not address defense/counter-defense compatibility. In the current pilot, current receptor summaries, including exact PHROGs/MMseqs and Phold/Foldseek module-identity signatures, do not yet outperform the {similarity_label} nearest-phage plus host K/O baseline under cold-phage, cold-K-locus, or cold-cluster splits. Fold-level intervals and sign-flip checks are diagnostic only. The held-out-group bootstrap intervals are benchmark-specific and use the current grouped folds, not an independent external validation. Treat any apparent model advantage as provisional until independent validation, leakage checks, genuine RBP module identities, and VIRIDIC/Mash-style manuscript-grade phage taxonomy/similarity baselines are added.\n"""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    marker = "\n## H1 Receptor-Layer Model Comparison\n"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + section
    else:
        text = text.rstrip() + section
    path.write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")

def main() -> int:
    args = parse_args()
    rows = [row for row in read_tsv(Path(args.matrix)) if row.get("pair_feature_state") == "complete_for_receptor_layer"]
    model_names = [
        "global_prevalence",
        "phage_marginal_rate",
        "host_marginal_rate",
        "taxonomy_cluster_rate",
        "host_K_type_rate",
        "host_KO_rate",
        "rbpbase_plus_host_KO_rate",
        "rbpbase_boundary_reviewed_plus_host_KO_rate",
        "pharokka_plus_host_KO_rate",
        "phold_plus_host_KO_rate",
        "phold_new_plus_host_KO_rate",
        "pharokka_phold_plus_host_KO_rate",
        "domain_module_plus_host_KO_rate",
        "structural_module_plus_host_KO_rate",
        "domain_structural_module_signature_rate",
        "domain_structural_module_plus_host_KO_rate",
        "receptor_signature_rate",
        "receptor_plus_host_KO_rate",
        "receptor_boundary_reviewed_plus_host_KO_rate",
        "genome_similarity_nearest_phage_rate",
        "genome_similarity_nearest_phage_host_KO_rate",
        "combined_receptor_host_taxonomy_rate",
        "combined_receptor_boundary_reviewed_host_taxonomy_rate",
    ]
    split_strategies = ["cold_phage", "cold_host", "cold_K_locus", "cold_phage_cluster"]
    similarity_scores = load_similarity_scores(Path(args.genome_similarity))
    out_rows: list[dict[str, str]] = []
    prediction_rows: list[dict[str, str]] = []
    support_diagnostic_rows: list[dict[str, str]] = []
    for split in split_strategies:
        folds = make_group_folds(rows, split, args.folds)
        for fold_idx, test_groups in enumerate(folds, start=1):
            train = [row for row in rows if group_key(row, split) not in test_groups]
            test = [row for row in rows if group_key(row, split) in test_groups]
            y = [to_int(row["spot_positive_binary"]) for row in test]
            for model_name in model_names:
                if model_name.startswith("genome_similarity_"):
                    scores, prevalence, support_details = predict_genome_similarity(
                        train,
                        test,
                        model_name,
                        similarity_scores,
                        args.smoothing,
                        args.similarity_top_k,
                    )
                    note = (
                        f"Grouped {genome_similarity_label(Path(args.genome_similarity))} whole-genome nearest-phage baseline; "
                        f"top_k={args.similarity_top_k}; spot-test initial interaction only; "
                        "not productive infection; not a VIRIDIC or independently validated taxonomy substitute."
                    )
                else:
                    rates, prevalence, support_counts = train_rate_model(train, model_name, args.smoothing)
                    scores, support_details = predict_with_details(test, model_name, rates, support_counts, prevalence)
                    note = "Grouped smoothed-rate baseline; spot-test initial interaction only; not productive infection."
                support_diagnostic_rows.append(summarize_support_details(split, fold_idx, model_name, support_details))
                out_rows.append(
                    {
                        "hypothesis": "H1_spot_interaction_receptor_layer",
                        "split_strategy": split,
                        "fold": str(fold_idx),
                        "model_name": model_name,
                        "feature_key": model_name,
                        "train_rows": str(len(train)),
                        "test_rows": str(len(test)),
                        "test_positive_rows": str(sum(y)),
                        "test_negative_rows": str(len(y) - sum(y)),
                        "average_precision": average_precision(y, scores),
                        "roc_auc": roc_auc(y, scores),
                        "balanced_accuracy_at_train_prevalence": balanced_accuracy(y, scores, prevalence),
                        "brier_score": brier_score(y, scores),
                        "train_prevalence": f"{prevalence:.6f}",
                        "notes": note,
                    }
                )
                for test_row, label, score, detail in zip(test, y, scores, support_details):
                    prediction_rows.append(
                        {
                            "interaction_id": test_row.get("interaction_id", ""),
                            "phage_id": test_row.get("phage_id", ""),
                            "host_id": test_row.get("host_id", ""),
                            "study_id": test_row.get("study_id", ""),
                            "panel_id": test_row.get("panel_id", ""),
                            "split_strategy": split,
                            "fold": str(fold_idx),
                            "held_out_group": group_key(test_row, split),
                            "true_label": str(label),
                            "predicted_score": f"{score:.8f}",
                            "model_id": model_name,
                            "baseline_id": "global_prevalence",
                            "support_state": detail.get("support_state", ""),
                            "training_support_rows": detail.get("training_support_rows", ""),
                            "intermediate_support_rows": detail.get("intermediate_support_rows", ""),
                            "nearest_phage_count": detail.get("nearest_phage_count", ""),
                            "used_global_prevalence": detail.get("used_global_prevalence", ""),
                            "claim_boundary": "Out-of-fold prediction for spot-test initial interaction only; not productive infection.",
                        }
                    )
    summary: list[dict[str, str]] = []
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in out_rows:
        grouped[(row["split_strategy"], row["model_name"])].append(row)
    for (split, model_name), model_rows in sorted(grouped.items()):
        summary.append(
            {
                "hypothesis": "H1_spot_interaction_receptor_layer",
                "split_strategy": split,
                "model_name": model_name,
                "folds_evaluated": str(len(model_rows)),
                "mean_average_precision": mean_metric(model_rows, "average_precision"),
                "mean_roc_auc": mean_metric(model_rows, "roc_auc"),
                "mean_balanced_accuracy_at_train_prevalence": mean_metric(model_rows, "balanced_accuracy_at_train_prevalence"),
                "mean_brier_score": mean_metric(model_rows, "brier_score"),
                "interpretation": "Exploratory grouped rate-baseline comparison for H1 using spot-test outcomes only.",
            }
        )
    pooled_summary = build_pooled_summary(prediction_rows)
    ablation_summary = build_ablation_summary(pooled_summary)
    group_bootstrap_summary = build_group_bootstrap_summary(
        prediction_rows,
        ablation_summary,
        args.group_bootstrap_iterations,
        args.seed,
    )
    delta_summary = build_delta_summary(out_rows, args.bootstrap_iterations, args.seed)
    readiness = [
        {
            "readiness_item": "H1_receptor_layer_model_comparison",
            "status": "quantitative_test_available_claim_not_final",
            "evidence": f"{len(out_rows)} fold-level model rows and {len(prediction_rows)} out-of-fold prediction rows across {len(split_strategies)} grouped split strategies and {len(model_names)} model families; {len(ablation_summary)} receptor-source ablation rows; {len(group_bootstrap_summary)} held-out-group bootstrap contrast rows; {len(delta_summary)} fold-level delta rows compare models against global prevalence.",
            "next_action": "Add independent validation, leakage checks, and VIRIDIC/Mash-style manuscript-grade phage taxonomy/similarity baselines before strengthening H1 claims.",
            "claim_boundary": "No final claim that receptor features outperform taxonomy from this exploratory baseline alone.",
        },
        {
            "readiness_item": "H4_defense_counterdefense",
            "status": "blocked_no_productive_infection_labels_no_defense_features",
            "evidence": "Model comparison uses spot-test outcomes and receptor-layer features only.",
            "next_action": "Keep H4 blocked until accepted defense/counter-defense evidence and suitable outcome labels exist.",
            "claim_boundary": "No defense/counter-defense claim.",
        },
    ]
    write_tsv(Path(args.model_output), MODEL_COLUMNS, out_rows)
    write_tsv(Path(args.summary_output), SUMMARY_COLUMNS, summary)
    write_tsv(Path(args.prediction_output), PREDICTION_COLUMNS, prediction_rows)
    write_tsv(Path(args.pooled_summary_output), POOLED_COLUMNS, pooled_summary)
    write_tsv(Path(args.support_diagnostics_output), SUPPORT_DIAGNOSTIC_COLUMNS, support_diagnostic_rows)
    write_tsv(Path(args.ablation_output), ABLATION_COLUMNS, ablation_summary)
    write_tsv(Path(args.group_bootstrap_output), GROUP_BOOTSTRAP_COLUMNS, group_bootstrap_summary)
    write_tsv(Path(args.delta_output), DELTA_COLUMNS, delta_summary)
    write_tsv(Path(args.readiness_output), READINESS_COLUMNS, readiness)
    build_report(Path(args.report_output), summary, pooled_summary, ablation_summary, group_bootstrap_summary, delta_summary, support_diagnostic_rows, args)
    print(f"Receptor-layer model comparison rows: {len(out_rows)}")
    print(f"Receptor-layer out-of-fold prediction rows: {len(prediction_rows)}")
    print(f"Receptor-layer pooled summary rows: {len(pooled_summary)}")
    print(f"Receptor-layer support diagnostic rows: {len(support_diagnostic_rows)}")
    print(f"Receptor-layer source ablation rows: {len(ablation_summary)}")
    print(f"Receptor-layer group bootstrap rows: {len(group_bootstrap_summary)}")
    print(f"Receptor-layer delta summary rows: {len(delta_summary)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
