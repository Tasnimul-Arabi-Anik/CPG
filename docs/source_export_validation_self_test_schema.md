# Source Export Validation Self-Test Schema

`scripts/self_test_source_export_validation.py` creates temporary reviewed-export TSVs and verifies that `scripts/validate_source_exports.py` accepts well-formed rows and blocks malformed curated rows before import.

## Command

```bash
python scripts/self_test_source_export_validation.py \
  --output results/validation/source_export_validation_self_test.tsv \
  --report-output results/validation/source_export_validation_self_test_report.tsv
```

The config-driven workflow runs this as `stage_9_source_export_validation_self_test` before `stage_9_validation`.

## Test Output

Default path: `results/validation/source_export_validation_self_test.tsv`.

| Column | Description |
| --- | --- |
| `test_id` | Stable self-test scenario identifier. |
| `scenario` | Behavior being tested. |
| `expected_status` | Expected `validation_status` from the reviewed export validator. |
| `observed_status` | Observed `validation_status`. |
| `expected_blocking` | Expected `blocking_issue` value. |
| `observed_blocking` | Observed `blocking_issue` value. |
| `expected_issue_contains` | Expected issue substring, or `NA`. |
| `observed_issues` | Observed row-format, duplicate-identity, or provenance warning details. |
| `status` | `pass` or `fail` for the scenario. |
| `notes` | Mismatch notes, or `NA`. |

## Report Output

Default path: `results/validation/source_export_validation_self_test_report.tsv`.

Columns: `severity`, `item`, and `message`.

## Scenarios

The self-test covers:

- well-formed populated export rows;
- malformed year values;
- out-of-range GC percentages;
- unsupported phage lifestyle labels;
- rows missing all identity values;
- missing notes/provenance warnings that should not block import by themselves.

## Interpretation

This is a validator regression test, not biological evidence. It proves that malformed reviewed source exports are caught before source import and before downstream H1-H6 support checks can treat those rows as usable data.
