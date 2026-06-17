#!/usr/bin/env python3
"""Build pairwise phage genome similarity evidence from local FASTA files."""

from __future__ import annotations

import argparse
import csv
import itertools
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable


ELIGIBLE_RECORD_TYPES = {"phage", "prophage", "metagenomic_viral_contig"}
OUTPUT_COLUMNS = [
    "genome_id_1",
    "genome_id_2",
    "identity_percent",
    "coverage_percent",
    "method",
]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run BLASTN between local FASTA-backed phage-like records and emit the "
            "Stage 2 pairwise similarity schema. The coverage value is conservative: "
            "the lower of reciprocal non-overlapping aligned fractions."
        )
    )
    parser.add_argument("--manifest", required=True, help="Stage 1 manifest TSV.")
    parser.add_argument("--sequence-qc", required=True, help="Stage 1 sequence QC TSV.")
    parser.add_argument("--output", required=True, help="Output pairwise similarity TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--blastn", default="blastn", help="BLASTN executable.")
    parser.add_argument("--min-hsp-length", type=int, default=100, help="Minimum HSP length retained for summary.")
    parser.add_argument("--task", default="blastn", help="BLASTN task, for example blastn or megablast.")
    return parser.parse_args()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return reader.fieldnames or [], [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def is_true(value: str) -> bool:
    return value.strip().lower() == "true"


def fasta_length(path: Path) -> int:
    total = 0
    with path.open() as handle:
        for line in handle:
            if not line.startswith(">"):
                total += len(line.strip())
    return total


def merge_intervals(intervals: list[tuple[int, int]]) -> int:
    if not intervals:
        return 0
    normalized = sorted((min(start, end), max(start, end)) for start, end in intervals)
    merged: list[tuple[int, int]] = []
    for start, end in normalized:
        if not merged or start > merged[-1][1] + 1:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return sum(end - start + 1 for start, end in merged)


def load_records(manifest_path: Path, sequence_qc_path: Path, report: list[dict[str, str]]) -> list[dict[str, str]]:
    _, manifest_rows = read_tsv(manifest_path)
    _, qc_rows = read_tsv(sequence_qc_path)
    qc_by_id = {row.get("genome_id", ""): row for row in qc_rows}
    records: list[dict[str, str]] = []
    for row in manifest_rows:
        genome_id = row.get("genome_id", "")
        if row.get("record_type") not in ELIGIBLE_RECORD_TYPES:
            continue
        qc_row = qc_by_id.get(genome_id, {})
        if not is_true(qc_row.get("passes_sequence_qc", "")):
            report.append({"severity": "warning", "item": genome_id, "message": "Skipped record without passing sequence QC."})
            continue
        path_text = qc_row.get("resolved_sequence_path") or row.get("raw_sequence_path", "")
        path = Path(path_text)
        if not path.exists():
            report.append({"severity": "warning", "item": genome_id, "message": f"Skipped missing FASTA: {path}"})
            continue
        records.append(
            {
                "genome_id": genome_id,
                "path": str(path),
                "length": str(fasta_length(path)),
            }
        )
    report.append({"severity": "info", "item": "records", "message": f"Loaded {len(records)} local FASTA-backed phage-like records."})
    return records


def run_blastn(left: dict[str, str], right: dict[str, str], args: argparse.Namespace) -> tuple[float, float, int]:
    outfmt = "6 qseqid sseqid pident length qstart qend sstart send evalue bitscore"
    with tempfile.TemporaryDirectory(prefix="cpg_blastn_pairwise_") as tmpdir:
        output_path = Path(tmpdir) / "blastn.tsv"
        command = [
            args.blastn,
            "-task",
            args.task,
            "-query",
            left["path"],
            "-subject",
            right["path"],
            "-outfmt",
            outfmt,
            "-out",
            str(output_path),
        ]
        subprocess.run(command, check=True)
        q_intervals: list[tuple[int, int]] = []
        s_intervals: list[tuple[int, int]] = []
        weighted_identity = 0.0
        aligned_bp = 0
        if output_path.exists():
            with output_path.open() as handle:
                for line in handle:
                    fields = line.rstrip("\n").split("\t")
                    if len(fields) < 10:
                        continue
                    pident = float(fields[2])
                    length = int(fields[3])
                    if length < args.min_hsp_length:
                        continue
                    qstart, qend = int(fields[4]), int(fields[5])
                    sstart, send = int(fields[6]), int(fields[7])
                    q_intervals.append((qstart, qend))
                    s_intervals.append((sstart, send))
                    weighted_identity += pident * length
                    aligned_bp += length
        if aligned_bp == 0:
            return 0.0, 0.0, 0
        left_length = int(left["length"])
        right_length = int(right["length"])
        query_coverage = merge_intervals(q_intervals) / left_length * 100 if left_length else 0.0
        subject_coverage = merge_intervals(s_intervals) / right_length * 100 if right_length else 0.0
        identity = weighted_identity / aligned_bp
        coverage = min(query_coverage, subject_coverage)
        return identity, coverage, aligned_bp


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []
    rows: list[dict[str, str]] = []
    try:
        records = load_records(Path(args.manifest), Path(args.sequence_qc), report)
        for left, right in itertools.combinations(records, 2):
            identity, coverage, aligned_bp = run_blastn(left, right, args)
            rows.append(
                {
                    "genome_id_1": left["genome_id"],
                    "genome_id_2": right["genome_id"],
                    "identity_percent": f"{identity:.3f}",
                    "coverage_percent": f"{coverage:.3f}",
                    "method": f"blastn_local_pairwise_min_hsp_{args.min_hsp_length}",
                }
            )
            report.append(
                {
                    "severity": "info",
                    "item": f"{left['genome_id']} vs {right['genome_id']}",
                    "message": (
                        f"identity={identity:.3f}; reciprocal_min_coverage={coverage:.3f}; "
                        f"retained_hsp_aligned_bp={aligned_bp}"
                    ),
                }
            )
    except Exception as exc:  # noqa: BLE001 - capture executable/input failures in report form
        report.append({"severity": "error", "item": "blastn_pairwise_similarity", "message": str(exc)})

    write_tsv(Path(args.output), OUTPUT_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    errors = sum(1 for row in report if row["severity"] == "error")
    print(f"BLASTN pairwise similarity complete: {len(rows)} rows, {errors} errors.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
