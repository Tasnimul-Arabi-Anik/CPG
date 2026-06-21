# Workflow Validation Schema

Stage 9 audits the current repository state against the project goal. It checks required outputs, required columns, documentation, claim ledger coverage, script compilation, workflow configuration, figure source files, and hypothesis coverage.

## Outputs

### `results/validation/schema_validation.tsv`

One row per required workflow output with existence, row count, required-column status, and pass/warn/fail status.

### `results/validation/hypothesis_coverage.tsv`

One row per main hypothesis H1-H6. Each row records whether detailed quantitative model or group-summary rows currently represent the hypothesis in `results/models/model_comparison.tsv`. The `status` column is a technical coverage state only. Use `analysis_available`, `data_adequate`, `claim_status`, and `claim_supported` to distinguish an available analysis from adequate data and manuscript-safe claim support.

### `results/validation/output_inventory.tsv`

Inventory of files under `results/`, including file size and TSV row counts where applicable.

### `results/validation/workflow_validation_report.tsv`

High-level audit report. Missing files or schema mismatches are errors. Empty but schema-valid scaffold outputs are warnings. The current repository can therefore be validated as a working pipeline scaffold without claiming biological conclusions before data are loaded.

## Interpretation

A passing validation report means the workflow structure is internally consistent. It does not mean the biological study is complete, especially if `config/samples.tsv` has no data rows or model statuses are `no_labeled_samples`, `single_class_uninformative`, or `insufficient_groups_for_rate_test`.

The validator also checks that the selected workflow config exists and contains the top-level sections required by `scripts/run_workflow.py`. Use `--results-dir` and `--samples` to audit alternate configured runs such as `config/workflow.mock.yaml`.

The documentation audit also requires the source catalog schema so dataset population can be reproduced before Stage 1 manifest validation.

The required output schema audit includes `source_catalog_readiness.tsv` and `source_catalog_audit_report.tsv` so planned, disabled, populated, and invalid source manifests are visible in validation reports. It also requires `results/models/hypothesis_summary.tsv` so H1-H6 have a single audited manuscript-facing evidence summary, and `results/qc/assay_feature_coverage.tsv` so assay outcomes cannot be interpreted without feature-coverage context. Workflow-config, external-evidence, RBP, defense/counter-defense, sequence-acquisition, and phage-host assay self-tests are included so schema drift and profile-resolution regressions are caught before production evidence is configured. The schema audit also requires external-evidence acceptance `content_lint` columns so circular workflow outputs, keyword-inference anti-defense rows, or unresolved evidence IDs cannot silently become production evidence.

## Mock Fixture Boundary

The workflow validator checks the selected workflow config for mock fixture path references. `config/workflow.mock.yaml` is allowed to reference `data/metadata/mock*`, `data/raw/mock*`, and `results/mock*` paths because it is a fixture workflow. The real workflow config should not reference mock fixture paths; if it does, `workflow_validation_report.tsv` records a `mock_fixture_boundary` failure.

## Workflow Run Report Metadata

`results/<profile>/validation/workflow_run_report.tsv` includes `workflow_profile`, `evidence_class`, `workflow_config_path`, `workflow_config_sha256`, `git_commit`, and `run_started_at` so generated outputs are traceable to the resolved config and source revision.
