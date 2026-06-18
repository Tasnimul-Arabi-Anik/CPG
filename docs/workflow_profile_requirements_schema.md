# Workflow Profile Requirements Schema

`scripts/validate_workflow_profile_requirements.py` validates resolved workflow profile semantics before the workflow executes evidence-generating stages.

The check is intentionally offline. It does not download data or run external bioinformatics tools.

## Purpose

The profile gate separates workflow scopes:

- `mock`: synthetic fixture plumbing checks.
- `seed`: reviewed seed metadata and bridge evidence; no biological claims.
- `production`: sequence-backed production profile that must fail closed while required evidence is absent.

Production profiles fail when required production evidence inputs or tested assay outcomes are missing. Mock and seed profiles can pass without production evidence, but their `profile.allows_biological_claims` value must remain `false`.

## Outputs

Default paths are profile-scoped:

- `results/<profile>/validation/workflow_profile_requirements.tsv`
- `results/<profile>/validation/workflow_profile_requirements_report.tsv`

## `workflow_profile_requirements.tsv`

| Column | Description |
| --- | --- |
| `requirement_id` | Stable requirement identifier. |
| `workflow_profile` | Resolved profile name. |
| `evidence_class` | Resolved evidence class. |
| `requirement` | Requirement being checked. |
| `observed` | Observed value or path. |
| `status` | `pass` or `fail`. |
| `severity` | `info`, `warning`, or `error`. |
| `message` | Human-readable validation result. |

## `workflow_profile_requirements_report.tsv`

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `item` | Report item. |
| `message` | Summary counts and failure status. |
