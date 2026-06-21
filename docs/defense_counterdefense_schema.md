# Defense and Counter-Defense Schema

Stage 6 integrates host antiviral defense systems with phage anti-defense candidates and writes compatibility features for downstream receptor-plus-defense modeling.

## Inputs

Primary inputs:
- `results/host_features/host_metadata.tsv`
- `results/host_features/phage_host_links.tsv`
- `results/annotations/phage_annotations.tsv`

Optional host defense input:
- PADLOC/DefenseFinder-style TSV with a host identifier column such as `sample`, `genome_id`, or `host_genome_id`.
- Recommended columns: `system`, `type`, `subtype`, `gene_count`, `genes`, `contig`, `start`, `end`, `tool`, and `confidence`.

Optional phage anti-defense input:
- TSV with `phage_genome_id` or `annotation_gene_id`.
- Recommended columns: `gene_id`, `gene_cluster_id`, `product`, `antidefense_class`, `target_defense_system`, `evidence_type`, `evidence_source`, and `confidence_score`.

## Outputs

### `results/defense_systems/host_defense_systems.tsv`

One row per normalized host defense system. Important columns:

| Column | Description |
| --- | --- |
| `host_genome_id` | Host genome identifier linked to Stage 5 host metadata. |
| `defense_system` | Tool-reported defense system name. |
| `defense_type` | Normalized defense class, for example CRISPR-Cas, restriction-modification, BREX, DISARM, Abi, toxin-antitoxin, retrons, or nuclease-based defense. |
| `genes` | Semicolon-delimited genes/proteins when supplied. |
| `evidence_source` | Tool or file source. |
| `confidence` | Tool score or confidence when supplied. |

### `results/defense_systems/phage_antidefense_candidates.tsv`

One row per explicit or screening-level phage anti-defense candidate. Rows marked `evidence_type=annotation_keyword_inference` are annotation-keyword screening hits only. They are written for review and prioritization, but they are not accepted counter-defense evidence and are excluded from compatibility matching unless the same candidate is supplied through an explicit reviewed anti-defense table.

### `results/defense_systems/compatibility_features.tsv`

One row per phage-host link with receptor metadata, host defense summaries, phage counter-defense summaries, and matched target counts.

Important columns:

| Column | Description |
| --- | --- |
| `phage_genome_id` | Phage/prophage/metagenomic viral record. |
| `host_genome_id` | Linked host genome or metadata placeholder. |
| `K_type`, `O_type`, `ST` | Receptor and host background features from Stage 5. |
| `host_defense_system_count` | Number of host defense systems linked to the host. |
| `host_defense_types` | Semicolon-delimited normalized host defense classes. |
| `phage_antidefense_count` | Number of accepted explicit phage anti-defense candidates linked to the phage for compatibility matching. Annotation-keyword screening rows are excluded. |
| `phage_antidefense_targets` | Semicolon-delimited defense systems targeted by accepted explicit phage candidates. |
| `matched_counterdefense_count` | Number of accepted explicit phage target classes matching host defense classes/systems. |
| `compatibility_feature_status` | Missingness/status flag for downstream modeling. |

### `results/defense_systems/defense_counterdefense_report.tsv`

Run-level validation and provenance messages.

## Current Behavior

This stage does not run PADLOC, DefenseFinder, or anti-defense databases directly. It normalizes their tabular outputs when supplied. Annotation-keyword phage hits are screening-only review candidates; they remain in `phage_antidefense_candidates.tsv` but are excluded from `compatibility_features.tsv` counter-defense counts, target matching, and compatibility statuses unless explicit reviewed evidence is supplied.
