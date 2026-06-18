# External Evidence Run Packet Schema

`scripts/create_external_evidence_run_packets.py` renders one Markdown handoff packet per external evidence layer from `results/qc/external_evidence_plan.tsv` and `results/qc/external_evidence_template_manifest.tsv`.

Default outputs:

- `results/qc/external_evidence_run_packet_manifest.tsv`
- `results/qc/external_evidence_run_packet_report.tsv`
- `results/qc/external_evidence_run_packets/README.md`
- `results/qc/external_evidence_run_packets/*.md`

These packets are not evidence. They are production handoffs for running standard tools or creating reviewed TSVs that match the configured optional-input schemas.

## `external_evidence_run_packet_manifest.tsv`

| Column | Description |
| --- | --- |
| `evidence_id` | External evidence layer, such as `kaptive_ko_typing` or `host_defense_systems`. |
| `packet_path` | Markdown packet path. |
| `template_path` | Fillable TSV template for this evidence layer. |
| `optional_input_key` | Key under `inputs` in `config/workflow.yaml`. |
| `configured_input_path` | Current configured TSV path, if any. |
| `evidence_status` | Status from the external evidence plan. |
| `tool_ids` | Planned tool IDs. |
| `tool_status` | Tool/input status from the external evidence plan. |
| `eligible_sequence_records` | Number of sequence-QC-backed records eligible for the layer. |
| `action_status` | Packet-level action state. |
| `next_action` | Next action from the external evidence plan. |

## `external_evidence_run_packet_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `item` | Report item, usually `external_evidence_run_packets`. |
| `message` | Summary counts for configured, ready, and sequence-blocked packets. |

## Packet Contents

Each Markdown packet includes:

- the evidence layer and supported hypotheses;
- planned tools and current tool status;
- required sequence scope and eligible record count;
- the workflow input key to configure;
- the fillable TSV template path and required columns;
- advisory production command text;
- RBP/domain and structural packets include copy-paste normalization commands for reviewed HMMER, Foldseek, Phold, or generic TSV outputs;
- host-defense and phage anti-defense packets include copy-paste normalization commands for reviewed DefenseFinder/PADLOC-style or curated anti-defense hit TSVs;
- an acceptance checklist for provenance and missing-value handling;
- a rerun command for evidence planning, validation, readiness, and claim-support audits.

## Claim Boundary

The packets support production evidence acquisition only. They do not justify biological claims until reviewed TSVs are configured, the full workflow passes, and the study-readiness and claim-support audits allow stronger wording.
