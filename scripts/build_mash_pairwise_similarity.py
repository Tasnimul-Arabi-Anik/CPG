#!/usr/bin/env python3
"""Build pairwise phage genome similarity evidence with Mash.

Mash performs the sequence comparison. This script prepares a FASTA list, runs
Mash sketch/dist, and normalizes the output into the existing pairwise
similarity schema used by receptor-layer model baselines.
"""

from __future__ import annotations

import argparse
import csv
import shlex
import subprocess
from pathlib import Path

OUTPUT_COLUMNS = [
    "genome_id_1",
    "genome_id_2",
    "identity_percent",
    "coverage_percent",
    "method",
    "evidence_source",
    "notes",
    "mash_distance",
    "p_value",
    "shared_hashes",
    "kmer_size",
    "sketch_size",
]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", default="results/production/pharokka_assay_phages/pharokka_input")
    parser.add_argument("--pattern", default="*.fasta")
    parser.add_argument("--work-dir", default="results/production/phage_similarity/mash")
    parser.add_argument("--output", default="results/production/phage_similarity/mash_pairwise_similarity.tsv")
    parser.add_argument("--report-output", default="results/production/phage_similarity/mash_pairwise_similarity_report.tsv")
    parser.add_argument("--mash-command", nargs="+", default=["mamba", "run", "-n", "pharokka", "mash"])
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument("--kmer-size", type=int, default=21)
    parser.add_argument("--sketch-size", type=int, default=10000)
    return parser.parse_args()


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def run_command(command: list[str]) -> str:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed with return code {completed.returncode}: {shlex.join(command)}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return completed.stdout


def tool_version(mash_command: list[str]) -> str:
    try:
        output = run_command([*mash_command, "--version"])
    except RuntimeError as exc:
        return f"version_error:{exc}"
    return output.strip().splitlines()[0] if output.strip() else "unknown"


def genome_id_from_path(path_text: str) -> str:
    name = Path(path_text).name
    for suffix in [".fasta", ".fa", ".fna", ".fas"]:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return Path(path_text).stem


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    fasta_paths = sorted(input_dir.glob(args.pattern))
    report: list[dict[str, str]] = []
    if not fasta_paths:
        report.append({"severity": "error", "item": "input_fastas", "message": f"No FASTA files found in {input_dir} matching {args.pattern}."})
        write_tsv(Path(args.output), OUTPUT_COLUMNS, [])
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        return 1

    fasta_list = work_dir / "assay_phage_fastas.txt"
    fasta_list.write_text("\n".join(str(path) for path in fasta_paths) + "\n", encoding="utf-8")
    sketch_prefix = work_dir / f"assay_phages_k{args.kmer_size}_s{args.sketch_size}"
    sketch_path = sketch_prefix.with_suffix(".msh")
    dist_path = work_dir / f"assay_phages_k{args.kmer_size}_s{args.sketch_size}_dist.tsv"
    version = tool_version(args.mash_command)

    sketch_command = [
        *args.mash_command,
        "sketch",
        "-p",
        str(args.threads),
        "-k",
        str(args.kmer_size),
        "-s",
        str(args.sketch_size),
        "-o",
        str(sketch_prefix),
        "-l",
        str(fasta_list),
    ]
    dist_command = [
        *args.mash_command,
        "dist",
        "-p",
        str(args.threads),
        str(sketch_path),
        str(sketch_path),
    ]
    run_command(sketch_command)
    dist_output = run_command(dist_command)
    dist_path.write_text(dist_output, encoding="utf-8")

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for line in dist_output.splitlines():
        if not line.strip():
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 5:
            continue
        left, right, distance_text, p_value, shared_hashes = parts[:5]
        left_id = genome_id_from_path(left)
        right_id = genome_id_from_path(right)
        if left_id == right_id:
            continue
        key = tuple(sorted([left_id, right_id]))
        if key in seen:
            continue
        seen.add(key)
        try:
            distance = float(distance_text)
        except ValueError:
            distance = 1.0
        identity = max(0.0, min(100.0, (1.0 - distance) * 100.0))
        rows.append(
            {
                "genome_id_1": key[0],
                "genome_id_2": key[1],
                "identity_percent": f"{identity:.6f}",
                "coverage_percent": "100.000000",
                "method": f"mash_k{args.kmer_size}_s{args.sketch_size}",
                "evidence_source": "build_mash_pairwise_similarity.py",
                "notes": (
                    f"Mash {version} distance converted to approximate similarity as (1-distance)*100; "
                    "coverage_percent is set to 100 so existing nearest-neighbor baseline ranks by Mash distance, "
                    "not by alignment coverage. This is an established k-mer distance baseline, not VIRIDIC."
                ),
                "mash_distance": f"{distance:.9f}",
                "p_value": p_value,
                "shared_hashes": shared_hashes,
                "kmer_size": str(args.kmer_size),
                "sketch_size": str(args.sketch_size),
            }
        )

    rows.sort(key=lambda row: (row["genome_id_1"], row["genome_id_2"]))
    report.extend(
        [
            {"severity": "info", "item": "mash_version", "message": version},
            {"severity": "info", "item": "input_fastas", "message": str(len(fasta_paths))},
            {"severity": "info", "item": "pairwise_rows", "message": str(len(rows))},
            {"severity": "info", "item": "sketch_command", "message": shlex.join(sketch_command)},
            {"severity": "info", "item": "dist_command", "message": shlex.join(dist_command)},
            {"severity": "warning", "item": "coverage_semantics", "message": "coverage_percent is fixed at 100 for compatibility with existing model scoring; Mash does not estimate alignment coverage."},
        ]
    )
    write_tsv(Path(args.output), OUTPUT_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Mash pairwise similarity complete: {len(rows)} rows from {len(fasta_paths)} FASTA files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
