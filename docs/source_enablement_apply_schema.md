# Source Enablement Apply Schema

`scripts/apply_source_enablement.py` is an explicit, non-destructive helper for updating `config/source_imports.yaml` and `config/source_catalog.yaml` from `results/qc/source_enablement_plan.tsv`. It defaults to dry-run mode and only considers sources whose `enablement_status` is `ready_for_enablement` or `enabled_for_sample_build`. Empty reviewed-export skeletons are skipped. The config-driven workflow runs it without `--apply` to produce an auditable dry-run report every run.

## Command

Dry-run import enablement after reviewed exports pass validation:

```bash
python scripts/apply_source_enablement.py \
  --enablement-plan results/qc/source_enablement_plan.tsv \
  --imports-config config/source_imports.yaml \
  --catalog config/source_catalog.yaml \
  --report-output results/qc/source_enablement_apply_report.tsv \
  --enable-imports \
  --root .
```

Write changes only after reviewing the report:

```bash
python scripts/apply_source_enablement.py \
  --enablement-plan results/qc/source_enablement_plan.tsv \
  --imports-config config/source_imports.yaml \
  --catalog config/source_catalog.yaml \
  --report-output results/qc/source_enablement_apply_report.tsv \
  --enable-imports \
  --apply \
  --root .
```

Catalog source enablement should normally happen after imports have generated populated source manifests and those manifests have been reviewed:

```bash
python scripts/apply_source_enablement.py \
  --enablement-plan results/qc/source_enablement_plan.tsv \
  --imports-config config/source_imports.yaml \
  --catalog config/source_catalog.yaml \
  --report-output results/qc/source_enablement_apply_report.tsv \
  --enable-catalog \
  --apply \
  --root .
```

## `results/qc/source_enablement_apply_report.tsv`

| Column | Description |
| --- | --- |
| `source_id` | Source identifier from the enablement plan. |
| `enablement_status` | Planned state from `source_enablement_plan.tsv`. |
| `import_id` | Matching source import identifier. |
| `import_enabled_before` | Import enabled state before the planned change. |
| `import_enabled_after` | Import enabled state after the planned change or dry-run proposal. |
| `catalog_enabled_before` | Catalog enabled state before the planned change. |
| `catalog_enabled_after` | Catalog enabled state after the planned change or dry-run proposal. |
| `action_status` | `dry_run`, `updated`, `unchanged`, `skipped_not_ready`, or error/skipped status. |
| `message` | Human-readable reason for action or skip. |

## Safety Rules

- The helper does not download records and does not modify `data/raw/`.
- Without `--apply`, no YAML files are modified.
- With `--apply`, the script writes `.bak` backups beside modified YAML files.
- Catalog entries are not enabled unless the source is already `enabled_for_sample_build` or the enablement plan records a populated manifest.
- This helper cannot make unsupported biological claims; source validation, sample support, readiness, and H1-H6 traceability still determine whether the study can be interpreted.
