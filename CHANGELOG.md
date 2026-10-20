# Changelog

## Unreleased

### Model inventory coverage

- Add a separate machine-readable inventory with many-to-many code/model/contract
  bindings, explicit model settings, and reviewed file classifications/digests.
- Add `mceg coverage [ROOT] [--inventory PATH] [--json]` to detect uncontracted
  models, missing or mismatched references, unlisted contracts, absent definitions,
  and new/changed source or coefficient files. AST checks never import providers.
- Keep source-review status, model registration, numerical evidence and physical
  support distinct. Document the initial-review and scope limits of detection.

Validation: 359 MCEG tests passed, including 33 coverage regressions. Actual
provider inventories map all 9 ExoEOS and 12 ExoGibbs contracts, while exposing
28 and 8 uncontracted entries and 7 and 188 unreviewed files, respectively.
Eight mutations per provider produced the expected new gaps; an additional
case per provider records the limit of detecting an entirely omitted variant
when its shared file and contract remain mapped.

### Volatile-solubility quantities

- Add distinct v0.2 quantities for H2O/CO2/N2 partial pressures and H2O/He/CO/CH4
  fugacities, identified while reviewing ExoGibbs solubility laws and ExoEOS
  magma models. Existing pressure-unit conversion and exact sample matching
  apply without treating these inputs as total melt pressure or as each other.
- Preserve the v0.1 schema and existing scientific assessments. No provider
  imports, solver execution, new dependencies, or automatic support rules.
- Document the provider authoring workflow using fourteen new provider-owned
  contracts, separate numerical/physical reviews, actual test receipts and
  selected-file verification. Numerical execution is an optional provider task,
  outside MCEG core.

Validation: 326 MCEG tests passed. All 21 provider contracts validated, including
the 14 new records; their 70 selected numerical/hash checks passed. The provider
runs recorded 877 ExoEOS and 72 ExoGibbs tests, and seven provider metadata checks
passed. A real Sun-Yao Context preserved unknown physical support while missing
partial pressure, substituted fugacity and changed oxide composition produced
the expected distinct membership outcomes.

### Authored task completion (`0.2.0rc2`)

- Add optional v0.2 `follow_up_resolutions` with a task reference, nonempty
  Evidence references and completion note. Reject missing references and duplicate
  completions. Show completed tasks separately with links to their evidence,
  preserving historical source fields, support and v0.1 restoration. Existing
  v0.2 documents remain readable; rc1 rejects the new field even when empty.
- Exercise completion, scoped checks and preservation of history using synthetic
  records. Scientific reviews and completion declarations remain provider-owned;
  MCEG does not depend on a particular provider, paper or review dataset.

Validation: 302 tests passed, including 12 synthetic completion cases covering
pending/completed work, invalid references, scoped navigation and unchanged
source traces, support judgments and v0.1 restoration.

### Scoped file verification

- Add `mceg check --assessment ID` and share its Evidence dependency audit with
  `explain --assessment ID`. Display the selected Subject and Context, preserve
  historical records, and keep stored support distinct from fresh verification.
- Add optional `--root DIR` file verification to both commands, requiring a
  selected v0.2 Assessment. Check its Subject manifest and Evidence dependency
  artifacts. Report missing, unreadable and mismatched files as failures; URI
  sources and absent pins remain unknown. Paths must stay within the root.
- Preserve root selection in follow-up commands and report per-file expected
  and observed hashes in JSON. No schema or runtime dependency changes.

Validation: 290 tests passed in the isolated PR checkout, including 28 file
verification tests. ExoInventory's 15 contract tests passed, and its selected
refactor review matched 26 Subject files and 6 Evidence artifacts.

### v0.2 release candidate (`0.2.0rc1`)

- Make `mceg explain` easier to scan in a terminal with colored status markers,
  numbered tasks, separate requirements/completion criteria, readable record
  labels and compact file/sample counts. Preserve the original text with
  `--plain` and automatic pipe output; JSON remains complete and unchanged.
  Extend `mceg -h` and `mceg explain -h` with command and usage examples.
- Add `--lang ja` to `check` and `explain` for Japanese UI messages and suggested
  work. Language follows copyable drill-down commands. A display-only catalog
  preserves authored scientific text, status tokens, IDs, JSON reports and
  default English output; no translated fields or dependencies are added.
- Add a separate `schema_version: "0.2"` reader and common Claim, Evidence,
  Subject, Context, Condition and Assessment records. Claim has no support
  status; support belongs to a scoped Assessment targeting an explicit Claim
  revision, with method identity and reasons. Historical numerical results
  retain their meanings.
- Add `mceg migrate` and validated-data restoration. Migration preserves old
  declarations, source/content hashes, prose scopes and Evidence identities,
  without inventing calculation conditions or rewriting Claim text. New records
  can coexist with the imported history. Existing v0.1 validation and tracing
  remain supported; old readers reject the new schema.
- Add `mceg assess` for source-scoped closed ranges and explicit joint samples.
  K and Pa/bar/MPa/GPa comparisons preserve quantity identity; total pressure
  and fugacity are not interchangeable. Missing input stays unknown; invalid
  values are errors. Membership does not infer scientific support.
- Export the existing reviewed curated-gas policy through `mceg assess
  --curated`, identifying selected files, archived artifacts, requested context,
  and both evaluator/review hashes. The adapter executes no provider code and
  preserves historical declarations and passes when current reuse is unknown.
- Add on-demand `mceg explain` views for Evidence, Claims and Assessments.
  Normal checks show a single command preserving the requested selection and
  context. Deep views distinguish recorded follow-ups from derived suggestions,
  show required material and completion criteria, and offer navigation to
  upstream gaps. The H2 v0.2 example records original-paper access/inspection
  tasks without treating document acquisition as completed review.
- Parse JSON as JSON, preserving exponent-valued numbers such as `1e-13`, while
  rejecting duplicate keys in both YAML and JSON. Values formerly misread by
  YAML as text now retain their JSON numeric type and can be rejected where a
  text field is required. Output commands write JSON for `.json` paths and YAML
  otherwise, and refuse to overwrite existing artifacts.
- Document migration, identity, assessment limits and terminal workflows in
  the README and [v0.2 guide](docs/en/v02.md). Runtime dependencies are unchanged.

Validation: 250 tests passed, covering all five baseline migrations, restoration
after adding new evidence, provenance compatibility, malformed references and
units, historical coexistence, exact samples, curated exports and actionable
source gaps. The installed wheel was checked outside the source tree against
the six real ExoGibbs contracts, four requested curated contexts, the H2 example,
and a changed implementation in a temporary provider copy. Original provider
files and scientific archives were not modified; no solver was executed.

Japanese UI follow-up: 254 tests passed. Language selection preserves JSON
byte-for-byte, authored text, exit codes, requested conditions and quoted paths
through drill-down commands. Default English output remains unchanged.

Explain UI follow-up: 262 tests passed. Across eight views in English and
Japanese, 48 comparisons against the preceding wheel preserved redirected text,
`--plain` and JSON byte-for-byte. Terminal checks covered colors, monochrome,
ASCII markers, and quoted navigation commands at 50 columns.

### Earlier CLI work in this candidate

- Add `mceg check` with automatic contract discovery, path filtering, readable
  PASS/FAIL/UNKNOWN results, verbose audit gaps, and optional JSON output.
  The command checks recorded structure and source traces for all contracts and
  reuses the reviewed curated-gas evaluator for file integrity, requested context,
  temperature bounds, and archived sample coverage. It runs no numerical solver.
- Use colored status markers, readable labels, highlighted totals, and wrapped
  explanations on terminals. Add `--plain` for the original text layout, select
  it automatically for pipes/redirection, and honor `NO_COLOR` and `TERM=dumb`.
  ASCII-only output streams use `+`/`x` markers. JSON reports remain undecorated.
- Package the shared curated evaluator, review pins, and archived default context
  so the command works from provider checkouts and wheel installations. Replay
  the saved assessment to record the extracted evaluator's hash; historical
  numerical evidence and assessment outcomes are unchanged. Existing validation
  and tracing behavior, v0.1 schema, and runtime dependencies are unchanged.

CLI validation: 194 MCEG tests passed. A wheel installed outside the source tree
discovered all six ExoGibbs contracts and reproduced the default, unsampled,
out-of-range, and different-JAX outcomes. An isolated copy of the real curated
archive detected a changed implementation while retaining its historical pass.
No numerical solver was executed for these CLI checks.
Terminal display checks confirmed color and monochrome modes, narrow-width
wrapping, and ASCII marker fallback. Plain/redirected text and JSON were compared
byte-for-byte with the preceding output formats; all 194 tests still pass.

Earlier example trials:

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

Earlier trial validation: 118 MCEG tests passed, including 44 H2 range-assessment checks; eight
bundled contracts/templates passed structural validation. The saved 1750 K
assessment reproduces the differing source outcomes, and the CLI also runs from
outside the checkout. Earlier provider trials validated both provider-owned
contracts and passed four H2 replay checks after metadata commits changed both
provider HEADs; the placement/revision trial also completed outside the checkout.
Those trials changed no frozen schema, public API, core implementation, dependency,
baseline contract or scientific provider implementation. Their scripts and receipts
are example-only.

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
