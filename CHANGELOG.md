# Changelog

## Unreleased

- Add a fixed-composition Second Virial mixture connection through the actual
  ExoEOS provider and ExoGibbs callback, with two v0.1 contracts, manual assessments
  and a saved four-state execution passing 35 numerical checks.
- Exercise provider-local placement of the five baseline contracts, explicitly
  report missing files and unchecked citations, and record a synthetic revision
  review that preserves historical passes without assigning them to new code.
- Document the trials and their design findings in English and Japanese.

Validation: 68 MCEG tests passed; eight contracts/templates passed structural
validation; the placement/revision trial completed from outside the checkout.
No frozen schema, public API, core implementation, dependency, baseline contract
or provider checkout changed. The scripts and receipt formats are example-only.

## 0.1.0 - 2026-10-15

Freeze the first experimental MCEG baseline with `schema_version: "0.1"`.

- Describe model implementations, assumptions, domains, claims, evidence, and
  limitations in YAML, with an independent Pydantic validator.
- Trace optional evidence provenance and report uninspected sources, unchecked
  comparisons, and discrepancies without promoting scientific claims.
- Include five model contracts and a reproducible H2 EOS-to-solubility example
  with manual applicability assessments and a saved numerical execution receipt.
- Record the partial primary-source audit and unresolved design questions in
  English and Japanese.
- Define the [freeze and compatibility policy](docs/en/versioning.md): schema
  extensions require a new schema version; scientific findings remain revisable.

Validation: 61 MCEG tests passed, all five contracts passed structural validation,
and the saved H2 execution passed four numerical checks. The package wheel built
successfully and validated all five contracts without importing provider packages.
Physical validation of the complete H2 calculation remains unknown.
