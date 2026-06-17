#!/usr/bin/env python3
"""Cluster phage-like genomes from a manifest using optional pairwise similarity."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable


ELIGIBLE_RECORD_TYPES = {"phage", "prophage", "metagenomic_viral_contig"}
SIMILARITY_COLUMNS = [
    "genome_id_1",
    "genome_id_2",
    "identity_percent",
    "coverage_percent",
    "method",
]
ANI_OUTPUT_COLUMNS = SIMILARITY_COLUMNS + [
    "passes_threshold",
    "included_in_clustering",
    "notes",
]
CLUSTER_COLUMNS = [
    "genome_id",
    "record_type",
    "cluster_id",
    "representative_id",
    "cluster_size",
    "identity_threshold_percent",
    "coverage_threshold_percent",
    "sequence_qc_status",
    "passes_sequence_qc",
    "clustering_basis",
    "notes",
]
REPRESENTATIVE_COLUMNS = [
    "cluster_id",
    "representative_id",
    "cluster_size",
    "member_genome_ids",
    "representative_reason",
    "representative_sequence_qc_status",
    "identity_threshold_percent",
    "coverage_threshold_percent",
]
REPORT_COLUMNS = ["severity", "item", "message"]


class UnionFind:
    def __init__(self, items: Iterable[str]) -> None:
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Dereplicate phage-like records from a manifest. If a pairwise "
            "similarity table is supplied, records passing identity and coverage "
            "thresholds are unioned into species-like clusters. Without that "
            "table, each eligible genome is emitted as a singleton cluster."
        )
    )
    parser.add_argument("--manifest", required=True, help="Stage 1 manifest TSV.")
    parser.add_argument("--thresholds", required=True, help="Threshold YAML file.")
    parser.add_argument(
        "--pairwise-similarity",
        default="",
        help="Optional TSV with genome_id_1, genome_id_2, identity_percent, coverage_percent, method.",
    )
    parser.add_argument(
        "--sequence-qc",
        default="",
        help="Optional Stage 1 sequence QC TSV. Local sequence failures are excluded when configured.",
    )
    parser.add_argument("--ani-output", required=True, help="Output normalized pairwise similarity TSV.")
    parser.add_argument("--clusters-output", required=True, help="Output cluster membership TSV.")
    parser.add_argument("--representatives-output", required=True, help="Output representative genomes TSV.")
    parser.add_argument("--report-output", required=True, help="Output dereplication report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in {"", "NA", "N/A", "na", "n/a", "None", "none"}


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(f"Required input does not exist: {path}")
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [
            {key: (value or "").strip() for key, value in row.items()}
            for row in reader
        ]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def load_thresholds(path: Path) -> tuple[float, float, bool]:
    default_identity = 95.0
    default_coverage = 85.0
    default_exclude_failed_qc = True
    text = path.read_text(encoding="utf-8")

    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        dereplication = data.get("dereplication", {}) if isinstance(data, dict) else {}
        identity = float(
            dereplication.get("species_like_identity_percent", default_identity)
        )
        coverage = float(
            dereplication.get("species_like_coverage_percent", default_coverage)
        )
        genome_qc = data.get("genome_qc", {}) if isinstance(data, dict) else {}
        exclude_failed_qc = bool_value(
            genome_qc.get("exclude_failed_local_sequence_qc_from_clustering", default_exclude_failed_qc),
            default_exclude_failed_qc,
        )
        return identity, coverage, exclude_failed_qc
    except Exception:
        identity = _extract_numeric_threshold(
            text, "species_like_identity_percent", default_identity
        )
        coverage = _extract_numeric_threshold(
            text, "species_like_coverage_percent", default_coverage
        )
        exclude_failed_qc = _extract_bool_threshold(
            text, "exclude_failed_local_sequence_qc_from_clustering", default_exclude_failed_qc
        )
        return identity, coverage, exclude_failed_qc


def bool_value(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    text = "" if value is None else str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return default


def _extract_numeric_threshold(text: str, key: str, default: float) -> float:
    match = re.search(rf"^\s*{re.escape(key)}\s*:\s*([0-9]+(?:\.[0-9]+)?)", text, re.M)
    return float(match.group(1)) if match else default


def _extract_bool_threshold(text: str, key: str, default: bool) -> bool:
    match = re.search(rf"^\s*{re.escape(key)}\s*:\s*(true|false|yes|no|1|0|on|off)", text, re.M | re.I)
    return bool_value(match.group(1), default) if match else default


def load_sequence_qc_rows(path_text: str, report: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    if is_missing(path_text):
        report.append(
            {
                "severity": "info",
                "item": "sequence_qc",
                "message": "No sequence QC table supplied; manifest-only eligibility was used.",
            }
        )
        return {}
    path = Path(path_text)
    if not path.exists():
        report.append(
            {
                "severity": "warning",
                "item": "sequence_qc",
                "message": f"Sequence QC table does not exist: {path}; manifest-only eligibility was used.",
            }
        )
        return {}
    fieldnames, rows = read_tsv(path)
    required = ["genome_id", "sequence_qc_status", "passes_sequence_qc"]
    missing = [column for column in required if column not in fieldnames]
    if missing:
        report.append(
            {
                "severity": "error",
                "item": "sequence_qc",
                "message": "Sequence QC table missing required columns: " + ", ".join(missing),
            }
        )
        return {}
    by_id = {row.get("genome_id", ""): row for row in rows if not is_missing(row.get("genome_id"))}
    report.append(
        {
            "severity": "info",
            "item": "sequence_qc",
            "message": f"Loaded {len(by_id)} sequence QC rows from {path}.",
        }
    )
    return by_id


def local_sequence_qc_failed(qc_row: dict[str, str]) -> bool:
    status = qc_row.get("sequence_qc_status", "")
    if status in {"", "no_sequence_provided"}:
        return False
    return qc_row.get("passes_sequence_qc", "").lower() != "true"


def eligible_manifest_rows(
    rows: list[dict[str, str]],
    sequence_qc_by_id: dict[str, dict[str, str]],
    exclude_failed_qc: bool,
    report: list[dict[str, str]],
) -> list[dict[str, str]]:
    eligible: list[dict[str, str]] = []
    excluded_by_sequence_qc = 0
    for row in rows:
        if row.get("record_type") not in ELIGIBLE_RECORD_TYPES:
            continue
        if row.get("validation_status", "pass") not in {"", "pass"}:
            continue
        if is_missing(row.get("genome_id")):
            continue
        prepared = dict(row)
        qc_row = sequence_qc_by_id.get(row["genome_id"], {})
        prepared["sequence_qc_status"] = qc_row.get("sequence_qc_status", "not_provided")
        prepared["passes_sequence_qc"] = qc_row.get("passes_sequence_qc", "NA")
        if exclude_failed_qc and local_sequence_qc_failed(qc_row):
            excluded_by_sequence_qc += 1
            continue
        eligible.append(prepared)
    if excluded_by_sequence_qc:
        report.append(
            {
                "severity": "warning",
                "item": "sequence_qc",
                "message": f"Excluded {excluded_by_sequence_qc} records with failing local sequence QC.",
            }
        )
    return eligible


def parse_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def load_pairwise_rows(
    path_text: str,
    eligible_ids: set[str],
    identity_threshold: float,
    coverage_threshold: float,
    report: list[dict[str, str]],
) -> list[dict[str, str]]:
    if is_missing(path_text):
        report.append(
            {
                "severity": "info",
                "item": "pairwise_similarity",
                "message": "No pairwise similarity table supplied; singleton clusters were emitted.",
            }
        )
        return []

    path = Path(path_text)
    if not path.exists():
        report.append(
            {
                "severity": "warning",
                "item": "pairwise_similarity",
                "message": f"Pairwise similarity table does not exist: {path}; singleton clusters were emitted.",
            }
        )
        return []

    fieldnames, raw_rows = read_tsv(path)
    missing = [column for column in SIMILARITY_COLUMNS if column not in fieldnames]
    if missing:
        report.append(
            {
                "severity": "error",
                "item": "pairwise_similarity",
                "message": "Pairwise similarity table missing required columns: " + ", ".join(missing),
            }
        )
        return []

    normalized: list[dict[str, str]] = []
    for index, row in enumerate(raw_rows, start=2):
        genome_id_1 = row.get("genome_id_1", "")
        genome_id_2 = row.get("genome_id_2", "")
        identity = parse_float(row.get("identity_percent", ""))
        coverage = parse_float(row.get("coverage_percent", ""))
        notes: list[str] = []

        if identity is None:
            notes.append(f"row {index}: invalid identity_percent")
        if coverage is None:
            notes.append(f"row {index}: invalid coverage_percent")
        if genome_id_1 not in eligible_ids or genome_id_2 not in eligible_ids:
            notes.append("one or both genomes are not eligible phage-like manifest records")

        passes = (
            identity is not None
            and coverage is not None
            and identity >= identity_threshold
            and coverage >= coverage_threshold
        )
        included = passes and not notes
        normalized.append(
            {
                "genome_id_1": genome_id_1,
                "genome_id_2": genome_id_2,
                "identity_percent": row.get("identity_percent", ""),
                "coverage_percent": row.get("coverage_percent", ""),
                "method": row.get("method", "unspecified"),
                "passes_threshold": str(passes).lower(),
                "included_in_clustering": str(included).lower(),
                "notes": "; ".join(notes) if notes else "OK",
            }
        )

    report.append(
        {
            "severity": "info",
            "item": "pairwise_similarity",
            "message": f"Loaded {len(normalized)} pairwise similarity rows from {path}.",
        }
    )
    return normalized


def choose_representative(members: list[dict[str, str]]) -> tuple[str, str]:
    def sort_key(row: dict[str, str]) -> tuple[int, int, int, int, int, str]:
        passes_sequence_qc = 1 if row.get("passes_sequence_qc") == "true" else 0
        has_raw_sequence = 1 if row.get("raw_sequence_exists") == "true" else 0
        has_accession = 0 if is_missing(row.get("accession")) else 1
        has_source = 0 if is_missing(row.get("source")) else 1
        genome_length = parse_int(row.get("genome_length", "0"))
        return (-passes_sequence_qc, -has_raw_sequence, -has_accession, -has_source, -genome_length, row["genome_id"])

    selected = sorted(members, key=sort_key)[0]
    reason_parts = []
    if selected.get("passes_sequence_qc") == "true":
        reason_parts.append("local sequence QC passed")
    if selected.get("raw_sequence_exists") == "true":
        reason_parts.append("local sequence exists")
    if not is_missing(selected.get("accession")):
        reason_parts.append("has accession")
    if not is_missing(selected.get("source")):
        reason_parts.append("has source metadata")
    if not is_missing(selected.get("genome_length")):
        reason_parts.append("longest or tied-longest genome after metadata priorities")
    if not reason_parts:
        reason_parts.append("lexicographic fallback")
    return selected["genome_id"], "; ".join(reason_parts)


def build_clusters(
    manifest_rows: list[dict[str, str]],
    pairwise_rows: list[dict[str, str]],
    identity_threshold: float,
    coverage_threshold: float,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows_by_id = {row["genome_id"]: row for row in manifest_rows}
    uf = UnionFind(rows_by_id)
    pairwise_linked_ids: set[str] = set()

    for row in pairwise_rows:
        if row.get("included_in_clustering") == "true":
            uf.union(row["genome_id_1"], row["genome_id_2"])
            pairwise_linked_ids.update([row["genome_id_1"], row["genome_id_2"]])

    grouped: dict[str, list[dict[str, str]]] = {}
    for genome_id, manifest_row in rows_by_id.items():
        grouped.setdefault(uf.find(genome_id), []).append(manifest_row)

    sorted_groups = sorted(
        grouped.values(), key=lambda members: sorted(row["genome_id"] for row in members)[0]
    )

    cluster_rows: list[dict[str, str]] = []
    representative_rows: list[dict[str, str]] = []

    for index, members in enumerate(sorted_groups, start=1):
        cluster_id = f"kp_phage_species_{index:05d}"
        sorted_members = sorted(members, key=lambda row: row["genome_id"])
        representative_id, reason = choose_representative(sorted_members)
        member_ids = [row["genome_id"] for row in sorted_members]
        if len(sorted_members) > 1 and any(genome_id in pairwise_linked_ids for genome_id in member_ids):
            basis = "pairwise_similarity_threshold"
        elif pairwise_rows:
            basis = "singleton_no_threshold_pairwise_link"
        else:
            basis = "singleton_no_pairwise_similarity"
        representative_rows.append(
            {
                "cluster_id": cluster_id,
                "representative_id": representative_id,
                "cluster_size": str(len(sorted_members)),
                "member_genome_ids": ";".join(member_ids),
                "representative_reason": reason,
                "representative_sequence_qc_status": next((row.get("sequence_qc_status", "") for row in sorted_members if row["genome_id"] == representative_id), ""),
                "identity_threshold_percent": f"{identity_threshold:g}",
                "coverage_threshold_percent": f"{coverage_threshold:g}",
            }
        )
        for row in sorted_members:
            cluster_rows.append(
                {
                    "genome_id": row["genome_id"],
                    "record_type": row.get("record_type", ""),
                    "cluster_id": cluster_id,
                    "representative_id": representative_id,
                    "cluster_size": str(len(sorted_members)),
                    "identity_threshold_percent": f"{identity_threshold:g}",
                    "coverage_threshold_percent": f"{coverage_threshold:g}",
                    "sequence_qc_status": row.get("sequence_qc_status", "not_provided"),
                    "passes_sequence_qc": row.get("passes_sequence_qc", "NA"),
                    "clustering_basis": basis,
                    "notes": "OK",
                }
            )

    return cluster_rows, representative_rows


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest)
    thresholds_path = Path(args.thresholds)

    identity_threshold, coverage_threshold, exclude_failed_qc = load_thresholds(thresholds_path)
    report: list[dict[str, str]] = [
        {
            "severity": "info",
            "item": "thresholds",
            "message": (
                f"Using identity >= {identity_threshold:g}% and coverage >= "
                f"{coverage_threshold:g}% for species-like clustering; "
                f"exclude_failed_local_sequence_qc_from_clustering={exclude_failed_qc}."
            ),
        }
    ]

    _, manifest_rows = read_tsv(manifest_path)
    sequence_qc_by_id = load_sequence_qc_rows(args.sequence_qc, report)
    eligible_rows = eligible_manifest_rows(manifest_rows, sequence_qc_by_id, exclude_failed_qc, report)
    eligible_ids = {row["genome_id"] for row in eligible_rows}
    report.append(
        {
            "severity": "info",
            "item": "manifest",
            "message": f"Found {len(eligible_rows)} eligible phage-like records in {manifest_path}.",
        }
    )

    pairwise_rows = load_pairwise_rows(
        args.pairwise_similarity,
        eligible_ids,
        identity_threshold,
        coverage_threshold,
        report,
    )
    cluster_rows, representative_rows = build_clusters(
        eligible_rows,
        pairwise_rows,
        identity_threshold,
        coverage_threshold,
    )

    write_tsv(Path(args.ani_output), ANI_OUTPUT_COLUMNS, pairwise_rows)
    write_tsv(Path(args.clusters_output), CLUSTER_COLUMNS, cluster_rows)
    write_tsv(Path(args.representatives_output), REPRESENTATIVE_COLUMNS, representative_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)

    error_count = sum(1 for row in report if row["severity"] == "error")
    print(
        f"Dereplicated {len(eligible_rows)} eligible records into "
        f"{len(representative_rows)} clusters using identity >= {identity_threshold:g}% "
        f"and coverage >= {coverage_threshold:g}%."
    )
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
