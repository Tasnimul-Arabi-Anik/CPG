#!/usr/bin/env python3
"""Normalize reviewed RBP/depolymerase domain and structural evidence outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable


PROVENANCE_COLUMNS = [
    "tool",
    "tool_version",
    "database",
    "database_version",
    "command",
    "run_date",
    "input_checksum",
    "output_checksum",
]

DOMAIN_COLUMNS = [
    "annotation_gene_id",
    "domain_id",
    "domain_name",
    "start_aa",
    "end_aa",
    "evalue",
    "evidence_source",
    "notes",
] + PROVENANCE_COLUMNS

STRUCTURAL_COLUMNS = [
    "annotation_gene_id",
    "structural_hit_id",
    "structural_hit_name",
    "tm_score",
    "probability",
    "evidence_source",
    "notes",
] + PROVENANCE_COLUMNS

REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}

ANNOTATION_ID_ALIASES = ["annotation_gene_id", "protein_id", "query", "qseqid", "gene_id", "id"]
DEFAULT_FOLDSEEK_FIELDS = "query,target,alntmscore,prob,evalue"
DEFAULT_PHOLD_FIELDS = "annotation_gene_id,structural_hit_id,structural_hit_name,probability"


class NormalizationError(Exception):
    """Raised for malformed reviewed evidence inputs."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize reviewed external RBP/depolymerase evidence into the TSV "
            "schemas consumed by Stage 4. This script does not run HMMER, Phold, or Foldseek."
        )
    )
    parser.add_argument("--domain-input", default="", help="Optional reviewed domain/profile result file.")
    parser.add_argument(
        "--domain-format",
        default="generic_tsv",
        choices=["generic_tsv", "hmmer_domtblout"],
        help="Format for --domain-input.",
    )
    parser.add_argument(
        "--hmmer-mode",
        default="hmmsearch",
        choices=["hmmsearch", "hmmscan"],
        help="HMMER search orientation for domtblout: hmmsearch means target=protein/query=profile; hmmscan means query=protein/target=profile.",
    )
    parser.add_argument("--structural-input", default="", help="Optional reviewed structural result file.")
    parser.add_argument(
        "--structural-format",
        default="generic_tsv",
        choices=["generic_tsv", "foldseek_tsv", "phold_tsv"],
        help="Format for --structural-input.",
    )
    parser.add_argument(
        "--foldseek-fields",
        default=DEFAULT_FOLDSEEK_FIELDS,
        help="Comma-separated Foldseek --format-output fields for headerless foldseek_tsv input.",
    )
    parser.add_argument(
        "--phold-fields",
        default=DEFAULT_PHOLD_FIELDS,
        help="Comma-separated field names for headerless phold_tsv input.",
    )
    parser.add_argument(
        "--annotation-manifest",
        default="",
        help="Optional Stage 3 annotation or protein manifest TSV used to validate annotation_gene_id values.",
    )
    parser.add_argument("--tool", default="", help="Tool name to record in normalized evidence provenance.")
    parser.add_argument("--tool-version", default="", help="Tool version to record in normalized evidence provenance.")
    parser.add_argument("--database", default="", help="Database/profile/template set name used for the search.")
    parser.add_argument("--database-version", default="", help="Database/profile/template set version used for the search.")
    parser.add_argument("--command", default="", help="Reviewed command used to generate the input evidence.")
    parser.add_argument("--run-date", default="", help="Reviewed run or retrieval date for the input evidence.")
    parser.add_argument(
        "--overwrite-empty",
        action="store_true",
        help="When an evidence input is absent, overwrite an existing output with a header-only table. Without this flag, existing outputs are preserved.",
    )
    parser.add_argument("--domain-output", required=True, help="Output normalized domain evidence TSV.")
    parser.add_argument("--structural-output", required=True, help="Output normalized structural evidence TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: object) -> bool:
    return normalize(value) in MISSING


def add_report(report: list[dict[str, str]], severity: str, item: str, message: str) -> None:
    report.append({"severity": severity, "item": item, "message": message})


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_checksum(row: dict[str, str], columns: list[str]) -> str:
    payload = {column: row.get(column, "") for column in columns if column != "output_checksum"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def add_output_checksums(rows: list[dict[str, str]], columns: list[str]) -> list[dict[str, str]]:
    output = []
    for row in rows:
        row = dict(row)
        row["output_checksum"] = row_checksum(row, columns)
        output.append(row)
    return output


def provenance(path: Path, args: argparse.Namespace | None, default_tool: str, evidence_source: str) -> dict[str, str]:
    return {
        "evidence_source": evidence_source,
        "tool": normalize(getattr(args, "tool", "")) or default_tool,
        "tool_version": normalize(getattr(args, "tool_version", "")),
        "database": normalize(getattr(args, "database", "")),
        "database_version": normalize(getattr(args, "database_version", "")),
        "command": normalize(getattr(args, "command", "")),
        "run_date": normalize(getattr(args, "run_date", "")),
        "input_checksum": file_sha256(path),
        "output_checksum": "",
    }


def with_provenance(row: dict[str, str], prov: dict[str, str]) -> dict[str, str]:
    output = dict(row)
    for column in ["evidence_source"] + PROVENANCE_COLUMNS:
        if column == "evidence_source":
            output[column] = output.get(column) or prov.get(column, "")
        else:
            output[column] = prov.get(column, "")
    return output


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise NormalizationError(f"Input does not exist: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    if not fieldnames:
        raise NormalizationError(f"Input has no header: {path}")
    return fieldnames, rows


def read_headerless_or_headered(path: Path, fields_text: str, format_name: str) -> list[dict[str, str]]:
    if not path.exists():
        raise NormalizationError(f"Input does not exist: {path}")
    lines = [line.rstrip("\n") for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip() and not line.startswith("#")]
    if not lines:
        return []
    first = split_record_line(lines[0])
    lower_first = {value.lower() for value in first}
    known_headers = {
        "query", "target", "qseqid", "tseqid", "annotation_gene_id", "protein_id", "structural_hit_id",
        "tm_score", "alntmscore", "prob", "probability", "pdb_hit", "product",
    }
    has_header = bool(lower_first & known_headers)
    if has_header:
        fieldnames = first
        data_lines = lines[1:]
    else:
        fieldnames = [field.strip() for field in fields_text.replace(";", ",").split(",") if field.strip()]
        data_lines = lines
    if not fieldnames:
        raise NormalizationError(f"No {format_name} fields were supplied for headerless input: {path}")
    rows: list[dict[str, str]] = []
    for line_number, line in enumerate(data_lines, start=2 if has_header else 1):
        values = split_record_line(line)
        if len(values) != len(fieldnames):
            raise NormalizationError(
                f"Malformed {format_name} row {line_number}: expected {len(fieldnames)} fields from format schema, observed {len(values)}"
            )
        rows.append({field: normalize(value) for field, value in zip(fieldnames, values)})
    return rows


def split_record_line(line: str) -> list[str]:
    if "\t" in line:
        return [value.strip() for value in line.split("\t")]
    return line.split()


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def first_value(row: dict[str, str], aliases: list[str]) -> str:
    for alias in aliases:
        if alias in row and not is_missing(row[alias]):
            return row[alias]
    lowered = {key.lower().replace(" ", "_"): value for key, value in row.items()}
    for alias in aliases:
        key = alias.lower().replace(" ", "_")
        if key in lowered and not is_missing(lowered[key]):
            return lowered[key]
    return ""


def load_annotation_ids(path_text: str) -> set[str]:
    if is_missing(path_text):
        return set()
    path = Path(path_text)
    fieldnames, rows = read_tsv(path)
    ids = set()
    for row in rows:
        value = first_value(row, ANNOTATION_ID_ALIASES)
        if not is_missing(value):
            ids.add(value)
    if not ids and fieldnames:
        raise NormalizationError(f"Annotation manifest has no recognizable annotation IDs: {path}")
    return ids


def parse_float(value: str, field: str, row_id: str, minimum: float | None = None, maximum: float | None = None) -> str:
    if is_missing(value):
        return ""
    try:
        parsed = float(value)
    except ValueError as exc:
        raise NormalizationError(f"{row_id}: {field} is not numeric: {value}") from exc
    if minimum is not None and parsed < minimum:
        raise NormalizationError(f"{row_id}: {field} is below {minimum:g}: {value}")
    if maximum is not None and parsed > maximum:
        raise NormalizationError(f"{row_id}: {field} is above {maximum:g}: {value}")
    return f"{parsed:g}"


def parse_probability(value: str, row_id: str) -> str:
    if is_missing(value):
        return ""
    parsed = parse_float(value, "probability", row_id, 0.0, 100.0)
    numeric = float(parsed)
    if numeric > 1.0:
        numeric = numeric / 100.0
    return f"{numeric:g}"


def parse_int_field(value: str, field: str, row_id: str) -> str:
    if is_missing(value):
        return ""
    try:
        parsed_float = float(value)
    except ValueError as exc:
        raise NormalizationError(f"{row_id}: {field} is not an integer coordinate: {value}") from exc
    if not parsed_float.is_integer():
        raise NormalizationError(f"{row_id}: {field} is not an integer coordinate: {value}")
    parsed = int(parsed_float)
    if parsed <= 0:
        raise NormalizationError(f"{row_id}: {field} must be positive: {value}")
    return str(parsed)


def normalize_domain_generic(path: Path, prov: dict[str, str] | None = None) -> list[dict[str, str]]:
    _, rows = read_tsv(path)
    prov = prov or provenance(path, None, "generic_domain_review", f"generic_tsv:{path}")
    output = []
    for row in rows:
        annotation_gene_id = first_value(row, ["annotation_gene_id", "target_name", "target", "protein_id", "query", "qseqid"])
        domain_id = first_value(row, ["domain_id", "hmm_id", "profile_id", "query_name", "domain", "sseqid"])
        domain_name = first_value(row, ["domain_name", "hmm_name", "profile_name", "query_description", "description", "hit_name"])
        if is_missing(annotation_gene_id) and is_missing(domain_id):
            continue
        output.append(
            with_provenance(
                {
                    "annotation_gene_id": annotation_gene_id,
                    "domain_id": domain_id,
                    "domain_name": domain_name or domain_id,
                    "start_aa": first_value(row, ["start_aa", "ali_from", "qstart", "start"]),
                    "end_aa": first_value(row, ["end_aa", "ali_to", "qend", "end"]),
                    "evalue": first_value(row, ["evalue", "i_evalue", "E-value", "eval"]),
                    "evidence_source": first_value(row, ["evidence_source", "tool", "source"]) or prov["evidence_source"],
                    "notes": first_value(row, ["notes"]) or "normalized reviewed domain evidence",
                },
                prov,
            )
        )
    return output


def normalize_domain_hmmer_domtblout(path: Path, hmmer_mode: str = "hmmsearch", prov: dict[str, str] | None = None) -> list[dict[str, str]]:
    if hmmer_mode not in {"hmmsearch", "hmmscan"}:
        raise NormalizationError(f"Unsupported hmmer mode: {hmmer_mode}")
    prov = prov or provenance(path, None, "hmmer", f"hmmer_domtblout:{path}")
    output = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(maxsplit=22)
            if len(parts) < 22:
                raise NormalizationError(f"Malformed HMMER domtblout row {line_number}: expected at least 22 columns, observed {len(parts)}")
            target_name = parts[0]
            target_accession = parts[1]
            query_name = parts[3]
            query_accession = parts[4]
            i_evalue = parts[12]
            ali_from = parts[17]
            ali_to = parts[18]
            description = parts[22] if len(parts) > 22 else ""
            if hmmer_mode == "hmmsearch":
                annotation_gene_id = target_name
                domain_id = query_accession if not is_missing(query_accession) and query_accession != "-" else query_name
                domain_name = query_name
            else:
                annotation_gene_id = query_name
                domain_id = target_accession if not is_missing(target_accession) and target_accession != "-" else target_name
                domain_name = description or target_name
            output.append(
                with_provenance(
                    {
                        "annotation_gene_id": annotation_gene_id,
                        "domain_id": domain_id,
                        "domain_name": domain_name or domain_id,
                        "start_aa": ali_from,
                        "end_aa": ali_to,
                        "evalue": i_evalue,
                        "evidence_source": prov["evidence_source"],
                        "notes": f"normalized reviewed HMMER domtblout evidence; hmmer_mode={hmmer_mode}",
                    },
                    prov,
                )
            )
    return output


def normalize_structural_generic(path: Path, prov: dict[str, str] | None = None) -> list[dict[str, str]]:
    _, rows = read_tsv(path)
    prov = prov or provenance(path, None, "generic_structural_review", f"generic_tsv:{path}")
    return normalize_structural_rows(rows, prov, "generic structural evidence")


def normalize_structural_rows(rows: list[dict[str, str]], prov: dict[str, str], notes: str) -> list[dict[str, str]]:
    output = []
    for row in rows:
        annotation_gene_id = first_value(row, ["annotation_gene_id", "query", "qseqid", "protein_id", "target_name"])
        hit_id = first_value(row, ["structural_hit_id", "target", "tseqid", "sseqid", "hit_id", "template", "fold", "pdb_hit", "phold_hit"])
        hit_name = first_value(row, ["structural_hit_name", "target_name", "hit_name", "description", "template_name", "product", "function"])
        if is_missing(annotation_gene_id) and is_missing(hit_id):
            continue
        output.append(
            with_provenance(
                {
                    "annotation_gene_id": annotation_gene_id,
                    "structural_hit_id": hit_id,
                    "structural_hit_name": hit_name or hit_id,
                    "tm_score": first_value(row, ["tm_score", "alntmscore", "qtmscore", "ttmscore", "tmscore", "foldseek_tm_score"]),
                    "probability": first_value(row, ["probability", "prob", "confidence", "phold_probability"]),
                    "evidence_source": first_value(row, ["evidence_source", "tool", "source"]) or prov["evidence_source"],
                    "notes": first_value(row, ["notes"]) or f"normalized reviewed {notes}",
                },
                prov,
            )
        )
    return output


def normalize_structural_foldseek(path: Path, fields_text: str = DEFAULT_FOLDSEEK_FIELDS, prov: dict[str, str] | None = None) -> list[dict[str, str]]:
    prov = prov or provenance(path, None, "foldseek", f"foldseek_tsv:{path}")
    rows = read_headerless_or_headered(path, fields_text, "foldseek_tsv")
    return normalize_structural_rows(rows, prov, "Foldseek structural evidence")


def normalize_structural_phold(path: Path, fields_text: str = DEFAULT_PHOLD_FIELDS, prov: dict[str, str] | None = None) -> list[dict[str, str]]:
    prov = prov or provenance(path, None, "phold", f"phold_tsv:{path}")
    rows = read_headerless_or_headered(path, fields_text, "phold_tsv")
    return normalize_structural_rows(rows, prov, "Phold structural evidence")


def validate_domain_rows(rows: list[dict[str, str]], allowed_ids: set[str], report: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str, str]] = set()
    output = []
    duplicate_count = 0
    for row in rows:
        row_id = row.get("annotation_gene_id", "<missing_annotation_gene_id>")
        if is_missing(row.get("annotation_gene_id")):
            raise NormalizationError("Domain evidence row is missing annotation_gene_id")
        if allowed_ids and row["annotation_gene_id"] not in allowed_ids:
            raise NormalizationError(f"Unknown annotation_gene_id in domain evidence: {row['annotation_gene_id']}")
        if is_missing(row.get("domain_id")):
            raise NormalizationError(f"{row_id}: domain_id is required")
        row["start_aa"] = parse_int_field(row.get("start_aa", ""), "start_aa", row_id)
        row["end_aa"] = parse_int_field(row.get("end_aa", ""), "end_aa", row_id)
        if row["start_aa"] and row["end_aa"] and int(row["start_aa"]) > int(row["end_aa"]):
            raise NormalizationError(f"{row_id}: start_aa is greater than end_aa")
        row["evalue"] = parse_float(row.get("evalue", ""), "evalue", row_id, 0.0, None)
        key = (row["annotation_gene_id"], row["domain_id"], row.get("start_aa", ""), row.get("end_aa", ""))
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        output.append(row)
    if duplicate_count:
        add_report(report, "warning", "domain_duplicates", f"Skipped {duplicate_count} duplicate domain evidence rows.")
    return add_output_checksums(output, DOMAIN_COLUMNS)


def validate_structural_rows(rows: list[dict[str, str]], allowed_ids: set[str], report: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    output = []
    duplicate_count = 0
    for row in rows:
        row_id = row.get("annotation_gene_id", "<missing_annotation_gene_id>")
        if is_missing(row.get("annotation_gene_id")):
            raise NormalizationError("Structural evidence row is missing annotation_gene_id")
        if allowed_ids and row["annotation_gene_id"] not in allowed_ids:
            raise NormalizationError(f"Unknown annotation_gene_id in structural evidence: {row['annotation_gene_id']}")
        if is_missing(row.get("structural_hit_id")):
            raise NormalizationError(f"{row_id}: structural_hit_id is required")
        row["tm_score"] = parse_float(row.get("tm_score", ""), "tm_score", row_id, 0.0, 1.0)
        row["probability"] = parse_probability(row.get("probability", ""), row_id)
        key = (row["annotation_gene_id"], row["structural_hit_id"])
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        output.append(row)
    if duplicate_count:
        add_report(report, "warning", "structural_duplicates", f"Skipped {duplicate_count} duplicate structural evidence rows.")
    return add_output_checksums(output, STRUCTURAL_COLUMNS)


def maybe_write_empty_output(path: Path, columns: list[str], overwrite_empty: bool, report: list[dict[str, str]], item: str) -> None:
    if path.exists() and not overwrite_empty:
        add_report(report, "info", item, f"no input supplied; preserved existing output because --overwrite-empty was not set: {path}")
        return
    write_tsv(path, columns, [])
    add_report(report, "info", item, f"no input supplied; wrote header-only output: {path}")


def normalize_domain_from_args(args: argparse.Namespace, allowed_ids: set[str], report: list[dict[str, str]]) -> list[dict[str, str]]:
    path = Path(args.domain_input)
    if not path.exists():
        raise NormalizationError(f"Domain input does not exist: {path}")
    prov = provenance(path, args, "hmmer" if args.domain_format == "hmmer_domtblout" else "generic_domain_review", f"{args.domain_format}:{path}")
    if args.domain_format == "hmmer_domtblout":
        rows = normalize_domain_hmmer_domtblout(path, args.hmmer_mode, prov)
    else:
        rows = normalize_domain_generic(path, prov)
    rows = validate_domain_rows(rows, allowed_ids, report)
    add_report(report, "info", "domain_evidence", f"normalized_rows={len(rows)}; input={path}; format={args.domain_format}")
    return rows


def normalize_structural_from_args(args: argparse.Namespace, allowed_ids: set[str], report: list[dict[str, str]]) -> list[dict[str, str]]:
    path = Path(args.structural_input)
    if not path.exists():
        raise NormalizationError(f"Structural input does not exist: {path}")
    default_tool = {"foldseek_tsv": "foldseek", "phold_tsv": "phold"}.get(args.structural_format, "generic_structural_review")
    prov = provenance(path, args, default_tool, f"{args.structural_format}:{path}")
    if args.structural_format == "foldseek_tsv":
        rows = normalize_structural_foldseek(path, args.foldseek_fields, prov)
    elif args.structural_format == "phold_tsv":
        rows = normalize_structural_phold(path, args.phold_fields, prov)
    else:
        rows = normalize_structural_generic(path, prov)
    rows = validate_structural_rows(rows, allowed_ids, report)
    add_report(report, "info", "structural_evidence", f"normalized_rows={len(rows)}; input={path}; format={args.structural_format}")
    return rows


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []
    domain_rows: list[dict[str, str]] = []
    structural_rows: list[dict[str, str]] = []

    try:
        allowed_ids = load_annotation_ids(args.annotation_manifest)
        if allowed_ids:
            add_report(report, "info", "annotation_manifest", f"loaded_annotation_gene_ids={len(allowed_ids)}; path={args.annotation_manifest}")

        domain_output = Path(args.domain_output)
        structural_output = Path(args.structural_output)
        if not is_missing(args.domain_input):
            domain_rows = normalize_domain_from_args(args, allowed_ids, report)
            write_tsv(domain_output, DOMAIN_COLUMNS, domain_rows)
        else:
            maybe_write_empty_output(domain_output, DOMAIN_COLUMNS, args.overwrite_empty, report, "domain_evidence")

        if not is_missing(args.structural_input):
            structural_rows = normalize_structural_from_args(args, allowed_ids, report)
            write_tsv(structural_output, STRUCTURAL_COLUMNS, structural_rows)
        else:
            maybe_write_empty_output(structural_output, STRUCTURAL_COLUMNS, args.overwrite_empty, report, "structural_evidence")

    except NormalizationError as exc:
        add_report(report, "error", "normalization", str(exc))
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        print(f"RBP external evidence normalization failed: {exc}")
        return 1

    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"RBP external evidence normalization complete: domain_rows={len(domain_rows)}; structural_rows={len(structural_rows)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
