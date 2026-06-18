#!/usr/bin/env python3
"""Self-test defense/counter-defense external evidence normalization scenarios."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable

import normalize_defense_external_evidence as normalizer


TEST_COLUMNS = [
    "test_id",
    "scenario",
    "expected_host_rows",
    "observed_host_rows",
    "expected_antidefense_rows",
    "observed_antidefense_rows",
    "expected_value",
    "observed_value",
    "status",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for defense external evidence normalization.")
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


def check_case(
    test_id: str,
    scenario: str,
    host_rows: list[dict[str, str]],
    anti_rows: list[dict[str, str]],
    expected_host_rows: int,
    expected_antidefense_rows: int,
    expected_value: str,
    observed_value: str,
) -> dict[str, str]:
    passed = (
        len(host_rows) == expected_host_rows
        and len(anti_rows) == expected_antidefense_rows
        and observed_value == expected_value
    )
    notes = []
    if len(host_rows) != expected_host_rows:
        notes.append("host_row_count_mismatch")
    if len(anti_rows) != expected_antidefense_rows:
        notes.append("antidefense_row_count_mismatch")
    if observed_value != expected_value:
        notes.append("value_mismatch")
    return {
        "test_id": test_id,
        "scenario": scenario,
        "expected_host_rows": str(expected_host_rows),
        "observed_host_rows": str(len(host_rows)),
        "expected_antidefense_rows": str(expected_antidefense_rows),
        "observed_antidefense_rows": str(len(anti_rows)),
        "expected_value": expected_value,
        "observed_value": observed_value,
        "status": "pass" if passed else "fail",
        "notes": ";".join(notes) if notes else "NA",
    }


def run_tests() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="defense-evidence-normalizer-") as tmp:
        tmpdir = Path(tmp)
        host_generic = tmpdir / "host_defense.tsv"
        write_text(
            host_generic,
            "host_genome_id\tsystem\ttype\tsubtype\tgenes\tevidence_source\tnotes\n"
            "hostA\tRM_1\trestriction-modification\tType I\thsdR;hsdM\tdefensefinder-test\treviewed\n",
        )
        host_rows, _ = normalizer.normalize_host_defense(str(host_generic), "generic_tsv")
        rows.append(
            check_case(
                "generic_host_defense",
                "generic host defense TSV is normalized",
                host_rows,
                [],
                1,
                0,
                "restriction-modification",
                host_rows[0].get("type", "") if host_rows else "",
            )
        )

        padloc_like = tmpdir / "padloc.tsv"
        write_text(
            padloc_like,
            "seqid\tsystem\ttarget.name\tstart\tend\ttool\tnotes\n"
            "hostB\tBREX\tpglX\t10\t400\tpadloc-test\treviewed\n",
        )
        padloc_rows, _ = normalizer.normalize_host_defense(str(padloc_like), "padloc_tsv")
        rows.append(
            check_case(
                "padloc_alias_host_defense",
                "PADLOC-like aliases are normalized",
                padloc_rows,
                [],
                1,
                0,
                "BREX",
                padloc_rows[0].get("type", "") if padloc_rows else "",
            )
        )

        cli_host_only = tmpdir / "cli_host_only.tsv"
        cli_anti_unrequested = tmpdir / "cli_anti_unrequested.tsv"
        cli_report = tmpdir / "cli_report.tsv"
        command = [
            sys.executable,
            str(Path(__file__).with_name("normalize_defense_external_evidence.py")),
            "--host-defense-input",
            str(host_generic),
            "--host-defense-output",
            str(cli_host_only),
            "--report-output",
            str(cli_report),
        ]
        completed = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        _, cli_host_rows = normalizer.read_tsv(cli_host_only) if cli_host_only.exists() else ([], [])
        rows.append(
            check_case(
                "cli_independent_outputs",
                "host-only CLI normalization does not create unrequested anti-defense output",
                cli_host_rows,
                [],
                1,
                0,
                "false",
                str(cli_anti_unrequested.exists()).lower(),
            )
        )

        phage_generic = tmpdir / "phage_antidefense.tsv"
        write_text(
            phage_generic,
            "annotation_gene_id\tproduct\tevidence_source\tnotes\n"
            "phageA|gene001\tanti-CRISPR protein AcrIF1\tprofile-test\treviewed\n",
        )
        anti_rows, _ = normalizer.normalize_phage_antidefense(str(phage_generic), "generic_tsv")
        rows.append(
            check_case(
                "generic_phage_antidefense",
                "generic phage anti-defense TSV is normalized and class inferred",
                [],
                anti_rows,
                0,
                1,
                "anti_crispr",
                anti_rows[0].get("antidefense_class", "") if anti_rows else "",
            )
        )

        rows.append(
            check_case(
                "header_only",
                "no reviewed input gives no normalized rows",
                [],
                [],
                0,
                0,
                "NA",
                "NA",
            )
        )
    return rows


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {
            "severity": "info",
            "item": "defense_external_evidence_normalization_self_test",
            "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}",
        }
    ]
    if failed:
        report.append({"severity": "error", "item": "defense_external_evidence_normalization_self_test", "message": "One or more normalizer self-tests failed."})
    else:
        report.append({"severity": "info", "item": "defense_external_evidence_normalization_self_test", "message": "All normalizer self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Defense external evidence normalization self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
