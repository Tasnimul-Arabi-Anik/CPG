# RBP External Evidence Normalization Self-Test Schema

`scripts/self_test_rbp_external_evidence_normalization.py` regression-tests the RBP external evidence normalizer with temporary fixture files only. It does not use project biological data.

## Outputs

- `results/validation/rbp_external_evidence_normalization_self_test.tsv`
- `results/validation/rbp_external_evidence_normalization_self_test_report.tsv`

## `rbp_external_evidence_normalization_self_test.tsv`

| Column | Description |
| --- | --- |
| `test_id` | Stable test identifier. |
| `scenario` | Test scenario description. |
| `expected_domain_rows` | Expected normalized domain row count. |
| `observed_domain_rows` | Observed normalized domain row count. |
| `expected_structural_rows` | Expected normalized structural row count. |
| `observed_structural_rows` | Observed normalized structural row count. |
| `expected_value` | Expected sentinel value. |
| `observed_value` | Observed sentinel value. |
| `status` | `pass` or `fail`. |
| `notes` | Mismatch notes or `NA`. |

## `rbp_external_evidence_normalization_self_test_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `item` | Report item. |
| `message` | Test count and pass/fail summary. |
