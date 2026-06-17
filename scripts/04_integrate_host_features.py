#!/usr/bin/env python3
"""Integrate manifest host metadata with optional Kleborate/Kaptive outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path
from typing import Iterable


PHAGE_LIKE_TYPES = {"phage", "prophage", "metagenomic_viral_contig"}

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
]

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
]

HOST_METADATA_COLUMNS = [
    "host_genome_id",
    "host_record_type",
    "host_record_source",
    "host_species",
    "host_strain",
    "source",
    "country",
    "year",
    "K_locus",
    "K_type",
    "O_locus",
    "O_type",
    "ST",
    "species_match",
    "AMR_markers",
    "virulence_markers",
    "ybt",
    "iuc",
    "iro",
    "rmpA",
    "rmpA2",
    "kleborate_status",
    "kaptive_status",
    "linked_phage_like_records",
    "linked_species_clusters",
    "notes",
]

PHAGE_HOST_LINK_COLUMNS = [
    "phage_genome_id",
    "record_type",
    "species_cluster_id",
    "representative_id",
    "host_genome_id",
    "host_link_status",
    "host_label",
    "host_species",
    "host_strain",
    "K_type",
    "O_type",
    "ST",
    "AMR_markers",
    "virulence_markers",
    "notes",
]

REPORT_COLUMNS = ["severity", "item", "message"]

SAMPLE_ID_ALIASES = [
    "host_genome_id",
    "genome_id",
    "sample",
    "Sample",
    "sample_id",
    "Sample ID",
    "strain",
    "Strain",
    "assembly",
    "Assembly",
    "isolate",
    "Isolate",
]

KLEBORATE_ALIASES = {
    "species": ["species", "Species", "species_match", "species_complex", "Kleborate species"],
    "species_match": ["species_match", "species_match_confidence", "species", "Species"],
    "mlst_scheme": ["mlst_scheme", "MLST scheme", "scheme"],
    "ST": ["ST", "st", "MLST", "sequence_type", "Sequence type"],
    "virulence_score": ["virulence_score", "virulence score", "virulence", "virulence_score_Kp"],
    "resistance_score": ["resistance_score", "resistance score", "resistance"],
    "AMR_markers": ["AMR_markers", "AMR", "acquired_AMR_genes", "resistance_genes", "resistance_gene_count", "Resistance genes"],
    "virulence_markers": ["virulence_markers", "virulence_genes", "Virulence genes"],
    "ybt": ["ybt", "YbST", "yersiniabactin"],
    "iuc": ["iuc", "aerobactin"],
    "iro": ["iro", "salmochelin"],
    "rmpA": ["rmpA"],
    "rmpA2": ["rmpA2"],
}

KAPTIVE_ALIASES = {
    "K_locus": ["K_locus", "K locus", "K_locus_best_match", "Best match locus", "Kaptive_K_locus"],
    "K_type": ["K_type", "K type", "K_locus_type", "Kaptive_K_type", "K"],
    "K_confidence": ["K_confidence", "K confidence", "K_locus_confidence", "Confidence", "Kaptive_K_confidence"],
    "O_locus": ["O_locus", "O locus", "O_locus_best_match", "O_best_match_locus", "Kaptive_O_locus"],
    "O_type": ["O_type", "O type", "O_locus_type", "Kaptive_O_type", "O"],
    "O_confidence": ["O_confidence", "O confidence", "O_locus_confidence", "Kaptive_O_confidence"],
}


class StageError(Exception):
    """Raised when required inputs are invalid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge manifest host metadata with optional Kleborate and Kaptive "
            "outputs, preserving phage records that lack linked host genomes."
        )
    )
    parser.add_argument("--manifest", required=True, help="Stage 1 manifest TSV.")
    parser.add_argument("--clusters", required=True, help="Stage 2 phage cluster TSV.")
    parser.add_argument("--kleborate-input", default="", help="Optional Kleborate-style TSV.")
    parser.add_argument("--kaptive-input", default="", help="Optional Kaptive-style TSV.")
    parser.add_argument("--host-metadata-output", required=True, help="Output integrated host metadata TSV.")
    parser.add_argument("--kaptive-output", required=True, help="Output normalized Kaptive TSV.")
    parser.add_argument("--kleborate-output", required=True, help="Output normalized Kleborate TSV.")
    parser.add_argument("--phage-host-links-output", required=True, help="Output phage/prophage to host link TSV.")
    parser.add_argument("--report-output", required=True, help="Output integration report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def normalize(value: str | None) -> str:
    return "" if value is None else value.strip()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(f"Required input does not exist: {path}")
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


def add_report(report: list[dict[str, str]], severity: str, item: str, message: str) -> None:
    report.append({"severity": severity, "item": item, "message": message})


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


def stable_metadata_host_id(host_species: str, host_strain: str, label: str) -> str:
    key = "|".join([host_species, host_strain, label]).lower()
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"metadata_host_{digest}"


def host_label(row: dict[str, str]) -> str:
    values = [row.get("host_species", ""), row.get("host_strain", ""), row.get("isolation_host", "")]
    values = [value for value in values if not is_missing(value)]
    return " | ".join(values) if values else ""


def normalize_kleborate(path_text: str, report: list[dict[str, str]]) -> list[dict[str, str]]:
    if is_missing(path_text):
        add_report(report, "info", "kleborate", "No Kleborate table supplied; Kleborate output contains headers only.")
        return []
    path = Path(path_text)
    if not path.exists():
        add_report(report, "warning", "kleborate", f"Kleborate table does not exist: {path}; continuing without it.")
        return []
    fieldnames, rows = read_tsv(path)
    if not fieldnames:
        add_report(report, "warning", "kleborate", f"Kleborate table has no header: {path}.")
        return []

    normalized = []
    skipped = 0
    for row in rows:
        host_id = first_value(row, SAMPLE_ID_ALIASES)
        if is_missing(host_id):
            skipped += 1
            continue
        out = {
            "host_genome_id": host_id,
            "kleborate_sample_id": first_value(row, SAMPLE_ID_ALIASES),
            "kleborate_source": str(path),
            "notes": "OK",
        }
        for column, aliases in KLEBORATE_ALIASES.items():
            out[column] = first_value(row, aliases)
        normalized.append(out)
    if skipped:
        add_report(report, "warning", "kleborate", f"Skipped {skipped} Kleborate rows without sample/genome identifier.")
    add_report(report, "info", "kleborate", f"Loaded {len(normalized)} normalized Kleborate rows from {path}.")
    return normalized


def normalize_kaptive(path_text: str, report: list[dict[str, str]]) -> list[dict[str, str]]:
    if is_missing(path_text):
        add_report(report, "info", "kaptive", "No Kaptive table supplied; Kaptive output contains headers only.")
        return []
    path = Path(path_text)
    if not path.exists():
        add_report(report, "warning", "kaptive", f"Kaptive table does not exist: {path}; continuing without it.")
        return []
    fieldnames, rows = read_tsv(path)
    if not fieldnames:
        add_report(report, "warning", "kaptive", f"Kaptive table has no header: {path}.")
        return []

    normalized = []
    skipped = 0
    for row in rows:
        host_id = first_value(row, SAMPLE_ID_ALIASES)
        if is_missing(host_id):
            skipped += 1
            continue
        out = {
            "host_genome_id": host_id,
            "kaptive_sample_id": first_value(row, SAMPLE_ID_ALIASES),
            "kaptive_source": str(path),
            "notes": "OK",
        }
        for column, aliases in KAPTIVE_ALIASES.items():
            out[column] = first_value(row, aliases)
        normalized.append(out)
    if skipped:
        add_report(report, "warning", "kaptive", f"Skipped {skipped} Kaptive rows without sample/genome identifier.")
    add_report(report, "info", "kaptive", f"Loaded {len(normalized)} normalized Kaptive rows from {path}.")
    return normalized


def load_clusters(path: Path) -> dict[str, dict[str, str]]:
    _, rows = read_tsv(path)
    return {row.get("genome_id", ""): row for row in rows if not is_missing(row.get("genome_id"))}


def host_entry_from_manifest(row: dict[str, str]) -> dict[str, str]:
    return {
        "host_genome_id": row.get("genome_id", ""),
        "host_record_type": "host_genome",
        "host_record_source": "manifest_host_record",
        "host_species": row.get("host_species", ""),
        "host_strain": row.get("host_strain", ""),
        "source": row.get("source", ""),
        "country": row.get("country", ""),
        "year": row.get("year", ""),
        "K_locus": "",
        "K_type": row.get("K_type", ""),
        "O_locus": "",
        "O_type": row.get("O_type", ""),
        "ST": row.get("ST", ""),
        "species_match": row.get("host_species", ""),
        "AMR_markers": row.get("AMR_markers", ""),
        "virulence_markers": row.get("virulence_markers", ""),
        "ybt": "",
        "iuc": "",
        "iro": "",
        "rmpA": "",
        "rmpA2": "",
        "kleborate_status": "not_supplied",
        "kaptive_status": "not_supplied",
        "linked_phage_like_records": "",
        "linked_species_clusters": "",
        "notes": "OK",
    }


def ensure_host_entry(hosts: dict[str, dict[str, str]], host_id: str, record_type: str, source: str) -> dict[str, str]:
    if host_id not in hosts:
        hosts[host_id] = {
            "host_genome_id": host_id,
            "host_record_type": record_type,
            "host_record_source": source,
            "host_species": "",
            "host_strain": "",
            "source": "",
            "country": "",
            "year": "",
            "K_locus": "",
            "K_type": "",
            "O_locus": "",
            "O_type": "",
            "ST": "",
            "species_match": "",
            "AMR_markers": "",
            "virulence_markers": "",
            "ybt": "",
            "iuc": "",
            "iro": "",
            "rmpA": "",
            "rmpA2": "",
            "kleborate_status": "not_supplied",
            "kaptive_status": "not_supplied",
            "linked_phage_like_records": "",
            "linked_species_clusters": "",
            "notes": "OK",
        }
    return hosts[host_id]


def set_if_present(row: dict[str, str], column: str, value: str) -> None:
    if not is_missing(value):
        row[column] = value


def merge_kleborate(hosts: dict[str, dict[str, str]], rows: list[dict[str, str]]) -> None:
    for source_row in rows:
        host_id = source_row["host_genome_id"]
        host = ensure_host_entry(hosts, host_id, "host_genome", "kleborate_only")
        set_if_present(host, "host_species", source_row.get("species", ""))
        set_if_present(host, "species_match", source_row.get("species_match", ""))
        set_if_present(host, "ST", source_row.get("ST", ""))
        set_if_present(host, "AMR_markers", source_row.get("AMR_markers", ""))
        set_if_present(host, "virulence_markers", source_row.get("virulence_markers", ""))
        for column in ["ybt", "iuc", "iro", "rmpA", "rmpA2"]:
            set_if_present(host, column, source_row.get(column, ""))
        host["kleborate_status"] = "supplied"


def merge_kaptive(hosts: dict[str, dict[str, str]], rows: list[dict[str, str]]) -> None:
    for source_row in rows:
        host_id = source_row["host_genome_id"]
        host = ensure_host_entry(hosts, host_id, "host_genome", "kaptive_only")
        for column in ["K_locus", "K_type", "O_locus", "O_type"]:
            set_if_present(host, column, source_row.get(column, ""))
        host["kaptive_status"] = "supplied"


def manifest_host_index(manifest_rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], dict[tuple[str, str], list[str]]]:
    host_rows = {
        row.get("genome_id", ""): row
        for row in manifest_rows
        if row.get("record_type") == "host" and not is_missing(row.get("genome_id"))
    }
    by_species_strain: dict[tuple[str, str], list[str]] = {}
    for host_id, row in host_rows.items():
        key = (row.get("host_species", "").lower(), row.get("host_strain", "").lower())
        if key != ("", ""):
            by_species_strain.setdefault(key, []).append(host_id)
    return host_rows, by_species_strain


def resolve_host_for_phage(
    row: dict[str, str],
    hosts: dict[str, dict[str, str]],
    manifest_host_rows: dict[str, dict[str, str]],
    by_species_strain: dict[tuple[str, str], list[str]],
) -> tuple[str, str, str]:
    source = row.get("source", "")
    if source in manifest_host_rows or source in hosts:
        return source, "source_matches_host_genome_id", "source field matches a host genome identifier"

    key = (row.get("host_species", "").lower(), row.get("host_strain", "").lower())
    if key in by_species_strain and len(by_species_strain[key]) == 1:
        return by_species_strain[key][0], "host_species_strain_exact_match", "matched one manifest host by species and strain"
    if key in by_species_strain and len(by_species_strain[key]) > 1:
        return "", "ambiguous_host_species_strain_match", "multiple manifest hosts match species and strain"

    label = host_label(row)
    if not is_missing(label):
        host_id = stable_metadata_host_id(row.get("host_species", ""), row.get("host_strain", ""), label)
        host = ensure_host_entry(hosts, host_id, "metadata_only_host", "phage_host_metadata")
        set_if_present(host, "host_species", row.get("host_species", "") or row.get("isolation_host", ""))
        set_if_present(host, "host_strain", row.get("host_strain", ""))
        set_if_present(host, "country", row.get("country", ""))
        set_if_present(host, "year", row.get("year", ""))
        set_if_present(host, "K_type", row.get("K_type", ""))
        set_if_present(host, "O_type", row.get("O_type", ""))
        set_if_present(host, "ST", row.get("ST", ""))
        host["notes"] = "metadata-only host; no host genome record linked"
        return host_id, "metadata_only_host_no_genome", "host metadata exists but no host genome record was linked"

    return "", "no_host_metadata", "no host metadata available for this phage-like record"


def build_phage_host_links(
    manifest_rows: list[dict[str, str]],
    clusters: dict[str, dict[str, str]],
    hosts: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    manifest_host_rows, by_species_strain = manifest_host_index(manifest_rows)
    links = []
    linked_by_host: dict[str, set[str]] = {}
    linked_clusters_by_host: dict[str, set[str]] = {}

    for row in manifest_rows:
        if row.get("record_type") not in PHAGE_LIKE_TYPES:
            continue
        genome_id = row.get("genome_id", "")
        cluster = clusters.get(genome_id, {})
        host_id, status, note = resolve_host_for_phage(row, hosts, manifest_host_rows, by_species_strain)
        host = hosts.get(host_id, {}) if host_id else {}
        if host_id:
            linked_by_host.setdefault(host_id, set()).add(genome_id)
            if not is_missing(cluster.get("cluster_id")):
                linked_clusters_by_host.setdefault(host_id, set()).add(cluster["cluster_id"])
        links.append(
            {
                "phage_genome_id": genome_id,
                "record_type": row.get("record_type", ""),
                "species_cluster_id": cluster.get("cluster_id", ""),
                "representative_id": cluster.get("representative_id", ""),
                "host_genome_id": host_id,
                "host_link_status": status,
                "host_label": host_label(row),
                "host_species": host.get("host_species", row.get("host_species", "")),
                "host_strain": host.get("host_strain", row.get("host_strain", "")),
                "K_type": host.get("K_type", row.get("K_type", "")),
                "O_type": host.get("O_type", row.get("O_type", "")),
                "ST": host.get("ST", row.get("ST", "")),
                "AMR_markers": host.get("AMR_markers", row.get("AMR_markers", "")),
                "virulence_markers": host.get("virulence_markers", row.get("virulence_markers", "")),
                "notes": note,
            }
        )

    for host_id, genome_ids in linked_by_host.items():
        hosts[host_id]["linked_phage_like_records"] = ";".join(sorted(genome_ids))
    for host_id, cluster_ids in linked_clusters_by_host.items():
        hosts[host_id]["linked_species_clusters"] = ";".join(sorted(cluster_ids))
    return links


def build_host_table(
    manifest_rows: list[dict[str, str]],
    kleborate_rows: list[dict[str, str]],
    kaptive_rows: list[dict[str, str]],
    clusters: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    hosts: dict[str, dict[str, str]] = {}
    for row in manifest_rows:
        if row.get("record_type") == "host" and not is_missing(row.get("genome_id")):
            hosts[row["genome_id"]] = host_entry_from_manifest(row)

    merge_kleborate(hosts, kleborate_rows)
    merge_kaptive(hosts, kaptive_rows)
    links = build_phage_host_links(manifest_rows, clusters, hosts)
    host_rows = [hosts[host_id] for host_id in sorted(hosts)]
    return host_rows, links


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []

    try:
        _, manifest_rows = read_tsv(Path(args.manifest))
        clusters = load_clusters(Path(args.clusters))
        add_report(report, "info", "manifest", f"Loaded {len(manifest_rows)} manifest rows and {len(clusters)} phage-like cluster rows.")
        kleborate_rows = normalize_kleborate(args.kleborate_input, report)
        kaptive_rows = normalize_kaptive(args.kaptive_input, report)
        host_rows, link_rows = build_host_table(manifest_rows, kleborate_rows, kaptive_rows, clusters)
        add_report(report, "info", "host_metadata", f"Integrated {len(host_rows)} host metadata rows and {len(link_rows)} phage-host links.")

        write_tsv(Path(args.kleborate_output), KLEBORATE_COLUMNS, kleborate_rows)
        write_tsv(Path(args.kaptive_output), KAPTIVE_COLUMNS, kaptive_rows)
        write_tsv(Path(args.host_metadata_output), HOST_METADATA_COLUMNS, host_rows)
        write_tsv(Path(args.phage_host_links_output), PHAGE_HOST_LINK_COLUMNS, link_rows)
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    except StageError:
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        return 1

    error_count = sum(1 for row in report if row["severity"] == "error")
    print(f"Integrated {len(host_rows)} host metadata rows and {len(link_rows)} phage-host links.")
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
