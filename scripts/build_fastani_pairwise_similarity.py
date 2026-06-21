#!/usr/bin/env python3
"""Build pairwise phage genome similarity evidence with fastANI.

fastANI performs the ANI calculation. This script prepares query/reference
FASTA lists, runs fastANI, and normalizes its output into the existing pairwise
similarity schema used by receptor-layer nearest-phage baselines. Pairs not
reported by fastANI are retained as explicit zero-identity/zero-coverage rows
so downstream comparisons have a complete pair table.
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
    "aligned_fragments",
    "total_fragments",
]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", default="results/production/pharokka_assay_phages/pharokka_input")
    parser.add_argument("--pattern", default="*.fasta")
    parser.add_argument("--work-dir", default="results/production/phage_similarity/fastani")
    parser.add_argument("--output", default="results/production/phage_similarity/fastani_pairwise_similarity.tsv")
    parser.add_argument("--report-output", default="results/production/phage_similarity/fastani_pairwise_similarity_report.tsv")
    parser.add_argument("--fastani-command", nargs="+", default=["conda", "run", "-n", "fastani_env", "fastANI"])
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
    for version_args in (["--version"], ["-v"]):
        try:
            completed = run_command([*command, *version_args])
        except RuntimeError:
            continue
        text = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part)
        if text:
            return text.splitlines()[0]
    return "unknown"


def genome_id_from_path(path_text: str) -> str:
    name = Path(path_text).name
    for suffix in [".fasta", ".fa", ".fna", ".fas"]:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return Path(path_text).stem


def parse_fastani(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    hits: dict[tuple[str, str], dict[str, str]] = {}
    if not path.exists():
        return hits
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                parts = line.split()
            if len(parts) < 5:
                continue
            query, reference, ani, aligned, total = parts[:5]
            qid = genome_id_from_path(query)
            rid = genome_id_from_path(reference)
            if qid == rid:
                continue
            key = tuple(sorted([qid, rid]))
            try:
                ani_value = float(ani)
                aligned_value = float(aligned)
                total_value = float(total)
            except ValueError:
                continue
            current = hits.get(key)
            current_score = float(current["identity_percent"]) if current else -1.0
            if ani_value >= current_score:
                hits[key] = {
                    "identity_percent": f"{ani_value:.6f}",
                    "coverage_percent": f"{(aligned_value / total_value * 100.0) if total_value else 0.0:.6f}",
                    "aligned_fragments": str(int(aligned_value)),
                    "total_fragments": str(int(total_value)),
                }
    return hits


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
    fastani_raw = work_dir / "assay_phages_fastani.tsv"
    fasta_list.write_text("\n".join(str(path) for path in fasta_paths) + "\n", encoding="utf-8")
    version = tool_version(args.fastani_command)
    command = [
        *args.fastani_command,
        "--ql",
        str(fasta_list),
        "--rl",
        str(fasta_list),
        "--threads",
        str(args.threads),
        "-o",
        str(fastani_raw),
    ]
    run_command(command)
    hits = parse_fastani(fastani_raw)

    rows: list[dict[str, str]] = []
    genome_ids = [genome_id_from_path(str(path)) for path in fasta_paths]
    for left, right in itertools.combinations(genome_ids, 2):
        key = tuple(sorted([left, right]))
        hit = hits.get(key)
        if hit:
            rows.append(
                {
                    "genome_id_1": key[0],
                    "genome_id_2": key[1],
                    "identity_percent": hit["identity_percent"],
                    "coverage_percent": hit["coverage_percent"],
                    "method": "fastani_all_vs_all",
                    "evidence_source": "build_fastani_pairwise_similarity.py",
                    "notes": (
                        f"fastANI {version}; coverage is aligned_fragments/total_fragments from fastANI output. "
                        "This is an ANI robustness baseline and may omit distant phage relationships by fastANI design."
                    ),
                    "aligned_fragments": hit["aligned_fragments"],
                    "total_fragments": hit["total_fragments"],
                }
            )
        else:
            rows.append(
                {
                    "genome_id_1": key[0],
                    "genome_id_2": key[1],
                    "identity_percent": "0.000000",
                    "coverage_percent": "0.000000",
                    "method": "fastani_all_vs_all_no_hit",
                    "evidence_source": "build_fastani_pairwise_similarity.py",
                    "notes": (
                        f"fastANI {version} did not report this pair; retained as explicit zero for complete pairwise baseline. "
                        "Zero means no fastANI-reported ANI hit, not proof of no homology."
                    ),
                    "aligned_fragments": "0",
                    "total_fragments": "0",
                }
            )

    rows.sort(key=lambda row: (row["genome_id_1"], row["genome_id_2"]))
    report.extend(
        [
            {"severity": "info", "item": "fastani_version", "message": version},
            {"severity": "info", "item": "input_fastas", "message": str(len(fasta_paths))},
            {"severity": "info", "item": "pairwise_rows", "message": str(len(rows))},
            {"severity": "info", "item": "reported_fastani_hits", "message": str(len(hits))},
            {"severity": "info", "item": "missing_fastani_hits", "message": str(len(rows) - len(hits))},
            {"severity": "info", "item": "fastani_command", "message": shlex.join(command)},
            {"severity": "warning", "item": "coverage_semantics", "message": "coverage_percent is fastANI aligned_fragments/total_fragments and is not VIRIDIC intergenomic similarity coverage."},
        ]
    )
    write_tsv(Path(args.output), OUTPUT_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"fastANI pairwise similarity complete: {len(rows)} rows from {len(fasta_paths)} FASTA files; reported_hits={len(hits)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
