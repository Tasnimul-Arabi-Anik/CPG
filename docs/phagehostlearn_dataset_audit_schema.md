# PhageHostLearn Dataset Audit Schema

`scripts/audit_phagehostlearn_dataset.py` is the source-specific adapter behind the generic `stage_0_assay_dataset_audit` workflow stage. The public runner surface stays generic, while this script preserves PhageHostLearn-specific checks for file integrity, matrix IDs, archive membership, canonical mappings, outcome parity, and seed feature metadata.

The audit separates readiness levels so valid observed assay outcomes can be preserved even when receptor, K/O/ST, or defense features are not yet production-ready.

## Readiness Levels

- `identity_ready`: source files, matrix IDs, source exports, archive membership, and canonical ID mappings.
- `assay_ready`: explicit tested spot-positive and spot-negative cells can be normalized/imported.
- `feature_ready`: optional RBPbase/Locibase metadata are available as seed support only.
- `model_ready`: H1/H3/H4-specific outcomes and features are sufficient for modeling.

K/O/ST, RBPbase, Locibase, host-defense, and counter-defense evidence must not block preservation of valid tested assay outcomes. They only affect feature/model readiness and claim strength.

## Output Columns

`phagehostlearn_2024_dataset_audit.tsv` contains:

| Column | Description |
| --- | --- |
| `check_id` | Stable audit check identifier. |
| `area` | Audit area such as `external_file_integrity`, `matrix_id_coverage`, `phage_archive_membership`, `host_archive_membership`, `canonical_id_mapping`, `feature_metadata_availability`, `assay_import_readiness`, `assay_matrix_export_parity`, or `model_feature_readiness`. |
| `readiness_level` | One of `identity_ready`, `assay_ready`, `feature_ready`, or `model_ready`. |
| `status` | Machine-readable status. |
| `severity` | `info`, `warning`, or `error`. |
| `blocking_for_assay_import` | `true` only when observed tested assay rows cannot safely be imported. |
| `evidence_path` | Input file(s) supporting the check. |
| `evidence_summary` | Compact count/status summary. |
| `next_action` | Concrete follow-up. |

The companion report contains `severity`, `item`, and `message`.

## Endpoint Semantics

For PhageHostLearn:

- blank matrix cell = untested;
- `0` = tested spot-negative;
- `1` = tested spot-positive;
- spot-positive = initial interaction only;
- `productive_infection_result` remains `not_measured`;
- H4 remains blocked until productive-infection, plaque, propagation, or EOP outcomes exist.

## Validation

`scripts/self_test_phagehostlearn_dataset.py` covers partial reviewed subsets, structural mapping blockers, header-only assay exports, and the real benchmark parity regression: 10,006 canonical rows, 333 spot-positive rows, 9,673 spot-negative rows, zero tested-false rows, zero productive-infection measurements, zero unresolved IDs, zero duplicate interaction IDs, and preserved blank untested matrix cells.
