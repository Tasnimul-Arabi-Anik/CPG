#!/usr/bin/env python3
"""Build host-defense evidence for PhageHostLearn hosts with DefenseFinder.

This script is glue around the established DefenseFinder tool. It extracts
reviewed host FASTA members from the PhageHostLearn ZIP archive into a
results-local working directory, runs DefenseFinder, and normalizes system-level
outputs into the existing Stage 6 host-defense evidence schema.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import subprocess
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

HOST_DEFENSE_COLUMNS = [
    "system",
    "type",
    "sample",
    "genome_id",
    "host_genome_id",
    "subtype",
    "gene_count",
    "genes",
    "contig",
    "start",
    "end",
    "evidence_source",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-source", default="data/metadata/source_exports/phagehostlearn_2024_hosts.tsv")
    parser.add_argument("--archive", default="data/metadata/external/phagehostlearn/klebsiella_genomes.zip")
    parser.add_argument("--assays", default="data/metadata/assay_source_exports/reviewed_klebsiella_phage_host_assays.tsv")
    parser.add_argument("--expected-archive-sha256", default="2859cfd259216608c41cfd0fda2a4a0659e17e61adf2fe856454a622e4200358")
    parser.add_argument("--defensefinder-command", default="defense-finder")
    parser.add_argument("--work-dir", default="results/production/host_defense/defensefinder")
    parser.add_argument("--output", default="data/metadata/production_evidence/host_defense_systems.tsv")
    parser.add_argument("--report-output", default="data/metadata/production_evidence/host_defense_systems_report.tsv")
    parser.add_argument("--jobs", type=int, default=16)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--force", action="store_true", help="Rerun DefenseFinder even when system outputs already exist.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in value).strip("_")


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: normalize(value) for key, value in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def assay_host_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {row.get("host_id", "") for row in read_tsv(path) if not is_missing(row.get("host_id", ""))}


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in writer.fieldnames})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_member(row: dict[str, str]) -> str:
    raw_path = row.get("raw_sequence_path", "")
    if "::" in raw_path:
        return raw_path.split("::", 1)[1]
    marker = "host_archive_member="
    notes = row.get("notes", "")
    if marker in notes:
        return notes.split(marker, 1)[1].split(";", 1)[0].strip()
    return ""


def defensefinder_version(command: str) -> str:
    try:
        proc = subprocess.run([command, "version"], text=True, capture_output=True, check=False)
    except OSError as exc:
        return f"unavailable: {exc}"
    text = (proc.stdout or proc.stderr).strip().replace("\n", " ")
    return text or f"exit_status={proc.returncode}"


def extract_inputs(host_rows: list[dict[str, str]], archive: Path, inputs_dir: Path) -> list[dict[str, str]]:
    inputs_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[dict[str, str]] = []
    with zipfile.ZipFile(archive) as zf:
        available = set(zf.namelist())
        for row in host_rows:
            host_id = row.get("genome_id", "")
            member = archive_member(row)
            if is_missing(host_id) or is_missing(member):
                continue
            if member not in available:
                extracted.append({**row, "_member": member, "_input_fasta": "", "_status": "missing_archive_member"})
                continue
            output = inputs_dir / f"{safe_name(host_id)}.fasta"
            output.write_bytes(zf.read(member))
            extracted.append({**row, "_member": member, "_input_fasta": output.as_posix(), "_status": "extracted"})
    return extracted


def run_one(row: dict[str, str], command: str, out_root: Path, workers: int, force: bool) -> dict[str, str]:
    host_id = row.get("genome_id", "")
    input_fasta = row.get("_input_fasta", "")
    out_dir = out_root / "runs" / safe_name(host_id)
    expected = out_dir / f"{Path(input_fasta).stem}_defense_finder_systems.tsv"
    log_path = out_root / "logs" / f"{safe_name(host_id)}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if row.get("_status") != "extracted":
        return {"host_genome_id": host_id, "status": row.get("_status", "not_extracted"), "systems_file": "", "log": log_path.as_posix()}
    if expected.exists() and not force:
        return {"host_genome_id": host_id, "status": "reused", "systems_file": expected.as_posix(), "log": log_path.as_posix()}
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [command, "run", input_fasta, "-o", out_dir.as_posix(), "-w", str(workers), "--preserve-raw"]
    env = os.environ.copy()
    command_dir = Path(command).resolve().parent if "/" in command else Path("")
    if command_dir.as_posix() not in {"", "."}:
        env["PATH"] = f"{command_dir}{os.pathsep}{env.get('PATH', '')}"
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.run(cmd, text=True, stdout=log, stderr=subprocess.STDOUT, check=False, env=env)
    status = "completed" if proc.returncode == 0 and expected.exists() else f"failed_exit_{proc.returncode}"
    return {"host_genome_id": host_id, "status": status, "systems_file": expected.as_posix() if expected.exists() else "", "log": log_path.as_posix()}


def read_system_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return read_tsv(path)


def protein_contigs(genes_file: Path) -> dict[str, str]:
    if not genes_file.exists():
        return {}
    mapping: dict[str, str] = {}
    for row in read_tsv(genes_file):
        hit_id = row.get("hit_id", "")
        replicon = row.get("replicon", "")
        if hit_id and replicon:
            mapping[hit_id] = replicon
    return mapping


def normalized_rows(run_rows: list[dict[str, str]], version: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for run in run_rows:
        host_id = run.get("host_genome_id", "")
        systems_file_text = run.get("systems_file", "")
        if not host_id or is_missing(systems_file_text):
            continue
        systems_file = Path(systems_file_text)
        if not systems_file.exists():
            continue
        genes_file = systems_file.with_name(systems_file.name.replace("_defense_finder_systems.tsv", "_defense_finder_genes.tsv"))
        contig_by_protein = protein_contigs(genes_file)
        for system in read_system_rows(systems_file):
            proteins = [protein.strip() for protein in system.get("protein_in_syst", "").split(",") if protein.strip()]
            contigs = sorted({contig_by_protein.get(protein, "") for protein in proteins if contig_by_protein.get(protein, "")})
            rows.append(
                {
                    "system": system.get("sys_id", ""),
                    "type": system.get("type", ""),
                    "sample": host_id,
                    "genome_id": host_id,
                    "host_genome_id": host_id,
                    "subtype": system.get("subtype", ""),
                    "gene_count": system.get("genes_count", ""),
                    "genes": system.get("protein_in_syst", ""),
                    "contig": ";".join(contigs),
                    "start": system.get("sys_beg", ""),
                    "end": system.get("sys_end", ""),
                    "evidence_source": f"DefenseFinder {version}; models defense-finder-models 3.1.0; CasFinder 3.1.0",
                    "notes": "System-level DefenseFinder call from reviewed PhageHostLearn host archive member; start/end are DefenseFinder protein identifiers, not nucleotide coordinates; spot-test endpoint does not prove productive infection.",
                }
            )
    rows.sort(key=lambda row: (row["host_genome_id"], row["type"], row["subtype"], row["system"]))
    return rows


def main() -> int:
    args = parse_args()
    host_source = Path(args.host_source)
    archive = Path(args.archive)
    work_dir = Path(args.work_dir)
    inputs_dir = work_dir / "inputs"
    archive_digest = sha256(archive)
    assay_hosts = assay_host_ids(Path(args.assays))
    source_rows = read_tsv(host_source)
    host_rows = [row for row in source_rows if not assay_hosts or row.get("genome_id", "") in assay_hosts]
    extracted = extract_inputs(host_rows, archive, inputs_dir)
    version = defensefinder_version(args.defensefinder_command)
    run_rows: list[dict[str, str]] = []
    runnable = [row for row in extracted if row.get("_status") == "extracted"]
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as executor:
        futures = [executor.submit(run_one, row, args.defensefinder_command, work_dir, args.workers, args.force) for row in runnable]
        for future in as_completed(futures):
            run_rows.append(future.result())
    skipped = [
        {"host_genome_id": row.get("genome_id", ""), "status": row.get("_status", ""), "systems_file": "", "log": ""}
        for row in extracted
        if row.get("_status") != "extracted"
    ]
    run_rows.extend(skipped)
    run_rows.sort(key=lambda row: row.get("host_genome_id", ""))
    rows = normalized_rows(run_rows, version)
    hosts_with_systems = len({row["host_genome_id"] for row in rows})
    completed = sum(1 for row in run_rows if row.get("status") in {"completed", "reused"})
    failed = [row for row in run_rows if row.get("status", "").startswith("failed") or row.get("status") == "missing_archive_member"]
    report = [
        {"severity": "info", "item": "defensefinder_version", "message": version},
        {"severity": "info", "item": "archive_sha256", "message": archive_digest},
        {"severity": "info" if archive_digest == args.expected_archive_sha256 else "error", "item": "archive_sha256_check", "message": f"expected={args.expected_archive_sha256}; observed={archive_digest}"},
        {"severity": "info", "item": "source_host_rows", "message": str(len(source_rows))},
        {"severity": "info", "item": "assay_host_rows", "message": str(len(host_rows))},
        {"severity": "info", "item": "assay_host_filter", "message": f"{len(assay_hosts)} hosts from {args.assays}" if assay_hosts else "not_applied"},
        {"severity": "info", "item": "extracted_fastas", "message": str(len(runnable))},
        {"severity": "info", "item": "completed_or_reused_runs", "message": str(completed)},
        {"severity": "info", "item": "hosts_with_defense_systems", "message": str(hosts_with_systems)},
        {"severity": "info", "item": "normalized_system_rows", "message": str(len(rows))},
        {"severity": "error" if failed else "info", "item": "failed_or_missing_runs", "message": ";".join(f"{row.get('host_genome_id')}={row.get('status')}" for row in failed) or "0"},
        {"severity": "info", "item": "command_template", "message": f"{args.defensefinder_command} run <host.fasta> -o <run_dir> -w {args.workers} --preserve-raw"},
    ]
    write_tsv(Path(args.output), HOST_DEFENSE_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"DefenseFinder host systems: {len(rows)} rows across {hosts_with_systems}/{len(host_rows)} hosts.")
    return 1 if any(row["severity"] == "error" for row in report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
