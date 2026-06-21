#!/usr/bin/env python3
"""Run Phold/Foldseek on Pharokka-annotated assay phages.

This is glue around Phold/Foldseek. It uses existing Pharokka GenBank outputs,
runs Phold, and summarizes the resulting structural annotation table. It does
not implement structural annotation itself.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import re
import shlex
import subprocess
import time
from collections import Counter
from pathlib import Path

RUN_COLUMNS = [
    "selection_rank",
    "phage_id",
    "phold_version",
    "foldseek_version",
    "status",
    "returncode",
    "elapsed_seconds",
    "command",
    "input_gbk",
    "outdir",
    "prediction_rows",
    "high_confidence_rows",
    "receptor_like_rows",
    "non_pharokka_annotation_rows",
    "non_pharokka_receptor_like_rows",
    "tail_rows",
    "lysis_rows",
    "structural_rows",
    "stdout_log",
    "stderr_log",
    "message",
]

HIT_COLUMNS = [
    "phage_id",
    "cds_id",
    "function",
    "product",
    "annotation_method",
    "annotation_confidence",
    "evalue",
    "query_coverage",
    "target_coverage",
    "annotation_source",
    "prostt5_confidence",
    "feature_type",
    "source_file",
    "evidence_note",
]

DECISION_COLUMNS = ["decision_item", "status", "evidence", "decision", "claim_boundary"]
METRIC_COLUMNS = ["metric", "value", "interpretation"]

KEYWORDS = [
    ("depolymerase", ["depolymerase"]),
    ("receptor_binding", ["receptor-binding", "receptor binding", "host specificity", "host-specificity"]),
    ("tailspike", ["tailspike", "tail spike"]),
    ("tail_fiber", ["tail fiber", "tail fibre", "tail-fiber", "tail-fibre"]),
    ("baseplate", ["baseplate", "base plate"]),
    ("tail", ["tail"]),
    ("lysis", ["endolysin", "lysin", "holin", "spanin", "lysis"]),
    ("structural", ["capsid", "portal", "terminase", "head", "virion", "structural"]),
]

RECEPTOR_LIKE = {"depolymerase", "receptor_binding", "tailspike", "tail_fiber", "baseplate"}
PHAROKKA_READY_STATUSES = {"completed", "skipped_existing"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phold/Foldseek on Pharokka-annotated assay phages.")
    parser.add_argument("--selection", default="results/pilot/pharokka_selection.tsv")
    parser.add_argument("--pharokka-run-summary", default="results/pilot/pharokka_run_summary.tsv")
    parser.add_argument("--output-dir", default="results/pilot/phold_output")
    parser.add_argument("--log-dir", default="logs/pilot/phold")
    parser.add_argument("--database", default="results/pilot/phold_db")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--jobs", type=int, default=1, help="Number of independent phages to run concurrently.")
    parser.add_argument("--max-phages", type=int, default=30)
    parser.add_argument("--max-seqs", type=int, default=100)
    parser.add_argument("--phold-command", nargs="+", default=["mamba", "run", "-n", "phold", "phold"])
    parser.add_argument("--foldseek-command", nargs="+", default=["mamba", "run", "-n", "phold", "foldseek"])
    parser.add_argument("--run-output", default="results/pilot/phold_run_summary.tsv")
    parser.add_argument("--hit-output", default="results/pilot/phold_relevant_hits.tsv")
    parser.add_argument("--decision-output", default="results/pilot/phold_next_step_decision.tsv")
    parser.add_argument("--metrics-output", default="results/pilot/phold_summary_metrics.tsv")
    parser.add_argument("--report-output", default="PILOT_REPORT.md")
    parser.add_argument("--report-section-title", default="Phold Structural Pilot")
    parser.add_argument("--analysis-label", default="Pharokka 30-phage pilot")
    parser.add_argument("--force", action="store_true", help="Rerun Phold even when per-CDS predictions already exist.")
    parser.add_argument("--hyps", action="store_true", default=True, help="Pass --hyps to Phold to annotate Pharokka hypothetical proteins.")
    parser.add_argument("--no-hyps", dest="hyps", action="store_false", help="Do not pass --hyps to Phold.")
    return parser.parse_args()


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{k: "" if v is None else v for k, v in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def command_text(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def get_version(command: list[str], args: list[str]) -> str:
    try:
        completed = subprocess.run([*command, *args], capture_output=True, text=True, check=False, timeout=60)
    except Exception as exc:  # pragma: no cover - runtime diagnostic
        return f"version_error:{exc}"
    text = (completed.stdout + completed.stderr).strip().splitlines()
    return text[0] if text else "unknown"


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "unknown"


def classify_row(row: dict[str, str]) -> list[str]:
    text = " ".join([row.get("function", ""), row.get("product", ""), row.get("annotation_source", "")]).lower()
    features: list[str] = []
    for label, terms in KEYWORDS:
        if any(term in text for term in terms):
            features.append(label)
    return features


def summarize_predictions(path: Path, phage_id: str) -> tuple[dict[str, int], list[dict[str, str]]]:
    counts = Counter()
    hits: list[dict[str, str]] = []
    if not path.exists():
        return counts, hits
    rows = read_tsv(path)
    counts["prediction_rows"] = len(rows)
    for row in rows:
        method = row.get("annotation_method", "").lower()
        confidence = row.get("annotation_confidence", "").lower()
        if confidence == "high":
            counts["high_confidence_rows"] += 1
        if method and method != "pharokka":
            counts["non_pharokka_annotation_rows"] += 1
        features = classify_row(row)
        if "tail" in features:
            counts["tail_rows"] += 1
        if "lysis" in features:
            counts["lysis_rows"] += 1
        if "structural" in features:
            counts["structural_rows"] += 1
        if any(feature in RECEPTOR_LIKE for feature in features):
            counts["receptor_like_rows"] += 1
            if method and method != "pharokka":
                counts["non_pharokka_receptor_like_rows"] += 1
        receptor_features = [feature for feature in features if feature in RECEPTOR_LIKE]
        output_features = receptor_features or [feature for feature in features if feature in {"tail", "lysis", "structural"}]
        for feature in output_features:
            hits.append(
                {
                    "phage_id": phage_id,
                    "cds_id": row.get("cds_id", ""),
                    "function": row.get("function", ""),
                    "product": row.get("product", ""),
                    "annotation_method": row.get("annotation_method", ""),
                    "annotation_confidence": row.get("annotation_confidence", ""),
                    "evalue": row.get("evalue", ""),
                    "query_coverage": row.get("qCov", ""),
                    "target_coverage": row.get("tCov", ""),
                    "annotation_source": row.get("annotation_source", ""),
                    "prostt5_confidence": row.get("prostt5_confidence", ""),
                    "feature_type": feature,
                    "source_file": str(path),
                    "evidence_note": "Phold/Foldseek structural annotation; candidate signal only, not functional validation.",
                }
            )
    return counts, hits


def run_command(command: list[str], stdout_path: Path, stderr_path: Path) -> int:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
        completed = subprocess.run(command, stdout=out, stderr=err, text=True, check=False)
    return completed.returncode


def build_task(
    selection: dict[str, str],
    pharokka: dict[str, str],
    args: argparse.Namespace,
    phold_version: str,
    foldseek_version: str,
) -> tuple[dict[str, str], Path, list[str]]:
    phage_id = selection.get("phage_id", "")
    rank = selection.get("selection_rank", "")
    input_gbk = Path(pharokka.get("outdir", "")) / f"{phage_id}.gbk"
    outdir = Path(args.output_dir) / safe_name(phage_id)
    stdout_log = Path(args.log_dir) / f"{safe_name(phage_id)}.stdout.log"
    stderr_log = Path(args.log_dir) / f"{safe_name(phage_id)}.stderr.log"
    predictions = outdir / f"{phage_id}_per_cds_predictions.tsv"
    command = [
        *args.phold_command,
        "run",
        "--cpu",
        "-i",
        str(input_gbk),
        "-o",
        str(outdir),
        "-d",
        str(Path(args.database)),
        "-t",
        str(args.threads),
        "-p",
        phage_id,
        "-f",
        "--max_seqs",
        str(args.max_seqs),
    ]
    if args.hyps:
        command.insert(len(args.phold_command) + 2, "--hyps")
    row = {
        "selection_rank": rank,
        "phage_id": phage_id,
        "phold_version": phold_version,
        "foldseek_version": foldseek_version,
        "status": "",
        "returncode": "",
        "elapsed_seconds": "0",
        "command": command_text(command),
        "input_gbk": str(input_gbk),
        "outdir": str(outdir),
        "stdout_log": str(stdout_log),
        "stderr_log": str(stderr_log),
        "message": "",
    }
    return row, predictions, command


def process_one(
    selection: dict[str, str],
    pharokka: dict[str, str],
    args: argparse.Namespace,
    phold_version: str,
    foldseek_version: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    row, predictions, command = build_task(selection, pharokka, args, phold_version, foldseek_version)
    input_gbk = Path(row["input_gbk"])
    stdout_log = Path(row["stdout_log"])
    stderr_log = Path(row["stderr_log"])
    phage_id = row["phage_id"]
    start = time.monotonic()
    if pharokka.get("status") not in PHAROKKA_READY_STATUSES:
        row.update({"status": "skipped_no_pharokka", "message": f"Pharokka status was {pharokka.get('status', '')}"})
    elif not input_gbk.exists():
        row.update({"status": "skipped_missing_gbk", "message": f"Missing Pharokka GenBank: {input_gbk}"})
    elif predictions.exists() and not args.force:
        row.update({"status": "skipped_existing", "returncode": "0", "message": "Existing Phold predictions reused"})
    else:
        returncode = run_command(command, stdout_log, stderr_log)
        row["returncode"] = str(returncode)
        row["status"] = "completed" if returncode == 0 and predictions.exists() else "failed"
        row["message"] = "Phold completed" if row["status"] == "completed" else "Phold failed or did not create predictions"
    row["elapsed_seconds"] = f"{time.monotonic() - start:.2f}"
    counts, hits = summarize_predictions(predictions, phage_id)
    for key in [
        "prediction_rows",
        "high_confidence_rows",
        "receptor_like_rows",
        "non_pharokka_annotation_rows",
        "non_pharokka_receptor_like_rows",
        "tail_rows",
        "lysis_rows",
        "structural_rows",
    ]:
        row[key] = str(counts.get(key, 0))
    return row, hits


def build_metrics(run_rows: list[dict[str, str]], hit_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    statuses = Counter(row.get("status", "") for row in run_rows)
    features = Counter(row.get("feature_type", "") for row in hit_rows)
    metrics = [
        {"metric": "phages_selected", "value": str(len(run_rows)), "interpretation": "Phages submitted to Phold/Foldseek summarization."},
        {"metric": "phages_completed_or_reused", "value": str(statuses.get("completed", 0) + statuses.get("skipped_existing", 0)), "interpretation": "Phages with available per-CDS Phold predictions."},
        {"metric": "phages_failed", "value": str(statuses.get("failed", 0)), "interpretation": "Phold runs that failed or did not create predictions."},
        {"metric": "relevant_hit_rows", "value": str(len(hit_rows)), "interpretation": "Rows in the filtered relevant-hit table."},
        {"metric": "prediction_rows", "value": str(sum(int(row.get("prediction_rows") or 0) for row in run_rows)), "interpretation": "Total per-CDS rows summarized from Phold outputs."},
        {"metric": "high_confidence_rows", "value": str(sum(int(row.get("high_confidence_rows") or 0) for row in run_rows)), "interpretation": "Per-CDS rows labelled high confidence by Phold."},
        {"metric": "receptor_like_rows", "value": str(sum(int(row.get("receptor_like_rows") or 0) for row in run_rows)), "interpretation": "Receptor-like keyword rows in Phold outputs, including carried-forward Pharokka rows."},
        {"metric": "non_pharokka_receptor_like_rows", "value": str(sum(int(row.get("non_pharokka_receptor_like_rows") or 0) for row in run_rows)), "interpretation": "Receptor-like rows newly assigned by non-Pharokka methods."},
    ]
    for feature, count in sorted(features.items()):
        metrics.append({"metric": f"feature_type_{feature}", "value": str(count), "interpretation": "Relevant-hit rows by feature type; prioritization evidence only."})
    return metrics


def build_decisions(run_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    completed = sum(1 for row in run_rows if row.get("status") in {"completed", "skipped_existing"})
    failed = sum(1 for row in run_rows if row.get("status") == "failed")
    receptor_like = sum(int(row.get("receptor_like_rows") or 0) for row in run_rows)
    non_pharokka_receptor_like = sum(int(row.get("non_pharokka_receptor_like_rows") or 0) for row in run_rows)
    full_set_ready = completed == len(run_rows) and failed == 0 and len(run_rows) >= 100
    return [
        {
            "decision_item": "structural_annotation_coverage",
            "status": "full_set_available" if full_set_ready else "incomplete",
            "evidence": f"{completed}/{len(run_rows)} phages completed or reused; {failed} failed",
            "decision": "Use full-set Phold/Foldseek outputs for receptor-candidate prioritization after feature-coverage audit." if full_set_ready else "Resolve failed or missing Phold outputs before feature modeling.",
            "claim_boundary": "Structural annotation is computational prioritization evidence, not functional validation.",
        },
        {
            "decision_item": "use_phold_receptor_like_rows_for_modeling",
            "status": "blocked_pending_feature_audit",
            "evidence": f"{receptor_like} receptor-like keyword rows summarized; {non_pharokka_receptor_like} newly assigned by non-Pharokka methods",
            "decision": "Do not model until full feature tables are normalized with host K/O and taxonomy baselines.",
            "claim_boundary": "No RBP-versus-taxonomy or host-range prediction claim from annotation rows alone.",
        },
    ]


def update_report(path: Path, run_rows: list[dict[str, str]], metrics: list[dict[str, str]], args: argparse.Namespace) -> None:
    values = {row["metric"]: row["value"] for row in metrics}
    completed = values.get("phages_completed_or_reused", "0")
    failed = values.get("phages_failed", "0")
    prediction_rows = values.get("prediction_rows", "0")
    high_conf = values.get("high_confidence_rows", "0")
    receptor_like = values.get("receptor_like_rows", "0")
    non_pharokka_receptor_like = values.get("non_pharokka_receptor_like_rows", "0")
    section = f"""\n\n## {args.report_section_title}\n\nPhold/Foldseek was run on the {args.analysis_label} using Pharokka GenBank outputs. Completed or reused runs: {completed}/{len(run_rows)}; failed runs: {failed}. Per-CDS rows summarized: {prediction_rows}. High-confidence annotation rows: {high_conf}. Receptor-like keyword rows in Phold outputs: {receptor_like}; receptor-like rows newly assigned by non-Pharokka methods: {non_pharokka_receptor_like}. Relevant hits are in `{args.hit_output}`; run commands and statuses are in `{args.run_output}`.\n\nOperational note: Phold 1.2.5 failed in the initial smoke test when `--omit_probs` was used, so this runner does not pass that option. Runs use `--cpu`; with `--hyps`, Phold focuses on Pharokka hypothetical proteins and carries forward existing Pharokka annotations for known CDSs.\n\nClaim boundary: these structural annotations are prioritization evidence only. They do not demonstrate capsule specificity, productive infection, or that RBP/depolymerase features outperform taxonomy.\n"""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    marker = f"\n## {args.report_section_title}\n"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + section
    else:
        text = text.rstrip() + section
    path.write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")


def main() -> int:
    args = parse_args()
    selection_rows = read_tsv(Path(args.selection))[: args.max_phages]
    pharokka_rows = read_tsv(Path(args.pharokka_run_summary))
    pharokka_by_phage = {row.get("phage_id", ""): row for row in pharokka_rows}
    phold_version = get_version(args.phold_command, ["--version"])
    foldseek_version = get_version(args.foldseek_command, ["version"])

    jobs = max(1, args.jobs)
    run_rows: list[dict[str, str]] = []
    hit_rows: list[dict[str, str]] = []
    tasks = [(selection, pharokka_by_phage.get(selection.get("phage_id", ""), {})) for selection in selection_rows]

    if jobs == 1:
        results = [process_one(selection, pharokka, args, phold_version, foldseek_version) for selection, pharokka in tasks]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
            future_to_rank = {
                executor.submit(process_one, selection, pharokka, args, phold_version, foldseek_version): int(selection.get("selection_rank") or 0)
                for selection, pharokka in tasks
            }
            completed_results: list[tuple[int, tuple[dict[str, str], list[dict[str, str]]]]] = []
            for future in concurrent.futures.as_completed(future_to_rank):
                completed_results.append((future_to_rank[future], future.result()))
        results = [result for _rank, result in sorted(completed_results, key=lambda item: item[0])]

    for row, hits in results:
        run_rows.append(row)
        hit_rows.extend(hits)

    decisions = build_decisions(run_rows)
    metrics = build_metrics(run_rows, hit_rows)
    write_tsv(Path(args.run_output), RUN_COLUMNS, run_rows)
    write_tsv(Path(args.hit_output), HIT_COLUMNS, hit_rows)
    write_tsv(Path(args.decision_output), DECISION_COLUMNS, decisions)
    write_tsv(Path(args.metrics_output), METRIC_COLUMNS, metrics)
    update_report(Path(args.report_output), run_rows, metrics, args)

    completed = sum(1 for row in run_rows if row.get("status") in {"completed", "skipped_existing"})
    failed = sum(1 for row in run_rows if row.get("status") == "failed")
    print(
        f"Phold run complete: phages={len(selection_rows)}; completed_or_reused={completed}; "
        f"failed={failed}; relevant_hits={len(hit_rows)}"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
