# PhageHostLearn Metadata Support Audit Schema

`scripts/audit_phagehostlearn_metadata_support.py` audits whether the disabled PhageHostLearn benchmark matrix has accompanying small metadata support from Zenodo files such as `RBPbase.csv`, `Locibase.json`, and `Locibase_invitro.json`.

This is a curation/readiness audit only. It does not approve source-to-canonical ID maps, does not populate canonical assay rows, and does not treat RBPbase or Locibase presence as accepted receptor specificity, K/O typing, or productive infection evidence.

## Inputs

Default inputs are configured through `phagehostlearn_metadata_support` in `config/workflow.base.yaml`:

- `matrix`: PhageHostLearn host-by-phage interaction matrix.
- `rbpbase`: optional RBPbase CSV keyed by `phage_ID`.
- `locibase`: optional Locibase JSON keyed by host/source ID.
- `locibase_invitro`: optional in vitro Locibase JSON keyed by host/source ID.
- `phage_export` and `host_export`: disabled benchmark source exports.
- `phage_map` and `host_map`: source-to-canonical ID maps.

Missing RBPbase or Locibase files are reported as warnings so mock and seed workflows can run from a clean checkout without network access. Malformed provided files are blocking.

## `phagehostlearn_2024_metadata_support.tsv`

| Column | Description |
| --- | --- |
| `entity_type` | `phage` or `host`. |
| `source_id` | Source identifier from the benchmark matrix, exports, maps, RBPbase, or Locibase. |
| `canonical_id` | Candidate local canonical ID from the reviewed map or source export. |
| `matrix_present` | Whether the ID appears in the interaction matrix. |
| `matrix_tested_cells` | Number of explicit tested matrix cells for this ID. |
| `matrix_positive_cells` | Number of explicit positive cells for this ID. |
| `matrix_negative_cells` | Number of explicit tested-negative cells for this ID. |
| `source_export_present` | Whether the ID appears in the disabled source export. |
| `source_export_review_status` | Review status parsed from source export notes. |
| `id_map_present` | Whether the ID appears in the source-to-canonical map. |
| `id_map_review_status` | Review status of the map row. Pending rows are not accepted. |
| `rbpbase_rows` | Phage-only count of RBPbase rows for the source ID. |
| `rbpbase_protein_count` | Phage-only count of unique RBPbase protein IDs. |
| `locibase_entry_count` | Host-only count of Locibase entries. |
| `locibase_invitro_entry_count` | Host-only count of in vitro Locibase entries. |
| `metadata_support_status` | Curation status such as `matrix_input_missing`, `matrix_present_rbpbase_supported`, `matrix_present_no_rbpbase_support`, or `matrix_present_locibase_input_missing`. |
| `blocking_for_assay_import` | `true` when a matrix entity is still blocked by absent or unreviewed source-to-canonical mapping. |
| `notes` | Claim-boundary and curation notes. |

## `phagehostlearn_2024_metadata_support_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `item` | Input or summary item. |
| `message` | Counts, missing-file warnings, or claim-boundary note. |

## Validation

The fixture self-test is `scripts/self_test_phagehostlearn_metadata_support.py`. It covers RBPbase overlap, Locibase overlap, pending-map blocking, reviewed-map unblocking, missing optional metadata files, malformed Locibase JSON, and path-collision rejection.
