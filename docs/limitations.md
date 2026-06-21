# Limitations

This project starts as a computational comparative genomics study. Predictions should not be presented as experimentally validated host range unless linked to adsorption, infection, plaque, efficiency-of-plating, or similar assay data.

Known limitations to track:

- Public phage-host metadata may be incomplete or inconsistent.
- The current seed profile includes reviewed PhageHostLearn spot-test outcomes, which support initial-interaction and panel-breadth screening only. They do not support productive-infection, plaque, EOP, or defense/counter-defense prediction claims.
- Local PhageHostLearn sources currently available in this repository contain spot-test matrix values and genome archives, but no plaque, EOP, propagation, or productive-infection outcome table. H4 therefore requires an additional curated productive-infection endpoint source before any defense/counter-defense prediction test is valid.
- PhageHostLearn RBPbase/Locibase bridge metadata are useful for seed screening coverage, but they are not production structural/domain annotation, Kaptive/Kleborate K/O/ST typing, or functional receptor validation.
- Isolation host, reported host, prophage resident host, and predicted host relationships must not be treated as tested susceptible or resistant outcomes.
- Current local BLASTN pairwise similarity evidence is a conservative initial baseline; comprehensive species-like clustering still requires reviewed all-vs-all similarity across the expanded public phage/prophage dataset, preferably with VIRIDIC, Mash, or an equivalent documented method.
- Checksum-verified seed FASTA files prove local raw-file reproducibility only for those rows; ignored `data/raw/` files still need reviewed acquisition or reconstruction on a clean checkout before production analyses.
- Current GenBank CDS product annotations are accession-backed bridge evidence, not a standardized de novo Pharokka/PHROGs/Phold annotation layer.
- Capsule and O-locus calls may be missing for historical phage hosts.
- Prophage RBP candidates may be inactive remnants.
- Structure-informed annotation can identify remote similarity but does not prove receptor specificity.
- Defense/counter-defense annotations are incomplete because many anti-defense genes remain undiscovered.
- Broad host range can reflect testing effort rather than intrinsic generalism.

Each manuscript claim should distinguish observation, computational inference, and experimentally validated conclusion.

Claim wording and remaining speculative claims are tracked explicitly in `docs/claim_ledger.md`. Reviewer-sensitive bridge-versus-production gaps are tracked in `docs/reviewer_pipeline_gap_audit.md`.

## Assay Feature Coverage

The seed profile contains reviewed spot-test outcomes, but most explanatory biological features are not yet production-assessed for the assay benchmark entities. Missing RBP, domain, structural, K/O/ST, defense, or counter-defense evidence must be interpreted as `not_assessed`, not as biological absence. H3 therefore has descriptive spot-breadth values but no supported RBP/counter-defense enrichment claim until production feature coverage is sufficient.
