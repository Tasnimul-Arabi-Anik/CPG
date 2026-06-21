# BLASTN Pairwise Similarity Self-Test Schema

`scripts/self_test_blastn_pairwise_similarity.py` verifies that `scripts/build_blastn_pairwise_similarity.py` can materialize reviewed ZIP-member FASTA paths into a temporary workspace before running BLASTN-like commands. The self-test uses a fake BLASTN executable, so CI does not require BLAST+.

## Outputs

### `results/validation/blastn_pairwise_similarity_self_test.tsv`

| Column | Description |
| --- | --- |
| `test_id` | Stable regression-test identifier. |
| `scenario` | Scenario being tested. |
| `expected_status` | Expected result. |
| `observed_status` | Observed result. |
| `status` | `pass` or `fail`. |
| `notes` | Failure details or `NA`. |

### `results/validation/blastn_pairwise_similarity_self_test_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info` or `error`. |
| `item` | Report item. |
| `message` | Summary of test counts or failure state. |
