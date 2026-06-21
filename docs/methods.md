# Methods

## Workflow Profiles and Config Resolution

Workflow execution uses `scripts/workflow_config.py` to resolve `extends:` inheritance and deep-merge profile overlays into `config/workflow.base.yaml`. `config/workflow.mock.yaml`, `config/workflow.seed.yaml`, and `config/workflow.production.yaml` define profile semantics, result/log namespaces, and evidence requirements without duplicating the full workflow. `config/workflow.yaml` currently extends the seed profile as the default local workflow.

`stage_0_profile_requirements` validates resolved profile semantics before downstream stages run. Mock and seed profiles can run without production evidence and keep `allows_biological_claims: false`. The production profile is fail-closed: it reports blocking errors until required production evidence inputs and populated tested phage-host assay outcomes exist.

`workflow_run_report.tsv` records profile name, evidence class, resolved config SHA-256, git commit, and run start time so generated outputs can be traced to the profile and config state that produced them.

## Tool Availability Audit

Before source import and dataset curation, `scripts/audit_tool_availability.py` checks command availability for workflow-core tools and planned external bioinformatics tools listed in `config/tools.yaml`. Missing specialized tools are warnings unless they are marked required for the current workflow; this keeps the direct Python workflow runnable while making production tool gaps explicit.

Implemented command:

```bash
python scripts/audit_tool_availability.py \
  --tools-config config/tools.yaml \
  --availability-output results/qc/tool_availability.tsv \
  --report-output results/qc/tool_audit_report.tsv
```

Output schemas are documented in `docs/tool_availability_schema.md`.

## Source Query Planning

Before source import, `scripts/plan_source_queries.py` records the intended public-source queries and reviewed local export paths for INPHARED, NCBI Virus/GenBank/RefSeq, literature-linked cultured phages, prophages, optional metagenomic contigs, and host genomes. This stage writes `source_query_plan.tsv` and `source_query_report.tsv`; it does not call public services and does not download genomes.

Implemented command:

```bash
python scripts/plan_source_queries.py   --queries-config config/source_queries.yaml   --catalog config/source_catalog.yaml   --imports-config config/source_imports.yaml   --plan-output results/qc/source_query_plan.tsv   --report-output results/qc/source_query_report.tsv
```

Output schemas are documented in `docs/source_query_plan_schema.md`.

## Source Export Templates

After source-query planning, `scripts/create_source_export_templates.py` creates header-only reviewed-export templates under `results/qc/source_export_templates/`. The templates use the expected columns and required identity columns from the query plan, but they are not production inputs and are not written under `data/metadata/source_exports/`.

Implemented command:

```bash
python scripts/create_source_export_templates.py   --query-plan results/qc/source_query_plan.tsv   --templates-dir results/qc/source_export_templates   --manifest-output results/qc/source_export_template_manifest.tsv   --report-output results/qc/source_export_template_report.tsv
```

Output schemas are documented in `docs/source_export_template_schema.md`.

## Source Export Bootstrap

After source-export templates are generated, `scripts/bootstrap_source_exports.py` can create non-overwriting header-only TSV skeletons at the configured reviewed-export paths under `data/metadata/source_exports/`. This is an explicit curation aid, not biological data, and it is not run automatically by the workflow. The resulting files must be populated with reviewed public-source rows before source validation, import, source enablement, and H1-H6 interpretation can pass.

Implemented command:

```bash
python scripts/bootstrap_source_exports.py \
  --query-plan results/qc/source_query_plan.tsv \
  --template-manifest results/qc/source_export_template_manifest.tsv \
  --report-output results/qc/source_export_bootstrap_report.tsv \
  --root .
```

Output schemas are documented in `docs/source_export_bootstrap_schema.md`.

## Source Export Validation

Before source import, `scripts/validate_source_exports.py` checks reviewed exports against the source-query and template expectations. Missing exports and header-only skeleton exports are warnings so scaffold runs remain possible. Populated exports with missing expected columns, missing identity values, or duplicate identity values are blocking errors.

Implemented command:

```bash
python scripts/validate_source_exports.py   --query-plan results/qc/source_query_plan.tsv   --template-manifest results/qc/source_export_template_manifest.tsv   --validation-output results/qc/source_export_validation.tsv   --report-output results/qc/source_export_validation_report.tsv   --root .
```

Output schemas are documented in `docs/source_export_validation_schema.md`. `scripts/self_test_source_export_validation.py` runs validator regression scenarios for valid rows, malformed year/GC/lifestyle fields, missing identity values, and provenance warnings; its schema is documented in `docs/source_export_validation_self_test_schema.md`. Populated reviewed exports are also checked for numeric `year`, `genome_length`, and `gc_percent` values, controlled `phage_lifestyle` values, and missing notes/provenance warnings.

## Source Manifest Import

Before source-catalog auditing, `scripts/import_source_manifests.py` can normalize local public metadata exports into source-manifest TSVs. This importer is configured by `config/source_imports.yaml`, writes `source_import_report.tsv`, and does not download genomes or modify `data/raw/`. The real-study imports are disabled until local exports are reviewed; the mock workflow enables a fixture import for smoke testing.

Implemented command:

```bash
python scripts/import_source_manifests.py \
  --config config/source_imports.yaml \
  --report-output results/qc/source_import_report.tsv
```

## Source Catalog Readiness Audit

Before sample-table construction, `scripts/audit_source_catalog.py` classifies each configured source as planned, ready, ready with defaults, populated but disabled, or invalid. The audit writes `source_catalog_readiness.tsv` and `source_catalog_audit_report.tsv`, which make source-manifest curation decisions explicit. Populated source manifests must contain at least one configured identity column; by default this is `genome_id`, `accession`, or `raw_sequence_path`.

## Source Enablement Apply Helper

After reviewed exports are populated and `scripts/plan_source_enablement.py` reports sources as `ready_for_enablement`, `scripts/apply_source_enablement.py` can dry-run or apply the corresponding YAML changes. The helper updates only sources that are ready according to the plan, skips empty exports, writes a report under `results/qc/`, and requires `--apply` before modifying `config/source_imports.yaml` or `config/source_catalog.yaml`. Catalog entries are enabled only after a populated manifest is recorded or the source is already classified as `enabled_for_sample_build`.

The config-driven workflow runs this helper in dry-run mode. Standalone dry-run command:

```bash
python scripts/apply_source_enablement.py \
  --enablement-plan results/qc/source_enablement_plan.tsv \
  --imports-config config/source_imports.yaml \
  --catalog config/source_catalog.yaml \
  --report-output results/qc/source_enablement_apply_report.tsv \
  --enable-imports \
  --root .
```

Output schemas are documented in `docs/source_enablement_apply_schema.md`.

## Source-Manifest Sample Builder

Source manifests are configured in `config/source_catalog.yaml` and merged into the Stage 1 sample schema by `scripts/build_samples_from_sources.py`. This step is disabled in the real workflow until source manifests are added, and enabled in `config/workflow.mock.yaml` for smoke testing.

Implemented command:

```bash
python scripts/build_samples_from_sources.py \
  --catalog config/source_catalog.yaml \
  --output-samples config/samples.tsv \
  --report-output results/qc/sample_source_report.tsv
```

The builder records provenance, missing source files, duplicate genome IDs, missing recommended columns, and identity-rule failures in `sample_source_report.tsv`; Stage 1 still performs formal sample-table validation. Missing recommended columns are filled from source defaults or `NA`, but sources with data rows and no recognized identity column are rejected.

The default source catalog includes disabled placeholders for INPHARED, NCBI Virus, literature-linked cultured phages, prophages, metagenomic discovery contigs, and host genomes. These entries should be enabled only after their source TSVs are populated and reviewed.

The initial NCBI Virus/GenBank/RefSeq cultured-phage source unlock uses a metadata-only seed batch from NCBI E-utilities with the query `"Klebsiella phage"[Title] AND "complete genome"[Title]`. Rows are stored in `data/metadata/source_exports/ncbi_virus_klebsiella_phages.tsv`, imported into `data/metadata/source_manifests/ncbi_virus_klebsiella_phages.tsv`, and enabled only after source-export validation and manifest review. Local FASTA paths are intentionally not populated by this source step; accession-backed sequence retrieval is deferred to the sequence fetch manifest so raw-data acquisition remains explicit and reviewable.

Regeneration command for the current metadata-only seed export:

```bash
python scripts/build_ncbi_klebsiella_phage_export.py \
  --retmax 10 \
  --date 2026-06-17 \
  --output data/metadata/source_exports/ncbi_virus_klebsiella_phages.tsv \
  --report-output data/metadata/source_exports/ncbi_virus_klebsiella_phages_report.tsv
```

## Sample Support Audit

After generated sample-table construction and source-overlap auditing, `scripts/audit_sample_support.py` checks whether the current sample table satisfies minimum configured support for H1-H6. The audit counts cultured phages, prophages, host genomes, K/O/ST-typed records, and phage rows with host metadata. It writes a per-hypothesis support table, a metric summary, and a concise report. This stage prevents empty or weakly populated real-data runs from being interpreted as biological support for the hypotheses.

Implemented command:

```bash
python scripts/audit_sample_support.py \
  --samples results/source_builder/samples.tsv \
  --thresholds config/thresholds.yaml \
  --hypothesis-output results/qc/sample_support_by_hypothesis.tsv \
  --summary-output results/qc/sample_support_summary.tsv \
  --report-output results/qc/sample_support_report.tsv
```

Output schemas are documented in `docs/sample_support_schema.md`.

`scripts/plan_sample_support_sources.py` maps failed sample-support metrics to the ranked source exports and columns most likely to satisfy them. This gives the source curator a metric-specific handoff before downstream sequence or evidence generation.

Implemented command:

```bash
python scripts/plan_sample_support_sources.py \
  --sample-support-summary results/qc/sample_support_summary.tsv \
  --minimum-source-plan results/qc/minimum_source_curation_plan.tsv \
  --column-dictionary results/qc/source_export_column_dictionary.tsv \
  --bridge-output results/qc/sample_support_source_bridge.tsv \
  --report-output results/qc/sample_support_source_bridge_report.tsv
```

Bridge output schemas are documented in `docs/sample_support_source_bridge_schema.md`.

`preflight_sample_support_exports.py` checks whether source exports named by the bridge exist, contain metric-critical columns, and have at least one row with enough populated values to satisfy each metric/source combination.

Implemented command:

```bash
python scripts/preflight_sample_support_exports.py \
  --bridge results/qc/sample_support_source_bridge.tsv \
  --preflight-output results/qc/sample_support_export_preflight.tsv \
  --report-output results/qc/sample_support_export_preflight_report.tsv \
  --root .
```

Preflight schemas are documented in `docs/sample_support_export_preflight_schema.md`.

## Source Readiness Dashboard

`scripts/build_source_readiness_dashboard.py` merges export validation, source enablement planning, source enablement dry-run status, and sample-support preflight into `results/qc/source_readiness_dashboard.tsv`. This is the preferred source-curation handoff because it ranks each source, reports blocked metrics, and lists the exact fields to populate.

Implemented command:

```bash
python scripts/build_source_readiness_dashboard.py \
  --minimum-source-plan results/qc/minimum_source_curation_plan.tsv \
  --source-export-validation results/qc/source_export_validation.tsv \
  --source-enablement-plan results/qc/source_enablement_plan.tsv \
  --source-enablement-apply results/qc/source_enablement_apply_report.tsv \
  --sample-support-preflight results/qc/sample_support_export_preflight.tsv \
  --dashboard-output results/qc/source_readiness_dashboard.tsv \
  --report-output results/qc/source_readiness_dashboard_report.tsv
```

Output schemas are documented in `docs/source_readiness_dashboard_schema.md`.

## Source Curation Work Orders

`build_source_curation_work_order.py` converts the source readiness dashboard into curation work orders that include target reviewed-row counts, required fields, and the focused validation command to run after source rows are added. This makes the next source-curation action explicit without treating unreviewed rows as evidence.

Implemented command:

```bash
python scripts/build_source_curation_work_order.py \
  --dashboard results/qc/source_readiness_dashboard.tsv \
  --sample-support-summary results/qc/sample_support_summary.tsv \
  --work-order-output results/qc/source_curation_work_order.tsv \
  --report-output results/qc/source_curation_work_order_report.tsv
```

Output schemas are documented in `docs/source_curation_work_order_schema.md`.

## Source Work-Order Packets

`create_source_work_order_packets.py` renders each source curation work order as a Markdown packet under `results/qc/source_work_order_packets/`. Each packet includes the export path, minimum row target, required fields, blocked metrics, source query context, starter-template links, identity fields, row-level curation checklist, export header to preserve, provenance boundaries, and validation commands.

Implemented command:

```bash
python scripts/create_source_work_order_packets.py \
  --work-orders results/qc/source_curation_work_order.tsv \
  --starter-kit-manifest results/qc/source_export_starter_kit_manifest.tsv \
  --dashboard results/qc/source_readiness_dashboard.tsv \
  --output-dir results/qc/source_work_order_packets \
  --manifest-output results/qc/source_work_order_packet_manifest.tsv \
  --report-output results/qc/source_work_order_packet_report.tsv \
  --root .
```

Output schemas are documented in `docs/source_work_order_packet_schema.md`.

## Source Work-Order Acceptance

`create_source_curation_issue_bodies.py` renders current work orders as GitHub-ready issue bodies under `results/qc/github_issue_bodies/`, allowing source-curation tasks to be delegated without losing the validation commands or claim boundaries.

`check_source_work_order_acceptance.py` verifies whether each current work order is satisfied by reviewed export rows. It checks export existence, required columns, required field values, minimum row counts, raw sequence path lint, and provenance-note lint, then writes `results/qc/source_work_order_acceptance.tsv`. `scripts/self_test_source_work_order_acceptance.py` regression-tests those acceptance and lint cases with temporary fixtures only.

Implemented command:

```bash
python scripts/check_source_work_order_acceptance.py \
  --work-orders results/qc/source_curation_work_order.tsv \
  --acceptance-output results/qc/source_work_order_acceptance.tsv \
  --report-output results/qc/source_work_order_acceptance_report.tsv \
  --root .
```

Output schemas are documented in `docs/source_work_order_acceptance_schema.md`.

## Source Post-Acceptance Transition Planning

`plan_source_post_acceptance.py` links accepted work orders to the next source transition command. It separates pending curation from import enablement, import execution, catalog enablement, and downstream sample-support reruns.

Implemented command:

```bash
python scripts/plan_source_post_acceptance.py \
  --acceptance results/qc/source_work_order_acceptance.tsv \
  --enablement-plan results/qc/source_enablement_plan.tsv \
  --enablement-apply results/qc/source_enablement_apply_report.tsv \
  --plan-output results/qc/source_post_acceptance_plan.tsv \
  --report-output results/qc/source_post_acceptance_report.tsv
```

Output schemas are documented in `docs/source_post_acceptance_schema.md`.

`create_sample_support_curation_packet.py` renders the bridge and preflight outputs as Markdown packets under `results/qc/sample_support_curation_packet/`, giving curators a source-specific checklist for blocked metrics and fields.

Implemented command:

```bash
python scripts/create_sample_support_curation_packet.py \
  --bridge results/qc/sample_support_source_bridge.tsv \
  --preflight results/qc/sample_support_export_preflight.tsv \
  --output-dir results/qc/sample_support_curation_packet \
  --manifest-output results/qc/sample_support_curation_packet_manifest.tsv \
  --report-output results/qc/sample_support_curation_packet_report.tsv \
  --root .
```

Packet schemas are documented in `docs/sample_support_curation_packet_schema.md`.

## Config-Driven Execution

Primary workflow paths are configured in `config/workflow.yaml`. The direct runner executes all implemented stages in dependency order and writes per-stage logs under `logs/`.

Implemented command:

```bash
python scripts/run_workflow.py --config config/workflow.yaml
```

This runner is intended for local validation and environments where Snakemake is unavailable. The repository `Snakefile` delegates to this runner so Snakemake and the direct workflow use the same stage order and config paths.

A populated fixture-backed smoke test uses the same runner and writes under `results/mock/`:

```bash
python scripts/run_workflow.py --config config/workflow.mock.yaml
```


## Phage-Host Assay Source Import

Tested phage-host outcomes are handled as a separate reviewed source layer, not as ordinary phage or host metadata. `scripts/import_phage_host_assays.py` reads `config/assay_imports.yaml`, normalizes reviewed assay source exports, and writes profile-local canonical tables under `results/<profile>/metadata/`. The same step can derive `tested_assay_host` relationship rows, but those relationships remain assay provenance rather than inferred infectivity labels.

Header-only assay exports are valid for mock and seed plumbing, but they do not support H1/H3/H4 biological claims. Populated rows must explicitly distinguish `tested=true` negatives from untested pairs, identify the study/panel/assay type, and carry a source reference. The canonical imported tables are checked again by `scripts/validate_phage_host_assays.py` before model or readiness audits consume them.

Reviewed host-by-phage matrices are normalized before import with `scripts/normalize_assay_matrix.py` and `config/assay_matrix_sources.yaml`. The PhageHostLearn 2024 Zenodo matrix has been normalized into a reviewed subset export for the seed workflow; the matrix-normalization stage remains disabled by default so clean-checkout runs do not require local Zenodo CSV files or regenerate reviewed artifacts implicitly. Matrix blanks are treated as untested cells, explicit `1/0` values become spot-test positive or tested-negative rows, and unresolved entity mappings are reported and skipped rather than silently entering the assay table. `scripts/create_assay_matrix_mapping_templates.py` extracts matrix source IDs into pending review templates; pending mappings are ignored until a reviewer marks them reviewed. `scripts/create_phagehostlearn_source_exports.py` creates benchmark phage and host source exports with deterministic canonical IDs, and `config/source_imports.yaml` uses `required_note_review_statuses` so only reviewed source-identity rows enter source manifests. The current seed path imports reviewed PhageHostLearn spot-test rows as initial-interaction evidence only; it does not provide productive-infection evidence for H4.

`data/metadata/external/phagehostlearn/phagehostlearn_file_manifest.tsv` records the expected local Zenodo files used by the benchmark path, including direct retrieval URLs, advisory commands, byte counts, MD5 values, and SHA-256 values when local review has been completed. The generic workflow stage `stage_0_assay_dataset_audit` currently calls the PhageHostLearn adapter `scripts/audit_phagehostlearn_dataset.py` for file integrity, matrix ID coverage, archive membership, canonical ID mappings, assay/export parity, optional RBPbase/Locibase metadata availability, assay-import readiness, and model-feature readiness. This audit deliberately separates identity readiness, assay readiness, feature readiness, and model readiness: missing K/O/ST, RBPbase, Locibase, defense, or counter-defense evidence must not block preservation of observed tested assay outcomes. Schema details are in `docs/phagehostlearn_dataset_audit_schema.md`.

`scripts/build_phagehostlearn_receptor_support.py` normalizes reviewed local PhageHostLearn RBPbase and Locibase files into tracked bridge-evidence tables under `data/metadata/external_evidence/`. The seed profile consumes `phagehostlearn_rbpbase_receptor_support.tsv` and `phagehostlearn_locibase_host_locus_support.tsv` as H1b bridge metadata features. These features are seed metadata coverage only: RBPbase scores are not structural/domain annotation, and Locibase fingerprints are not Kaptive/Kleborate K/O/ST typing. Column contracts are documented in `docs/phagehostlearn_receptor_support_schema.md`.

## Stage 1: Dataset Curation

Input records are listed in `config/samples.tsv`. The manifest builder validates required columns, unique genome identifiers, record types, numeric genome length, GC percentage, and optional local raw-sequence paths.

Implemented command:

```bash
python scripts/00_build_phage_manifest.py \
  --input config/samples.tsv \
  --manifest-output results/qc/phage_genome_manifest.tsv \
  --report-output results/qc/manifest_validation_report.tsv \
  --excluded-output results/qc/excluded_genomes.tsv
```

The script does not download genomes and does not modify `data/raw/`.

## Stage 1b: Local Genome Sequence QC

The sequence QC script reads local FASTA files referenced by `raw_sequence_path` in the Stage 1 manifest. It computes sequence count, total length, observed GC percentage, N-content, ambiguous-base content, and metadata agreement against configured thresholds. Phage-like records use `genome_qc.max_genome_length_bp`; host genome rows use `genome_qc.max_host_genome_length_bp` when present so complete bacterial assemblies are not incorrectly failed by phage-length limits. Records without local sequence files are retained and reported so metadata-only curation remains possible, but final genome-level analyses should use rows with passing sequence QC.

Implemented command:

```bash
python scripts/00_qc_genome_sequences.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --thresholds config/thresholds.yaml \
  --qc-output results/qc/genome_sequence_qc.tsv \
  --report-output results/qc/genome_sequence_qc_report.tsv \
  --root .
```

Output schemas are documented in `docs/genome_sequence_qc_schema.md`.

## Stage 1c: Sequence Fetch Manifest

After sequence acquisition planning, `scripts/create_sequence_fetch_manifest.py` creates `results/qc/sequence_fetch_manifest.tsv` and a review-only `results/qc/sequence_fetch_commands.sh`. `scripts/create_sequence_fetch_review_packet.py` also writes `results/qc/sequence_fetch_review_packet.md`, which summarizes ready accession-backed commands, target paths, and post-acquisition checks for manual review. These scripts are never executed as download steps by the workflow. They exist to make accession-backed retrieval auditable before any network download or local FASTA placement.

Implemented command:

```bash
python scripts/create_sequence_fetch_manifest.py \
  --sequence-plan results/qc/sequence_acquisition_plan.tsv \
  --manifest-output results/qc/sequence_fetch_manifest.tsv \
  --commands-output results/qc/sequence_fetch_commands.sh \
  --report-output results/qc/sequence_fetch_report.tsv \
  --root .
```

Output schemas are documented in `docs/sequence_fetch_manifest_schema.md`.

## Stage 1d: Production Evidence Handoff

After external-evidence planning, `scripts/create_production_evidence_handoff.py` writes `results/qc/production_evidence_handoff.md`. This generated handoff distinguishes current bridge evidence from production-grade external evidence expected for manuscript claims, including Pharokka/PHROGs annotation, VIRIDIC/Mash-style similarity, RBP domain/structural evidence, Kleborate/Kaptive host features, and DefenseFinder/PADLOC host-defense calls.

Implemented command:

```bash
python scripts/create_production_evidence_handoff.py \
  --external-evidence-plan results/qc/external_evidence_plan.tsv \
  --unlock-plan results/qc/external_evidence_unlock_plan.tsv \
  --output results/qc/production_evidence_handoff.md \
  --report-output results/qc/production_evidence_handoff_report.tsv
```

## Stage 1e: Pipeline Efficiency Audit

`scripts/audit_pipeline_efficiency.py` writes `results/validation/pipeline_efficiency_audit.tsv` and `results/validation/pipeline_efficiency_report.tsv`. This reviewer-facing audit checks that the workflow uses staged reviewed source layers rather than indiscriminate scraping, keeps metagenomic discovery contigs separate from the primary atlas, enforces Klebsiella/phage import filters, preserves a raw-data review boundary, keeps dereplication thresholds in config, runs source-overlap auditing, separates bridge evidence from production external evidence, externalizes compute-heavy production tools, and stages sequence acquisition before genome-level claims.

The audit supports workflow-design and resource-readiness claims only. It does not support biological conclusions unless downstream source, sequence, external-evidence, modeling, readiness, and claim-support audits pass.

Implemented command:

```bash
python scripts/audit_pipeline_efficiency.py \
  --workflow-config config/workflow.yaml \
  --source-catalog config/source_catalog.yaml \
  --source-imports config/source_imports.yaml \
  --thresholds config/thresholds.yaml \
  --external-evidence-plan results/qc/external_evidence_plan.tsv \
  --sequence-acquisition-plan results/qc/sequence_acquisition_plan.tsv \
  --output results/validation/pipeline_efficiency_audit.tsv \
  --report-output results/validation/pipeline_efficiency_report.tsv
```

## Stage 2: Dereplication and Similarity Interface

The dereplication script consumes the Stage 1 manifest, Stage 1 sequence QC output, and optional pairwise similarity rows. Eligible records are `phage`, `prophage`, and `metagenomic_viral_contig` rows with passing manifest validation. Metadata-only rows remain eligible, while local FASTA-backed records with failing sequence QC are excluded when `genome_qc.exclude_failed_local_sequence_qc_from_clustering` is true. If no pairwise similarity table is supplied, each eligible genome is emitted as a singleton cluster and the report explicitly records the singleton fallback.

Implemented command:

```bash
python scripts/01_dereplicate_phages.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --thresholds config/thresholds.yaml \
  --sequence-qc results/qc/genome_sequence_qc.tsv \
  --ani-output results/clusters/phage_ani.tsv \
  --clusters-output results/clusters/phage_clusters.tsv \
  --representatives-output results/clusters/representatives.tsv \
  --report-output results/clusters/dereplication_report.tsv
```

Optional pairwise input schema is documented in `docs/dereplication_schema.md`. Thresholds are read from `config/thresholds.yaml`.

For the initial local FASTA-backed dataset, `data/metadata/external_evidence/blastn_pairwise_similarity.tsv` was generated with BLASTN from records passing Stage 1 sequence QC. This provides a conservative nucleotide-similarity baseline for the current cultured-phage/prophage pair; it is not a replacement for VIRIDIC, Mash, or an equivalent reviewed all-vs-all similarity run in the comprehensive public-scale analysis. The bridge TSV includes `evidence_source` and `notes` provenance fields for acceptance auditing. Regeneration command:

```bash
python scripts/build_blastn_pairwise_similarity.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --sequence-qc results/qc/genome_sequence_qc.tsv \
  --output data/metadata/external_evidence/blastn_pairwise_similarity.tsv \
  --report-output data/metadata/external_evidence/blastn_pairwise_similarity_report.tsv
```

## Stage 3: Annotation and Pangenome Interface

The annotation script consumes the Stage 1 manifest, Stage 2 cluster table, and optional Pharokka/PHROGs-style gene annotation rows. It writes normalized gene annotations, deterministic provisional gene clusters, and a wide pangenome count matrix. Hypothetical proteins are retained. Accepted annotation rows are retained when their `genome_id` is present in the Stage 1 manifest even if that genome is absent from Stage 2 clusters; in that case `species_cluster_id` and `representative_id` are left blank and the row notes record that the annotation was retained without a Stage 2 cluster. This lets reviewed sequence-backed annotation evidence remain usable without pretending that missing local FASTA files passed sequence QC or assigning unsupported taxonomy clusters.

Implemented command:

```bash
python scripts/02_build_annotation_tables.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --clusters results/clusters/phage_clusters.tsv \
  --annotations-output results/annotations/phage_annotations.tsv \
  --gene-clusters-output results/annotations/gene_clusters.tsv \
  --pangenome-output results/annotations/pangenome_matrix.tsv \
  --report-output results/annotations/annotation_report.tsv
```

Optional annotation input schema is documented in `docs/annotation_schema.md`. Current gene clustering uses PHROG ID, informative product name, protein sequence hash, or singleton fallback. This is a schema-stable merge layer, not a final orthology method.

For the initial real-data path, `data/metadata/external_evidence/genbank_cds_annotations.tsv` is a GenBank-derived bridge annotation table. It combines CDS features parsed from local GenBank files for the initial cultured phage/prophage records with accession-fetched NCBI GenBank CDS features for the NCBI seed phage source. This is curated product-annotation evidence, not standardized de novo phage annotation and not a substitute for Pharokka/PHROGs, domain, or structural annotation. The bridge TSV includes `tool`, `evidence`, and `notes` provenance fields for acceptance auditing.

Initial local GenBank regeneration command, after downloading the relevant GenBank files to `/tmp/cpg_annotation_gbff/`:

```bash
python scripts/build_genbank_cds_annotation_input.py \
  --record 'Klebsiella phage PhiKpNIH-2=/tmp/cpg_annotation_gbff/NC_049845.1.gbff' \
  --record 'NTUH-K2044_PhiSpy_pp1_NC_012731.1_2098066_2113724=/tmp/cpg_annotation_gbff/NC_012731.1.gbff:2098066-2113724' \
  --output data/metadata/external_evidence/genbank_cds_annotations.tsv \
  --report-output data/metadata/external_evidence/genbank_cds_annotations_report.tsv
```

NCBI accession-backed GenBank CDS evidence can then be appended without writing FASTA or modifying `data/raw/`. Reviewer-sensitive gaps between this bridge annotation layer and the production standardized pipeline are listed in `docs/reviewer_pipeline_gap_audit.md`.

```bash
python scripts/build_ncbi_genbank_cds_annotation_input.py \
  --manifest data/metadata/source_manifests/ncbi_virus_klebsiella_phages.tsv \
  --base-input data/metadata/external_evidence/genbank_cds_annotations.tsv \
  --output data/metadata/external_evidence/genbank_cds_annotations.tsv \
  --report-output data/metadata/external_evidence/ncbi_genbank_cds_annotations_report.tsv
```

For the current production profile, the Stage 3 annotation input is a no-network merge of the accepted assay-phage CDS rows plus the already parsed NTUH-K2044 prophage CDS rows. This keeps the prophage visible to H2 audits while preserving the claim boundary that those prophage annotations are GenBank bridge evidence, not standardized Pharokka/PHROGs/domain/structural evidence.

```bash
python scripts/build_ncbi_genbank_cds_annotation_input.py \
  --manifest data/metadata/source_manifests/klebsiella_prophages.tsv \
  --base-input data/metadata/production_evidence/phagehostlearn_prodigal_cds_annotations.tsv \
  --parsed-input data/metadata/external_evidence/genbank_cds_annotations.tsv \
  --parsed-genome-id NTUH-K2044_PhiSpy_pp1_NC_012731.1_2098066_2113724 \
  --skip-fetch \
  --output data/metadata/production_evidence/phagehostlearn_plus_prophage_cds_annotations.tsv \
  --report-output data/metadata/production_evidence/phagehostlearn_plus_prophage_cds_annotations_report.tsv
```

## Stage 4: RBP/Depolymerase Candidate Prioritization

The RBP/depolymerase script consumes normalized annotations and gene clusters, then combines annotation keywords, sequence-cluster evidence, optional domain evidence, optional structural evidence, protein length, and local synteny context. Candidate novelty tiers are conservative: annotation text alone is not treated as a novelty claim.

Implemented command:

```bash
python scripts/03_predict_rbps_depolymerases.py \
  --annotations results/annotations/phage_annotations.tsv \
  --gene-clusters results/annotations/gene_clusters.tsv \
  --thresholds config/thresholds.yaml \
  --candidates-output results/rbp_depolymerase/candidates.tsv \
  --domain-architectures-output results/rbp_depolymerase/domain_architectures.tsv \
  --module-clusters-output results/rbp_depolymerase/module_clusters.tsv \
  --novel-candidates-output results/rbp_depolymerase/novel_candidates.tsv \
  --report-output results/rbp_depolymerase/rbp_depolymerase_report.tsv
```

Optional domain and structural evidence schemas are documented in `docs/rbp_depolymerase_schema.md`.

## Stage 5: Host Feature Integration

The host feature script consumes the Stage 1 manifest, Stage 2 phage clusters, and optional Kleborate/Kaptive-style tables. It writes normalized host metadata plus explicit non-assay phage-host relationships. The older phage-host link table is retained as a deprecated compatibility output for downstream scaffold stages and is not an infectivity label.

Implemented command:

```bash
python scripts/04_integrate_host_features.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --clusters results/clusters/phage_clusters.tsv \
  --host-metadata-output results/host_features/host_metadata.tsv \
  --kaptive-output results/host_features/kaptive_results.tsv \
  --kleborate-output results/host_features/kleborate_results.tsv \
  --phage-host-links-output results/host_features/phage_host_links.tsv \
  --phage-host-relationships-output results/host_features/phage_host_relationships.tsv \
  --report-output results/host_features/host_feature_report.tsv
```

Optional Kleborate and Kaptive input schemas are documented in `docs/host_feature_schema.md`.

## Phage-Host Assay Contract and Validation

Pairwise host-range prediction requires explicit tested phage-host assay rows. The project therefore separates `data/metadata/phage_host_relationships.tsv`, which records non-assay relationships such as isolation host, reported host, prophage resident host, predicted host, and assay-panel membership, from `data/metadata/phage_host_assays.tsv`, which records tested positive and tested negative interactions.

The validator accepts header-only tables as schema scaffolds but treats them as insufficient for H1b, H3, and H4. Populated assay rows must resolve phage and host IDs to canonical entities, record `tested=true` or `tested=false`, preserve study/provenance fields, keep untested pairs distinct from tested negatives, and avoid inferring productive infection from spot clearing alone.

Implemented command:

```bash
python scripts/validate_phage_host_assays.py   --assays data/metadata/phage_host_assays.tsv   --relationships data/metadata/phage_host_relationships.tsv   --phage-manifest results/qc/phage_genome_manifest.tsv   --host-metadata results/host_features/host_metadata.tsv   --assay-validation-output results/validation/phage_host_assay_validation.tsv   --relationship-validation-output results/validation/phage_host_relationship_validation.tsv   --report-output results/validation/phage_host_assay_validation_report.tsv   --root .
```

`self_test_phage_host_assay_validation.py` covers header-only tables, valid positives, tested negatives, untested-negative contradictions, spot-only productive-infection claims, malformed EOP values, duplicates, unknown IDs, and invalid relationship types. Output schemas are documented in `docs/phage_host_assay_schema.md`, and the scientific interpretation contract is documented in `docs/scientific_analysis_contract.md`.

## Host Defense Run Handoff

After host feature integration, `scripts/create_host_defense_run_handoff.py` creates a DefenseFinder/PADLOC run manifest for reviewed host genome records with local FASTA files. The manifest and command file are production handoffs only; host defense calls are not accepted until reviewed tool output is normalized and configured as `inputs.host_defense_input`.

Implemented command:

```bash
python scripts/create_host_defense_run_handoff.py \
  --host-metadata results/host_features/host_metadata.tsv \
  --sequence-plan results/qc/sequence_acquisition_plan.tsv \
  --manifest-output results/qc/host_defense_run_handoff.tsv \
  --commands-output results/qc/host_defense_run_commands.sh \
  --report-output results/qc/host_defense_run_handoff_report.tsv \
  --root .
```

Output schemas are documented in `docs/host_defense_run_handoff_schema.md`.

## Stage 6: Defense/Counter-Defense Feature Integration

The defense/counter-defense script consumes host metadata, phage-host links, phage annotations, and optional host defense or phage anti-defense evidence tables. It writes normalized host defense systems, phage anti-defense candidates, and compatibility rows that combine receptor metadata with defense/counter-defense features.

Implemented command:

```bash
python scripts/05_integrate_defense_counterdefense.py \
  --host-metadata results/host_features/host_metadata.tsv \
  --phage-host-links results/host_features/phage_host_links.tsv \
  --annotations results/annotations/phage_annotations.tsv \
  --host-defense-output results/defense_systems/host_defense_systems.tsv \
  --phage-antidefense-output results/defense_systems/phage_antidefense_candidates.tsv \
  --compatibility-output results/defense_systems/compatibility_features.tsv \
  --report-output results/defense_systems/defense_counterdefense_report.tsv
```

Optional PADLOC/DefenseFinder-style and phage anti-defense schemas are documented in `docs/defense_counterdefense_schema.md`.

## Stage 7: Feature-Set Model Comparison

The generic model comparison script consumes phage clusters, RBP/depolymerase candidates, phage-host links, compatibility features, optional phage/host bridge metadata, and canonical phage-host assay rows when available. It writes transparent leave-one-out categorical baselines for K/O association proxies, group summaries for prophage RBP reservoirs, host background defense burden, exploratory novelty context, assay-derived spot-test breadth, and assay-feature coverage. H2 now includes an explicit prophage annotation coverage audit: annotated prophages are counted separately from prophages with detected RBP/depolymerase candidates so bridge-annotated, zero-candidate prophages are not silently omitted. A separate frozen H1 receptor benchmark (`scripts/run_receptor_layer_model_comparison.py`) consumes production receptor evidence, exact PHROGs/MMseqs profile-family and Phold/Foldseek hit-identity signatures, ordered per-gene PHROGs/MMseqs profile-hit proxies, host K/O evidence, and genome-similarity baselines to evaluate spot-test interaction under grouped splits. In the current benchmark, exact unordered PHROG profile-family + structural hit identities improve over RBPbase plus host K/O but do not robustly outperform BLASTN genome-similarity plus host K/O; ordered profile-hit proxies underperform in cold-phage/cold-cluster splits; H1 therefore remains exploratory rather than claim-supported. H3 retains tested-host denominators, positive spot-test counts, continuous spot-positive fractions, and Wilson intervals for the observed tested panel; these are initial-interaction summaries only. H4 remains explicitly blocked until productive-infection, plaque, EOP, or propagation outcomes are curated. To make that blocker quantitative, Stage 7 writes `productive_outcome_availability_audit` rows to `feature_importance.tsv` for `spot_result`, `plaque_result`, `productive_infection_result`, `growth_inhibition_result`, and `eop`; spot-test rows are counted separately from productive-outcome fields.

Implemented command:

```bash
python scripts/06_compare_feature_models.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --clusters results/clusters/phage_clusters.tsv \
  --rbp-candidates results/rbp_depolymerase/candidates.tsv \
  --phage-host-links results/host_features/phage_host_links.tsv \
  --compatibility-features results/defense_systems/compatibility_features.tsv \
  --phage-host-assays results/metadata/phage_host_assays.tsv \
  --model-comparison-output results/models/model_comparison.tsv \
  --feature-importance-output results/models/feature_importance.tsv \
  --prediction-errors-output results/models/prediction_errors.tsv \
  --hypothesis-summary-output results/models/hypothesis_summary.tsv \
  --report-output results/models/model_report.tsv
```

The current model layer is a reproducible scaffold. It also writes `results/models/hypothesis_summary.tsv`, a one-row-per-hypothesis evidence table that links H1-H6 to model rows, metrics, claim status, and interpretation guardrails. Stage 7 additionally writes `results/<profile>/qc/assay_feature_coverage.tsv`, which measures unique-entity and pair-level coverage for assay phage sequences, assay host sequences, K/O/ST calls, standardized phage annotations, RBP candidates, domain/structural evidence, host defense evidence, phage counter-defense evidence, receptor-layer completeness, defense/counter-defense completeness, and productive-infection outcomes. Missing analysis is represented as `not_assessed`, not as zero detected. It does not claim productive host-range prediction from spot-test labels. `compatibility_feature_status` and `matched_counterdefense_status` are no longer modeled as H4 targets because they are derived from receptor/defense feature availability rather than observed productive-infection outcomes.

## Stage 8: Figure Source and Draft SVG Generation

The figure generation script consumes outputs from Stages 1-7 and writes source TSVs plus lightweight draft SVGs for the six planned manuscript figures. The source TSVs are authoritative; the SVGs are reproducible visual scaffolds that can be polished later.

Implemented command:

```bash
python scripts/07_generate_figure_sources.py \
  --manifest results/qc/phage_genome_manifest.tsv \
  --clusters results/clusters/phage_clusters.tsv \
  --gene-clusters results/annotations/gene_clusters.tsv \
  --pangenome results/annotations/pangenome_matrix.tsv \
  --rbp-candidates results/rbp_depolymerase/candidates.tsv \
  --rbp-modules results/rbp_depolymerase/module_clusters.tsv \
  --novel-candidates results/rbp_depolymerase/novel_candidates.tsv \
  --host-metadata results/host_features/host_metadata.tsv \
  --phage-host-links results/host_features/phage_host_links.tsv \
  --host-defense results/defense_systems/host_defense_systems.tsv \
  --phage-antidefense results/defense_systems/phage_antidefense_candidates.tsv \
  --compatibility results/defense_systems/compatibility_features.tsv \
  --model-comparison results/models/model_comparison.tsv \
  --feature-importance results/models/feature_importance.tsv \
  --output-dir results/figures \
  --manifest-output results/figures/figure_manifest.tsv \
  --report-output results/figures/figure_generation_report.tsv
```

Figure output schemas are documented in `docs/figure_generation_schema.md`.


## Stage 9: Workflow Validation and Manuscript-Readiness Audit

The validation script audits required outputs, required columns, documentation files, script compilation, figure source files, assay validation outputs, source query/acquisition plans, and H1-H6 hypothesis coverage in the model comparison table. Missing files or schema mismatches are errors. Empty but schema-valid scaffold outputs are warnings.

Implemented command:

```bash
python scripts/08_validate_workflow.py \
  --root . \
  --schema-output results/validation/schema_validation.tsv \
  --hypothesis-output results/validation/hypothesis_coverage.tsv \
  --inventory-output results/validation/output_inventory.tsv \
  --report-output results/validation/workflow_validation_report.tsv
```

Validation output schemas are documented in `docs/workflow_validation_schema.md`.

## Stage 10: Study Readiness Audit

The study readiness audit consumes validation outputs, acquisition plans, sample-support audits, external-evidence plans, and major analysis tables to identify which requirements are ready for manuscript-level interpretation and which remain blocking. It is intentionally stricter than schema validation: a schema-valid empty table can pass workflow validation while still failing study readiness.

`scripts/10_plan_readiness_actions.py` converts the readiness blockers into `results/validation/readiness_action_plan.tsv`, a ranked handoff for moving from scaffold validation to real H1-H6 tests. It groups source-curation, sample-support, sequence-acquisition, external-evidence, and final model/figure rerun actions, and records the smallest useful validation command after each action. For source curation, A01 uses `results/qc/source_work_order_packet_manifest.tsv`, `results/qc/source_work_order_acceptance.tsv`, and `results/qc/minimum_source_curation_plan.tsv` to highlight the first blocking work-order packets and highest-ranked missing reviewed exports as the immediate primary artifacts while retaining the full source and hypothesis plans as supporting context.

Implemented command:

```bash
python scripts/09_audit_study_readiness.py \
  --root . \
  --results-dir results \
  --samples config/samples.tsv \
  --readiness-output results/validation/study_readiness.tsv \
  --report-output results/validation/study_readiness_report.tsv
```

Readiness output schemas are documented in `docs/study_readiness_schema.md` and `docs/readiness_action_plan_schema.md`.

`11_audit_goal_completion.py` performs a stricter objective-level audit after readiness action planning. It checks whether the original goal is actually complete: config-driven execution, outputs under `results/`, H1-H6 passing quantitative tests, sample support, manuscript readiness, and required documentation.

Implemented command:

```bash
python scripts/11_audit_goal_completion.py \
  --root . \
  --results-dir results \
  --audit-output results/validation/goal_completion_audit.tsv \
  --report-output results/validation/goal_completion_report.tsv
```

Goal-completion output schemas are documented in `docs/goal_completion_audit_schema.md`.

`12_build_hypothesis_traceability.py` builds an H1-H6 traceability matrix that links required sources, external evidence, sample support, model summaries, claim status, figures, and readiness status.

Implemented command:

```bash
python scripts/12_build_hypothesis_traceability.py \
  --source-plan results/qc/minimum_hypothesis_source_plan.tsv \
  --evidence-plan results/qc/external_evidence_unlock_plan.tsv \
  --sample-support results/qc/sample_support_by_hypothesis.tsv \
  --hypothesis-summary results/models/hypothesis_summary.tsv \
  --hypothesis-coverage results/validation/hypothesis_coverage.tsv \
  --figure-manifest results/figures/figure_manifest.tsv \
  --readiness results/validation/study_readiness.tsv \
  --trace-output results/validation/hypothesis_traceability.tsv \
  --report-output results/validation/hypothesis_traceability_report.tsv
```

Traceability schemas are documented in `docs/hypothesis_traceability_schema.md`.


## Source Acquisition Planning

Before sample generation, `scripts/plan_source_queries.py` records query intent and reviewed export paths in `results/qc/source_query_plan.tsv`, `scripts/create_source_export_templates.py` writes fillable headers under `results/qc/source_export_templates/`, `scripts/create_source_export_dictionary.py` writes the source export column dictionary in `results/qc/source_export_column_dictionary.tsv`, `scripts/create_source_query_commands.py` writes reviewed-export command sheets in `results/qc/source_query_commands.tsv` and `results/qc/source_query_commands.sh`, and `scripts/validate_source_exports.py` checks reviewed exports before import. Then `scripts/plan_source_acquisition.py` compares `config/source_catalog.yaml`, `config/source_imports.yaml`, and local source-manifest files. The output `results/qc/source_acquisition_plan.tsv` records which public exports or manually curated manifests are missing, which populated manifests remain disabled, and which command advances each source. `scripts/import_source_manifests.py` treats `data/metadata/source_exports/` as authoritative and regenerates normalized source manifests. `scripts/audit_source_manifest_drift.py` then regenerates enabled manifests in a temporary directory and compares checksums to the configured source manifests, writing `results/qc/source_manifest_drift.tsv`; drift is a blocking reproducibility issue because it means source exports and source manifests disagree.

`scripts/summarize_source_curation_tasks.py` consolidates query, template, export validation, acquisition, and readiness status into `results/qc/source_curation_tasks.tsv`, the single reviewed-export handoff table for moving the real study from planned sources to populated sample rows. `scripts/plan_hypothesis_source_unlocks.py` maps those source states to H1-H6 in `results/qc/hypothesis_source_unlock_plan.tsv` and `results/qc/hypothesis_source_unlock_matrix.tsv`. `scripts/create_source_export_starter_kit.py` writes `results/qc/source_export_starter_kit/`, a per-source fillable header and curation README that consolidates required columns, identity rules, queries, expected export paths, and validation commands for A01. `scripts/bootstrap_source_exports.py` can then explicitly create non-overwriting skeleton files at those expected export paths so curators work in the same locations that validation and import consume. `scripts/plan_minimum_source_curation.py` writes `results/qc/minimum_source_curation_plan.tsv` and `results/qc/minimum_hypothesis_source_plan.tsv`, ranking sources by how many H1-H6 minimum source sets they unblock. `scripts/preflight_priority_source_exports.py` writes `results/qc/priority_source_export_preflight.tsv` and issue details for the highest-ranked source exports before enablement. `scripts/create_priority_source_collection_packet.py` renders those highest-priority source handoffs as `results/qc/priority_source_collection_packet/`, combining query commands, starter templates, preflight status, and validation commands. `scripts/plan_source_enablement.py` writes `results/qc/source_enablement_plan.tsv`, which reports whether each reviewed export is missing, ready for import enablement, waiting for manifest review, or enabled for sample building. `scripts/apply_source_enablement.py` then writes `results/qc/source_enablement_apply_report.tsv` as a workflow dry-run and can separately apply only those config changes that the enablement plan marks safe. `scripts/create_source_curation_packet.py` renders the same handoff as `results/qc/source_curation_packet/`, with one checklist per source. `scripts/audit_source_overlaps.py` writes `results/qc/source_overlap_groups.tsv` and `results/qc/source_overlap_summary.tsv` after sample generation, flagging duplicate genome IDs, accessions, or raw sequence paths across enabled sources before downstream dereplication. `scripts/audit_sample_support.py` then writes `results/qc/sample_support_by_hypothesis.tsv` and `results/qc/sample_support_summary.tsv`, which the readiness audit uses to block H1-H6 interpretation until configured sample-support minima are met. `scripts/plan_sample_support_sources.py` writes `results/qc/sample_support_source_bridge.tsv`, linking failed support metrics to ranked source exports and fields to populate. `scripts/preflight_sample_support_exports.py` writes `results/qc/sample_support_export_preflight.tsv`, checking whether those exports currently have metric-supporting rows. `scripts/build_source_readiness_dashboard.py` merges those blockers with source validation and enablement state into `results/qc/source_readiness_dashboard.tsv`. `scripts/build_source_curation_work_order.py` converts the dashboard into `results/qc/source_curation_work_order.tsv`, a ranked list of reviewed-row tasks. `scripts/create_source_work_order_packets.py` renders those tasks as `results/qc/source_work_order_packets/` Markdown packets. `scripts/check_source_work_order_acceptance.py` checks whether reviewed exports satisfy those tasks. `scripts/plan_source_post_acceptance.py` plans the next import, manifest review, catalog enablement, or sample-support rerun step after acceptance. `scripts/create_sample_support_curation_packet.py` renders those blockers as `results/qc/sample_support_curation_packet/` checklists. Together these make the transition from a scaffold to a populated phage atlas auditable.

## External Evidence Planning

After sequence QC, `scripts/plan_external_evidence.py` writes `results/qc/external_evidence_plan.tsv`. The table maps each planned external evidence source to a workflow optional input key, minimum TSV schema checks, sequence-data prerequisite, planned tools, current tool availability, evidence provenance, real-claim usability, and the next action required for manuscript-ready analyses. The `evidence_origin` and `real_claim_use_status` fields explicitly separate mock fixtures from production evidence so scaffold tests cannot be mistaken for biological support. This makes missing production evidence explicit before downstream model and figure stages run.

## Sequence Acquisition Planning

After manifest validation, `scripts/plan_sequence_acquisition.py` creates `results/qc/sequence_acquisition_plan.tsv`. This table separates records with existing local FASTA files from records that can be retrieved from accessions and metadata-only records that need additional curation. The workflow does not download sequence files automatically; suggested commands are recorded for review and reproducibility.

Reviewed local raw FASTA files remain untracked under `data/raw/`. `data/metadata/sequence_acquisition_manifest.tsv` records the accession, source version, retrieval command, retrieval date, expected raw path, byte count, SHA-256 digest, and review status for each reviewed raw file. `scripts/validate_sequence_acquisition_manifest.py` writes `results/validation/sequence_acquisition_manifest_validation.tsv` and blocks reviewed rows whose local file is missing or whose checksum differs. This validates reproducibility of local raw inputs, but it does not make seed data manuscript-ready or replace production evidence generation.

## External Evidence Templates

After external-evidence planning, `scripts/create_external_evidence_templates.py` creates header-only TSV templates for pairwise similarity, phage annotation, RBP domain/structural evidence, host K/O/ST evidence, host defense systems, and phage anti-defense candidates. These templates are written under `results/qc/external_evidence_templates/` and are not treated as configured production evidence until their paths are explicitly set in `config/workflow.yaml`.

Implemented command:

```bash
python scripts/create_external_evidence_templates.py \
  --evidence-plan results/qc/external_evidence_plan.tsv \
  --templates-dir results/qc/external_evidence_templates \
  --manifest-output results/qc/external_evidence_template_manifest.tsv \
  --report-output results/qc/external_evidence_template_report.tsv \
  --root .
```

Output schemas are documented in `docs/external_evidence_template_schema.md`.

## External Evidence Run Packets

After template generation, `scripts/create_external_evidence_run_packets.py` writes one Markdown packet per evidence layer under `results/qc/external_evidence_run_packets/`. Each packet records the planned tool IDs, sequence scope, eligible record count, required TSV columns, template path, advisory production command, acceptance checklist, and rerun command for validation. These packets are handoffs for running standard tools or producing reviewed TSVs; they are not themselves biological evidence.

Implemented command:

```bash
python scripts/create_external_evidence_run_packets.py \
  --evidence-plan results/qc/external_evidence_plan.tsv \
  --template-manifest results/qc/external_evidence_template_manifest.tsv \
  --output-dir results/qc/external_evidence_run_packets \
  --manifest-output results/qc/external_evidence_run_packet_manifest.tsv \
  --report-output results/qc/external_evidence_run_packet_report.tsv \
  --root .
```

Output schemas are documented in `docs/external_evidence_run_packet_schema.md`.

## External Evidence Protein Handoff

After normalized annotation, `scripts/export_external_evidence_proteins.py` writes FASTA files and a manifest for external domain/profile and structure-informed RBP/depolymerase evidence generation. The all-protein FASTA supports broad production scans; the prioritized FASTA is a smaller run target for RBP/depolymerase-focused HMM/profile, Foldseek, or Phold-style analyses. Priority labels are run-target hints only and are not treated as domain or structural evidence.

Implemented command:

```bash
python scripts/export_external_evidence_proteins.py \
  --annotations results/annotations/phage_annotations.tsv \
  --all-proteins-output results/qc/external_evidence_proteins/phage_proteins.faa \
  --candidate-proteins-output results/qc/external_evidence_proteins/rbp_depolymerase_candidate_proteins.faa \
  --manifest-output results/qc/external_evidence_proteins/protein_export_manifest.tsv \
  --report-output results/qc/external_evidence_proteins/protein_export_report.tsv
```

Output schemas are documented in `docs/external_evidence_protein_handoff_schema.md`.

## RBP External Evidence Normalization

After external domain/profile or structure-informed annotation is run, `scripts/normalize_rbp_external_evidence.py` converts reviewed HMMER, Foldseek, Phold, or generic TSV outputs into the exact optional evidence schemas consumed by Stage 4. The normalizer does not run external tools and does not make novelty claims; it only standardizes reviewed evidence for `inputs.domain_evidence` and `inputs.structural_evidence`.

The importer now treats reviewed evidence as a production contract rather than a loose table merge. HMMER orientation is explicit with `--hmmer-mode`, Foldseek and Phold field orders are explicit for headerless outputs, annotation identifiers are canonicalized to Stage 3 `annotation_gene_id` values, numeric ranges and non-finite values are validated, duplicate hits are reported, and absent inputs preserve existing outputs unless `--overwrite-empty` is requested. Domain and structural provenance are supplied separately, row-level provenance takes precedence, and both output tables are atomically replaced only after every supplied input validates.

Implemented command pattern:

```bash
python scripts/normalize_rbp_external_evidence.py \
  --domain-input results/external/rbp_domains/hmmer.domtblout \
  --domain-format hmmer_domtblout \
  --hmmer-mode hmmsearch \
  --structural-input results/external/rbp_structures/foldseek.tsv \
  --structural-format foldseek_tsv \
  --foldseek-fields query,target,alntmscore,prob,evalue \
  --annotation-manifest results/annotations/phage_annotations.tsv \
  --domain-tool hmmer \
  --domain-tool-version reviewed \
  --domain-database reviewed_profile_set \
  --domain-database-version reviewed_profile_snapshot \
  --structural-tool foldseek \
  --structural-tool-version reviewed \
  --structural-database reviewed_structure_set \
  --structural-database-version reviewed_structure_snapshot \
  --domain-output data/metadata/external_evidence/rbp_domain_evidence.tsv \
  --structural-output data/metadata/external_evidence/rbp_structural_evidence.tsv \
  --report-output results/qc/normalize_rbp_external_evidence_report.tsv
```

Output schemas are documented in `docs/rbp_external_evidence_normalization_schema.md`.

The normalization logic is regression-tested with fixture-only scenarios by `scripts/self_test_rbp_external_evidence_normalization.py`. The self-test covers generic domain TSVs, both HMMER `domtblout` orientations, headerless Foldseek parsing, Phold-style parsing, annotation-manifest failures, canonical protein-ID translation, ambiguous alias failures, numeric validation including non-finite values, duplicate handling, no-input preservation, explicit empty overwrite, path-collision rejection, distinct domain/structural provenance, transactional no-partial-write behavior, and full success/failure command paths.

Implemented self-test command:

```bash
python scripts/self_test_rbp_external_evidence_normalization.py \
  --output results/validation/rbp_external_evidence_normalization_self_test.tsv \
  --report-output results/validation/rbp_external_evidence_normalization_self_test_report.tsv
```

Self-test schemas are documented in `docs/rbp_external_evidence_normalization_self_test_schema.md`.

## Defense External Evidence Normalization

After external host-defense or phage anti-defense searches are run, `scripts/normalize_defense_external_evidence.py` converts reviewed DefenseFinder/PADLOC-style host-defense outputs and reviewed phage anti-defense hit tables into the exact optional evidence schemas consumed by Stage 6. The normalizer does not run external tools and does not make defense-escape claims; it only standardizes reviewed evidence for `inputs.host_defense_input` and `inputs.phage_antidefense_input`.

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

Output schemas are documented in `docs/defense_external_evidence_normalization_schema.md`. Host-defense and phage anti-defense outputs can also be written independently, which avoids overwriting one reviewed target TSV while normalizing the other.

The normalization logic is regression-tested with fixture-only scenarios by `scripts/self_test_defense_external_evidence_normalization.py`. The self-test covers generic host-defense TSVs, PADLOC-like alias handling, independent host-only output writing, generic phage anti-defense TSVs with anti-defense class inference, and header-only behavior when no reviewed inputs are supplied.

Implemented self-test command:

```bash
python scripts/self_test_defense_external_evidence_normalization.py \
  --output results/validation/defense_external_evidence_normalization_self_test.tsv \
  --report-output results/validation/defense_external_evidence_normalization_self_test_report.tsv
```

Self-test schemas are documented in `docs/defense_external_evidence_normalization_self_test_schema.md`.

## Phage Anti-Defense Screening Handoff

After protein export, `scripts/create_phage_antidefense_screening_handoff.py` writes a screening manifest and command hints for curated phage anti-defense searches. The handoff links `annotation_gene_id` values to the all-protein FASTA and identifies annotation-text priority targets for review. These priority labels are not accepted anti-defense evidence; reviewed HMM/profile, sequence, or structure-informed hits must be normalized and configured as `inputs.phage_antidefense_input`.

Implemented command:

```bash
python scripts/create_phage_antidefense_screening_handoff.py \
  --annotations results/annotations/phage_annotations.tsv \
  --protein-manifest results/qc/external_evidence_proteins/protein_export_manifest.tsv \
  --all-proteins results/qc/external_evidence_proteins/phage_proteins.faa \
  --manifest-output results/qc/phage_antidefense_screening_handoff.tsv \
  --commands-output results/qc/phage_antidefense_screening_commands.sh \
  --report-output results/qc/phage_antidefense_screening_handoff_report.tsv \
  --root .
```

Output schemas are documented in `docs/phage_antidefense_screening_handoff_schema.md`.

## External Evidence Acceptance

`check_external_evidence_acceptance.py` reads `results/qc/external_evidence_plan.tsv` after optional evidence TSVs are configured and writes `results/qc/external_evidence_acceptance.tsv`. This table reports whether each evidence layer is accepted for workflow use, missing, schema-invalid, waiting for sequence data, or accepted with provenance lint. It also counts rows with populated `evidence_source`, `tool`, `evidence`, or `notes` fields so production evidence can be reviewed before claims are strengthened.

Implemented command:

```bash
python scripts/check_external_evidence_acceptance.py \
  --evidence-plan results/qc/external_evidence_plan.tsv \
  --acceptance-output results/qc/external_evidence_acceptance.tsv \
  --report-output results/qc/external_evidence_acceptance_report.tsv \
  --root .
```

Output schemas are documented in `docs/external_evidence_acceptance_schema.md`.

For the initial reviewed host row, `scripts/build_host_feature_bridge_evidence.py` normalizes K/O/ST/AMR/virulence values from `data/metadata/source_manifests/klebsiella_host_genomes.tsv` into Kleborate-style and Kaptive-style bridge TSVs. These TSVs preserve the source-manifest provenance notes and are configured as optional host-feature evidence inputs. They are not a substitute for rerunning Kleborate and Kaptive across the expanded production host set.

Implemented bridge command:

```bash
python scripts/build_host_feature_bridge_evidence.py \
  --host-manifest data/metadata/source_manifests/klebsiella_host_genomes.tsv \
  --kleborate-output data/metadata/external_evidence/kleborate_host_features.tsv \
  --kaptive-output data/metadata/external_evidence/kaptive_ko_typing.tsv \
  --report-output data/metadata/external_evidence/host_feature_bridge_evidence_report.tsv
```

The acceptance logic is regression-tested with fixture-only scenarios by `scripts/self_test_external_evidence_acceptance.py`. The self-test verifies accepted evidence with complete provenance, accepted evidence with provenance lint, schema-invalid configured evidence, and missing production tool/input states.

Implemented self-test command:

```bash
python scripts/self_test_external_evidence_acceptance.py \
  --output results/validation/external_evidence_acceptance_self_test.tsv \
  --report-output results/validation/external_evidence_acceptance_self_test_report.tsv
```

Self-test schemas are documented in `docs/external_evidence_acceptance_self_test_schema.md`.

## Source-Driven Sample Generation

The real workflow now treats curated source manifests as the production data entry point. `scripts/build_samples_from_sources.py` normalizes enabled entries from `config/source_catalog.yaml` into `results/source_builder/samples.tsv`, and downstream stages consume that generated table. This keeps source provenance explicit and avoids overwriting raw data or the static `config/samples.tsv` template.


## External Evidence Unlock Planning

`results/qc/external_evidence_unlock_plan.tsv` maps required external evidence tables to H1-H6. It is generated from `results/qc/external_evidence_plan.tsv` and `results/qc/external_evidence_template_manifest.tsv`, and distinguishes evidence that is ready from evidence still waiting for source records, local sequence QC, external tools, or configured TSV inputs.

Minimum source curation schemas are documented in `docs/minimum_source_curation_schema.md`.

Source enablement schemas are documented in `docs/source_enablement_schema.md`.

Priority source preflight schemas are documented in `docs/priority_source_preflight_schema.md`.

Priority source collection packet schemas are documented in `docs/priority_source_collection_packet_schema.md`.

Source overlap audit schemas are documented in `docs/source_overlap_schema.md`.

## Claim Support Audit

The claim-support audit joins the manuscript claim ledger to workflow validation, H1-H6 model summaries, hypothesis traceability, and external evidence provenance. This audit defines the strongest wording currently allowed for each claim and prevents mock fixture or scaffold-only outputs from being used as real biological conclusions.
