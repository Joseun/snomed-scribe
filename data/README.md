# SNOMED subset — verification needed

The codes in `snomed_subset.csv` are the commonly-cited SNOMED CT concept
IDs for these terms in public FHIR/SNOMED examples. They have **not** been
cross-checked against a licensed terminology browser (e.g. NHS TRUD) and
should be verified before the project relies on them for anything beyond
scaffolding/demo purposes.

Tracked as a follow-up task: verify each code against NHS TRUD's SNOMED CT
UK release, and extend the subset to ~100-200 concepts once verified.
