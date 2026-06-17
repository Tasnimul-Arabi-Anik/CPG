# Source Curation Packet Schema

Stage 0 writes a human-readable reviewed-export packet under `results/qc/source_curation_packet/`. The packet is generated from `results/qc/source_curation_tasks.tsv` and is intended for manual source review without changing raw data.

## Inputs

- `results/qc/source_curation_tasks.tsv`

## Outputs

### `results/qc/source_curation_packet/README.md`

Index of all source packets, including source ID, priority, curation status, blocking status, packet link, and expected export path.

### `results/qc/source_curation_packet/<source_id>.md`

One packet per configured source. Each packet records:

- record layer and priority;
- target database or manual curation source;
- reviewed export path to populate;
- generated export template path;
- normalized manifest path;
- query or curation definition;
- required export columns;
- identity columns required for import and deduplication;
- checklist for export creation, validation, import enablement, catalog enablement, and readiness;
- current status, next action, command hint, and notes.

### `results/qc/source_curation_packet_manifest.tsv`

One row per packet with `source_id`, `packet_path`, export/template/manifest paths, priority, curation status, blocking status, and next action.

### `results/qc/source_curation_packet_report.tsv`

Run-level summary with source, ready, and blocking counts.

## Interpretation

The packet is a curation aid, not a data source. The authoritative machine-readable handoff remains `results/qc/source_curation_tasks.tsv`; the packet makes that table easier to review and execute.
