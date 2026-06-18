# PhageHostLearn Map Review Audit Schema

`scripts/audit_phagehostlearn_map_review.py` audits whether PhageHostLearn source-to-canonical ID maps are ready for manual review. It consumes the metadata-support audit, disabled benchmark source exports, and map TSVs.

This audit does not approve mappings and does not edit map files. It reports whether each row is structurally valid, still blocked by pending source-entity review, waiting for the local matrix input, or already usable by `scripts/normalize_assay_matrix.py`.

## Inputs

Default inputs are configured through `phagehostlearn_map_review` in `config/workflow.base.yaml`:

- `metadata_support`: `phagehostlearn_2024_metadata_support.tsv` from `stage_0_phagehostlearn_metadata_support`.
- `phage_export` and `host_export`: disabled benchmark source exports.
- `phage_map` and `host_map`: source-to-canonical ID maps used by `normalize_assay_matrix.py`.

## `phagehostlearn_2024_map_review.tsv`

| Column | Description |
| --- | --- |
| `entity_type` | `phage` or `host`. |
| `source_id` | Source identifier from the PhageHostLearn matrix/map. |
| `canonical_id` | Candidate canonical local ID from the map row. |
| `map_review_status` | Current map-row review status. Only `reviewed`, `accepted`, or `approved` are accepted by the matrix normalizer. |
| `source_export_present` | Whether a matching source export entity row exists. |
| `source_export_review_status` | Review status parsed from source export notes. |
| `canonical_matches_export` | Whether the map canonical ID matches the source export genome ID. |
| `metadata_support_present` | Whether the metadata-support audit has a row for this entity. |
| `matrix_present` | Whether the entity appears in the local matrix audit. |
| `metadata_support_status` | Support status from the metadata-support audit. |
| `structural_status` | High-level audit state such as `structurally_valid`, `reviewed`, `waiting_matrix`, or `invalid`. |
| `review_recommendation` | Exact review recommendation, for example `pending_entity_review`, `ready_for_manual_map_review`, or `reviewed_ready_for_assay_normalization`. |
| `blocking_for_assay_import` | Whether this row still blocks assay-matrix import. |
| `required_action` | Next manual action. |
| `notes` | Supporting detail. |

## `phagehostlearn_2024_map_review_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `item` | Summary or input item. |
| `message` | Recommendation counts and claim-boundary notes. |

## Validation

The fixture self-test is `scripts/self_test_phagehostlearn_map_review.py`. It covers pending source-entity review, manually reviewable rows, reviewed-ready rows, canonical mismatches, missing matrix input, and path-collision rejection.
