# SNOMED subset

Every code in `snomed_subset.csv` has been checked against the SNOMED CT
International Edition via a public HL7 FHIR terminology server
(`https://tx.fhir.org`, `CodeSystem/$lookup` on `http://snomed.info/sct`) —
confirmed active and correctly named. This caught two real errors in the
original (unverified) data: `13791008` was Asthenia, not Asthma, and
`89362005` ("Weight loss") was inactive, superseded by `816160009`.

This is **not** the same as verification against NHS TRUD's licensed UK
SNOMED CT release — the International Edition can differ from the UK
extension in places — so this subset should still be treated as
demo/scaffolding-scope, not a source of truth for a real clinical system.

Tracked as a follow-up task: verify against NHS TRUD's UK release, and
extend the subset to ~100-200 concepts (currently 15) covering the range
of common UK primary-care presentations described in docs/SPEC.md.
