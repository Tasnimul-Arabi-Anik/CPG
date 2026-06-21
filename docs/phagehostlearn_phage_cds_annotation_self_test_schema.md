# PhageHostLearn Phage CDS Annotation Self-Test Schema

`scripts/self_test_phagehostlearn_phage_cds_annotations.py` validates the local PhageHostLearn phage CDS annotation builder without requiring Prodigal in CI. It uses a fake Prodigal executable and temporary ZIP fixtures.

## Outputs

### Self-test results

Columns:

| Column | Description |
| --- | --- |
| `test_id` | Stable self-test identifier. |
| `scenario` | Behavior under test. |
| `expected_status` | Expected outcome. |
| `observed_status` | Observed outcome. |
| `status` | `pass` or `fail`. |
| `notes` | Failure context or `NA`. |

### Self-test report

Columns:

| Column | Description |
| --- | --- |
| `severity` | `info` or `error`. |
| `item` | Report item. |
| `message` | Human-readable summary. |

## Coverage

The self-test checks:

- reviewed source-to-canonical phage mapping;
- archive-member extraction through a ZIP fixture;
- Prodigal protein FASTA parsing;
- input/output path collision rejection;
- transactional preservation of existing outputs when input validation fails.

The test does not validate biological CDS quality. It validates the import contract for sequence-backed baseline CDS prediction rows.
