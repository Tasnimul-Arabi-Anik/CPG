# Tool Availability Audit Schema

`scripts/audit_tool_availability.py` checks command availability for workflow-core tools and planned external bioinformatics tools listed in `config/tools.yaml`. It does not install tools and does not download databases.

## Command

```bash
python scripts/audit_tool_availability.py \
  --tools-config config/tools.yaml \
  --availability-output results/qc/tool_availability.tsv \
  --report-output results/qc/tool_audit_report.tsv
```

The direct workflow runner executes this as `stage_0_tool_audit` before source imports and source-catalog auditing.

## Config

Tool audit entries live under `tool_audit.tools` in `config/tools.yaml`. Each entry supports:

| Field | Description |
| --- | --- |
| `tool_id` | Stable tool identifier. |
| `stage` | Workflow stage that will eventually use the tool. |
| `purpose` | Short reason the tool is listed. |
| `command` | Command name checked with `PATH`. |
| `version_args` | Optional list of arguments for a version check. |
| `required_for_current_workflow` | If true, a missing command is an error. If false, it is a warning. |
| `install_hint` | Human-readable install or provenance note. |
| `notes` | Additional caveats. |

## Availability Output

`tool_availability.tsv` columns:

| Column | Description |
| --- | --- |
| `tool_id` | Stable tool identifier. |
| `stage` | Workflow stage associated with the tool. |
| `purpose` | Tool purpose. |
| `command` | Command checked. |
| `required_for_current_workflow` | Whether missing command is an error. |
| `availability_status` | `available`, `missing`, or `not_configured`. |
| `executable_path` | Resolved path from `PATH`, if available. |
| `version_command` | Version command run, if any. |
| `version_status` | `ok`, `failed`, or `not_checked`. |
| `version_output` | Condensed version-command output. |
| `install_hint` | Install or provenance note from config. |
| `notes` | Additional notes from config. |

## Report Output

`tool_audit_report.tsv` columns:

| Column | Description |
| --- | --- |
| `severity` | `info`, `warning`, or `error`. |
| `item` | Tool identifier or audit component. |
| `message` | Availability message. |

## Interpretation

Missing planned tools are warnings until their workflow stage directly invokes them. This keeps the current repository runnable through the direct Python workflow while preserving an explicit record of what must be installed before production annotation, structural search, K/O typing, and defense-system annotation.
