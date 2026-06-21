#!/usr/bin/env python3
"""Self-test PhageHostLearn phage CDS annotation generation."""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for PhageHostLearn phage CDS annotation generation.")
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


def make_fake_prodigal(path: Path) -> Path:
    script = path / "fake_prodigal.py"
    script.write_text(
        """#!/usr/bin/env python3
import sys
from pathlib import Path
args = sys.argv[1:]
inp = Path(args[args.index('-i') + 1])
out = Path(args[args.index('-a') + 1])
header = 'fixture_contig'
for line in inp.read_text().splitlines():
    if line.startswith('>'):
        header = line[1:].strip()
        break
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(f'>{header}_1 # 1 # 90 # 1 # ID=1_1;partial=00;start_type=ATG\\nMKKLLPTAA\\n')
Path(args[args.index('-o') + 1]).write_text('# fake prodigal output\\n')
""",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | 0o111)
    return script


def write_fixtures(root: Path, missing_member: bool = False) -> dict[str, Path]:
    source = root / "source"
    phage_map = source / "phage_map.tsv"
    manifest = source / "phage_manifest.tsv"
    archive = source / "phages.zip"
    rbpbase = source / "RBPbase.csv"
    source.mkdir(parents=True, exist_ok=True)
    write_tsv(
        phage_map,
        ["source_id", "canonical_id", "review_status", "notes"],
        [
            {"source_id": "phageA", "canonical_id": "canonical_phage_A", "review_status": "reviewed", "notes": "fixture"},
            {"source_id": "pending_phage", "canonical_id": "pending_phage", "review_status": "pending", "notes": "not accepted"},
        ],
    )
    member = "phages_genomes/missing.fasta" if missing_member else "phages_genomes/phageA.fasta"
    write_tsv(
        manifest,
        [
            "record_type",
            "genome_id",
            "accession",
            "source",
            "isolation_host",
            "host_species",
            "host_strain",
            "country",
            "year",
            "phage_lifestyle",
            "genome_length",
            "gc_percent",
            "K_type",
            "O_type",
            "ST",
            "AMR_markers",
            "virulence_markers",
            "raw_sequence_path",
            "notes",
        ],
        [
            {
                "record_type": "phage",
                "genome_id": "canonical_phage_A",
                "accession": "NA",
                "source": "PhageHostLearn_2024",
                "isolation_host": "NA",
                "host_species": "Klebsiella pneumoniae species complex",
                "host_strain": "NA",
                "country": "NA",
                "year": "NA",
                "phage_lifestyle": "NA",
                "genome_length": "96",
                "gc_percent": "50.0",
                "K_type": "NA",
                "O_type": "NA",
                "ST": "NA",
                "AMR_markers": "NA",
                "virulence_markers": "NA",
                "raw_sequence_path": "data/raw/external/phagehostlearn/phages_genomes/phageA.fasta",
                "notes": f"source_id=phageA; zip_member={member}; review_status=reviewed",
            }
        ],
    )
    write_tsv(
        rbpbase,
        ["phage_ID", "protein_ID", "protein_sequence", "dna_sequence", "xgb_score"],
        [
            {
                "phage_ID": "phageA",
                "protein_ID": "phageA_gp1",
                "protein_sequence": "MKKLLPTAA",
                "dna_sequence": "NA",
                "xgb_score": "0.990000",
            }
        ],
    )
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("phages_genomes/phageA.fasta", ">phageA\n" + "ATG" * 32 + "\n")
    return {"phage_map": phage_map, "manifest": manifest, "archive": archive, "rbpbase": rbpbase}


def run_builder(paths: dict[str, Path], output_dir: Path, fake_prodigal: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).with_name("build_phagehostlearn_phage_cds_annotations.py")
    cmd = [
        sys.executable,
        script.as_posix(),
        "--phage-id-map",
        paths["phage_map"].as_posix(),
        "--phage-manifest",
        paths["manifest"].as_posix(),
        "--phage-archive",
        paths["archive"].as_posix(),
        "--rbpbase",
        paths["rbpbase"].as_posix(),
        "--prodigal-executable",
        fake_prodigal.as_posix(),
        "--prodigal-version",
        "fixture-prodigal",
        "--annotation-output",
        (output_dir / "annotations.tsv").as_posix(),
        "--report-output",
        (output_dir / "report.tsv").as_posix(),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, check=False, text=True, capture_output=True)


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="phagehostlearn-phage-cds-") as tmp:
        root = Path(tmp)
        fake_prodigal = make_fake_prodigal(root)
        paths = write_fixtures(root)
        output_dir = root / "outputs"
        completed = run_builder(paths, output_dir, fake_prodigal)
        rows = read_rows(output_dir / "annotations.tsv")
        report_rows = read_rows(output_dir / "report.tsv")
        valid = (
            completed.returncode == 0
            and len(rows) == 1
            and rows[0]["genome_id"] == "canonical_phage_A"
            and rows[0]["gene_id"] == "prodigal_00001"
            and rows[0]["evidence"] == "sequence_backed_cds_prediction;RBPbase_ML_candidate"
            and rows[0]["module_hint"] == "rbp_depolymerase"
            and rows[0]["product"] == "RBPbase receptor-binding protein candidate"
            and any(row["metric"] == "annotation_rows" and row["value"] == "1" for row in report_rows)
            and any(row["metric"] == "rbpbase_exact_source_row_matches" and row["value"] == "1" for row in report_rows)
        )
        tests.append(result("valid_fixture_outputs", "reviewed phage archive member normalizes to one CDS row", "ok", "ok" if valid else "bad_output"))

        collision_dir = root / "collision"
        completed = run_builder(paths, collision_dir, fake_prodigal, ["--annotation-output", paths["manifest"].as_posix()])
        report_rows = read_rows(collision_dir / "report.tsv")
        collision_ok = completed.returncode != 0 and any("Input/output path collision" in row.get("notes", "") for row in report_rows)
        tests.append(result("path_collision_fails", "input/output path collisions are rejected", "ok", "ok" if collision_ok else "bad_output"))

        bad_paths = write_fixtures(root / "missing", missing_member=True)
        transactional_dir = root / "transactional"
        transactional_dir.mkdir(parents=True, exist_ok=True)
        out = transactional_dir / "annotations.tsv"
        out.write_text("sentinel\n", encoding="utf-8")
        completed = run_builder(bad_paths, transactional_dir, fake_prodigal)
        unchanged = out.read_text(encoding="utf-8") == "sentinel\n"
        tests.append(result("malformed_input_preserves_outputs", "missing archive member fails before replacing existing annotations", "ok", "ok" if completed.returncode != 0 and unchanged else "bad_output"))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {
            "severity": "info",
            "item": "phagehostlearn_phage_cds_annotation_self_test",
            "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}",
        }
    ]
    if failed:
        report.append({"severity": "error", "item": "phagehostlearn_phage_cds_annotation_self_test", "message": "One or more self-tests failed."})
    else:
        report.append({"severity": "info", "item": "phagehostlearn_phage_cds_annotation_self_test", "message": "All self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"PhageHostLearn phage CDS annotation self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
