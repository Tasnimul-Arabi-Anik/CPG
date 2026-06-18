#!/usr/bin/env python3
"""Self-test RBP external evidence normalization scenarios."""

from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path
from typing import Callable, Iterable

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


def make_args(tmpdir: Path, **overrides: str | bool) -> argparse.Namespace:
    defaults: dict[str, str | bool] = {
        "domain_input": "",
        "domain_format": "generic_tsv",
        "hmmer_mode": "hmmsearch",
        "structural_input": "",
        "structural_format": "generic_tsv",
        "foldseek_fields": normalizer.DEFAULT_FOLDSEEK_FIELDS,
        "phold_fields": normalizer.DEFAULT_PHOLD_FIELDS,
        "annotation_manifest": "",
        "tool": "",
        "tool_version": "",
        "database": "",
        "database_version": "",
        "command": "",
        "run_date": "",
        "overwrite_empty": False,
        "domain_output": str(tmpdir / "domain_out.tsv"),
        "structural_output": str(tmpdir / "structural_out.tsv"),
        "report_output": str(tmpdir / "report.tsv"),
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def check_case(
    test_id: str,
    scenario: str,
    domain_rows: list[dict[str, str]],
    structural_rows: list[dict[str, str]],
    expected_domain_rows: int,
    expected_structural_rows: int,
    expected_value: str,
    observed_value: str,
    notes: str = "NA",
) -> dict[str, str]:
    passed = (
        len(domain_rows) == expected_domain_rows
        and len(structural_rows) == expected_structural_rows
        and observed_value == expected_value
    )
    mismatch_notes = []
    if len(domain_rows) != expected_domain_rows:
        mismatch_notes.append("domain_row_count_mismatch")
    if len(structural_rows) != expected_structural_rows:
        mismatch_notes.append("structural_row_count_mismatch")
    if observed_value != expected_value:
        mismatch_notes.append("value_mismatch")
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
        "notes": ";".join(mismatch_notes) if mismatch_notes else notes,
    }


def check_error_case(
    test_id: str,
    scenario: str,
    func: Callable[[], object],
    expected_message: str,
) -> dict[str, str]:
    observed_message = ""
    try:
        func()
    except normalizer.NormalizationError as exc:
        observed_message = str(exc)
    passed = expected_message in observed_message
    return {
        "test_id": test_id,
        "scenario": scenario,
        "expected_domain_rows": "NA",
        "observed_domain_rows": "NA",
        "expected_structural_rows": "NA",
        "observed_structural_rows": "NA",
        "expected_value": expected_message,
        "observed_value": observed_message or "no_error",
        "status": "pass" if passed else "fail",
        "notes": "NA" if passed else "expected_error_not_observed",
    }


def normalize_domain(path: Path, tmpdir: Path, **overrides: str | bool) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    report: list[dict[str, str]] = []
    args = make_args(tmpdir, domain_input=str(path), **overrides)
    allowed_ids = normalizer.load_annotation_ids(str(tmpdir / "annotation_manifest.tsv"))
    return normalizer.normalize_domain_from_args(args, allowed_ids, report), report


def normalize_structural(path: Path, tmpdir: Path, **overrides: str | bool) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    report: list[dict[str, str]] = []
    args = make_args(tmpdir, structural_input=str(path), **overrides)
    allowed_ids = normalizer.load_annotation_ids(str(tmpdir / "annotation_manifest.tsv"))
    return normalizer.normalize_structural_from_args(args, allowed_ids, report), report


def run_tests() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="rbp-evidence-normalizer-") as tmp:
        tmpdir = Path(tmp)
        manifest = tmpdir / "annotation_manifest.tsv"
        write_text(
            manifest,
            "annotation_gene_id\tphage_id\tproduct\n"
            "geneA\tphage1\ttail fiber\n"
            "geneB\tphage1\ttail spike\n"
            "geneC\tphage2\tdepolymerase\n"
            "geneD\tphage2\thypothetical protein\n"
            "geneE\tphage3\ttail fiber\n",
        )

        generic_domain = tmpdir / "domain.tsv"
        write_text(
            generic_domain,
            "annotation_gene_id\tdomain_id\tdomain_name\tstart_aa\tend_aa\tevalue\tevidence_source\tnotes\n"
            "geneA\tPF00001\tTail fiber domain\t5\t120\t1e-20\thmmer-test\treviewed\n",
        )
        domain_rows, _ = normalize_domain(generic_domain, tmpdir, tool="hmmer", tool_version="3.4", database="pfam", database_version="review-fixture")
        rows.append(
            check_case(
                "generic_domain",
                "generic domain TSV is normalized with provenance columns",
                domain_rows,
                [],
                1,
                0,
                "hmmer|3.4|pfam|review-fixture",
                "|".join(
                    [
                        domain_rows[0].get("tool", ""),
                        domain_rows[0].get("tool_version", ""),
                        domain_rows[0].get("database", ""),
                        domain_rows[0].get("database_version", ""),
                    ]
                )
                if domain_rows
                else "",
            )
        )

        hmmer_hmmsearch = tmpdir / "hmmsearch.domtblout"
        write_text(
            hmmer_hmmsearch,
            "# domtblout fixture\n"
            "geneB - 300 Tail_HMM PF00002 120 1e-50 200.0 0.0 1 1 1e-45 1e-44 180.0 0.0 1 110 20 130 18 132 0.98 Tail spike profile\n",
        )
        hmmer_search_rows, _ = normalize_domain(hmmer_hmmsearch, tmpdir, domain_format="hmmer_domtblout", hmmer_mode="hmmsearch")
        rows.append(
            check_case(
                "hmmer_hmmsearch_orientation",
                "HMMER hmmsearch uses target as annotation_gene_id and query as domain",
                hmmer_search_rows,
                [],
                1,
                0,
                "geneB|PF00002|20|130",
                "|".join(
                    [
                        hmmer_search_rows[0].get("annotation_gene_id", ""),
                        hmmer_search_rows[0].get("domain_id", ""),
                        hmmer_search_rows[0].get("start_aa", ""),
                        hmmer_search_rows[0].get("end_aa", ""),
                    ]
                )
                if hmmer_search_rows
                else "",
            )
        )

        hmmer_hmmscan = tmpdir / "hmmscan.domtblout"
        write_text(
            hmmer_hmmscan,
            "# domtblout fixture\n"
            "Tail_HMM PF00003 120 geneC - 420 1e-40 180.0 0.0 1 1 1e-35 1e-34 150.0 0.0 1 105 40 160 36 165 0.97 Capsule depolymerase profile\n",
        )
        hmmer_scan_rows, _ = normalize_domain(hmmer_hmmscan, tmpdir, domain_format="hmmer_domtblout", hmmer_mode="hmmscan")
        rows.append(
            check_case(
                "hmmer_hmmscan_orientation",
                "HMMER hmmscan uses query as annotation_gene_id and target as domain",
                hmmer_scan_rows,
                [],
                1,
                0,
                "geneC|PF00003|40|160",
                "|".join(
                    [
                        hmmer_scan_rows[0].get("annotation_gene_id", ""),
                        hmmer_scan_rows[0].get("domain_id", ""),
                        hmmer_scan_rows[0].get("start_aa", ""),
                        hmmer_scan_rows[0].get("end_aa", ""),
                    ]
                )
                if hmmer_scan_rows
                else "",
            )
        )

        foldseek = tmpdir / "foldseek.tsv"
        write_text(foldseek, "geneD\tPDB:1ABC\t0.73\t88.5\t1e-12\n")
        foldseek_rows, _ = normalize_structural(foldseek, tmpdir, structural_format="foldseek_tsv")
        rows.append(
            check_case(
                "foldseek_headerless",
                "headerless Foldseek TSV is parsed using explicit --format-output fields",
                [],
                foldseek_rows,
                0,
                1,
                "geneD|PDB:1ABC|0.73|0.885",
                "|".join(
                    [
                        foldseek_rows[0].get("annotation_gene_id", ""),
                        foldseek_rows[0].get("structural_hit_id", ""),
                        foldseek_rows[0].get("tm_score", ""),
                        foldseek_rows[0].get("probability", ""),
                    ]
                )
                if foldseek_rows
                else "",
            )
        )

        phold = tmpdir / "phold.tsv"
        write_text(
            phold,
            "annotation_gene_id\tstructural_hit_id\tstructural_hit_name\tprobability\n"
            "geneE\tphold:tailspike\tTailspike-like receptor binding protein\t0.91\n",
        )
        phold_rows, _ = normalize_structural(phold, tmpdir, structural_format="phold_tsv")
        rows.append(
            check_case(
                "phold_headered",
                "headered Phold-style TSV is parsed as structure-informed evidence",
                [],
                phold_rows,
                0,
                1,
                "geneE|phold:tailspike|0.91",
                "|".join(
                    [
                        phold_rows[0].get("annotation_gene_id", ""),
                        phold_rows[0].get("structural_hit_id", ""),
                        phold_rows[0].get("probability", ""),
                    ]
                )
                if phold_rows
                else "",
            )
        )

        duplicate_domain = tmpdir / "duplicate_domain.tsv"
        write_text(
            duplicate_domain,
            "annotation_gene_id\tdomain_id\tdomain_name\tstart_aa\tend_aa\tevalue\n"
            "geneA\tPF00001\tTail fiber domain\t5\t120\t1e-20\n"
            "geneA\tPF00001\tTail fiber domain\t5\t120\t1e-20\n",
        )
        duplicate_rows, duplicate_report = normalize_domain(duplicate_domain, tmpdir)
        rows.append(
            check_case(
                "duplicate_domain_hits",
                "duplicate domain hits are skipped and reported",
                duplicate_rows,
                [],
                1,
                0,
                "warning",
                next((entry["severity"] for entry in duplicate_report if entry["item"] == "domain_duplicates"), ""),
            )
        )

        unknown_domain = tmpdir / "unknown_domain.tsv"
        write_text(
            unknown_domain,
            "annotation_gene_id\tdomain_id\tdomain_name\tstart_aa\tend_aa\tevalue\n"
            "missing_gene\tPF00001\tTail fiber domain\t5\t120\t1e-20\n",
        )
        rows.append(
            check_error_case(
                "unknown_annotation_id",
                "annotation_gene_id values must resolve to the annotation manifest",
                lambda: normalize_domain(unknown_domain, tmpdir),
                "Unknown annotation_gene_id",
            )
        )

        bad_domain = tmpdir / "bad_domain.tsv"
        write_text(
            bad_domain,
            "annotation_gene_id\tdomain_id\tdomain_name\tstart_aa\tend_aa\tevalue\n"
            "geneA\tPF00001\tTail fiber domain\t120\t5\t1e-20\n",
        )
        rows.append(
            check_error_case(
                "invalid_domain_coordinates",
                "domain coordinates must be positive and ordered",
                lambda: normalize_domain(bad_domain, tmpdir),
                "start_aa is greater than end_aa",
            )
        )

        fractional_domain = tmpdir / "fractional_domain.tsv"
        write_text(
            fractional_domain,
            "annotation_gene_id\tdomain_id\tdomain_name\tstart_aa\tend_aa\tevalue\n"
            "geneA\tPF00001\tTail fiber domain\t5.5\t120\t1e-20\n",
        )
        rows.append(
            check_error_case(
                "noninteger_domain_coordinate",
                "domain coordinates must be integers, not truncated floats",
                lambda: normalize_domain(fractional_domain, tmpdir),
                "start_aa is not an integer coordinate",
            )
        )

        bad_structural = tmpdir / "bad_structural.tsv"
        write_text(
            bad_structural,
            "annotation_gene_id\tstructural_hit_id\tstructural_hit_name\ttm_score\tprobability\n"
            "geneD\tPDB:1ABC\tTailspike fold\t1.2\t0.95\n",
        )
        rows.append(
            check_error_case(
                "invalid_structural_score",
                "structural TM-score values must be in the expected numeric range",
                lambda: normalize_structural(bad_structural, tmpdir),
                "tm_score is above 1",
            )
        )

        existing_output = tmpdir / "existing_domain_output.tsv"
        write_text(existing_output, "sentinel\nkeep_me\n")
        preserve_report: list[dict[str, str]] = []
        normalizer.maybe_write_empty_output(existing_output, normalizer.DOMAIN_COLUMNS, False, preserve_report, "domain_evidence")
        rows.append(
            check_case(
                "preserve_existing_without_input",
                "absent input preserves existing evidence output unless overwrite-empty is set",
                [],
                [],
                0,
                0,
                "keep_me",
                existing_output.read_text(encoding="utf-8").splitlines()[1],
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
