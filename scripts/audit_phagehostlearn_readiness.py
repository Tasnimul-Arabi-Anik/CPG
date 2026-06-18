#!/usr/bin/env python3
"""Audit readiness of the PhageHostLearn benchmark import path."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable


READINESS_COLUMNS = [
    "check_id",
    "area",
    "status",
    "severity",
    "blocking_for_assay_import",
    "evidence_path",
    "evidence_summary",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
REVIEWED = {"reviewed", "accepted", "approved"}


class ReadinessAuditError(Exception):
    """Raised when readiness audit inputs are malformed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit PhageHostLearn benchmark import readiness.")
    parser.add_argument("--phage-export", default="data/metadata/source_exports/phagehostlearn_2024_phages.tsv")
    parser.add_argument("--host-export", default="data/metadata/source_exports/phagehostlearn_2024_hosts.tsv")
    parser.add_argument("--phage-map", default="data/metadata/assay_source_exports/phagehostlearn_2024_phage_id_map.tsv")
    parser.add_argument("--host-map", default="data/metadata/assay_source_exports/phagehostlearn_2024_host_id_map.tsv")
    parser.add_argument("--assay-export", default="data/metadata/assay_source_exports/reviewed_klebsiella_phage_host_assays.tsv")
    parser.add_argument("--source-imports", default="config/source_imports.yaml")
    parser.add_argument("--source-catalog", default="config/source_catalog.yaml")
    parser.add_argument("--readiness-output", required=True)
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--root", default=".")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: object) -> bool:
    return normalize(value) in MISSING


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment issue
        raise ReadinessAuditError("PyYAML is required for source config audits.") from exc
    if not path.exists():
        raise ReadinessAuditError(f"Missing YAML input: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ReadinessAuditError(f"YAML input must be a mapping: {path}")
    return data


def note_value(notes: str, key: str) -> str:
    match = re.search(rf"(?:^|;\s*){re.escape(key)}=([^;]+)", notes)
    return match.group(1).strip() if match else ""


def add_row(
    rows: list[dict[str, str]],
    check_id: str,
    area: str,
    status: str,
    severity: str,
    blocking: bool,
    evidence_path: str,
    summary: str,
    next_action: str,
) -> None:
    rows.append(
        {
            "check_id": check_id,
            "area": area,
            "status": status,
            "severity": severity,
            "blocking_for_assay_import": "true" if blocking else "false",
            "evidence_path": evidence_path,
            "evidence_summary": summary,
            "next_action": next_action,
        }
    )


def config_item(config: dict, collection: str, key_name: str, source_id: str) -> dict:
    items = config.get(collection, [])
    if not isinstance(items, list):
        return {}
    for item in items:
        if isinstance(item, dict) and item.get(key_name) == source_id:
            return item
    return {}


def enabled_state(config: dict, collection: str, key_name: str, source_id: str) -> tuple[bool, bool]:
    item = config_item(config, collection, key_name, source_id)
    return bool(item), bool(item.get("enabled", False))


def review_filter_state(config: dict, collection: str, key_name: str, source_id: str) -> tuple[bool, bool, bool, str]:
    item = config_item(config, collection, key_name, source_id)
    if not item:
        return False, False, False, "NA"
    raw_statuses = item.get("required_note_review_statuses", [])
    if isinstance(raw_statuses, str):
        statuses = [raw_statuses]
    elif isinstance(raw_statuses, list):
        statuses = [normalize(status) for status in raw_statuses]
    else:
        statuses = []
    normalized_statuses = {status.lower() for status in statuses if status}
    review_filtered = bool(normalized_statuses & REVIEWED)
    return True, bool(item.get("enabled", False)), review_filtered, ",".join(sorted(normalized_statuses)) or "NA"


def entity_summary(export_rows: list[dict[str, str]], entity_type: str) -> dict[str, int]:
    source_ids = [note_value(row.get("notes", ""), "source_id") for row in export_rows]
    source_ids = [sid for sid in source_ids if sid]
    raw_paths = [row.get("raw_sequence_path", "") for row in export_rows]
    if entity_type == "phage":
        with_inventory = sum(1 for row in export_rows if not is_missing(row.get("genome_length")) and not is_missing(row.get("gc_percent")))
        missing_sequence = sum(1 for row in export_rows if is_missing(row.get("raw_sequence_path")))
        pending_review = sum(1 for row in export_rows if "review_status=pending_entity_review" in row.get("notes", ""))
        return {
            "rows": len(export_rows),
            "source_ids": len(set(source_ids)),
            "with_inventory": with_inventory,
            "missing_raw_path": missing_sequence,
            "pending_entity_review": pending_review,
        }
    missing_k = sum(1 for row in export_rows if is_missing(row.get("K_type")))
    missing_o = sum(1 for row in export_rows if is_missing(row.get("O_type")))
    missing_st = sum(1 for row in export_rows if is_missing(row.get("ST")))
    missing_raw_path = sum(1 for path in raw_paths if is_missing(path))
    pending_review = sum(1 for row in export_rows if "review_status=pending_entity_review" in row.get("notes", ""))
    return {
        "rows": len(export_rows),
        "source_ids": len(set(source_ids)),
        "missing_K_type": missing_k,
        "missing_O_type": missing_o,
        "missing_ST": missing_st,
        "missing_raw_path": missing_raw_path,
        "pending_entity_review": pending_review,
    }


def map_summary(map_rows: list[dict[str, str]], source_ids: set[str], canonical_ids: set[str]) -> dict[str, int]:
    mapped_source_ids = {row.get("source_id", "") for row in map_rows if row.get("source_id")}
    canonical_values = [row.get("canonical_id", "") for row in map_rows]
    reviewed = sum(1 for row in map_rows if row.get("review_status", "").lower() in REVIEWED)
    pending = sum(1 for row in map_rows if row.get("review_status", "").lower() == "pending")
    missing_canonical = sum(1 for value in canonical_values if is_missing(value))
    unresolved_canonical = sum(1 for value in canonical_values if not is_missing(value) and value not in canonical_ids)
    return {
        "rows": len(map_rows),
        "source_ids": len(mapped_source_ids),
        "missing_source_ids": len(source_ids - mapped_source_ids),
        "extra_source_ids": len(mapped_source_ids - source_ids),
        "reviewed": reviewed,
        "pending": pending,
        "unreviewed": len(map_rows) - reviewed,
        "missing_canonical": missing_canonical,
        "unresolved_canonical": unresolved_canonical,
    }


def map_structural_blocking(stats: dict[str, int]) -> bool:
    return any(stats[key] for key in ("missing_source_ids", "extra_source_ids", "missing_canonical", "unresolved_canonical"))


def map_readiness(stats: dict[str, int]) -> tuple[str, str, bool]:
    structural_blocking = map_structural_blocking(stats)
    if structural_blocking:
        return "fail_structural_map", "error", True
    if stats["reviewed"] == 0:
        return "blocked_no_reviewed_rows", "warning", True
    if stats["reviewed"] < stats["rows"]:
        return "partial_reviewed_subset", "warning", False
    return "pass", "info", False


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    phage_export = resolve(root, args.phage_export)
    host_export = resolve(root, args.host_export)
    phage_map = resolve(root, args.phage_map)
    host_map = resolve(root, args.host_map)
    assay_export = resolve(root, args.assay_export)
    source_imports = resolve(root, args.source_imports)
    source_catalog = resolve(root, args.source_catalog)
    readiness: list[dict[str, str]] = []

    phage_fields, phage_rows = read_tsv(phage_export)
    host_fields, host_rows = read_tsv(host_export)
    _phage_map_fields, phage_map_rows = read_tsv(phage_map)
    _host_map_fields, host_map_rows = read_tsv(host_map)
    _assay_fields, assay_rows = read_tsv(assay_export)
    imports_cfg = load_yaml(source_imports)
    catalog_cfg = load_yaml(source_catalog)

    phage_ids = {row.get("genome_id", "") for row in phage_rows if row.get("genome_id")}
    host_ids = {row.get("genome_id", "") for row in host_rows if row.get("genome_id")}
    phage_source_ids = {note_value(row.get("notes", ""), "source_id") for row in phage_rows}
    host_source_ids = {note_value(row.get("notes", ""), "source_id") for row in host_rows}
    phage_source_ids.discard("")
    host_source_ids.discard("")

    phage_stats = entity_summary(phage_rows, "phage")
    add_row(
        readiness,
        "PHL001",
        "phage_entities",
        "pass" if phage_stats["rows"] else "fail",
        "info" if phage_stats["rows"] else "error",
        not bool(phage_stats["rows"]),
        display(root, phage_export),
        "; ".join(f"{key}={value}" for key, value in phage_stats.items()),
        "Review missing FASTA inventory cases and local raw sequence provenance before enabling source.",
    )

    host_stats = entity_summary(host_rows, "host")
    host_blocking = host_stats["rows"] == 0
    add_row(
        readiness,
        "PHL002",
        "host_entities",
        "pass" if not host_blocking else "fail",
        "warning" if host_stats.get("missing_K_type", 0) else "info",
        host_blocking,
        display(root, host_export),
        "; ".join(f"{key}={value}" for key, value in host_stats.items()),
        "Populate host genome acquisition and K/O/ST evidence before production host-range modeling.",
    )

    phage_map_stats = map_summary(phage_map_rows, phage_source_ids, phage_ids)
    phage_map_status, phage_map_severity, phage_map_blocking = map_readiness(phage_map_stats)
    add_row(
        readiness,
        "PHL003",
        "phage_id_map",
        phage_map_status,
        phage_map_severity,
        phage_map_blocking,
        display(root, phage_map),
        "; ".join(f"{key}={value}" for key, value in phage_map_stats.items()),
        "Review pending phage source-to-canonical map rows; reviewed rows may be imported as a filtered subset.",
    )

    host_map_stats = map_summary(host_map_rows, host_source_ids, host_ids)
    host_map_status, host_map_severity, host_map_blocking = map_readiness(host_map_stats)
    add_row(
        readiness,
        "PHL004",
        "host_id_map",
        host_map_status,
        host_map_severity,
        host_map_blocking,
        display(root, host_map),
        "; ".join(f"{key}={value}" for key, value in host_map_stats.items()),
        "Review pending host source-to-canonical map rows; K/O/ST provenance remains separate from source identity review.",
    )

    import_found_phage, import_enabled_phage, import_filtered_phage, import_filter_phage = review_filter_state(imports_cfg, "imports", "import_id", "phagehostlearn_2024_phages")
    import_found_host, import_enabled_host, import_filtered_host, import_filter_host = review_filter_state(imports_cfg, "imports", "import_id", "phagehostlearn_2024_hosts")
    catalog_found_phage, catalog_enabled_phage = enabled_state(catalog_cfg, "sources", "source_id", "phagehostlearn_2024_phages")
    catalog_found_host, catalog_enabled_host = enabled_state(catalog_cfg, "sources", "source_id", "phagehostlearn_2024_hosts")
    phage_unfiltered_enablement = (import_enabled_phage or catalog_enabled_phage) and phage_stats.get("pending_entity_review", 0) > 0 and not import_filtered_phage
    host_unfiltered_enablement = (import_enabled_host or catalog_enabled_host) and host_stats.get("pending_entity_review", 0) > 0 and not import_filtered_host
    enabled_too_early = phage_unfiltered_enablement or host_unfiltered_enablement
    any_enabled = import_enabled_phage or import_enabled_host or catalog_enabled_phage or catalog_enabled_host
    any_filtered = import_filtered_phage or import_filtered_host
    if enabled_too_early:
        enablement_status = "fail_unfiltered_enablement"
    elif any_enabled and any_filtered:
        enablement_status = "pass_review_filtered_subset_enabled"
    elif any_enabled:
        enablement_status = "pass_enabled_no_pending_review"
    else:
        enablement_status = "pass_disabled_pending_review"
    add_row(
        readiness,
        "PHL005",
        "source_enablement",
        enablement_status,
        "info" if not enabled_too_early else "error",
        enabled_too_early,
        f"{display(root, source_imports)};{display(root, source_catalog)}",
        f"imports_found={int(import_found_phage)+int(import_found_host)}; catalog_found={int(catalog_found_phage)+int(catalog_found_host)}; imports_enabled={int(import_enabled_phage)+int(import_enabled_host)}; catalog_enabled={int(catalog_enabled_phage)+int(catalog_enabled_host)}; import_review_filtered={int(import_filtered_phage)+int(import_filtered_host)}; phage_filter_statuses={import_filter_phage}; host_filter_statuses={import_filter_host}",
        "Keep benchmark imports review-filtered until all pending entities are reviewed; catalog enablement must consume filtered manifests.",
    )

    assay_populated = len([row for row in assay_rows if any(not is_missing(v) for v in row.values())])
    assay_ready = assay_populated > 0 and not (phage_map_blocking or host_map_blocking)
    if assay_ready:
        assay_status = "pass"
    elif phage_map_blocking or host_map_blocking:
        assay_status = "blocked_no_reviewed_map_subset"
    else:
        assay_status = "blocked_no_reviewed_assay_rows"
    add_row(
        readiness,
        "PHL006",
        "assay_export",
        assay_status,
        "info" if assay_ready else "warning",
        not assay_ready,
        display(root, assay_export),
        f"assay_rows={assay_populated}; phage_map_blocking={phage_map_blocking}; host_map_blocking={host_map_blocking}",
        "Normalize reviewed map subsets into canonical assay rows; keep pending IDs excluded until reviewed.",
    )

    blocking = [row for row in readiness if row["blocking_for_assay_import"] == "true"]
    report = [
        {
            "severity": "info",
            "item": "phagehostlearn_readiness",
            "message": f"checks={len(readiness)}; blocking={len(blocking)}; assay_ready={assay_ready}",
        }
    ]
    if blocking:
        report.append({"severity": "warning", "item": "phagehostlearn_readiness", "message": "Benchmark assay import remains blocked pending reviewed source subsets and/or safe source enablement."})
    else:
        report.append({"severity": "info", "item": "phagehostlearn_readiness", "message": "Benchmark reviewed subset is ready for canonical assay import."})
    write_tsv(resolve(root, args.readiness_output), READINESS_COLUMNS, readiness)
    write_tsv(resolve(root, args.report_output), REPORT_COLUMNS, report)
    print(f"PhageHostLearn readiness audit complete: checks={len(readiness)}; blocking={len(blocking)}.")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except ReadinessAuditError as exc:
        root = Path(args.root).resolve()
        report = [{"severity": "error", "item": "phagehostlearn_readiness", "message": str(exc)}]
        write_tsv(resolve(root, args.report_output), REPORT_COLUMNS, report)
        print(f"PhageHostLearn readiness audit failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
