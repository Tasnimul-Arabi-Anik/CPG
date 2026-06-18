# External Evidence Acceptance Schema

`scripts/check_external_evidence_acceptance.py` checks the current external evidence plan and reports whether configured TSVs are ready for workflow use, still missing, schema-invalid, accepted with provenance lint, or rejected by evidence-specific content checks.

Default outputs:

- `results/qc/external_evidence_acceptance.tsv`
- `results/qc/external_evidence_acceptance_report.tsv`

This is an operational acceptance check. It does not prove biological claims and does not replace the claim-support audit.

## `external_evidence_acceptance.tsv`

| Column | Description |
| --- | --- |
| `evidence_id` | External evidence layer. |
| `analysis_layer` | Workflow layer that consumes the evidence. |
| `optional_input_key` | Key under `inputs` in `config/workflow.yaml`. |
| `configured_input_path` | Configured evidence TSV path, if any. |
| `configured_input_exists` | Whether the configured path exists. |
| `configured_input_rows` | Data-row count reported by the external evidence plan. |
| `configured_input_schema_status` | Minimum schema status from the external evidence plan. |
| `evidence_status` | Evidence readiness status from the external evidence plan. |
| `evidence_origin` | Provenance class from the external evidence plan. |
| `real_claim_use_status` | Claim-use boundary from the external evidence plan. |
| `blocking_for_manuscript` | Whether the layer blocks manuscript-strength claims. |
| `rows_with_evidence_source` | Rows with `evidence_source`, `tool`, or `evidence` populated. |
| `rows_with_notes` | Rows with `notes` populated. |
| `provenance_lint` | Missing provenance columns or missing populated provenance values. |
| `content_lint` | Evidence-specific content problems, such as workflow-generated result paths, keyword-inference anti-defense rows configured as production evidence, or IDs that do not resolve against current workflow manifest/annotation/host tables. |
| `acceptance_status` | Operational status for this evidence layer. |
| `blocking_issue` | Whether this layer currently blocks production evidence readiness. |
| `next_action` | Concrete next action. |

## Acceptance Status Values

| Status | Meaning |
| --- | --- |
| `accepted` | Configured TSV exists, has rows, passes schema checks, and has populated provenance fields. |
| `accepted_with_provenance_lint` | Configured TSV is usable by the workflow but provenance fields should be reviewed before manuscript use. |
| `content_rejected` | Configured TSV has rows and passes minimum schema checks, but content lint prevents accepting it as production external evidence. |
| `schema_invalid` | Configured TSV has rows but fails the minimum schema check. |
| `configured_empty` | Configured TSV exists but has no data rows. |
| `configured_missing` | Workflow points to a missing TSV path. |
| `waiting_for_sequence_data` | Required sequence-backed records are not yet available. |
| `missing_tool_or_input` | Required sequence records exist but no configured TSV or available planned tool exists. |
| `manual_evidence_required` | A reviewed manual or external-analysis TSV is required. |
| `ready_to_run_external_tool` | Required sequence records and at least one planned tool are available. |
| `not_ready` | Fallback status for unclassified evidence states. |

## Interpretation

Rows with `accepted` or `accepted_with_provenance_lint` can be consumed by workflow stages, but only the full study-readiness, hypothesis-coverage, traceability, and claim-support audits determine whether a manuscript claim can be strengthened. Rows marked `content_rejected` must not be configured as accepted production evidence; this currently guards against circular workflow-generated outputs, keyword-only anti-defense inference, and evidence IDs that do not resolve against the current manifest, annotation table, or host metadata when those reference tables are available.
