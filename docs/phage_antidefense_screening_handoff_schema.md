# Phage Anti-Defense Screening Handoff Schema

`scripts/create_phage_antidefense_screening_handoff.py` creates a reviewer-facing screening manifest for phage anti-defense candidate discovery.

This handoff does not infer or accept phage anti-defense genes. It records stable `annotation_gene_id` targets, links them to the exported phage protein FASTA, and writes command hints for curated HMM/profile or sequence database screening. Accepted anti-defense evidence must still be produced as a reviewed TSV and configured through `inputs.phage_antidefense_input`.

## Outputs

- `results/qc/phage_antidefense_screening_handoff.tsv`
- `results/qc/phage_antidefense_screening_commands.sh`
- `results/qc/phage_antidefense_screening_handoff_report.tsv`

## `phage_antidefense_screening_handoff.tsv`

| Column | Description |
| --- | --- |
| `annotation_gene_id` | Stable gene identifier from Stage 3 annotation output. |
| `phage_genome_id` | Source phage/prophage genome identifier. |
| `gene_id` | Original gene identifier when available. |
| `product` | Product annotation used only for screening prioritization. |
| `protein_length_aa` | Protein length when available. |
| `screening_priority` | `anti_defense_review_priority` or `background`. |
| `screening_reason` | Text signal used to prioritize external review. |
| `suggested_target_defense_system` | Candidate target class suggested for review, not accepted evidence. |
| `protein_fasta` | FASTA used for external HMM/profile or sequence screening. |
| `output_tsv_target` | Expected reviewed TSV target for normalized anti-defense evidence. |
| `run_status` | `ready_for_curated_screening` or `waiting_for_protein_fasta`. |
| `notes` | Claim-boundary and provenance note. |

## `phage_antidefense_screening_handoff_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `item` | Report item. |
| `message` | Summary of screening targets, priority targets, and FASTA availability. |
