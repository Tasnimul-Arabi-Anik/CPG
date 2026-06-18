# PhageHostLearn External File Manifest Schema

`data/metadata/external/phagehostlearn/phagehostlearn_file_manifest.tsv` records the expected local files for the PhageHostLearn benchmark source. The benchmark files are ignored by Git; this manifest preserves where they should be placed and how to verify them.

`scripts/validate_phagehostlearn_external_files.py` validates the manifest without downloading files. Missing files are warnings by default so mock and seed workflows can run from a clean checkout. If a file is present, size, MD5, and SHA-256 mismatches are blocking errors. Use `--require-present` when running a production/local benchmark review that requires all files.

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
| `expected_sha256` | Expected SHA-256 digest from local review. |
| `required_for` | Workflow layer that uses the file. |
| `notes` | Claim-boundary and curation notes. |

## Validation Output

`phagehostlearn_2024_external_files.tsv` contains one row per manifest file with observed file size/checksums when present and status values such as `local_file_missing`, `checksum_verified`, `size_mismatch`, `md5_mismatch`, or `sha256_mismatch`.

The companion report records summary counts and repeats the claim boundary: checksum verification supports benchmark-file provenance only; it does not approve assay rows or biological claims.

## Self-Test

`self_test_phagehostlearn_external_files.py` covers matching checksums, missing-file warnings, missing-file errors under `--require-present`, checksum mismatch, and invalid path rejection.
