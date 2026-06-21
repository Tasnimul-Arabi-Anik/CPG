#!/usr/bin/env python3
"""Normalize PhageHostLearn host K/O/ST typing outputs to production evidence TSVs."""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path
from typing import Iterable


KAPTIVE_COLUMNS = [
    "host_genome_id",
    "kaptive_sample_id",
    "K_locus",
    "K_type",
    "K_confidence",
    "O_locus",
    "O_type",
    "O_confidence",
    "kaptive_source",
    "notes",
    "evidence_source",
]

KLEBORATE_COLUMNS = [
    "host_genome_id",
    "kleborate_sample_id",
    "species",
    "species_match",
    "mlst_scheme",
    "ST",
    "virulence_score",
    "resistance_score",
    "AMR_markers",
    "virulence_markers",
    "ybt",
    "iuc",
    "iro",
    "rmpA",
    "rmpA2",
    "kleborate_source",
    "notes",
    "evidence_source",
]

REPORT_COLUMNS = ["metric", "value", "status", "notes"]
REVIEWED_STATUSES = {"reviewed", "accepted", "approved"}
MISSING_VALUES = {"", "NA", "N/A", "na", "n/a", "None", "none", "-", "Not Tested", "not tested"}


class EvidenceError(Exception):
    """Raised when production evidence cannot be normalized safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Map PhageHostLearn Kaptive/Kleborate host-typing outputs to canonical "
            "benchmark host IDs and write reviewed production evidence tables."
        )
    )
    parser.add_argument("--host-id-map", required=True, help="source_id to canonical_id map TSV.")
    parser.add_argument("--kaptive-k", required=True, help="Kaptive Klebsiella K-locus TSV.")
    parser.add_argument("--kaptive-o", required=True, help="Kaptive Klebsiella O-locus TSV.")
    parser.add_argument("--kleborate", required=True, help="Kleborate KpSC output TSV.")
    parser.add_argument("--host-archive", required=True, help="Reviewed PhageHostLearn host FASTA ZIP.")
    parser.add_argument("--kaptive-version", required=True, help="Kaptive version string.")
    parser.add_argument("--kleborate-version", required=True, help="Kleborate version string.")
    parser.add_argument("--kaptive-k-command", required=True, help="Exact Kaptive K command or reviewed command description.")
    parser.add_argument("--kaptive-o-command", required=True, help="Exact Kaptive O command or reviewed command description.")
    parser.add_argument("--kleborate-command", required=True, help="Exact Kleborate command or reviewed command description.")
    parser.add_argument("--kaptive-output", required=True, help="Normalized Kaptive evidence TSV.")
    parser.add_argument("--kleborate-output", required=True, help="Normalized Kleborate evidence TSV.")
    parser.add_argument("--report-output", required=True, help="Normalization review report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING_VALUES


def clean(value: str | None) -> str:
    return "NA" if is_missing(value) else value.strip()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise EvidenceError(f"Required input does not exist: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: "" if value is None else value.strip() for key, value in row.items()} for row in reader]
    if not fieldnames:
        raise EvidenceError(f"Input has no header: {path}")
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def write_tsv_temp(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    write_tsv(tmp, columns, rows)
    return tmp


def resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def validate_paths(args: argparse.Namespace) -> None:
    inputs = {
        "host_id_map": resolved(args.host_id_map),
        "kaptive_k": resolved(args.kaptive_k),
        "kaptive_o": resolved(args.kaptive_o),
        "kleborate": resolved(args.kleborate),
        "host_archive": resolved(args.host_archive),
    }
    outputs = {
        "kaptive_output": resolved(args.kaptive_output),
        "kleborate_output": resolved(args.kleborate_output),
        "report_output": resolved(args.report_output),
    }
    seen_outputs: dict[Path, str] = {}
    for name, output in outputs.items():
        if output in seen_outputs:
            raise EvidenceError(f"Output path collision: {name} and {seen_outputs[output]} both resolve to {output}")
        seen_outputs[output] = name
    for output_name, output in outputs.items():
        for input_name, input_path in inputs.items():
            if output == input_path:
                raise EvidenceError(f"Input/output path collision: {output_name} equals {input_name} ({output})")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_host_map(path: Path) -> dict[str, str]:
    _, rows = read_tsv(path)
    mapping: dict[str, str] = {}
    duplicate_sources: set[str] = set()
    duplicate_canonicals: set[str] = set()
    seen_canonicals: set[str] = set()
    for row in rows:
        status = row.get("review_status", "").strip().lower()
        if status not in REVIEWED_STATUSES:
            continue
        source_id = row.get("source_id", "").strip()
        canonical_id = row.get("canonical_id", "").strip()
        if not source_id or not canonical_id:
            continue
        if source_id in mapping:
            duplicate_sources.add(source_id)
        if canonical_id in seen_canonicals:
            duplicate_canonicals.add(canonical_id)
        mapping[source_id] = canonical_id
        seen_canonicals.add(canonical_id)
    if duplicate_sources:
        raise EvidenceError("Duplicate reviewed host source IDs: " + ";".join(sorted(duplicate_sources)))
    if duplicate_canonicals:
        raise EvidenceError("Duplicate reviewed host canonical IDs: " + ";".join(sorted(duplicate_canonicals)))
    if not mapping:
        raise EvidenceError(f"No reviewed host mappings found in {path}")
    return mapping


def resolve_source_id(sample: str, mapping: dict[str, str]) -> str:
    if sample in mapping:
        return sample
    if sample.endswith("_contig") and f"{sample}s" in mapping:
        return f"{sample}s"
    return ""


def index_by_sample(rows: list[dict[str, str]], sample_column: str, mapping: dict[str, str], source_name: str) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    duplicate_samples: set[str] = set()
    unmapped_samples: set[str] = set()
    for row in rows:
        sample = row.get(sample_column, "").strip()
        if not sample:
            raise EvidenceError(f"{source_name} row without {sample_column}")
        source_id = resolve_source_id(sample, mapping)
        if not source_id:
            unmapped_samples.add(sample)
            continue
        if source_id in indexed:
            duplicate_samples.add(source_id)
        indexed[source_id] = row
    if duplicate_samples:
        raise EvidenceError(f"Duplicate {source_name} sample IDs: " + ";".join(sorted(duplicate_samples)))
    if unmapped_samples:
        raise EvidenceError(f"Unmapped {source_name} sample IDs: " + ";".join(sorted(unmapped_samples)))
    return indexed


def source_note(*parts: str) -> str:
    return "; ".join(part for part in parts if part)


def normalize_kaptive(args: argparse.Namespace, mapping: dict[str, str], report: list[dict[str, str]], hashes: dict[str, str]) -> list[dict[str, str]]:
    _, k_rows = read_tsv(Path(args.kaptive_k))
    _, o_rows = read_tsv(Path(args.kaptive_o))
    k_by_sample = index_by_sample(k_rows, "Assembly", mapping, "Kaptive K")
    o_by_sample = index_by_sample(o_rows, "Assembly", mapping, "Kaptive O")
    missing_o = sorted(set(k_by_sample) - set(o_by_sample))
    missing_k = sorted(set(o_by_sample) - set(k_by_sample))
    if missing_k or missing_o:
        raise EvidenceError(f"Kaptive K/O sample mismatch; missing_k={missing_k}; missing_o={missing_o}")

    rows = []
    non_typeable = 0
    for sample in sorted(k_by_sample):
        k_row = k_by_sample[sample]
        o_row = o_by_sample[sample]
        k_conf = clean(k_row.get("Match confidence"))
        o_conf = clean(o_row.get("Match confidence"))
        if k_conf != "Typeable" or o_conf != "Typeable":
            non_typeable += 1
        rows.append(
            {
                "host_genome_id": mapping[sample],
                "kaptive_sample_id": clean(k_row.get("Assembly")),
                "K_locus": clean(k_row.get("Best match locus")),
                "K_type": clean(k_row.get("Best match type")),
                "K_confidence": k_conf,
                "O_locus": clean(o_row.get("Best match locus")),
                "O_type": clean(o_row.get("Best match type")),
                "O_confidence": o_conf,
                "kaptive_source": source_note(
                    f"Kaptive {args.kaptive_version}",
                    "K database=Klebsiella_k_locus_primary_reference",
                    "O database=Klebsiella_o_locus_primary_reference",
                    f"host_archive_sha256={hashes['host_archive']}",
                    f"kaptive_k_sha256={hashes['kaptive_k']}",
                    f"kaptive_o_sha256={hashes['kaptive_o']}",
                ),
                "evidence_source": source_note(f"tool=Kaptive", f"tool_version={args.kaptive_version}", "source=PhageHostLearn_2024_host_archive"),
                "notes": source_note(
                    "review_status=reviewed",
                    "source_study=phagehostlearn_2024",
                    "evidence_scope=host_KO_typing",
                    f"K_command={args.kaptive_k_command}",
                    f"O_command={args.kaptive_o_command}",
                    f"K_problems={clean(k_row.get('Problems'))}",
                    f"O_problems={clean(o_row.get('Problems'))}",
                ),
            }
        )
    report.append({"metric": "kaptive_rows", "value": str(len(rows)), "status": "pass", "notes": f"non_typeable_or_non_typeable_locus_rows={non_typeable}"})
    return rows


def collect_values(row: dict[str, str], prefixes: tuple[str, ...]) -> str:
    values = []
    for key, value in row.items():
        if any(key.startswith(prefix) for prefix in prefixes) and not is_missing(value):
            values.append(f"{key.split('__')[-1]}={value.strip()}")
    return ";".join(values) if values else "NA"


def normalize_kleborate(args: argparse.Namespace, mapping: dict[str, str], report: list[dict[str, str]], hashes: dict[str, str]) -> list[dict[str, str]]:
    _, rows = read_tsv(Path(args.kleborate))
    by_sample = index_by_sample(rows, "strain", mapping, "Kleborate")
    output = []
    not_tested = 0
    for sample in sorted(by_sample):
        row = by_sample[sample]
        st = clean(row.get("klebsiella_pneumo_complex__mlst__ST"))
        if st == "NA":
            not_tested += 1
        output.append(
            {
                "host_genome_id": mapping[sample],
                "kleborate_sample_id": sample,
                "species": clean(row.get("enterobacterales__species__species")),
                "species_match": clean(row.get("enterobacterales__species__species_match")),
                "mlst_scheme": "Kleborate_klebsiella_pneumo_complex__mlst" if st != "NA" else "NA",
                "ST": st,
                "virulence_score": clean(row.get("klebsiella_pneumo_complex__virulence_score__virulence_score")),
                "resistance_score": clean(row.get("klebsiella_pneumo_complex__resistance_score__resistance_score")),
                "AMR_markers": collect_values(row, ("klebsiella_pneumo_complex__amr__",)),
                "virulence_markers": collect_values(
                    row,
                    (
                        "klebsiella__ybst__Yersiniabactin",
                        "klebsiella__cbst__Colibactin",
                        "klebsiella__abst__Aerobactin",
                        "klebsiella__smst__Salmochelin",
                        "klebsiella__rmst__RmpADC",
                        "klebsiella__rmpa2__rmpA2",
                    ),
                ),
                "ybt": clean(row.get("klebsiella__ybst__Yersiniabactin")),
                "iuc": clean(row.get("klebsiella__abst__Aerobactin")),
                "iro": clean(row.get("klebsiella__smst__Salmochelin")),
                "rmpA": clean(row.get("klebsiella__rmst__rmpA")),
                "rmpA2": clean(row.get("klebsiella__rmpa2__rmpA2")),
                "kleborate_source": source_note(
                    f"Kleborate {args.kleborate_version}",
                    "preset=kpsc",
                    f"host_archive_sha256={hashes['host_archive']}",
                    f"kleborate_output_sha256={hashes['kleborate']}",
                ),
                "evidence_source": source_note(f"tool=Kleborate", f"tool_version={args.kleborate_version}", "source=PhageHostLearn_2024_host_archive"),
                "notes": source_note(
                    "review_status=reviewed",
                    "source_study=phagehostlearn_2024",
                    "evidence_scope=host_species_ST_AMR_virulence",
                    f"command={args.kleborate_command}",
                    f"QC_warnings={clean(row.get('general__contig_stats__QC_warnings'))}",
                ),
            }
        )
    missing_from_kleborate = sorted(set(mapping) - set(by_sample))
    report.append({"metric": "kleborate_rows", "value": str(len(output)), "status": "warning" if missing_from_kleborate else "pass", "notes": f"not_tested_ST_rows={not_tested}; mapped_hosts_without_kleborate_row={';'.join(missing_from_kleborate) if missing_from_kleborate else 'NA'}"})
    return output


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []
    temp_outputs: list[Path] = []
    try:
        validate_paths(args)
        hashes = {
            "host_archive": sha256(Path(args.host_archive)),
            "kaptive_k": sha256(Path(args.kaptive_k)),
            "kaptive_o": sha256(Path(args.kaptive_o)),
            "kleborate": sha256(Path(args.kleborate)),
        }
        mapping = load_host_map(Path(args.host_id_map))
        report.append({"metric": "reviewed_host_mappings", "value": str(len(mapping)), "status": "pass", "notes": str(Path(args.host_id_map))})
        report.append({"metric": "host_archive_sha256", "value": hashes["host_archive"], "status": "pass", "notes": str(Path(args.host_archive))})
        kaptive_rows = normalize_kaptive(args, mapping, report, hashes)
        kleborate_rows = normalize_kleborate(args, mapping, report, hashes)
        kaptive_tmp = write_tsv_temp(Path(args.kaptive_output), KAPTIVE_COLUMNS, kaptive_rows)
        kleborate_tmp = write_tsv_temp(Path(args.kleborate_output), KLEBORATE_COLUMNS, kleborate_rows)
        temp_outputs.extend([kaptive_tmp, kleborate_tmp])
        report.append({"metric": "kaptive_output_sha256", "value": sha256(kaptive_tmp), "status": "pass", "notes": args.kaptive_output})
        report.append({"metric": "kleborate_output_sha256", "value": sha256(kleborate_tmp), "status": "pass", "notes": args.kleborate_output})
        kaptive_tmp.replace(Path(args.kaptive_output))
        kleborate_tmp.replace(Path(args.kleborate_output))
        temp_outputs.clear()
    except EvidenceError as exc:
        for tmp in temp_outputs:
            if tmp.exists():
                tmp.unlink()
        report.append({"metric": "normalization_error", "value": "1", "status": "fail", "notes": str(exc)})
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        return 1
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Wrote {len(kaptive_rows)} Kaptive rows and {len(kleborate_rows)} Kleborate rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
