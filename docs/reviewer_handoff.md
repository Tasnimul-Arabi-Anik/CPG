# Reviewer Handoff

This repository is a reproducible scaffold for a Klebsiella phage comparative genomics study. The scientific goal is to test whether phage host range is better explained by RBP/depolymerase module architecture plus defense/counter-defense compatibility than by whole-genome phage taxonomy alone.

## Current Review Position

The repository is ready for technical review of the workflow design, data contracts, and mock analysis path. It is not yet ready for biological interpretation from real data.

Current expected state after running the real workflow:

- workflow scripts run from config;
- outputs are written under `results/`;
- H1-H6 tests exist as quantitative model rows;
- real H1-H6 evidence is limited because reviewed source exports are header-only;
- `results/source_builder/samples.tsv` has zero real rows;
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

The first three commands mirror the GitHub Actions CI. The final real workflow command should run, but its readiness audit should still report blocked real-data support until reviewed exports are populated.

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
- `results/validation/readiness_action_plan.tsv`: ranked actions needed before manuscript-level claims.
- `results/qc/external_evidence_plan.tsv`: evidence readiness, provenance origin, and real-claim usability status.

## What To Review Technically

Reviewers should focus on:

- whether source-curation gates prevent unreviewed or malformed rows from becoming evidence;
- whether mock data exercise all major workflow layers without pretending to be real data;
- whether H1-H6 each map to a quantitative test and figure/data output;
- whether real and mock paths are separated cleanly, including the `mock_fixture_boundary` validation row;
- whether optional external evidence tables have clear schemas and provenance labels separating mock fixtures from production evidence;
- whether claim wording is conservative and tied to current evidence status.

## Current Biological Blocker

The first real-data blocker is source work order WO001:

- packet: `results/qc/source_work_order_packets/WO001_inphared_klebsiella_phages.md`
- reviewed export to populate: `data/metadata/source_exports/inphared_klebsiella_phages.tsv`
- minimum rows requested: one reviewed cultured Klebsiella phage row with required fields.

Do not fabricate rows. The row must come from a reviewed INPHARED/source export or equivalent curated source. Unknown values should be `NA`; uncertainty and provenance should be recorded in `notes`.

After curating a row, run the focused command shown in the WO001 packet, then rerun the full workflow and inspect:

- `results/qc/source_work_order_acceptance.tsv`
- `results/qc/source_post_acceptance_plan.tsv`
- `results/qc/sample_support_by_hypothesis.tsv`
- `results/validation/study_readiness.tsv`
- `results/validation/goal_completion_audit.tsv`

## Claim Boundaries

Acceptable current claim:

> The repository implements a reproducible comparative-genomics scaffold and mock validation path for testing a two-layer Klebsiella phage host-range hypothesis.

Not acceptable yet:

> The study demonstrates that RBP/depolymerase plus defense/counter-defense features explain Klebsiella phage host range.

That claim requires populated reviewed source data, sequence/evidence tables, H1-H6 passing rows, and manuscript-readiness audit pass status.

## GitHub Review Notes

Generated `results/` files and workflow logs are ignored by Git except directory sentinels. Reviewers should regenerate outputs locally or through CI. Small mock FASTA fixtures under `data/raw/mock_public/` are tracked because the mock workflow depends on them. The validation report includes `mock_fixture_boundary`; it should pass for the real workflow by reporting no mock fixture path references.
