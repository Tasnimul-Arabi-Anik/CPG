#!/usr/bin/env python3
"""Self-test external evidence acceptance and provenance lint scenarios."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from typing import Iterable

import check_external_evidence_acceptance as acceptance


TEST_COLUMNS = [
    "test_id",
    "scenario",
    "expected_acceptance_status",
    "observed_acceptance_status",
    "expected_blocking",
    "observed_blocking",
    "expected_lint_contains",
    "observed_provenance_lint",
    "expected_content_lint_contains",
    "observed_content_lint",
    "status",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
PLAN_COLUMNS = [
    "evidence_id",
    "analysis_layer",
    "optional_input_key",
    "configured_input_path",
    "configured_input_exists",
    "configured_input_rows",
    "configured_input_schema_status",
    "evidence_status",
    "evidence_origin",
    "real_claim_use_status",
    "blocking_for_manuscript",
    "next_action",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for external evidence acceptance.")
    parser.add_argument("--output", required=True, help="Output self-test result TSV.")
    parser.add_argument("--report-output", required=True, help="Output self-test report TSV.")
    return parser.parse_args()


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def plan_row(
    tmpdir: Path,
    evidence_id: str,
    evidence_path: Path | None,
    evidence_status: str,
    schema_status: str,
    rows: str,
    next_action: str = "self-test next action",
) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "analysis_layer": "self_test_layer",
        "optional_input_key": evidence_id + "_input",
        "configured_input_path": evidence_path.as_posix() if evidence_path else "",
        "configured_input_exists": "true" if evidence_path and evidence_path.exists() else "false",
        "configured_input_rows": rows,
        "configured_input_schema_status": schema_status,
        "evidence_status": evidence_status,
        "evidence_origin": "configured_reviewed_tsv" if evidence_path else "not_configured",
        "real_claim_use_status": "usable_after_source_and_claim_audits" if evidence_path else "not_usable_for_real_claims",
        "blocking_for_manuscript": "true",
        "next_action": next_action,
    }


def check_case(
    tmpdir: Path,
    test_id: str,
    scenario: str,
    evidence_body: str | None,
    evidence_status: str,
    schema_status: str,
    configured_rows: str,
    expected_acceptance_status: str,
    expected_blocking: str,
    expected_lint_contains: str = "",
    expected_content_lint_contains: str = "",
    evidence_id: str | None = None,
    evidence_subpath: str | None = None,
) -> dict[str, str]:
    evidence_path: Path | None = None
    if evidence_body is not None:
        evidence_path = tmpdir / (evidence_subpath or f"{test_id}.tsv")
        write_text(evidence_path, evidence_body)
    plan_path = tmpdir / f"{test_id}_plan.tsv"
    plan_evidence_id = evidence_id or test_id
    write_tsv(plan_path, PLAN_COLUMNS, [plan_row(tmpdir, plan_evidence_id, evidence_path, evidence_status, schema_status, configured_rows)])
    rows, _ = acceptance.check_acceptance(tmpdir, plan_path)
    observed = rows[0] if rows else {}
    observed_lint = observed.get("provenance_lint", "")
    observed_content_lint = observed.get("content_lint", "")
    status_ok = observed.get("acceptance_status") == expected_acceptance_status
    blocking_ok = observed.get("blocking_issue") == expected_blocking
    lint_ok = True if not expected_lint_contains else expected_lint_contains in observed_lint
    content_lint_ok = True if not expected_content_lint_contains else expected_content_lint_contains in observed_content_lint
    passed = status_ok and blocking_ok and lint_ok and content_lint_ok
    notes = []
    if not status_ok:
        notes.append("status_mismatch")
    if not blocking_ok:
        notes.append("blocking_mismatch")
    if not lint_ok:
        notes.append("lint_mismatch")
    if not content_lint_ok:
        notes.append("content_lint_mismatch")
    return {
        "test_id": test_id,
        "scenario": scenario,
        "expected_acceptance_status": expected_acceptance_status,
        "observed_acceptance_status": observed.get("acceptance_status", ""),
        "expected_blocking": expected_blocking,
        "observed_blocking": observed.get("blocking_issue", ""),
        "expected_lint_contains": expected_lint_contains or "NA",
        "observed_provenance_lint": observed_lint or "NA",
        "expected_content_lint_contains": expected_content_lint_contains or "NA",
        "observed_content_lint": observed_content_lint or "NA",
        "status": "pass" if passed else "fail",
        "notes": ";".join(notes) if notes else "NA",
    }


def run_tests() -> list[dict[str, str]]:
    with tempfile.TemporaryDirectory(prefix="external-evidence-acceptance-") as tmp:
        tmpdir = Path(tmp)
        return [
            check_case(
                tmpdir,
                "accepted_complete_provenance",
                "configured TSV with evidence source and notes is accepted",
                "genome_id\tevidence_source\tnotes\nphage_1\ttool_v1\treviewed command\n",
                "provided_input_ready",
                "pass",
                "1",
                "accepted",
                "false",
            ),
            check_case(
                tmpdir,
                "accepted_with_lint",
                "configured TSV without notes is accepted but linted",
                "genome_id\tevidence_source\nphage_1\ttool_v1\n",
                "provided_input_ready",
                "pass",
                "1",
                "accepted_with_provenance_lint",
                "false",
                "missing_notes_column",
            ),
            check_case(
                tmpdir,
                "schema_invalid",
                "schema-invalid configured TSV remains blocking",
                "genome_id\tevidence_source\tnotes\nphage_1\ttool_v1\treviewed command\n",
                "configured_input_schema_invalid",
                "fail",
                "1",
                "schema_invalid",
                "true",
            ),
            check_case(
                tmpdir,
                "missing_tool_or_input",
                "missing production tool or TSV remains blocking",
                None,
                "missing_tool_or_input",
                "not_checked",
                "0",
                "missing_tool_or_input",
                "true",
            ),
            check_case(
                tmpdir,
                "reject_keyword_inference_antidefense",
                "keyword-inference anti-defense rows are not accepted as production evidence",
                "antidefense_class\tphage_genome_id\tevidence_type\tevidence_source\tnotes\nanti_restriction\tphage_1\tannotation_keyword_inference\tstage6\trequires validation\n",
                "provided_input_ready",
                "pass",
                "1",
                "content_rejected",
                "true",
                expected_content_lint_contains="annotation_keyword_inference_rows=1",
                evidence_id="phage_antidefense_candidates",
            ),
            check_case(
                tmpdir,
                "reject_workflow_generated_results_path",
                "workflow-generated result TSVs cannot be reconfigured as external production evidence",
                "genome_id\tevidence_source\tnotes\nphage_1\tstage_output\tgenerated result path\n",
                "provided_input_ready",
                "pass",
                "1",
                "content_rejected",
                "true",
                expected_content_lint_contains="configured_path_is_workflow_generated_output",
                evidence_id="pairwise_similarity",
                evidence_subpath="results/defense_systems/phage_antidefense_candidates.tsv",
            ),
        ]


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {
            "severity": "info",
            "item": "external_evidence_acceptance_self_test",
            "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}",
        }
    ]
    if failed:
        report.append({"severity": "error", "item": "external_evidence_acceptance_self_test", "message": "One or more acceptance self-tests failed."})
    else:
        report.append({"severity": "info", "item": "external_evidence_acceptance_self_test", "message": "All acceptance self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"External evidence acceptance self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
