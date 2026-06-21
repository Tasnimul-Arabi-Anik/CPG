#!/usr/bin/env python3
"""Reconcile receptor-feature evidence sources for assay phages.

This script summarizes existing evidence tables from PhageHostLearn RBPbase,
Prodigal exact CDS matches, Pharokka product annotations, and Phold/Foldseek
structural annotations. It does not predict receptor specificity.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

SOURCE_COLUMNS = [
    "source_name",
    "evidence_class",
    "phage_count",
    "row_count",
    "candidate_cds_or_protein_count",
    "tail_fiber_rows",
    "tailspike_rows",
    "receptor_binding_rows",
    "depolymerase_rows",
    "baseplate_rows",
    "non_pharokka_rows",
    "claim_boundary",
]

MISSING_COLUMNS = [
    "source_phage_id",
    "phage_id",
    "protein_id",
    "xgb_score",
    "protein_length_aa",
    "missing_reason",
    "review_action",
    "claim_boundary",
]

SUMMARY_COLUMNS = ["metric", "value", "interpretation"]

RECEPTOR_FEATURES = {"tail_fiber", "tailspike", "receptor_binding", "depolymerase", "baseplate"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rbpbase", default="data/metadata/external/phagehostlearn/RBPbase.csv")
    parser.add_argument("--phage-map", default="data/metadata/assay_source_exports/phagehostlearn_2024_phage_id_map.tsv")
    parser.add_argument(
        "--prodigal-annotations",
        default="data/metadata/production_evidence/phagehostlearn_prodigal_cds_annotations.tsv",
    )
    parser.add_argument(
        "--pharokka-annotations",
        default="results/production/pharokka_assay_phage_annotation_summary.tsv",
    )
    parser.add_argument("--phold-hits", default="results/production/phold_assay_phage_relevant_hits.tsv")
    parser.add_argument(
        "--phold-review",
        default="results/production/receptor_features/phold_non_pharokka_receptor_review.tsv",
    )
    parser.add_argument(
        "--source-output",
        default="results/production/receptor_features/receptor_source_reconciliation.tsv",
    )
    parser.add_argument(
        "--missing-rbpbase-output",
        default="results/production/receptor_features/receptor_source_reconciliation_missing_rbpbase.tsv",
    )
    parser.add_argument(
        "--summary-output",
        default="results/production/receptor_features/receptor_source_reconciliation_summary.tsv",
    )
    parser.add_argument("--report-output", default="PILOT_REPORT.md")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: "" if value is None else value for key, value in row.items()} for row in csv.DictReader(handle)]


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


def source_to_canonical_map(path: Path) -> dict[str, str]:
    rows = read_tsv(path)
    mapping: dict[str, str] = {}
    for row in rows:
        source_id = row.get("source_id", "")
        canonical_id = row.get("canonical_id", "")
        status = row.get("review_status", "").lower()
        if source_id and canonical_id and status in {"reviewed", "accepted", "pass"}:
            mapping[source_id] = canonical_id
    return mapping


def to_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


def source_row(
    source_name: str,
    evidence_class: str,
    phages: set[str],
    row_count: int,
    candidate_count: int,
    feature_counts: Counter[str],
    non_pharokka_rows: int,
    claim_boundary: str,
) -> dict[str, str]:
    return {
        "source_name": source_name,
        "evidence_class": evidence_class,
        "phage_count": str(len(phages)),
        "row_count": str(row_count),
        "candidate_cds_or_protein_count": str(candidate_count),
        "tail_fiber_rows": str(feature_counts.get("tail_fiber", 0)),
        "tailspike_rows": str(feature_counts.get("tailspike", 0)),
        "receptor_binding_rows": str(feature_counts.get("receptor_binding", 0)),
        "depolymerase_rows": str(feature_counts.get("depolymerase", 0)),
        "baseplate_rows": str(feature_counts.get("baseplate", 0)),
        "non_pharokka_rows": str(non_pharokka_rows),
        "claim_boundary": claim_boundary,
    }


def build_missing_rbpbase_rows(
    rbpbase_rows: list[dict[str, str]],
    source_map: dict[str, str],
    exact_match_sequences: set[str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in rbpbase_rows:
        sequence = row.get("protein_sequence", "")
        if sequence in exact_match_sequences:
            continue
        source_phage = row.get("phage_ID", "")
        rows.append(
            {
                "source_phage_id": source_phage,
                "phage_id": source_map.get(source_phage, ""),
                "protein_id": row.get("protein_ID", ""),
                "xgb_score": row.get("xgb_score", ""),
                "protein_length_aa": str(len(sequence)),
                "missing_reason": "RBPbase protein sequence does not exact-match any current Prodigal CDS protein sequence.",
                "review_action": "Inspect gene-calling boundary, alternative start/stop, archive member identity, and whether the RBPbase protein should be carried as external published candidate evidence rather than exact CDS evidence.",
                "claim_boundary": "Published RBPbase candidate missing from current exact CDS match set; not negative evidence for receptor function.",
            }
        )
    rows.sort(key=lambda item: (item["source_phage_id"], item["protein_id"]))
    return rows


def add_report(path: Path, summary: list[dict[str, str]]) -> None:
    values = {row["metric"]: row["value"] for row in summary}
    section = f"""

## Receptor Feature Source Reconciliation

Receptor evidence sources were reconciled in `results/production/receptor_features/receptor_source_reconciliation.tsv`. The reviewed PhageHostLearn RBPbase source contains {values.get('rbpbase_source_rows', '0')} candidate proteins across {values.get('rbpbase_source_phages', '0')} assay phages. Current Prodigal CDS exact protein matching recovers {values.get('rbpbase_exact_cds_match_rows', '0')} of those candidates; {values.get('rbpbase_missing_exact_cds_match_rows', '0')} RBPbase proteins do not exact-match a current Prodigal CDS protein and are listed in `results/production/receptor_features/receptor_source_reconciliation_missing_rbpbase.tsv`.

Pharokka contributes {values.get('pharokka_receptor_like_rows', '0')} receptor-like keyword rows, while Phold/Foldseek contributes {values.get('phold_receptor_like_rows', '0')} receptor-like feature rows, including {values.get('phold_non_pharokka_receptor_like_rows', '0')} non-Pharokka structural remote-homology rows. These counts are evidence-source reconciliation, not additive validated receptor loci.

Claim boundary: RBPbase, Pharokka, and Phold evidence rows are candidate-prioritization signals. They do not prove capsule specificity, depolymerase activity, productive infection, or H1 model superiority.
"""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    marker = "\n## Receptor Feature Source Reconciliation\n"
    if marker in text:
        before, rest = text.split(marker, 1)
        after = ""
        next_marker = rest.find("\n## ")
        if next_marker != -1:
            after = rest[next_marker:]
        text = before.rstrip() + section + after
    else:
        insert_before = "\n## H1 Receptor-Layer Model Comparison\n"
        if insert_before in text:
            before, after = text.split(insert_before, 1)
            text = before.rstrip() + section + insert_before + after
        else:
            text = text.rstrip() + section
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    rbpbase = read_csv(Path(args.rbpbase))
    source_map = source_to_canonical_map(Path(args.phage_map))
    prodigal = read_tsv(Path(args.prodigal_annotations))
    pharokka = read_tsv(Path(args.pharokka_annotations))
    phold = read_tsv(Path(args.phold_hits))
    phold_review = read_tsv(Path(args.phold_review))

    rbpbase_phages = {source_map.get(row.get("phage_ID", ""), "") for row in rbpbase if source_map.get(row.get("phage_ID", ""), "")}
    exact_rbpbase_rows = [
        row
        for row in prodigal
        if row.get("functional_category") == "receptor_binding_candidate"
        or row.get("product") == "RBPbase receptor-binding protein candidate"
    ]
    exact_match_sequences = {row.get("protein_sequence", "") for row in exact_rbpbase_rows if row.get("protein_sequence", "")}
    missing_rbpbase = build_missing_rbpbase_rows(rbpbase, source_map, exact_match_sequences)

    pharokka_feature_counts = Counter(row.get("feature_type", "") for row in pharokka if row.get("feature_type", "") in RECEPTOR_FEATURES)
    pharokka_receptor = [row for row in pharokka if row.get("feature_type", "") in RECEPTOR_FEATURES]

    phold_receptor = [row for row in phold if row.get("feature_type", "") in RECEPTOR_FEATURES]
    phold_feature_counts = Counter(row.get("feature_type", "") for row in phold_receptor)
    phold_non_pharokka = [row for row in phold_receptor if row.get("annotation_method", "").lower() != "pharokka"]

    phold_review_counts = Counter(row.get("evidence_tier", "") for row in phold_review)

    source_rows = [
        source_row(
            "PhageHostLearn_RBPbase_source",
            "published_ml_candidate_proteins",
            rbpbase_phages,
            len(rbpbase),
            len(rbpbase),
            Counter(),
            0,
            "Published RBPbase candidate proteins from PhageHostLearn; candidate evidence, not functional receptor proof.",
        ),
        source_row(
            "Prodigal_exact_RBPbase_CDS_matches",
            "sequence_backed_exact_cds_matches_to_rbpbase",
            {row.get("genome_id", "") for row in exact_rbpbase_rows if row.get("genome_id", "")},
            len(exact_rbpbase_rows),
            len(exact_rbpbase_rows),
            Counter({"receptor_binding": len(exact_rbpbase_rows)}),
            0,
            "Exact protein-sequence matches between current Prodigal CDS calls and RBPbase candidates; not domain/structural proof.",
        ),
        source_row(
            "Pharokka_keyword_receptor_like_rows",
            "standardized_product_annotation_keywords",
            {row.get("phage_id", "") for row in pharokka_receptor if row.get("phage_id", "")},
            len(pharokka),
            len(pharokka_receptor),
            pharokka_feature_counts,
            0,
            "Pharokka product annotation keyword evidence; not capsule specificity or functional validation.",
        ),
        source_row(
            "Phold_Foldseek_receptor_like_rows",
            "structure_informed_annotation_keywords",
            {row.get("phage_id", "") for row in phold_receptor if row.get("phage_id", "")},
            len(phold),
            len(phold_receptor),
            phold_feature_counts,
            len(phold_non_pharokka),
            "Phold/Foldseek receptor-like structural annotation; candidate prioritization only.",
        ),
        source_row(
            "Phold_non_Pharokka_manual_review_rows",
            "remote_homology_manual_review_targets",
            {row.get("phage_id", "") for row in phold_review if row.get("phage_id", "")},
            len(phold_review),
            len(phold_review),
            Counter(row.get("feature_type", "") for row in phold_review),
            len(phold_review),
            "Non-Pharokka Phold/Foldseek review targets; not accepted receptor-function evidence.",
        ),
    ]

    summary = [
        {
            "metric": "rbpbase_source_rows",
            "value": str(len(rbpbase)),
            "interpretation": "Original PhageHostLearn RBPbase candidate protein rows.",
        },
        {
            "metric": "rbpbase_source_phages",
            "value": str(len(rbpbase_phages)),
            "interpretation": "Assay phages with at least one original RBPbase candidate.",
        },
        {
            "metric": "rbpbase_exact_cds_match_rows",
            "value": str(len(exact_rbpbase_rows)),
            "interpretation": "Current Prodigal CDS rows that exactly match an RBPbase candidate protein sequence.",
        },
        {
            "metric": "rbpbase_missing_exact_cds_match_rows",
            "value": str(len(missing_rbpbase)),
            "interpretation": "Original RBPbase candidate proteins not recovered as exact current Prodigal CDS protein matches.",
        },
        {
            "metric": "pharokka_receptor_like_rows",
            "value": str(len(pharokka_receptor)),
            "interpretation": "Pharokka rows with receptor-like keyword feature labels.",
        },
        {
            "metric": "phold_receptor_like_rows",
            "value": str(len(phold_receptor)),
            "interpretation": "Phold relevant-hit feature rows with receptor-like labels; feature-level count, not unique loci.",
        },
        {
            "metric": "phold_non_pharokka_receptor_like_rows",
            "value": str(len(phold_non_pharokka)),
            "interpretation": "Phold receptor-like rows assigned by non-Pharokka methods.",
        },
        {
            "metric": "phold_non_pharokka_high_priority_review_rows",
            "value": str(phold_review_counts.get("high_priority_candidate", 0)),
            "interpretation": "Non-Pharokka Phold/Foldseek review rows ranked high-priority by confidence, coverage, and label specificity.",
        },
        {
            "metric": "rbpbase_missing_high_score_ge_0_9_rows",
            "value": str(sum(1 for row in missing_rbpbase if to_float(row.get("xgb_score", "")) >= 0.9)),
            "interpretation": "Missing exact CDS matches among high-scoring RBPbase candidates; review before treating exact-match set as complete.",
        },
    ]

    write_tsv(Path(args.source_output), SOURCE_COLUMNS, source_rows)
    write_tsv(Path(args.missing_rbpbase_output), MISSING_COLUMNS, missing_rbpbase)
    write_tsv(Path(args.summary_output), SUMMARY_COLUMNS, summary)
    add_report(Path(args.report_output), summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
