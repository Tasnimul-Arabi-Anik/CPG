# Scientific Analysis Contract

This contract defines the units of analysis, outcomes, predictors, and readiness gates for the Klebsiella phage comparative genomics study. It prevents the workflow from mistaking metadata availability for biological compatibility.

## Core Rule

The central pairwise host-range question requires a tested phage-host assay row. Isolation host, reported host, prophage resident host, and predicted host relationships are not productive-infection outcomes.

## Readiness Levels

| Level | Meaning | Allowed use |
| --- | --- | --- |
| `plumbing_ready` | Scripts run and write correctly shaped outputs. | Workflow and software claims only. |
| `seed_data_ready` | Reviewed seed rows exercise real-data paths. | Minimum-real-data review and curation planning. |
| `analysis_ready` | Required outcome, predictors, and inclusion rules are populated at sufficient scale. | Quantitative analysis with cautious interpretation. |
| `claim_ready` | Analysis passes leakage, split, baseline, uncertainty, and sensitivity checks. | Manuscript claims stated with limitations. |
| `manuscript_ready` | Claims, figures, methods, raw acquisition, and validation audits are complete. | Submission-oriented manuscript package. |

One seed row can satisfy `seed_data_ready`; it cannot satisfy `analysis_ready`, `claim_ready`, or `manuscript_ready`.

## Canonical Data Tables

| Table | Unit | Purpose |
| --- | --- | --- |
| `phages.tsv` or phage manifest | One phage genome | Atlas, dereplication, annotation, RBP/depolymerase and anti-defense evidence. |
| `hosts.tsv` or host metadata | One host genome | K/O/ST/AMR/virulence and defense-system evidence. |
| `results/<profile>/metadata/phage_host_relationships.tsv` | One non-assay phage-host relationship | Provenance for isolation host, reported host, resident host, predicted host, or assay-panel membership. |
| `results/<profile>/metadata/phage_host_assays.tsv` | One tested phage-host pair per study/panel/assay | Response variable for receptor compatibility, host-range breadth, and productive-infection modeling. |

## Hypothesis Contracts

| Hypothesis | Unit of analysis | Outcome | Required predictors | Current readiness rule |
| --- | --- | --- | --- | --- |
| H1a | Phage or known positive phage-host association | K/O tropism among known positives | RBP/depolymerase modules, taxonomy, genome similarity, host K/O | Association proxy only until production phage receptor features and host K/O evidence are jointly available for the positive set. |
| H1b | Tested phage-host pair | Adsorption, spot, plaque, EOP, or initial interaction outcome | RBP/depolymerase modules and host K/O/receptor features | Spot-test positives and negatives are curated for the PhageHostLearn benchmark, and benchmark host K/O result rows are available; receptor-compatibility claims remain blocked until production assay-phage RBP/depolymerase/domain evidence and grouped cold-host/cold-phage/cold-study evaluation are available. |
| H2 | Prophage protein, module, or host genome | Prophage RBP/depolymerase candidate status and host K/O association | Prophage calls, RBP/depolymerase evidence, host K/O, structural/domain evidence | Exploratory until larger host/prophage cohort and production evidence are present. |
| H3 | Phage with a tested host panel | Spot-test host-range breadth across tested hosts, with K-type/lineage breadth when host typing is available | RBP modularity, recombination/domain features, anti-defense burden | Seed profile has initial-interaction breadth labels; production benchmark host typing is available, but claims remain blocked until production RBP/counter-defense features are available and panel/lineage-aware analyses pass. |
| H4 | Tested phage-host pair, preferably receptor-compatible subset | Productive infection, plaque, EOP, or explicitly curated infection outcome | Receptor features, host defense systems, phage counter-defense features, study/panel covariates | Blocked until productive-infection labels exist; compatibility strings are not valid biological targets. |
| H5 | Host genome or lineage | Prophage burden, defense-system burden, or lineage-associated repertoire | ST, AMR, virulence, species-complex member, prophage and defense annotations | Separate host-population analysis; not a phage infectivity claim. |
| H6 | Phage genome, module, or ecological source stratum | Novel RBP/depolymerase candidate enrichment | Ecological source, phage cluster size, annotation depth, sequence completeness | Exploratory unless ecological source is separated from database provenance. |

## Modeling Rules

- Random pair-level splits are debugging checks, not primary evidence.
- Primary pairwise models must use grouped evaluation that can test cold-host, cold-phage, cold-cluster, and cold-study performance.
- Receptor-only, defense-only, counter-defense-only, and combined models must be compared against observed assay outcomes, not labels constructed from the same features.
- H4 must be tested as an incremental contribution among receptor-compatible or initial-interaction-positive pairs when those labels exist.
- Null results are allowed. The defense/counter-defense layer may fail to improve prediction, and that outcome should be reported honestly.

## Claim Boundaries

Allowed now:

```text
The repository implements a reproducible framework for curating genomes, evidence, and assay outcomes needed to test receptor and defense/counter-defense hypotheses.
```

Not allowed yet:

```text
RBP/depolymerase modules predict Klebsiella host range better than taxonomy.
Defense/counter-defense compatibility explains productive infection.
The workflow predicts infection success or recommends therapeutic phages.
```

Stronger claims require populated assay outcomes, production evidence, leakage-safe model evaluation, uncertainty estimates, and claim-support audit approval.
