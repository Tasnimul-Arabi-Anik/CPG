# RBP External Evidence Normalization Self-Test Schema

`scripts/self_test_rbp_external_evidence_normalization.py` regression-tests the RBP external evidence normalizer with temporary fixture files only. It does not use project biological data.

## Coverage

The fixture suite checks:

- generic domain TSV normalization with type-specific provenance columns;
- row-level provenance precedence over CLI provenance;
- HMMER `domtblout` parsing for `hmmsearch` orientation;
- HMMER `domtblout` parsing for `hmmscan` orientation;
- headerless Foldseek TSV parsing with explicit field order;
- headered Phold-style TSV parsing;
- duplicate domain-hit reporting and de-duplication;
- annotation-manifest referential-integrity failures;
- canonical `protein_id` alias translation to `annotation_gene_id`;
- ambiguous identifier mapping failures;
- invalid domain-coordinate ordering and non-integer coordinate failures;
- invalid structural-score and non-finite numeric failures;
- preservation of existing outputs when an evidence input is absent and `--overwrite-empty` is not set;
- transactional no-partial-write behavior when one evidence type is malformed;
- domain/structural distinct provenance in one invocation;
- input/output path collision failures;
- explicit `--overwrite-empty` replacement behavior;
- full successful and failing command-path exit codes.

## Outputs

- `results/validation/rbp_external_evidence_normalization_self_test.tsv`
- `results/validation/rbp_external_evidence_normalization_self_test_report.tsv`

## `rbp_external_evidence_normalization_self_test.tsv`

| Column | Description |
| --- | --- |
| `test_id` | Stable test identifier. |
| `scenario` | Test scenario description. |
| `expected_domain_rows` | Expected normalized domain row count, or `NA` for error-only tests. |
| `observed_domain_rows` | Observed normalized domain row count, or `NA` for error-only tests. |
| `expected_structural_rows` | Expected normalized structural row count, or `NA` for error-only tests. |
| `observed_structural_rows` | Observed normalized structural row count, or `NA` for error-only tests. |
| `expected_value` | Expected sentinel value or error-message fragment. |
| `observed_value` | Observed sentinel value or error message. |
| `status` | `pass` or `fail`. |
| `notes` | Mismatch notes or `NA`. |

## `rbp_external_evidence_normalization_self_test_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `item` | Report item. |
| `message` | Test count and pass/fail summary. |
