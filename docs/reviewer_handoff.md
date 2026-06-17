# Reviewer Handoff

This repository is a reproducible seed-data workflow for a Klebsiella phage comparative genomics study. The scientific goal is to test whether phage host range is better explained by RBP/depolymerase module architecture plus defense/counter-defense compatibility than by whole-genome phage taxonomy alone.

## Current Review Position

The repository is ready for technical review of the workflow design, data contracts, mock analysis path, and minimum real-data path. It is not yet ready for biological interpretation from real data.

Current expected state after running the real workflow:

- workflow scripts run from config;
- outputs are written under `results/`;
- H1-H6 tests exist as quantitative model rows;
- reviewed seed rows are present for INPHARED, NCBI Virus/GenBank, host-genome, and prophage source layers;
- `results/source_builder/samples.tsv` should contain seed real-data rows built from enabled source manifests;
- real H1-H6 evidence remains limited because the seed dataset is small, most public records still need expansion/deduplication, and production external evidence is incomplete;
- `results/validation/goal_completion_audit.tsv` should keep the goal incomplete.

Current expected state after running the mock workflow:

- mock workflow passes end to end;
- mock H1-H6 rows pass;
- mock readiness has no blocking manuscript-level requirements;
- mock results are fixtures only and must not be used as biological claims.

## Fast Validation Commands

Run these from the repository root:

```bash
python -m py_compile scripts/*.py
python scripts/self_test_source_export_validation.py   --output results/validation/source_export_validation_self_test.tsv   --report-output results/validation/source_export_validation_self_test_report.tsv
python scripts/run_workflow.py --config config/workflow.mock.yaml
python scripts/run_workflow.py --config config/workflow.yaml
```

The first three commands mirror the GitHub Actions CI. The final real workflow command should run, but its readiness audit should still report blocked manuscript-level support until source acquisition is consistent, production evidence tables are accepted, and H1-H6 have data-supported model rows.

## What To Inspect First

Start with these files:

- `README.md`: entry points and CI checks.
- `project_goal.md`: durable scientific goal and definition of done.
- `AGENTS.md`: project instructions for Codex/AI agents.
- `docs/hypotheses.md`: H1-H6 mapping to tests and expected outputs.
- `docs/methods.md`: current workflow methods.
- `docs/claim_ledger.md`: allowed, unsupported, and forbidden claim wording.
- `docs/limitations.md`: computational prediction and validation boundaries.
- `results/validation/goal_completion_audit.tsv`: current objective audit after a workflow run.
- `results/validation/claim_support_audit.tsv`: machine-readable claim support audit.
- `results/validation/readiness_action_plan.tsv`: ranked actions needed before manuscript-level claims.
- `results/qc/external_evidence_plan.tsv`: evidence readiness, provenance origin, and real-claim usability status.
- `results/qc/external_evidence_acceptance.tsv`: configured reviewed evidence versus missing tool/input blockers.
- `results/qc/genome_sequence_qc_report.tsv`: current sequence-backed versus metadata-only record status.
- `results/source_builder/sample_source_report.tsv`: enabled source manifests and seed-row loading status.

## What To Review Technically

Reviewers should focus on:

- whether source-curation gates prevent unreviewed or malformed rows from becoming evidence;
- whether mock data exercise all major workflow layers without pretending to be real data;
- whether H1-H6 each map to a quantitative test and figure/data output;
- whether real and mock paths are separated cleanly, including the `mock_fixture_boundary` validation row;
- whether seed real-data rows are clearly separated from manuscript-scale biological evidence;
- whether optional external evidence tables have clear schemas and provenance labels separating mock fixtures, bridge evidence, handoff files, and production evidence;
- whether claim wording is conservative and tied to current evidence status.

## Current Biological Blockers

Use the GitHub issue template `.github/ISSUE_TEMPLATE/source-curation.yml` for reviewed source-curation handoffs. The initial INPHARED seed work order has been superseded by the current seed-data state; reviewed rows now exist in multiple source layers and should be audited through the generated reports rather than treated as header-only placeholders.

The current blockers are:

- expand and deduplicate INPHARED and NCBI cultured-phage sources before atlas-size or source-enrichment interpretation;
- acquire or reconstruct local FASTA/GenBank sequence files for metadata-only rows using the generated sequence-fetch manifests;
- replace bridge evidence with reviewed production evidence from standardized tools where needed;
- add accepted RBP domain/structural evidence, host defense evidence, and phage anti-defense evidence;
- rerun H1-H6 model comparisons after the above evidence layers are accepted.

Inspect these generated reports after each real workflow run:

- `results/qc/source_work_order_acceptance.tsv`
- `results/qc/source_post_acceptance_plan.tsv`
- `results/qc/sample_support_by_hypothesis.tsv`
- `results/qc/external_evidence_acceptance.tsv`
- `results/qc/genome_sequence_qc_report.tsv`
- `results/validation/study_readiness.tsv`
- `results/validation/goal_completion_audit.tsv`

Do not fabricate rows. New records must come from reviewed source exports or equivalent curated sources. Unknown values should be `NA`; uncertainty and provenance should be recorded in `notes`.

## Annotation And Evidence Standard

Fetched public annotations are acceptable as bridge evidence and provenance, but manuscript-grade comparisons should use standardized reannotation or normalized reviewed outputs. In the current workflow:

- GenBank CDS annotation evidence is a bridge layer, not a substitute for standardized Pharokka/PHROGs-style production annotation.
- BLASTN pairwise similarity is a bridge layer, not a substitute for production VIRIDIC/Mash/ANI-style dereplication evidence.
- Kleborate and Kaptive bridge TSVs are useful for seed validation, but expanded host sets should be typed consistently.
- Screening handoff files are not accepted anti-defense, defense, domain, or structural evidence until reviewed outputs are normalized and configured as input TSVs.

This distinction is important for reviewer interpretation: the repository can validate the data path now, but biological claims require production evidence layers.

## Claim Boundaries

Inspect `results/validation/claim_support_audit.tsv` after each workflow run before strengthening manuscript wording.

Acceptable current claim:

> The repository implements a reproducible comparative-genomics workflow with seed real-data rows, bridge evidence, and mock validation for testing a two-layer Klebsiella phage host-range hypothesis.

Not acceptable yet:

> The study demonstrates that RBP/depolymerase plus defense/counter-defense features explain Klebsiella phage host range.

That claim requires expanded reviewed source data, sequence-backed QC, accepted production evidence tables, H1-H6 data-supported model rows, and manuscript-readiness audit pass status.

## GitHub Review Notes

Generated `results/` files and workflow logs are ignored by Git except directory sentinels. Reviewers should regenerate outputs locally or through CI. Small mock FASTA fixtures under `data/raw/mock_public/` are tracked because the mock workflow depends on them. The validation report includes `mock_fixture_boundary`; it should pass for the real workflow by reporting no mock fixture path references.
