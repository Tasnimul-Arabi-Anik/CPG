# PhageHostLearn External File Manifest Schema

`data/metadata/external/phagehostlearn/phagehostlearn_file_manifest.tsv` records the expected local files for the PhageHostLearn benchmark source. The benchmark files are ignored by Git; this manifest preserves where they should be placed and how to verify them.

`scripts/validate_phagehostlearn_external_files.py` validates the manifest without downloading files. Missing files are warnings by default so mock and seed workflows can run from a clean checkout. If a file is present, size and MD5 mismatches are blocking errors. SHA-256 is checked when `expected_sha256` is populated; rows with `expected_sha256=NA` become `sha256_pending_local_review` warnings after size and MD5 pass. Use `--require-present` when running a production/local benchmark review that requires all files, and `--require-sha256` when local SHA-256 review is mandatory.

## Manifest Columns

| Column | Description |
| --- | --- |
| `file_id` | Stable local file identifier. |
| `source_database` | Source database, e.g. `Zenodo`. |
| `source_record` | Source record or DOI. |
| `source_version` | Source snapshot/version date recorded for the manifest. |
| `retrieval_url` | Direct retrieval URL. |
| `retrieval_command` | Advisory local retrieval command; not executed by the workflow. |
| `expected_path` | Local expected path under `data/metadata/external/phagehostlearn/`. |
| `expected_size_bytes` | Expected byte count. |
| `expected_md5` | Expected MD5 digest from the source file record/local review. |
| `expected_sha256` | Expected SHA-256 digest from local review, or `NA` when a large file has source MD5/size recorded but local SHA-256 review is still pending. |
| `required_for` | Workflow layer that uses the file. |
| `notes` | Claim-boundary and curation notes. |

## Validation Output

`phagehostlearn_2024_external_files.tsv` contains one row per manifest file with observed file size/checksums when present and status values such as `local_file_missing`, `checksum_verified`, `size_mismatch`, `md5_mismatch`, or `sha256_mismatch`.

The companion report records summary counts and repeats the claim boundary: checksum verification supports benchmark-file provenance only; it does not approve assay rows or biological claims. The host genome archive is large and may remain `local_file_missing` or `sha256_pending_local_review` until a local reviewer downloads it and records the SHA-256. Its manifest command uses resumable `curl -C -` to a `.part` file and only moves that file to the final expected path after completion, because Zenodo downloads may be slow or interrupted.

## Self-Test

`self_test_phagehostlearn_external_files.py` covers matching checksums, missing-file warnings, missing-file errors under `--require-present`, checksum mismatch, and invalid path rejection.
