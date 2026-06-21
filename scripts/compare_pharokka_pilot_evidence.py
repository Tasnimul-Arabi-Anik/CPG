#!/usr/bin/env python3
"""Compare Pharokka pilot annotations against existing Prodigal/RBPbase candidates.

This is glue code only: it compares coordinates and product categories from
existing tool outputs. It does not implement gene prediction or RBP prediction.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote

RECEPTOR_FEATURES = {"receptor_binding", "tailspike", "tail_fiber", "baseplate"}
STRUCTURAL_FEATURES = {"tail_structural", "structural", "lysis"}

PHAGE_COLUMNS = [
    "phage_id",
    "selection_rank",
    "spot_positive_fraction",
    "tested_host_count",
    "pharokka_run_status",
    "pharokka_cds_count",
    "pharokka_keyword_rows",
    "pharokka_receptor_like_rows",
    "pharokka_tail_fiber_rows",
    "pharokka_tailspike_rows",
    "pharokka_receptor_binding_rows",
    "pharokka_baseplate_rows",
    "prodigal_rbpbase_candidate_count",
    "prodigal_candidates_with_any_pharokka_overlap",
    "prodigal_candidates_with_receptor_like_pharokka_overlap",
    "pharokka_receptor_like_rows_with_prodigal_candidate_overlap",
    "evidence_relationship",
    "recommended_next_action",
]

OVERLAP_COLUMNS = [
    "phage_id",
    "prodigal_candidate_id",
    "prodigal_gene_id",
    "prodigal_start",
    "prodigal_end",
    "prodigal_product",
    "pharokka_gene_id",
    "pharokka_start",
    "pharokka_end",
    "pharokka_product",
    "pharokka_feature_types",
    "overlap_bp",
    "overlap_fraction_of_shorter_feature",
    "relationship",
]

DECISION_COLUMNS = [
    "decision_item",
    "status",
    "evidence",
    "decision",
    "claim_boundary",
]

KEYWORDS = [
    ("depolymerase", ["depolymerase"]),
    ("receptor_binding", ["receptor-binding", "receptor binding", "host specificity", "host-specificity"]),
    ("tailspike", ["tailspike", "tail spike"]),
    ("tail_fiber", ["tail fiber", "tail fibre", "tail-fiber", "tail-fibre"]),
    ("baseplate", ["baseplate", "base plate"]),
    ("tail_structural", ["tail tube", "tail sheath", "tail protein", "tail completion", "tail terminator"]),
    ("structural", ["capsid", "portal", "terminase", "head", "virion", "structural"]),
    ("lysis", ["endolysin", "lysin", "holin", "spanin", "lysis"]),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Pharokka pilot outputs with Prodigal/RBPbase candidates.")
    parser.add_argument("--selection", default="results/pilot/pharokka_selection.tsv")
    parser.add_argument("--run-summary", default="results/pilot/pharokka_run_summary.tsv")
    parser.add_argument("--pharokka-keywords", default="results/pilot/pharokka_rbp_annotation_summary.tsv")
    parser.add_argument("--pharokka-output-dir", default="results/pilot/pharokka_output")
    parser.add_argument("--prodigal-cds", default="data/metadata/production_evidence/phagehostlearn_prodigal_cds_annotations.tsv")
    parser.add_argument("--candidates", default="results/production/rbp_depolymerase/candidates.tsv")
    parser.add_argument("--phage-output", default="results/pilot/pharokka_rbp_evidence_comparison.tsv")
    parser.add_argument("--overlap-output", default="results/pilot/pharokka_prodigal_rbp_overlap.tsv")
    parser.add_argument("--decision-output", default="results/pilot/pharokka_next_step_decision.tsv")
    parser.add_argument("--report-output", default="PILOT_REPORT.md")
    parser.add_argument("--overlap-threshold", type=float, default=0.80)
    return parser.parse_args()


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
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


def to_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_attrs(attrs: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in attrs.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            parsed[key] = unquote(value)
    return parsed


def classify_product(product: str) -> set[str]:
    lower = product.lower()
    out: set[str] = set()
    for label, terms in KEYWORDS:
        if any(term in lower for term in terms):
            out.add(label)
    return out


def interval_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> tuple[int, float]:
    a0, a1 = sorted((start_a, end_a))
    b0, b1 = sorted((start_b, end_b))
    left = max(a0, b0)
    right = min(a1, b1)
    overlap = max(0, right - left + 1)
    len_a = max(1, a1 - a0 + 1)
    len_b = max(1, b1 - b0 + 1)
    return overlap, overlap / min(len_a, len_b)


def load_pharokka_cds(pharokka_output_dir: Path, phage_id: str) -> list[dict[str, object]]:
    outdir = pharokka_output_dir / phage_id
    gff = outdir / f"{phage_id}.gff"
    rows: list[dict[str, object]] = []
    if not gff.exists():
        return rows
    with gff.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 9 or parts[2] != "CDS":
                continue
            attrs = parse_attrs(parts[8])
            product = attrs.get("product") or attrs.get("Name") or ""
            rows.append(
                {
                    "phage_id": phage_id,
                    "gene_id": attrs.get("ID") or attrs.get("locus_tag") or "",
                    "start": to_int(parts[3]),
                    "end": to_int(parts[4]),
                    "strand": parts[6],
                    "product": product,
                    "feature_types": classify_product(product),
                }
            )
    return rows


def command_available(command: list[str]) -> bool:
    completed = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return completed.returncode == 0


def relationship_for_counts(prodigal_count: int, pharokka_receptor: int, concordant: int) -> tuple[str, str]:
    if concordant > 0:
        return (
            "concordant_receptor_signal",
            "Review concordant loci first, then inspect Pharokka-only receptor-like rows.",
        )
    if pharokka_receptor > 0 and prodigal_count > 0:
        return (
            "discordant_gene_call_or_annotation_signal",
            "Inspect coordinate differences manually before scaling; gene callers disagree for receptor-like loci.",
        )
    if pharokka_receptor > 0:
        return (
            "pharokka_only_receptor_signal",
            "Inspect Pharokka receptor-like loci as possible missed RBPbase candidates.",
        )
    if prodigal_count > 0:
        return (
            "prodigal_rbpbase_only_signal",
            "Retain RBPbase candidates but require domain/structural support before claiming receptor function.",
        )
    return ("no_receptor_like_signal_in_current_tables", "No immediate receptor-candidate priority from current pilot evidence.")


def update_report(path: Path, phage_rows: list[dict[str, str]], overlap_rows: list[dict[str, str]], decision_rows: list[dict[str, str]]) -> None:
    completed = sum(1 for row in phage_rows if row.get("pharokka_run_status") == "completed")
    concordant = sum(1 for row in phage_rows if row.get("evidence_relationship") == "concordant_receptor_signal")
    pharokka_only = sum(1 for row in phage_rows if row.get("evidence_relationship") == "pharokka_only_receptor_signal")
    prodigal_only = sum(1 for row in phage_rows if row.get("evidence_relationship") == "prodigal_rbpbase_only_signal")
    receptor_rows = sum(to_int(row.get("pharokka_receptor_like_rows", "0")) for row in phage_rows)
    section = f"""\n## Pharokka/RBPbase Comparison\n\nThe 30-phage Pharokka pilot was compared with the existing Prodigal/RBPbase candidate layer using coordinate overlap. Completed Pharokka runs compared: {completed}/30. Pharokka receptor-like rows in the selected set: {receptor_rows}. Phages with concordant Pharokka receptor-like and Prodigal/RBPbase candidate loci: {concordant}. Pharokka-only receptor-like signal: {pharokka_only}. Prodigal/RBPbase-only signal: {prodigal_only}. Coordinate-level overlaps are in `results/pilot/pharokka_prodigal_rbp_overlap.tsv`; phage-level evidence relationships are in `results/pilot/pharokka_rbp_evidence_comparison.tsv`.\n\nDecision: do not claim receptor specificity or model superiority from this comparison. Use it to prioritize loci for structural/domain evidence. Phold/Foldseek are not currently available in the active or Pharokka environment, so the next implementation step is either install Phold/Foldseek for the 30-phage subset or manually review concordant/high-priority Pharokka loci before scaling to all 105 phages.\n"""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    marker = "\n## Pharokka/RBPbase Comparison\n"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + section
    else:
        text = text.rstrip() + section
    path.write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")


def main() -> int:
    args = parse_args()
    selection = read_tsv(Path(args.selection))
    runs = read_tsv(Path(args.run_summary))
    keywords = read_tsv(Path(args.pharokka_keywords))
    candidates = read_tsv(Path(args.candidates))
    prodigal_cds = read_tsv(Path(args.prodigal_cds))

    selected_ids = [row.get("phage_id", "") for row in selection if row.get("phage_id")]
    run_by_phage = {row.get("phage_id", ""): row for row in runs}
    selection_by_phage = {row.get("phage_id", ""): row for row in selection}

    keyword_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in keywords:
        phage = row.get("phage_id", "")
        if phage in selected_ids:
            keyword_counts[phage][row.get("feature_type", "")] += 1

    candidates_by_phage: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        phage = row.get("genome_id", "")
        if phage in selected_ids:
            candidates_by_phage[phage].append(row)

    prodigal_by_key = {(row.get("genome_id", ""), row.get("gene_id", "")): row for row in prodigal_cds}

    phage_rows: list[dict[str, str]] = []
    overlap_rows: list[dict[str, str]] = []
    pharokka_output_dir = Path(args.pharokka_output_dir)

    for phage in selected_ids:
        pharokka_cds = load_pharokka_cds(pharokka_output_dir, phage)
        pharokka_receptor_like = [row for row in pharokka_cds if row["feature_types"] & RECEPTOR_FEATURES]
        candidate_rows = candidates_by_phage.get(phage, [])
        candidates_with_any = set()
        candidates_with_receptor = set()
        pharokka_receptor_with_candidate = set()

        for candidate in candidate_rows:
            prodigal = prodigal_by_key.get((phage, candidate.get("gene_id", "")))
            if not prodigal:
                continue
            p_start = to_int(prodigal.get("start", "0"))
            p_end = to_int(prodigal.get("end", "0"))
            best: tuple[float, int, dict[str, object] | None] = (0.0, 0, None)
            for pharokka in pharokka_cds:
                overlap_bp, overlap_fraction = interval_overlap(p_start, p_end, int(pharokka["start"]), int(pharokka["end"]))
                if overlap_fraction > best[0]:
                    best = (overlap_fraction, overlap_bp, pharokka)
            if best[2] is None or best[0] < args.overlap_threshold:
                continue
            pharokka = best[2]
            feature_types = set(pharokka["feature_types"])
            relationship = "coordinate_overlap"
            candidates_with_any.add(candidate.get("candidate_id", ""))
            if feature_types & RECEPTOR_FEATURES:
                relationship = "coordinate_overlap_receptor_like"
                candidates_with_receptor.add(candidate.get("candidate_id", ""))
                pharokka_receptor_with_candidate.add(str(pharokka["gene_id"]))
            overlap_rows.append(
                {
                    "phage_id": phage,
                    "prodigal_candidate_id": candidate.get("candidate_id", ""),
                    "prodigal_gene_id": candidate.get("gene_id", ""),
                    "prodigal_start": str(p_start),
                    "prodigal_end": str(p_end),
                    "prodigal_product": prodigal.get("product", candidate.get("product", "")),
                    "pharokka_gene_id": str(pharokka["gene_id"]),
                    "pharokka_start": str(pharokka["start"]),
                    "pharokka_end": str(pharokka["end"]),
                    "pharokka_product": str(pharokka["product"]),
                    "pharokka_feature_types": ";".join(sorted(feature_types)) if feature_types else "none",
                    "overlap_bp": str(best[1]),
                    "overlap_fraction_of_shorter_feature": f"{best[0]:.3f}",
                    "relationship": relationship,
                }
            )

        receptor_count = sum(keyword_counts[phage][feature] for feature in RECEPTOR_FEATURES)
        relationship, next_action = relationship_for_counts(len(candidate_rows), receptor_count, len(candidates_with_receptor))
        selected = selection_by_phage.get(phage, {})
        phage_rows.append(
            {
                "phage_id": phage,
                "selection_rank": selected.get("selection_rank", ""),
                "spot_positive_fraction": selected.get("spot_positive_fraction", ""),
                "tested_host_count": selected.get("tested_host_count", ""),
                "pharokka_run_status": run_by_phage.get(phage, {}).get("status", "not_run"),
                "pharokka_cds_count": str(len(pharokka_cds)),
                "pharokka_keyword_rows": str(sum(keyword_counts[phage].values())),
                "pharokka_receptor_like_rows": str(receptor_count),
                "pharokka_tail_fiber_rows": str(keyword_counts[phage]["tail_fiber"]),
                "pharokka_tailspike_rows": str(keyword_counts[phage]["tailspike"]),
                "pharokka_receptor_binding_rows": str(keyword_counts[phage]["receptor_binding"]),
                "pharokka_baseplate_rows": str(keyword_counts[phage]["baseplate"]),
                "prodigal_rbpbase_candidate_count": str(len(candidate_rows)),
                "prodigal_candidates_with_any_pharokka_overlap": str(len(candidates_with_any)),
                "prodigal_candidates_with_receptor_like_pharokka_overlap": str(len(candidates_with_receptor)),
                "pharokka_receptor_like_rows_with_prodigal_candidate_overlap": str(len(pharokka_receptor_with_candidate)),
                "evidence_relationship": relationship,
                "recommended_next_action": next_action,
            }
        )

    phold_available = command_available(["bash", "-lc", "command -v phold >/dev/null 2>&1"]) or command_available(["mamba", "run", "-n", "pharokka", "which", "phold"])
    foldseek_available = command_available(["bash", "-lc", "command -v foldseek >/dev/null 2>&1"]) or command_available(["mamba", "run", "-n", "pharokka", "which", "foldseek"])
    completed = sum(1 for row in phage_rows if row["pharokka_run_status"] == "completed")
    concordant = sum(1 for row in phage_rows if row["evidence_relationship"] == "concordant_receptor_signal")
    receptor_phages = sum(1 for row in phage_rows if to_int(row["pharokka_receptor_like_rows"]) > 0)

    if phold_available and foldseek_available:
        structural_decision = "Run Phold/Foldseek on the 30-phage subset before scaling."
        structural_status = "available"
    else:
        structural_decision = "Install Phold/Foldseek or defer structural claims; do not substitute custom structure inference."
        structural_status = "blocked_not_available"

    decision_rows = [
        {
            "decision_item": "scale_pharokka_to_all_105",
            "status": "defer",
            "evidence": f"completed_30={completed}; receptor_like_phages={receptor_phages}; concordant_phages={concordant}",
            "decision": "Review 30-phage comparison first; scale only after confirming the annotation signal is useful.",
            "claim_boundary": "Scaling annotation does not validate receptor specificity or host-range prediction.",
        },
        {
            "decision_item": "run_structural_annotation",
            "status": structural_status,
            "evidence": f"phold_available={phold_available}; foldseek_available={foldseek_available}",
            "decision": structural_decision,
            "claim_boundary": "No structural novelty or remote-homology claims without accepted structural evidence.",
        },
        {
            "decision_item": "use_for_modeling",
            "status": "blocked",
            "evidence": "Pharokka pilot provides annotation evidence only; no leakage-safe receptor model has been run.",
            "decision": "Do not use these rows as claim-ready model evidence yet.",
            "claim_boundary": "No claim that RBP modules outperform taxonomy from this pilot comparison.",
        },
    ]

    write_tsv(Path(args.phage_output), PHAGE_COLUMNS, phage_rows)
    write_tsv(Path(args.overlap_output), OVERLAP_COLUMNS, overlap_rows)
    write_tsv(Path(args.decision_output), DECISION_COLUMNS, decision_rows)
    update_report(Path(args.report_output), phage_rows, overlap_rows, decision_rows)
    print(
        f"Pharokka comparison complete: phages={len(phage_rows)}; overlaps={len(overlap_rows)}; "
        f"receptor_like_phages={receptor_phages}; concordant_phages={concordant}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
