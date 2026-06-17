# Sequence Fetch Manifest Schema

`scripts/create_sequence_fetch_manifest.py` converts `results/qc/sequence_acquisition_plan.tsv` into a reviewable sequence-fetch manifest and a non-executing shell command script. `scripts/create_sequence_fetch_review_packet.py` then summarizes ready commands into a Markdown review packet. These scripts do not download genomes and do not modify `data/raw/`.

## Command

```bash
python scripts/create_sequence_fetch_manifest.py \
  --sequence-plan results/qc/sequence_acquisition_plan.tsv \
  --manifest-output results/qc/sequence_fetch_manifest.tsv \
  --commands-output results/qc/sequence_fetch_commands.sh \
  --report-output results/qc/sequence_fetch_report.tsv \
  --root .
```

The direct workflow runner executes this as `stage_1_sequence_fetch_manifest` after sequence acquisition planning. It then executes `stage_1_sequence_fetch_review_packet` when enabled.

## Manifest Output

Default path: `results/qc/sequence_fetch_manifest.tsv`.

| Column | Description |
| --- | --- |
| `command_id` | Stable command-row identifier. |
| `genome_id` | Genome identifier from the manifest. |
| `record_type` | Record type: phage, prophage, metagenomic viral contig, host, etc. |
| `accession` | Accession from the manifest. |
| `source` | Metadata source. |
| `acquisition_status` | Status from the sequence acquisition plan. |
| `retrieval_method` | Planned retrieval method. |
| `raw_sequence_path` | Raw sequence path from metadata. |
| `resolved_sequence_path` | Resolved local path when configured. |
| `expected_sequence_path` | Expected sequence path when accession-backed retrieval is possible. |
| `raw_sequence_exists` | Whether the local sequence already exists. |
| `command_class` | `fetch_command`, `manual_curation`, `already_local`, `excluded`, `manual_review`, or `not_needed`. |
| `command_text` | Fetch command for accession-backed rows only. |
| `requires_network` | Whether running the command would require network access. |
| `requires_manual_review` | Whether the row should be reviewed before production use. |
| `ready_to_run` | Whether a command is syntactically ready for manual execution. |
| `next_action` | Human-readable action. |
| `notes` | Source-plan notes. |

## Command Script

Default path: `results/qc/sequence_fetch_commands.sh`.

This script contains only ready accession-backed fetch commands. It is never executed by the workflow; it is a review artifact for the user or HPC/data-acquisition step.

## Production Use

Review the manifest, run selected commands outside the workflow when appropriate, place FASTA files at the expected paths, and rerun sequence QC. Rows requiring manual curation should be fixed in source manifests by adding an accession or `raw_sequence_path`.

## Review Packet

Default paths:

- `results/qc/sequence_fetch_review_packet.md`
- `results/qc/sequence_fetch_review_packet_report.tsv`

The review packet summarizes command classes, acquisition statuses, ready accession-backed fetch commands, and post-acquisition checks. It is a handoff artifact only; it does not execute commands and does not create FASTA files.
