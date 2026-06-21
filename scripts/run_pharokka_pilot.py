#!/usr/bin/env python3
"""Run a bounded Pharokka pilot on representative assay phages.

This script is glue around established tools: it selects representative assay
phages, extracts reviewed FASTA archive members, calls Pharokka, and summarizes
Pharokka product annotations. It does not implement phage annotation itself.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shlex
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}

SELECTION_COLUMNS = [
    "selection_rank",
    "phage_id",
    "selection_reason",
    "tested_host_count",
    "spot_positive_host_count",
    "spot_positive_fraction",
    "source_locator",
    "fasta_path",
    "extraction_status",
    "extraction_message",
]

RUN_COLUMNS = [
    "selection_rank",
    "phage_id",
    "pharokka_version",
    "status",
    "returncode",
    "command",
    "fasta_path",
    "outdir",
    "stdout_log",
    "stderr_log",
    "output_files",
    "message",
]

ANNOTATION_COLUMNS = [
    "phage_id",
    "gene_id",
    "feature_type",
    "product",
    "source_file",
    "evidence_note",
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
    parser = argparse.ArgumentParser(description="Run a bounded Pharokka pilot on selected assay phages.")
    parser.add_argument("--host-range", default="results/pilot/host_range_summary.tsv")
    parser.add_argument("--manifest", default="results/production/qc/phage_genome_manifest.tsv")
    parser.add_argument("--output-dir", default="results/pilot")
    parser.add_argument("--log-dir", default="logs/pilot/pharokka")
    parser.add_argument("--database", default="results/pilot/pharokka_db")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--max-phages", type=int, default=30)
    parser.add_argument("--pharokka-command", nargs="+", default=["mamba", "run", "-n", "pharokka", "pharokka.py"])
    parser.add_argument("--selection-output", default="results/pilot/pharokka_selection.tsv")
    parser.add_argument("--run-output", default="results/pilot/pharokka_run_summary.tsv")
    parser.add_argument("--annotation-output", default="results/pilot/pharokka_rbp_annotation_summary.tsv")
    parser.add_argument("--report-output", default="PILOT_REPORT.md")
    parser.add_argument("--report-section-title", default="Pharokka Pilot")
    parser.add_argument("--analysis-label", default="30-phage representative pilot selection")
    parser.add_argument("--force", action="store_true", help="Pass -f to Pharokka and overwrite per-phage output directories.")
    return parser.parse_args()


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{k: "" if v is None else v for k, v in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "unknown"


def parse_fraction(row: dict[str, str]) -> float:
    try:
        return float(row.get("spot_positive_fraction", "0") or "0")
    except ValueError:
        return 0.0


def parse_int(row: dict[str, str], key: str) -> int:
    try:
        return int(float(row.get(key, "0") or "0"))
    except ValueError:
        return 0


def choose_evenly(rows: list[dict[str, str]], count: int) -> list[dict[str, str]]:
    if count <= 0 or not rows:
        return []
    if len(rows) <= count:
        return list(rows)
    if count == 1:
        return [rows[len(rows) // 2]]
    chosen: list[dict[str, str]] = []
    used: set[int] = set()
    for idx in range(count):
        pos = round(idx * (len(rows) - 1) / (count - 1))
        if pos not in used:
            chosen.append(rows[pos])
            used.add(pos)
    return chosen


def select_phages(host_range: list[dict[str, str]], max_phages: int) -> list[dict[str, str]]:
    rows = sorted(host_range, key=lambda r: (parse_fraction(r), r.get("phage_id", "")))
    low_n = min(10, max_phages, len(rows))
    high_n = min(10, max(0, max_phages - low_n), max(0, len(rows) - low_n))

    selected: list[tuple[dict[str, str], str]] = []
    seen: set[str] = set()

    for row in rows[-high_n:][::-1]:
        phage = row.get("phage_id", "")
        if phage and phage not in seen:
            selected.append((row, "top_spot_positive_fraction"))
            seen.add(phage)

    for row in rows[:low_n]:
        phage = row.get("phage_id", "")
        if phage and phage not in seen:
            selected.append((row, "bottom_spot_positive_fraction"))
            seen.add(phage)

    remaining = [row for row in rows if row.get("phage_id", "") not in seen]
    middle_target = max(0, max_phages - len(selected))
    for row in choose_evenly(remaining, min(10, middle_target)):
        phage = row.get("phage_id", "")
        if phage and phage not in seen:
            selected.append((row, "evenly_spaced_remaining_breadth"))
            seen.add(phage)

    if len(selected) < max_phages:
        fill = sorted(remaining, key=lambda r: (-parse_int(r, "tested_host_count"), r.get("phage_id", "")))
        for row in fill:
            phage = row.get("phage_id", "")
            if phage and phage not in seen:
                selected.append((row, "fill_by_tested_host_count"))
                seen.add(phage)
            if len(selected) >= max_phages:
                break

    out = []
    for idx, (row, reason) in enumerate(selected[:max_phages], start=1):
        copied = dict(row)
        copied["selection_rank"] = str(idx)
        copied["selection_reason"] = reason
        out.append(copied)
    return out


def split_locator(locator: str) -> tuple[Path, str] | None:
    if "::" not in locator:
        return None
    archive, member = locator.split("::", 1)
    archive_path = Path(unquote(archive))
    return archive_path, member


def safe_member(member: str) -> bool:
    pure = PurePosixPath(member)
    return not pure.is_absolute() and ".." not in pure.parts and bool(member.strip())


def extract_fasta(locator: str, destination: Path) -> tuple[str, str]:
    parsed = split_locator(locator)
    if parsed is None:
        return "failed", "raw_sequence_path is not a ZIP-member locator"
    archive, member = parsed
    if not safe_member(member):
        return "failed", "unsafe archive member path"
    if not archive.exists():
        return "failed", f"archive not found: {archive}"
    try:
        with zipfile.ZipFile(archive) as zf:
            if member not in zf.namelist():
                return "failed", f"member not found in archive: {member}"
            data = zf.read(member)
    except Exception as exc:  # pragma: no cover - runtime diagnostic
        return "failed", f"archive read failed: {exc}"
    if not data.startswith(b">"):
        return "failed", "extracted member is not FASTA-like"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return "pass", "extracted reviewed ZIP-member FASTA"


def run_command(command: list[str], stdout_path: Path, stderr_path: Path) -> int:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
        completed = subprocess.run(command, stdout=out, stderr=err, text=True, check=False)
    return completed.returncode


def get_version(pharokka_command: list[str]) -> str:
    try:
        completed = subprocess.run([*pharokka_command, "-V"], capture_output=True, text=True, check=False, timeout=60)
    except Exception as exc:  # pragma: no cover - runtime diagnostic
        return f"version_error:{exc}"
    text = (completed.stdout + completed.stderr).strip().splitlines()
    return text[0] if text else "unknown"


def parse_gff_attributes(attributes: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in attributes.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            parsed[key] = unquote(value)
    return parsed


def classify_product(product: str) -> list[str]:
    lower = product.lower()
    features: list[str] = []
    for label, terms in KEYWORDS:
        if any(term in lower for term in terms):
            features.append(label)
    return features


def summarize_annotations(phage_id: str, outdir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for gff in sorted(outdir.glob("*.gff")):
        with gff.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip() or line.startswith("#"):
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 9:
                    continue
                attrs = parse_gff_attributes(parts[8])
                product = attrs.get("product") or attrs.get("Name") or ""
                gene_id = attrs.get("ID") or attrs.get("locus_tag") or attrs.get("protein_id") or ""
                for feature in classify_product(product):
                    rows.append(
                        {
                            "phage_id": phage_id,
                            "gene_id": gene_id,
                            "feature_type": feature,
                            "product": product,
                            "source_file": str(gff),
                            "evidence_note": "Pharokka product annotation keyword summary; not functional validation.",
                        }
                    )
    return rows


def update_report(
    report_path: Path,
    completed: int,
    failed: int,
    annotation_rows: int,
    version: str,
    section_title: str,
    analysis_label: str,
) -> None:
    section = f"""\n## {section_title}\n\nPharokka `{version}` was run on the {analysis_label}. Completed or reused runs: {completed}; failed runs: {failed}. The run produced `{annotation_rows}` product-annotation rows matching receptor-binding, tail, structural, depolymerase, or lysis keywords in Pharokka GFF outputs. These rows are standardized annotation evidence for prioritization only; they are not capsule-binding, depolymerase-function, or productive-infection validation.\n"""
    if report_path.exists():
        text = report_path.read_text(encoding="utf-8")
        marker = f"\n## {section_title}\n"
        if marker in text:
            text = text.split(marker, 1)[0].rstrip() + section
        else:
            text = text.rstrip() + section
    else:
        text = section.lstrip()
    report_path.write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    log_dir = Path(args.log_dir)
    database = Path(args.database)
    selection_path = Path(args.selection_output)
    run_path = Path(args.run_output)
    annotation_path = Path(args.annotation_output)
    report_path = Path(args.report_output)

    host_range = read_tsv(Path(args.host_range))
    manifest = read_tsv(Path(args.manifest))
    manifest_by_id = {row.get("genome_id", ""): row for row in manifest}
    selected = select_phages(host_range, args.max_phages)
    version = get_version(args.pharokka_command)

    selection_rows: list[dict[str, str]] = []
    run_rows: list[dict[str, str]] = []
    annotation_rows: list[dict[str, str]] = []

    input_dir = output_dir / "pharokka_input"
    pharokka_out_root = output_dir / "pharokka_output"
    pharokka_out_root.mkdir(parents=True, exist_ok=True)

    for row in selected:
        phage_id = row["phage_id"]
        safe = safe_name(phage_id)
        manifest_row = manifest_by_id.get(phage_id, {})
        locator = manifest_row.get("raw_sequence_path", "")
        fasta_path = input_dir / f"{safe}.fasta"
        extraction_status, extraction_message = extract_fasta(locator, fasta_path)

        selection_rows.append(
            {
                "selection_rank": row["selection_rank"],
                "phage_id": phage_id,
                "selection_reason": row["selection_reason"],
                "tested_host_count": row.get("tested_host_count", ""),
                "spot_positive_host_count": row.get("spot_positive_host_count", ""),
                "spot_positive_fraction": row.get("spot_positive_fraction", ""),
                "source_locator": locator,
                "fasta_path": str(fasta_path),
                "extraction_status": extraction_status,
                "extraction_message": extraction_message,
            }
        )

        outdir = pharokka_out_root / safe
        stdout_log = log_dir / f"{safe}.stdout.log"
        stderr_log = log_dir / f"{safe}.stderr.log"
        expected_gff = outdir / f"{safe}.gff"
        command = [
            *args.pharokka_command,
            "-i",
            str(fasta_path),
            "-o",
            str(outdir),
            "-d",
            str(database),
            "-t",
            str(args.threads),
            "-p",
            safe,
        ]
        if args.force:
            command.append("-f")

        if extraction_status != "pass":
            status = "input_unavailable"
            returncode = "NA"
            message = extraction_message
            output_files = ""
        elif not database.exists():
            status = "database_missing"
            returncode = "NA"
            message = f"database directory not found: {database}"
            output_files = ""
        elif expected_gff.exists() and not args.force:
            status = "skipped_existing"
            returncode = "0"
            message = "Existing Pharokka output reused"
            annotation_rows.extend(summarize_annotations(phage_id, outdir))
            output_files = ";".join(str(path) for path in sorted(outdir.glob("*")) if path.is_file()) if outdir.exists() else ""
        else:
            code = run_command(command, stdout_log, stderr_log)
            returncode = str(code)
            if code == 0:
                status = "completed"
                message = "Pharokka completed"
                annotation_rows.extend(summarize_annotations(phage_id, outdir))
            else:
                status = "failed"
                message = f"Pharokka exited with return code {code}"
            output_files = ";".join(str(path) for path in sorted(outdir.glob("*")) if path.is_file()) if outdir.exists() else ""

        run_rows.append(
            {
                "selection_rank": row["selection_rank"],
                "phage_id": phage_id,
                "pharokka_version": version,
                "status": status,
                "returncode": returncode,
                "command": " ".join(shlex.quote(part) for part in command),
                "fasta_path": str(fasta_path),
                "outdir": str(outdir),
                "stdout_log": str(stdout_log),
                "stderr_log": str(stderr_log),
                "output_files": output_files,
                "message": message,
            }
        )

    write_tsv(selection_path, SELECTION_COLUMNS, selection_rows)
    write_tsv(run_path, RUN_COLUMNS, run_rows)
    write_tsv(annotation_path, ANNOTATION_COLUMNS, annotation_rows)

    completed = sum(1 for row in run_rows if row["status"] in {"completed", "skipped_existing"})
    failed = sum(1 for row in run_rows if row["status"] == "failed")
    update_report(
        report_path,
        completed,
        failed,
        len(annotation_rows),
        version,
        args.report_section_title,
        args.analysis_label,
    )
    print(
        f"Pharokka pilot complete: selected={len(selection_rows)}; completed={completed}; "
        f"failed={failed}; annotation_rows={len(annotation_rows)}"
    )
    return 0 if failed == 0 and completed > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
