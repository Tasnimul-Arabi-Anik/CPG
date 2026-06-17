#!/usr/bin/env python3
"""Create reviewed-export query command sheets from source_query_plan.tsv."""

from __future__ import annotations

import argparse
import csv
import shlex
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus


COMMAND_COLUMNS = [
    "query_id",
    "source_id",
    "record_layer",
    "target_database",
    "expected_export_path",
    "template_path",
    "requires_network",
    "review_mode",
    "web_url",
    "command_text",
    "output_contract",
    "review_checklist",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create query command sheets for reviewed local source exports.")
    parser.add_argument("--source-query-plan", required=True, help="Source query plan TSV.")
    parser.add_argument("--template-manifest", required=True, help="Source export template manifest TSV.")
    parser.add_argument("--commands-output", required=True, help="Output command sheet TSV.")
    parser.add_argument("--shell-output", required=True, help="Output shell handoff file with non-executing command comments.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def template_by_query(rows: list[dict[str, str]]) -> dict[str, str]:
    return {row.get("query_id", ""): row.get("template_path", "") for row in rows if not is_missing(row.get("query_id"))}


def ncbi_url(database: str, query: str) -> str:
    db = "nuccore"
    if "assembly" in database.lower():
        db = "assembly"
    return f"https://www.ncbi.nlm.nih.gov/{db}/?term={quote_plus(query)}"


def pubmed_url(query: str) -> str:
    return f"https://pubmed.ncbi.nlm.nih.gov/?term={quote_plus(query)}"


def inphared_url() -> str:
    return "https://github.com/RyanCook94/INPHARED"


def review_checklist(row: dict[str, str]) -> str:
    checks = [
        "save as TSV at expected_export_path",
        "preserve accession/genome identity columns",
        "remove obvious non-Klebsiella or non-phage contamination where applicable",
        "record provenance and snapshot/date in notes",
        "keep raw downloaded files separate from reviewed export if used",
    ]
    if row.get("record_layer") == "host_genomes":
        checks.append("retain K/O/ST/AMR/virulence fields or mark missing explicitly")
    if row.get("record_layer") == "prophages":
        checks.append("retain host genome ID and prophage coordinate/protein provenance in notes")
    if row.get("record_layer") == "metagenomic_discovery":
        checks.append("keep discovery contigs separate from primary cultured/prophage atlas")
    return "; ".join(checks)


def route_for(row: dict[str, str], template_path: str) -> dict[str, str]:
    target = row.get("target_database", "")
    target_lower = target.lower()
    query = row.get("query_string", "")
    export_path = row.get("expected_export_path", "")
    quoted_export = shlex.quote(export_path)
    quoted_template = shlex.quote(template_path) if template_path else ""

    if "ncbi" in target_lower and "assembly" in target_lower:
        web_url = ncbi_url(target, query)
        command = (
            f"printf 'Review NCBI Assembly search results and export selected metadata as TSV. URL: {web_url} Template: {quoted_template}\\n' "
            f"&& mkdir -p {shlex.quote(str(Path(export_path).parent))} && printf 'Populate reviewed host-genome export: %s\\n' {quoted_export}"
        )
        return {"requires_network": "true", "review_mode": "ncbi_assembly_reviewed_export", "web_url": web_url, "command_text": command}

    if "ncbi" in target_lower or "genbank" in target_lower or "refseq" in target_lower:
        web_url = ncbi_url(target, query)
        command = (
            f"printf 'Review NCBI nucleotide/virus search results and export selected metadata as TSV. URL: {web_url} Template: {quoted_template}\\n' "
            f"&& mkdir -p {shlex.quote(str(Path(export_path).parent))} && printf 'Populate reviewed phage export: %s\\n' {quoted_export}"
        )
        return {"requires_network": "true", "review_mode": "ncbi_nucleotide_reviewed_export", "web_url": web_url, "command_text": command}

    if "literature" in target_lower or "manual" in target_lower:
        web_url = pubmed_url(query)
        command = (
            f"printf 'Review literature records and accession tables. PubMed URL: {web_url} Template: {quoted_template}\\n' "
            f"&& mkdir -p {shlex.quote(str(Path(export_path).parent))} && printf 'Populate reviewed literature export: %s\\n' {quoted_export}"
        )
        return {"requires_network": "true", "review_mode": "manual_literature_review", "web_url": web_url, "command_text": command}

    if "inphared" in target_lower:
        web_url = inphared_url()
        command = (
            f"printf 'Use a reviewed INPHARED snapshot/export filtered for Klebsiella hosts. Project URL: {web_url} Template: {quoted_template}\\n' "
            f"&& mkdir -p {shlex.quote(str(Path(export_path).parent))} && printf 'Populate reviewed INPHARED export: %s\\n' {quoted_export}"
        )
        return {"requires_network": "true", "review_mode": "inphared_snapshot_review", "web_url": web_url, "command_text": command}

    if "prophage" in target_lower or row.get("record_layer") == "prophages":
        command = (
            f"printf 'Generate local prophage-mining export with host K/O/ST links. Template: {quoted_template}\\n' "
            f"&& mkdir -p {shlex.quote(str(Path(export_path).parent))} && printf 'Populate reviewed prophage export: %s\\n' {quoted_export}"
        )
        return {"requires_network": "false", "review_mode": "local_prophage_mining_export", "web_url": "", "command_text": command}

    if "metagenomic" in target_lower or row.get("record_layer") == "metagenomic_discovery":
        command = (
            f"printf 'Generate or review local viral-contig discovery table. Template: {quoted_template}\\n' "
            f"&& mkdir -p {shlex.quote(str(Path(export_path).parent))} && printf 'Populate reviewed metagenomic discovery export: %s\\n' {quoted_export}"
        )
        return {"requires_network": "false", "review_mode": "local_discovery_export", "web_url": "", "command_text": command}

    command = f"mkdir -p {shlex.quote(str(Path(export_path).parent))} && printf 'Populate reviewed export: %s\\n' {quoted_export}"
    return {"requires_network": "false", "review_mode": "reviewed_local_export", "web_url": "", "command_text": command}


def build_commands(query_rows: list[dict[str, str]], templates: dict[str, str]) -> list[dict[str, str]]:
    commands = []
    for row in query_rows:
        template_path = templates.get(row.get("query_id", ""), "")
        route = route_for(row, template_path)
        commands.append(
            {
                "query_id": row.get("query_id", ""),
                "source_id": row.get("source_id", ""),
                "record_layer": row.get("record_layer", ""),
                "target_database": row.get("target_database", ""),
                "expected_export_path": row.get("expected_export_path", ""),
                "template_path": template_path,
                "requires_network": route["requires_network"],
                "review_mode": route["review_mode"],
                "web_url": route["web_url"],
                "command_text": route["command_text"],
                "output_contract": "Reviewed TSV matching required columns and identity fields; no automatic trust of external metadata.",
                "review_checklist": review_checklist(row),
                "notes": row.get("notes", ""),
            }
        )
    return commands


def write_shell(path: Path, commands: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Reviewed-export command sheet generated by scripts/create_source_query_commands.py.",
        "# The commands below do not download data automatically. They print or document",
        "# the reviewed export paths that must be populated before enabling real sources.",
        "",
    ]
    for row in commands:
        lines.extend(
            [
                f"# Query: {row['query_id']} ({row['source_id']})",
                f"# Target: {row['target_database']}",
                f"# Web URL: {row['web_url'] or 'NA'}",
                row["command_text"],
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    _, query_rows = read_tsv(Path(args.source_query_plan))
    _, template_rows = read_tsv(Path(args.template_manifest))
    commands = build_commands(query_rows, template_by_query(template_rows))
    write_tsv(Path(args.commands_output), COMMAND_COLUMNS, commands)
    write_shell(Path(args.shell_output), commands)
    network = sum(1 for row in commands if row.get("requires_network") == "true")
    report = [
        {"severity": "info", "item": "source_query_commands", "message": f"commands={len(commands)}; network_review={network}; local_review={len(commands) - network}"}
    ]
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Wrote {len(commands)} source query command rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
