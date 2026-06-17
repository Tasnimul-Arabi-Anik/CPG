# Source Work-Order Packet Schema

`scripts/create_source_work_order_packets.py` renders `results/qc/source_curation_work_order.tsv` as Markdown packets under `results/qc/source_work_order_packets/`. These packets combine each work order with starter-kit and dashboard context so reviewed source rows can be curated from a single per-source file. Each packet also includes a row-entry checklist, the exact export header to preserve, provenance boundaries, and focused acceptance commands.

## Command

```bash
python scripts/create_source_work_order_packets.py \
  --work-orders results/qc/source_curation_work_order.tsv \
  --starter-kit-manifest results/qc/source_export_starter_kit_manifest.tsv \
  --dashboard results/qc/source_readiness_dashboard.tsv \
  --output-dir results/qc/source_work_order_packets \
  --manifest-output results/qc/source_work_order_packet_manifest.tsv \
  --report-output results/qc/source_work_order_packet_report.tsv \
  --root .
```

The config-driven workflow runs this stage after `stage_0_source_curation_work_order`.

## Directory Outputs

- `results/qc/source_work_order_packets/README.md`: index of rendered work-order packets.
- `results/qc/source_work_order_packets/WO*_SOURCE.md`: one Markdown packet per work order.

## Packet Sections

Each Markdown packet includes:

- curation target, required fields, blocked sample-support metrics, and expected export path;
- identity fields and a row-level checklist for non-missing required values;
- the exact TSV header that must be preserved in the reviewed export;
- provenance and raw-data boundaries that prevent unreviewed rows from becoming evidence;
- the full source-refresh command and a focused source-work-order acceptance command.

## `results/qc/source_work_order_packet_manifest.tsv`

| Column | Description |
| --- | --- |
| `work_order_id` | Work-order identifier. |
| `source_id` | Source to curate. |
| `packet_path` | Markdown packet path. |
| `expected_export_path` | Reviewed export path to fill. |
| `minimum_rows_to_add` | Minimum reviewed rows requested by the work order. |
| `required_fields` | Fields needed in reviewed rows. |
| `curation_priority` | Priority inherited from the source readiness dashboard. |

## `results/qc/source_work_order_packet_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info` or `warning`. |
| `item` | Report item name. |
| `message` | Packet count and packet index path. |

## Interpretation

Packets are operational curation aids only. They do not create biological evidence and do not validate reviewed rows by themselves. H1-H6 remain blocked until reviewed exports are populated, validated, imported into source manifests, enabled, and downstream sample-support and evidence checks pass.
