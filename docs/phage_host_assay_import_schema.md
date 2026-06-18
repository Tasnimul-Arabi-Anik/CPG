# Phage-host assay import schema

The assay import layer converts reviewed phage-host interaction exports into canonical profile-local assay and relationship tables. It is intended for benchmark or literature-derived tested interaction matrices, including sources with both positive and tested-negative pairs.

The importer does not download data and does not infer untested pairs as negatives. Header-only exports are valid for seed/mock workflow plumbing but cannot support H1/H3/H4 biological claims.

## Config

`config/assay_imports.yaml` contains an `imports` list. Each enabled import may define:

- `import_id`: stable source import identifier.
- `enabled`: whether to process the source.
- `input_path`: reviewed assay source export TSV or CSV.
- `delimiter`: `tab`, `comma`, or `auto`.
- `derive_relationships`: whether to emit `tested_assay_host` relationships from assay rows.
- `*_default`: conservative defaults for non-biological or source-level fields such as `study_id_default`, `panel_id_default`, `assay_type_default`, `evidence_tier_default`, `reference_default`, and `outcome_tier_default`.
- `column_map`: optional explicit mapping from canonical assay columns to source export columns.

Mock CI uses `config/assay_imports.mock.yaml`.

## Source Export

A reviewed source export should use the canonical assay columns whenever possible:

```text
interaction_id, phage_id, host_id, study_id, panel_id, assay_type, tested, adsorption_result, spot_result, plaque_result, productive_infection_result, eop, eop_reference_host, growth_inhibition_result, moi, temperature_c, medium, replicate_count, outcome_tier, evidence_tier, reference, notes
```

Required populated-row fields after import normalization are:

- `interaction_id`
- `phage_id`
- `host_id`
- `study_id`
- `assay_type`
- `tested`
- `evidence_tier`
- `reference`

`interaction_id` may be deterministically generated from study/panel/phage/host/assay fields when absent. This is a technical identifier and not biological evidence.

## Outputs

`stage_0_assay_imports` writes profile-local outputs:

- `results/<profile>/metadata/phage_host_assays.tsv`
- `results/<profile>/metadata/phage_host_relationships.tsv`
- `results/<profile>/qc/assay_import_report.tsv`

The import is transactional: malformed enabled inputs produce an error report and do not rewrite canonical assay outputs. Input paths may not collide with output paths.

## Self-test

`stage_9_phage_host_assay_import_self_test` writes:

- `results/<profile>/validation/phage_host_assay_import_self_test.tsv`
- `results/<profile>/validation/phage_host_assay_import_self_test_report.tsv`

The self-test covers header-only imports, populated assay imports, derived `tested_assay_host` relationships, malformed input blocking, output preservation on failure, and path-collision rejection.

## Claim Boundary

A passing import proves only that reviewed source rows can be normalized. Host-range breadth, productive infection, defense/counter-defense compatibility, and prediction claims require populated validated assay rows plus downstream model support.
