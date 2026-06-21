# PhageHostLearn Host Typing Evidence Self-Test Schema

`scripts/self_test_phagehostlearn_host_typing_evidence.py` regression-tests `scripts/build_phagehostlearn_host_typing_evidence.py` with temporary fixture files only. It does not use project biological data.

Implemented command:

```bash
python scripts/self_test_phagehostlearn_host_typing_evidence.py \
  --output results/validation/phagehostlearn_host_typing_evidence_self_test.tsv \
  --report-output results/validation/phagehostlearn_host_typing_evidence_self_test_report.tsv
```

## Coverage

The fixture suite checks:

- reviewed source-to-canonical host ID mapping;
- Kaptive K/O row normalization, including untypeable confidence retention;
- Kleborate host-feature normalization with missing-row reporting;
- input/output path-collision rejection;
- malformed-input failure without replacing existing evidence outputs.

## `phagehostlearn_host_typing_evidence_self_test.tsv`

| Column | Description |
| --- | --- |
| `test_id` | Stable regression-test identifier. |
| `scenario` | Behavior being tested. |
| `expected_status` | Expected scenario outcome. |
| `observed_status` | Observed scenario outcome. |
| `status` | `pass` or `fail`. |
| `notes` | Failure reason or `NA`. |

## `phagehostlearn_host_typing_evidence_self_test_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info` or `error`. |
| `item` | Report item. |
| `message` | Summary test counts or failure message. |

This self-test validates host-typing evidence normalization mechanics only. It does not validate real K/O/ST biological interpretation or support receptor-compatibility claims without matching phage RBP/depolymerase evidence.
