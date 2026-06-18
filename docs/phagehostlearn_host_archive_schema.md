# PhageHostLearn Host Archive Audit Schema

`scripts/audit_phagehostlearn_host_archive.py` compares PhageHostLearn host source IDs in `data/metadata/source_exports/phagehostlearn_2024_hosts.tsv` with FASTA members in `data/metadata/external/phagehostlearn/klebsiella_genomes.zip`.

The audit supports manual host source-entity review. It does not approve source-to-canonical maps, import assay rows, infer K/O/ST calls, or support biological claims.

## Inputs

- `host_export`: reviewed or pending PhageHostLearn host source export.
- `archive`: local `klebsiella_genomes.zip` from Zenodo record `10.5281/zenodo.11061100`.

If the archive is absent, all host rows are emitted as `archive_missing` warnings so clean-checkout seed workflows remain runnable.

## Output Columns

| Column | Description |
| --- | --- |
| `source_id` | PhageHostLearn host source ID parsed from `notes` or `host_strain`. |
| `genome_id` | Canonical candidate host genome ID from the source export. |
| `host_strain` | Host strain label from the source export. |
| `archive_path` | Local archive path used for the audit. |
| `archive_present` | Whether the archive exists locally. |
| `member_present` | Whether a matching `fasta_files/<source_id>.fasta` member exists. |
| `member_path` | Matching ZIP member path, or `NA`. |
| `member_size_bytes` | Uncompressed ZIP member size, or `NA`. |
| `member_compressed_size_bytes` | Compressed ZIP member size, or `NA`. |
| `status` | `sequence_member_present`, `sequence_member_missing`, `archive_missing`, or an invalid/duplicate status. |
| `severity` | `info`, `warning`, or `error`. |
| `blocking_for_entity_review` | Whether the row still blocks source-entity review. |
| `notes` | Human-readable review note. |

## Validation

`self_test_phagehostlearn_host_archive.py` covers matched members, missing members, missing archive behavior, and duplicate FASTA basename rejection.
