#!/usr/bin/env python3
"""QC local genome FASTA files referenced by the Stage 1 manifest."""

from __future__ import annotations

import argparse
import csv
import gzip
import zipfile
from pathlib import Path
from typing import Iterable, TextIO


QC_COLUMNS = [
    "genome_id",
    "record_type",
    "raw_sequence_path",
    "resolved_sequence_path",
    "sequence_qc_status",
    "sequence_count",
    "total_length_bp",
    "metadata_length_bp",
    "length_delta_bp",
    "length_matches_metadata",
    "gc_percent_observed",
    "metadata_gc_percent",
    "gc_delta_percent",
    "gc_matches_metadata",
    "n_count",
    "n_percent",
    "ambiguous_count",
    "ambiguous_percent",
    "passes_sequence_qc",
    "sequence_qc_messages",
]

REPORT_COLUMNS = ["genome_id", "record_type", "severity", "field", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


class SequenceQCError(Exception):
    """Raised for invalid sequence QC configuration."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QC FASTA files referenced by the Stage 1 manifest.")
    parser.add_argument("--manifest", required=True, help="Stage 1 phage_genome_manifest.tsv.")
    parser.add_argument("--thresholds", required=True, help="YAML thresholds file.")
    parser.add_argument("--qc-output", required=True, help="Output sequence QC TSV.")
    parser.add_argument("--report-output", required=True, help="Output sequence QC report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for relative raw_sequence_path values.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="") as handle:
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


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise SequenceQCError("PyYAML is required to read thresholds.") from exc
    if not path.exists():
        raise SequenceQCError(f"Thresholds file does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SequenceQCError("Thresholds file must contain a YAML mapping.")
    return data


def thresholds(data: dict) -> dict[str, float]:
    genome_qc = data.get("genome_qc", {}) if isinstance(data.get("genome_qc", {}), dict) else {}
    return {
        "min_genome_length_bp": float(genome_qc.get("min_genome_length_bp", 0)),
        "max_genome_length_bp": float(genome_qc.get("max_genome_length_bp", 10**12)),
        "max_host_genome_length_bp": float(genome_qc.get("max_host_genome_length_bp", genome_qc.get("max_genome_length_bp", 10**12))),
        "min_gc_percent": float(genome_qc.get("min_gc_percent", 0)),
        "max_gc_percent": float(genome_qc.get("max_gc_percent", 100)),
        "max_n_percent": float(genome_qc.get("max_n_percent", 5)),
        "max_ambiguous_percent": float(genome_qc.get("max_ambiguous_percent", 1)),
        "metadata_length_tolerance_bp": float(genome_qc.get("metadata_length_tolerance_bp", 0)),
        "metadata_gc_tolerance_percent": float(genome_qc.get("metadata_gc_tolerance_percent", 1)),
    }


def add_report(report: list[dict[str, str]], genome_id: str, record_type: str, severity: str, field: str, message: str) -> None:
    report.append(
        {
            "genome_id": genome_id or "NA",
            "record_type": record_type or "NA",
            "severity": severity,
            "field": field,
            "message": message,
        }
    )


def resolve_sequence_path(root: Path, raw_sequence_path: str) -> Path:
    path = Path(raw_sequence_path)
    return path if path.is_absolute() else root / path


def open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt")
    return path.open("rt")


def read_fasta_stats_from_lines(lines: Iterable[str], source_label: str) -> dict[str, int]:
    sequence_count = 0
    total_length = 0
    gc_count = 0
    atgc_count = 0
    n_count = 0
    ambiguous_count = 0
    seen_sequence = False
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            sequence_count += 1
            seen_sequence = True
            continue
        if not seen_sequence:
            raise SequenceQCError(f"FASTA sequence line found before header in {source_label}")
        seq = line.upper()
        total_length += len(seq)
        for base in seq:
            if base in {"A", "C", "G", "T"}:
                atgc_count += 1
                if base in {"G", "C"}:
                    gc_count += 1
            elif base == "N":
                n_count += 1
            else:
                ambiguous_count += 1
    return {
        "sequence_count": sequence_count,
        "total_length_bp": total_length,
        "gc_count": gc_count,
        "atgc_count": atgc_count,
        "n_count": n_count,
        "ambiguous_count": ambiguous_count,
    }


def read_fasta_stats(path: Path) -> dict[str, int]:
    with open_text(path) as handle:
        return read_fasta_stats_from_lines(handle, path.as_posix())


def split_archive_locator(raw_sequence_path: str) -> tuple[str, str] | None:
    if "::" not in raw_sequence_path:
        return None
    archive_path, member = raw_sequence_path.split("::", 1)
    archive_path = archive_path.strip()
    member = member.strip()
    if not archive_path or not member:
        raise SequenceQCError("Archive sequence path must use archive.zip::member.fasta")
    member_path = Path(member)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise SequenceQCError(f"Archive member path is not allowed: {member}")
    return archive_path, member


def read_fasta_stats_from_archive(archive_path: Path, member: str) -> dict[str, int]:
    if archive_path.suffix.lower() != ".zip":
        raise SequenceQCError(f"Unsupported archive sequence path, expected .zip: {archive_path}")
    with zipfile.ZipFile(archive_path) as archive:
        if member not in archive.namelist():
            raise SequenceQCError(f"Archive member does not exist: {archive_path}::{member}")
        text = archive.read(member).decode("utf-8-sig")
    return read_fasta_stats_from_lines(text.splitlines(), f"{archive_path}::{member}")


def parse_float(value: str) -> float | None:
    if is_missing(value):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_int(value: str) -> int | None:
    if is_missing(value):
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def fmt_float(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "NA"
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def qc_one(row: dict[str, str], root: Path, limits: dict[str, float], report: list[dict[str, str]]) -> dict[str, str]:
    genome_id = row.get("genome_id", "")
    record_type = row.get("record_type", "")
    raw_path = row.get("raw_sequence_path", "")
    metadata_length = parse_int(row.get("genome_length", ""))
    metadata_gc = parse_float(row.get("gc_percent", ""))

    base = {
        "genome_id": genome_id,
        "record_type": record_type,
        "raw_sequence_path": raw_path,
        "resolved_sequence_path": "",
        "sequence_qc_status": "no_sequence_provided",
        "sequence_count": "0",
        "total_length_bp": "NA",
        "metadata_length_bp": str(metadata_length) if metadata_length is not None else "NA",
        "length_delta_bp": "NA",
        "length_matches_metadata": "NA",
        "gc_percent_observed": "NA",
        "metadata_gc_percent": fmt_float(metadata_gc),
        "gc_delta_percent": "NA",
        "gc_matches_metadata": "NA",
        "n_count": "NA",
        "n_percent": "NA",
        "ambiguous_count": "NA",
        "ambiguous_percent": "NA",
        "passes_sequence_qc": "false",
        "sequence_qc_messages": "no raw_sequence_path provided",
    }

    if is_missing(raw_path):
        add_report(report, genome_id, record_type, "info", "raw_sequence_path", "No raw_sequence_path provided; sequence QC skipped.")
        return base

    try:
        archive_locator = split_archive_locator(raw_path)
    except SequenceQCError as exc:
        base["sequence_qc_status"] = "invalid_sequence_path"
        base["sequence_qc_messages"] = str(exc)
        add_report(report, genome_id, record_type, "error", "raw_sequence_path", str(exc))
        return base

    if archive_locator:
        archive_text, member = archive_locator
        resolved = resolve_sequence_path(root, archive_text)
        base["resolved_sequence_path"] = f"{resolved.as_posix()}::{member}"
        missing_message = "sequence archive does not exist"
    else:
        member = ""
        resolved = resolve_sequence_path(root, raw_path)
        base["resolved_sequence_path"] = resolved.as_posix()
        missing_message = "raw_sequence_path does not exist"

    if not resolved.exists():
        base["sequence_qc_status"] = "missing_sequence_file"
        base["sequence_qc_messages"] = missing_message
        add_report(report, genome_id, record_type, "warning", "raw_sequence_path", f"Sequence file does not exist: {resolved}")
        return base

    messages: list[str] = []
    try:
        stats = read_fasta_stats_from_archive(resolved, member) if archive_locator else read_fasta_stats(resolved)
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile, SequenceQCError) as exc:
        base["sequence_qc_status"] = "invalid_fasta"
        base["sequence_qc_messages"] = str(exc)
        add_report(report, genome_id, record_type, "error", "fasta", str(exc))
        return base

    sequence_count = stats["sequence_count"]
    total_length = stats["total_length_bp"]
    atgc_count = stats["atgc_count"]
    gc_percent = (100 * stats["gc_count"] / atgc_count) if atgc_count else None
    n_percent = (100 * stats["n_count"] / total_length) if total_length else None
    ambiguous_percent = (100 * stats["ambiguous_count"] / total_length) if total_length else None

    if sequence_count == 0 or total_length == 0:
        messages.append("no sequences found in FASTA")
    if total_length < limits["min_genome_length_bp"]:
        messages.append(f"length below minimum {int(limits['min_genome_length_bp'])}")
    max_length_key = "max_host_genome_length_bp" if record_type == "host" else "max_genome_length_bp"
    max_length = limits[max_length_key]
    if total_length > max_length:
        messages.append(f"length above maximum {int(max_length)}")
    if gc_percent is not None and gc_percent < limits["min_gc_percent"]:
        messages.append(f"GC below minimum {fmt_float(limits['min_gc_percent'])}")
    if gc_percent is not None and gc_percent > limits["max_gc_percent"]:
        messages.append(f"GC above maximum {fmt_float(limits['max_gc_percent'])}")
    if n_percent is not None and n_percent > limits["max_n_percent"]:
        messages.append(f"N percent above maximum {fmt_float(limits['max_n_percent'])}")
    if ambiguous_percent is not None and ambiguous_percent > limits["max_ambiguous_percent"]:
        messages.append(f"ambiguous percent above maximum {fmt_float(limits['max_ambiguous_percent'])}")

    length_delta = None
    length_matches = "NA"
    if metadata_length is not None:
        length_delta = total_length - metadata_length
        length_matches = str(abs(length_delta) <= limits["metadata_length_tolerance_bp"]).lower()
        if length_matches == "false":
            messages.append("sequence length does not match metadata")

    gc_delta = None
    gc_matches = "NA"
    if metadata_gc is not None and gc_percent is not None:
        gc_delta = gc_percent - metadata_gc
        gc_matches = str(abs(gc_delta) <= limits["metadata_gc_tolerance_percent"]).lower()
        if gc_matches == "false":
            messages.append("sequence GC does not match metadata")

    status = "pass" if not messages else "warn"
    for message in messages:
        add_report(report, genome_id, record_type, "warning", "sequence_qc", message)
    if not messages:
        add_report(report, genome_id, record_type, "info", "sequence_qc", "Sequence QC passed.")

    base.update(
        {
            "sequence_qc_status": status,
            "sequence_count": str(sequence_count),
            "total_length_bp": str(total_length),
            "length_delta_bp": str(length_delta) if length_delta is not None else "NA",
            "length_matches_metadata": length_matches,
            "gc_percent_observed": fmt_float(gc_percent),
            "gc_delta_percent": fmt_float(gc_delta),
            "gc_matches_metadata": gc_matches,
            "n_count": str(stats["n_count"]),
            "n_percent": fmt_float(n_percent),
            "ambiguous_count": str(stats["ambiguous_count"]),
            "ambiguous_percent": fmt_float(ambiguous_percent),
            "passes_sequence_qc": str(not messages).lower(),
            "sequence_qc_messages": "; ".join(messages) if messages else "OK",
        }
    )
    return base


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    _, manifest_rows = read_tsv(Path(args.manifest))
    limits = thresholds(load_yaml(Path(args.thresholds)))
    report: list[dict[str, str]] = []
    qc_rows = [qc_one(row, root, limits, report) for row in manifest_rows]
    if not manifest_rows:
        add_report(report, "NA", "NA", "info", "manifest", "No manifest rows found; sequence QC table contains headers only.")
    write_tsv(Path(args.qc_output), QC_COLUMNS, qc_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    errors = sum(1 for row in report if row.get("severity") == "error")
    warnings = sum(1 for row in report if row.get("severity") == "warning")
    print(f"Sequence QC complete: {len(qc_rows)} rows, {errors} errors, {warnings} warnings.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
