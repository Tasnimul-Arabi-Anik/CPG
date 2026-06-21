# Sequence Acquisition Self-Test Schema

`scripts/self_test_sequence_acquisition.py` regression-tests `scripts/plan_sequence_acquisition.py` with temporary fixture files only. It verifies that reviewed ZIP-member locators formatted as `archive.zip::member.fasta` are treated as local sequence-backed inputs when the archive and member exist, while unsafe member paths are not treated as available sequence.

## Command

```bash
python scripts/self_test_sequence_acquisition.py \
  --output results/validation/sequence_acquisition_self_test.tsv \
  --report-output results/validation/sequence_acquisition_self_test_report.tsv
```

## `sequence_acquisition_self_test.tsv`

| Column | Description |
| --- | --- |
| `test_id` | Stable regression-test identifier. |
| `scenario` | Behavior under test. |
| `expected_status` | Expected result token. |
| `observed_status` | Observed result token. |
| `status` | `pass` or `fail`. |
| `notes` | Failure detail, or `NA` when passing. |

## `sequence_acquisition_self_test_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info` or `error`. |
| `item` | Report item. |
| `message` | Summary message with pass/fail counts. |
