# Defense External Evidence Normalization Self-Test Schema

`scripts/self_test_defense_external_evidence_normalization.py` runs fixture-only regression tests for `scripts/normalize_defense_external_evidence.py`, including alias normalization, anti-defense class inference, and independent output writing.

Implemented command:

```bash
python scripts/self_test_defense_external_evidence_normalization.py \
  --output results/validation/defense_external_evidence_normalization_self_test.tsv \
  --report-output results/validation/defense_external_evidence_normalization_self_test_report.tsv
```

## `defense_external_evidence_normalization_self_test.tsv`

| Column | Description |
| --- | --- |
| `test_id` | Stable regression-test identifier. |
| `scenario` | What behavior is being tested. |
| `expected_host_rows` | Expected normalized host-defense row count. |
| `observed_host_rows` | Observed normalized host-defense row count. |
| `expected_antidefense_rows` | Expected normalized phage anti-defense row count. |
| `observed_antidefense_rows` | Observed normalized phage anti-defense row count. |
| `expected_value` | Expected sentinel value for the scenario. |
| `observed_value` | Observed sentinel value. |
| `status` | `pass` or `fail`. |
| `notes` | Failure reason or `NA`. |

## `defense_external_evidence_normalization_self_test_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info` or `error`. |
| `item` | Report item. |
| `message` | Summary test counts or failure message. |
