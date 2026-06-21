#!/usr/bin/env python3
"""Compare feature sets for receptor and defense/counter-defense hypotheses."""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


MODEL_COMPARISON_COLUMNS = [
    "analysis_id",
    "hypothesis",
    "task",
    "target",
    "feature_set",
    "model_type",
    "n_samples",
    "n_classes",
    "n_features",
    "coverage",
    "accuracy",
    "macro_f1",
    "baseline_accuracy",
    "delta_vs_baseline",
    "status",
    "notes",
]

FEATURE_IMPORTANCE_COLUMNS = [
    "analysis_id",
    "hypothesis",
    "task",
    "feature_set",
    "feature",
    "non_missing_count",
    "unique_value_count",
    "full_accuracy",
    "accuracy_without_feature",
    "delta_accuracy",
    "association_metric",
    "association_value",
    "notes",
]

PREDICTION_ERROR_COLUMNS = [
    "analysis_id",
    "task",
    "target",
    "feature_set",
    "sample_id",
    "phage_genome_id",
    "host_genome_id",
    "true_label",
    "predicted_label",
    "matched_training_count",
    "used_fallback",
    "correct",
    "features_used",
    "status",
]

ASSAY_FEATURE_COVERAGE_COLUMNS = [
    "metric",
    "entity_level",
    "numerator",
    "denominator",
    "coverage_fraction",
    "evidence_state",
    "blocking_hypotheses",
    "next_action",
    "study_id",
    "panel_id",
    "phage_id",
    "host_id",
    "tested_host_count",
    "spot_positive_host_count",
    "spot_positive_fraction",
    "spot_positive_fraction_ci95_low",
    "spot_positive_fraction_ci95_high",
]


HYPOTHESIS_SUMMARY_COLUMNS = [
    "hypothesis",
    "primary_question",
    "required_test",
    "evidence_path",
    "matching_model_rows",
    "ok_model_rows",
    "limited_model_rows",
    "max_n_samples",
    "primary_analysis_id",
    "primary_task",
    "primary_target",
    "primary_feature_set",
    "comparison_feature_set",
    "primary_metric",
    "primary_metric_value",
    "baseline_metric_value",
    "effect_size",
    "summary_status",
    "claim_status",
    "interpretation_guardrail",
    "next_action",
]

REPORT_COLUMNS = ["severity", "item", "message"]

MISSING_VALUES = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
NON_INFORMATIVE_FEATURE_VALUES = MISSING_VALUES | {"not_assessed", "evidence_rejected"}
PRODUCTIVE_INFECTION_OBSERVED_VALUES = {"positive", "negative", "inconclusive", "equivocal"}

K_O_FEATURE_SETS = {
    "taxonomy_only": ["species_cluster_id"],
    "whole_genome_similarity": ["species_cluster_id", "representative_id"],
    "rbp_depolymerase_modules": ["rbp_module_clusters", "rbp_enzyme_classes", "rbp_candidate_count_bin"],
    "taxonomy_plus_rbp": ["species_cluster_id", "rbp_module_clusters", "rbp_enzyme_classes"],
}


COMPATIBILITY_FEATURE_SETS = {
    "receptor_only": ["K_type", "O_type", "ST"],
    "host_defense": ["host_defense_system_count_bin", "host_defense_types"],
    "phage_counterdefense": ["phage_antidefense_count_bin", "phage_antidefense_targets"],
    "defense_counterdefense": ["host_defense_types", "phage_antidefense_targets", "matched_counterdefense_count_bin"],
    "receptor_plus_defense_counterdefense": ["K_type", "O_type", "ST", "host_defense_types", "phage_antidefense_targets", "matched_counterdefense_count_bin"],
    "taxonomy_plus_receptor_defense_counterdefense": ["species_cluster_id", "K_type", "O_type", "ST", "host_defense_types", "phage_antidefense_targets", "matched_counterdefense_count_bin"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare interpretable feature-set baselines for K/O prediction and "
            "receptor plus defense/counter-defense compatibility features."
        )
    )
    parser.add_argument("--manifest", required=True, help="Stage 1 phage_genome_manifest.tsv.")
    parser.add_argument("--clusters", required=True, help="Stage 2 phage_clusters.tsv.")
    parser.add_argument("--rbp-candidates", required=True, help="Stage 4 candidates.tsv.")
    parser.add_argument("--phage-host-links", required=True, help="Stage 5 phage_host_links.tsv.")
    parser.add_argument("--compatibility-features", required=True, help="Stage 6 compatibility_features.tsv.")
    parser.add_argument("--phage-host-assays", default="", help="Optional canonical phage_host_assays.tsv for assay-derived breadth/outcome tests.")
    parser.add_argument("--sequence-qc", default="", help="Optional genome_sequence_qc.tsv for assay feature-coverage auditing.")
    parser.add_argument("--annotations", default="", help="Optional phage_annotations.tsv for assay feature-coverage auditing.")
    parser.add_argument("--domain-architectures", default="", help="Optional RBP domain_architectures.tsv for assay feature-coverage auditing.")
    parser.add_argument("--phage-module-identities", default="", help="Optional assay_phage_module_identity_signatures.tsv for H3 module-count association.")
    parser.add_argument("--host-metadata", default="", help="Optional host_metadata.tsv for assay feature-coverage auditing.")
    parser.add_argument("--host-defense", default="", help="Optional host_defense_systems.tsv for assay feature-coverage auditing.")
    parser.add_argument("--phage-antidefense", default="", help="Optional phage_antidefense_candidates.tsv for assay feature-coverage auditing.")
    parser.add_argument("--phage-receptor-support", default="", help="Optional phage bridge-metadata TSV, e.g. normalized RBPbase.")
    parser.add_argument("--host-receptor-support", default="", help="Optional host locus bridge-metadata TSV, e.g. normalized Locibase.")
    parser.add_argument("--h3-min-assessed-phages", type=int, default=20, help="Minimum independent phages with assessed H3 feature evidence before association testing is analysis-ready.")
    parser.add_argument("--h3-min-feature-groups", type=int, default=2, help="Minimum assessed feature groups required before H3 association testing is analysis-ready.")
    parser.add_argument("--h3-min-group-size", type=int, default=5, help="Minimum phages per assessed H3 feature group before association testing is analysis-ready.")
    parser.add_argument("--assay-feature-coverage-output", default="", help="Output assay feature-coverage audit TSV. Defaults to results/qc next to model outputs.")
    parser.add_argument("--model-comparison-output", required=True, help="Output model comparison TSV.")
    parser.add_argument("--feature-importance-output", required=True, help="Output feature importance TSV.")
    parser.add_argument("--prediction-errors-output", required=True, help="Output prediction/error TSV.")
    parser.add_argument("--hypothesis-summary-output", required=True, help="Output H1-H6 hypothesis evidence summary TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING_VALUES


def is_informative_feature_value(value: str | None) -> bool:
    return value is not None and value.strip() not in NON_INFORMATIVE_FEATURE_VALUES


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


def read_optional_tsv(path_value: str) -> tuple[list[str], list[dict[str, str]]]:
    if not path_value or not Path(path_value).exists():
        return [], []
    return read_tsv(Path(path_value))


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


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def split_values(value: str) -> list[str]:
    if is_missing(value):
        return []
    return sorted({item.strip() for item in value.replace(",", ";").split(";") if item.strip()})


def joined(values: Iterable[str]) -> str:
    cleaned = sorted({value for value in values if not is_missing(value)})
    return ";".join(cleaned)


def parse_int(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def parse_float_or_none(value: str) -> float | None:
    if is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mean_or_none(values: Iterable[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


def format_float(value: float | None) -> str:
    return "" if value is None else f"{value:.3f}"


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    phat = successes / total
    denom = 1 + z * z / total
    centre = phat + z * z / (2 * total)
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * total)) / total)
    return (centre - margin) / denom, (centre + margin) / denom


def count_bin(value: int) -> str:
    if value <= 0:
        return "0"
    if value == 1:
        return "1"
    return "2plus"


def safe_value(value: str | None) -> str:
    return "NA" if is_missing(value) else value.strip()


def majority_label(labels: list[str]) -> str:
    if not labels:
        return ""
    counts = Counter(labels)
    max_count = max(counts.values())
    winners = sorted(label for label, count in counts.items() if count == max_count)
    return winners[0]


def macro_f1(true_labels: list[str], predicted_labels: list[str]) -> float:
    labels = sorted(set(true_labels) | set(predicted_labels))
    if not labels:
        return 0.0
    scores = []
    for label in labels:
        tp = sum(1 for truth, pred in zip(true_labels, predicted_labels) if truth == label and pred == label)
        fp = sum(1 for truth, pred in zip(true_labels, predicted_labels) if truth != label and pred == label)
        fn = sum(1 for truth, pred in zip(true_labels, predicted_labels) if truth == label and pred != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        scores.append(f1)
    return sum(scores) / len(scores)


def feature_key(sample: dict[str, str], features: list[str]) -> tuple[str, ...]:
    return tuple(safe_value(sample.get(feature, "")) for feature in features)


def has_any_feature_value(sample: dict[str, str], features: list[str]) -> bool:
    return any(is_informative_feature_value(sample.get(feature, "")) for feature in features)


def leave_one_out(samples: list[dict[str, str]], target: str, features: list[str]) -> dict[str, object]:
    eligible = [sample for sample in samples if not is_missing(sample.get(target))]
    labels = [sample[target] for sample in eligible]
    predictions = []
    baseline_predictions = []

    for index, sample in enumerate(eligible):
        train = eligible[:index] + eligible[index + 1:]
        train_labels = [row[target] for row in train]
        fallback = majority_label(train_labels) or majority_label(labels)
        key = feature_key(sample, features)
        matched = [row for row in train if feature_key(row, features) == key]
        if matched:
            prediction = majority_label([row[target] for row in matched])
            used_fallback = False
        else:
            prediction = fallback
            used_fallback = True
        baseline = fallback
        predictions.append(
            {
                "sample": sample,
                "true_label": sample[target],
                "predicted_label": prediction,
                "baseline_label": baseline,
                "matched_training_count": len(matched),
                "used_fallback": used_fallback,
                "correct": prediction == sample[target],
                "baseline_correct": baseline == sample[target],
            }
        )
        baseline_predictions.append(baseline)

    pred_labels = [row["predicted_label"] for row in predictions]
    accuracy = sum(1 for row in predictions if row["correct"]) / len(predictions) if predictions else 0.0
    baseline_accuracy = sum(1 for row in predictions if row["baseline_correct"]) / len(predictions) if predictions else 0.0
    coverage = sum(1 for row in predictions if not row["used_fallback"]) / len(predictions) if predictions else 0.0
    status = "ok"
    if not eligible:
        status = "no_labeled_samples"
    elif len(set(labels)) < 2:
        status = "single_class_uninformative"
    elif len(eligible) < 3:
        status = "too_few_samples_interpret_with_caution"

    return {
        "eligible": eligible,
        "predictions": predictions,
        "n_samples": len(eligible),
        "n_classes": len(set(labels)),
        "accuracy": accuracy,
        "baseline_accuracy": baseline_accuracy,
        "coverage": coverage,
        "macro_f1": macro_f1(labels, pred_labels) if predictions else 0.0,
        "status": status,
    }



def load_manifest(path: Path) -> dict[str, dict[str, str]]:
    _, rows = read_tsv(path)
    return {row.get("genome_id", ""): row for row in rows if not is_missing(row.get("genome_id"))}


def load_clusters(path: Path) -> dict[str, dict[str, str]]:
    _, rows = read_tsv(path)
    return {row.get("genome_id", ""): row for row in rows if not is_missing(row.get("genome_id"))}


def rbp_features_by_phage(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if not is_missing(row.get("genome_id")):
            grouped[row["genome_id"]].append(row)

    features: dict[str, dict[str, str]] = {}
    for phage_id, phage_rows in grouped.items():
        modules = joined(row.get("module_cluster_id", "") for row in phage_rows)
        classes = joined(row.get("predicted_enzyme_class", "") for row in phage_rows)
        novelty = joined(row.get("novelty_tier", "") for row in phage_rows)
        high_conf = sum(1 for row in phage_rows if row.get("is_high_confidence") == "true")
        features[phage_id] = {
            "rbp_module_clusters": modules,
            "rbp_enzyme_classes": classes,
            "rbp_novelty_tiers": novelty,
            "rbp_candidate_count": str(len(phage_rows)),
            "rbp_candidate_count_bin": count_bin(len(phage_rows)),
            "rbp_candidate_evidence_state": "assessed_positive",
            "rbp_high_confidence_count": str(high_conf),
            "rbp_high_confidence_count_bin": count_bin(high_conf),
        }
    return features


def compatibility_by_pair(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(row.get("phage_genome_id", ""), row.get("host_genome_id", "")): row for row in rows}


def phage_counterdefense_by_phage(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        phage_id = row.get("phage_genome_id", "")
        if not is_missing(phage_id):
            grouped[phage_id].append(row)
    features: dict[str, dict[str, str]] = {}
    for phage_id, phage_rows in grouped.items():
        anti_count = max([parse_int(row.get("phage_antidefense_count", "0")) for row in phage_rows] + [0])
        assessed = any(row.get("counterdefense_metadata_available", "").lower() == "true" for row in phage_rows)
        state = "assessed_positive" if anti_count > 0 else ("assessed_zero_detected" if assessed else "not_assessed")
        features[phage_id] = {
            "phage_antidefense_count_bin": count_bin(anti_count) if state != "not_assessed" else "not_assessed",
            "phage_antidefense_evidence_state": state,
            "phage_antidefense_targets": joined(row.get("phage_antidefense_targets", "") for row in phage_rows),
            "phage_antidefense_classes": joined(row.get("phage_antidefense_classes", "") for row in phage_rows),
        }
    return features


def phage_module_identities_by_phage(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    features: dict[str, dict[str, str]] = {}
    for row in rows:
        phage_id = row.get("phage_id", "") or row.get("phage_genome_id", "")
        if is_missing(phage_id):
            continue
        domain_count = parse_int(row.get("rbp_domain_module_count", "0"))
        structural_count = parse_int(row.get("rbp_structural_module_count", "0"))
        state = row.get("rbp_module_identity_state", "")
        if is_missing(state):
            state = "assessed_positive" if domain_count + structural_count > 0 else "assessed_zero_detected"
        features[phage_id] = {
            "rbp_domain_module_count": str(domain_count),
            "rbp_structural_module_count": str(structural_count),
            "rbp_total_module_count": str(domain_count + structural_count),
            "rbp_module_identity_state": state,
        }
    return features


def phage_antidefense_candidates_by_phage(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        phage_id = row.get("phage_genome_id", "")
        if not is_missing(phage_id):
            grouped[phage_id].append(row)
    return {
        phage_id: {
            "phage_antidefense_candidate_count": str(len(phage_rows)),
            "phage_antidefense_candidate_state": "assessed_positive",
        }
        for phage_id, phage_rows in grouped.items()
    }


def phage_receptor_support_by_phage(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    features: dict[str, dict[str, str]] = {}
    for row in rows:
        phage_id = row.get("phage_genome_id", "")
        if is_missing(phage_id):
            continue
        features[phage_id] = {
            "phage_receptor_support_status": row.get("receptor_support_status", ""),
            "phage_receptor_support_count_bin": row.get("protein_count_bin", "not_assessed"),
            "phage_receptor_support_score_bin": row.get("max_xgb_score_bin", "not_assessed"),
        }
    return features


def host_receptor_support_by_host(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    features: dict[str, dict[str, str]] = {}
    for row in rows:
        host_id = row.get("host_genome_id", "")
        if is_missing(host_id):
            continue
        features[host_id] = {
            "host_receptor_support_status": row.get("receptor_support_status", ""),
            "host_locus_fingerprint_sha256": row.get("locus_fingerprint_sha256", ""),
            "host_locus_protein_count_bin": row.get("locus_protein_count_bin", "not_assessed"),
        }
    return features


def spot_breadth_primary_label(tested_count: int) -> str:
    if tested_count <= 0:
        return "no_tested_hosts"
    return "continuous_primary_not_binned"


def build_assay_breadth_samples(
    assay_rows: list[dict[str, str]],
    manifest: dict[str, dict[str, str]],
    clusters: dict[str, dict[str, str]],
    rbp_features: dict[str, dict[str, str]],
    phage_counterdefense: dict[str, dict[str, str]],
    phage_module_identities: dict[str, dict[str, str]],
    phage_antidefense_candidates: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str, str], Counter[str]] = defaultdict(Counter)
    for row in assay_rows:
        if row.get("tested") != "true":
            continue
        if row.get("assay_type") != "spot":
            continue
        result = row.get("spot_result", "")
        if result not in {"positive", "negative"}:
            continue
        phage_id = row.get("phage_id", "")
        if is_missing(phage_id):
            continue
        key = (phage_id, row.get("study_id", "NA"), row.get("panel_id", "NA"), row.get("assay_type", "spot"))
        grouped[key][result] += 1

    samples: list[dict[str, str]] = []
    for (phage_id, study_id, panel_id, assay_type), counts in sorted(grouped.items()):
        tested_count = counts.get("positive", 0) + counts.get("negative", 0)
        positive_count = counts.get("positive", 0)
        cluster = clusters.get(phage_id, {})
        manifest_row = manifest.get(phage_id, {})
        rbp = rbp_features.get(phage_id, {})
        counterdefense = phage_counterdefense.get(phage_id, {})
        module_identity = phage_module_identities.get(phage_id, {})
        antidefense_candidates = phage_antidefense_candidates.get(phage_id, {})
        fraction = positive_count / tested_count if tested_count else 0.0
        ci_low, ci_high = wilson_interval(positive_count, tested_count)
        samples.append(
            {
                "sample_id": f"{phage_id}|{study_id}|{panel_id}|{assay_type}",
                "phage_genome_id": phage_id,
                "host_genome_id": "assay_panel",
                "record_type": manifest_row.get("record_type", "phage"),
                "species_cluster_id": cluster.get("cluster_id", ""),
                "representative_id": cluster.get("representative_id", ""),
                "source": manifest_row.get("source", ""),
                "source_group": source_group(manifest_row),
                "species_cluster_size_bin": cluster_size_bin(cluster),
                "study_id": study_id,
                "panel_id": panel_id,
                "assay_type": assay_type,
                "rbp_module_clusters": rbp.get("rbp_module_clusters", ""),
                "rbp_enzyme_classes": rbp.get("rbp_enzyme_classes", ""),
                "rbp_novelty_tiers": rbp.get("rbp_novelty_tiers", ""),
                "rbp_candidate_count_bin": rbp.get("rbp_candidate_count_bin", "not_assessed"),
                "rbp_candidate_evidence_state": rbp.get("rbp_candidate_evidence_state", "not_assessed"),
                "rbp_high_confidence_count_bin": rbp.get("rbp_high_confidence_count_bin", "not_assessed"),
                "novel_rbp_status": novelty_status(rbp),
                "phage_antidefense_classes": counterdefense.get("phage_antidefense_classes", ""),
                "phage_antidefense_targets": counterdefense.get("phage_antidefense_targets", ""),
                "phage_antidefense_count_bin": counterdefense.get("phage_antidefense_count_bin", "not_assessed"),
                "phage_antidefense_evidence_state": counterdefense.get("phage_antidefense_evidence_state", "not_assessed"),
                "rbp_domain_module_count": module_identity.get("rbp_domain_module_count", ""),
                "rbp_structural_module_count": module_identity.get("rbp_structural_module_count", ""),
                "rbp_total_module_count": module_identity.get("rbp_total_module_count", ""),
                "rbp_module_identity_state": module_identity.get("rbp_module_identity_state", "not_assessed"),
                "phage_antidefense_candidate_count": antidefense_candidates.get("phage_antidefense_candidate_count", ""),
                "phage_antidefense_candidate_state": antidefense_candidates.get("phage_antidefense_candidate_state", "not_assessed"),
                "spot_tested_host_count": str(tested_count),
                "tested_host_count": str(tested_count),
                "spot_positive_host_count": str(positive_count),
                "spot_host_range_fraction": f"{fraction:.3f}",
                "spot_positive_fraction": f"{fraction:.3f}",
                "spot_positive_fraction_ci95_low": format_float(ci_low),
                "spot_positive_fraction_ci95_high": format_float(ci_high),
                "spot_host_range_breadth_bin": spot_breadth_primary_label(tested_count),
            }
        )
    return samples


def novelty_status(rbp: dict[str, str]) -> str:
    if rbp.get("rbp_candidate_evidence_state", "not_assessed") == "not_assessed":
        return "not_assessed"
    tiers = set(split_values(rbp.get("rbp_novelty_tiers", "")))
    candidate_count = parse_int(rbp.get("rbp_candidate_count", "0"))
    if tiers & {"tier_1", "tier_2"}:
        return "tier_1_or_2_rbp_candidate"
    if "tier_3" in tiers:
        return "known_family_rbp_candidate"
    if candidate_count > 0:
        return "candidate_without_novelty_evidence"
    return "assessed_zero_detected"


def source_group(row: dict[str, str]) -> str:
    source = safe_value(row.get("source", ""))
    if source == "NA":
        return "unknown_source"
    return source.lower().replace(" ", "_")


def cluster_size_bin(cluster: dict[str, str]) -> str:
    size = parse_int(cluster.get("cluster_size", "0"))
    if size <= 0:
        return "unknown_cluster_size"
    if size == 1:
        return "singleton_species_like_cluster"
    return "multi_genome_species_like_cluster"


def build_samples(
    links: list[dict[str, str]],
    manifest: dict[str, dict[str, str]],
    clusters: dict[str, dict[str, str]],
    rbp_features: dict[str, dict[str, str]],
    compatibility: dict[tuple[str, str], dict[str, str]],
) -> list[dict[str, str]]:
    samples = []
    for link in links:
        phage_id = link.get("phage_genome_id", "")
        host_id = link.get("host_genome_id", "")
        cluster = clusters.get(phage_id, {})
        manifest_row = manifest.get(phage_id, {})
        rbp = rbp_features.get(phage_id, {})
        compat = compatibility.get((phage_id, host_id), {})
        matched_counterdefense_count = parse_int(compat.get("matched_counterdefense_count", "0"))
        host_defense_count = parse_int(compat.get("host_defense_system_count", "0"))
        anti_count = parse_int(compat.get("phage_antidefense_count", "0"))
        host_defense_state = "assessed_positive" if host_defense_count > 0 else ("assessed_zero_detected" if compat.get("defense_metadata_available", "").lower() == "true" else "not_assessed")
        antidefense_state = "assessed_positive" if anti_count > 0 else ("assessed_zero_detected" if compat.get("counterdefense_metadata_available", "").lower() == "true" else "not_assessed")
        matched_state = "assessed_positive" if matched_counterdefense_count > 0 else ("assessed_zero_detected" if host_defense_state != "not_assessed" and antidefense_state != "not_assessed" else "not_assessed")
        sample = {
            "sample_id": f"{phage_id}|{host_id}",
            "phage_genome_id": phage_id,
            "host_genome_id": host_id,
            "record_type": link.get("record_type", ""),
            "species_cluster_id": link.get("species_cluster_id", "") or cluster.get("cluster_id", ""),
            "representative_id": link.get("representative_id", "") or cluster.get("representative_id", ""),
            "K_type": link.get("K_type", ""),
            "O_type": link.get("O_type", ""),
            "ST": link.get("ST", ""),
            "host_link_status": link.get("host_link_status", ""),
            "source": manifest_row.get("source", ""),
            "source_group": source_group(manifest_row),
            "country": manifest_row.get("country", ""),
            "year": manifest_row.get("year", ""),
            "phage_lifestyle": manifest_row.get("phage_lifestyle", ""),
            "species_cluster_size_bin": cluster_size_bin(cluster),
            "rbp_module_clusters": rbp.get("rbp_module_clusters", ""),
            "rbp_enzyme_classes": rbp.get("rbp_enzyme_classes", ""),
            "rbp_novelty_tiers": rbp.get("rbp_novelty_tiers", ""),
            "rbp_candidate_count_bin": rbp.get("rbp_candidate_count_bin", "not_assessed"),
            "rbp_high_confidence_count_bin": rbp.get("rbp_high_confidence_count_bin", "not_assessed"),
            "novel_rbp_status": novelty_status(rbp),
            "host_defense_types": compat.get("host_defense_types", ""),
            "host_defense_systems": compat.get("host_defense_systems", ""),
            "host_defense_system_count_bin": count_bin(host_defense_count) if host_defense_state != "not_assessed" else "not_assessed",
            "host_defense_evidence_state": host_defense_state,
            "phage_antidefense_classes": compat.get("phage_antidefense_classes", ""),
            "phage_antidefense_targets": compat.get("phage_antidefense_targets", ""),
            "phage_antidefense_count_bin": count_bin(anti_count) if antidefense_state != "not_assessed" else "not_assessed",
            "phage_antidefense_evidence_state": antidefense_state,
            "matched_counterdefense_count_bin": count_bin(matched_counterdefense_count) if matched_state != "not_assessed" else "not_assessed",
            "matched_counterdefense_evidence_state": matched_state,
            "compatibility_feature_status": compat.get("compatibility_feature_status", ""),
            "matched_counterdefense_status": "matched_counterdefense" if matched_counterdefense_count > 0 else matched_state,
        }
        samples.append(sample)
    return samples


def feature_summary(samples: list[dict[str, str]], feature: str) -> tuple[int, int]:
    values = [safe_value(sample.get(feature, "")) for sample in samples if is_informative_feature_value(sample.get(feature, ""))]
    return len(values), len(set(values))


def add_model_results(
    rows: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
    error_rows: list[dict[str, str]],
    analysis_id: str,
    hypothesis: str,
    task: str,
    target: str,
    feature_set: str,
    features: list[str],
    samples: list[dict[str, str]],
) -> None:
    result = leave_one_out(samples, target, features)
    accuracy = float(result["accuracy"])
    baseline = float(result["baseline_accuracy"])
    rows.append(
        {
            "analysis_id": analysis_id,
            "hypothesis": hypothesis,
            "task": task,
            "target": target,
            "feature_set": feature_set,
            "model_type": "leave_one_out_exact_match_majority_baseline",
            "n_samples": str(result["n_samples"]),
            "n_classes": str(result["n_classes"]),
            "n_features": str(len(features)),
            "coverage": f"{float(result['coverage']):.3f}",
            "accuracy": f"{accuracy:.3f}",
            "macro_f1": f"{float(result['macro_f1']):.3f}",
            "baseline_accuracy": f"{baseline:.3f}",
            "delta_vs_baseline": f"{accuracy - baseline:.3f}",
            "status": str(result["status"]),
            "notes": "Exact-match categorical baseline; use as a transparent scaffold until experimental labels and larger data are available.",
        }
    )

    for prediction in result["predictions"]:  # type: ignore[index]
        sample = prediction["sample"]
        error_rows.append(
            {
                "analysis_id": analysis_id,
                "task": task,
                "target": target,
                "feature_set": feature_set,
                "sample_id": sample.get("sample_id", ""),
                "phage_genome_id": sample.get("phage_genome_id", ""),
                "host_genome_id": sample.get("host_genome_id", ""),
                "true_label": prediction["true_label"],
                "predicted_label": prediction["predicted_label"],
                "matched_training_count": str(prediction["matched_training_count"]),
                "used_fallback": str(prediction["used_fallback"]).lower(),
                "correct": str(prediction["correct"]).lower(),
                "features_used": ";".join(f"{feature}={safe_value(sample.get(feature, ''))}" for feature in features),
                "status": str(result["status"]),
            }
        )

    for feature in features:
        without = [item for item in features if item != feature]
        if without:
            without_result = leave_one_out(samples, target, without)
            without_accuracy = float(without_result["accuracy"])
        else:
            without_accuracy = baseline
        non_missing, unique_count = feature_summary(samples, feature)
        feature_rows.append(
            {
                "analysis_id": analysis_id,
                "hypothesis": hypothesis,
                "task": task,
                "feature_set": feature_set,
                "feature": feature,
                "non_missing_count": str(non_missing),
                "unique_value_count": str(unique_count),
                "full_accuracy": f"{accuracy:.3f}",
                "accuracy_without_feature": f"{without_accuracy:.3f}",
                "delta_accuracy": f"{accuracy - without_accuracy:.3f}",
                "association_metric": "leave_one_feature_out_delta_accuracy",
                "association_value": f"{accuracy - without_accuracy:.3f}",
                "notes": "Feature contribution is unstable for small or single-class datasets.",
            }
        )



def add_blocked_test(
    rows: list[dict[str, str]],
    hypothesis: str,
    analysis_id: str,
    task: str,
    target: str,
    feature_set: str,
    model_type: str,
    n_samples: int,
    status: str,
    notes: str,
) -> None:
    rows.append(
        {
            "analysis_id": analysis_id,
            "hypothesis": hypothesis,
            "task": task,
            "target": target,
            "feature_set": feature_set,
            "model_type": model_type,
            "n_samples": str(n_samples),
            "n_classes": "0",
            "n_features": "0",
            "coverage": "0.000",
            "accuracy": "",
            "macro_f1": "",
            "baseline_accuracy": "",
            "delta_vs_baseline": "",
            "status": status,
            "notes": notes,
        }
    )


def add_rate_test(
    rows: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
    samples: list[dict[str, str]],
    hypothesis: str,
    analysis_id: str,
    task: str,
    group_feature: str,
    outcome_feature: str,
) -> None:
    groups: dict[str, list[str]] = defaultdict(list)
    for sample in samples:
        group = safe_value(sample.get(group_feature, ""))
        outcome = sample.get(outcome_feature, "")
        if is_missing(outcome):
            continue
        groups[group].append(outcome)
    n_samples = sum(len(values) for values in groups.values())
    n_classes = len({value for values in groups.values() for value in values})
    status = "ok" if n_samples >= 3 and n_classes >= 2 and len(groups) >= 2 else "insufficient_groups_for_rate_test"
    rows.append(
        {
            "analysis_id": analysis_id,
            "hypothesis": hypothesis,
            "task": task,
            "target": outcome_feature,
            "feature_set": group_feature,
            "model_type": "group_rate_summary",
            "n_samples": str(n_samples),
            "n_classes": str(n_classes),
            "n_features": "1",
            "coverage": "1.000" if n_samples else "0.000",
            "accuracy": "",
            "macro_f1": "",
            "baseline_accuracy": "",
            "delta_vs_baseline": "",
            "status": status,
            "notes": "Quantitative group summary for hypothesis tracking; not a predictive classifier.",
        }
    )
    for group, values in sorted(groups.items()):
        counts = Counter(values)
        total = sum(counts.values())
        top_label, top_count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
        feature_rows.append(
            {
                "analysis_id": analysis_id,
                "hypothesis": hypothesis,
                "task": task,
                "feature_set": group_feature,
                "feature": group,
                "non_missing_count": str(total),
                "unique_value_count": str(len(counts)),
                "full_accuracy": "",
                "accuracy_without_feature": "",
                "delta_accuracy": "",
                "association_metric": "top_group_label_fraction",
                "association_value": f"{top_count / total:.3f}" if total else "0.000",
                "notes": f"Top {outcome_feature}={top_label}; counts=" + ";".join(f"{label}:{count}" for label, count in sorted(counts.items())),
            }
        )


def add_h2_prophage_annotation_coverage(
    rows: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
    annotation_rows: list[dict[str, str]],
    rbp_rows: list[dict[str, str]],
) -> None:
    annotated_prophages = {
        row.get("genome_id", "")
        for row in annotation_rows
        if row.get("record_type", "") == "prophage" and not is_missing(row.get("genome_id"))
    }
    candidate_prophages = {
        row.get("genome_id", "")
        for row in rbp_rows
        if row.get("record_type", "") == "prophage" and not is_missing(row.get("genome_id"))
    }
    assessed_count = len(annotated_prophages)
    detected_count = len(annotated_prophages & candidate_prophages)
    prophage_states = {"detected" if genome in candidate_prophages else "zero_detected" for genome in annotated_prophages}
    if assessed_count == 0:
        status = "blocked_no_prophage_annotations"
    elif detected_count == 0:
        status = "prophage_annotations_assessed_zero_rbp_candidates"
    elif assessed_count < 3:
        status = "blocked_insufficient_prophage_cohort"
    else:
        status = "analysis_ready"
    coverage = detected_count / assessed_count if assessed_count else 0.0
    rows.append(
        {
            "analysis_id": "prophage_annotation_rbp_candidate_coverage",
            "hypothesis": "H2",
            "task": "prophage_rbp_module_reservoir_coverage",
            "target": "prophage_rbp_candidate_status",
            "feature_set": "record_type",
            "model_type": "annotation_candidate_coverage_audit",
            "n_samples": str(assessed_count),
            "n_classes": str(len(prophage_states)),
            "n_features": "1",
            "coverage": f"{coverage:.3f}" if assessed_count else "0.000",
            "accuracy": "",
            "macro_f1": "",
            "baseline_accuracy": "",
            "delta_vs_baseline": "",
            "status": status,
            "notes": (
                f"annotated_prophages={assessed_count}; prophages_with_rbp_candidates={detected_count}; "
                "GenBank prophage CDS rows are bridge annotation only, not standardized Pharokka/PHROGs/domain/structural evidence."
            ),
        }
    )
    feature_rows.append(
        {
            "analysis_id": "prophage_annotation_rbp_candidate_coverage",
            "hypothesis": "H2",
            "task": "prophage_rbp_module_reservoir_coverage",
            "feature_set": "record_type",
            "feature": "prophage",
            "non_missing_count": str(assessed_count),
            "unique_value_count": str(len(prophage_states)),
            "full_accuracy": "",
            "accuracy_without_feature": "",
            "delta_accuracy": "",
            "association_metric": "prophage_rbp_candidate_fraction",
            "association_value": f"{coverage:.3f}" if assessed_count else "",
            "notes": (
                f"annotated_prophages={';'.join(sorted(annotated_prophages)) or 'none'}; "
                f"candidate_prophages={';'.join(sorted(candidate_prophages & annotated_prophages)) or 'none'}; "
                "assessed_zero_detected means no candidate was detected from current accepted/bridge annotation evidence, not biological absence."
            ),
        }
    )


def median_value(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def add_host_defense_burden_by_st(
    rows: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
    host_metadata_rows: list[dict[str, str]],
    host_defense_rows: list[dict[str, str]],
) -> None:
    defense_counts: Counter[str] = Counter()
    defense_types: dict[str, set[str]] = defaultdict(set)
    for row in host_defense_rows:
        host_id = row.get("host_genome_id", "")
        if is_missing(host_id):
            continue
        defense_counts[host_id] += 1
        defense_type = row.get("defense_type", "") or row.get("defense_system", "")
        if not is_missing(defense_type):
            defense_types[host_id].add(defense_type)

    benchmark_host_count = sum(
        1
        for row in host_metadata_rows
        if row.get("host_genome_id", "").startswith("phagehostlearn_2024_host_")
    )
    st_hosts = []
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in host_metadata_rows:
        host_id = row.get("host_genome_id", "")
        st = row.get("ST", "")
        if not host_id.startswith("phagehostlearn_2024_host_"):
            continue
        if is_missing(host_id) or is_missing(st):
            continue
        if host_id not in defense_counts:
            continue
        count = defense_counts[host_id]
        prepared = {
            "host_genome_id": host_id,
            "ST": st,
            "defense_count": str(count),
            "defense_type_count": str(len(defense_types.get(host_id, set()))),
        }
        st_hosts.append(prepared)
        grouped[st].append(prepared)

    n_samples = len(st_hosts)
    n_groups = len(grouped)
    groups_with_three = sum(1 for values in grouped.values() if len(values) >= 3)
    status = "ok" if n_samples >= 20 and n_groups >= 3 and groups_with_three >= 3 else "insufficient_groups_for_rate_test"
    counts = [parse_float_or_none(row["defense_count"]) for row in st_hosts]
    present = [value for value in counts if value is not None]
    overall_mean = mean_or_none(present)
    overall_median = median_value(present)
    rows.append(
        {
            "analysis_id": "st_vs_defense_burden_numeric",
            "hypothesis": "H5",
            "task": "host_background_defense_burden_summary",
            "target": "host_defense_system_count",
            "feature_set": "ST",
            "model_type": "numeric_group_summary",
            "n_samples": str(n_samples),
            "n_classes": str(len({row["defense_count"] for row in st_hosts})),
            "n_features": "1",
            "coverage": f"{n_samples / benchmark_host_count:.3f}" if benchmark_host_count else "0.000",
            "accuracy": "",
            "macro_f1": "",
            "baseline_accuracy": "",
            "delta_vs_baseline": "",
            "status": status,
            "notes": (
                "Association-only numeric ST versus DefenseFinder burden summary; "
                f"st_groups={n_groups}; groups_with_n_ge_3={groups_with_three}; "
                f"overall_mean={format_float(overall_mean)}; overall_median={format_float(overall_median)}."
            ),
        }
    )

    for st, values in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        defense_values = [parse_float_or_none(row["defense_count"]) for row in values]
        present_values = [value for value in defense_values if value is not None]
        mean_count = mean_or_none(present_values)
        median_count = median_value(present_values)
        min_count = min(present_values) if present_values else None
        max_count = max(present_values) if present_values else None
        type_counts = [parse_float_or_none(row["defense_type_count"]) for row in values]
        mean_type_count = mean_or_none(type_counts)
        feature_rows.append(
            {
                "analysis_id": "st_vs_defense_burden_numeric",
                "hypothesis": "H5",
                "task": "host_background_defense_burden_summary",
                "feature_set": "ST",
                "feature": st,
                "non_missing_count": str(len(values)),
                "unique_value_count": str(len({row["defense_count"] for row in values})),
                "full_accuracy": "",
                "accuracy_without_feature": "",
                "delta_accuracy": "",
                "association_metric": "mean_host_defense_system_count_by_ST",
                "association_value": format_float(mean_count),
                "notes": (
                    f"median={format_float(median_count)}; range={format_float(min_count)}-{format_float(max_count)}; "
                    f"mean_defense_type_count={format_float(mean_type_count)}; association_only_not_infectivity."
                ),
            }
        )


def add_assay_breadth_descriptive_result(
    rows: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
    samples: list[dict[str, str]],
) -> None:
    fractions = [parse_float_or_none(sample.get("spot_positive_fraction", "")) for sample in samples]
    present = [value for value in fractions if value is not None]
    rows.append(
        {
            "analysis_id": "spot_breadth_descriptive",
            "hypothesis": "H3",
            "task": "describe_spot_host_range_breadth",
            "target": "spot_positive_fraction",
            "feature_set": "assay_panel",
            "model_type": "descriptive_continuous_breadth",
            "n_samples": str(len(samples)),
            "n_classes": str(len(set(format_float(value) for value in present))),
            "n_features": "0",
            "coverage": "1.000" if samples else "0.000",
            "accuracy": "",
            "macro_f1": "",
            "baseline_accuracy": "",
            "delta_vs_baseline": "",
            "status": "descriptive_breadth_available" if samples else "blocked_no_host_range_breadth_labels",
            "notes": "Continuous spot-test breadth from explicit tested denominators; no arbitrary breadth threshold is used and this does not test RBP/counter-defense enrichment.",
        }
    )
    for sample in samples:
        feature_rows.append(
            {
                "analysis_id": "spot_breadth_descriptive",
                "hypothesis": "H3",
                "task": "describe_spot_host_range_breadth",
                "feature_set": "assay_panel",
                "feature": sample.get("phage_genome_id", ""),
                "non_missing_count": sample.get("tested_host_count", sample.get("spot_tested_host_count", "0")),
                "unique_value_count": sample.get("spot_positive_host_count", "0"),
                "full_accuracy": "",
                "accuracy_without_feature": "",
                "delta_accuracy": "",
                "association_metric": "spot_positive_fraction_wilson_ci95",
                "association_value": sample.get("spot_positive_fraction", ""),
                "notes": (
                    f"study_id={sample.get('study_id', '')};panel_id={sample.get('panel_id', '')};"
                    f"tested_host_count={sample.get('tested_host_count', '')};"
                    f"spot_positive_host_count={sample.get('spot_positive_host_count', '')};"
                    f"ci95={sample.get('spot_positive_fraction_ci95_low', '')}-{sample.get('spot_positive_fraction_ci95_high', '')}"
                ),
            }
        )


def add_assay_breadth_feature_readiness(
    rows: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
    samples: list[dict[str, str]],
    analysis_id: str,
    feature: str,
    min_assessed_phages: int,
    min_feature_groups: int,
    min_group_size: int,
) -> None:
    assessed = [sample for sample in samples if is_informative_feature_value(sample.get(feature, ""))]
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for sample in assessed:
        groups[safe_value(sample.get(feature, ""))].append(sample)
    small_groups = [group for group, group_samples in groups.items() if len(group_samples) < min_group_size]
    if not samples:
        status = "blocked_no_host_range_breadth_labels"
        notes = "No explicit assay panel denominators are available for H3."
    elif not assessed:
        status = "blocked_feature_not_assessed"
        notes = f"{feature} is not assessed for assay phages; missing evidence is not treated as biological zero."
    elif len(assessed) < min_assessed_phages or len(groups) < min_feature_groups or small_groups:
        status = "blocked_insufficient_feature_coverage"
        notes = (
            f"assessed_phages={len(assessed)}; feature_groups={len(groups)}; "
            f"small_groups={len(small_groups)}; thresholds=min_assessed_phages:{min_assessed_phages},"
            f"min_feature_groups:{min_feature_groups},min_group_size:{min_group_size}."
        )
    else:
        status = "analysis_ready"
        notes = "Feature coverage is sufficient for a pre-specified H3 association analysis, but claim support still requires production evidence and uncertainty analysis."

    rows.append(
        {
            "analysis_id": analysis_id,
            "hypothesis": "H3",
            "task": "test_spot_breadth_feature_association",
            "target": "spot_positive_fraction",
            "feature_set": feature,
            "model_type": "h3_feature_coverage_gate",
            "n_samples": str(len(samples)),
            "n_classes": str(len(set(sample.get("spot_positive_fraction", "") for sample in samples if not is_missing(sample.get("spot_positive_fraction", ""))))),
            "n_features": "1",
            "coverage": f"{len(assessed) / len(samples):.3f}" if samples else "0.000",
            "accuracy": "",
            "macro_f1": "",
            "baseline_accuracy": "",
            "delta_vs_baseline": "",
            "status": status,
            "notes": notes,
        }
    )

    if not assessed:
        feature_rows.append(
            {
                "analysis_id": analysis_id,
                "hypothesis": "H3",
                "task": "test_spot_breadth_feature_association",
                "feature_set": feature,
                "feature": "not_assessed",
                "non_missing_count": "0",
                "unique_value_count": "0",
                "full_accuracy": "",
                "accuracy_without_feature": "",
                "delta_accuracy": "",
                "association_metric": "h3_feature_coverage_fraction",
                "association_value": "0.000",
                "notes": "No assay phages have this feature assessed; do not interpret as zero detected.",
            }
        )
        return

    for group, group_samples in sorted(groups.items()):
        fractions = [parse_float_or_none(sample.get("spot_positive_fraction", "")) for sample in group_samples]
        present = [value for value in fractions if value is not None]
        mean_fraction = sum(present) / len(present) if present else None
        feature_rows.append(
            {
                "analysis_id": analysis_id,
                "hypothesis": "H3",
                "task": "test_spot_breadth_feature_association",
                "feature_set": feature,
                "feature": group,
                "non_missing_count": str(len(group_samples)),
                "unique_value_count": str(len(set(format_float(value) for value in present))),
                "full_accuracy": "",
                "accuracy_without_feature": "",
                "delta_accuracy": "",
                "association_metric": "mean_spot_positive_fraction_by_feature_group",
                "association_value": format_float(mean_fraction),
                "notes": "Descriptive only unless the corresponding model row is analysis_ready and production evidence is configured.",
            }
        )


def average_ranks(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(indexed):
        end = index + 1
        while end < len(indexed) and indexed[end][1] == indexed[index][1]:
            end += 1
        rank = (index + 1 + end) / 2
        for original_index, _value in indexed[index:end]:
            ranks[original_index] = rank
        index = end
    return ranks


def pearson_correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denom_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    denom_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if denom_x == 0 or denom_y == 0:
        return None
    return numerator / (denom_x * denom_y)


def spearman_correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    return pearson_correlation(average_ranks(xs), average_ranks(ys))


def add_assay_breadth_numeric_association(
    rows: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
    samples: list[dict[str, str]],
    analysis_id: str,
    feature: str,
    state_feature: str,
    min_assessed_phages: int,
    min_feature_groups: int,
    min_group_size: int,
) -> None:
    assessed: list[tuple[dict[str, str], float, float]] = []
    for sample in samples:
        state = sample.get(state_feature, "not_assessed")
        if state == "evidence_rejected":
            continue
        if state == "not_assessed" or is_missing(state):
            continue
        feature_value = parse_float_or_none(sample.get(feature, ""))
        breadth = parse_float_or_none(sample.get("spot_positive_fraction", ""))
        if feature_value is None or breadth is None:
            continue
        assessed.append((sample, feature_value, breadth))

    grouped: dict[str, list[tuple[dict[str, str], float, float]]] = defaultdict(list)
    for sample, feature_value, breadth in assessed:
        grouped[format_float(feature_value)].append((sample, feature_value, breadth))

    if not samples:
        status = "blocked_no_host_range_breadth_labels"
        notes = "No explicit assay panel denominators are available for H3."
    elif not assessed:
        status = "blocked_feature_not_assessed"
        notes = f"{feature} is not assessed for assay phages; missing evidence is not treated as biological zero."
    elif len(assessed) < min_assessed_phages or len(grouped) < min_feature_groups:
        status = "blocked_insufficient_feature_coverage"
        notes = (
            f"assessed_phages={len(assessed)}; feature_values={len(grouped)}; "
            f"thresholds=min_assessed_phages:{min_assessed_phages},min_feature_groups:{min_feature_groups}. "
            f"min_group_size:{min_group_size} applies to categorical feature-readiness gates, not numeric rank correlation."
        )
    else:
        status = "analysis_ready"
        notes = "Exploratory phage-level Spearman association between assessed feature count and spot-test breadth; not a productive-infection or causal host-range claim."

    feature_values = [feature_value for _sample, feature_value, _breadth in assessed]
    breadth_values = [breadth for _sample, _feature_value, breadth in assessed]
    rho = spearman_correlation(feature_values, breadth_values) if status == "analysis_ready" else None
    rows.append(
        {
            "analysis_id": analysis_id,
            "hypothesis": "H3",
            "task": "test_spot_breadth_feature_association",
            "target": "spot_positive_fraction",
            "feature_set": feature,
            "model_type": "spearman_rank_correlation",
            "n_samples": str(len(assessed)),
            "n_classes": str(len(set(format_float(value) for value in breadth_values))),
            "n_features": "1",
            "coverage": f"{len(assessed) / len(samples):.3f}" if samples else "0.000",
            "accuracy": "",
            "macro_f1": "",
            "baseline_accuracy": "",
            "delta_vs_baseline": "",
            "status": status,
            "notes": notes + (f" spearman_rho={format_float(rho)}." if rho is not None else ""),
        }
    )

    if not assessed:
        feature_rows.append(
            {
                "analysis_id": analysis_id,
                "hypothesis": "H3",
                "task": "test_spot_breadth_feature_association",
                "feature_set": feature,
                "feature": "not_assessed",
                "non_missing_count": "0",
                "unique_value_count": "0",
                "full_accuracy": "",
                "accuracy_without_feature": "",
                "delta_accuracy": "",
                "association_metric": "h3_feature_coverage_fraction",
                "association_value": "0.000",
                "notes": "No assay phages have this feature assessed; do not interpret as zero detected.",
            }
        )
        return

    feature_rows.append(
        {
            "analysis_id": analysis_id,
            "hypothesis": "H3",
            "task": "test_spot_breadth_feature_association",
            "feature_set": feature,
            "feature": "spearman_rho",
            "non_missing_count": str(len(assessed)),
            "unique_value_count": str(len(set(format_float(value) for value in feature_values))),
            "full_accuracy": "",
            "accuracy_without_feature": "",
            "delta_accuracy": "",
            "association_metric": "spearman_rho_spot_positive_fraction",
            "association_value": format_float(rho),
            "notes": "Phage-level association only; spot-test endpoint and tested-panel composition limit interpretation.",
        }
    )
    for group, group_samples in sorted(grouped.items(), key=lambda item: (parse_float_or_none(item[0]) is None, parse_float_or_none(item[0]) or 0.0)):
        breadths = [breadth for _sample, _feature_value, breadth in group_samples]
        feature_rows.append(
            {
                "analysis_id": analysis_id,
                "hypothesis": "H3",
                "task": "test_spot_breadth_feature_association",
                "feature_set": feature,
                "feature": group,
                "non_missing_count": str(len(group_samples)),
                "unique_value_count": str(len(set(format_float(value) for value in breadths))),
                "full_accuracy": "",
                "accuracy_without_feature": "",
                "delta_accuracy": "",
                "association_metric": "mean_spot_positive_fraction_by_numeric_feature_value",
                "association_value": format_float(mean_or_none(breadths)),
                "notes": "Descriptive bin of the same phage-level association; not a thresholded breadth definition.",
            }
        )


def row_id_set(rows: list[dict[str, str]], key: str) -> set[str]:
    return {row.get(key, "") for row in rows if not is_missing(row.get(key, ""))}


def is_verified_sequence(genome_id: str, manifest: dict[str, dict[str, str]], sequence_qc: dict[str, dict[str, str]]) -> bool:
    qc = sequence_qc.get(genome_id, {})
    if qc:
        return qc.get("passes_sequence_qc", "").lower() == "true" or qc.get("sequence_qc_status", "").lower() == "pass"
    manifest_row = manifest.get(genome_id, {})
    return manifest_row.get("has_raw_sequence", "").lower() == "true" and not is_missing(manifest_row.get("raw_sequence_path", ""))


def is_standardized_annotation(row: dict[str, str]) -> bool:
    tool = row.get("tool", "").lower()
    evidence = row.get("evidence", "").lower()
    return any(token in tool for token in ["pharokka", "phrog"]) or "standardized" in evidence


def has_domain_evidence(row: dict[str, str]) -> bool:
    values = [row.get("domain_hit", ""), row.get("domain_support", ""), row.get("best_domain_hit", "")]
    return any(is_informative_feature_value(value) and value.lower() not in {"absent", "none", "no_domain_evidence"} for value in values)


def has_structural_evidence(row: dict[str, str]) -> bool:
    values = [row.get("structural_hit", ""), row.get("structural_support", ""), row.get("best_structural_hit", "")]
    return any(is_informative_feature_value(value) and value.lower() not in {"absent", "none", "no_structural_evidence"} for value in values)


def coverage_state(detected_count: int, assessed_count: int, denominator: int, rejected_count: int = 0) -> str:
    if denominator <= 0:
        return "not_assessed"
    if rejected_count > 0 and assessed_count <= 0 and detected_count <= 0:
        return "evidence_rejected"
    if assessed_count <= 0:
        return "not_assessed"
    if detected_count <= 0:
        return "assessed_zero_detected"
    return "assessed_positive"


def coverage_fraction(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.3f}" if denominator else "0.000"


def add_coverage_row(
    rows: list[dict[str, str]],
    metric: str,
    entity_level: str,
    numerator: int,
    denominator: int,
    evidence_state: str,
    blocking_hypotheses: str,
    next_action: str,
    extra: dict[str, str] | None = None,
) -> None:
    row = {
        "metric": metric,
        "entity_level": entity_level,
        "numerator": str(numerator),
        "denominator": str(denominator),
        "coverage_fraction": coverage_fraction(numerator, denominator),
        "evidence_state": evidence_state,
        "blocking_hypotheses": blocking_hypotheses,
        "next_action": next_action,
    }
    if extra:
        row.update(extra)
    rows.append(row)


def build_assay_feature_coverage(
    assay_rows: list[dict[str, str]],
    assay_breadth_samples: list[dict[str, str]],
    manifest: dict[str, dict[str, str]],
    sequence_qc_rows: list[dict[str, str]],
    annotation_rows: list[dict[str, str]],
    rbp_rows: list[dict[str, str]],
    domain_rows: list[dict[str, str]],
    host_metadata_rows: list[dict[str, str]],
    compatibility_rows: list[dict[str, str]],
    host_defense_rows: list[dict[str, str]],
    phage_antidefense_rows: list[dict[str, str]],
    phage_receptor_rows: list[dict[str, str]],
    host_receptor_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    tested_spot_rows = [
        row for row in assay_rows
        if row.get("tested") == "true" and row.get("assay_type") == "spot" and row.get("spot_result") in {"positive", "negative"}
    ]
    assay_phages = sorted({row.get("phage_id", "") for row in tested_spot_rows if not is_missing(row.get("phage_id", ""))})
    assay_hosts = sorted({row.get("host_id", "") for row in tested_spot_rows if not is_missing(row.get("host_id", ""))})
    assay_pairs = [(row.get("phage_id", ""), row.get("host_id", "")) for row in tested_spot_rows]
    phage_count = len(assay_phages)
    host_count = len(assay_hosts)
    pair_count = len(assay_pairs)

    sequence_qc = {row.get("genome_id", ""): row for row in sequence_qc_rows if not is_missing(row.get("genome_id", ""))}
    host_metadata = {row.get("host_genome_id", ""): row for row in host_metadata_rows if not is_missing(row.get("host_genome_id", ""))}
    standardized_annotation_phages = {row.get("genome_id", "") for row in annotation_rows if is_standardized_annotation(row) and not is_missing(row.get("genome_id", ""))}
    rbp_phages = {row.get("genome_id", "") for row in rbp_rows if not is_missing(row.get("genome_id", ""))}
    domain_phages = {row.get("genome_id", "") for row in rbp_rows + domain_rows if not is_missing(row.get("genome_id", "")) and has_domain_evidence(row)}
    structural_phages = {row.get("genome_id", "") for row in rbp_rows + domain_rows if not is_missing(row.get("genome_id", "")) and has_structural_evidence(row)}
    domain_assessed_phages = {row.get("genome_id", "") for row in domain_rows if not is_missing(row.get("genome_id", ""))}
    structural_assessed_phages = {row.get("genome_id", "") for row in domain_rows if not is_missing(row.get("genome_id", "")) and any(column in row for column in ["structural_hit", "structural_hit_id", "structural_support", "best_structural_hit"])}

    host_defense_assessed_hosts = row_id_set(host_defense_rows, "host_genome_id")
    host_defense_detected_hosts = {
        row.get("host_genome_id", "")
        for row in host_defense_rows
        if not is_missing(row.get("host_genome_id", ""))
        and (
            parse_int(row.get("host_defense_system_count", "0")) > 0
            or is_informative_feature_value(row.get("host_defense_types", ""))
            or is_informative_feature_value(row.get("host_defense_systems", ""))
            or is_informative_feature_value(row.get("defense_type", ""))
            or is_informative_feature_value(row.get("defense_system", ""))
        )
    }
    antidefense_assessed_phages = row_id_set(phage_antidefense_rows, "phage_genome_id")
    antidefense_detected_phages = {
        row.get("phage_genome_id", "")
        for row in phage_antidefense_rows
        if not is_missing(row.get("phage_genome_id", ""))
        and (
            parse_int(row.get("phage_antidefense_count", "0")) > 0
            or is_informative_feature_value(row.get("phage_antidefense_targets", ""))
            or is_informative_feature_value(row.get("phage_antidefense_classes", ""))
            or is_informative_feature_value(row.get("target_defense_system", ""))
            or is_informative_feature_value(row.get("antidefense_class", ""))
        )
    }
    phage_receptor_phages = row_id_set(phage_receptor_rows, "phage_genome_id")
    host_receptor_hosts = row_id_set(host_receptor_rows, "host_genome_id")

    phage_seq = {phage for phage in assay_phages if is_verified_sequence(phage, manifest, sequence_qc)}
    host_seq = {host for host in assay_hosts if is_verified_sequence(host, manifest, sequence_qc)}
    sequence_assessed_ids = set(sequence_qc) | phage_seq | host_seq
    k_hosts = {host for host in assay_hosts if is_informative_feature_value(host_metadata.get(host, {}).get("K_type", ""))}
    o_hosts = {host for host in assay_hosts if is_informative_feature_value(host_metadata.get(host, {}).get("O_type", ""))}
    st_hosts = {host for host in assay_hosts if is_informative_feature_value(host_metadata.get(host, {}).get("ST", ""))}
    # Current source-identity host rows explicitly say K/O/ST are unreviewed. Without a
    # production typing status, a missing call is not an assessed zero.
    k_assessed_hosts = set(k_hosts)
    o_assessed_hosts = set(o_hosts)
    st_assessed_hosts = set(st_hosts)

    rows: list[dict[str, str]] = []
    add_coverage_row(rows, "unique_assay_phages", "unique_phage", phage_count, phage_count, coverage_state(phage_count, phage_count, phage_count), "H1b;H3", "Use as denominator for assay-phage feature acquisition.")
    add_coverage_row(rows, "unique_assay_hosts", "unique_host", host_count, host_count, coverage_state(host_count, host_count, host_count), "H1b", "Use as denominator for assay-host feature acquisition.")
    add_coverage_row(rows, "tested_spot_pairs", "pair", pair_count, pair_count, coverage_state(pair_count, pair_count, pair_count), "H1b;H3", "Spot outcomes are available for initial-interaction analyses only.")

    entity_metrics = [
        ("phage_sequence_verified", "unique_phage", len(set(assay_phages) & phage_seq), len(set(assay_phages) & sequence_assessed_ids), phage_count, "H1b;H3", "Verify or reconstruct assay phage sequences before production annotation."),
        ("host_sequence_verified", "unique_host", len(set(assay_hosts) & host_seq), len(set(assay_hosts) & sequence_assessed_ids), host_count, "H1b;H4", "Extract/reconstruct assay host genomes and verify checksums before K/O/ST or defense typing."),
        ("host_K_type", "unique_host", len(k_hosts), len(k_assessed_hosts), host_count, "H1b", "Run reviewed Kaptive/Kleborate-style typing for assay hosts."),
        ("host_O_type", "unique_host", len(o_hosts), len(o_assessed_hosts), host_count, "H1b", "Run reviewed Kaptive/Kleborate-style typing for assay hosts."),
        ("host_ST", "unique_host", len(st_hosts), len(st_assessed_hosts), host_count, "H1b;H5", "Run reviewed Kleborate/MLST typing for assay hosts."),
        ("standardized_phage_annotation", "unique_phage", len(set(assay_phages) & standardized_annotation_phages), len(set(assay_phages) & standardized_annotation_phages), phage_count, "H1b;H3", "Run standardized phage annotation for assay phages; bridge GenBank annotations are not counted here."),
        ("rbp_candidates", "unique_phage", len(set(assay_phages) & rbp_phages), len(set(assay_phages) & rbp_phages), phage_count, "H1b;H3", "Run accepted RBP/depolymerase prediction for assay phages."),
        ("domain_evidence", "unique_phage", len(set(assay_phages) & domain_phages), len(set(assay_phages) & domain_assessed_phages), phage_count, "H1b;H3", "Add reviewed domain evidence for assay-phage RBP candidates."),
        ("structural_evidence", "unique_phage", len(set(assay_phages) & structural_phages), len(set(assay_phages) & structural_assessed_phages), phage_count, "H1b;H3", "Add reviewed structural/remote-homology evidence for assay-phage RBP candidates."),
        ("host_defense_evidence", "unique_host", len(set(assay_hosts) & host_defense_detected_hosts), len(set(assay_hosts) & host_defense_assessed_hosts), host_count, "H4;H5", "Run PADLOC/DefenseFinder or reviewed host-defense evidence for assay hosts."),
        ("phage_counterdefense_evidence", "unique_phage", len(set(assay_phages) & antidefense_detected_phages), len(set(assay_phages) & antidefense_assessed_phages), phage_count, "H3;H4", "Run reviewed phage anti-defense/counter-defense screening for assay phages."),
    ]
    for metric, level, detected, assessed, denominator, blockers, action in entity_metrics:
        add_coverage_row(rows, metric, level, detected, denominator, coverage_state(detected, assessed, denominator), blockers, action)

    pair_metrics = [
        ("phage_sequence_verified", "pair", sum(1 for phage, _host in assay_pairs if phage in phage_seq), sum(1 for phage, _host in assay_pairs if phage in sequence_assessed_ids), pair_count, "H1b;H3", "Complete assay-phage sequence verification for every tested pair."),
        ("host_sequence_verified", "pair", sum(1 for _phage, host in assay_pairs if host in host_seq), sum(1 for _phage, host in assay_pairs if host in sequence_assessed_ids), pair_count, "H1b;H4", "Complete assay-host sequence verification for every tested pair."),
        ("host_K_type", "pair", sum(1 for _phage, host in assay_pairs if host in k_hosts), sum(1 for _phage, host in assay_pairs if host in k_assessed_hosts), pair_count, "H1b", "Acquire K-type calls for tested hosts."),
        ("host_O_type", "pair", sum(1 for _phage, host in assay_pairs if host in o_hosts), sum(1 for _phage, host in assay_pairs if host in o_assessed_hosts), pair_count, "H1b", "Acquire O-type calls for tested hosts."),
        ("host_ST", "pair", sum(1 for _phage, host in assay_pairs if host in st_hosts), sum(1 for _phage, host in assay_pairs if host in st_assessed_hosts), pair_count, "H1b;H5", "Acquire ST calls for tested hosts."),
        ("standardized_phage_annotation", "pair", sum(1 for phage, _host in assay_pairs if phage in standardized_annotation_phages), sum(1 for phage, _host in assay_pairs if phage in standardized_annotation_phages), pair_count, "H1b;H3", "Annotate assay phages with standardized production tools."),
        ("rbp_candidates", "pair", sum(1 for phage, _host in assay_pairs if phage in rbp_phages), sum(1 for phage, _host in assay_pairs if phage in rbp_phages), pair_count, "H1b;H3", "Predict assay-phage RBP/depolymerase candidates."),
        ("domain_evidence", "pair", sum(1 for phage, _host in assay_pairs if phage in domain_phages), sum(1 for phage, _host in assay_pairs if phage in domain_assessed_phages), pair_count, "H1b;H3", "Add domain evidence for assay-phage RBP candidates."),
        ("structural_evidence", "pair", sum(1 for phage, _host in assay_pairs if phage in structural_phages), sum(1 for phage, _host in assay_pairs if phage in structural_assessed_phages), pair_count, "H1b;H3", "Add structural evidence for assay-phage RBP candidates."),
        ("host_defense_evidence", "pair", sum(1 for _phage, host in assay_pairs if host in host_defense_detected_hosts), sum(1 for _phage, host in assay_pairs if host in host_defense_assessed_hosts), pair_count, "H4;H5", "Annotate host defense systems for assay hosts."),
        ("phage_counterdefense_evidence", "pair", sum(1 for phage, _host in assay_pairs if phage in antidefense_detected_phages), sum(1 for phage, _host in assay_pairs if phage in antidefense_assessed_phages), pair_count, "H3;H4", "Annotate phage counter-defense features for assay phages."),
    ]
    for metric, level, detected, assessed, denominator, blockers, action in pair_metrics:
        add_coverage_row(rows, metric, level, detected, denominator, coverage_state(detected, assessed, denominator), blockers, action)

    receptor_complete = sum(
        1
        for phage, host in assay_pairs
        if phage in rbp_phages and (host in k_hosts or host in o_hosts)
    )
    receptor_assessed = sum(
        1
        for phage, host in assay_pairs
        if phage in rbp_phages and (host in k_assessed_hosts or host in o_assessed_hosts)
    )
    seed_bridge_metadata_coverage = sum(
        1
        for phage, host in assay_pairs
        if phage in phage_receptor_phages and host in host_receptor_hosts
    )
    defense_complete = sum(1 for phage, host in assay_pairs if phage in antidefense_detected_phages and host in host_defense_detected_hosts)
    defense_assessed = sum(1 for phage, host in assay_pairs if phage in antidefense_assessed_phages and host in host_defense_assessed_hosts)
    productive_measured = sum(1 for row in tested_spot_rows if row.get("productive_infection_result", "").strip().lower() in PRODUCTIVE_INFECTION_OBSERVED_VALUES)
    add_coverage_row(rows, "receptor_layer_feature_completeness", "pair", receptor_complete, pair_count, coverage_state(receptor_complete, receptor_assessed, pair_count), "H1b", "Acquire production assay-phage RBP candidates and host K/O calls; seed bridge support is reported separately.")
    add_coverage_row(rows, "seed_bridge_metadata_coverage", "pair", seed_bridge_metadata_coverage, pair_count, coverage_state(seed_bridge_metadata_coverage, seed_bridge_metadata_coverage, pair_count), "H1b", "RBPbase/Locibase seed bridge metadata can exercise the path, but it is not production K/O or RBP/domain evidence.")
    add_coverage_row(rows, "defense_counterdefense_feature_completeness", "pair", defense_complete, pair_count, coverage_state(defense_complete, defense_assessed, pair_count), "H4", "Acquire host-defense and phage counter-defense evidence for the same tested pairs.")
    add_coverage_row(rows, "productive_infection_outcomes", "pair", productive_measured, pair_count, coverage_state(productive_measured, productive_measured, pair_count), "H4", "Curate plaque, EOP, propagation, or productive-infection labels; spot tests alone do not satisfy H4.")

    for sample in assay_breadth_samples:
        tested = parse_int(sample.get("tested_host_count", sample.get("spot_tested_host_count", "0")))
        positive = parse_int(sample.get("spot_positive_host_count", "0"))
        add_coverage_row(
            rows,
            "spot_breadth_continuous",
            "phage_panel",
            positive,
            tested,
            "descriptive_breadth_available" if tested else "not_assessed",
            "H3",
            "Use as descriptive initial-interaction breadth only until production RBP/counter-defense features are assessed.",
            {
                "study_id": sample.get("study_id", ""),
                "panel_id": sample.get("panel_id", ""),
                "phage_id": sample.get("phage_genome_id", ""),
                "tested_host_count": str(tested),
                "spot_positive_host_count": str(positive),
                "spot_positive_fraction": sample.get("spot_positive_fraction", ""),
                "spot_positive_fraction_ci95_low": sample.get("spot_positive_fraction_ci95_low", ""),
                "spot_positive_fraction_ci95_high": sample.get("spot_positive_fraction_ci95_high", ""),
            },
        )
    return rows


def summary_status(rows: list[dict[str, str]]) -> tuple[str, str, str, str]:
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    max_n = max([parse_int(row.get("n_samples", "0")) for row in rows] + [0])
    statuses = {row.get("status", "") for row in rows}
    if "biological_claim_supported" in statuses:
        status = "pass"
        claim_status = "biological_claim_supported"
        action = "Biological claim support is available; verify effect direction, uncertainty, and limitations before manuscript use."
    elif "analysis_supported" in statuses or "analysis_ready" in statuses:
        status = "warn"
        claim_status = "data_dependent"
        action = "Analysis-ready rows exist, but biological claim support still requires effect-size, uncertainty, and claim-ledger review."
    elif ok_rows:
        status = "warn"
        claim_status = "data_dependent"
        action = "Technical rows are complete, but ok status alone is not biological claim support."
    elif rows:
        status = "warn"
        claim_status = "data_dependent"
        action = "Add the missing outcome or feature evidence required by this hypothesis."
    else:
        status = "fail"
        claim_status = "data_dependent"
        action = "Generate the required model or group-summary rows for this hypothesis."
    return status, claim_status, action, str(max_n)


def first_row(rows: list[dict[str, str]], default: dict[str, str] | None = None) -> dict[str, str]:
    return rows[0] if rows else (default or {})


def rows_for(model_rows: list[dict[str, str]], hypothesis: str, analysis_ids: set[str] | None = None) -> list[dict[str, str]]:
    rows = [row for row in model_rows if row.get("hypothesis") == hypothesis]
    if analysis_ids is not None:
        rows = [row for row in rows if row.get("analysis_id") in analysis_ids]
    return rows


def model_row(model_rows: list[dict[str, str]], target: str, feature_set: str) -> dict[str, str] | None:
    matches = [row for row in model_rows if row.get("target") == target and row.get("feature_set") == feature_set]
    return matches[0] if matches else None


def mean_accuracy_for(model_rows: list[dict[str, str]], targets: list[str], feature_set: str) -> float | None:
    return mean_or_none(
        parse_float_or_none(row.get("accuracy", ""))
        for target in targets
        for row in [model_row(model_rows, target, feature_set)]
        if row is not None
    )


def mean_delta_between(model_rows: list[dict[str, str]], targets: list[str], primary_feature_set: str, comparison_feature_set: str) -> float | None:
    deltas: list[float] = []
    for target in targets:
        primary = model_row(model_rows, target, primary_feature_set)
        comparison = model_row(model_rows, target, comparison_feature_set)
        if primary is None or comparison is None:
            continue
        primary_accuracy = parse_float_or_none(primary.get("accuracy", ""))
        comparison_accuracy = parse_float_or_none(comparison.get("accuracy", ""))
        if primary_accuracy is not None and comparison_accuracy is not None:
            deltas.append(primary_accuracy - comparison_accuracy)
    return mean_or_none(deltas)


def group_fraction_range(
    feature_rows: list[dict[str, str]],
    analysis_ids: set[str],
    association_metric: str = "top_group_label_fraction",
) -> tuple[float | None, float | None, float | None]:
    values = [
        parse_float_or_none(row.get("association_value", ""))
        for row in feature_rows
        if row.get("analysis_id") in analysis_ids and row.get("association_metric") == association_metric
    ]
    present = [value for value in values if value is not None]
    if not present:
        return None, None, None
    return max(present), min(present), max(present) - min(present)


def summary_row(
    hypothesis: str,
    question: str,
    required_test: str,
    evidence_path: str,
    rows: list[dict[str, str]],
    primary: dict[str, str],
    primary_metric: str,
    primary_metric_value: float | None,
    baseline_metric_value: float | None,
    effect_size: float | None,
    comparison_feature_set: str,
    guardrail: str,
) -> dict[str, str]:
    ok_count = sum(1 for row in rows if row.get("status") == "ok")
    limited_count = sum(1 for row in rows if row.get("status") and row.get("status") != "ok")
    status, claim_status, action, max_n = summary_status(rows)
    row_statuses = {row.get("status", "") for row in rows}
    if "blocked_no_host_range_breadth_labels" in row_statuses:
        action = "Curate phage-host assay panels with tested-host denominators and susceptible-host numerators, then rerun Stage 7."
    elif "analysis_ready" in row_statuses and "blocked_insufficient_feature_coverage" in row_statuses:
        action = "Exploratory H3 association rows are available for assessed receptor-module features, but counter-defense coverage is still insufficient and biological claims remain data-dependent."
    elif "blocked_feature_not_assessed" in row_statuses:
        action = "Use the descriptive spot-breadth table, but acquire accepted production RBP/depolymerase and counter-defense evidence before testing H3 associations."
    elif "blocked_insufficient_feature_coverage" in row_statuses:
        action = "Increase assessed assay-phage feature coverage and satisfy the pre-specified H3 thresholds before testing H3 associations."
    elif "descriptive_breadth_available" in row_statuses:
        action = "Spot-test breadth is available descriptively; do not treat it as support for RBP/counter-defense enrichment until feature evidence is assessed."
    elif "prophage_annotations_assessed_zero_rbp_candidates" in row_statuses:
        action = "Expand the prophage cohort and run standardized Pharokka/PHROGs plus domain/structural annotation before making an H2 reservoir claim."
    elif "blocked_insufficient_prophage_cohort" in row_statuses:
        action = "Increase the reviewed prophage cohort before testing prophage RBP/depolymerase reservoir enrichment."
    elif "blocked_no_productive_infection_labels" in row_statuses:
        action = "Curate productive-infection, plaque, or EOP outcomes for tested phage-host pairs, then rerun Stage 7."
    return {
        "hypothesis": hypothesis,
        "primary_question": question,
        "required_test": required_test,
        "evidence_path": evidence_path,
        "matching_model_rows": str(len(rows)),
        "ok_model_rows": str(ok_count),
        "limited_model_rows": str(limited_count),
        "max_n_samples": max_n,
        "primary_analysis_id": primary.get("analysis_id", ""),
        "primary_task": primary.get("task", ""),
        "primary_target": primary.get("target", ""),
        "primary_feature_set": primary.get("feature_set", ""),
        "comparison_feature_set": comparison_feature_set,
        "primary_metric": primary_metric,
        "primary_metric_value": format_float(primary_metric_value),
        "baseline_metric_value": format_float(baseline_metric_value),
        "effect_size": format_float(effect_size),
        "summary_status": status,
        "claim_status": claim_status,
        "interpretation_guardrail": guardrail,
        "next_action": action,
    }


def build_hypothesis_summary(
    model_rows: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
    evidence_path: str,
) -> list[dict[str, str]]:
    h1_rows = rows_for(model_rows, "H1")
    h1_primary = first_row([row for row in h1_rows if row.get("feature_set") == "rbp_depolymerase_modules"])
    h1_targets = ["K_type", "O_type"]
    h1_metric = mean_accuracy_for(h1_rows, h1_targets, "rbp_depolymerase_modules")
    h1_baseline = mean_accuracy_for(h1_rows, h1_targets, "taxonomy_only")
    h1_effect = mean_delta_between(h1_rows, h1_targets, "rbp_depolymerase_modules", "taxonomy_only")

    h4_rows = rows_for(model_rows, "H4")
    h4_primary = first_row([row for row in h4_rows if row.get("feature_set") == "receptor_plus_defense_counterdefense"], first_row(h4_rows))
    h4_targets = ["productive_infection_result"]
    h4_metric = mean_accuracy_for(h4_rows, h4_targets, "receptor_plus_defense_counterdefense")
    h4_baseline = mean_accuracy_for(h4_rows, h4_targets, "receptor_only")
    h4_effect = mean_delta_between(h4_rows, h4_targets, "receptor_plus_defense_counterdefense", "receptor_only")

    group_specs = [
        (
            "H2",
            "Do prophages provide a reservoir of RBP/depolymerase modules?",
            "record type versus RBP module group-rate summary",
            {"prophage_annotation_rbp_candidate_coverage", "record_type_vs_rbp_modules"},
            "top_label_fraction_range_by_record_type",
            "Prophage module rows are candidates only; function and capsule specificity require validation.",
        ),
        (
            "H3",
            "Are broad-host-range phages enriched for modular RBPs and counter-defense genes?",
            "host-range breadth test from explicit assay panel denominators plus feature-coverage gates",
            {
                "host_range_breadth_blocker",
                "spot_breadth_descriptive",
                "spot_breadth_vs_rbp_candidates",
                "spot_breadth_vs_counterdefense_candidates",
                "spot_breadth_vs_domain_module_count",
                "spot_breadth_vs_structural_module_count",
                "spot_breadth_vs_total_module_count",
                "spot_breadth_vs_antidefense_candidate_count",
            },
            "spot_test_host_range_breadth_descriptive_and_feature_readiness",
            "Spot-test breadth is initial-interaction evidence only; productive-infection breadth remains unavailable without plaque/EOP/propagation outcomes.",
        ),
        (
            "H5",
            "Do host lineages differ in defense burden?",
            "ST versus host defense burden numeric summary",
            {"st_vs_defense_burden_numeric"},
            "mean_defense_system_count_range_by_ST",
            "Lineage differences are associations and may reflect sampling bias; DefenseFinder burden is not phage susceptibility.",
        ),
        (
            "H6",
            "Are novel RBP candidates enriched by source or cluster context?",
            "source and cluster-size versus RBP novelty group-rate summaries",
            {"source_vs_rbp_novelty", "cluster_size_vs_rbp_novelty"},
            "top_label_fraction_range_by_source_or_cluster",
            "Novelty prioritization is computational and does not establish receptor specificity.",
        ),
    ]

    summary = [
        summary_row(
            "H1",
            "Do RBP/depolymerase features predict K/O association better than taxonomy?",
            "K/O proxy model comparison; pairwise spot-interaction modeling remains blocked until production receptor features are available",
            evidence_path,
            h1_rows,
            h1_primary,
            "mean_accuracy_receptor_plus_rbp_or_rbp_depolymerase_modules",
            h1_metric,
            h1_baseline,
            h1_effect,
            "taxonomy_only",
            "Do not claim RBP superiority unless production receptor/RBP evidence and leakage-safe pairwise evaluation are implemented in a later analysis.",
        ),
        summary_row(
            "H4",
            "Among receptor-compatible tested pairs, do defense/counter-defense features improve productive-infection prediction?",
            "productive-infection assay model comparison with receptor-only and receptor plus defense/counter-defense feature sets",
            evidence_path,
            h4_rows,
            h4_primary,
            "mean_accuracy_receptor_plus_defense_counterdefense",
            h4_metric,
            h4_baseline,
            h4_effect,
            "receptor_only",
            "Blocked until productive-infection, plaque, or EOP outcomes exist; compatibility feature strings are not biological targets.",
        ),
    ]

    for hypothesis, question, required_test, analysis_ids, metric_name, guardrail in group_specs:
        rows = [row for row in model_rows if row.get("analysis_id") in analysis_ids]
        primary = first_row(rows)
        association_metric = "mean_host_defense_system_count_by_ST" if hypothesis == "H5" else "top_group_label_fraction"
        metric, baseline, effect = group_fraction_range(feature_rows, analysis_ids, association_metric)
        summary.append(
            summary_row(
                hypothesis,
                question,
                required_test,
                evidence_path,
                rows,
                primary,
                metric_name,
                metric,
                baseline,
                effect,
                "group_rate_min_top_fraction",
                guardrail,
            )
        )
    return sorted(summary, key=lambda row: row["hypothesis"])



def run_models(
    samples: list[dict[str, str]],
    assay_breadth_samples: list[dict[str, str]],
    assay_row_count: int,
    h3_min_assessed_phages: int,
    h3_min_feature_groups: int,
    h3_min_group_size: int,
    host_metadata_rows: list[dict[str, str]],
    host_defense_rows: list[dict[str, str]],
    annotation_rows: list[dict[str, str]],
    rbp_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    model_rows: list[dict[str, str]] = []
    feature_rows: list[dict[str, str]] = []
    error_rows: list[dict[str, str]] = []

    for target, hypothesis in [("K_type", "H1"), ("O_type", "H1")]:
        for feature_set, features in K_O_FEATURE_SETS.items():
            add_model_results(
                model_rows,
                feature_rows,
                error_rows,
                f"{target}_{feature_set}",
                hypothesis,
                f"predict_{target}",
                target,
                feature_set,
                features,
                samples,
            )

    add_blocked_test(
        model_rows,
        "H4",
        "productive_infection_receptor_defense_blocker",
        "predict_productive_infection_result",
        "productive_infection_result",
        "receptor_plus_defense_counterdefense",
        "blocked_assay_outcome_required",
        assay_row_count if assay_row_count else len(samples),
        "blocked_no_productive_infection_labels",
        "H4 requires tested productive-infection, plaque, or EOP outcomes. compatibility_feature_status and matched_counterdefense_status are feature-derived labels and are not valid biological targets.",
    )

    add_h2_prophage_annotation_coverage(model_rows, feature_rows, annotation_rows, rbp_rows)
    add_rate_test(
        model_rows,
        feature_rows,
        samples,
        "H2",
        "record_type_vs_rbp_modules",
        "prophage_rbp_module_reservoir_summary",
        "record_type",
        "rbp_module_clusters",
    )
    if assay_breadth_samples:
        add_assay_breadth_descriptive_result(model_rows, feature_rows, assay_breadth_samples)
        add_assay_breadth_feature_readiness(
            model_rows,
            feature_rows,
            assay_breadth_samples,
            "spot_breadth_vs_rbp_candidates",
            "rbp_candidate_count_bin",
            h3_min_assessed_phages,
            h3_min_feature_groups,
            h3_min_group_size,
        )
        add_assay_breadth_feature_readiness(
            model_rows,
            feature_rows,
            assay_breadth_samples,
            "spot_breadth_vs_counterdefense_candidates",
            "phage_antidefense_count_bin",
            h3_min_assessed_phages,
            h3_min_feature_groups,
            h3_min_group_size,
        )
        add_assay_breadth_numeric_association(
            model_rows,
            feature_rows,
            assay_breadth_samples,
            "spot_breadth_vs_domain_module_count",
            "rbp_domain_module_count",
            "rbp_module_identity_state",
            h3_min_assessed_phages,
            h3_min_feature_groups,
            h3_min_group_size,
        )
        add_assay_breadth_numeric_association(
            model_rows,
            feature_rows,
            assay_breadth_samples,
            "spot_breadth_vs_structural_module_count",
            "rbp_structural_module_count",
            "rbp_module_identity_state",
            h3_min_assessed_phages,
            h3_min_feature_groups,
            h3_min_group_size,
        )
        add_assay_breadth_numeric_association(
            model_rows,
            feature_rows,
            assay_breadth_samples,
            "spot_breadth_vs_total_module_count",
            "rbp_total_module_count",
            "rbp_module_identity_state",
            h3_min_assessed_phages,
            h3_min_feature_groups,
            h3_min_group_size,
        )
        add_assay_breadth_numeric_association(
            model_rows,
            feature_rows,
            assay_breadth_samples,
            "spot_breadth_vs_antidefense_candidate_count",
            "phage_antidefense_candidate_count",
            "phage_antidefense_candidate_state",
            h3_min_assessed_phages,
            h3_min_feature_groups,
            h3_min_group_size,
        )
    else:
        add_blocked_test(
            model_rows,
            "H3",
            "host_range_breadth_blocker",
            "test_host_range_breadth_association",
            "host_range_breadth",
            "rbp_modularity_plus_counterdefense",
            "blocked_assay_panel_required",
            len(samples),
            "blocked_no_host_range_breadth_labels",
            "H3 requires assay panels with tested-host denominators and susceptible-host numerators. RBP/counter-defense co-occurrence is not a host-range breadth test.",
        )
    add_host_defense_burden_by_st(
        model_rows,
        feature_rows,
        host_metadata_rows,
        host_defense_rows,
    )
    add_rate_test(
        model_rows,
        feature_rows,
        samples,
        "H6",
        "source_vs_rbp_novelty",
        "source_novelty_enrichment_summary",
        "source_group",
        "novel_rbp_status",
    )
    add_rate_test(
        model_rows,
        feature_rows,
        samples,
        "H6",
        "cluster_size_vs_rbp_novelty",
        "cluster_novelty_enrichment_summary",
        "species_cluster_size_bin",
        "novel_rbp_status",
    )
    return model_rows, feature_rows, error_rows


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []

    manifest = load_manifest(Path(args.manifest))
    clusters = load_clusters(Path(args.clusters))
    _, rbp_rows = read_tsv(Path(args.rbp_candidates))
    _, link_rows = read_tsv(Path(args.phage_host_links))
    _, compatibility_rows = read_tsv(Path(args.compatibility_features))
    assay_rows: list[dict[str, str]] = []
    if args.phage_host_assays and Path(args.phage_host_assays).exists():
        _, assay_rows = read_tsv(Path(args.phage_host_assays))
    _, sequence_qc_rows = read_optional_tsv(args.sequence_qc)
    _, annotation_rows = read_optional_tsv(args.annotations)
    _, domain_rows = read_optional_tsv(args.domain_architectures)
    _, module_identity_rows = read_optional_tsv(args.phage_module_identities)
    _, host_metadata_rows = read_optional_tsv(args.host_metadata)
    _, host_defense_rows = read_optional_tsv(args.host_defense)
    _, phage_antidefense_rows = read_optional_tsv(args.phage_antidefense)
    _, phage_receptor_rows = read_optional_tsv(args.phage_receptor_support)
    _, host_receptor_rows = read_optional_tsv(args.host_receptor_support)
    rbp_features = rbp_features_by_phage(rbp_rows)
    add_report(
        report,
        "info",
        "inputs",
        f"Loaded {len(manifest)} manifest rows, {len(clusters)} cluster rows, {len(rbp_rows)} RBP candidates, {len(link_rows)} phage-host links, {len(compatibility_rows)} compatibility rows, {len(assay_rows)} assay rows, {len(annotation_rows)} annotation rows, {len(module_identity_rows)} module-identity rows, {len(host_metadata_rows)} host metadata rows, {len(host_defense_rows)} host-defense rows, {len(phage_antidefense_rows)} phage anti-defense rows, {len(phage_receptor_rows)} phage bridge-metadata rows, and {len(host_receptor_rows)} host bridge-metadata rows.",
    )

    samples = build_samples(
        link_rows,
        manifest,
        clusters,
        rbp_features,
        compatibility_by_pair(compatibility_rows),
    )
    assay_breadth_samples = build_assay_breadth_samples(
        assay_rows,
        manifest,
        clusters,
        rbp_features,
        phage_counterdefense_by_phage(compatibility_rows),
        phage_module_identities_by_phage(module_identity_rows),
        phage_antidefense_candidates_by_phage(phage_antidefense_rows),
    )
    model_rows, feature_rows, error_rows = run_models(
        samples,
        assay_breadth_samples,
        len(assay_rows),
        args.h3_min_assessed_phages,
        args.h3_min_feature_groups,
        args.h3_min_group_size,
        host_metadata_rows,
        host_defense_rows,
        annotation_rows,
        rbp_rows,
    )
    hypothesis_summary_rows = build_hypothesis_summary(model_rows, feature_rows, display_path(Path(args.model_comparison_output)))
    assay_feature_coverage_rows = build_assay_feature_coverage(
        assay_rows,
        assay_breadth_samples,
        manifest,
        sequence_qc_rows,
        annotation_rows,
        rbp_rows,
        domain_rows,
        host_metadata_rows,
        compatibility_rows,
        host_defense_rows,
        phage_antidefense_rows,
        phage_receptor_rows,
        host_receptor_rows,
    )
    add_report(
        report,
        "info",
        "models",
        f"Built {len(model_rows)} model/test rows, {len(feature_rows)} feature rows, {len(error_rows)} prediction rows, {len(hypothesis_summary_rows)} hypothesis summary rows, and {len(assay_feature_coverage_rows)} assay feature-coverage rows from {len(samples)} metadata-link samples and {len(assay_breadth_samples)} assay-breadth samples.",
    )

    assay_feature_coverage_output = Path(args.assay_feature_coverage_output) if args.assay_feature_coverage_output else Path(args.model_comparison_output).parent.parent / "qc" / "assay_feature_coverage.tsv"
    write_tsv(Path(args.model_comparison_output), MODEL_COMPARISON_COLUMNS, model_rows)
    write_tsv(Path(args.feature_importance_output), FEATURE_IMPORTANCE_COLUMNS, feature_rows)
    write_tsv(Path(args.prediction_errors_output), PREDICTION_ERROR_COLUMNS, error_rows)
    write_tsv(Path(args.hypothesis_summary_output), HYPOTHESIS_SUMMARY_COLUMNS, hypothesis_summary_rows)
    write_tsv(assay_feature_coverage_output, ASSAY_FEATURE_COVERAGE_COLUMNS, assay_feature_coverage_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)

    print(
        f"Compared {len(model_rows)} feature-set models/tests using {len(samples)} phage-host samples; "
        f"wrote {len(error_rows)} prediction rows, {len(hypothesis_summary_rows)} hypothesis summary rows, and {len(assay_feature_coverage_rows)} assay feature-coverage rows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
