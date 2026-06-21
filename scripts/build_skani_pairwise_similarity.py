#!/usr/bin/env python3
"""Build pairwise phage genome similarity evidence with skani.

skani performs the ANI and aligned-fraction calculation. This script prepares a
FASTA list, runs ``skani triangle --small-genomes --full-matrix``, and
normalizes the resulting ANI and AF matrices into the existing pairwise
similarity schema used by receptor-layer nearest-phage baselines.
"""

from __future__ import annotations

import argparse
import csv
import itertools
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
    "skani_ani",
    "skani_af_1_to_2",
    "skani_af_2_to_1",
    "skani_min_af",
    "small_genomes_preset",
]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", default="results/production/pharokka_assay_phages/pharokka_input")
    parser.add_argument("--pattern", default="*.fasta")
    parser.add_argument("--work-dir", default="results/production/phage_similarity/skani")
    parser.add_argument("--output", default="results/production/phage_similarity/skani_pairwise_similarity.tsv")
    parser.add_argument("--report-output", default="results/production/phage_similarity/skani_pairwise_similarity_report.tsv")
    parser.add_argument("--skani-command", nargs="+", default=["skani"])
    parser.add_argument("--threads", type=int, default=32)
    return parser.parse_args()


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed with return code {completed.returncode}: {shlex.join(command)}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return completed


def tool_version(command: list[str]) -> str:
    try:
        completed = run_command([*command, "--version"])
    except RuntimeError:
        return "unknown"
    text = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part)
    return text.splitlines()[0] if text else "unknown"


def genome_id_from_path(path_text: str) -> str:
    name = Path(path_text).name
    for suffix in [".fasta", ".fa", ".fna", ".fas"]:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return Path(path_text).stem


def parse_numeric_matrix(path: Path) -> tuple[list[str], list[list[float]]]:
    lines = [line.rstrip("\n") for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"Empty skani matrix: {path}")
    try:
        expected = int(lines[0].strip())
    except ValueError as exc:
        raise ValueError(f"First skani matrix line must be row count in {path}") from exc
    labels: list[str] = []
    matrix: list[list[float]] = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 2:
            raise ValueError(f"Malformed skani matrix row in {path}: {line}")
        labels.append(genome_id_from_path(parts[0]))
        try:
            matrix.append([float(value) for value in parts[1:]])
        except ValueError as exc:
            raise ValueError(f"Non-numeric skani matrix row in {path}: {line}") from exc
    if len(labels) != expected:
        raise ValueError(f"Expected {expected} skani matrix rows in {path}, observed {len(labels)}")
    for row in matrix:
        if len(row) != expected:
            raise ValueError(f"Expected {expected} values per skani matrix row in {path}")
    return labels, matrix


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    fasta_paths = sorted(input_dir.glob(args.pattern))
    report: list[dict[str, str]] = []
    if not fasta_paths:
        report.append({"severity": "error", "item": "input_fastas", "message": f"No FASTA files found in {input_dir} matching {args.pattern}."})
        write_tsv(Path(args.output), OUTPUT_COLUMNS, [])
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        return 1

    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    fasta_list = work_dir / "assay_phage_fastas.txt"
    ani_matrix = work_dir / "assay_phages_skani_ani.tsv"
    fasta_list.write_text("\n".join(str(path.resolve()) for path in fasta_paths) + "\n", encoding="utf-8")

    version = tool_version(args.skani_command)
    command = [
        *args.skani_command,
        "triangle",
        "--small-genomes",
        "--full-matrix",
        "-t",
        str(args.threads),
        "-l",
        str(fasta_list.resolve()),
        "-o",
        str(ani_matrix.resolve()),
    ]
    completed = run_command(command)
    af_matrix = Path(str(ani_matrix) + ".af")
    labels, ani_values = parse_numeric_matrix(ani_matrix)
    af_labels, af_values = parse_numeric_matrix(af_matrix)
    if labels != af_labels:
        raise RuntimeError("skani ANI and AF matrices have different row order or labels")

    rows: list[dict[str, str]] = []
    for i, j in itertools.combinations(range(len(labels)), 2):
        left, right = sorted([labels[i], labels[j]])
        left_index = labels.index(left)
        right_index = labels.index(right)
        ani = ani_values[left_index][right_index]
        af_left_to_right = af_values[left_index][right_index]
        af_right_to_left = af_values[right_index][left_index]
        min_af = min(af_left_to_right, af_right_to_left)
        rows.append(
            {
                "genome_id_1": left,
                "genome_id_2": right,
                "identity_percent": f"{ani:.6f}",
                "coverage_percent": f"{min_af:.6f}",
                "method": "skani_triangle_small_genomes",
                "evidence_source": "build_skani_pairwise_similarity.py",
                "notes": (
                    f"skani {version}; --small-genomes --full-matrix. coverage_percent is the minimum bidirectional "
                    "aligned fraction from skani's AF matrix. This is an ANI/AF robustness baseline, not VIRIDIC."
                ),
                "skani_ani": f"{ani:.6f}",
                "skani_af_1_to_2": f"{af_left_to_right:.6f}",
                "skani_af_2_to_1": f"{af_right_to_left:.6f}",
                "skani_min_af": f"{min_af:.6f}",
                "small_genomes_preset": "true",
            }
        )

    rows.sort(key=lambda row: (row["genome_id_1"], row["genome_id_2"]))
    nonzero_pairs = sum(1 for row in rows if float(row["coverage_percent"]) > 0 and float(row["identity_percent"]) > 0)
    report.extend(
        [
            {"severity": "info", "item": "skani_version", "message": version},
            {"severity": "info", "item": "input_fastas", "message": str(len(fasta_paths))},
            {"severity": "info", "item": "pairwise_rows", "message": str(len(rows))},
            {"severity": "info", "item": "nonzero_skani_pairs", "message": str(nonzero_pairs)},
            {"severity": "info", "item": "skani_command", "message": shlex.join(command)},
            {"severity": "warning", "item": "coverage_semantics", "message": "coverage_percent is minimum bidirectional skani aligned fraction, not VIRIDIC intergenomic similarity coverage."},
        ]
    )
    write_tsv(Path(args.output), OUTPUT_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"skani pairwise similarity complete: {len(rows)} rows from {len(fasta_paths)} FASTA files; nonzero_pairs={nonzero_pairs}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
