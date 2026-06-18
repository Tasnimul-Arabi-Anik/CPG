# RBP External Evidence Normalization Schema

`scripts/normalize_rbp_external_evidence.py` converts reviewed external domain/profile and structure-informed outputs into the optional Stage 4 evidence TSVs:

- `inputs.domain_evidence`
- `inputs.structural_evidence`

The script does not run HMMER, Foldseek, Phold, or any external database search. It only normalizes reviewed outputs so they can be configured in `config/workflow.yaml`. Header-only outputs are not accepted biological evidence.

## Supported Inputs

Domain evidence:

- `generic_tsv`
- `hmmer_domtblout`

Structural evidence:

- `generic_tsv`
- `foldseek_tsv`
- `phold_tsv`

HMMER orientation must be explicit with `--hmmer-mode`:

- `hmmsearch`: target is the protein or `annotation_gene_id`, query is the profile/domain.
- `hmmscan`: query is the protein or `annotation_gene_id`, target is the profile/domain.

Foldseek and Phold TSV inputs can be headered or headerless. Headerless files require an explicit field order with `--foldseek-fields` or `--phold-fields`. The default Foldseek field order is:

```text
query,target,alntmscore,prob,evalue
```

## Validation

The normalizer now performs safety checks before writing production evidence tables:

- optional `--annotation-manifest` validation that every `annotation_gene_id` resolves to the Stage 3 protein/annotation manifest;
- required `domain_id` and `structural_hit_id` values;
- positive ordered domain coordinates when `start_aa` and `end_aa` are supplied;
- non-negative domain E-values;
- structural `tm_score` in the 0-1 range;
- structural probability in the 0-1 range, with 0-100 percentages normalized to 0-1;
- duplicate domain and structural hits are skipped and reported;
- malformed headerless field counts are blocking errors.

If an input for an evidence type is absent and the corresponding output already exists, the existing file is preserved unless `--overwrite-empty` is set. This prevents a domain-only normalization run from silently replacing existing structural evidence with a header-only table.

## Provenance Columns

Both normalized evidence tables include these provenance columns:

| Column | Description |
| --- | --- |
| `tool` | Tool or review source used to generate the input evidence. |
| `tool_version` | Tool version when known. |
| `database` | Profile, structure, or annotation database name. |
| `database_version` | Database/profile/template version when known. |
| `command` | Reviewed command used to generate the input evidence. |
| `run_date` | Run or retrieval date. |
| `input_checksum` | SHA-256 checksum of the reviewed input evidence file. |
| `output_checksum` | Row-level checksum over the normalized output fields. |

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
| provenance columns | See provenance table above. |

## Structural Output

Required output columns:

| Column | Description |
| --- | --- |
| `annotation_gene_id` | Stable gene identifier from Stage 3. |
| `structural_hit_id` | Structural hit/template identifier. |
| `structural_hit_name` | Human-readable structural hit/template name. |
| `tm_score` | TM-score or equivalent when available. |
| `probability` | Probability/confidence value normalized to 0-1 when available. |
| `evidence_source` | Tool/file provenance. |
| `notes` | Review and normalization notes. |
| provenance columns | See provenance table above. |

## Example

```bash
python scripts/normalize_rbp_external_evidence.py \
  --domain-input results/external/rbp_domains/hmmer.domtblout \
  --domain-format hmmer_domtblout \
  --hmmer-mode hmmsearch \
  --structural-input results/external/rbp_structures/foldseek.tsv \
  --structural-format foldseek_tsv \
  --foldseek-fields query,target,alntmscore,prob,evalue \
  --annotation-manifest results/annotations/phage_annotations.tsv \
  --tool-version reviewed \
  --database reviewed_profile_or_structure_set \
  --database-version reviewed_snapshot \
  --domain-output data/metadata/external_evidence/rbp_domain_evidence.tsv \
  --structural-output data/metadata/external_evidence/rbp_structural_evidence.tsv \
  --report-output results/qc/normalize_rbp_external_evidence_report.tsv
```

## Report

`normalize_rbp_external_evidence_report.tsv` uses:

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `item` | Evidence layer or validation item. |
| `message` | Normalized row count, duplicate warning, preservation note, or blocking error. |
