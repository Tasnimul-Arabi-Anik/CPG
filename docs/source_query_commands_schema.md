# Source Query Commands Schema

Stage 0 writes reviewed-export query command sheets from `results/qc/source_query_plan.tsv`. These files make source export acquisition reproducible without downloading or trusting external data automatically.

## Inputs

- `results/qc/source_query_plan.tsv`
- `results/qc/source_export_template_manifest.tsv`

## Outputs

### `results/qc/source_query_commands.tsv`

One row per planned source query. Important columns:

- `query_id`: planned source query identifier.
- `source_id`: matching source catalog identifier.
- `record_layer`: cultured phage, literature phage, prophage, host genome, or discovery layer.
- `target_database`: database or local curation context.
- `expected_export_path`: reviewed TSV path to populate.
- `template_path`: generated export template path.
- `requires_network`: whether external web/database review is expected.
- `review_mode`: route for curation, such as NCBI review, literature review, INPHARED snapshot review, or local prophage mining export.
- `web_url`: search or project URL when applicable.
- `command_text`: local shell-safe hint that documents the reviewed export path and route.
- `output_contract`: expected reviewed TSV contract.
- `review_checklist`: source-level curation checks before enabling imports/catalog entries.

### `results/qc/source_query_commands.sh`

A shell handoff file that documents the same commands and URLs. It does not download data automatically; it prints the reviewed export targets and preserves the manual-review boundary.

### `results/qc/source_query_commands_report.tsv`

Run-level summary with command count and network/local review counts.

## Interpretation

These command sheets are acquisition aids. The authoritative source input remains the reviewed export written under `data/metadata/source_exports/`, then validated by the source export validation stage.
