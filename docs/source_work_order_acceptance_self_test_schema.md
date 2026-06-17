# Source Work-Order Acceptance Self-Test Schema

`scripts/self_test_source_work_order_acceptance.py` creates temporary source work-order exports and verifies that `scripts/check_source_work_order_acceptance.py` accepts complete reviewed rows while surfacing raw sequence path and provenance lint warnings.

The self-test uses temporary files only. It does not create real study rows and does not modify `data/raw/`.

## Command

```bash
python scripts/self_test_source_work_order_acceptance.py \
  --output results/validation/source_work_order_acceptance_self_test.tsv \
  --report-output results/validation/source_work_order_acceptance_self_test_report.tsv
```

## `results/validation/source_work_order_acceptance_self_test.tsv`

| Column | Description |
| --- | --- |
| `test_id` | Regression scenario identifier. |
| `scenario` | Human-readable scenario description. |
| `expected_acceptance_status` | Expected source work-order acceptance status. |
| `observed_acceptance_status` | Observed acceptance status. |
| `expected_blocking` | Expected `blocking_issue` value. |
| `observed_blocking` | Observed `blocking_issue` value. |
| `expected_issue_contains` | Expected substring in lint issue columns, or `NA`. |
| `observed_raw_sequence_path_issues` | Raw sequence path lint issues reported by the acceptance checker. |
| `observed_provenance_note_issues` | Provenance note lint issues reported by the acceptance checker. |
| `status` | `pass` or `fail`. |
| `notes` | Failure notes, or `NA`. |

## `results/validation/source_work_order_acceptance_self_test_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info` or `error`. |
| `item` | Report item name. |
| `message` | Test count summary. |

## Interpretation

This self-test proves the acceptance checker preserves curation gates and lint reporting. It does not validate any real Klebsiella phage record.
