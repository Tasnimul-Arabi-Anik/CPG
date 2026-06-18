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
    parser.add_argument("--model-comparison-output", required=True, help="Output model comparison TSV.")
    parser.add_argument("--feature-importance-output", required=True, help="Output feature importance TSV.")
    parser.add_argument("--prediction-errors-output", required=True, help="Output prediction/error TSV.")
    parser.add_argument("--hypothesis-summary-output", required=True, help="Output H1-H6 hypothesis evidence summary TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING_VALUES


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
            "rbp_high_confidence_count": str(high_conf),
            "rbp_high_confidence_count_bin": count_bin(high_conf),
        }
    return features


def compatibility_by_pair(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(row.get("phage_genome_id", ""), row.get("host_genome_id", "")): row for row in rows}


def novelty_status(rbp: dict[str, str]) -> str:
    tiers = set(split_values(rbp.get("rbp_novelty_tiers", "")))
    candidate_count = parse_int(rbp.get("rbp_candidate_count", "0"))
    if tiers & {"tier_1", "tier_2"}:
        return "tier_1_or_2_rbp_candidate"
    if "tier_3" in tiers:
        return "known_family_rbp_candidate"
    if candidate_count > 0:
        return "candidate_without_novelty_evidence"
    return "no_rbp_candidate"


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
            "rbp_candidate_count_bin": rbp.get("rbp_candidate_count_bin", "0"),
            "rbp_high_confidence_count_bin": rbp.get("rbp_high_confidence_count_bin", "0"),
            "novel_rbp_status": novelty_status(rbp),
            "host_defense_types": compat.get("host_defense_types", ""),
            "host_defense_systems": compat.get("host_defense_systems", ""),
            "host_defense_system_count_bin": count_bin(host_defense_count),
            "phage_antidefense_classes": compat.get("phage_antidefense_classes", ""),
            "phage_antidefense_targets": compat.get("phage_antidefense_targets", ""),
            "phage_antidefense_count_bin": count_bin(anti_count),
            "matched_counterdefense_count_bin": count_bin(matched_counterdefense_count),
            "compatibility_feature_status": compat.get("compatibility_feature_status", ""),
            "matched_counterdefense_status": "matched_counterdefense" if matched_counterdefense_count > 0 else "no_matched_counterdefense",
        }
        samples.append(sample)
    return samples


def feature_summary(samples: list[dict[str, str]], feature: str) -> tuple[int, int]:
    values = [safe_value(sample.get(feature, "")) for sample in samples if not is_missing(sample.get(feature, ""))]
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


def summary_status(rows: list[dict[str, str]]) -> tuple[str, str, str, str]:
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    limited_rows = [row for row in rows if row.get("status") and row.get("status") != "ok"]
    max_n = max([parse_int(row.get("n_samples", "0")) for row in rows] + [0])
    if ok_rows:
        status = "pass"
        claim_status = "workflow_supported"
        action = "Use real populated outputs to decide whether the biological hypothesis is supported."
    elif rows:
        status = "warn"
        claim_status = "data_dependent"
        action = "Add labeled samples or metadata breadth until at least one quantitative row has ok status."
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


def group_fraction_range(feature_rows: list[dict[str, str]], analysis_ids: set[str]) -> tuple[float | None, float | None, float | None]:
    values = [
        parse_float_or_none(row.get("association_value", ""))
        for row in feature_rows
        if row.get("analysis_id") in analysis_ids and row.get("association_metric") == "top_group_label_fraction"
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
            {"record_type_vs_rbp_modules"},
            "top_label_fraction_range_by_record_type",
            "Prophage module rows are candidates only; function and capsule specificity require validation.",
        ),
        (
            "H3",
            "Are broad-host-range phages enriched for modular RBPs and counter-defense genes?",
            "host-range breadth test from explicit assay panel denominators",
            {"host_range_breadth_blocker"},
            "host_range_breadth_metric",
            "Blocked until explicit assay panels provide tested-host denominators and susceptible-host numerators.",
        ),
        (
            "H5",
            "Do host lineages differ in defense burden?",
            "ST versus host defense burden group-rate summary",
            {"st_vs_defense_status"},
            "top_label_fraction_range_by_ST",
            "Lineage differences are associations and may reflect sampling bias.",
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
            "Do RBP/depolymerase modules predict K/O association better than phage taxonomy?",
            "K/O prediction model comparison",
            evidence_path,
            h1_rows,
            h1_primary,
            "mean_accuracy_rbp_depolymerase_modules",
            h1_metric,
            h1_baseline,
            h1_effect,
            "taxonomy_only",
            "Do not claim RBP superiority unless populated real-data metrics outperform taxonomy/genome baselines.",
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
        metric, baseline, effect = group_fraction_range(feature_rows, analysis_ids)
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



def run_models(samples: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
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
        len(samples),
        "blocked_no_productive_infection_labels",
        "H4 requires tested productive-infection, plaque, or EOP outcomes. compatibility_feature_status and matched_counterdefense_status are feature-derived labels and are not valid biological targets.",
    )

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
    add_rate_test(
        model_rows,
        feature_rows,
        samples,
        "H5",
        "st_vs_defense_status",
        "host_background_defense_summary",
        "ST",
        "host_defense_system_count_bin",
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
    add_report(
        report,
        "info",
        "inputs",
        f"Loaded {len(manifest)} manifest rows, {len(clusters)} cluster rows, {len(rbp_rows)} RBP candidates, {len(link_rows)} phage-host links, and {len(compatibility_rows)} compatibility rows.",
    )

    samples = build_samples(
        link_rows,
        manifest,
        clusters,
        rbp_features_by_phage(rbp_rows),
        compatibility_by_pair(compatibility_rows),
    )
    model_rows, feature_rows, error_rows = run_models(samples)
    hypothesis_summary_rows = build_hypothesis_summary(model_rows, feature_rows, display_path(Path(args.model_comparison_output)))
    add_report(
        report,
        "info",
        "models",
        f"Built {len(model_rows)} model/test rows, {len(feature_rows)} feature rows, {len(error_rows)} prediction rows, and {len(hypothesis_summary_rows)} hypothesis summary rows from {len(samples)} samples.",
    )

    write_tsv(Path(args.model_comparison_output), MODEL_COMPARISON_COLUMNS, model_rows)
    write_tsv(Path(args.feature_importance_output), FEATURE_IMPORTANCE_COLUMNS, feature_rows)
    write_tsv(Path(args.prediction_errors_output), PREDICTION_ERROR_COLUMNS, error_rows)
    write_tsv(Path(args.hypothesis_summary_output), HYPOTHESIS_SUMMARY_COLUMNS, hypothesis_summary_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)

    print(
        f"Compared {len(model_rows)} feature-set models/tests using {len(samples)} phage-host samples; "
        f"wrote {len(error_rows)} prediction rows and {len(hypothesis_summary_rows)} hypothesis summary rows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
