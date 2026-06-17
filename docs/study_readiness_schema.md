# Study Readiness Audit Schema

`scripts/09_audit_study_readiness.py` summarizes whether the current workflow outputs are sufficient for manuscript-level interpretation. It does not replace workflow schema validation; it consumes validation and analysis outputs to produce an explicit evidence-backed readiness matrix.

## Command

```bash
python scripts/09_audit_study_readiness.py \
  --root . \
  --results-dir results \
  --samples config/samples.tsv \
  --readiness-output results/validation/study_readiness.tsv \
  --report-output results/validation/study_readiness_report.tsv
```

The direct workflow runner executes this as `stage_10_study_readiness` after `stage_9_validation`.

## Readiness Matrix

`study_readiness.tsv` columns:

| Column | Description |
| --- | --- |
| `requirement_id` | Stable requirement identifier. |
| `area` | Workflow or manuscript-readiness area. |
| `requirement` | Requirement being assessed. |
| `evidence_path` | File used as primary evidence. |
| `evidence_summary` | Compact quantitative summary of evidence. |
| `status` | `pass`, `warn`, or `fail`. |
| `blocking_for_manuscript` | Whether this gap blocks manuscript-level claims. |
| `next_action` | Concrete action needed to improve readiness. |

Audited areas include dataset curation, source readiness, source query/template/export-validation/acquisition planning, source work-order acceptance, tool availability, sequence acquisition planning, sequence QC, external evidence planning, dereplication, annotation/pangenome, RBP/depolymerase candidates, host features, defense/counter-defense features, configured H1-H6 sample support, H1-H6 tests, figures, and documentation/claims. Disabled optional source placeholders remain visible in source-acquisition summaries, but they block manuscript readiness only if they are enabled, required, or have an enabled import path that is inconsistent.

## Report

`study_readiness_report.tsv` columns:

| Column | Description |
| --- | --- |
| `severity` | `info` or `warning`. |
| `item` | Report item. |
| `message` | Summary message with pass/warn/fail counts. |

## Interpretation

A mock workflow can pass readiness using bundled fixture data. A real workflow should not be treated as manuscript-ready while requirements remain `fail` or blocking. In particular, an empty audited sample table, blocked rows in `results/qc/sample_support_by_hypothesis.tsv`, empty biological output tables, missing real source manifests, or only limited H1-H6 tests mean the repository is a validated scaffold rather than a populated biological study.


## Acquisition and Evidence Planning Checks

The readiness audit consumes upstream planning outputs in addition to downstream analysis tables:

- `results/qc/source_query_plan.tsv` records the planned public/local queries and reviewed export targets for each source layer.
- `results/qc/source_export_template_manifest.tsv` records generated header-only templates for reviewed source exports.
- `results/qc/source_export_validation.tsv` checks reviewed exports for expected headers, identity values, and duplicate identities before import.
- `results/qc/source_acquisition_plan.tsv` checks whether source manifests or local exports are ready to import/build.
- `results/qc/source_work_order_acceptance.tsv` checks whether reviewed source curation work orders have enough required rows; it is blocking only when H1-H6 sample-support requirements do not already pass.
- `results/qc/source_work_order_packet_manifest.tsv` links the first blocking work order to a Markdown curation packet such as `results/qc/source_work_order_packets/WO001_inphared_klebsiella_phages.md`.
- `results/qc/sample_support_by_hypothesis.tsv` checks whether the generated sample table meets configured minimum counts for H1-H6 interpretation.
- `results/qc/sequence_acquisition_plan.tsv` checks whether manifest records have local FASTA files, accession-backed fetch paths, or metadata gaps.
- `results/qc/sequence_fetch_manifest.tsv` records reviewable accession-backed commands and manual curation rows before any sequence downloads are run.
- `results/qc/external_evidence_plan.tsv` checks whether pairwise similarity, annotation, RBP/domain/structural, host-feature, and defense/counter-defense evidence are configured and schema-valid.
- `results/qc/external_evidence_template_manifest.tsv` records fillable schemas for missing external evidence TSVs.

These checks make the reason for a downstream empty table explicit. For example, empty annotation tables are interpreted differently when the external evidence plan is still waiting for sequence-backed genomes versus when a configured annotation TSV is present but schema-invalid.
