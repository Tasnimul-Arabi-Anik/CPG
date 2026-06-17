# Figure Generation Schema

Stage 8 generates reproducible source tables and draft SVGs for the six planned manuscript figures. The SVGs are lightweight scaffolds created with the Python standard library; the source TSVs are the authoritative figure data and should be used for final visual polishing.

## Inputs

Stage 8 consumes the current outputs from Stages 1-7:

- dataset manifest and phage clusters;
- gene clusters and pangenome matrix;
- RBP/depolymerase candidates and module clusters;
- host metadata and phage-host links;
- defense/counter-defense compatibility features;
- model comparison and feature importance tables.

## Outputs

For each planned figure, Stage 8 writes a source TSV and draft SVG under `results/figures/`:

- `figure_1_dataset_atlas_source.tsv` and `figure_1_dataset_atlas.svg`
- `figure_2_phage_pangenome_source.tsv` and `figure_2_phage_pangenome.svg`
- `figure_3_rbp_module_network_source.tsv` and `figure_3_rbp_module_network.svg`
- `figure_4_k_o_association_source.tsv` and `figure_4_k_o_association.svg`
- `figure_5_defense_counterdefense_source.tsv` and `figure_5_defense_counterdefense.svg`
- `figure_6_novelty_prioritization_source.tsv` and `figure_6_novelty_prioritization.svg`

Additional outputs:

- `results/figures/figure_manifest.tsv`: one row per figure with paths and status.
- `results/figures/figure_generation_report.tsv`: run-level provenance messages.

## Current Behavior

The draft SVGs are not final publication art. They are reproducible visual checks tied to source data. Empty datasets still produce schema-valid source tables and SVGs marked as empty.
