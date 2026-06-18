# Defense External Evidence Normalization Schema

`scripts/normalize_defense_external_evidence.py` converts reviewed host-defense and phage anti-defense result tables into the optional evidence TSV schemas consumed by Stage 6. It does not run DefenseFinder, PADLOC, HMM/profile searches, structure searches, or anti-defense databases.

Implemented command pattern:

```bash
python scripts/normalize_defense_external_evidence.py \
  --host-defense-input results/external/defensefinder/host_defense.tsv \
  --host-defense-format defensefinder_tsv \
  --host-defense-output data/metadata/external_evidence/host_defense_systems.tsv \
  --phage-antidefense-input results/external/antidefense/reviewed_hits.tsv \
  --phage-antidefense-format reviewed_hits_tsv \
  --phage-antidefense-output data/metadata/external_evidence/phage_antidefense_candidates.tsv \
  --report-output results/qc/normalize_defense_external_evidence_report.tsv
```

Supported input format labels:

- `generic_tsv`
- `defensefinder_tsv`
- `padloc_tsv`
- `reviewed_hits_tsv` for phage anti-defense hits

The current parser is alias-based TSV normalization. It accepts common column names from reviewed DefenseFinder/PADLOC-style outputs and curated anti-defense hit tables, then writes stable workflow input columns. Host-defense and phage anti-defense outputs can be written independently, which avoids overwriting one reviewed target TSV while normalizing the other.

## Host Defense Output

Default target path: `data/metadata/external_evidence/host_defense_systems.tsv`.

| Column | Description |
| --- | --- |
| `system` | Defense system name reported by the reviewed tool/output. |
| `type` | Normalized defense class where possible, for example CRISPR-Cas, restriction-modification, BREX, DISARM, Abi, toxin-antitoxin, retrons, or nuclease-based defense. |
| `sample` | Host identifier copied from the reviewed input. |
| `genome_id` | Host genome identifier copied from the reviewed input. |
| `host_genome_id` | Host genome identifier used by Stage 6. |
| `subtype` | Optional defense subtype. |
| `gene_count` | Optional number of genes/components in the system. |
| `genes` | Optional gene/protein/component identifiers. |
| `contig` | Optional contig or replicon identifier. |
| `start` | Optional start coordinate. |
| `end` | Optional end coordinate. |
| `evidence_source` | Reviewed tool, database, file, or provenance label. |
| `notes` | Provenance, reviewer, snapshot, or uncertainty note. |

## Phage Anti-Defense Output

Default target path: `data/metadata/external_evidence/phage_antidefense_candidates.tsv`.

| Column | Description |
| --- | --- |
| `antidefense_class` | Reviewed or inferred anti-defense/counter-defense class. |
| `phage_genome_id` | Phage/prophage genome identifier. If missing, it can be derived from `annotation_gene_id` values formatted as `phage|gene`. |
| `annotation_gene_id` | Stable Stage 3 annotation gene identifier. |
| `gene_id` | Optional gene/protein/locus identifier. |
| `product` | Reviewed product, hit, or profile description. |
| `target_defense_system` | Defense system expected to be targeted. |
| `evidence_type` | Evidence class, such as reviewed profile hit, reviewed structural hit, or curated table. |
| `confidence_score` | Optional score, probability, E-value, or confidence label. |
| `evidence_source` | Reviewed tool, database, file, or provenance label. |
| `notes` | Provenance, reviewer, snapshot, or uncertainty note. |

Header-only outputs are valid handoff artifacts but are not accepted production evidence.
