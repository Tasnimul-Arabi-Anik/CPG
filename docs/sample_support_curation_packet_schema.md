# Sample Support Curation Packet Schema

`scripts/create_sample_support_curation_packet.py` renders Markdown curation packets from `sample_support_source_bridge.tsv` and `sample_support_export_preflight.tsv`. The packet is a human-facing handoff for creating reviewed exports that satisfy failed sample-support metrics.

## Command

```bash
python scripts/create_sample_support_curation_packet.py \
  --bridge results/qc/sample_support_source_bridge.tsv \
  --preflight results/qc/sample_support_export_preflight.tsv \
  --output-dir results/qc/sample_support_curation_packet \
  --manifest-output results/qc/sample_support_curation_packet_manifest.tsv \
  --report-output results/qc/sample_support_curation_packet_report.tsv \
  --root .
```

## Outputs

- `results/qc/sample_support_curation_packet/README.md`: index of source-specific packets.
- `results/qc/sample_support_curation_packet/<source_id>.md`: per-source checklist with blocked metrics, fields to populate, expected export path, and rerun commands.
- `results/qc/sample_support_curation_packet_manifest.tsv`: machine-readable manifest.
- `results/qc/sample_support_curation_packet_report.tsv`: run-level report.

## Manifest Columns

- `source_id`: source export identifier.
- `packet_path`: generated Markdown packet path.
- `recommended_rank`: source rank from the minimum source plan.
- `expected_export_path`: reviewed export path to populate.
- `blocked_metrics`: metrics still blocked by sample-support export preflight.
- `fields_to_populate`: union of fields relevant to this source across blocked metrics.
- `required_for_hypotheses`: H1-H6 hypotheses affected by this source.
- `blocking_preflight_rows`: number of blocked metric/source preflight rows.
- `ready_preflight_rows`: number of metric/source rows already ready.
- `next_action`: concise curation action.

## Interpretation

This packet does not create reviewed source data. It translates workflow blockers into a concise curation checklist so the next manual or network-backed source collection step can be performed reproducibly.
