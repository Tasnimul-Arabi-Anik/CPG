# Klebsiella phage comparative genomics

## Scientific objective

Determine which novel comparative genomic analyses are feasible with the available Klebsiella phage and host data.

The leading hypothesis is that phage-host compatibility reflects both:

1. receptor compatibility, including RBP/depolymerase and host K/O type;
2. intracellular compatibility, including bacterial defense systems and phage counter-defense genes.

Do not assume this hypothesis can be tested until the available host-range and host-genome data have been audited.

## Operating principle

Use established bioinformatics tools wherever possible.

Do not implement replacements for existing annotation, clustering, alignment, taxonomy, host-typing, structure-search, or defense-detection software.

Before writing custom code:

1. identify whether an established tool already performs the task;
2. inspect its documented inputs and outputs;
3. run it on a small real dataset;
4. write glue code only if needed to combine or analyze its results.

## Permitted custom code

Custom scripts may be written for:

- metadata cleaning and validation;
- output parsing and table joining;
- statistical analysis;
- visualization;
- reproducible execution of established tools.

Do not create placeholder modules or hypothetical output tables.

## Development rule

Begin with a pilot of real genomes.

Do not build a full workflow manager until individual commands have successfully run and their outputs have been inspected.

Every completed task must report:

- tool and version used;
- exact command run;
- input files;
- output files;
- records retained or excluded;
- errors or uncertainties;
- scientific interpretation.

Use existing tools directly. Do not create a wrapper, abstraction layer, database, dashboard, API, application, or reusable framework unless the current analysis cannot be completed without it.

No placeholder files.

Before writing more than 100 lines of custom code, state which existing tools were considered and why none solves the requirement.

Prioritize obtaining a scientifically interpretable result from real data over improving repository architecture.

## Scientific safeguards

Distinguish:

- experimentally measured host range;
- predicted host association;
- isolation host;
- prophage host;
- computational inference.

Do not treat these as interchangeable.

Do not claim a host-range predictor without independent test data.
Do not claim novelty solely because a sequence has no close BLAST hit.
