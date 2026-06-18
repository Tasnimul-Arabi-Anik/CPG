# Phage-Host Assay and Relationship Schemas

This repository separates non-assay phage-host relationships from tested phage-host outcomes.

`data/metadata/phage_host_relationships.tsv` records biological or metadata relationships such as isolation host, reported host, prophage resident host, predicted host, or a host included in an assay panel. These relationships are useful for provenance and candidate prioritization, but they are not infection labels.

`data/metadata/phage_host_assays.tsv` records experimentally tested phage-host pairs. This table is the required response-variable source for pairwise host-range prediction, broad-host-range estimates, and defense/counter-defense compatibility tests.

## Assay Table

Path:

```text
data/metadata/phage_host_assays.tsv
```

Required columns:

| Column | Description |
| --- | --- |
| `interaction_id` | Stable row identifier for the tested phage-host interaction. |
| `phage_id` | Canonical phage genome identifier. Must resolve to a phage manifest row for populated records. |
| `host_id` | Canonical host genome identifier. Must resolve to a host metadata or host manifest row for populated records. |
| `study_id` | Study, dataset, or source panel identifier. Required for populated records. |
| `panel_id` | Host-panel identifier when available. Use `NA` if unknown. |
| `assay_type` | Assay class such as `adsorption`, `spot`, `plaque`, `eop`, `growth_inhibition`, `productive_infection`, or `mixed_panel`. |
| `tested` | `true` or `false`. Untested pairs must not be encoded as negative results. |
| `adsorption_result` | `positive`, `negative`, `inconclusive`, `not_measured`, or `NA`. |
| `spot_result` | `positive`, `negative`, `inconclusive`, `not_measured`, or `NA`. |
| `plaque_result` | `positive`, `negative`, `inconclusive`, `not_measured`, or `NA`. |
| `productive_infection_result` | `positive`, `negative`, `inconclusive`, `not_measured`, or `NA`. Productive infection cannot be inferred from spot clearing alone. |
| `eop` | Efficiency of plating. Numeric and non-negative if populated. |
| `eop_reference_host` | Reference host for EOP normalization when `eop` is populated. |
| `growth_inhibition_result` | `positive`, `negative`, `inconclusive`, `not_measured`, or `NA`. |
| `moi` | Multiplicity of infection when available. Numeric and non-negative if populated. |
| `temperature_c` | Assay temperature in Celsius when available. Numeric if populated. |
| `medium` | Assay medium or `NA`. |
| `replicate_count` | Positive integer when available. |
| `outcome_tier` | Interpreted outcome tier, for example `initial_interaction`, `productive_infection_confirmed`, `tested_negative`, `mixed`, `not_tested`, or `unknown`. |
| `evidence_tier` | Evidence tier such as `curated_assay`, `supplementary_matrix`, `literature_table`, or `metadata_only`. Pairwise modeling should require assay evidence tiers. |
| `reference` | Publication, accession, DOI, dataset version, or local reviewed source. Required for populated records. |
| `notes` | Free-text provenance, uncertainty, and curation notes. |

Validation rules:

- Header-only assay tables are schema-valid but do not support H1b, H3, or H4.
- `untested` is not a negative result.
- Negative assay results require `tested=true`.
- Productive infection requires plaque, EOP, direct productive-infection evidence, or an explicitly curated productive-infection outcome tier. Spot clearing alone is insufficient.
- EOP must be numeric and non-negative.
- Populated rows require `interaction_id`, `phage_id`, `host_id`, `study_id`, `assay_type`, `tested`, `evidence_tier`, and `reference`.
- Duplicate `interaction_id` values and duplicate study/panel/phage/host/assay records are blocking.

## Relationship Table

Path:

```text
data/metadata/phage_host_relationships.tsv
```

Required columns:

| Column | Description |
| --- | --- |
| `relationship_id` | Stable relationship row identifier. |
| `phage_id` | Canonical phage genome identifier. |
| `host_id` | Canonical host genome identifier. |
| `relationship_type` | One of `isolation_host`, `reported_host`, `prophage_resident_host`, `predicted_host`, or `tested_assay_host`. |
| `relationship_status` | Curation status such as `reviewed`, `inferred`, `predicted`, `unresolved`, or `deprecated`. |
| `relationship_evidence` | Evidence source or rule used to define the relationship. |
| `source_reference` | Publication, accession, dataset, or local reviewed source. |
| `confidence` | Optional `high`, `medium`, `low`, or numeric value from 0 to 1. |
| `notes` | Free-text provenance and uncertainty. |

Relationship rows must not be used as infection outcomes unless a matching row exists in `phage_host_assays.tsv`.
