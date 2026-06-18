#!/usr/bin/env python3
"""Self-test workflow configuration inheritance and placeholder resolution."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from typing import Callable, Iterable

from workflow_config import WorkflowConfigError, load_workflow_config, resolved_config_sha256


TEST_COLUMNS = [
    "test_id",
    "scenario",
    "expected_status",
    "observed_status",
    "status",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for workflow config resolution.")
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


def result(test_id: str, scenario: str, expected: str, observed: str, notes: str = "NA") -> dict[str, str]:
    passed = expected == observed
    return {
        "test_id": test_id,
        "scenario": scenario,
        "expected_status": expected,
        "observed_status": observed,
        "status": "pass" if passed else "fail",
        "notes": "NA" if passed else notes,
    }


def expect_ok(test_id: str, scenario: str, check: Callable[[], bool], notes: str) -> dict[str, str]:
    try:
        observed = "ok" if check() else "unexpected_value"
    except Exception as exc:  # pragma: no cover - report-oriented guard
        observed = f"error:{type(exc).__name__}"
        notes = str(exc)
    return result(test_id, scenario, "ok", observed, notes)


def expect_error(test_id: str, scenario: str, action: Callable[[], object], expected_fragment: str) -> dict[str, str]:
    try:
        action()
    except WorkflowConfigError as exc:
        observed = "expected_error" if expected_fragment in str(exc) else "unexpected_error"
        notes = str(exc)
    except Exception as exc:  # pragma: no cover - report-oriented guard
        observed = f"wrong_exception:{type(exc).__name__}"
        notes = str(exc)
    else:
        observed = "no_error"
        notes = "Expected WorkflowConfigError was not raised."
    return result(test_id, scenario, "expected_error", observed, notes)


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="workflow-config-self-test-") as tmp:
        root = Path(tmp)
        config_dir = root / "config"
        config_dir.mkdir()
        base = config_dir / "workflow.base.yaml"
        seed = config_dir / "workflow.seed.yaml"
        alias = config_dir / "workflow.yaml"
        bad_placeholder = config_dir / "bad-placeholder.yaml"
        circular_a = config_dir / "circular-a.yaml"
        circular_b = config_dir / "circular-b.yaml"

        base.write_text(
            "\n".join(
                [
                    "paths:",
                    "  results_dir: results/base",
                    "  logs_dir: logs/base",
                    "profile:",
                    "  name: base",
                    "  evidence_class: base_fixture",
                    "inputs:",
                    "  samples: config/samples.tsv",
                    "outputs:",
                    "  validation:",
                    "    report: '{results_dir}/validation/workflow_validation_report.tsv'",
                    "    run_report: '{results_dir}/validation/workflow_run_report.tsv'",
                    "logs:",
                    "  stage_0: '{logs_dir}/00_stage.log'",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        seed.write_text(
            "\n".join(
                [
                    "extends: workflow.base.yaml",
                    "paths:",
                    "  results_dir: results/seed",
                    "  logs_dir: logs/seed",
                    "profile:",
                    "  name: seed",
                    "  evidence_class: reviewed_seed_bridge",
                    "inputs:",
                    "  samples: results/seed/source_builder/samples.tsv",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        alias.write_text("extends: workflow.seed.yaml\n", encoding="utf-8")
        bad_placeholder.write_text("bad: '{missing_placeholder}/x.tsv'\n", encoding="utf-8")
        circular_a.write_text("extends: circular-b.yaml\n", encoding="utf-8")
        circular_b.write_text("extends: circular-a.yaml\n", encoding="utf-8")

        tests.append(
            expect_ok(
                "extends_deep_merge",
                "overlay preserves nested base keys while replacing configured leaves",
                lambda: (
                    (cfg := load_workflow_config("config/workflow.seed.yaml", root))["inputs"]["samples"]
                    == "results/seed/source_builder/samples.tsv"
                    and cfg["outputs"]["validation"]["run_report"] == "results/seed/validation/workflow_run_report.tsv"
                    and cfg["logs"]["stage_0"] == "logs/seed/00_stage.log"
                ),
                "Deep merge or placeholder substitution did not match expected seed values.",
            )
        )
        tests.append(
            expect_ok(
                "alias_resolution",
                "workflow.yaml alias resolves through workflow.seed.yaml",
                lambda: load_workflow_config("config/workflow.yaml", root)["profile"]["name"] == "seed",
                "Workflow alias did not resolve to the seed profile.",
            )
        )
        tests.append(
            expect_ok(
                "resolved_hash_stable",
                "resolved config checksum is a stable SHA-256 hex digest",
                lambda: len(resolved_config_sha256(load_workflow_config("config/workflow.seed.yaml", root))) == 64,
                "Resolved config checksum was not a SHA-256-length digest.",
            )
        )
        tests.append(
            expect_error(
                "unknown_placeholder_fails",
                "unknown placeholders raise a blocking workflow config error",
                lambda: load_workflow_config("config/bad-placeholder.yaml", root),
                "Unknown workflow config placeholder",
            )
        )
        tests.append(
            expect_error(
                "circular_extends_fails",
                "circular extends chains raise a blocking workflow config error",
                lambda: load_workflow_config("config/circular-a.yaml", root),
                "Circular workflow config extends chain",
            )
        )
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {
            "severity": "info",
            "item": "workflow_config_self_test",
            "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}",
        }
    ]
    if failed:
        report.append({"severity": "error", "item": "workflow_config_self_test", "message": "One or more workflow config self-tests failed."})
    else:
        report.append({"severity": "info", "item": "workflow_config_self_test", "message": "All workflow config self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Workflow config self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
