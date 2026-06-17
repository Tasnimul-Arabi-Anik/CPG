#!/usr/bin/env python3
"""Self-test RBP external evidence normalization scenarios."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from typing import Iterable

import normalize_rbp_external_evidence as normalizer


TEST_COLUMNS = [
    "test_id",
    "scenario",
    "expected_domain_rows",
    "observed_domain_rows",
    "expected_structural_rows",
    "observed_structural_rows",
    "expected_value",
    "observed_value",
    "status",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for RBP external evidence normalization.")
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
    domain_rows: list[dict[str, str]],
    structural_rows: list[dict[str, str]],
    expected_domain_rows: int,
    expected_structural_rows: int,
    expected_value: str,
    observed_value: str,
) -> dict[str, str]:
    passed = (
        len(domain_rows) == expected_domain_rows
        and len(structural_rows) == expected_structural_rows
        and observed_value == expected_value
    )
    notes = []
    if len(domain_rows) != expected_domain_rows:
        notes.append("domain_row_count_mismatch")
    if len(structural_rows) != expected_structural_rows:
        notes.append("structural_row_count_mismatch")
    if observed_value != expected_value:
        notes.append("value_mismatch")
    return {
        "test_id": test_id,
        "scenario": scenario,
        "expected_domain_rows": str(expected_domain_rows),
        "observed_domain_rows": str(len(domain_rows)),
        "expected_structural_rows": str(expected_structural_rows),
        "observed_structural_rows": str(len(structural_rows)),
        "expected_value": expected_value,
        "observed_value": observed_value,
        "status": "pass" if passed else "fail",
        "notes": ";".join(notes) if notes else "NA",
    }


def run_tests() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="rbp-evidence-normalizer-") as tmp:
        tmpdir = Path(tmp)
        generic_domain = tmpdir / "domain.tsv"
        write_text(
            generic_domain,
            "annotation_gene_id\tdomain_id\tdomain_name\tstart_aa\tend_aa\tevalue\tevidence_source\tnotes\n"
            "geneA\tPF00001\tTail fiber domain\t5\t120\t1e-20\thmmer-test\treviewed\n",
        )
        domain_rows = normalizer.normalize_domain_generic(generic_domain)
        rows.append(
            check_case(
                "generic_domain",
                "generic domain TSV is normalized",
                domain_rows,
                [],
                1,
                0,
                "PF00001",
                domain_rows[0].get("domain_id", "") if domain_rows else "",
            )
        )

        hmmer = tmpdir / "hmmer.domtblout"
        write_text(
            hmmer,
            "# target name accession tlen query name accession qlen E-value score bias # of c-Evalue i-Evalue score bias hmm from hmm to ali from ali to env from env to acc description\n"
            "geneB - 300 Tail_HMM PF00002 120 1e-50 200.0 0.0 1 1 1e-45 1e-44 180.0 0.0 1 110 20 130 18 132 0.98 Tail spike profile\n",
        )
        hmmer_rows = normalizer.normalize_domain_hmmer_domtblout(hmmer)
        rows.append(
            check_case(
                "hmmer_domtblout",
                "HMMER domtblout target/query fields are normalized",
                hmmer_rows,
                [],
                1,
                0,
                "Tail_HMM",
                hmmer_rows[0].get("domain_id", "") if hmmer_rows else "",
            )
        )

        structural = tmpdir / "foldseek.tsv"
        write_text(
            structural,
            "annotation_gene_id\tstructural_hit_id\tstructural_hit_name\ttm_score\tprobability\tevidence_source\tnotes\n"
            "geneC\tPDB:1ABC\tTailspike fold\t0.73\t0.95\tfoldseek-test\treviewed\n",
        )
        structural_rows = normalizer.normalize_structural_generic(structural)
        rows.append(
            check_case(
                "generic_structural",
                "generic structural TSV is normalized",
                [],
                structural_rows,
                0,
                1,
                "PDB:1ABC",
                structural_rows[0].get("structural_hit_id", "") if structural_rows else "",
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
            "item": "rbp_external_evidence_normalization_self_test",
            "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}",
        }
    ]
    if failed:
        report.append({"severity": "error", "item": "rbp_external_evidence_normalization_self_test", "message": "One or more normalizer self-tests failed."})
    else:
        report.append({"severity": "info", "item": "rbp_external_evidence_normalization_self_test", "message": "All normalizer self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"RBP external evidence normalization self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
