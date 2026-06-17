#!/usr/bin/env python3
"""Generate figure source tables and lightweight SVG drafts."""

from __future__ import annotations

import argparse
import csv
import html
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


REPORT_COLUMNS = ["severity", "item", "message"]
FIGURE_MANIFEST_COLUMNS = [
    "figure_id",
    "title",
    "source_tsv",
    "draft_svg",
    "primary_inputs",
    "row_count",
    "status",
    "notes",
]

MISSING_VALUES = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate source TSVs and draft SVGs for planned manuscript figures."
    )
    parser.add_argument("--manifest", required=True, help="Stage 1 manifest TSV.")
    parser.add_argument("--clusters", required=True, help="Stage 2 phage_clusters.tsv.")
    parser.add_argument("--gene-clusters", required=True, help="Stage 3 gene_clusters.tsv.")
    parser.add_argument("--pangenome", required=True, help="Stage 3 pangenome_matrix.tsv.")
    parser.add_argument("--rbp-candidates", required=True, help="Stage 4 candidates.tsv.")
    parser.add_argument("--rbp-modules", required=True, help="Stage 4 module_clusters.tsv.")
    parser.add_argument("--novel-candidates", required=True, help="Stage 4 novel_candidates.tsv.")
    parser.add_argument("--host-metadata", required=True, help="Stage 5 host_metadata.tsv.")
    parser.add_argument("--phage-host-links", required=True, help="Stage 5 phage_host_links.tsv.")
    parser.add_argument("--host-defense", required=True, help="Stage 6 host_defense_systems.tsv.")
    parser.add_argument("--phage-antidefense", required=True, help="Stage 6 phage_antidefense_candidates.tsv.")
    parser.add_argument("--compatibility", required=True, help="Stage 6 compatibility_features.tsv.")
    parser.add_argument("--model-comparison", required=True, help="Stage 7 model_comparison.tsv.")
    parser.add_argument("--feature-importance", required=True, help="Stage 7 feature_importance.tsv.")
    parser.add_argument("--output-dir", required=True, help="Output directory under results/figures.")
    parser.add_argument("--manifest-output", required=True, help="Figure manifest TSV.")
    parser.add_argument("--report-output", required=True, help="Figure generation report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING_VALUES


def normalize(value: str | None) -> str:
    return "" if value is None else value.strip()


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [{key: normalize(value) for key, value in row.items()} for row in reader]


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def add_report(report: list[dict[str, str]], severity: str, item: str, message: str) -> None:
    report.append({"severity": severity, "item": item, "message": message})


def counter_rows(counter: Counter[str], category_column: str, count_column: str = "count") -> list[dict[str, str]]:
    return [
        {category_column: key, count_column: str(value)}
        for key, value in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def count_by(rows: list[dict[str, str]], column: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        value = row.get(column, "")
        counts[value if not is_missing(value) else "missing"] += 1
    return counts


def split_values(value: str) -> list[str]:
    if is_missing(value):
        return []
    return [item.strip() for item in value.replace(",", ";").split(";") if item.strip()]


def parse_int(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def parse_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def svg_bar_chart(path: Path, title: str, rows: list[dict[str, str]], label_col: str, value_col: str, width: int = 900, height: int = 520) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    chart_rows = rows[:12]
    max_value = max([parse_float(row.get(value_col, "0")) for row in chart_rows] + [1.0])
    margin_left = 260
    margin_top = 70
    row_height = 30
    bar_max = width - margin_left - 70
    content_height = max(height, margin_top + 40 + row_height * max(1, len(chart_rows)))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{content_height}" viewBox="0 0 {width} {content_height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="30" y="38" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#222222">{html.escape(title)}</text>',
    ]
    if not chart_rows:
        parts.append('<text x="30" y="100" font-family="Arial, sans-serif" font-size="16" fill="#666666">No data available.</text>')
    for index, row in enumerate(chart_rows):
        y = margin_top + index * row_height
        label = row.get(label_col, "missing") or "missing"
        value = parse_float(row.get(value_col, "0"))
        bar_width = max(0, int((value / max_value) * bar_max)) if max_value else 0
        parts.append(f'<text x="30" y="{y + 19}" font-family="Arial, sans-serif" font-size="13" fill="#333333">{html.escape(label[:48])}</text>')
        parts.append(f'<rect x="{margin_left}" y="{y}" width="{bar_width}" height="20" fill="#31688e"/>')
        parts.append(f'<text x="{margin_left + bar_width + 8}" y="{y + 15}" font-family="Arial, sans-serif" font-size="13" fill="#333333">{value:g}</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def status_for_rows(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "empty_schema_valid"
    if len(rows) == 1 and rows[0].get("status") == "empty_schema_valid":
        return "empty_schema_valid"
    return "ready"


def figure_1(manifest: list[dict[str, str]], clusters: list[dict[str, str]]) -> list[dict[str, str]]:
    cluster_count_by_type = count_by(clusters, "record_type")
    rows = []
    for record_type, count in count_by(manifest, "record_type").items():
        rows.append(
            {
                "panel": "record_type_counts",
                "category": record_type,
                "count": str(count),
                "clustered_count": str(cluster_count_by_type.get(record_type, 0)),
                "notes": "manifest records and clustered phage-like records",
            }
        )
    for lifestyle, count in count_by(manifest, "phage_lifestyle").items():
        rows.append(
            {
                "panel": "lifestyle_counts",
                "category": lifestyle,
                "count": str(count),
                "clustered_count": "",
                "notes": "lifestyle metadata from manifest",
            }
        )
    return rows


def figure_2(gene_clusters: list[dict[str, str]], pangenome: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = []
    for module_hint, count in count_by(gene_clusters, "module_hint").items():
        rows.append({"panel": "module_hint_counts", "category": module_hint, "count": str(count), "notes": "gene cluster module hints"})
    genome_count_distribution = Counter(row.get("genome_count", "0") for row in gene_clusters)
    for genome_count, count in sorted(genome_count_distribution.items(), key=lambda item: (parse_int(item[0]), item[0])):
        rows.append({"panel": "gene_cluster_genome_count_distribution", "category": genome_count, "count": str(count), "notes": "number of genomes containing each gene cluster"})
    if not rows and pangenome:
        rows.append({"panel": "pangenome_rows", "category": "gene_clusters", "count": str(len(pangenome)), "notes": "fallback pangenome row count"})
    return rows


def figure_3(candidates: list[dict[str, str]], modules: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = []
    for module in modules:
        rows.append(
            {
                "module_cluster_id": module.get("module_cluster_id", ""),
                "representative_product": module.get("representative_product", ""),
                "candidate_count": module.get("candidate_count", "0"),
                "genome_count": module.get("genome_count", "0"),
                "predicted_enzyme_classes": module.get("predicted_enzyme_classes", ""),
                "novelty_tiers": module.get("novelty_tiers", ""),
                "max_confidence_score": module.get("max_confidence_score", "0"),
            }
        )
    if not rows:
        for label, count in count_by(candidates, "predicted_enzyme_class").items():
            rows.append({"module_cluster_id": label, "representative_product": label, "candidate_count": str(count), "genome_count": "", "predicted_enzyme_classes": label, "novelty_tiers": "", "max_confidence_score": "0"})
    return rows


def rbp_modules_by_phage(candidates: list[dict[str, str]]) -> dict[str, str]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for row in candidates:
        if not is_missing(row.get("genome_id")) and not is_missing(row.get("module_cluster_id")):
            grouped[row["genome_id"]].add(row["module_cluster_id"])
    return {key: ";".join(sorted(values)) for key, values in grouped.items()}


def figure_4(links: list[dict[str, str]], candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    modules = rbp_modules_by_phage(candidates)
    counts: Counter[tuple[str, str, str]] = Counter()
    for link in links:
        module_text = modules.get(link.get("phage_genome_id", ""), "missing_rbp_module")
        for module in split_values(module_text) or ["missing_rbp_module"]:
            counts[(module, link.get("K_type", "missing") or "missing", link.get("O_type", "missing") or "missing")] += 1
    return [
        {"module_cluster_id": module, "K_type": k_type, "O_type": o_type, "phage_host_link_count": str(count)}
        for (module, k_type, o_type), count in sorted(counts.items())
    ]


def figure_5(compatibility: list[dict[str, str]], model_comparison: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = []
    for status, count in count_by(compatibility, "compatibility_feature_status").items():
        rows.append({"panel": "compatibility_status_counts", "category": status, "count": str(count), "metric": "count", "value": str(count)})
    for row in model_comparison:
        if row.get("hypothesis") == "H4" and row.get("task") in {"predict_compatibility_feature_status", "predict_matched_counterdefense_status"}:
            rows.append(
                {
                    "panel": row.get("task", ""),
                    "category": row.get("feature_set", ""),
                    "count": row.get("n_samples", "0"),
                    "metric": "delta_vs_baseline",
                    "value": row.get("delta_vs_baseline", ""),
                }
            )
    return rows


def figure_6(novel: list[dict[str, str]], links: list[dict[str, str]], feature_importance: list[dict[str, str]]) -> list[dict[str, str]]:
    link_by_phage = {row.get("phage_genome_id", ""): row for row in links}
    rows = []
    for row in novel:
        link = link_by_phage.get(row.get("genome_id", ""), {})
        rows.append(
            {
                "priority_type": "novel_rbp_candidate",
                "item_id": row.get("candidate_id", ""),
                "phage_genome_id": row.get("genome_id", ""),
                "K_type": link.get("K_type", ""),
                "O_type": link.get("O_type", ""),
                "score": row.get("confidence_score", "0"),
                "rationale": row.get("novelty_rationale", ""),
            }
        )
    for row in feature_importance[:20]:
        rows.append(
            {
                "priority_type": "model_feature_signal",
                "item_id": row.get("feature", ""),
                "phage_genome_id": "",
                "K_type": "",
                "O_type": "",
                "score": row.get("association_value", "0"),
                "rationale": f"{row.get('hypothesis', '')}:{row.get('task', '')}:{row.get('feature_set', '')}",
            }
        )
    return rows


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    manifest_output = Path(args.manifest_output)
    report_output = Path(args.report_output)
    report: list[dict[str, str]] = []

    inputs = {
        "manifest": read_tsv(Path(args.manifest)),
        "clusters": read_tsv(Path(args.clusters)),
        "gene_clusters": read_tsv(Path(args.gene_clusters)),
        "pangenome": read_tsv(Path(args.pangenome)),
        "rbp_candidates": read_tsv(Path(args.rbp_candidates)),
        "rbp_modules": read_tsv(Path(args.rbp_modules)),
        "novel_candidates": read_tsv(Path(args.novel_candidates)),
        "host_metadata": read_tsv(Path(args.host_metadata)),
        "phage_host_links": read_tsv(Path(args.phage_host_links)),
        "host_defense": read_tsv(Path(args.host_defense)),
        "phage_antidefense": read_tsv(Path(args.phage_antidefense)),
        "compatibility": read_tsv(Path(args.compatibility)),
        "model_comparison": read_tsv(Path(args.model_comparison)),
        "feature_importance": read_tsv(Path(args.feature_importance)),
    }
    add_report(report, "info", "inputs", "; ".join(f"{key}={len(value)}" for key, value in inputs.items()))

    figure_specs = [
        ("figure_1_dataset_atlas", "Dataset and phage diversity atlas", figure_1(inputs["manifest"], inputs["clusters"]), "category", "count", "manifest;clusters"),
        ("figure_2_phage_pangenome", "Klebsiella phage pangenome", figure_2(inputs["gene_clusters"], inputs["pangenome"]), "category", "count", "gene_clusters;pangenome"),
        ("figure_3_rbp_module_network", "RBP/depolymerase module network", figure_3(inputs["rbp_candidates"], inputs["rbp_modules"]), "module_cluster_id", "candidate_count", "rbp_candidates;rbp_modules"),
        ("figure_4_k_o_association", "Host K/O association map", figure_4(inputs["phage_host_links"], inputs["rbp_candidates"]), "module_cluster_id", "phage_host_link_count", "phage_host_links;rbp_candidates"),
        ("figure_5_defense_counterdefense", "Defense/counter-defense compatibility model", figure_5(inputs["compatibility"], inputs["model_comparison"]), "category", "count", "compatibility;model_comparison"),
        ("figure_6_novelty_prioritization", "Novelty and translational prioritization", figure_6(inputs["novel_candidates"], inputs["phage_host_links"], inputs["feature_importance"]), "item_id", "score", "novel_candidates;feature_importance;phage_host_links"),
    ]

    figure_manifest = []
    for figure_id, title, rows, label_col, value_col, primary_inputs in figure_specs:
        source_tsv = output_dir / f"{figure_id}_source.tsv"
        draft_svg = output_dir / f"{figure_id}.svg"
        columns = list(rows[0].keys()) if rows else ["status", "notes"]
        if not rows:
            rows = [{"status": "empty_schema_valid", "notes": "No source rows available for this figure yet."}]
            columns = ["status", "notes"]
        write_tsv(source_tsv, columns, rows)
        svg_bar_chart(draft_svg, title, rows, label_col if label_col in columns else columns[0], value_col if value_col in columns else columns[-1])
        figure_manifest.append(
            {
                "figure_id": figure_id,
                "title": title,
                "source_tsv": str(source_tsv),
                "draft_svg": str(draft_svg),
                "primary_inputs": primary_inputs,
                "row_count": str(len(rows)),
                "status": status_for_rows(rows),
                "notes": "Draft SVG is a reproducible scaffold; visual polishing can happen later.",
            }
        )

    write_tsv(manifest_output, FIGURE_MANIFEST_COLUMNS, figure_manifest)
    add_report(report, "info", "figures", f"Generated {len(figure_manifest)} figure source tables and SVG drafts in {output_dir}.")
    write_tsv(report_output, REPORT_COLUMNS, report)
    print(f"Generated {len(figure_manifest)} figure source tables and SVG drafts in {output_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
