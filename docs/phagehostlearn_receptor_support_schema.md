# PhageHostLearn Receptor-Support Bridge Schema

`scripts/build_phagehostlearn_receptor_support.py` normalizes reviewed local PhageHostLearn RBPbase and Locibase files into tracked seed bridge-evidence tables under `data/metadata/external_evidence/`. These tables are bridge metadata for H1b coverage auditing only. They are not production K/O typing, structural RBP annotation, or functional receptor validation.

## Phage RBPbase Support

File: `data/metadata/external_evidence/phagehostlearn_rbpbase_receptor_support.tsv`

| Column | Meaning |
| --- | --- |
| `phage_genome_id` | Canonical project phage ID. |
| `source_phage_id` | PhageHostLearn source phage ID from RBPbase. |
| `support_source` | Source label, currently `PhageHostLearn_RBPbase`. |
| `receptor_support_status` | Evidence tier label; seed support only. |
| `protein_count` | Number of RBPbase protein rows for the phage. |
| `protein_count_bin` | Binned protein count for seed coverage summaries. |
| `max_xgb_score` | Maximum RBPbase XGBoost score observed for the phage. |
| `max_xgb_score_bin` | Binned maximum score for seed coverage summaries. |
| `protein_ids` | Semicolon-separated RBPbase protein IDs. |
| `source_file_sha256` | SHA-256 of the reviewed local RBPbase file. |
| `notes` | Claim boundary and provenance notes. |

## Host Locibase Support

File: `data/metadata/external_evidence/phagehostlearn_locibase_host_locus_support.tsv`

| Column | Meaning |
| --- | --- |
| `host_genome_id` | Canonical project host ID. |
| `source_host_id` | PhageHostLearn source host ID from Locibase. |
| `support_source` | `Locibase`, `Locibase_invitro`, or both. |
| `receptor_support_status` | Evidence tier label; seed support only. |
| `locus_protein_count` | Number of locus protein sequences for this host. |
| `locus_protein_count_bin` | Binned locus protein count for seed coverage summaries. |
| `locus_fingerprint_sha256` | Stable SHA-256 fingerprint of sorted locus protein sequences. |
| `source_file_sha256` | SHA-256 values of reviewed local source files. |
| `notes` | Claim boundary and provenance notes. |

## Interpretation Rules

- RBPbase metadata can help report seed bridge metadata coverage, but it is not a substitute for standardized Pharokka/PHROGs/domain/structural RBP evidence.
- Locibase fingerprints can distinguish host locus support patterns, but they are not Kaptive/Kleborate K/O/ST calls.
- These bridge metadata tables must not generate claim-facing H1b model metrics; pairwise H1b modeling waits for production receptor/RBP evidence and grouped cold-host/cold-phage/cold-study evaluation.
