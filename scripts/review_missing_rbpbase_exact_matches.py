#!/usr/bin/env python3
"""Review RBPbase candidates missing exact current Prodigal CDS matches.

The sequence comparison is done with BLASTP. This script only prepares FASTA
inputs from existing reviewed tables, runs BLASTP, and summarizes the result.
It does not implement sequence alignment or infer receptor specificity.
"""

from __future__ import annotations

import argparse
import csv
import shlex
import subprocess
from collections import Counter
from pathlib import Path

QUERY_COLUMNS = [
    "source_phage_id",
    "phage_id",
    "protein_id",
    "xgb_score",
    "protein_length_aa",
    "query_fasta_id",
    "query_fasta_path",
]

SUBJECT_COLUMNS = [
    "phage_id",
    "gene_id",
    "protein_id",
    "protein_length_aa",
    "product",
    "functional_category",
    "subject_fasta_id",
    "subject_fasta_path",
]

BLAST_COLUMNS = [
    "qseqid",
    "sseqid",
    "pident",
    "alignment_length",
    "mismatch",
    "gapopen",
    "qstart",
    "qend",
    "sstart",
    "send",
    "evalue",
    "bitscore",
    "qlen",
    "slen",
    "qcovhsp",
]

BLAST_OUTFMT_FIELDS = [
    "qseqid",
    "sseqid",
    "pident",
    "length",
    "mismatch",
    "gapopen",
    "qstart",
    "qend",
    "sstart",
    "send",
    "evalue",
    "bitscore",
    "qlen",
    "slen",
    "qcovhsp",
]

REVIEW_COLUMNS = [
    "source_phage_id",
    "phage_id",
    "protein_id",
    "xgb_score",
    "rbpbase_length_aa",
    "top_same_phage_gene_id",
    "top_same_phage_product",
    "top_same_phage_functional_category",
    "top_same_phage_pident",
    "top_same_phage_qcovhsp",
    "top_same_phage_alignment_length",
    "top_same_phage_evalue",
    "top_same_phage_bitscore",
    "top_same_phage_subject_length_aa",
    "length_delta_aa",
    "same_phage_hit_status",
    "boundary_review_status",
    "review_action",
    "claim_boundary",
]

SUMMARY_COLUMNS = ["metric", "value", "interpretation"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--missing-rbpbase", default="results/production/receptor_features/receptor_source_reconciliation_missing_rbpbase.tsv")
    parser.add_argument("--rbpbase", default="data/metadata/external/phagehostlearn/RBPbase.csv")
    parser.add_argument("--prodigal-annotations", default="data/metadata/production_evidence/phagehostlearn_prodigal_cds_annotations.tsv")
    parser.add_argument("--work-dir", default="results/production/receptor_features/missing_rbpbase_review")
    parser.add_argument("--query-fasta", default="missing_rbpbase_queries.faa")
    parser.add_argument("--subject-fasta", default="same_phage_prodigal_subjects.faa")
    parser.add_argument("--query-manifest", default="missing_rbpbase_query_manifest.tsv")
    parser.add_argument("--subject-manifest", default="missing_rbpbase_subject_manifest.tsv")
    parser.add_argument("--blast-output", default="missing_rbpbase_vs_prodigal_blastp.tsv")
    parser.add_argument("--review-output", default="missing_rbpbase_boundary_review.tsv")
    parser.add_argument("--summary-output", default="missing_rbpbase_boundary_review_summary.tsv")
    parser.add_argument("--report-output", default="PILOT_REPORT.md")
    parser.add_argument("--blastp", default="blastp")
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument("--max-target-seqs", type=int, default=25)
    parser.add_argument("--evalue", default="1e-5")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: "" if value is None else value for key, value in row.items()} for row in csv.DictReader(handle)]


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: "" if value is None else value for key, value in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def wrap_fasta(sequence: str, width: int = 80) -> str:
    return "\n".join(sequence[idx : idx + width] for idx in range(0, len(sequence), width))


def write_fasta(path: Path, records: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for header, sequence in records:
            handle.write(f">{header}\n")
            handle.write(wrap_fasta(sequence) + "\n")


def parse_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


def parse_int(value: str) -> int:
    try:
        return int(float(value))
    except ValueError:
        return 0


def safe_header(*parts: str) -> str:
    cleaned = []
    for part in parts:
        cleaned.append("".join(char if char.isalnum() or char in "._-" else "_" for char in part))
    return "|".join(cleaned)


def blast_version(blastp: str) -> str:
    completed = subprocess.run([blastp, "-version"], capture_output=True, text=True, check=False)
    text = (completed.stdout + completed.stderr).strip().splitlines()
    return text[0] if text else "unknown"


def build_inputs(args: argparse.Namespace, work_dir: Path) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], Path, Path]:
    missing_rows = read_tsv(Path(args.missing_rbpbase))
    rbpbase_rows = read_csv(Path(args.rbpbase))
    prodigal_rows = read_tsv(Path(args.prodigal_annotations))

    missing_keys = {(row["source_phage_id"], row["protein_id"]) for row in missing_rows}
    rbpbase_by_key = {(row.get("phage_ID", ""), row.get("protein_ID", "")): row for row in rbpbase_rows}
    missing_by_key = {(row["source_phage_id"], row["protein_id"]): row for row in missing_rows}
    missing_phages = {row["phage_id"] for row in missing_rows}

    query_records: list[tuple[str, str]] = []
    query_manifest: list[dict[str, str]] = []
    query_by_id: dict[str, dict[str, str]] = {}
    for source_phage, protein_id in sorted(missing_keys):
        rbp = rbpbase_by_key.get((source_phage, protein_id))
        missing = missing_by_key[(source_phage, protein_id)]
        if not rbp or not rbp.get("protein_sequence", ""):
            continue
        fasta_id = safe_header(missing["phage_id"], source_phage, protein_id)
        sequence = rbp["protein_sequence"]
        query_records.append((fasta_id, sequence))
        row = {
            "source_phage_id": source_phage,
            "phage_id": missing["phage_id"],
            "protein_id": protein_id,
            "xgb_score": missing.get("xgb_score", ""),
            "protein_length_aa": str(len(sequence)),
            "query_fasta_id": fasta_id,
            "query_fasta_path": str(work_dir / args.query_fasta),
        }
        query_manifest.append(row)
        query_by_id[fasta_id] = row

    subject_records: list[tuple[str, str]] = []
    subject_manifest: list[dict[str, str]] = []
    subject_by_id: dict[str, dict[str, str]] = {}
    for row in prodigal_rows:
        phage_id = row.get("genome_id", "")
        sequence = row.get("protein_sequence", "")
        if phage_id not in missing_phages or not sequence:
            continue
        fasta_id = safe_header(phage_id, row.get("gene_id", ""))
        subject_records.append((fasta_id, sequence))
        manifest_row = {
            "phage_id": phage_id,
            "gene_id": row.get("gene_id", ""),
            "protein_id": row.get("protein_id", ""),
            "protein_length_aa": str(len(sequence)),
            "product": row.get("product", ""),
            "functional_category": row.get("functional_category", ""),
            "subject_fasta_id": fasta_id,
            "subject_fasta_path": str(work_dir / args.subject_fasta),
        }
        subject_manifest.append(manifest_row)
        subject_by_id[fasta_id] = manifest_row

    query_fasta = work_dir / args.query_fasta
    subject_fasta = work_dir / args.subject_fasta
    write_fasta(query_fasta, query_records)
    write_fasta(subject_fasta, subject_records)
    write_tsv(work_dir / args.query_manifest, QUERY_COLUMNS, query_manifest)
    write_tsv(work_dir / args.subject_manifest, SUBJECT_COLUMNS, subject_manifest)
    return query_by_id, subject_by_id, query_fasta, subject_fasta


def run_blastp(args: argparse.Namespace, query_fasta: Path, subject_fasta: Path, blast_output: Path) -> str:
    outfmt = "6 " + " ".join(BLAST_OUTFMT_FIELDS)
    command = [
        args.blastp,
        "-query",
        str(query_fasta),
        "-subject",
        str(subject_fasta),
        "-outfmt",
        outfmt,
        "-evalue",
        args.evalue,
        "-max_target_seqs",
        str(args.max_target_seqs),
        "-num_threads",
        str(args.threads),
        "-out",
        str(blast_output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            "BLASTP failed with return code "
            f"{completed.returncode}\ncommand={shlex.join(command)}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return shlex.join(command)


def read_blast(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for raw in reader:
            if not raw:
                continue
            rows.append({column: raw[idx] if idx < len(raw) else "" for idx, column in enumerate(BLAST_COLUMNS)})
    return rows


def best_same_phage_hits(
    blast_rows: list[dict[str, str]],
    query_by_id: dict[str, dict[str, str]],
    subject_by_id: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    hits: dict[str, dict[str, str]] = {}
    for row in blast_rows:
        query = query_by_id.get(row.get("qseqid", ""), {})
        subject = subject_by_id.get(row.get("sseqid", ""), {})
        if not query or not subject or query.get("phage_id") != subject.get("phage_id"):
            continue
        qid = row["qseqid"]
        current = hits.get(qid)
        if current is None:
            hits[qid] = row
            continue
        current_key = (parse_float(current.get("bitscore", "")), parse_float(current.get("qcovhsp", "")), parse_float(current.get("pident", "")))
        new_key = (parse_float(row.get("bitscore", "")), parse_float(row.get("qcovhsp", "")), parse_float(row.get("pident", "")))
        if new_key > current_key:
            hits[qid] = row
    return hits


def classify_hit(query: dict[str, str], subject: dict[str, str], hit: dict[str, str] | None) -> tuple[str, str, str]:
    if hit is None:
        return (
            "no_same_phage_hit",
            "no_same_phage_blastp_hit_detected",
            "Carry as published RBPbase candidate evidence; inspect archive identity and gene caller boundary before treating as absent.",
        )
    pident = parse_float(hit.get("pident", ""))
    qcov = parse_float(hit.get("qcovhsp", ""))
    qlen = parse_int(hit.get("qlen", ""))
    slen = parse_int(hit.get("slen", ""))
    length_delta = abs(qlen - slen)
    if pident >= 99.0 and qcov >= 95.0 and length_delta > 0:
        return (
            "near_identical_same_phage_hit",
            "likely_start_stop_or_gene_boundary_difference",
            "Inspect start/stop coordinates and preserve RBPbase candidate as boundary-adjusted evidence if source identity is confirmed.",
        )
    if pident >= 95.0 and qcov >= 80.0:
        return (
            "strong_same_phage_hit",
            "likely_gene_boundary_or_minor_sequence_difference",
            "Inspect gene-calling boundary and sequence provenance before deciding whether to merge with the Prodigal CDS.",
        )
    if pident >= 70.0 and qcov >= 50.0:
        return (
            "partial_same_phage_hit",
            "related_current_cds_not_exact_match",
            "Manual review required; do not collapse into exact RBPbase evidence without coordinate/protein review.",
        )
    return (
        "weak_same_phage_hit",
        "weak_or_fragmentary_similarity",
        "Carry as external published candidate evidence unless manual review supports exclusion.",
    )


def build_review_rows(
    query_by_id: dict[str, dict[str, str]],
    subject_by_id: dict[str, dict[str, str]],
    hits: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for qid, query in sorted(query_by_id.items(), key=lambda item: (item[1]["source_phage_id"], item[1]["protein_id"])):
        hit = hits.get(qid)
        subject = subject_by_id.get(hit["sseqid"], {}) if hit else {}
        status, boundary_status, review_action = classify_hit(query, subject, hit)
        qlen = parse_int(hit.get("qlen", "")) if hit else parse_int(query.get("protein_length_aa", ""))
        slen = parse_int(hit.get("slen", "")) if hit else 0
        rows.append(
            {
                "source_phage_id": query.get("source_phage_id", ""),
                "phage_id": query.get("phage_id", ""),
                "protein_id": query.get("protein_id", ""),
                "xgb_score": query.get("xgb_score", ""),
                "rbpbase_length_aa": query.get("protein_length_aa", ""),
                "top_same_phage_gene_id": subject.get("gene_id", ""),
                "top_same_phage_product": subject.get("product", ""),
                "top_same_phage_functional_category": subject.get("functional_category", ""),
                "top_same_phage_pident": hit.get("pident", "") if hit else "",
                "top_same_phage_qcovhsp": hit.get("qcovhsp", "") if hit else "",
                "top_same_phage_alignment_length": hit.get("alignment_length", "") if hit else "",
                "top_same_phage_evalue": hit.get("evalue", "") if hit else "",
                "top_same_phage_bitscore": hit.get("bitscore", "") if hit else "",
                "top_same_phage_subject_length_aa": str(slen) if hit else "",
                "length_delta_aa": str(abs(qlen - slen)) if hit else "",
                "same_phage_hit_status": status,
                "boundary_review_status": boundary_status,
                "review_action": review_action,
                "claim_boundary": "BLASTP review explains why exact CDS matching missed this RBPbase candidate; it is not functional receptor validation or negative evidence.",
            }
        )
    return rows


def build_summary(review_rows: list[dict[str, str]], command: str, version: str) -> list[dict[str, str]]:
    statuses = Counter(row["same_phage_hit_status"] for row in review_rows)
    boundaries = Counter(row["boundary_review_status"] for row in review_rows)
    high_score_rows = [row for row in review_rows if parse_float(row.get("xgb_score", "")) >= 0.9]
    return [
        {"metric": "blastp_version", "value": version, "interpretation": "Established sequence-comparison tool used for same-phage review."},
        {"metric": "blastp_command", "value": command, "interpretation": "Exact BLASTP command used to generate review alignments."},
        {"metric": "review_rows", "value": str(len(review_rows)), "interpretation": "RBPbase candidates missing exact current Prodigal CDS matches."},
        {"metric": "high_score_ge_0_9_review_rows", "value": str(len(high_score_rows)), "interpretation": "Missing exact matches with RBPbase xgb_score >= 0.9."},
        *[
            {"metric": f"{status}_rows", "value": str(statuses.get(status, 0)), "interpretation": f"Rows with same_phage_hit_status={status}."}
            for status in ["near_identical_same_phage_hit", "strong_same_phage_hit", "partial_same_phage_hit", "weak_same_phage_hit", "no_same_phage_hit"]
        ],
        *[
            {"metric": f"{status}_rows", "value": str(boundaries.get(status, 0)), "interpretation": f"Rows with boundary_review_status={status}."}
            for status in [
                "likely_start_stop_or_gene_boundary_difference",
                "likely_gene_boundary_or_minor_sequence_difference",
                "related_current_cds_not_exact_match",
                "weak_or_fragmentary_similarity",
                "no_same_phage_blastp_hit_detected",
            ]
        ],
    ]


def add_report(path: Path, summary: list[dict[str, str]]) -> None:
    values = {row["metric"]: row["value"] for row in summary}
    section = f"""

## Missing RBPbase Exact-Match Review

The 27 RBPbase candidates absent from current exact Prodigal CDS matches were reviewed with BLASTP against current same-phage Prodigal proteins. Review table: `results/production/receptor_features/missing_rbpbase_review/missing_rbpbase_boundary_review.tsv`. BLASTP version: `{values.get('blastp_version', 'unknown')}`.

Rows reviewed: {values.get('review_rows', '0')}; high-scoring RBPbase rows (`xgb_score >= 0.9`): {values.get('high_score_ge_0_9_review_rows', '0')}. Same-phage hit status counts: near-identical {values.get('near_identical_same_phage_hit_rows', '0')}, strong {values.get('strong_same_phage_hit_rows', '0')}, partial {values.get('partial_same_phage_hit_rows', '0')}, weak {values.get('weak_same_phage_hit_rows', '0')}, no hit {values.get('no_same_phage_hit_rows', '0')}. Boundary-review statuses: likely start/stop or gene-boundary difference {values.get('likely_start_stop_or_gene_boundary_difference_rows', '0')}; likely minor boundary/sequence difference {values.get('likely_gene_boundary_or_minor_sequence_difference_rows', '0')}; related current CDS not exact match {values.get('related_current_cds_not_exact_match_rows', '0')}.

Claim boundary: BLASTP review explains why exact-match evidence is incomplete. It does not validate receptor function, and missing exact CDS matches should not be interpreted as biological absence.
"""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    marker = "\n## Missing RBPbase Exact-Match Review\n"
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
    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    query_by_id, subject_by_id, query_fasta, subject_fasta = build_inputs(args, work_dir)
    blast_output = work_dir / args.blast_output
    command = run_blastp(args, query_fasta, subject_fasta, blast_output)
    version = blast_version(args.blastp)
    blast_rows = read_blast(blast_output)
    best_hits = best_same_phage_hits(blast_rows, query_by_id, subject_by_id)
    review_rows = build_review_rows(query_by_id, subject_by_id, best_hits)
    summary = build_summary(review_rows, command, version)
    write_tsv(work_dir / args.review_output, REVIEW_COLUMNS, review_rows)
    write_tsv(work_dir / args.summary_output, SUMMARY_COLUMNS, summary)
    add_report(Path(args.report_output), summary)
    print(f"Reviewed {len(review_rows)} missing RBPbase candidates with BLASTP.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
