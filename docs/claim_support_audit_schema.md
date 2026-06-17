# Claim Support Audit Schema

`results/validation/claim_support_audit.tsv` is a machine-readable interpretation guardrail for `docs/claim_ledger.md`.

The audit joins the claim ledger to workflow validation, H1-H6 model summaries, H1-H6 traceability, and external evidence provenance. Its purpose is to prevent mock or scaffold evidence from being promoted into real biological claims.

## Outputs

| File | Description |
| --- | --- |
| `results/validation/claim_support_audit.tsv` | One row per claim ledger claim. |
| `results/validation/claim_support_report.tsv` | Compact report summarizing claim-use restrictions. |

Mock workflow equivalents are written under `results/mock/validation/`.

## Columns

| Column | Description |
| --- | --- |
| `claim_id` | Claim identifier from `docs/claim_ledger.md`. |
| `linked_hypotheses` | H1-H6 hypotheses linked to the claim. |
| `claim_type` | Claim category from the ledger. |
| `ledger_status` | Current prose status from the ledger. |
| `evidence_sources` | Evidence paths listed by the ledger. |
| `workflow_support_status` | Whether workflow validation supports framework/resource wording. |
| `hypothesis_trace_status` | Joined H1-H6 traceability statuses for linked hypotheses. |
| `model_summary_status` | Joined H1-H6 model summary statuses for linked hypotheses. |
| `external_evidence_origin_status` | Provenance state for linked evidence layers, such as `not_configured`, `mock_fixture`, or real evidence states. |
| `real_claim_use_status` | Whether evidence can support real manuscript claims. |
| `allowed_current_claim_level` | Strongest currently allowed claim level. |
| `manuscript_use_status` | Practical use category, such as methods/resource, mock-only, hypothesis-only, cautious computational claim, or do-not-use. |
| `forbidden_claim_reason` | Why stronger wording is not allowed. |
| `next_action` | Action required to strengthen or unlock the claim. |

## Interpretation

`workflow_supported` supports methods or resource claims about the pipeline. It does not support biological conclusions by itself.

`mock_only_scaffold_support` means the mock workflow verifies plumbing only. It must not be used as real biological evidence.

`data_dependent_not_supported` means the claim remains a hypothesis or planned test until reviewed real evidence is configured and model rows pass.

`computational_inference` allows cautious wording only after real evidence and quantitative outputs are ready. Functional capsule specificity, anti-defense activity, productive infection, and therapeutic claims still require experimental validation.
