# PhageHostLearn Source Export Schema

`scripts/create_phagehostlearn_source_exports.py` builds reviewable source exports for the PhageHostLearn 2024 benchmark entities. It reads a reviewed local copy of `phage_host_interactions.csv` and, when available, `phages_genomes.zip` and `klebsiella_genomes.zip` from Zenodo record `10.5281/zenodo.11061100`.

The script does not approve mappings. It creates entity rows and source-to-canonical ID maps with pending review status; only rows later marked `reviewed`, `accepted`, or `approved` are imported by the review-filtered source importer and matrix normalizer.

## Outputs

- `data/metadata/source_exports/phagehostlearn_2024_phages.tsv`
- `data/metadata/source_exports/phagehostlearn_2024_hosts.tsv`
- `data/metadata/assay_source_exports/phagehostlearn_2024_phage_id_map.tsv`
- `data/metadata/assay_source_exports/phagehostlearn_2024_host_id_map.tsv`
- `results/qc/phagehostlearn_2024_source_export_report.tsv`

The phage export includes deterministic benchmark genome IDs, source IDs in notes, genome length and GC when the phage FASTA member is present in the reviewed zip, and a reviewed ZIP-member raw path. Raw FASTA files remain untracked.

The host export includes deterministic benchmark host IDs and source IDs from the interaction matrix. When the reviewed host archive is supplied, rows with matching FASTA members receive `data/metadata/external/phagehostlearn/klebsiella_genomes.zip::fasta_files/<host>.fasta` raw paths. K/O/ST/AMR/virulence remain separate production evidence layers.

## Review Boundary

Generated source rows are curation artifacts. `config/source_imports.yaml` uses `required_note_review_statuses` so only reviewed source-identity rows are imported into source manifests; pending rows remain excluded even when the PhageHostLearn source entries are enabled. Map rows must also be changed from `pending` to `reviewed`, `accepted`, or `approved` before `scripts/normalize_assay_matrix.py` can emit populated canonical assay rows for downstream H1/H3 receptor-layer tests. K/O/ST, local FASTA unpacking, and productive-infection evidence remain separate review steps. The PhageHostLearn spot-test matrix remains initial-interaction evidence, not productive-infection evidence for H4.

## Example

```bash
python scripts/create_phagehostlearn_source_exports.py \
  --matrix /path/to/phage_host_interactions.csv \
  --phage-zip /path/to/phages_genomes.zip \
  --host-zip /path/to/klebsiella_genomes.zip \
  --phage-export-output data/metadata/source_exports/phagehostlearn_2024_phages.tsv \
  --host-export-output data/metadata/source_exports/phagehostlearn_2024_hosts.tsv \
  --phage-map-output data/metadata/assay_source_exports/phagehostlearn_2024_phage_id_map.tsv \
  --host-map-output data/metadata/assay_source_exports/phagehostlearn_2024_host_id_map.tsv \
  --report-output results/qc/phagehostlearn_2024_source_export_report.tsv \
  --root .
```
