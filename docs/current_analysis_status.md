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
| Sequence-backed CDS annotation rows | 8,393 |
| Assay phages represented | 105 |
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

Generated local benchmark outputs under ignored `results/production/`:

| Output | Rows |
| --- | ---: |
| Pairwise receptor feature matrix | 10,006 |
| Primary model comparison | 380 |
| Out-of-fold predictions | 760,456 |
| Pooled summary | 76 |
| Feature-source ablation | 44 |
| Held-out-group bootstrap | 44 |

Primary cold-phage-cluster contrast:

`AP(receptor + host K/O) - AP(genome similarity + host K/O)`

| Genome-similarity baseline | Receptor AP | Baseline AP | Delta AP | Bootstrap 95% CI |
| --- | ---: | ---: | ---: | --- |
| BLASTN | 0.118254 | 0.195850 | -0.077596 | [-0.171900, 0.014083] |
| fastANI | 0.118254 | 0.188858 | -0.070604 | [-0.158084, 0.010668] |
| skani | 0.118254 | 0.199395 | -0.081141 | [-0.169619, -0.002116] |

Current interpretation: within this benchmark, the current receptor-feature summaries do not outperform genome-similarity plus host K/O baselines in the primary cold-phage-cluster comparison. H1 remains exploratory and should not be claimed as supported.

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

Annotation-keyword phage anti-defense hits are screening-only. They are excluded from compatibility matching unless supplied through an explicit reviewed evidence table.

Claim boundary: H4 remains `blocked_no_productive_infection_labels`. These evidence tables support coverage auditing and future H4 tests only; they do not demonstrate defense escape or improved prediction.

## Hypothesis Status

| Hypothesis | Current status | Reason |
| --- | --- | --- |
| H1 receptor compatibility | Exploratory, not supported as a stronger-than-taxonomy claim | Current receptor summaries do not beat genome-similarity + K/O baselines in the primary comparison. |
| H2 prophage receptor reservoir | Not the focus of the current PR stack | Requires larger prophage/host cohort and structural/synteny association analysis. |
| H3 breadth versus modularity/counter-defense | Descriptive breadth available only | Spot-test breadth exists, but feature association is not claim-ready. |
| H4 defense/counter-defense improves productive-infection prediction | Blocked | No productive-infection, plaque, propagation, or EOP labels exist. |
| H5 host lineage/prophage/defense landscape | Data-dependent | Host defense evidence exists for benchmark hosts, but lineage/ecology analysis is not mature. |
| H6 source/ecology novelty | Data-dependent | Requires broader source-balanced atlas and ecological source labels, not database provenance alone. |

## Reviewer-Safe Claims

Allowed now:

> The repository contains a reproducible, config-driven benchmark workflow with reviewed spot-test outcomes, production receptor evidence, host K/O typing evidence, genome-similarity baselines, and host defense/phage anti-defense candidate evidence for the PhageHostLearn benchmark.

Allowed now:

> In the current exploratory H1 benchmark, receptor-feature summaries do not outperform genome-similarity plus host K/O baselines under the primary cold-phage-cluster comparison.

Not allowed now:

> RBP/depolymerase features explain Klebsiella phage host range better than taxonomy.

Not allowed now:

> Defense/counter-defense features explain infection failure or improve host-range prediction.

Not allowed now:

> Spot-test positives demonstrate productive infection or therapeutic suitability.

## Immediate Next Steps

1. Review and merge PR #12.
2. Rebase/retarget PR #13 onto the updated base after #12 merges, then review and merge PR #13.
3. Rebase/retarget PR #14 after #13 merges, then review and merge PR #14.
4. After the stack is merged, rerun the production workflow and claim audits from the merged `main` state.
5. If testing H4 remains a priority, curate productive-infection, plaque, propagation, or EOP outcomes. Defense/counter-defense evidence alone cannot test H4.
6. If expanding toward a Genome Biology-level atlas, scale source curation and sequence-backed annotation beyond the benchmark while preserving source-overlap and claim-boundary audits.

## What Not To Do Next

Do not add a new dashboard, framework, model registry, or broad abstraction layer before the current PR stack is reviewed. The next work should either be review/merge hygiene or a real data unlock, not more scaffold expansion.
