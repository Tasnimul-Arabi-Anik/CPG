# Host Defense Run Handoff Schema

`scripts/create_host_defense_run_handoff.py` creates a reviewer-facing run manifest for host antiviral defense-system annotation tools such as DefenseFinder and PADLOC.

This handoff does not run external tools and does not infer host defense systems. It records reviewed local host FASTA paths and suggested commands. Accepted host defense evidence must still be produced as a reviewed TSV and configured through `inputs.host_defense_input`.

## Outputs

- `results/qc/host_defense_run_handoff.tsv`
- `results/qc/host_defense_run_commands.sh`
- `results/qc/host_defense_run_handoff_report.tsv`

## `host_defense_run_handoff.tsv`

| Column | Description |
| --- | --- |
| `host_genome_id` | Host genome identifier from Stage 5 host metadata. |
| `host_species` | Host species label when curated. |
| `host_strain` | Host strain label when curated. |
| `accession` | Source accession from the sequence acquisition plan. |
| `raw_sequence_path` | Reviewed local FASTA path used for external tools. |
| `raw_sequence_exists` | Whether the local FASTA exists at workflow time. |
| `defensefinder_command` | Suggested DefenseFinder command for this host FASTA. |
| `padloc_command` | Suggested PADLOC command for this host FASTA. |
| `output_tsv_target` | Expected reviewed TSV target for normalized host defense evidence. |
| `run_status` | `ready_for_external_tool_run` or `waiting_for_reviewed_local_fasta`. |
| `notes` | Claim-boundary and provenance note. |

## `host_defense_run_handoff_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `item` | Report item. |
| `message` | Summary of host genomes and run-ready FASTA records. |
