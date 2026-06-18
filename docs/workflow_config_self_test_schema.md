# Workflow config self-test schema

`stage_9_workflow_config_self_test` verifies that workflow profile inheritance and placeholder substitution behave consistently for the direct runner, validators, and Snakemake-facing config loader.

## `results/<profile>/validation/workflow_config_self_test.tsv`

Columns:

- `test_id`: stable self-test identifier.
- `scenario`: behavior being exercised.
- `expected_status`: expected result category.
- `observed_status`: result produced by the self-test.
- `status`: `pass` or `fail`.
- `notes`: diagnostic detail for failed cases, otherwise `NA`.

Required covered cases:

- profile overlays deep-merge with `workflow.base.yaml`;
- `{results_dir}` and `{logs_dir}` placeholders resolve from profile paths;
- `config/workflow.yaml` can act as a seed alias;
- resolved config checksums are stable SHA-256 digests;
- unknown placeholders are blocking errors;
- circular `extends` chains are blocking errors.

## `results/<profile>/validation/workflow_config_self_test_report.tsv`

Columns:

- `severity`: `info` or `error`.
- `item`: report item identifier.
- `message`: human-readable summary, including pass/fail counts.

A passing self-test proves only config-resolution mechanics. It does not prove biological readiness, production evidence availability, or manuscript claim support.
