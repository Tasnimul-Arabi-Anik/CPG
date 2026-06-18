# Source Manifest Drift Audit Schema

`scripts/audit_source_manifest_drift.py` enforces that `data/metadata/source_exports/` are authoritative. It regenerates enabled source manifests into a temporary directory using `scripts/import_source_manifests.py`, compares checksums with configured source manifests, and reports drift without editing either layer.

## Command

```bash
python scripts/audit_source_manifest_drift.py \
  --config config/source_imports.yaml \
  --drift-output results/qc/source_manifest_drift.tsv \
  --report-output results/qc/source_manifest_drift_report.tsv \
  --root .
```

The direct workflow runner executes this as `stage_0_source_manifest_drift` when `source_manifest_drift.enabled: true`.

## Drift Output

| Column | Description |
| --- | --- |
| `import_id` | Import identifier from `config/source_imports.yaml`. |
| `enabled` | Whether the import is enabled. |
| `input_path` | Source export path. |
| `output_path` | Configured normalized source manifest path. |
| `input_checksum` | SHA-256 checksum of the source export when present. |
| `current_output_checksum` | SHA-256 checksum of the configured source manifest. |
| `regenerated_output_checksum` | SHA-256 checksum of the temporary regenerated manifest. |
| `status` | `in_sync`, `manifest_drift`, `manifest_missing`, or `disabled_not_checked`. |
| `severity` | `info` or `error`. |
| `message` | Human-readable audit result. |

A `manifest_drift` error means the source export was changed without regenerating the source manifest, or the source manifest was edited manually. Regenerate with `stage_0_source_imports` rather than editing both files by hand.
