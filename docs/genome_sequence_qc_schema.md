# Genome Sequence QC Schema

`scripts/00_qc_genome_sequences.py` checks local FASTA files referenced by `raw_sequence_path` in the Stage 1 manifest. It does not download genomes and does not modify raw sequence files.

## Command

```bash
python scripts/00_qc_genome_sequences.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --thresholds config/thresholds.yaml \
  --qc-output results/qc/genome_sequence_qc.tsv \
  --report-output results/qc/genome_sequence_qc_report.tsv \
  --root .
```

The direct workflow runner executes this as `stage_1_sequence_qc` after `stage_1_sequence_acquisition`. The acquisition stage writes a local checklist but does not download genomes.

## Inputs

- `results/qc/phage_genome_manifest.tsv`: Stage 1 manifest with `genome_id`, `record_type`, `genome_length`, `gc_percent`, and `raw_sequence_path`.
- `config/thresholds.yaml`: `genome_qc` thresholds controlling length, GC, N-content, ambiguous-base content, and metadata comparison tolerance.
- Local FASTA files referenced by `raw_sequence_path`. Relative paths are resolved from the configured repository root.

## Sequence QC Output

`genome_sequence_qc.tsv` columns:

| Column | Description |
| --- | --- |
| `genome_id` | Project genome identifier. |
| `record_type` | Record type from the manifest. |
| `raw_sequence_path` | Raw sequence path from the manifest. |
| `resolved_sequence_path` | Absolute or root-resolved sequence path used for reading. |
| `sequence_qc_status` | `pass`, `warn`, `missing_sequence_file`, `invalid_fasta`, or `no_sequence_provided`. |
| `sequence_count` | Number of FASTA records. |
| `total_length_bp` | Total FASTA length across records. |
| `metadata_length_bp` | Manifest genome length, if present. |
| `length_delta_bp` | Observed length minus metadata length. |
| `length_matches_metadata` | Whether length difference is within configured tolerance. |
| `gc_percent_observed` | GC percentage computed from A/C/G/T bases. |
| `metadata_gc_percent` | Manifest GC percentage, if present. |
| `gc_delta_percent` | Observed GC minus metadata GC. |
| `gc_matches_metadata` | Whether GC difference is within configured tolerance. |
| `n_count` | Number of `N` bases. |
| `n_percent` | Percent of all bases that are `N`. |
| `ambiguous_count` | Number of non-ACGTN bases. |
| `ambiguous_percent` | Percent of all bases that are non-ACGTN. |
| `passes_sequence_qc` | `true` only when sequence file exists and no threshold or metadata warnings were raised. |
| `sequence_qc_messages` | Semicolon-delimited QC messages or `OK`. |

## Report Output

`genome_sequence_qc_report.tsv` columns:

| Column | Description |
| --- | --- |
| `genome_id` | Project genome identifier or `NA`. |
| `record_type` | Record type or `NA`. |
| `severity` | `info`, `warning`, or `error`. |
| `field` | Field or check that produced the message. |
| `message` | Human-readable QC message. |

## Interpretation

Rows with no `raw_sequence_path` are retained with `sequence_qc_status=no_sequence_provided`; this is useful during metadata-only curation but is not sufficient for final genome-level claims. Rows with `passes_sequence_qc=false` should be reviewed before production dereplication, annotation, or manuscript analyses.

## Downstream Use

Stage 2 dereplication can consume this table through `--sequence-qc`. When `genome_qc.exclude_failed_local_sequence_qc_from_clustering: true`, local FASTA-backed records with failing sequence QC are excluded before species-like clustering. Metadata-only records with `sequence_qc_status=no_sequence_provided` remain eligible during early curation and are marked in cluster outputs.


See `docs/sequence_acquisition_schema.md` for the local sequence-acquisition planning stage that runs before QC.
