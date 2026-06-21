#!/usr/bin/env python3
"""Build sequence-backed CDS annotation rows for PhageHostLearn assay phages."""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable


ANNOTATION_COLUMNS = [
    "genome_id",
    "gene_id",
    "contig_id",
    "start",
    "end",
    "strand",
    "product",
    "protein_id",
    "protein_sequence",
    "protein_length_aa",
    "phrog_id",
    "phrog_category",
    "functional_category",
    "module_hint",
    "evidence",
    "tool",
    "evidence_source",
    "notes",
]

REPORT_COLUMNS = ["metric", "value", "status", "notes"]
REVIEWED_STATUSES = {"reviewed", "accepted", "approved"}
MISSING_VALUES = {"", "NA", "N/A", "na", "n/a", "None", "none", "-", "Not Tested", "not tested"}


class AnnotationError(Exception):
    """Raised when phage CDS evidence cannot be generated safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract reviewed PhageHostLearn phage FASTA members to a temporary "
            "workspace, run Prodigal, and write a normalized CDS annotation TSV."
        )
    )
    parser.add_argument("--phage-id-map", required=True, help="PhageHostLearn source_id to canonical_id map TSV.")
    parser.add_argument("--phage-manifest", required=True, help="Reviewed PhageHostLearn phage source manifest TSV.")
    parser.add_argument("--phage-archive", required=True, help="Reviewed PhageHostLearn phage FASTA ZIP.")
    parser.add_argument("--prodigal-executable", default="prodigal", help="Prodigal executable path.")
    parser.add_argument("--rbpbase", default="", help="Optional reviewed local PhageHostLearn RBPbase.csv for exact protein-sequence candidate matching.")
    parser.add_argument("--prodigal-version", required=True, help="Reviewed Prodigal version string.")
    parser.add_argument("--prodigal-mode", default="meta", choices=["meta", "single"], help="Prodigal mode to run.")
    parser.add_argument("--annotation-output", required=True, help="Normalized annotation TSV.")
    parser.add_argument("--report-output", required=True, help="Annotation build report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING_VALUES


def clean(value: str | None) -> str:
    return "NA" if is_missing(value) else value.strip()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise AnnotationError(f"Required input does not exist: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: "" if value is None else value.strip() for key, value in row.items()} for row in reader]
    if not fieldnames:
        raise AnnotationError(f"Input has no header: {path}")
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
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
        "phage_id_map": resolved(args.phage_id_map),
        "phage_manifest": resolved(args.phage_manifest),
        "phage_archive": resolved(args.phage_archive),
    }
    if not is_missing(args.rbpbase):
        inputs["rbpbase"] = resolved(args.rbpbase)
    outputs = {
        "annotation_output": resolved(args.annotation_output),
        "report_output": resolved(args.report_output),
    }
    if outputs["annotation_output"] == outputs["report_output"]:
        raise AnnotationError(f"Output path collision: annotation_output and report_output both resolve to {outputs['annotation_output']}")
    for output_name, output in outputs.items():
        for input_name, input_path in inputs.items():
            if output == input_path:
                raise AnnotationError(f"Input/output path collision: {output_name} equals {input_name} ({output})")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_notes(notes: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in notes.split(";"):
        part = part.strip()
        if "=" in part:
            key, value = part.split("=", 1)
            parsed[key.strip()] = value.strip()
    return parsed


def load_phage_map(path: Path) -> dict[str, str]:
    _, rows = read_tsv(path)
    mapping: dict[str, str] = {}
    duplicate_sources: set[str] = set()
    duplicate_canonicals: set[str] = set()
    seen_canonicals: set[str] = set()
    for row in rows:
        if row.get("review_status", "").strip().lower() not in REVIEWED_STATUSES:
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
        raise AnnotationError("Duplicate reviewed phage source IDs: " + ";".join(sorted(duplicate_sources)))
    if duplicate_canonicals:
        raise AnnotationError("Duplicate reviewed phage canonical IDs: " + ";".join(sorted(duplicate_canonicals)))
    if not mapping:
        raise AnnotationError(f"No reviewed phage mappings found in {path}")
    return mapping


def parse_score(value: str) -> float | None:
    if is_missing(value):
        return None
    try:
        score = float(value)
    except ValueError:
        return None
    return score if math.isfinite(score) else None


def load_rbpbase(path_text: str, mapping: dict[str, str]) -> tuple[dict[str, dict[str, list[dict[str, str]]]], str, int]:
    if is_missing(path_text):
        return {}, "NA", 0
    path = Path(path_text)
    if not path.exists():
        raise AnnotationError(f"RBPbase file does not exist: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        first_line = sample.splitlines()[0] if sample.splitlines() else ""
        delimiter = "	" if "	" in first_line else ","
        reader = csv.DictReader(handle, delimiter=delimiter)
        required = {"phage_ID", "protein_ID", "protein_sequence", "xgb_score"}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise AnnotationError(f"{path} missing required RBPbase columns: {', '.join(missing)}")
        grouped: dict[str, dict[str, list[dict[str, str]]]] = {}
        loaded = 0
        for row in reader:
            source_id = clean(row.get("phage_ID"))
            protein_sequence = re.sub(r"\s+", "", clean(row.get("protein_sequence"))).rstrip("*").upper()
            if source_id not in mapping or is_missing(protein_sequence):
                continue
            canonical_id = mapping[source_id]
            score = parse_score(row.get("xgb_score", ""))
            prepared = {
                "source_phage_id": source_id,
                "source_protein_id": clean(row.get("protein_ID")),
                "protein_sequence": protein_sequence,
                "xgb_score": "NA" if score is None else f"{score:.6f}",
            }
            grouped.setdefault(canonical_id, {}).setdefault(protein_sequence, []).append(prepared)
            loaded += 1
    return grouped, sha256(path), loaded


def load_manifest_members(path: Path, mapping: dict[str, str]) -> dict[str, dict[str, str]]:
    _, rows = read_tsv(path)
    members: dict[str, dict[str, str]] = {}
    duplicate_canonicals: set[str] = set()
    missing_sources: set[str] = set()
    for row in rows:
        if row.get("record_type", "") != "phage":
            continue
        notes = parse_notes(row.get("notes", ""))
        source_id = notes.get("source_id", "")
        zip_member = notes.get("zip_member", "")
        if source_id not in mapping:
            continue
        canonical_id = mapping[source_id]
        if canonical_id in members:
            duplicate_canonicals.add(canonical_id)
        if not zip_member:
            missing_sources.add(source_id)
            continue
        members[canonical_id] = {
            "source_id": source_id,
            "zip_member": zip_member,
            "genome_length": row.get("genome_length", ""),
            "gc_percent": row.get("gc_percent", ""),
            "manifest_notes": row.get("notes", ""),
        }
    missing_from_manifest = sorted(set(mapping.values()) - set(members))
    if duplicate_canonicals:
        raise AnnotationError("Duplicate reviewed phage manifest rows: " + ";".join(sorted(duplicate_canonicals)))
    if missing_sources:
        raise AnnotationError("Reviewed phage manifest rows missing zip_member: " + ";".join(sorted(missing_sources)))
    if missing_from_manifest:
        raise AnnotationError("Reviewed phage mappings missing from manifest: " + ";".join(missing_from_manifest))
    return members


def parse_fasta_bytes(data: bytes, member: str) -> tuple[str, str]:
    text = data.decode("utf-8-sig")
    header = ""
    sequence_parts: list[str] = []
    for line in text.splitlines():
        if not line:
            continue
        if line.startswith(">"):
            if header:
                raise AnnotationError(f"Expected one FASTA record in {member}, found multiple records")
            header = line[1:].strip()
        else:
            sequence_parts.append(re.sub(r"\s+", "", line).upper())
    sequence = "".join(sequence_parts)
    if not header or not sequence:
        raise AnnotationError(f"Empty or malformed FASTA member: {member}")
    if not re.fullmatch(r"[ACGTRYSWKMBDHVN.-]+", sequence):
        raise AnnotationError(f"Unexpected nucleotide characters in FASTA member: {member}")
    return header, sequence.replace("-", "")


def write_fasta(path: Path, header: str, sequence: str) -> None:
    with path.open("w", encoding="utf-8") as handle:
        handle.write(f">{header}\n")
        for i in range(0, len(sequence), 80):
            handle.write(sequence[i : i + 80] + "\n")


def parse_prodigal_faa(path: Path, genome_id: str, source_id: str, prodigal_version: str, prodigal_mode: str, archive_sha: str, member_sha: str, rbpbase_hits: dict[str, list[dict[str, str]]], rbpbase_sha: str, matched_rbpbase_ids: set[tuple[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current_header = ""
    sequence_parts: list[str] = []

    def flush() -> None:
        nonlocal current_header, sequence_parts
        if not current_header:
            return
        protein_sequence = re.sub(r"[^A-Za-z*]", "", "".join(sequence_parts)).rstrip("*").upper()
        parts = [part.strip() for part in current_header.split(" # ")]
        if len(parts) < 4:
            raise AnnotationError(f"Could not parse Prodigal protein header for {genome_id}: {current_header}")
        gene_index = len(rows) + 1
        gene_id = f"prodigal_{gene_index:05d}"
        strand = "+" if parts[3] == "1" else "-" if parts[3] == "-1" else parts[3]
        rbp_matches = rbpbase_hits.get(protein_sequence, [])
        rbp_ids = sorted({match["source_protein_id"] for match in rbp_matches if not is_missing(match.get("source_protein_id"))})
        rbp_scores = [parse_score(match.get("xgb_score", "")) for match in rbp_matches]
        rbp_scores = [score for score in rbp_scores if score is not None]
        for match in rbp_matches:
            if not is_missing(match.get("source_protein_id")):
                matched_rbpbase_ids.add((genome_id, match["source_protein_id"]))
        has_rbpbase = bool(rbp_matches)
        product = "RBPbase receptor-binding protein candidate" if has_rbpbase else "hypothetical protein"
        functional_category = "receptor_binding_candidate" if has_rbpbase else "unannotated_cds"
        module_hint = "rbp_depolymerase" if has_rbpbase else ""
        evidence = "sequence_backed_cds_prediction;RBPbase_ML_candidate" if has_rbpbase else "sequence_backed_cds_prediction"
        tool = f"Prodigal {prodigal_version};RBPbase" if has_rbpbase else f"Prodigal {prodigal_version}"
        rbp_note = ""
        if has_rbpbase:
            max_score_text = f"{max(rbp_scores):.6f}" if rbp_scores else "NA"
            rbp_note = (
                f"; rbpbase_protein_ids={';'.join(rbp_ids)}; "
                f"rbpbase_max_xgb_score={max_score_text}; "
                f"rbpbase_sha256={rbpbase_sha}"
            )
        rows.append(
            {
                "genome_id": genome_id,
                "gene_id": gene_id,
                "contig_id": genome_id,
                "start": parts[1],
                "end": parts[2],
                "strand": strand,
                "product": product,
                "protein_id": f"{genome_id}|{gene_id}",
                "protein_sequence": protein_sequence,
                "protein_length_aa": str(len(protein_sequence)),
                "phrog_id": "NA",
                "phrog_category": "NA",
                "functional_category": functional_category,
                "module_hint": module_hint,
                "evidence": evidence,
                "tool": tool,
                "evidence_source": f"tool=Prodigal; tool_version={prodigal_version}; mode={prodigal_mode}; source=PhageHostLearn_2024_phage_archive" + ("; candidate_source=PhageHostLearn_RBPbase" if has_rbpbase else ""),
                "notes": (
                    "review_status=reviewed; source_study=phagehostlearn_2024; "
                    "evidence_scope=baseline_CDS_prediction_with_optional_RBPbase_ML_candidate_not_domain_or_structural_annotation; "
                    f"source_id={source_id}; phage_archive_sha256={archive_sha}; member_sha256={member_sha}"
                    f"{rbp_note}"
                ),
            }
        )
        current_header = ""
        sequence_parts = []

    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                flush()
                current_header = line[1:].strip()
            else:
                sequence_parts.append(line)
    flush()
    return rows


def run_prodigal(args: argparse.Namespace, genome_id: str, source_id: str, sequence: str, archive_sha: str, member_sha: str, workdir: Path, rbpbase_hits: dict[str, list[dict[str, str]]], rbpbase_sha: str, matched_rbpbase_ids: set[tuple[str, str]]) -> list[dict[str, str]]:
    workdir.mkdir(parents=True, exist_ok=True)
    input_fasta = workdir / f"{genome_id}.fna"
    faa_output = workdir / f"{genome_id}.faa"
    sco_output = workdir / f"{genome_id}.sco"
    write_fasta(input_fasta, genome_id, sequence)
    cmd = [
        args.prodigal_executable,
        "-i",
        input_fasta.as_posix(),
        "-a",
        faa_output.as_posix(),
        "-f",
        "sco",
        "-o",
        sco_output.as_posix(),
        "-p",
        args.prodigal_mode,
        "-q",
    ]
    completed = subprocess.run(cmd, check=False, text=True, capture_output=True)
    if completed.returncode != 0:
        raise AnnotationError(f"Prodigal failed for {genome_id}: {completed.stderr.strip() or completed.stdout.strip()}")
    if not faa_output.exists():
        raise AnnotationError(f"Prodigal did not create protein output for {genome_id}")
    return parse_prodigal_faa(faa_output, genome_id, source_id, args.prodigal_version, args.prodigal_mode, archive_sha, member_sha, rbpbase_hits, rbpbase_sha, matched_rbpbase_ids)


def build_annotations(args: argparse.Namespace, mapping: dict[str, str], members: dict[str, dict[str, str]], archive_sha: str, rbpbase_by_phage: dict[str, dict[str, list[dict[str, str]]]], rbpbase_sha: str, report: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    no_cds: list[str] = []
    length_mismatches: list[str] = []
    matched_rbpbase_ids: set[tuple[str, str]] = set()
    with zipfile.ZipFile(args.phage_archive) as archive, tempfile.TemporaryDirectory(prefix="phagehostlearn-prodigal-") as tmp:
        names = set(archive.namelist())
        work_root = Path(tmp)
        for canonical_id in sorted(mapping.values()):
            member_info = members[canonical_id]
            member = member_info["zip_member"]
            if member not in names:
                raise AnnotationError(f"Archive member missing for {canonical_id}: {member}")
            data = archive.read(member)
            member_sha = hashlib.sha256(data).hexdigest()
            _header, sequence = parse_fasta_bytes(data, member)
            expected_length = member_info.get("genome_length", "")
            if expected_length and expected_length.isdigit() and int(expected_length) != len(sequence):
                length_mismatches.append(f"{canonical_id}:{expected_length}!={len(sequence)}")
            phage_rows = run_prodigal(args, canonical_id, member_info["source_id"], sequence, archive_sha, member_sha, work_root / canonical_id, rbpbase_by_phage.get(canonical_id, {}), rbpbase_sha, matched_rbpbase_ids)
            rows.extend(phage_rows)
            if not phage_rows:
                no_cds.append(canonical_id)
    if length_mismatches:
        report.append({"metric": "sequence_length_mismatches", "value": str(len(length_mismatches)), "status": "warning", "notes": ";".join(length_mismatches[:25])})
    if no_cds:
        report.append({"metric": "phages_without_cds", "value": str(len(no_cds)), "status": "warning", "notes": ";".join(no_cds)})
    if rbpbase_by_phage:
        total_rbpbase_rows = sum(len(matches) for by_sequence in rbpbase_by_phage.values() for matches in by_sequence.values())
        rbpbase_phages = {genome for genome, by_sequence in rbpbase_by_phage.items() if by_sequence}
        matched_phages = {genome for genome, _protein in matched_rbpbase_ids}
        report.append({"metric": "rbpbase_source_rows", "value": str(total_rbpbase_rows), "status": "pass", "notes": f"reviewed_phages_with_rbpbase_rows={len(rbpbase_phages)}; rbpbase_sha256={rbpbase_sha}"})
        report.append({"metric": "rbpbase_exact_source_row_matches", "value": str(len(matched_rbpbase_ids)), "status": "pass" if matched_rbpbase_ids else "warning", "notes": f"matched_phages={len(matched_phages)}"})
    return rows


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []
    temp_outputs: list[Path] = []
    try:
        validate_paths(args)
        archive_sha = sha256(Path(args.phage_archive))
        mapping = load_phage_map(Path(args.phage_id_map))
        members = load_manifest_members(Path(args.phage_manifest), mapping)
        rbpbase_by_phage, rbpbase_sha, rbpbase_rows = load_rbpbase(args.rbpbase, mapping)
        report.append({"metric": "reviewed_phage_mappings", "value": str(len(mapping)), "status": "pass", "notes": str(Path(args.phage_id_map))})
        report.append({"metric": "manifest_phage_rows", "value": str(len(members)), "status": "pass", "notes": str(Path(args.phage_manifest))})
        report.append({"metric": "phage_archive_sha256", "value": archive_sha, "status": "pass", "notes": str(Path(args.phage_archive))})
        if rbpbase_rows:
            report.append({"metric": "rbpbase_rows_loaded", "value": str(rbpbase_rows), "status": "pass", "notes": args.rbpbase})
        annotation_rows = build_annotations(args, mapping, members, archive_sha, rbpbase_by_phage, rbpbase_sha, report)
        annotated_phages = {row["genome_id"] for row in annotation_rows}
        report.append({"metric": "annotated_phages", "value": str(len(annotated_phages)), "status": "pass" if len(annotated_phages) == len(mapping) else "warning", "notes": f"expected={len(mapping)}"})
        report.append({"metric": "annotation_rows", "value": str(len(annotation_rows)), "status": "pass" if annotation_rows else "fail", "notes": "baseline CDS predictions only"})
        tmp = write_tsv_temp(Path(args.annotation_output), ANNOTATION_COLUMNS, annotation_rows)
        temp_outputs.append(tmp)
        report.append({"metric": "annotation_output_sha256", "value": sha256(tmp), "status": "pass", "notes": args.annotation_output})
        tmp.replace(Path(args.annotation_output))
        temp_outputs.clear()
    except (AnnotationError, zipfile.BadZipFile) as exc:
        for tmp in temp_outputs:
            if tmp.exists():
                tmp.unlink()
        report.append({"metric": "annotation_error", "value": "1", "status": "fail", "notes": str(exc)})
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        return 1
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Wrote {len(annotation_rows)} Prodigal CDS annotation rows for {len({row['genome_id'] for row in annotation_rows})} phages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
