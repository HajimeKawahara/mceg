# Changelog

## Unreleased

- Add an example-only H2 range evaluator with separate metadata/Seo temperature
  intervals and the original abstract's study-wide pressure envelope. It records
  source-bound assessments, converts pressure units, preserves missing inputs as
  unknown, and requires review when the pinned contract changes. Physical
  validation remains unknown; no Claim status is inferred.
- Document Claim/Evidence/Assessment separation and a proposed later-schema
  migration that preserves historical declarations and execution outcomes.
- Add a consumer replay for provider-owned H2 contracts, retaining the nine
  manual assessments and checking selected source identity separately from HEAD.
  The provider pilots retain their original scientific implementations and dependencies.
- Add a fixed-composition Second Virial mixture connection through the actual
  ExoEOS provider and ExoGibbs callback, with two v0.1 contracts, manual assessments
  and a saved four-state execution passing 35 numerical checks.
- Exercise provider-local placement of the five baseline contracts, explicitly
  report missing files and unchecked citations, and record a synthetic revision
  review that preserves historical passes without assigning them to new code.
- Document the trials and their design findings in English and Japanese.

Validation: 118 MCEG tests passed, including 44 H2 range-assessment checks; eight
bundled contracts/templates passed structural validation. The saved 1750 K
assessment reproduces the differing source outcomes, and the CLI also runs from
outside the checkout. Earlier provider trials validated both provider-owned
contracts and passed four H2 replay checks after metadata commits changed both
provider HEADs; the placement/revision trial also completed outside the checkout.
No frozen schema, public API, core implementation, dependency, baseline contract
or scientific provider implementation changed. Scripts and receipts are example-only.

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
