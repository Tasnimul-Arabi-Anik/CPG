# Sequence Acquisition Manifest Schema

`data/metadata/sequence_acquisition_manifest.tsv` is the reviewed, checksum-backed record of raw FASTA acquisition for sequence-backed seed or production records. Raw FASTA files remain untracked under `data/raw/`, but this manifest records how to reconstruct and verify them.

The mock workflow uses `data/metadata/mock_sequence_acquisition_manifest.tsv`, which points only to tracked fixture FASTA files under `data/raw/mock_public/`. The seed workflow uses `data/metadata/seed_sequence_acquisition_manifest.tsv`, which preserves acquisition provenance as manual-review rows so a clean checkout can run seed metadata/bridge validation without ignored raw FASTA files. The production profile uses `data/metadata/sequence_acquisition_manifest.tsv` for checksum-enforced local raw-file verification.

## Command

```bash
python scripts/validate_sequence_acquisition_manifest.py \
  --manifest data/metadata/sequence_acquisition_manifest.tsv \
  --validation-output results/validation/sequence_acquisition_manifest_validation.tsv \
  --report-output results/validation/sequence_acquisition_manifest_validation_report.tsv \
  --root .
```

The direct workflow runner executes this as `stage_1_sequence_acquisition_manifest_validation` when `sequence_acquisition_manifest.enabled: true`.

## Manifest Columns

| Column | Description |
| --- | --- |
| `entity_id` | Project entity or genome identifier. Must be unique. |
| `accession` | Public accession or accession range used to retrieve the sequence. |
| `database` | Source database or accession authority. |
| `source_version` | Source snapshot, accession version, or reviewed retrieval context. |
| `retrieval_command` | Human-reviewable command or procedure used to reconstruct the file. It is not executed by the workflow. |
| `retrieved_at` | Retrieval or review date in `YYYY-MM-DD` format. |
| `expected_path` | Local raw FASTA path, which must be under `data/raw/`. |
| `file_size` | Expected byte count for reviewed local files. May be `NA` for pending rows. |
| `sha256` | Expected SHA-256 digest for reviewed local files. May be `NA` for pending rows. |
| `review_status` | `reviewed_local_file`, `checksum_verified`, `pending_retrieval`, `pending_checksum`, or `manual_review_required`. |
| `notes` | Provenance and review notes. |

## Validation Output

Default path: `results/validation/sequence_acquisition_manifest_validation.tsv`.

| Column | Description |
| --- | --- |
| `entity_id` | Entity from the acquisition manifest. |
| `accession` | Public accession or accession range. |
| `expected_path` | Local raw path from the manifest. |
| `review_status` | Review status from the manifest. |
| `path_exists` | Whether the expected path exists in the current checkout. |
| `expected_file_size` | File size recorded in the manifest. |
| `observed_file_size` | Local file size observed during validation. |
| `expected_sha256` | SHA-256 digest recorded in the manifest. |
| `observed_sha256` | Local SHA-256 digest observed during validation. |
| `status` | Row validation status, such as `checksum_verified`, `pending_retrieval`, or `sha256_mismatch`. |
| `severity` | `info`, `warning`, or `error`. |
| `message` | Human-readable validation message. |

Reviewed local files must exist and match both `file_size` and `sha256`. Pending rows may lack checksum fields but remain warnings, not production-ready evidence.

## Self-Test

```bash
python scripts/self_test_sequence_acquisition_manifest.py \
  --output results/validation/sequence_acquisition_manifest_self_test.tsv \
  --report-output results/validation/sequence_acquisition_manifest_self_test_report.tsv
```

The self-test uses temporary files and covers checksum success, checksum mismatch, missing reviewed files, pending retrieval rows, and path enforcement under `data/raw/`.
