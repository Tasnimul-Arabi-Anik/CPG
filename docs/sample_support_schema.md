# Sample Support Audit Schema

`scripts/audit_sample_support.py` checks whether the generated sample table has the minimum record types and host metadata needed to treat each H1-H6 analysis as data-supported. It is an early curation audit, not a biological result.

## Inputs

- `--samples`: generated or configured sample TSV.
- `--thresholds`: `config/thresholds.yaml`, section `sample_support`.

## Thresholds

The current defaults are intentionally minimal smoke-test thresholds:

- `min_total_records`
- `min_cultured_phages`
- `min_host_genomes`
- `min_prophages`
- `min_k_typed_records`
- `min_o_typed_records`
- `min_st_typed_records`
- `min_phage_rows_with_host_metadata`

Raise these thresholds before manuscript-scale interpretation. Defaults of `1` only distinguish an empty scaffold from a minimally populated handoff.

## Outputs

### `sample_support_by_hypothesis.tsv`

Columns:

- `hypothesis`: H1-H6.
- `support_status`: `ready_minimum_sample_support` or `blocked_minimum_sample_support`.
- `sample_rows`: total rows in the audited sample table.
- `cultured_phage_rows`: rows with `record_type` equal to `phage` or `cultured_phage`.
- `prophage_rows`: rows with `record_type` equal to `prophage`.
- `host_rows`: rows with `record_type` equal to `host`.
- `k_typed_rows`: rows with non-missing `K_type`.
- `o_typed_rows`: rows with non-missing `O_type`.
- `st_typed_rows`: rows with non-missing `ST`.
- `phage_rows_with_host_metadata`: cultured phage rows with isolation host, host species, or host strain metadata.
- `required_minima`: configured requirements used for the hypothesis.
- `missing_support`: observed/configured counts for unmet requirements, or `NA`.
- `next_action`: curation action required when blocked.

### `sample_support_summary.tsv`

Columns:

- `metric`: threshold key from `sample_support`.
- `value`: observed count.
- `threshold`: configured minimum.
- `status`: `pass` or `fail`.
- `notes`: human-readable count summary.

### `sample_support_report.tsv`

Columns:

- `severity`: `info` or `warning`.
- `item`: report item.
- `message`: concise audit summary.

## Interpretation

A `ready_minimum_sample_support` row means the sample table satisfies configured minimum counts for that hypothesis. It does not mean the statistical test is powered, biologically valid, or manuscript-ready. A `blocked_minimum_sample_support` row means source exports or source catalog enablement must be completed before the corresponding hypothesis can be interpreted from real data.
