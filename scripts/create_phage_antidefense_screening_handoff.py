#!/usr/bin/env python3
"""Create a phage anti-defense screening handoff from normalized annotations and proteins."""

from __future__ import annotations

import argparse
import csv
import re
import shlex
from pathlib import Path
from typing import Iterable


MANIFEST_COLUMNS = [
    "annotation_gene_id",
    "phage_genome_id",
    "gene_id",
    "product",
    "protein_length_aa",
    "screening_priority",
    "screening_reason",
    "suggested_target_defense_system",
    "protein_fasta",
    "output_tsv_target",
    "run_status",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}

ANTIDEFENSE_PATTERNS = [
    ("anti_crispr_keyword", "CRISPR-Cas", re.compile(r"anti[-_ ]?crispr|\bacr\b|acr[IFV][0-9]", re.I)),
    (
        "anti_restriction_or_modification_keyword",
        "restriction-modification",
        re.compile(r"anti[-_ ]?restriction|restriction alleviation|ocr protein|ard[ab]|methyltransferase|DNA methylase|dam methylase|modification methylase", re.I),
    ),
    (
        "dna_modification_keyword",
        "restriction-modification",
        re.compile(r"mom protein|DNA modification|hydroxymethyl|glucosyltransferase|methyltransferase|DNA methylase", re.I),
    ),
    ("nuclease_inhibitor_keyword", "nuclease-based defense", re.compile(r"nuclease inhibitor|anti[-_ ]?nuclease|inhibitor of nuclease", re.I)),
    (
        "recombination_repair_keyword",
        "abortive infection or DNA damage defense",
        re.compile(r"recombinase|rec[abfor]|single[-_ ]strand annealing|rad52", re.I),
    ),
    ("general_counterdefense_keyword", "unknown", re.compile(r"anti[-_ ]?defen[cs]e|counter[-_ ]?defen[cs]e|defense inhibitor", re.I)),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create reviewer-facing anti-defense screening targets and command hints. "
            "This does not produce accepted phage anti-defense evidence."
        )
    )
    parser.add_argument("--annotations", required=True, help="Stage 3 phage_annotations.tsv.")
    parser.add_argument("--protein-manifest", required=True, help="Protein export manifest TSV.")
    parser.add_argument("--all-proteins", required=True, help="All-protein FASTA from external evidence protein handoff.")
    parser.add_argument("--manifest-output", required=True, help="Output anti-defense screening manifest TSV.")
    parser.add_argument("--commands-output", required=True, help="Output shell command hints.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for relative paths.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
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


def display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def priority_for_annotation(row: dict[str, str]) -> tuple[str, str, str]:
    text = " ".join(
        [
            row.get("product", ""),
            row.get("phrog_category", ""),
        ]
    )
    reasons = []
    targets = []
    for reason, target, pattern in ANTIDEFENSE_PATTERNS:
        if pattern.search(text):
            reasons.append(reason)
            targets.append(target)
    if reasons:
        return "anti_defense_review_priority", ";".join(dict.fromkeys(reasons)), ";".join(dict.fromkeys(targets))
    return "background", "no_counterdefense_screening_signal", ""


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    report: list[dict[str, str]] = []
    annotation_fields, annotation_rows = read_tsv(Path(args.annotations))
    protein_fields, protein_rows = read_tsv(Path(args.protein_manifest))
    missing_annotations = [column for column in ["annotation_gene_id", "genome_id", "gene_id", "product"] if column not in annotation_fields]
    missing_proteins = [column for column in ["annotation_gene_id"] if column not in protein_fields]
    if missing_annotations or missing_proteins:
        messages = []
        if missing_annotations:
            messages.append("annotations missing: " + ";".join(missing_annotations))
        if missing_proteins:
            messages.append("protein_manifest missing: " + ";".join(missing_proteins))
        write_tsv(Path(args.manifest_output), MANIFEST_COLUMNS, [])
        Path(args.commands_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.commands_output).write_text("", encoding="utf-8")
        write_tsv(Path(args.report_output), REPORT_COLUMNS, [{"severity": "error", "item": "phage_antidefense_handoff", "message": " | ".join(messages)}])
        return 1

    protein_ids = {row.get("annotation_gene_id", "") for row in protein_rows if not is_missing(row.get("annotation_gene_id"))}
    all_proteins_path = Path(args.all_proteins)
    if not all_proteins_path.is_absolute():
        all_proteins_path = root / all_proteins_path
    all_proteins_display = display_path(root, all_proteins_path)
    output_tsv = "data/metadata/external_evidence/phage_antidefense_candidates.tsv"
    manifest: list[dict[str, str]] = []
    for row in annotation_rows:
        annotation_gene_id = row.get("annotation_gene_id", "")
        if is_missing(annotation_gene_id) or annotation_gene_id not in protein_ids:
            continue
        priority, reason, target = priority_for_annotation(row)
        manifest.append(
            {
                "annotation_gene_id": annotation_gene_id,
                "phage_genome_id": row.get("genome_id", ""),
                "gene_id": row.get("gene_id", ""),
                "product": row.get("product", ""),
                "protein_length_aa": row.get("protein_length_aa", ""),
                "screening_priority": priority,
                "screening_reason": reason,
                "suggested_target_defense_system": target,
                "protein_fasta": all_proteins_display,
                "output_tsv_target": output_tsv,
                "run_status": "ready_for_curated_screening" if all_proteins_path.exists() else "waiting_for_protein_fasta",
                "notes": "Screening target only; do not configure as phage anti-defense evidence until curated database/tool results are reviewed.",
            }
        )

    commands = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Generated handoff commands. Review anti-defense databases/tool versions before running.",
        "# Normalize reviewed hits to data/metadata/external_evidence/phage_antidefense_candidates.tsv and configure inputs.phage_antidefense_input.",
        "",
        f"PHAGE_PROTEINS={shlex.quote(all_proteins_display)}",
        "ANTIDEFENSE_HMM_DB=${ANTIDEFENSE_HMM_DB:-/path/to/curated_antidefense_profiles.hmm}",
        "ANTIDEFENSE_FASTA_DB=${ANTIDEFENSE_FASTA_DB:-/path/to/curated_antidefense_proteins.faa}",
        "ANTIDEFENSE_DIAMOND_DB=${ANTIDEFENSE_DIAMOND_DB:-results/external/phage_antidefense/curated_antidefense.dmnd}",
        "mkdir -p results/external/phage_antidefense",
        "",
        "# Example profile search. Replace ANTIDEFENSE_HMM_DB with a reviewed anti-defense profile database.",
        "hmmsearch --tblout results/external/phage_antidefense/antidefense_hmmsearch.tbl \"$ANTIDEFENSE_HMM_DB\" \"$PHAGE_PROTEINS\"",
        "",
        "# Example sequence search. Replace ANTIDEFENSE_FASTA_DB with a reviewed anti-defense protein database.",
        "diamond makedb --in \"$ANTIDEFENSE_FASTA_DB\" --db \"$ANTIDEFENSE_DIAMOND_DB\"",
        "diamond blastp --query \"$PHAGE_PROTEINS\" --db \"$ANTIDEFENSE_DIAMOND_DB\" --out results/external/phage_antidefense/antidefense_diamond.tsv --outfmt 6",
        "",
        "# Optional structure-informed review can use Phold/Foldseek output linked by annotation_gene_id.",
        "# Convert reviewed hits to the template at results/qc/external_evidence_templates/phage_antidefense_candidates.tsv.",
        "",
    ]
    Path(args.commands_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.commands_output).write_text("\n".join(commands), encoding="utf-8")
    write_tsv(Path(args.manifest_output), MANIFEST_COLUMNS, manifest)
    priority_count = sum(1 for row in manifest if row["screening_priority"] == "anti_defense_review_priority")
    report.append(
        {
            "severity": "info",
            "item": "phage_antidefense_handoff",
            "message": f"screening_targets={len(manifest)}; anti_defense_review_priority={priority_count}; protein_fasta_exists={str(all_proteins_path.exists()).lower()}",
        }
    )
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
