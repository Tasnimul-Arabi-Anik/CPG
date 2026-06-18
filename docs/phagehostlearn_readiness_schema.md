# PhageHostLearn Readiness Audit Schema

`scripts/audit_phagehostlearn_readiness.py` audits whether the PhageHostLearn benchmark artifacts are ready to be enabled and imported as canonical phage-host assay rows.

The audit is deliberately conservative. Pending source exports and mapping rows are useful curation artifacts, but they block assay import until reviewed. The audit also detects source imports or catalog entries that are enabled before map review is complete.

## Inputs

Default inputs:

- `data/metadata/source_exports/phagehostlearn_2024_phages.tsv`
- `data/metadata/source_exports/phagehostlearn_2024_hosts.tsv`
- `data/metadata/assay_source_exports/phagehostlearn_2024_phage_id_map.tsv`
- `data/metadata/assay_source_exports/phagehostlearn_2024_host_id_map.tsv`
- `data/metadata/assay_source_exports/reviewed_klebsiella_phage_host_assays.tsv`
- `config/source_imports.yaml`
- `config/source_catalog.yaml`

## Readiness Output

The readiness table columns are:

```text
check_id	area	status	severity	blocking_for_assay_import	evidence_path	evidence_summary	next_action
```

Important checks:

- `PHL001`: benchmark phage entity export exists and has source IDs.
- `PHL002`: benchmark host entity export exists and records host feature missingness.
- `PHL003`: phage source-to-canonical map covers exported source IDs and has reviewed rows.
- `PHL004`: host source-to-canonical map covers exported source IDs and has reviewed rows.
- `PHL005`: benchmark source imports/catalog entries are not enabled before review.
- `PHL006`: canonical assay export is populated only after maps are reviewed and entities are enabled.

## Report Output

The report table has:

```text
severity	item	message
```

A warning report means the benchmark path is still blocked by review or missing evidence. It does not indicate code failure.

## Example

```bash
python scripts/audit_phagehostlearn_readiness.py \
  --readiness-output results/qc/phagehostlearn_2024_readiness.tsv \
  --report-output results/qc/phagehostlearn_2024_readiness_report.tsv \
  --root .
```

Only when all blocking rows are resolved should the benchmark source imports/catalog entries be enabled and the matrix normalized into populated `phage_host_assays.tsv` rows.
