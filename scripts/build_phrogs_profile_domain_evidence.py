#!/usr/bin/env python3
"""Build reviewed generic domain evidence from MMseqs PHROGs profile hits.

MMseqs performs the profile search. This script only joins the tabular MMseqs
output to PHROG annotations and keeps receptor-relevant PHROG hits for the
existing RBP/depolymerase evidence normalizer.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path

OUTPUT_COLUMNS = [
    "annotation_gene_id",
    "domain_id",
    "domain_name",
    "start_aa",
    "end_aa",
    "evalue",
    "evidence_source",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
RECEPTOR_PATTERNS = [
    re.compile(pattern, re.I)
    for pattern in [
        r"tail\s*fiber",
        r"tail\s*spike",
        r"baseplate\s*spike",
        r"receptor",
        r"depolymerase",
        r"polysaccharide",
        r"capsule",
        r"colanic\s+acid",
        r"glycosidase",
        r"glycanase",
    ]
]
EXCLUDE_PATTERNS = [re.compile(r"assembly", re.I)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mmseqs-hits", default="results/production/rbp_depolymerase/phrogs_profile_domain/phrogs_profile_hits.tsv")
    parser.add_argument("--phrog-annotations", default="results/pilot/pharokka_db/phrog_annot_v4.tsv")
    parser.add_argument("--output", default="data/metadata/production_evidence/phrogs_profile_receptor_domain_input.tsv")
    parser.add_argument("--report-output", default="data/metadata/production_evidence/phrogs_profile_receptor_domain_input_report.tsv")
    parser.add_argument("--min-qcov", type=float, default=0.10)
    return parser.parse_args()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def phrog_map(path: Path) -> dict[str, dict[str, str]]:
    mapping = {}
    for row in read_tsv(path):
        phrog = row.get("phrog", "")
        if phrog:
            mapping[f"phrog_{phrog}"] = row
    return mapping


def is_receptor_relevant(annotation: dict[str, str]) -> bool:
    text = " ".join([annotation.get("annot", ""), annotation.get("category", "")])
    return any(pattern.search(text) for pattern in RECEPTOR_PATTERNS) and not any(pattern.search(text) for pattern in EXCLUDE_PATTERNS)


def to_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


def main() -> int:
    args = parse_args()
    hits = read_tsv(Path(args.mmseqs_hits))
    annotations = phrog_map(Path(args.phrog_annotations))
    rows: list[dict[str, str]] = []
    skipped = Counter()
    for hit in hits:
        target = hit.get("target", "")
        annotation = annotations.get(target)
        if not annotation:
            skipped["unknown_phrog"] += 1
            continue
        if not is_receptor_relevant(annotation):
            skipped["not_receptor_relevant"] += 1
            continue
        if to_float(hit.get("qcov", "0")) < args.min_qcov:
            skipped["low_qcov"] += 1
            continue
        start = hit.get("qstart", "")
        end = hit.get("qend", "")
        if start and end and int(float(start)) > int(float(end)):
            start, end = end, start
        notes = (
            "PHROGs profile hit from MMseqs2; computational receptor-module candidate only, not capsule specificity or functional validation; "
            f"phrog_category={annotation.get('category', '')}; bits={hit.get('bits', '')}; qcov={hit.get('qcov', '')}; "
            f"tcov={hit.get('tcov', '')}; pident={hit.get('pident', '')}"
        )
        rows.append(
            {
                "annotation_gene_id": hit.get("query", ""),
                "domain_id": target,
                "domain_name": annotation.get("annot", "") or target,
                "start_aa": str(int(float(start))) if start else "",
                "end_aa": str(int(float(end))) if end else "",
                "evalue": hit.get("evalue", ""),
                "evidence_source": "MMseqs2 PHROGs profile search",
                "notes": notes,
            }
        )
    rows.sort(key=lambda row: (row["annotation_gene_id"], row["domain_id"], row["start_aa"], row["end_aa"]))
    report = [
        {"severity": "info", "item": "input_hits", "message": str(len(hits))},
        {"severity": "info", "item": "normalized_rows", "message": str(len(rows))},
        {"severity": "info", "item": "unique_proteins", "message": str(len({row['annotation_gene_id'] for row in rows}))},
        {"severity": "info", "item": "unique_phrogs", "message": str(len({row['domain_id'] for row in rows}))},
        {"severity": "info", "item": "min_qcov", "message": f"{args.min_qcov:g}"},
    ]
    report.extend({"severity": "info", "item": f"skipped_{key}", "message": str(value)} for key, value in sorted(skipped.items()))
    write_tsv(Path(args.output), OUTPUT_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"PHROGs receptor-domain evidence rows: {len(rows)} from {len(hits)} MMseqs hits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
