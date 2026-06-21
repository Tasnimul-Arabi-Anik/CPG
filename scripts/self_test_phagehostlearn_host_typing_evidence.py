#!/usr/bin/env python3
"""Self-test PhageHostLearn host-typing evidence normalization."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for PhageHostLearn host-typing evidence normalization.")
    parser.add_argument("--output", required=True, help="Output self-test result TSV.")
    parser.add_argument("--report-output", required=True, help="Output self-test report TSV.")
    return parser.parse_args()


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


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


def write_fixtures(root: Path, malformed_kleborate: bool = False) -> dict[str, Path]:
    source = root / "source"
    host_map = source / "host_map.tsv"
    kaptive_k = source / "kaptive_k.tsv"
    kaptive_o = source / "kaptive_o.tsv"
    kleborate = source / "kleborate.tsv"
    archive = source / "hosts.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"fixture host archive\n")
    write_tsv(
        host_map,
        ["source_id", "canonical_id", "review_status", "notes"],
        [
            {"source_id": "hostA", "canonical_id": "canonical_host_A", "review_status": "reviewed", "notes": "fixture"},
            {"source_id": "hostB_contigs", "canonical_id": "canonical_host_B", "review_status": "reviewed", "notes": "fixture"},
            {"source_id": "pending_host", "canonical_id": "pending_host", "review_status": "pending", "notes": "not accepted"},
        ],
    )
    write_tsv(
        kaptive_k,
        ["Assembly", "Best match locus", "Best match type", "Match confidence", "Problems"],
        [
            {"Assembly": "hostA", "Best match locus": "KL1", "Best match type": "K1", "Match confidence": "Typeable", "Problems": ""},
            {"Assembly": "hostB_contig", "Best match locus": "KL2", "Best match type": "unknown (KL2)", "Match confidence": "Untypeable", "Problems": "low_identity"},
        ],
    )
    write_tsv(
        kaptive_o,
        ["Assembly", "Best match locus", "Best match type", "Match confidence", "Problems"],
        [
            {"Assembly": "hostA", "Best match locus": "OL1", "Best match type": "O1", "Match confidence": "Typeable", "Problems": ""},
            {"Assembly": "hostB_contig", "Best match locus": "OL2", "Best match type": "O2", "Match confidence": "Typeable", "Problems": ""},
        ],
    )
    kleborate_rows = [
        {
            "strain": "hostA",
            "enterobacterales__species__species": "Klebsiella pneumoniae",
            "enterobacterales__species__species_match": "strong",
            "klebsiella_pneumo_complex__mlst__ST": "ST1",
            "klebsiella_pneumo_complex__virulence_score__virulence_score": "1",
            "klebsiella_pneumo_complex__resistance_score__resistance_score": "0",
            "klebsiella_pneumo_complex__amr__Bla_chr": "SHV-1",
            "klebsiella__ybst__Yersiniabactin": "NA",
            "klebsiella__cbst__Colibactin": "NA",
            "klebsiella__abst__Aerobactin": "NA",
            "klebsiella__smst__Salmochelin": "NA",
            "klebsiella__rmst__RmpADC": "NA",
            "klebsiella__rmst__rmpA": "NA",
            "klebsiella__rmpa2__rmpA2": "NA",
            "general__contig_stats__QC_warnings": "NA",
        }
    ]
    if malformed_kleborate:
        kleborate_rows.append({**kleborate_rows[0], "strain": "unmapped_host"})
    write_tsv(kleborate, list(kleborate_rows[0]), kleborate_rows)
    return {
        "host_map": host_map,
        "kaptive_k": kaptive_k,
        "kaptive_o": kaptive_o,
        "kleborate": kleborate,
        "archive": archive,
    }


def run_normalizer(paths: dict[str, Path], output_dir: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).with_name("build_phagehostlearn_host_typing_evidence.py")
    cmd = [
        sys.executable,
        script.as_posix(),
        "--host-id-map",
        paths["host_map"].as_posix(),
        "--kaptive-k",
        paths["kaptive_k"].as_posix(),
        "--kaptive-o",
        paths["kaptive_o"].as_posix(),
        "--kleborate",
        paths["kleborate"].as_posix(),
        "--host-archive",
        paths["archive"].as_posix(),
        "--kaptive-version",
        "fixture-kaptive",
        "--kleborate-version",
        "fixture-kleborate",
        "--kaptive-k-command",
        "fixture kaptive k command",
        "--kaptive-o-command",
        "fixture kaptive o command",
        "--kleborate-command",
        "fixture kleborate command",
        "--kaptive-output",
        (output_dir / "kaptive.tsv").as_posix(),
        "--kleborate-output",
        (output_dir / "kleborate.tsv").as_posix(),
        "--report-output",
        (output_dir / "report.tsv").as_posix(),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, check=False, text=True, capture_output=True)


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="phagehostlearn-host-typing-") as tmp:
        root = Path(tmp)
        paths = write_fixtures(root)
        output_dir = root / "outputs"
        completed = run_normalizer(paths, output_dir)
        kaptive_rows = read_rows(output_dir / "kaptive.tsv")
        kleborate_rows = read_rows(output_dir / "kleborate.tsv")
        report_rows = read_rows(output_dir / "report.tsv")
        valid = (
            completed.returncode == 0
            and len(kaptive_rows) == 2
            and len(kleborate_rows) == 1
            and kaptive_rows[1]["host_genome_id"] == "canonical_host_B"
            and kaptive_rows[1]["K_confidence"] == "Untypeable"
            and any(row["metric"] == "kleborate_rows" and row["status"] == "warning" for row in report_rows)
        )
        tests.append(result("valid_fixture_outputs", "reviewed Kaptive/Kleborate fixture rows normalize to canonical host evidence", "ok", "ok" if valid else "bad_output"))

        collision_dir = root / "collision"
        completed = run_normalizer(
            paths,
            collision_dir,
            ["--kaptive-output", paths["kaptive_k"].as_posix()],
        )
        report_rows = read_rows(collision_dir / "report.tsv")
        collision_ok = completed.returncode != 0 and any("Input/output path collision" in row.get("notes", "") for row in report_rows)
        tests.append(result("path_collision_fails", "input/output path collisions are rejected", "ok", "ok" if collision_ok else "bad_output"))

        bad_paths = write_fixtures(root / "malformed", malformed_kleborate=True)
        transactional_dir = root / "transactional"
        transactional_dir.mkdir(parents=True, exist_ok=True)
        kaptive_out = transactional_dir / "kaptive.tsv"
        kleborate_out = transactional_dir / "kleborate.tsv"
        kaptive_out.write_text("sentinel\n", encoding="utf-8")
        kleborate_out.write_text("sentinel\n", encoding="utf-8")
        completed = run_normalizer(bad_paths, transactional_dir)
        unchanged = kaptive_out.read_text(encoding="utf-8") == "sentinel\n" and kleborate_out.read_text(encoding="utf-8") == "sentinel\n"
        tests.append(result("malformed_input_preserves_outputs", "malformed Kleborate input fails before replacing existing evidence outputs", "ok", "ok" if completed.returncode != 0 and unchanged else "bad_output"))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {
            "severity": "info",
            "item": "phagehostlearn_host_typing_evidence_self_test",
            "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}",
        }
    ]
    if failed:
        report.append({"severity": "error", "item": "phagehostlearn_host_typing_evidence_self_test", "message": "One or more self-tests failed."})
    else:
        report.append({"severity": "info", "item": "phagehostlearn_host_typing_evidence_self_test", "message": "All self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"PhageHostLearn host-typing evidence self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
