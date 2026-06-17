# RBP External Evidence Normalization Schema

`scripts/normalize_rbp_external_evidence.py` converts reviewed external domain/profile and structure-informed outputs into the optional Stage 4 evidence TSVs:

- `inputs.domain_evidence`
- `inputs.structural_evidence`

The script does not run HMMER, Foldseek, Phold, or any external database search. It only normalizes reviewed outputs so they can be configured in `config/workflow.yaml`.

## Supported Inputs

Domain evidence:
- `generic_tsv`
- `hmmer_domtblout`

Structural evidence:
- `generic_tsv`
- `foldseek_tsv`
- `phold_tsv`

## Domain Output

Required output columns:

| Column | Description |
| --- | --- |
| `annotation_gene_id` | Stable gene identifier from Stage 3. |
| `domain_id` | Domain/profile identifier. |
| `domain_name` | Human-readable domain/profile name. |
| `start_aa` | Alignment start in the protein when available. |
| `end_aa` | Alignment end in the protein when available. |
| `evalue` | Domain/profile E-value when available. |
| `evidence_source` | Tool/file provenance. |
| `notes` | Review and normalization notes. |

## Structural Output

Required output columns:

| Column | Description |
| --- | --- |
| `annotation_gene_id` | Stable gene identifier from Stage 3. |
| `structural_hit_id` | Structural hit/template identifier. |
| `structural_hit_name` | Human-readable structural hit/template name. |
| `tm_score` | TM-score or equivalent when available. |
| `probability` | Probability/confidence/score when available. |
| `evidence_source` | Tool/file provenance. |
| `notes` | Review and normalization notes. |

## Report

`normalize_rbp_external_evidence_report.tsv` uses:

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `item` | Evidence layer. |
| `message` | Normalized row count and input path summary. |
