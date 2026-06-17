# Priority Source Collection Packet Schema

Stage 0 writes a priority source collection packet under `results/qc/priority_source_collection_packet/`. It combines source rank, query command, web URL, starter template, preflight status, expected export path, and validation command for the highest-ranked source exports.

## `results/qc/priority_source_collection_packet_manifest.tsv`

One row per included priority source. Important columns:

| Column | Description |
| --- | --- |
| `source_id` | Source identifier. |
| `recommended_rank` | Rank from minimum source curation planning. |
| `packet_path` | Per-source Markdown packet. |
| `target_database` | Source database or review origin. |
| `requires_network` | Whether manual network/source review is expected. |
| `review_mode` | Review workflow category. |
| `web_url` | Suggested source URL when available. |
| `starter_template_path` | Header-only starter TSV. |
| `starter_readme_path` | Source-specific starter README. |
| `expected_export_path` | Reviewed export path to populate. |
| `preflight_status` | Current preflight state for the source. |
| `required_for_hypotheses` | H1-H6 hypotheses requiring this source. |
| `validation_command` | Command to rerun after curation. |

## `results/qc/priority_source_collection_packet/README.md`

Index of per-source collection packets.

## Per-source packet files

Each packet includes the source query/collection command, source URL where configured, expected output contract, review checklist, preflight expectations, and validation command.

## Interpretation

This packet is a curation handoff only. It does not download records, create reviewed exports, or support biological claims until source exports and downstream evidence are populated and validated.
