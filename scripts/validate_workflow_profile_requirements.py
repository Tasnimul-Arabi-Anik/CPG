#!/usr/bin/env python3
"""Validate workflow profile semantics and fail-closed production prerequisites."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable

from workflow_config import WorkflowConfigError, load_workflow_config, resolved_config_sha256


VALIDATION_COLUMNS = [
    "requirement_id",
    "workflow_profile",
    "evidence_class",
    "requirement",
    "observed",
    "status",
    "severity",
    "message",
]
REPORT_COLUMNS = ["severity", "item", "message"]
PRODUCTION_EVIDENCE_INPUTS = [
    "pairwise_similarity",
    "annotation_input",
    "domain_evidence",
    "structural_evidence",
    "kleborate_input",
    "kaptive_input",
    "host_defense_input",
    "phage_antidefense_input",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate workflow profile requirements without downloading data.")
    parser.add_argument("--config", required=True, help="Workflow config path to resolve and validate.")
    parser.add_argument("--validation-output", required=True, help="Per-requirement validation TSV.")
    parser.add_argument("--report-output", required=True, help="Summary report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for resolving relative paths.")
    return parser.parse_args()


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def row(req_id: str, profile: dict, requirement: str, observed: str, status: str, severity: str, message: str) -> dict[str, str]:
    return {
        "requirement_id": req_id,
        "workflow_profile": str(profile.get("name", "")),
        "evidence_class": str(profile.get("evidence_class", "")),
        "requirement": requirement,
        "observed": observed,
        "status": status,
        "severity": severity,
        "message": message,
    }


def status_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def validate_profile(config: dict, root: Path) -> list[dict[str, str]]:
    profile = config.get("profile", {}) if isinstance(config.get("profile", {}), dict) else {}
    paths = config.get("paths", {}) if isinstance(config.get("paths", {}), dict) else {}
    inputs = config.get("inputs", {}) if isinstance(config.get("inputs", {}), dict) else {}
    sequence_manifest = config.get("sequence_acquisition_manifest", {}) if isinstance(config.get("sequence_acquisition_manifest", {}), dict) else {}
    output: list[dict[str, str]] = []

    profile_name = str(profile.get("name", ""))
    evidence_class = str(profile.get("evidence_class", ""))
    output.append(row("profile_name", profile, "profile.name is declared", profile_name, "pass" if profile_name else "fail", "info" if profile_name else "error", "Profile name is required." if not profile_name else "Profile name is declared."))
    output.append(row("evidence_class", profile, "profile.evidence_class is declared", evidence_class, "pass" if evidence_class else "fail", "info" if evidence_class else "error", "Evidence class is required." if not evidence_class else "Evidence class is declared."))

    allows_claims = status_bool(profile.get("allows_biological_claims", False))
    output.append(row("biological_claims_disabled", profile, "Config alone must not permit biological claims", str(allows_claims).lower(), "fail" if allows_claims else "pass", "error" if allows_claims else "info", "Profile config cannot enable biological claims by itself." if allows_claims else "Biological claims remain disabled by profile config."))

    results_dir = str(paths.get("results_dir", ""))
    profile_results = str(profile.get("results_directory", ""))
    status = "pass" if results_dir and profile_results and results_dir == profile_results else "fail"
    output.append(row("results_namespace", profile, "paths.results_dir matches profile.results_directory", f"paths={results_dir}; profile={profile_results}", status, "info" if status == "pass" else "error", "Results namespace is explicit and profile-scoped." if status == "pass" else "Profile results_directory must match paths.results_dir."))

    if status_bool(profile.get("requires_sequence_checksums", False)):
        manifest_path = str(sequence_manifest.get("manifest", ""))
        manifest_enabled = status_bool(sequence_manifest.get("enabled", False))
        status = "pass" if manifest_enabled and manifest_path and Path(manifest_path).name == "sequence_acquisition_manifest.tsv" else "fail"
        output.append(row("sequence_checksum_manifest", profile, "checksum-requiring profile uses the production acquisition manifest", f"enabled={manifest_enabled}; manifest={manifest_path}", status, "info" if status == "pass" else "error", "Production checksum manifest is configured." if status == "pass" else "Checksum-requiring profiles must use data/metadata/sequence_acquisition_manifest.tsv."))

    if status_bool(profile.get("requires_production_external_evidence", False)):
        for input_key in PRODUCTION_EVIDENCE_INPUTS:
            value = str(inputs.get(input_key, "")).strip()
            exists = bool(value) and resolve_path(root, value).exists()
            status = "pass" if exists else "fail"
            output.append(row(f"production_input_{input_key}", profile, f"production input {input_key} is configured and exists", value or "<blank>", status, "info" if status == "pass" else "error", "Production evidence input exists." if status == "pass" else "Production profile is blocked until this reviewed evidence input is configured and present."))

        assay_path_text = str(inputs.get("phage_host_assays", "")).strip()
        assay_path = resolve_path(root, assay_path_text) if assay_path_text else Path("")
        assay_rows = read_tsv_rows(assay_path) if assay_path_text else []
        status = "pass" if assay_path_text and assay_path.exists() and assay_rows else "fail"
        output.append(row("production_assay_outcomes", profile, "production profile has populated tested phage-host assay outcomes", assay_path_text or "<blank>", status, "info" if status == "pass" else "error", "Production assay table has data rows." if status == "pass" else "Production profile is blocked until explicit tested phage-host assay outcomes are populated."))
    else:
        output.append(row("production_evidence_not_required", profile, "non-production profiles do not require production external evidence", str(profile.get("requires_production_external_evidence", False)).lower(), "pass", "info", "Profile can run as fixture/seed plumbing without production evidence claims."))

    return output


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    try:
        config = load_workflow_config(args.config, root)
        rows = validate_profile(config, root)
        rows.append(row("resolved_config_sha256", config.get("profile", {}), "resolved config SHA-256 is recorded", resolved_config_sha256(config), "pass", "info", "Resolved config checksum recorded for provenance."))
    except WorkflowConfigError as exc:
        rows = [
            {
                "requirement_id": "workflow_config_resolution",
                "workflow_profile": "",
                "evidence_class": "",
                "requirement": "workflow config resolves",
                "observed": args.config,
                "status": "fail",
                "severity": "error",
                "message": str(exc),
            }
        ]
    errors = [entry for entry in rows if entry.get("severity") == "error"]
    warnings = [entry for entry in rows if entry.get("severity") == "warning"]
    report = [
        {"severity": "info", "item": "workflow_profile_requirements", "message": f"rows={len(rows)}; errors={len(errors)}; warnings={len(warnings)}"}
    ]
    if errors:
        report.append({"severity": "error", "item": "workflow_profile_requirements", "message": "Profile requirements failed; production or claim-bearing execution is blocked."})
    write_tsv(Path(args.validation_output), VALIDATION_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Workflow profile requirement validation complete: rows={len(rows)}; errors={len(errors)}; warnings={len(warnings)}.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
