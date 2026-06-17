#!/usr/bin/env python3
"""Build a metadata-only NCBI Klebsiella phage source export."""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import date
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import urlopen


EXPORT_COLUMNS = [
    "accession",
    "genome_id",
    "host_species",
    "country",
    "year",
    "genome_length",
    "gc_percent",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
DEFAULT_QUERY = '"Klebsiella phage"[Title] AND "complete genome"[Title]'
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Query NCBI nuccore through E-utilities and write a reviewed, "
            "metadata-only Klebsiella phage export. This script never downloads "
            "FASTA and never writes data/raw; sequence acquisition is handled by "
            "the project's sequence fetch manifest."
        )
    )
    parser.add_argument("--query", default=DEFAULT_QUERY, help="NCBI nuccore search query.")
    parser.add_argument("--retmax", type=int, default=10, help="Maximum NCBI records to export.")
    parser.add_argument("--output", required=True, help="Output reviewed export TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--date", default=str(date.today()), help="Review date to record in notes.")
    parser.add_argument("--email", default="", help="Optional email parameter for NCBI E-utilities.")
    parser.add_argument("--api-key", default="", help="Optional NCBI API key.")
    parser.add_argument("--sleep-seconds", type=float, default=0.34, help="Delay between E-utilities calls.")
    return parser.parse_args()


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def eutils_url(endpoint: str, params: dict[str, str]) -> str:
    return f"{EUTILS}/{endpoint}.fcgi?{urlencode(params)}"


def eutils_json(endpoint: str, params: dict[str, str], sleep_seconds: float) -> dict:
    url = eutils_url(endpoint, params)
    with urlopen(url, timeout=60) as response:
        data = json.load(response)
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    return data


def base_params(args: argparse.Namespace) -> dict[str, str]:
    params: dict[str, str] = {}
    if args.email:
        params["email"] = args.email
    if args.api_key:
        params["api_key"] = args.api_key
    return params


def search_ids(args: argparse.Namespace) -> tuple[str, list[str]]:
    params = {
        **base_params(args),
        "db": "nuccore",
        "term": args.query,
        "retmode": "json",
        "retmax": str(args.retmax),
        "sort": "relevance",
    }
    data = eutils_json("esearch", params, args.sleep_seconds)
    result = data.get("esearchresult", {})
    return result.get("count", "0"), result.get("idlist", [])


def fetch_summaries(args: argparse.Namespace, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    params = {
        **base_params(args),
        "db": "nuccore",
        "id": ",".join(ids),
        "retmode": "json",
    }
    data = eutils_json("esummary", params, args.sleep_seconds)
    result = data.get("result", {})
    return [result[uid] for uid in result.get("uids", []) if uid in result]


def keep_summary(summary: dict) -> bool:
    title = summary.get("title", "")
    accession = summary.get("accessionversion", "")
    return bool(accession) and "Klebsiella phage" in title and "complete genome" in title


def genome_name(title: str) -> str:
    suffix = ", complete genome"
    return title[: -len(suffix)] if title.endswith(suffix) else title


def row_from_summary(summary: dict, query: str, review_date: str) -> dict[str, str]:
    uid = str(summary.get("uid", "NA"))
    title = summary.get("title", "")
    return {
        "accession": summary.get("accessionversion", ""),
        "genome_id": genome_name(title),
        "host_species": "Klebsiella sp.",
        "country": "NA",
        "year": "NA",
        "genome_length": str(summary.get("slen", "NA")),
        "gc_percent": "NA",
        "notes": (
            f"Reviewed metadata-only NCBI E-utilities seed row for NCBI Virus/GenBank/RefSeq cultured-phage source on {review_date}; "
            f"query={query}; uid={uid}; ESummary title={title}; organism={summary.get('organism', 'NA')}; "
            "host species conservatively recorded as Klebsiella sp. from phage title, not strain-resolved host metadata; "
            "gc_percent and local FASTA intentionally left NA/pending until sequence acquisition is performed through the project fetch-manifest workflow; "
            "seed batch supports source-unlock testing and should be expanded/deduplicated before manuscript-scale analysis."
        ),
    }


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []
    rows: list[dict[str, str]] = []
    try:
        count, ids = search_ids(args)
        summaries = fetch_summaries(args, ids)
        rows = [row_from_summary(summary, args.query, args.date) for summary in summaries if keep_summary(summary)]
        report.append({"severity": "info", "item": "ncbi_search", "message": f"query_count={count}; retrieved_ids={len(ids)}; retained_rows={len(rows)}"})
        if not rows:
            report.append({"severity": "warning", "item": "ncbi_export", "message": "No rows retained after Klebsiella phage complete-genome filtering."})
    except Exception as exc:  # noqa: BLE001 - report network/API failures in TSV form
        report.append({"severity": "error", "item": "ncbi_export", "message": str(exc)})

    write_tsv(Path(args.output), EXPORT_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    errors = sum(1 for row in report if row["severity"] == "error")
    print(f"NCBI Klebsiella phage export complete: {len(rows)} rows, {errors} errors.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
