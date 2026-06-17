# Readiness Action Plan Schema

Stage 10 writes `results/validation/readiness_action_plan.tsv` after the manuscript-readiness audit. It converts failing readiness requirements into a ranked, file-specific action list so the transition from a validated scaffold to a populated biological study is auditable.

## `results/validation/readiness_action_plan.tsv`

One row per action group. Important columns:

| Column | Description |
| --- | --- |
| `action_id` | Stable action identifier. |
| `priority` | Lower numbers should be addressed first. |
| `action_area` | Short action category. |
| `requirement_ids` | Readiness requirement IDs addressed by the action. |
| `blocking_requirement_count` | Number of blocking readiness requirements in this action group. |
| `related_hypotheses` | H1-H6 hypotheses affected by the action. |
| `primary_artifacts_to_populate` | Files, directories, templates, or evidence IDs that need manual curation or external tool output. |
| `supporting_planning_files` | Existing workflow files that explain the handoff. |
| `command_hint` | Human-readable action guidance. |
| `validation_command` | Smallest useful command to rerun after completing the action. |
| `expected_downstream_outputs` | Outputs expected to change after the action is completed. |
| `readiness_blockers_addressed` | Readiness areas addressed by this action. |
| `rationale` | Why this action moves the manuscript-ready study forward. |

## `results/validation/readiness_action_report.tsv`

Run-level report with action count and blocking requirement count.

## Interpretation

This action plan is not biological evidence. It is an operational bridge from the current workflow state to manuscript-ready analyses. The real study remains unsupported while the action plan lists blocking source, sample-support, sequence, or evidence requirements. Source-curation actions include `results/qc/source_curation_work_order.tsv`, `results/qc/source_work_order_packet_manifest.tsv`, `results/qc/source_work_order_packets/`, `results/qc/source_work_order_acceptance.tsv`, `results/qc/source_post_acceptance_plan.tsv`, `results/qc/sample_support_by_hypothesis.tsv`, `results/qc/sample_support_summary.tsv`, `results/qc/sample_support_source_bridge.tsv`, `results/qc/sample_support_export_preflight.tsv`, and `results/qc/sample_support_curation_packet/` so missing H1-H6 support metrics are visible during A01 handoff.


## A01 source-curation prioritization

When source curation, source work-order acceptance, or sample support blocks manuscript readiness, action `A01` uses `results/qc/source_work_order_packet_manifest.tsv` and `results/qc/minimum_source_curation_plan.tsv` to keep `primary_artifacts_to_populate` focused on the first blocking work-order packets and highest-ranked missing reviewed exports. By default this highlights the top two ranked sources, while `supporting_planning_files` still points to the full minimum-source plan, hypothesis-source plan, source command sheet, column dictionary, sample-support audit outputs, and sample-support source bridge, and metric-specific source export preflight, and sample-support curation packet.

This keeps the immediate handoff actionable: complete the first listed work-order packet or highest-ranked export first, rerun the listed validation command, and let the regenerated acceptance and sample-support audits determine which H1-H6 blockers remain.
