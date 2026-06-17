# External Evidence Acceptance Self-Test Schema

`scripts/self_test_external_evidence_acceptance.py` creates temporary evidence-plan and evidence-TSV fixtures, then verifies that `scripts/check_external_evidence_acceptance.py` preserves the production evidence gate.

Default outputs:

- `results/validation/external_evidence_acceptance_self_test.tsv`
- `results/validation/external_evidence_acceptance_self_test_report.tsv`

## `external_evidence_acceptance_self_test.tsv`

| Column | Description |
| --- | --- |
| `test_id` | Stable self-test case identifier. |
| `scenario` | Scenario being tested. |
| `expected_acceptance_status` | Expected acceptance status. |
| `observed_acceptance_status` | Observed acceptance status. |
| `expected_blocking` | Expected blocking flag. |
| `observed_blocking` | Observed blocking flag. |
| `expected_lint_contains` | Expected substring in provenance lint, or `NA`. |
| `observed_provenance_lint` | Observed provenance lint string. |
| `status` | `pass` or `fail`. |
| `notes` | Failure notes or `NA`. |

## `external_evidence_acceptance_self_test_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info` or `error`. |
| `item` | Report item. |
| `message` | Summary count of passing and failing self-test cases. |

## Covered Cases

The self-test covers:

- configured evidence accepted with complete provenance;
- configured evidence accepted with provenance lint;
- schema-invalid configured evidence remaining blocking;
- missing production tool/input remaining blocking.

This self-test validates the acceptance gate logic only. It does not validate real external evidence or support biological claims.
