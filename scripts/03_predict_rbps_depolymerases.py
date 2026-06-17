#!/usr/bin/env python3
"""Predict candidate RBP/depolymerase modules from normalized phage annotations."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable


CANDIDATE_COLUMNS = [
    "candidate_id",
    "genome_id",
    "record_type",
    "species_cluster_id",
    "representative_id",
    "gene_id",
    "annotation_gene_id",
    "gene_cluster_id",
    "module_cluster_id",
    "product",
    "protein_length_aa",
    "sequence_hit",
    "domain_hit",
    "structural_hit",
    "synteny_context",
    "predicted_enzyme_class",
    "evidence_types",
    "confidence_score",
    "confidence_label",
    "novelty_tier",
    "novelty_rationale",
    "is_high_confidence",
    "notes",
]

DOMAIN_ARCHITECTURE_COLUMNS = [
    "candidate_id",
    "annotation_gene_id",
    "genome_id",
    "gene_id",
    "domain_architecture",
    "domain_count",
    "domain_sources",
    "best_domain_hit",
    "domain_support",
    "notes",
]

MODULE_CLUSTER_COLUMNS = [
    "module_cluster_id",
    "gene_cluster_id",
    "candidate_count",
    "genome_count",
    "species_cluster_count",
    "representative_product",
    "predicted_enzyme_classes",
    "evidence_types",
    "max_confidence_score",
    "member_candidate_ids",
    "member_genome_ids",
    "member_species_cluster_ids",
    "novelty_tiers",
    "notes",
]

REPORT_COLUMNS = ["severity", "item", "message"]

DOMAIN_REQUIRED_COLUMNS = ["annotation_gene_id", "domain_id", "domain_name"]
STRUCTURAL_REQUIRED_COLUMNS = ["annotation_gene_id", "structural_hit_id", "structural_hit_name"]

RBP_PATTERN = re.compile(
    r"receptor[- ]?binding|tail ?fiber|tail ?spike|tailspike|baseplate|host[- ]?range|adhesin",
    re.I,
)
DEPOLYMERASE_PATTERN = re.compile(
    r"(?<!rbp_)depolymerase|capsul(?:e|ar)|polysaccharide|glycosidase|glycanase|(?:^|[_\s-])lyase(?:$|[_\s-])|hyaluronidase|pectate|sialidase",
    re.I,
)
EXCLUSION_PATTERN = re.compile(r"terminase|capsid|portal|holin|endolysin|integrase|polymerase|helicase", re.I)
TAIL_CONTEXT_PATTERN = re.compile(r"tail|baseplate|fiber|spike|tape measure|sheath", re.I)
STRUCTURAL_SUPPORT_PATTERN = re.compile(r"depolymerase|tail|fiber|spike|receptor|capsule|polysaccharide|glycosidase|lyase", re.I)


class StageError(Exception):
    """Raised when required inputs are invalid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Identify candidate receptor-binding proteins and depolymerases "
            "from normalized annotations, optional domain evidence, and optional "
            "structure-informed evidence."
        )
    )
    parser.add_argument("--annotations", required=True, help="Stage 3 phage_annotations.tsv.")
    parser.add_argument("--gene-clusters", required=True, help="Stage 3 gene_clusters.tsv.")
    parser.add_argument("--thresholds", required=True, help="config/thresholds.yaml.")
    parser.add_argument("--domain-evidence", default="", help="Optional domain evidence TSV.")
    parser.add_argument("--structural-evidence", default="", help="Optional structural evidence TSV.")
    parser.add_argument("--candidates-output", required=True, help="Output candidate table TSV.")
    parser.add_argument("--domain-architectures-output", required=True, help="Output domain architecture table TSV.")
    parser.add_argument("--module-clusters-output", required=True, help="Output RBP/depolymerase module cluster table TSV.")
    parser.add_argument("--novel-candidates-output", required=True, help="Output high-priority novel candidate table TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def normalize(value: str | None) -> str:
    return "" if value is None else value.strip()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(f"Required input does not exist: {path}")
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


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


def parse_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def load_thresholds(path: Path) -> dict[str, float | bool]:
    defaults: dict[str, float | bool] = {
        "min_protein_length_aa": 150.0,
        "high_confidence_score": 0.75,
        "medium_confidence_score": 0.50,
        "require_synteny_for_high_confidence": True,
    }
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        values = data.get("rbp_depolymerase", {}) if isinstance(data, dict) else {}
        defaults["min_protein_length_aa"] = float(values.get("min_protein_length_aa", defaults["min_protein_length_aa"]))
        defaults["high_confidence_score"] = float(values.get("high_confidence_score", defaults["high_confidence_score"]))
        defaults["medium_confidence_score"] = float(values.get("medium_confidence_score", defaults["medium_confidence_score"]))
        defaults["require_synteny_for_high_confidence"] = bool(
            values.get("require_synteny_for_high_confidence", defaults["require_synteny_for_high_confidence"])
        )
        return defaults
    except Exception:
        for key in ["min_protein_length_aa", "high_confidence_score", "medium_confidence_score"]:
            match = re.search(rf"^\s*{re.escape(key)}\s*:\s*([0-9]+(?:\.[0-9]+)?)", text, re.M)
            if match:
                defaults[key] = float(match.group(1))
        match = re.search(r"^\s*require_synteny_for_high_confidence\s*:\s*(true|false)", text, re.I | re.M)
        if match:
            defaults["require_synteny_for_high_confidence"] = match.group(1).lower() == "true"
        return defaults


def load_evidence(
    path_text: str,
    required_columns: list[str],
    evidence_name: str,
    report: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    if is_missing(path_text):
        add_report(report, "info", evidence_name, f"No {evidence_name} table supplied.")
        return {}
    path = Path(path_text)
    if not path.exists():
        add_report(report, "warning", evidence_name, f"{evidence_name} table does not exist: {path}; continuing without it.")
        return {}
    fieldnames, rows = read_tsv(path)
    missing = [column for column in required_columns if column not in fieldnames]
    if missing:
        add_report(report, "error", evidence_name, f"{evidence_name} missing required columns: " + ", ".join(missing))
        raise StageError(f"Invalid {evidence_name} schema")
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        annotation_gene_id = row.get("annotation_gene_id", "")
        if not is_missing(annotation_gene_id):
            grouped[annotation_gene_id].append(row)
    add_report(report, "info", evidence_name, f"Loaded {sum(len(v) for v in grouped.values())} {evidence_name} rows for {len(grouped)} genes.")
    return grouped


def load_gene_clusters(path: Path) -> dict[str, dict[str, str]]:
    _, rows = read_tsv(path)
    return {row.get("gene_cluster_id", ""): row for row in rows if not is_missing(row.get("gene_cluster_id"))}


def row_text(row: dict[str, str], cluster_row: dict[str, str] | None = None) -> str:
    parts = [
        row.get("product", ""),
        row.get("phrog_category", ""),
        row.get("functional_category", ""),
        row.get("module_hint", ""),
    ]
    if cluster_row:
        parts.extend(
            [
                cluster_row.get("representative_product", ""),
                cluster_row.get("phrog_category", ""),
                cluster_row.get("functional_category", ""),
                cluster_row.get("module_hint", ""),
            ]
        )
    return " ".join(parts)


def evidence_names(rows: list[dict[str, str]], id_column: str, name_column: str) -> str:
    names = []
    for row in rows:
        hit_id = row.get(id_column, "")
        hit_name = row.get(name_column, "")
        if is_missing(hit_id) and is_missing(hit_name):
            continue
        names.append(f"{hit_id}:{hit_name}" if not is_missing(hit_id) else hit_name)
    return ";".join(names)


def domain_architecture(rows: list[dict[str, str]]) -> tuple[str, str, str, str]:
    if not rows:
        return "", "0", "", "none"

    def domain_start(row: dict[str, str]) -> tuple[int, str]:
        return (parse_int(row.get("start_aa", ""), 10**9), row.get("domain_name", ""))

    ordered = sorted(rows, key=domain_start)
    labels = [row.get("domain_name", "") or row.get("domain_id", "") for row in ordered]
    sources = sorted({row.get("evidence_source", row.get("tool", "")) for row in ordered if not is_missing(row.get("evidence_source", row.get("tool", "")))})
    best = ordered[0]
    best_hit = f"{best.get('domain_id', '')}:{best.get('domain_name', '')}".strip(":")
    support = "rbp_depolymerase_domain" if STRUCTURAL_SUPPORT_PATTERN.search(" ".join(labels)) else "domain_present"
    return "|".join(labels), str(len(labels)), ";".join(sources), f"{best_hit} ({support})"


def sequence_hit(row: dict[str, str], cluster_row: dict[str, str] | None) -> tuple[str, str]:
    phrog_id = row.get("phrog_id", "")
    product = row.get("product", "")
    functional_category = row.get("functional_category", "")
    if not is_missing(phrog_id):
        return f"{phrog_id}:{product or functional_category}", "strong_sequence_hit"
    if cluster_row and cluster_row.get("gene_cluster_source") == "product" and not is_missing(product):
        return f"product:{product}", "weak_sequence_hit"
    if not is_missing(product) and not re.search(r"hypothetical|unknown|uncharacteri[sz]ed", product, re.I):
        return f"product:{product}", "weak_sequence_hit"
    return "", "no_sequence_hit"


def structural_hit(rows: list[dict[str, str]]) -> str:
    return evidence_names(rows, "structural_hit_id", "structural_hit_name")


def domain_hit(rows: list[dict[str, str]]) -> str:
    return evidence_names(rows, "domain_id", "domain_name")


def predicted_enzyme_class(text: str, domain_text: str, structure_text: str) -> str:
    combined = " ".join([text, domain_text, structure_text])
    if DEPOLYMERASE_PATTERN.search(combined) and re.search(r"tail ?spike|tailspike|spike", combined, re.I):
        return "capsule_depolymerase_tailspike"
    if DEPOLYMERASE_PATTERN.search(combined):
        return "putative_depolymerase"
    if re.search(r"tail ?fiber|fiber", combined, re.I):
        return "tail_fiber_receptor_binding_protein"
    if re.search(r"tail ?spike|tailspike|spike", combined, re.I):
        return "tailspike_receptor_binding_protein"
    if re.search(r"baseplate", combined, re.I):
        return "baseplate_receptor_binding_candidate"
    return "receptor_binding_candidate"


def sorted_annotations(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            row.get("genome_id", ""),
            parse_int(row.get("start", ""), 10**9),
            parse_int(row.get("end", ""), 10**9),
            row.get("annotation_gene_id", ""),
        ),
    )


def build_synteny_context(rows: list[dict[str, str]]) -> dict[str, str]:
    by_genome: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_genome[row.get("genome_id", "")].append(row)

    context: dict[str, str] = {}
    for genome_rows in by_genome.values():
        ordered = sorted_annotations(genome_rows)
        for index, row in enumerate(ordered):
            neighbors = ordered[max(0, index - 2):index] + ordered[index + 1:index + 3]
            labels = []
            has_tail_context = False
            for neighbor in neighbors:
                product = neighbor.get("product", "")
                module_hint = neighbor.get("module_hint", "")
                compact = f"{neighbor.get('gene_id', '')}:{module_hint}:{product}".strip(":")
                labels.append(compact)
                if TAIL_CONTEXT_PATTERN.search(" ".join([product, module_hint])):
                    has_tail_context = True
            prefix = "tail_context" if has_tail_context else "no_tail_context"
            context[row.get("annotation_gene_id", "")] = f"{prefix}|" + ";".join(labels) if labels else f"{prefix}|no_neighbors"
    return context


def candidate_evidence(
    row: dict[str, str],
    cluster_row: dict[str, str] | None,
    domains: list[dict[str, str]],
    structures: list[dict[str, str]],
    synteny_context: str,
    thresholds: dict[str, float | bool],
) -> dict[str, str] | None:
    text = row_text(row, cluster_row)
    d_hit = domain_hit(domains)
    s_hit = structural_hit(structures)
    seq_hit, seq_strength = sequence_hit(row, cluster_row)
    has_rbp_text = bool(RBP_PATTERN.search(text))
    has_depolymerase_text = bool(DEPOLYMERASE_PATTERN.search(text))
    has_domain_support = bool(d_hit and STRUCTURAL_SUPPORT_PATTERN.search(d_hit))
    has_structural_support = bool(s_hit and STRUCTURAL_SUPPORT_PATTERN.search(s_hit))
    module_hint_support = row.get("module_hint") == "rbp_depolymerase" or (cluster_row or {}).get("module_hint") == "rbp_depolymerase"
    has_tail_context = synteny_context.startswith("tail_context")
    protein_len = parse_int(row.get("protein_length_aa", ""), 0)
    min_len = int(float(thresholds["min_protein_length_aa"]))
    length_support = protein_len >= min_len if protein_len else False

    if EXCLUSION_PATTERN.search(row.get("product", "")) and not (has_domain_support or has_structural_support):
        return None

    is_candidate = any([has_rbp_text, has_depolymerase_text, has_domain_support, has_structural_support, module_hint_support])
    if not is_candidate:
        return None

    score = 0.0
    evidence_types: list[str] = []
    if has_rbp_text:
        score += 0.25
        evidence_types.append("rbp_keyword")
    if has_depolymerase_text:
        score += 0.25
        evidence_types.append("depolymerase_keyword")
    if module_hint_support:
        score += 0.20
        evidence_types.append("annotation_module_hint")
    if seq_strength == "strong_sequence_hit":
        score += 0.15
        evidence_types.append("sequence_hit")
    elif seq_strength == "weak_sequence_hit":
        score += 0.05
        evidence_types.append("weak_sequence_hit")
    if has_domain_support:
        score += 0.20
        evidence_types.append("domain_support")
    elif d_hit:
        score += 0.10
        evidence_types.append("domain_present")
    if has_structural_support:
        score += 0.25
        evidence_types.append("structural_support")
    elif s_hit:
        score += 0.10
        evidence_types.append("structural_hit")
    if has_tail_context:
        score += 0.10
        evidence_types.append("tail_synteny_context")
    if length_support:
        score += 0.05
        evidence_types.append("length_support")
    elif protein_len and protein_len < min_len:
        evidence_types.append("short_protein")

    score = min(score, 1.0)
    high_threshold = float(thresholds["high_confidence_score"])
    medium_threshold = float(thresholds["medium_confidence_score"])
    require_synteny = bool(thresholds["require_synteny_for_high_confidence"])
    high_conf = score >= high_threshold and (has_tail_context or not require_synteny)
    if high_conf:
        confidence_label = "high"
    elif score >= medium_threshold:
        confidence_label = "medium"
    else:
        confidence_label = "low"

    if seq_strength == "no_sequence_hit" and (has_domain_support or has_structural_support):
        novelty_tier = "tier_1"
        novelty_rationale = "no sequence-level hit but domain or structural support is present"
    elif seq_strength != "strong_sequence_hit" and (has_domain_support or has_structural_support or has_tail_context):
        novelty_tier = "tier_2"
        novelty_rationale = "weak sequence-level evidence with domain, structural, or synteny support"
    elif seq_strength == "strong_sequence_hit":
        novelty_tier = "tier_3"
        novelty_rationale = "known or sequence-clustered RBP/depolymerase family candidate"
    else:
        novelty_tier = "insufficient_novelty_evidence"
        novelty_rationale = "candidate is driven by annotation text without enough independent novelty evidence"

    combined = " ".join([text, d_hit, s_hit])
    return {
        "sequence_hit": seq_hit,
        "sequence_strength": seq_strength,
        "domain_hit": d_hit,
        "structural_hit": s_hit,
        "synteny_context": synteny_context,
        "predicted_enzyme_class": predicted_enzyme_class(text, d_hit, s_hit),
        "evidence_types": ";".join(evidence_types) if evidence_types else "none",
        "confidence_score": f"{score:.3f}",
        "confidence_label": confidence_label,
        "novelty_tier": novelty_tier,
        "novelty_rationale": novelty_rationale,
        "is_high_confidence": str(high_conf).lower(),
        "notes": "shorter than configured minimum length" if protein_len and protein_len < min_len else "OK",
    }


def build_candidates(
    annotations: list[dict[str, str]],
    gene_clusters: dict[str, dict[str, str]],
    domain_by_gene: dict[str, list[dict[str, str]]],
    structural_by_gene: dict[str, list[dict[str, str]]],
    thresholds: dict[str, float | bool],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    synteny_by_gene = build_synteny_context(annotations)
    candidates: list[dict[str, str]] = []
    architectures: list[dict[str, str]] = []

    for row in sorted_annotations(annotations):
        annotation_gene_id = row.get("annotation_gene_id", "")
        cluster_row = gene_clusters.get(row.get("gene_cluster_id", ""))
        domains = domain_by_gene.get(annotation_gene_id, [])
        structures = structural_by_gene.get(annotation_gene_id, [])
        synteny = synteny_by_gene.get(annotation_gene_id, "no_tail_context|not_available")
        evidence = candidate_evidence(row, cluster_row, domains, structures, synteny, thresholds)
        if evidence is None:
            continue

        candidate_id = f"rbp_candidate_{len(candidates) + 1:06d}"
        domain_arch, domain_count, domain_sources, best_domain = domain_architecture(domains)
        candidates.append(
            {
                "candidate_id": candidate_id,
                "genome_id": row.get("genome_id", ""),
                "record_type": row.get("record_type", ""),
                "species_cluster_id": row.get("species_cluster_id", ""),
                "representative_id": row.get("representative_id", ""),
                "gene_id": row.get("gene_id", ""),
                "annotation_gene_id": annotation_gene_id,
                "gene_cluster_id": row.get("gene_cluster_id", ""),
                "module_cluster_id": "",
                "product": row.get("product", ""),
                "protein_length_aa": row.get("protein_length_aa", ""),
                "sequence_hit": evidence["sequence_hit"],
                "domain_hit": evidence["domain_hit"],
                "structural_hit": evidence["structural_hit"],
                "synteny_context": evidence["synteny_context"],
                "predicted_enzyme_class": evidence["predicted_enzyme_class"],
                "evidence_types": evidence["evidence_types"],
                "confidence_score": evidence["confidence_score"],
                "confidence_label": evidence["confidence_label"],
                "novelty_tier": evidence["novelty_tier"],
                "novelty_rationale": evidence["novelty_rationale"],
                "is_high_confidence": evidence["is_high_confidence"],
                "notes": evidence["notes"],
            }
        )
        architectures.append(
            {
                "candidate_id": candidate_id,
                "annotation_gene_id": annotation_gene_id,
                "genome_id": row.get("genome_id", ""),
                "gene_id": row.get("gene_id", ""),
                "domain_architecture": domain_arch,
                "domain_count": domain_count,
                "domain_sources": domain_sources,
                "best_domain_hit": best_domain,
                "domain_support": "present" if domains else "absent",
                "notes": "OK" if domains else "no domain evidence supplied for candidate",
            }
        )
    return candidates, architectures


def build_module_clusters(candidates: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        key = row.get("gene_cluster_id") or row.get("predicted_enzyme_class") or row.get("candidate_id")
        grouped[key].append(row)

    module_rows: list[dict[str, str]] = []
    for index, key in enumerate(sorted(grouped), start=1):
        module_id = f"rbp_module_{index:06d}"
        members = sorted(grouped[key], key=lambda row: row["candidate_id"])
        genomes = sorted({row["genome_id"] for row in members})
        species_clusters = sorted({row["species_cluster_id"] for row in members if not is_missing(row["species_cluster_id"])})
        classes = sorted({row["predicted_enzyme_class"] for row in members if not is_missing(row["predicted_enzyme_class"])})
        evidence = sorted({item for row in members for item in row.get("evidence_types", "").split(";") if item})
        novelty = sorted({row["novelty_tier"] for row in members if not is_missing(row["novelty_tier"])})
        max_score = max(parse_float(row.get("confidence_score", "0")) for row in members)
        for row in members:
            row["module_cluster_id"] = module_id
        module_rows.append(
            {
                "module_cluster_id": module_id,
                "gene_cluster_id": key,
                "candidate_count": str(len(members)),
                "genome_count": str(len(genomes)),
                "species_cluster_count": str(len(species_clusters)),
                "representative_product": members[0].get("product", ""),
                "predicted_enzyme_classes": ";".join(classes),
                "evidence_types": ";".join(evidence),
                "max_confidence_score": f"{max_score:.3f}",
                "member_candidate_ids": ";".join(row["candidate_id"] for row in members),
                "member_genome_ids": ";".join(genomes),
                "member_species_cluster_ids": ";".join(species_clusters),
                "novelty_tiers": ";".join(novelty),
                "notes": "OK",
            }
        )
    return candidates, module_rows


def novel_subset(candidates: list[dict[str, str]], thresholds: dict[str, float | bool]) -> list[dict[str, str]]:
    medium = float(thresholds["medium_confidence_score"])
    selected = []
    for row in candidates:
        tier = row.get("novelty_tier", "")
        score = parse_float(row.get("confidence_score", "0"))
        if tier in {"tier_1", "tier_2"} and score >= medium:
            selected.append(row)
    return selected


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []

    try:
        thresholds = load_thresholds(Path(args.thresholds))
        add_report(
            report,
            "info",
            "thresholds",
            (
                "Using min_protein_length_aa={min_protein_length_aa:g}, "
                "medium_confidence_score={medium_confidence_score:g}, "
                "high_confidence_score={high_confidence_score:g}."
            ).format(**thresholds),
        )
        _, annotations = read_tsv(Path(args.annotations))
        gene_clusters = load_gene_clusters(Path(args.gene_clusters))
        add_report(report, "info", "annotations", f"Loaded {len(annotations)} annotations and {len(gene_clusters)} gene clusters.")
        domain_by_gene = load_evidence(args.domain_evidence, DOMAIN_REQUIRED_COLUMNS, "domain_evidence", report)
        structural_by_gene = load_evidence(args.structural_evidence, STRUCTURAL_REQUIRED_COLUMNS, "structural_evidence", report)

        candidates, architectures = build_candidates(annotations, gene_clusters, domain_by_gene, structural_by_gene, thresholds)
        candidates, module_clusters = build_module_clusters(candidates)
        novel_candidates = novel_subset(candidates, thresholds)

        add_report(
            report,
            "info",
            "rbp_depolymerase_candidates",
            f"Predicted {len(candidates)} candidates, {len(module_clusters)} module clusters, and {len(novel_candidates)} high-priority novel candidates.",
        )

        write_tsv(Path(args.candidates_output), CANDIDATE_COLUMNS, candidates)
        write_tsv(Path(args.domain_architectures_output), DOMAIN_ARCHITECTURE_COLUMNS, architectures)
        write_tsv(Path(args.module_clusters_output), MODULE_CLUSTER_COLUMNS, module_clusters)
        write_tsv(Path(args.novel_candidates_output), CANDIDATE_COLUMNS, novel_candidates)
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    except StageError:
        write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
        return 1

    error_count = sum(1 for row in report if row["severity"] == "error")
    print(
        f"Predicted {len(candidates)} RBP/depolymerase candidates across "
        f"{len(module_clusters)} module clusters; {len(novel_candidates)} prioritized as novel."
    )
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
