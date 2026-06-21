# Sequence Acquisition Plan Schema

`scripts/plan_sequence_acquisition.py` creates a local-only sequence acquisition checklist from the Stage 1 manifest. It does not download genomes, does not call NCBI, and does not modify `data/raw/`.

## Command

```bash
python scripts/plan_sequence_acquisition.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --raw-directory data/raw/genomes \
  --plan-output results/qc/sequence_acquisition_plan.tsv \
  --report-output results/qc/sequence_acquisition_report.tsv \
  --root .
```

The direct workflow runner executes this as `stage_1_sequence_acquisition` after `stage_1_manifest` and before `stage_1_sequence_qc`.

## Plan Output

Default path: `results/qc/sequence_acquisition_plan.tsv`.

| Column | Description |
| --- | --- |
| `genome_id` | Project genome identifier from the manifest. |
| `record_type` | `phage`, `prophage`, `metagenomic_viral_contig`, or `host`. |
| `accession` | Public accession string from the source manifest. |
| `source` | Source label from the manifest. |
| `validation_status` | Stage 1 manifest validation status. |
| `raw_sequence_path` | Curated local sequence path, if already supplied. |
| `resolved_sequence_path` | Root-resolved local sequence path. |
| `raw_sequence_exists` | Whether `raw_sequence_path` currently exists. For ZIP-member locators, this is true only when the archive exists and contains the requested safe member path. |
| `expected_sequence_path` | Suggested local FASTA path when an accession exists but no sequence path is set. |
| `acquisition_needed` | `true` when a record is not sequence-backed. |
| `acquisition_status` | Current sequence-acquisition state. |
| `retrieval_method` | Suggested retrieval route such as `ncbi_edirect_nuccore` or `ncbi_datasets_genome`. |
| `suggested_command` | Human-reviewable command hint. It is not executed by the workflow. |
| `notes` | Original notes plus planner guidance. |

## Status Values

| Status | Meaning |
| --- | --- |
| `local_sequence_available` | `raw_sequence_path` exists and can be checked by sequence QC, including reviewed ZIP-member locators whose archive and member are present. |
| `configured_path_missing_fetchable` | `raw_sequence_path` is set but missing, and an accession can be used to retrieve it. |
| `configured_path_missing_no_accession` | `raw_sequence_path` is set but missing, and no accession is available. |
| `accession_ready_for_fetch` | No local path is set, but an accession is available. |
| `metadata_only_no_accession` | Neither accession nor local path is available. |
| `excluded_manifest_record` | Stage 1 excluded this record, so no sequence acquisition is planned. |

## Production Use

For production analyses, phage-like and host records should move from `accession_ready_for_fetch` or `configured_path_missing_fetchable` to `local_sequence_available`, followed by a passing row in `results/qc/genome_sequence_qc.tsv`. The suggested commands are intentionally advisory because public database access and download tooling vary across local machines, HPC systems, and institutional networks.

## Related Fetch Manifest

After this plan is generated, `scripts/create_sequence_fetch_manifest.py` writes `results/qc/sequence_fetch_manifest.tsv` and a review-only `results/qc/sequence_fetch_commands.sh`. The workflow does not execute the commands automatically.
