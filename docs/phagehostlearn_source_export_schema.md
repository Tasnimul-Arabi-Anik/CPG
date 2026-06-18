# PhageHostLearn Source Export Schema

`scripts/create_phagehostlearn_source_exports.py` builds disabled, reviewable source exports for the PhageHostLearn 2024 benchmark entities. It reads a reviewed local copy of `phage_host_interactions.csv` and, when available, `phages_genomes.zip` from Zenodo record `10.5281/zenodo.11061100`.

The script does not enable sources and does not approve mappings. It creates entity rows and source-to-canonical ID maps with `review_status=pending`, so the assay matrix cannot be imported as evidence until a reviewer approves the rows.

## Outputs

- `data/metadata/source_exports/phagehostlearn_2024_phages.tsv`
- `data/metadata/source_exports/phagehostlearn_2024_hosts.tsv`
- `data/metadata/assay_source_exports/phagehostlearn_2024_phage_id_map.tsv`
- `data/metadata/assay_source_exports/phagehostlearn_2024_host_id_map.tsv`
- `results/qc/phagehostlearn_2024_source_export_report.tsv`

The phage export includes deterministic benchmark genome IDs, source IDs in notes, genome length and GC when the phage FASTA member is present in the reviewed zip, and an expected raw path under `data/raw/external/`. Raw FASTA files remain untracked.

The host export includes deterministic benchmark host IDs and source IDs from the interaction matrix. Host genome archive inventory, K/O/ST typing, and local raw sequence acquisition remain pending review before these rows can be enabled.

## Review Boundary

Generated source rows are curation artifacts. Keep `phagehostlearn_2024_phages` and `phagehostlearn_2024_hosts` disabled in `config/source_imports.yaml` and `config/source_catalog.yaml` until:

- source IDs are checked against the Zenodo archives;
- local raw sequence acquisition paths and checksums are reviewed;
- host K/O/ST evidence is populated or explicitly marked unavailable;
- assay matrix map rows are changed from `pending` to `reviewed`, `accepted`, or `approved`.

Only after those steps should `scripts/normalize_assay_matrix.py` emit populated canonical assay rows for downstream H1/H3 receptor-layer tests. The PhageHostLearn spot-test matrix remains initial-interaction evidence, not productive-infection evidence for H4.

## Example

```bash
python scripts/create_phagehostlearn_source_exports.py \
  --matrix /path/to/phage_host_interactions.csv \
  --phage-zip /path/to/phages_genomes.zip \
  --phage-export-output data/metadata/source_exports/phagehostlearn_2024_phages.tsv \
  --host-export-output data/metadata/source_exports/phagehostlearn_2024_hosts.tsv \
  --phage-map-output data/metadata/assay_source_exports/phagehostlearn_2024_phage_id_map.tsv \
  --host-map-output data/metadata/assay_source_exports/phagehostlearn_2024_host_id_map.tsv \
  --report-output results/qc/phagehostlearn_2024_source_export_report.tsv \
  --root .
```
