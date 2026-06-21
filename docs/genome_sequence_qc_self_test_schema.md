# Genome Sequence QC Self-Test Schema

`scripts/self_test_genome_sequence_qc.py` verifies the generic sequence QC contract, including local ZIP-member FASTA locators of the form:

```text
archive.zip::path/inside/archive.fasta
```

The self-test does not download data and does not write to `data/raw/`.

## Outputs

### Self-test results

| Column | Description |
| --- | --- |
| `test_id` | Stable self-test identifier. |
| `scenario` | Behavior under test. |
| `expected_status` | Expected outcome. |
| `observed_status` | Observed outcome. |
| `status` | `pass` or `fail`. |
| `notes` | Failure details or `NA`. |

### Self-test report

| Column | Description |
| --- | --- |
| `severity` | `info` or `error`. |
| `item` | Report item. |
| `message` | Summary message. |

## Covered Behaviors

- ZIP-member FASTA records can pass sequence QC when the archive and member exist.
- The resolved sequence path records both archive and member.
- Archive member path traversal such as `../bad.fasta` is rejected.
