# External Evidence Protein Handoff Schema

`scripts/export_external_evidence_proteins.py` exports normalized phage/prophage protein sequences from `results/annotations/phage_annotations.tsv` for external domain/profile and structure-informed annotation runs.

This handoff is not biological evidence by itself. It provides stable `annotation_gene_id` FASTA headers and a prioritization manifest so tools such as HMMER/profile searches, Foldseek, or Phold can generate reviewed TSVs for `inputs.domain_evidence` and `inputs.structural_evidence`.

## Outputs

- `results/qc/external_evidence_proteins/phage_proteins.faa`
- `results/qc/external_evidence_proteins/rbp_depolymerase_candidate_proteins.faa`
- `results/qc/external_evidence_proteins/protein_export_manifest.tsv`
- `results/qc/external_evidence_proteins/protein_export_report.tsv`

## `protein_export_manifest.tsv`

| Column | Description |
| --- | --- |
| `annotation_gene_id` | Stable gene identifier from the normalized annotation table. |
| `genome_id` | Source phage/prophage genome identifier. |
| `gene_id` | Original gene identifier when available. |
| `product` | Product text from the normalized annotation table. |
| `protein_length_aa` | Protein length in amino acids when available. |
| `functional_category` | Normalized functional category from Stage 3. |
| `module_hint` | Stage 3 module hint used only for run prioritization. |
| `candidate_priority` | `rbp_depolymerase_priority` or `background`. |
| `candidate_reason` | Text signal used to prioritize external annotation. |
| `sequence_source` | Annotation/evidence source that supplied the protein sequence. |
| `notes` | Provenance and claim-boundary note. |

## `protein_export_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `item` | Report item. |
| `message` | Summary of annotation rows, exported proteins, and prioritized proteins. |
