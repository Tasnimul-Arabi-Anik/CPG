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


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


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
        "domain_tool": "",
        "domain_tool_version": "",
        "domain_database": "",
        "domain_database_version": "",
        "domain_command": "",
        "domain_run_date": "",
        "structural_tool": "",
        "structural_tool_version": "",
        "structural_database": "",
        "structural_database_version": "",
        "structural_command": "",
        "structural_run_date": "",
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
    args = make_args(tmpdir, domain_input=str(path), annotation_manifest=str(tmpdir / "annotation_manifest.tsv"), **overrides)
    id_map = normalizer.load_annotation_id_map(args.annotation_manifest)
    return normalizer.normalize_domain_from_args(args, id_map, report), report


def normalize_structural(path: Path, tmpdir: Path, **overrides: str | bool) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    report: list[dict[str, str]] = []
    args = make_args(tmpdir, structural_input=str(path), annotation_manifest=str(tmpdir / "annotation_manifest.tsv"), **overrides)
    id_map = normalizer.load_annotation_id_map(args.annotation_manifest)
    return normalizer.normalize_structural_from_args(args, id_map, report), report


def run_tests() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="rbp-evidence-normalizer-") as tmp:
        tmpdir = Path(tmp)
        manifest = tmpdir / "annotation_manifest.tsv"
        write_text(
            manifest,
            "annotation_gene_id\tprotein_id\tgene_id\tphage_id\tproduct\n"
            "geneA\tprotA\taliasA\tphage1\ttail fiber\n"
            "geneB\tprotB\taliasB\tphage1\ttail spike\n"
            "geneC\tprotC\taliasC\tphage2\tdepolymerase\n"
            "geneD\tprotD\taliasD\tphage2\thypothetical protein\n"
            "geneE\tprotE\taliasE\tphage3\ttail fiber\n",
        )

        generic_domain = tmpdir / "domain.tsv"
        write_text(
            generic_domain,
            "annotation_gene_id\tdomain_id\tdomain_name\tstart_aa\tend_aa\tevalue\tevidence_source\tnotes\n"
            "geneA\tPF00001\tTail fiber domain\t5\t120\t1e-20\thmmer-test\treviewed\n",
        )
        domain_rows, _ = normalize_domain(
            generic_domain,
            tmpdir,
            domain_tool="hmmer",
            domain_tool_version="3.4",
            domain_database="pfam",
            domain_database_version="review-fixture",
        )
        rows.append(
            check_case(
                "generic_domain",
                "generic domain TSV is normalized with type-specific provenance columns",
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

        row_provenance = tmpdir / "row_provenance_domain.tsv"
        write_text(
            row_provenance,
            "annotation_gene_id\tdomain_id\tdomain_name\tstart_aa\tend_aa\tevalue\ttool\tdatabase\n"
            "geneA\tPF00001\tTail fiber domain\t5\t120\t1e-20\trow_hmmer\trow_pfam\n",
        )
        row_prov_rows, _ = normalize_domain(row_provenance, tmpdir, domain_tool="cli_hmmer", domain_database="cli_pfam")
        rows.append(
            check_case(
                "row_level_provenance_precedence",
                "row-level provenance is retained ahead of CLI provenance",
                row_prov_rows,
                [],
                1,
                0,
                "row_hmmer|row_pfam",
                "|".join([row_prov_rows[0].get("tool", ""), row_prov_rows[0].get("database", "")]) if row_prov_rows else "",
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

        transactional_domain = tmpdir / "transactional_domain.tsv"
        transactional_structural = tmpdir / "transactional_structural.tsv"
        domain_out = tmpdir / "transactional_domain_out.tsv"
        structural_out = tmpdir / "transactional_structural_out.tsv"
        write_text(transactional_domain, generic_domain.read_text(encoding="utf-8"))
        write_text(
            transactional_structural,
            "annotation_gene_id\tstructural_hit_id\tstructural_hit_name\tprobability\n"
            "geneE\tphold:tailspike\tTailspike-like receptor binding protein\tnan\n",
        )
        write_text(domain_out, "sentinel\nkeep_domain\n")
        write_text(structural_out, "sentinel\nkeep_structural\n")
        txn_args = make_args(
            tmpdir,
            annotation_manifest=str(manifest),
            domain_input=str(transactional_domain),
            structural_input=str(transactional_structural),
            domain_output=str(domain_out),
            structural_output=str(structural_out),
            report_output=str(tmpdir / "transactional_report.tsv"),
        )
        txn_rc = normalizer.run(txn_args)
        rows.append(
            check_case(
                "transactional_no_partial_write",
                "valid domain evidence is not written when structural evidence validation fails",
                [],
                [],
                0,
                0,
                "1|keep_domain|keep_structural",
                "|".join(
                    [
                        str(txn_rc),
                        domain_out.read_text(encoding="utf-8").splitlines()[1],
                        structural_out.read_text(encoding="utf-8").splitlines()[1],
                    ]
                ),
            )
        )

        distinct_domain = tmpdir / "distinct_domain.tsv"
        distinct_structural = tmpdir / "distinct_structural.tsv"
        write_text(distinct_domain, generic_domain.read_text(encoding="utf-8"))
        write_text(distinct_structural, phold.read_text(encoding="utf-8"))
        distinct_args = make_args(
            tmpdir,
            annotation_manifest=str(manifest),
            domain_input=str(distinct_domain),
            structural_input=str(distinct_structural),
            structural_format="phold_tsv",
            domain_output=str(tmpdir / "distinct_domain_out.tsv"),
            structural_output=str(tmpdir / "distinct_structural_out.tsv"),
            report_output=str(tmpdir / "distinct_report.tsv"),
            domain_tool="hmmer",
            domain_database="Pfam",
            structural_tool="phold",
            structural_database="PholdDB",
        )
        distinct_rc = normalizer.run(distinct_args)
        distinct_domain_rows = read_tsv(Path(distinct_args.domain_output)) if distinct_rc == 0 else []
        distinct_structural_rows = read_tsv(Path(distinct_args.structural_output)) if distinct_rc == 0 else []
        rows.append(
            check_case(
                "domain_and_structural_distinct_provenance",
                "domain and structural rows use evidence-type-specific provenance",
                distinct_domain_rows,
                distinct_structural_rows,
                1,
                1,
                "hmmer|Pfam|phold|PholdDB",
                "|".join(
                    [
                        distinct_domain_rows[0].get("tool", "") if distinct_domain_rows else "",
                        distinct_domain_rows[0].get("database", "") if distinct_domain_rows else "",
                        distinct_structural_rows[0].get("tool", "") if distinct_structural_rows else "",
                        distinct_structural_rows[0].get("database", "") if distinct_structural_rows else "",
                    ]
                ),
            )
        )

        protein_id_domain = tmpdir / "protein_id_domain.tsv"
        write_text(
            protein_id_domain,
            "protein_id\tdomain_id\tdomain_name\tstart_aa\tend_aa\tevalue\n"
            "protA\tPF00001\tTail fiber domain\t5\t120\t1e-20\n",
        )
        protein_rows, protein_report = normalize_domain(protein_id_domain, tmpdir)
        rows.append(
            check_case(
                "canonical_protein_id_translation",
                "protein_id aliases are translated to canonical annotation_gene_id",
                protein_rows,
                [],
                1,
                0,
                "geneA|direct_matches=0; translated_aliases=1",
                "|".join(
                    [
                        protein_rows[0].get("annotation_gene_id", "") if protein_rows else "",
                        next((entry["message"] for entry in protein_report if entry["item"] == "domain_annotation_ids"), "missing_report"),
                    ]
                ),
            )
        )

        ambiguous_manifest = tmpdir / "ambiguous_annotation_manifest.tsv"
        write_text(
            ambiguous_manifest,
            "annotation_gene_id\tprotein_id\n"
            "geneX\tshared_prot\n"
            "geneY\tshared_prot\n",
        )
        rows.append(
            check_error_case(
                "ambiguous_identifier_mapping_fails",
                "aliases mapping to multiple canonical annotation_gene_id values are blocking",
                lambda: normalizer.load_annotation_id_map(str(ambiguous_manifest)),
                "Ambiguous annotation identifier mapping",
            )
        )

        nan_domain = tmpdir / "nan_domain.tsv"
        write_text(
            nan_domain,
            "annotation_gene_id\tdomain_id\tdomain_name\tstart_aa\tend_aa\tevalue\n"
            "geneA\tPF00001\tTail fiber domain\t5\t120\tnan\n",
        )
        rows.append(
            check_error_case(
                "nan_numeric_value_fails",
                "non-finite numeric values are rejected",
                lambda: normalize_domain(nan_domain, tmpdir),
                "evalue is non-finite",
            )
        )

        collision_args = make_args(tmpdir, domain_input=str(generic_domain), domain_output=str(generic_domain))
        rows.append(
            check_error_case(
                "input_output_path_collision_fails",
                "input/output path collisions are rejected before normalization",
                lambda: normalizer.validate_path_collisions(collision_args),
                "domain_input must not be the same path as domain_output",
            )
        )

        overwrite_domain = tmpdir / "overwrite_domain.tsv"
        overwrite_structural = tmpdir / "overwrite_structural.tsv"
        write_text(overwrite_domain, "sentinel\nold_domain\n")
        write_text(overwrite_structural, "sentinel\nold_structural\n")
        overwrite_args = make_args(
            tmpdir,
            overwrite_empty=True,
            domain_output=str(overwrite_domain),
            structural_output=str(overwrite_structural),
            report_output=str(tmpdir / "overwrite_report.tsv"),
        )
        overwrite_rc = normalizer.run(overwrite_args)
        rows.append(
            check_case(
                "overwrite_empty_explicitly_replaces",
                "--overwrite-empty replaces existing evidence outputs with header-only tables",
                [],
                [],
                0,
                0,
                "0|annotation_gene_id|annotation_gene_id",
                "|".join(
                    [
                        str(overwrite_rc),
                        overwrite_domain.read_text(encoding="utf-8").splitlines()[0].split("\t")[0],
                        overwrite_structural.read_text(encoding="utf-8").splitlines()[0].split("\t")[0],
                    ]
                ),
            )
        )

        full_success_args = make_args(
            tmpdir,
            annotation_manifest=str(manifest),
            domain_input=str(generic_domain),
            structural_input=str(phold),
            structural_format="phold_tsv",
            domain_output=str(tmpdir / "full_success_domain.tsv"),
            structural_output=str(tmpdir / "full_success_structural.tsv"),
            report_output=str(tmpdir / "full_success_report.tsv"),
            domain_tool="hmmer",
            structural_tool="phold",
        )
        full_success_rc = normalizer.run(full_success_args)
        full_success_domain_rows = read_tsv(Path(full_success_args.domain_output)) if full_success_rc == 0 else []
        full_success_structural_rows = read_tsv(Path(full_success_args.structural_output)) if full_success_rc == 0 else []
        rows.append(
            check_case(
                "full_cli_success",
                "full run succeeds with valid domain and structural inputs",
                full_success_domain_rows,
                full_success_structural_rows,
                1,
                1,
                "0",
                str(full_success_rc),
            )
        )

        full_failure_args = make_args(
            tmpdir,
            annotation_manifest=str(manifest),
            domain_input=str(nan_domain),
            domain_output=str(tmpdir / "full_failure_domain.tsv"),
            structural_output=str(tmpdir / "full_failure_structural.tsv"),
            report_output=str(tmpdir / "full_failure_report.tsv"),
        )
        full_failure_rc = normalizer.run(full_failure_args)
        rows.append(
            check_case(
                "full_cli_failure_exit_code",
                "full run exits nonzero on malformed reviewed evidence",
                [],
                [],
                0,
                0,
                "1|False",
                "|".join([str(full_failure_rc), str(Path(full_failure_args.domain_output).exists())]),
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
