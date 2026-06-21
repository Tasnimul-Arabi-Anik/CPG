#!/usr/bin/env python3
"""Build pilot-facing summaries from current production CPG outputs.

This script is intentionally glue-only: it does not implement annotation,
clustering, receptor prediction, host typing, or defense detection. It reads
existing reviewed/tool outputs and writes a compact pilot audit plus report.
"""

from __future__ import annotations

import argparse
import csv
import math
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}

DATA_AUDIT_COLUMNS = [
    "entity_id",
    "record_type",
    "source",
    "sequence_path",
    "sequence_qc_status",
    "sequence_verified",
    "genome_length_bp",
    "number_of_contigs",
    "complete_status",
    "isolation_host",
    "tested_host_count",
    "spot_positive_host_count",
    "host_range_data_available",
    "host_genome_available",
    "K_type_available",
    "O_type_available",
    "ST_available",
    "metadata_source",
    "include_in_pilot",
    "exclusion_reason",
]

HOST_RANGE_COLUMNS = [
    "phage_id",
    "study_id",
    "panel_id",
    "tested_host_count",
    "spot_positive_host_count",
    "spot_negative_host_count",
    "spot_positive_fraction",
    "spot_positive_fraction_ci95_low",
    "spot_positive_fraction_ci95_high",
    "productive_infection_measured_count",
    "interpretation",
]

RBP_COLUMNS = [
    "phage_id",
    "candidate_count",
    "high_confidence_count",
    "sequence_evidence_count",
    "domain_evidence_count",
    "structural_evidence_count",
    "novel_candidate_count",
    "candidate_status",
    "review_note",
]

TOOL_COLUMNS = [
    "analysis_layer",
    "tool_or_source",
    "version_or_snapshot",
    "availability",
    "status",
    "exact_command_or_source",
    "input_files",
    "output_files",
    "records_or_rows",
    "interpretation",
]

FEASIBILITY_COLUMNS = [
    "hypothesis",
    "current_status",
    "current_evidence",
    "what_can_be_claimed_now",
    "blocking_gap",
    "next_established_tool_step",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact pilot audit/report from production outputs.")
    parser.add_argument("--results-dir", default="results/production", help="Profile results directory to summarize.")
    parser.add_argument("--output-dir", default="results/pilot", help="Pilot output directory.")
    parser.add_argument("--report-output", default="PILOT_REPORT.md", help="Markdown pilot report path.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or str(value).strip() in MISSING


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [{key: "" if value is None else value for key, value in row.items()} for row in reader]


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def version(command: str, args: list[str]) -> str:
    executable = shutil.which(command)
    if not executable:
        return "not_available"
    try:
        completed = subprocess.run([executable, *args], check=False, capture_output=True, text=True, timeout=20)
    except Exception as exc:  # pragma: no cover - defensive reporting only
        return f"available_version_error:{exc}"
    text = (completed.stdout + completed.stderr).strip().splitlines()
    return text[0] if text else "available_version_unknown"


def tool_available(command: str) -> str:
    return "available" if shutil.which(command) else "not_available"


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def index_by(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row.get(key, ""): row for row in rows if row.get(key, "")}


def build_host_range(assays: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, dict[str, int]]]:
    stats: dict[str, dict[str, int]] = defaultdict(lambda: Counter())
    meta: dict[str, tuple[str, str]] = {}
    for row in assays:
        phage = row.get("phage_id", "")
        if not phage or row.get("tested", "").lower() != "true":
            continue
        meta.setdefault(phage, (row.get("study_id", "NA"), row.get("panel_id", "NA")))
        stats[phage]["tested"] += 1
        spot = row.get("spot_result", "")
        if spot == "positive":
            stats[phage]["spot_positive"] += 1
        elif spot == "negative":
            stats[phage]["spot_negative"] += 1
        if row.get("productive_infection_result", "") in {"positive", "negative", "equivocal"}:
            stats[phage]["productive_measured"] += 1
    rows: list[dict[str, str]] = []
    for phage in sorted(stats):
        tested = stats[phage]["tested"]
        pos = stats[phage]["spot_positive"]
        neg = stats[phage]["spot_negative"]
        low, high = wilson(pos, tested)
        study, panel = meta.get(phage, ("NA", "NA"))
        rows.append(
            {
                "phage_id": phage,
                "study_id": study,
                "panel_id": panel,
                "tested_host_count": str(tested),
                "spot_positive_host_count": str(pos),
                "spot_negative_host_count": str(neg),
                "spot_positive_fraction": f"{pos / tested:.6f}" if tested else "NA",
                "spot_positive_fraction_ci95_low": f"{low:.6f}",
                "spot_positive_fraction_ci95_high": f"{high:.6f}",
                "productive_infection_measured_count": str(stats[phage]["productive_measured"]),
                "interpretation": "spot-test initial interaction only; not productive infection evidence",
            }
        )
    return rows, stats


def build_rbp_summary(manifest: list[dict[str, str]], candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    assay_phages = sorted(row["genome_id"] for row in manifest if row.get("record_type") == "phage" and row.get("genome_id", "").startswith("phagehostlearn_2024_phage_"))
    by_phage: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        by_phage[row.get("genome_id", "")].append(row)
    out: list[dict[str, str]] = []
    for phage in assay_phages:
        rows = by_phage.get(phage, [])
        seq = sum(1 for row in rows if not is_missing(row.get("sequence_hit")) and row.get("sequence_hit") not in {"no_sequence_hit", "none"})
        domain = sum(1 for row in rows if not is_missing(row.get("domain_hit")) and row.get("domain_hit") not in {"no_domain_evidence", "none"})
        structural = sum(1 for row in rows if not is_missing(row.get("structural_hit")) and row.get("structural_hit") not in {"no_structural_evidence", "none"})
        high = sum(1 for row in rows if row.get("is_high_confidence", "").lower() == "true")
        novel = sum(1 for row in rows if row.get("novelty_tier", "") in {"novel_high_priority", "novel_candidate"})
        if rows:
            status = "possible_candidate_present"
            note = "Candidates are sequence-backed Prodigal/RBPbase/annotation evidence; domain and structural evidence remain absent unless counted separately."
        else:
            status = "no_candidate_in_current_table"
            note = "This is not biological absence unless accepted production RBP analysis covered this phage."
        out.append(
            {
                "phage_id": phage,
                "candidate_count": str(len(rows)),
                "high_confidence_count": str(high),
                "sequence_evidence_count": str(seq),
                "domain_evidence_count": str(domain),
                "structural_evidence_count": str(structural),
                "novel_candidate_count": str(novel),
                "candidate_status": status,
                "review_note": note,
            }
        )
    return out


def build_data_audit(
    manifest: list[dict[str, str]],
    sequence_qc: list[dict[str, str]],
    host_range_stats: dict[str, dict[str, int]],
    kaptive: list[dict[str, str]],
    kleborate: list[dict[str, str]],
) -> list[dict[str, str]]:
    qc = index_by(sequence_qc, "genome_id")
    kaptive_ids = {row.get("host_genome_id", "") for row in kaptive}
    k_type_ids = {row.get("host_genome_id", "") for row in kaptive if not is_missing(row.get("K_type"))}
    o_type_ids = {row.get("host_genome_id", "") for row in kaptive if not is_missing(row.get("O_type"))}
    st_ids = {row.get("host_genome_id", "") for row in kleborate if not is_missing(row.get("ST"))}
    rows: list[dict[str, str]] = []
    for row in manifest:
        entity = row.get("genome_id", "")
        q = qc.get(entity, {})
        record_type = row.get("record_type", "")
        host_range = host_range_stats.get(entity, Counter())
        sequence_verified = q.get("passes_sequence_qc", "false") == "true"
        include = False
        reasons: list[str] = []
        if entity.startswith("phagehostlearn_2024_phage_") or entity.startswith("phagehostlearn_2024_host_"):
            include = True
        if record_type in {"phage", "prophage"} and sequence_verified:
            include = True
        if not include:
            reasons.append("outside current pilot assay/sequence-backed focus")
        rows.append(
            {
                "entity_id": entity,
                "record_type": record_type,
                "source": row.get("source", "NA"),
                "sequence_path": row.get("raw_sequence_path", ""),
                "sequence_qc_status": q.get("sequence_qc_status", "not_assessed"),
                "sequence_verified": str(sequence_verified).lower(),
                "genome_length_bp": q.get("total_length_bp") or row.get("genome_length", "NA"),
                "number_of_contigs": q.get("sequence_count", "NA"),
                "complete_status": "single_contig_sequence_backed" if q.get("sequence_count") == "1" else ("multi_contig_or_fragmented" if sequence_verified else "not_sequence_verified"),
                "isolation_host": row.get("isolation_host", "NA"),
                "tested_host_count": str(host_range.get("tested", 0)),
                "spot_positive_host_count": str(host_range.get("spot_positive", 0)),
                "host_range_data_available": str(bool(host_range)).lower(),
                "host_genome_available": str(record_type == "host" and sequence_verified).lower(),
                "K_type_available": str(entity in k_type_ids).lower(),
                "O_type_available": str(entity in o_type_ids).lower(),
                "ST_available": str(entity in st_ids).lower(),
                "metadata_source": "production_profile_outputs",
                "include_in_pilot": str(include).lower(),
                "exclusion_reason": "; ".join(reasons) if reasons else "NA",
            }
        )
    return rows


def build_tool_summary(results_dir: Path, counts: dict[str, int]) -> list[dict[str, str]]:
    kaptive_review = read_tsv(Path("data/metadata/production_evidence/phagehostlearn_host_typing_review.tsv"))
    review_values = {row.get("metric", ""): row.get("value", "") for row in kaptive_review}
    return [
        {
            "analysis_layer": "phage_host_assay_outcomes",
            "tool_or_source": "PhageHostLearn 2024 reviewed matrix import",
            "version_or_snapshot": "Zenodo 10.5281/zenodo.11061100; 2024-04-25",
            "availability": "local_reviewed_input_available",
            "status": "completed",
            "exact_command_or_source": "python scripts/import_phage_host_assays.py --config config/assay_imports.yaml ...",
            "input_files": "data/metadata/assay_source_exports/reviewed_klebsiella_phage_host_assays.tsv",
            "output_files": f"{results_dir}/metadata/phage_host_assays.tsv",
            "records_or_rows": f"assay_rows={counts['assays']}; spot_positive={counts['spot_positive']}; spot_negative={counts['spot_negative']}",
            "interpretation": "Observed spot-test initial-interaction outcomes; not productive infection.",
        },
        {
            "analysis_layer": "host_KO_ST_typing",
            "tool_or_source": "Kaptive / Kleborate reviewed outputs",
            "version_or_snapshot": "Kaptive 3.2.1; Kleborate 3.2.4",
            "availability": "reviewed_outputs_available; executables_not_on_PATH_now",
            "status": "completed_from_reviewed_outputs",
            "exact_command_or_source": "See data/metadata/production_evidence/phagehostlearn_host_typing_review.tsv",
            "input_files": "data/metadata/external/phagehostlearn/klebsiella_genomes.zip; reviewed Kaptive/Kleborate outputs",
            "output_files": "data/metadata/production_evidence/kaptive_ko_typing.tsv; data/metadata/production_evidence/kleborate_host_features.tsv",
            "records_or_rows": f"kaptive_rows={review_values.get('kaptive_rows', 'NA')}; kleborate_rows={review_values.get('kleborate_rows', 'NA')}",
            "interpretation": "Host receptor/background evidence available; confidence and unresolved calls retained.",
        },
        {
            "analysis_layer": "phage_CDS_annotation",
            "tool_or_source": "Prodigal",
            "version_or_snapshot": version("prodigal", ["-v"]),
            "availability": tool_available("prodigal"),
            "status": "completed",
            "exact_command_or_source": "prodigal -p meta on reviewed PhageHostLearn phage FASTA archive members via scripts/build_phagehostlearn_phage_cds_annotations.py",
            "input_files": "data/metadata/external/phagehostlearn/phages_genomes.zip; data/metadata/external/phagehostlearn/RBPbase.csv",
            "output_files": "data/metadata/production_evidence/phagehostlearn_prodigal_cds_annotations.tsv",
            "records_or_rows": f"cds_rows={counts['annotations']}; rbp_candidate_rows={counts['rbp_candidates']}",
            "interpretation": "Baseline CDS and exact RBPbase candidate evidence; not Pharokka/PHROGs, domain, structural, or functional validation.",
        },
        {
            "analysis_layer": "whole_genome_similarity",
            "tool_or_source": "BLASTN pairwise baseline",
            "version_or_snapshot": version("blastn", ["-version"]),
            "availability": tool_available("blastn"),
            "status": "completed",
            "exact_command_or_source": "python scripts/build_blastn_pairwise_similarity.py --manifest results/production/qc/phage_genome_manifest.tsv --sequence-qc results/production/qc/genome_sequence_qc.tsv --output data/metadata/production_evidence/phage_genome_similarity.tsv --report-output data/metadata/production_evidence/phage_genome_similarity_report.tsv --blastn blastn --task blastn --min-hsp-length 100",
            "input_files": "results/production/qc/phage_genome_manifest.tsv; results/production/qc/genome_sequence_qc.tsv",
            "output_files": "data/metadata/production_evidence/phage_genome_similarity.tsv",
            "records_or_rows": f"pairwise_rows={counts['pairwise']}",
            "interpretation": "Useful local baseline; not a substitute for VIRIDIC/Mash/skani/ANI manuscript-scale comparison.",
        },
        {
            "analysis_layer": "phage_annotation_standard",
            "tool_or_source": "Pharokka",
            "version_or_snapshot": "not_run",
            "availability": tool_available("pharokka") if tool_available("pharokka") == "available" else tool_available("pharokka.py"),
            "status": "blocked_not_installed_or_not_on_PATH",
            "exact_command_or_source": "not run in current environment",
            "input_files": "pilot phage FASTA files available as ZIP-member locators",
            "output_files": "NA",
            "records_or_rows": "0",
            "interpretation": "Run directly next for standardized phage annotation before strong RBP claims.",
        },
        {
            "analysis_layer": "structure_informed_annotation",
            "tool_or_source": "Phold / Foldseek",
            "version_or_snapshot": "not_run",
            "availability": f"phold={tool_available('phold')}; foldseek={tool_available('foldseek')}",
            "status": "blocked_not_installed_or_not_on_PATH",
            "exact_command_or_source": "not run in current environment",
            "input_files": "Pharokka GenBank output required first",
            "output_files": "NA",
            "records_or_rows": "0",
            "interpretation": "Needed for structure-informed RBP/depolymerase novelty claims.",
        },
        {
            "analysis_layer": "defense_counterdefense",
            "tool_or_source": "DefenseFinder/PADLOC and curated phage anti-defense screening",
            "version_or_snapshot": "not_run",
            "availability": f"defense-finder={tool_available('defense-finder')}; padloc={tool_available('padloc')}",
            "status": "blocked_not_installed_or_not_on_PATH_and_no_productive_infection_labels",
            "exact_command_or_source": "not run in current environment",
            "input_files": "host FASTA archive members now sequence-QC-backed; phage proteins available",
            "output_files": "NA",
            "records_or_rows": "0",
            "interpretation": "Do not test H4 until productive-infection/plaque/EOP outcomes exist; defense landscapes can still be descriptive.",
        },
    ]


def build_feasibility(hypothesis_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_h = {row.get("hypothesis", ""): row for row in hypothesis_rows}
    return [
        {
            "hypothesis": "H1 receptor/RBP vs taxonomy",
            "current_status": by_h.get("H1", {}).get("summary_status", "warn"),
            "current_evidence": "10,006 spot-test pairs; 200/200 host K/O rows; 105/105 phage CDS annotations; 103/105 phages with RBPbase-exact candidates; BLASTN similarity baseline",
            "what_can_be_claimed_now": "A receptor-layer pilot dataset exists and can support exploratory initial-interaction analysis.",
            "blocking_gap": "No Pharokka/PHROGs, Phold/Foldseek/domain evidence, or leakage-safe grouped model yet.",
            "next_established_tool_step": "Run Pharokka on 20-50 representative phages, then Phold/Foldseek if installed.",
        },
        {
            "hypothesis": "H2 prophage RBP reservoir",
            "current_status": by_h.get("H2", {}).get("summary_status", "warn"),
            "current_evidence": "Only a tiny prophage fixture/seed layer is present in the production summaries.",
            "what_can_be_claimed_now": "Not testable beyond plumbing/fixture demonstration.",
            "blocking_gap": "Needs a real Klebsiella host/prophage cohort and standardized prophage extraction/annotation.",
            "next_established_tool_step": "Curate host genomes and use established prophage callers before comparative analysis.",
        },
        {
            "hypothesis": "H3 breadth vs RBP/counter-defense",
            "current_status": by_h.get("H3", {}).get("summary_status", "warn"),
            "current_evidence": "Spot-test breadth is available from explicit denominators for 105 assay phages.",
            "what_can_be_claimed_now": "Descriptive tested-panel spot breadth only.",
            "blocking_gap": "Counter-defense not assessed; RBP candidates lack domain/structural support; no productive-infection breadth.",
            "next_established_tool_step": "Run standardized phage annotation and RBP/domain/structure tools before association testing.",
        },
        {
            "hypothesis": "H4 defense/counter-defense improves productive infection prediction",
            "current_status": by_h.get("H4", {}).get("summary_status", "warn"),
            "current_evidence": "No productive-infection/plaque/EOP labels; no host-defense or phage anti-defense tables.",
            "what_can_be_claimed_now": "Not testable.",
            "blocking_gap": "Requires productive-infection outcomes plus DefenseFinder/PADLOC and phage anti-defense evidence.",
            "next_established_tool_step": "Curate plaque/EOP/propagation outcomes first; then run DefenseFinder/PADLOC for descriptive landscape.",
        },
        {
            "hypothesis": "H5 lineage vs defense landscape",
            "current_status": by_h.get("H5", {}).get("summary_status", "warn"),
            "current_evidence": "188/200 assay hosts have Kleborate rows/ST context; defense evidence absent.",
            "what_can_be_claimed_now": "Host typing coverage can be described; defense-burden claims cannot.",
            "blocking_gap": "No PADLOC/DefenseFinder output.",
            "next_established_tool_step": "Run DefenseFinder or PADLOC on the 200 host genomes if installed/available.",
        },
        {
            "hypothesis": "H6 novelty/source or cluster prioritization",
            "current_status": by_h.get("H6", {}).get("summary_status", "warn"),
            "current_evidence": "Candidate and cluster summaries exist, but domain/structural novelty evidence is absent.",
            "what_can_be_claimed_now": "Computational prioritization only, not novelty or receptor specificity.",
            "blocking_gap": "Needs established genome comparison and structure/domain evidence.",
            "next_established_tool_step": "Run VIRIDIC/Mash/skani if available and Phold/Foldseek/domain searches for candidate proteins.",
        },
    ]


def main() -> int:
    args = parse_args()
    results_dir = Path(args.results_dir)
    output_dir = Path(args.output_dir)
    manifest = read_tsv(results_dir / "qc" / "phage_genome_manifest.tsv")
    sequence_qc = read_tsv(results_dir / "qc" / "genome_sequence_qc.tsv")
    assays = read_tsv(results_dir / "metadata" / "phage_host_assays.tsv")
    kaptive = read_tsv(results_dir / "host_features" / "kaptive_results.tsv")
    kleborate = read_tsv(results_dir / "host_features" / "kleborate_results.tsv")
    candidates = read_tsv(results_dir / "rbp_depolymerase" / "candidates.tsv")
    hypothesis = read_tsv(results_dir / "models" / "hypothesis_summary.tsv")
    annotations = read_tsv(results_dir / "annotations" / "phage_annotations.tsv")
    pairwise = read_tsv(Path("data/metadata/production_evidence/phage_genome_similarity.tsv"))

    host_range, host_range_stats = build_host_range(assays)
    rbp_summary = build_rbp_summary(manifest, candidates)
    data_audit = build_data_audit(manifest, sequence_qc, host_range_stats, kaptive, kleborate)

    counts = {
        "assays": len(assays),
        "spot_positive": sum(1 for row in assays if row.get("spot_result") == "positive"),
        "spot_negative": sum(1 for row in assays if row.get("spot_result") == "negative"),
        "annotations": len(annotations),
        "rbp_candidates": len(candidates),
        "pairwise": len(pairwise),
    }
    tool_summary = build_tool_summary(results_dir, counts)
    feasibility = build_feasibility(hypothesis)

    write_tsv(output_dir / "data_audit.tsv", DATA_AUDIT_COLUMNS, data_audit)
    write_tsv(output_dir / "host_range_summary.tsv", HOST_RANGE_COLUMNS, host_range)
    write_tsv(output_dir / "rbp_candidate_summary.tsv", RBP_COLUMNS, rbp_summary)
    write_tsv(output_dir / "tool_run_summary.tsv", TOOL_COLUMNS, tool_summary)
    write_tsv(output_dir / "hypothesis_feasibility.tsv", FEASIBILITY_COLUMNS, feasibility)

    seq_pass = sum(1 for row in sequence_qc if row.get("passes_sequence_qc") == "true")
    host_seq = sum(1 for row in data_audit if row.get("record_type") == "host" and row.get("sequence_verified") == "true")
    assay_host_seq = sum(1 for row in data_audit if row.get("entity_id", "").startswith("phagehostlearn_2024_host_") and row.get("sequence_verified") == "true")
    assay_phages = sum(1 for row in rbp_summary)
    rbp_with = sum(1 for row in rbp_summary if int(row["candidate_count"]) > 0)
    productive = sum(1 for row in assays if row.get("productive_infection_result") in {"positive", "negative", "equivocal"})

    report = f"""# Pilot Report: Klebsiella Phage Comparative Genomics\n\n## Purpose\n\nThis pilot audits the current repository data and summarizes real outputs already available from established tools or reviewed external datasets. It does not claim that the full receptor-plus-defense hypothesis is proven.\n\n## Current Data\n\n- Total manifest records: {len(manifest)}.\n- Sequence-QC passing records: {seq_pass}.\n- Tested phage-host spot outcomes: {counts['assays']} pairs.\n- Spot-positive pairs: {counts['spot_positive']}.\n- Spot-negative pairs: {counts['spot_negative']}.\n- Productive-infection/plaque/EOP outcomes: {productive}.\n- Assay phages summarized for RBP candidates: {assay_phages}.\n- Assay phages with current candidate RBP/depolymerase rows: {rbp_with}/{assay_phages}.\n- Sequence-backed host records: {host_seq}.\n- Sequence-backed PhageHostLearn assay hosts: {assay_host_seq}/200.\n\n## Real Outputs Inspected\n\n- `results/pilot/data_audit.tsv` audits sequence, host-range, host typing, and inclusion status.\n- `results/pilot/host_range_summary.tsv` gives continuous tested-panel spot breadth with Wilson intervals.\n- `results/pilot/rbp_candidate_summary.tsv` summarizes current candidate evidence per assay phage.\n- `results/pilot/tool_run_summary.tsv` records tool/source status, versions where available, commands, inputs, and outputs.\n- `results/pilot/hypothesis_feasibility.tsv` states which hypotheses are currently testable.\n\n## Tool Status\n\nProdigal and BLASTN are available and have been used for current production evidence. Reviewed Kaptive/Kleborate outputs are available, but the executables are not currently on `PATH`. Pharokka, Phold, Foldseek, HMMER, DefenseFinder, and PADLOC are not currently available on `PATH`; they should be run directly once installed rather than replaced with custom implementations.\n\n## Scientific Interpretation\n\nThe repository now has a real response-variable layer for initial interaction: PhageHostLearn spot tests provide explicit positives and tested negatives. This supports descriptive spot-range and future receptor-layer modeling. It does not support productive-infection prediction because spot clearing is not plaque/EOP/propagation evidence.\n\nHost receptor/background evidence is now strong enough for a pilot: Kaptive K/O rows cover the assay hosts, and Kleborate rows cover most assay hosts. Phage-side evidence is still incomplete: Prodigal CDS calls and exact RBPbase matches identify candidate proteins, but they are not equivalent to Pharokka/PHROGs annotation, domain evidence, Phold/Foldseek structural evidence, or functional depolymerase validation.\n\nDefense/counter-defense analysis is not currently testable. There are no host-defense calls, no accepted phage anti-defense calls, and no productive-infection outcomes.\n\n## What Can Be Tested Now\n\n- Descriptive spot-test breadth for assay phages.\n- Exploratory receptor-layer coverage: host K/O availability plus phage candidate availability.\n- Preliminary genome-similarity clustering using the current BLASTN baseline, with clear limitations.\n\n## What Cannot Be Claimed Yet\n\n- RBP/depolymerase modules outperform taxonomy for host-range prediction.\n- Defense/counter-defense compatibility explains host-range gaps.\n- Any specific candidate binds a capsule or degrades a capsule.\n- Spot-test positives represent productive infection.\n- The BLASTN baseline replaces VIRIDIC/Mash/skani/ANI for manuscript-grade phage clustering.\n\n## Recommended Next Pilot Step\n\nInstall and run Pharokka on a representative subset of 20-50 sequence-backed assay phages, inspect the real output, then run Phold/Foldseek if available. Only after that should RBP candidate claims be strengthened. DefenseFinder/PADLOC should wait until either productive-infection labels are curated or the goal is explicitly changed to a descriptive host-defense landscape.\n"""
    Path(args.report_output).write_text(report, encoding="utf-8")
    print(f"Pilot summary complete: data_audit={len(data_audit)}; host_range={len(host_range)}; rbp_summary={len(rbp_summary)}; report={args.report_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
