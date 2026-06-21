# Current Analysis Status

Last updated: 2026-06-21

This file is a compact handoff for remote AI reviewers and collaborators. It summarizes the current stacked PR state, what evidence exists, what has been tested, and which claims remain unsupported.

## Current Stack

The active production evidence and analysis work is split into three reviewable PRs:

| PR | Branch | Base | Purpose | Status |
| --- | --- | --- | --- | --- |
| #12 | `prA-production-receptor-evidence` | `main` | Production receptor evidence for the 105 assay phages | Open draft, mergeable, CI passed |
| #13 | `prB-h1-receptor-benchmark` | `prA-production-receptor-evidence` | Frozen H1 receptor-layer benchmark using PR #12 evidence | Open draft, mergeable, CI passed |
| #14 | `prC-defense-counterdefense-evidence` | `prB-h1-receptor-benchmark` | Host defense and explicit phage anti-defense candidate evidence | Open draft, mergeable, CI passed |

Merge/review order should remain: #12, then #13, then #14.

## Study Question

The working biological hypothesis is a two-filter model:

1. Receptor compatibility: phage RBP/depolymerase features versus host capsule/LPS features.
2. Intracellular compatibility: host defense systems versus phage counter-defense genes.

The current validated assay endpoint is spot-test interaction only. Spot positivity is treated as initial interaction evidence, not productive infection.

## Production Tool/Evidence Visibility

Tracked normalized production evidence is under `data/metadata/production_evidence/`. The compact tool-run manifest is `data/metadata/production_evidence/production_tool_run_manifest.tsv`; it distinguishes accepted tracked TSVs from native output directories that are generated locally under ignored `results/production/` paths.

Current established-tool status:

| Tool/layer | Current status |
| --- | --- |
| Pharokka | Local native runs completed for 105 assay phages; native outputs are ignored under `results/production/pharokka_assay_phages/`. |
| Phold/Foldseek | Local native runs completed for 105 assay phages; tracked normalized receptor and ACR candidate subsets are configured. |
| Kaptive | Tracked production K/O typing exists for 200 assay hosts. |
| Kleborate | Tracked production host feature evidence exists for 188 assay hosts. |
| DefenseFinder | Tracked production host-defense evidence exists for 200 assay hosts. |
| BLASTN/fastANI/skani | Tracked benchmark genome-similarity baselines exist for the 105 assay phages. |
| VIRIDIC | Not run; do not describe current similarity evidence as VIRIDIC. |
| PADLOC | Not run; current host-defense evidence is DefenseFinder-only. |

The default CI path validates tracked normalized evidence and mock/seed workflows. It does not install or rerun the heavy external tools.

## Assay Outcome Layer

The reviewed PhageHostLearn benchmark assay layer contains:

| Metric | Count |
| --- | ---: |
| Tested phage-host spot-test pairs | 10,006 |
| Spot-positive pairs | 333 |
| Spot-negative pairs | 9,673 |
| Assay phages | 105 |
| Assay hosts | 200 |
| Productive-infection/plaque/EOP outcomes | 0 |

Blank matrix cells remain untested and are not converted into negatives.

## PR #12: Production Receptor Evidence

PR #12 freezes receptor-layer evidence inputs for the assay phages and does not run H1 models.

Evidence included:

| Evidence | Count |
| --- | ---: |
| Sequence-backed assay-phage CDS annotation rows | 8,393 |
| Assay phages represented | 105 |
| Combined Stage 3 annotation input rows | 8,417 |
| GenBank bridge prophage CDS rows in combined input | 24 |
| PHROGs/MMseqs receptor-domain rows | 495 |
| Phold/Foldseek receptor-like structural rows | 23 |

The 23 Phold-only receptor-like candidates were conservatively triaged:

| Triage class | Count |
| --- | ---: |
| Strong structure-informed candidate | 8 |
| Possible tail/receptor-associated protein | 5 |
| Generic structural protein | 6 |
| Insufficiently specific | 4 |

The generic production workflow now also retains these accepted annotation rows in Stage 3 when their assay phage IDs are present in the manifest but absent from Stage 2 clusters because local raw FASTA files are not tracked. The retained rows keep blank species-cluster fields, so this does not promote missing local sequence files into completed taxonomy or dereplication evidence.

The production profile now uses `data/metadata/production_evidence/phagehostlearn_plus_prophage_cds_annotations.tsv` as its Stage 3 annotation input. That file is a no-network merge of the 8,393 accepted assay-phage CDS rows with 24 existing parsed GenBank CDS rows for the NTUH-K2044 computational prophage candidate. The prophage rows are bridge annotation only, not standardized Pharokka/PHROGs/domain/structural evidence. Stage 4 currently detects zero RBP/depolymerase candidates for that prophage from these bridge rows.

Claim boundary: these are computational receptor candidates. They do not prove capsule specificity, depolymerase activity, host range, or productive infection.

## PR #13: H1 Receptor Benchmark

PR #13 consumes the receptor evidence from PR #12 and adds host K/O evidence plus genome-similarity baselines.

Additional evidence included:

| Evidence | Count |
| --- | ---: |
| Kaptive host rows | 200 |
| Kleborate host rows | 188 |
| BLASTN phage similarity rows | 5,671 |
| fastANI phage similarity rows | 5,460 |
| skani phage similarity rows | 5,460 |

Generated large local benchmark outputs under ignored `results/production/`:

| Output | Rows |
| --- | ---: |
| Pairwise receptor feature matrix | 10,006 |
| Primary model comparison | 380 |
| Out-of-fold predictions | 760,456 |

Tracked compact benchmark review outputs:

| Output | Rows |
| --- | ---: |
| Assay phage receptor feature coverage | 105 |
| Assay phage module identity signatures | 105 |
| Assay phage cluster assignments | 105 |
| Pooled summary | 104 |
| Support diagnostics | 520 |
| Feature-source ablation | 76 |
| Held-out-group bootstrap | 76 |
| Compact artifact checksum manifest | 7 |

Primary cold-phage-cluster contrasts now separate unordered module identity from ordered architecture proxies:

| Contrast | Model AP | Baseline AP | Delta AP | Bootstrap 95% CI |
| --- | ---: | ---: | ---: | --- |
| Unordered domain+structural module identity + K/O vs RBPbase + K/O | 0.190417 | 0.064114 | 0.126303 | [0.053441, 0.215846] |
| Unordered domain+structural module identity + K/O vs BLASTN nearest-phage + K/O | 0.190417 | 0.195850 | -0.005433 | [-0.076435, 0.047078] |
| Ordered domain+structural architecture proxy + K/O vs unordered module identity + K/O | 0.060394 | 0.190417 | -0.130023 | [-0.235675, -0.058682] |
| Ordered domain+structural architecture proxy + K/O vs BLASTN nearest-phage + K/O | 0.060394 | 0.195850 | -0.135456 | [-0.238648, -0.061170] |

Current interpretation: exact unordered domain+structural module identity signatures improve over RBPbase plus host K/O in cold-phage-cluster evaluation, but they do not robustly outperform BLASTN nearest-phage genome similarity plus host K/O. Ordered per-gene PHROGs/MMseqs architecture proxies were added from existing Prodigal gene order and MMseqs domain coordinates; in the current exact-key rate model they are too sparse under cold-phage/cold-cluster evaluation and underperform unordered module identity signatures. These architecture proxies are not manually curated domain boundaries, C-terminal receptor-recognition architecture, or functional capsule specificity.

Cold-K-locus support diagnostics also show that exact receptor/module + K/O models use global-prevalence fallback for all 10,006 cold-K predictions, while the genome-similarity + K/O model uses nearest-phage intermediate fallback for all 10,006 cold-K predictions. Treat the current cold-K result as a fallback-design diagnostic, not a fair novel-receptor generalization test.

## PR #14: Defense/Counter-Defense Evidence

PR #14 adds the defense/counter-defense evidence layer without adding an H4 model.

Evidence included:

| Evidence | Count |
| --- | ---: |
| DefenseFinder host-defense rows | 2,758 |
| Assay hosts with host-defense evidence | 200 / 200 |
| Explicit Phold ACR anti-CRISPR candidate rows | 7 |
| Assay phages with explicit phage anti-defense candidates | 7 / 105 |
| Tested pairs with host-defense evidence | 10,006 / 10,006 |
| Tested pairs with both host-defense and phage anti-defense candidate evidence | 814 / 10,006 |
| Productive-infection outcomes | 0 / 10,006 |
| ST-typed assay hosts with DefenseFinder burden | 188 / 200 |
| ST groups represented in H5 burden summary | 120 |

Annotation-keyword phage anti-defense hits are screening-only. They are excluded from compatibility matching unless supplied through an explicit reviewed evidence table.

H3 spot-breadth association rows are now generated from the same evidence layer:

| H3 feature | Assessed phages | Spearman rho versus tested-panel spot-positive fraction | Status |
| --- | ---: | ---: | --- |
| Domain module count | 105 / 105 | 0.110 | Exploratory analysis-ready row, claim remains data-dependent |
| Structural module count | 105 / 105 | 0.010 | Exploratory analysis-ready row, claim remains data-dependent |
| Total domain + structural module count | 105 / 105 | 0.106 | Exploratory analysis-ready row, claim remains data-dependent |
| Explicit anti-defense candidate count | 7 / 105 | NA | Blocked by insufficient coverage and one observed feature value |

Claim boundary: H4 remains `blocked_no_productive_infection_labels`. Stage 7 now records a field-level H4 outcome availability audit in `results/production/models/feature_importance.tsv`: `spot_result` has 10,006 observed initial-interaction outcomes, while `plaque_result`, `productive_infection_result`, `growth_inhibition_result`, and numeric `eop` each have 0 observed productive-outcome values. These evidence tables support coverage auditing and future H4 tests only; they do not demonstrate defense escape or improved prediction. The H3 rows are phage-level spot-test breadth associations only; they do not establish productive-infection breadth, causal breadth mechanisms, or general host-range strategy.

H4 source audit: the local PhageHostLearn matrix (data/metadata/external/phagehostlearn/phage_host_interactions.csv) contains spot-test values only; the reviewed assay export (data/metadata/assay_source_exports/reviewed_klebsiella_phage_host_assays.tsv) has 10,006 assay_type=spot rows with plaque_result, productive_infection_result, growth_inhibition_result, and eop all unmeasured; and the bundled PhageHostLearn phage/host archives contain genome files rather than plaque, EOP, propagation, or productive-infection outcome tables. The associated publication describes the matrix as spot-test interaction data, so no current repository source can complete H4 without an additional curated productive-infection/plaque/EOP dataset.

Latest assay-feature coverage audit correction: `results/production/qc/assay_feature_coverage.tsv` now counts accepted sequence-backed normalized phage annotation for 105/105 assay phages and 10,006/10,006 tested pairs. Domain evidence covers 105/105 assay phages, while structural/remote-homology hit evidence covers 12/105 assay phages and 1,048/10,006 tested pairs. Structural non-hit phages are not interpreted as assessed-zero structural evidence; the audit only marks the hit-bearing structural evidence as assessed-positive. Productive-infection outcome coverage remains 0/10,006.

## Hypothesis Status

| Hypothesis | Current status | Reason |
| --- | --- | --- |
| H1 receptor compatibility | Exploratory, module-identity signal available but not claim-ready | Exact unordered domain+structural module identity signatures beat RBPbase + K/O but do not robustly beat BLASTN genome-similarity + K/O; ordered per-gene architecture proxies were tested and underperform in cold-phage/cold-cluster splits; novel-K generalization remains fallback-limited. |
| H2 prophage receptor reservoir | Quantitative assessed-zero prophage audit row available, claim remains unsupported | One sequence-backed computational prophage now has 24 GenBank bridge CDS rows in Stage 3, but Stage 4 finds zero RBP/depolymerase candidates and the cohort is far too small for a reservoir claim. |
| H3 breadth versus modularity/counter-defense | Exploratory module-count association rows available, claim remains data-dependent | Domain and total module counts show weak positive phage-level correlations with tested-panel spot-positive fraction (rho 0.110 and 0.106); structural count is near zero (rho 0.010); explicit anti-defense candidate coverage is insufficient at 7/105 phages. |
| H4 defense/counter-defense improves productive-infection prediction | Blocked | No productive-infection, plaque, propagation, or EOP labels exist. |
| H5 host lineage/prophage/defense landscape | Data-dependent association summary available | The workflow now summarizes ST versus DefenseFinder burden for 188/200 benchmark hosts across 120 ST groups, but this is association-only and not phage susceptibility or infectivity evidence. |
| H6 source/ecology novelty | Data-dependent | Requires broader source-balanced atlas and ecological source labels, not database provenance alone. |

## Reviewer-Safe Claims

Allowed now:

> The repository contains a reproducible, config-driven benchmark workflow with reviewed spot-test outcomes, production receptor evidence, host K/O typing evidence, genome-similarity baselines, and host defense/phage anti-defense candidate evidence for the PhageHostLearn benchmark.

Allowed now:

> In the current exploratory H1 benchmark, exact unordered receptor module identity signatures improve over RBPbase and are competitive with BLASTN genome-similarity baselines under cold-phage-cluster evaluation, but do not robustly outperform genome similarity; ordered architecture proxies are currently too sparse for cold-phage/cold-cluster prediction.

Allowed now:

> In the current exploratory H3 phage-level summary, receptor module counts show only weak association with tested-panel spot-positive breadth, while explicit anti-defense candidate coverage remains insufficient for a counter-defense breadth test.

Not allowed now:

> RBP/depolymerase module architecture explains Klebsiella phage host range better than taxonomy.

Not allowed now:

> Defense/counter-defense features explain infection failure or improve host-range prediction.

Not allowed now:

> Spot-test positives demonstrate productive infection or therapeutic suitability.

## Current Goal Audit Snapshot

After the latest production run, the standard hypothesis-coverage audit recognizes the compact H1 receptor-layer benchmark rather than only the older one-sample K/O proxy rows:

| Hypothesis | Coverage audit status | Evidence basis |
| --- | --- | --- |
| H1 | pass | 104 pooled receptor-layer benchmark rows across 4 grouped split strategies and 26 model families; claim remains exploratory and spot-test-only. |
| H2 | pass | The annotated-prophage coverage audit is quantitative and analysis-ready, reporting 0/1 prophages with detected RBP/depolymerase candidates; this does not support a reservoir claim. |
| H3 | pass | Quantitative receptor-module breadth association rows are analysis-ready; counter-defense subcomponents remain blocked by insufficient coverage. |
| H4 | warn | Blocked by absence of productive-infection, plaque, propagation, or EOP outcomes. |
| H5 | pass | ST versus DefenseFinder burden summary. |
| H6 | pass | Source/cluster novelty prioritization summaries. |

Goal completion remains incomplete because `G03` and `G05` are still blocking: H4 still lacks productive-infection, plaque, propagation, or EOP outcomes. H2 and H3 now have quantitative analysis-ready rows, but H2 remains too small for a reservoir claim and H3 counter-defense coverage remains limited; claim support remains data-dependent.

## Immediate Next Steps

1. Review and merge PR #12.
2. Rebase/retarget PR #13 onto the updated base after #12 merges, then review and merge PR #13.
3. Rebase/retarget PR #14 after #13 merges, then review and merge PR #14.
4. After the stack is merged, rerun the production workflow and claim audits from the merged `main` state.
5. If testing H4 remains a priority, curate productive-infection, plaque, propagation, or EOP outcomes. Defense/counter-defense evidence alone cannot test H4.
6. If expanding toward a Genome Biology-level atlas, scale source curation and sequence-backed annotation beyond the benchmark while preserving source-overlap and claim-boundary audits.

## What Not To Do Next

Do not add a new dashboard, framework, model registry, or broad abstraction layer before the current PR stack is reviewed. The next work should either be review/merge hygiene or a real data unlock, not more scaffold expansion.
