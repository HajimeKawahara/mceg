# Add a model contract to a provider

Use a provider-owned `mceg/contracts/<model>.yaml` to describe one model family,
its conventions, and the evidence actually reviewed. Start with v0.2 for new
records. Keep MCEG outside the provider's runtime dependencies.

This procedure was exercised on 2026-10-20 with six ExoGibbs solubility laws and
eight ExoEOS liquid, fluid, alloy and solute constructions. Each provider has
`mceg/model_inventory.md`, the new contracts, and
`results/mceg/20261020_model_survey/{receipt.json,tests.xml,tests.log}`.
The audited source revisions are:

| Provider | Revision | Fresh numerical tests |
| --- | --- | --- |
| ExoEOS | `37b9173f37866495949fd7c90340a02b7ceaa78d` | 877 across ten modules |
| ExoGibbs | `7dc3ce1183c0b3d74e24cde502f638cac3625b83` | 72 across two modules |

The examples below assume those provider checkouts and an MCEG environment
containing the new volatile quantity names. An older `0.2.0rc1` installation
may reject these names; this extension is recorded under Unreleased.

## 1. Define the model before writing YAML

Read the public entry point, implementation, coefficient data, documentation
and relevant tests. Check existing contracts first. Record the implementation
revision with `git rev-parse HEAD` and inspect working-tree changes.

Write down the ordered components, amount/concentration basis, native units,
standard states, returned quantity, model options and caller obligations. A
function name alone is often insufficient:

| Decision | Example from the survey |
| --- | --- |
| Empirical law or thermodynamic construction? | ExoGibbs Sun-Yao returns water capacity/concentration; ExoEOS integrates supplied capacities into extensive G |
| What is the driving quantity? | H2O/CO2/N2 partial pressure, CO fugacity in bar, CH4 fugacity in GPa |
| What does a fraction measure? | CO returns elemental-C mass fraction; N returns elemental-N mass fraction; CH4 returns molecular mole fraction |
| What is the denominator? | Binary water mass is divided by dry-plus-water mass; H2 and He do not silently enter that denominator |
| Which model option was selected? | `water_model`, `helium_host`, EOS species order and root policy belong to the calculation identity |
| Is the returned energy full or excess? | Native magma G already includes standards and mixing; a second mixing term would be counted twice |

Separate models when standards, coefficients or physical assumptions change.
For example, mode-4 hydrous liquid at zero carbon remains distinct from mode 1.
A family contract may document several options, but a concrete application
must retain the chosen options in its Context and supporting artifacts.

Record these boundaries in `mceg/models.yaml` before linking contracts. Use one
inventory entry per reviewed model/choice, with explicit file/symbol bindings
and settings. Several entries may share a function and family contract; several
functions may implement one model. Keep known missing contracts as empty links,
classify reviewed support files with a reason, and leave other files unreviewed.
See the [inventory format and detection limits](coverage.md). File hashes guard
the reviewed snapshot; they cannot discover an omitted pre-existing model.

## 2. Separate numerical domains from scientific applicability

Put implementation constraints under `domains: numerical_evaluation`: supported
shapes, positive inputs, composition faces, singular derivatives, root choices
and caller-side validation. Distinguish an implemented rejection from a caller
obligation; a traced function may check shapes only.

Use `scientific_applicability: unknown` when the relevant material and conditions
have not been established. Published or provider-reported marginal T/P bounds
can be recorded as separate range Conditions with their own source. They do not
establish a jointly validated rectangle. A test grid is numerical coverage,
not an experimental envelope.

Current structured Conditions support closed ranges and exact joint samples.
Keep composition inequalities, phase/root constraints and relationships such as
`p_H2O <= P_melt` in the documented domain unless explicitly represented by an
existing evaluator. MCEG does not infer those constraints from prose.

## 3. Record what was inspected

For each Evidence record, retain source paths or immutable URLs, the relevant
location, scope, inspection status and any upstream dependency. Local paths
resolve from the provider root, not the YAML directory.

Distinguish implementation inspection, source inspection and a completed
comparison. Reading a DOI or provider metadata does not inspect the original
paper. Use `not_inspected`, `partial` and `comparison: not_checked` where
appropriate; explain the missing material in a Follow-up. If the actual
evidence is a provider transcription, describe that role explicitly.

In this survey, solubility calibration marginals remain provider-reported.
Original-source gaps remain visible. Stored MELTS reference comparisons retain
their source/binary provenance, without claiming that the external programs or
experiments were freshly executed.

## 4. Execute a relevant numerical check and save its receipt

Select existing tests that examine the model's actual contract: formula values,
unit conversions, an independent reference, amount derivatives, host response,
boundaries or conservation. Add a regression only when a needed behavior lacks
coverage. Record an unexecuted test as `not_run`.

For example, from ExoGibbs, using its numerical Python environment:

```bash
mkdir -p /tmp/sun-yao-review
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 \
python -m pytest -q -p no:cacheprovider \
  tests/unittests/solubility/sun_yao2026_test.py \
  --junitxml=/tmp/sun-yao-review/tests.xml \
  > /tmp/sun-yao-review/tests.log 2>&1
```

Check the exit status and JUnit outcomes before declaring a pass. Save a receipt
with the command, working directory/import location, Python and dependency
versions, backend/precision, source revision, selected-file hashes and artifact
hashes. Check selected files against the recorded Git objects and verify that
their bytes did not change during execution. Include coefficient data, test
definitions and reference fixtures as well as implementation files. State the
limits of the manifest; selected files do not constitute a complete environment
or transitive dependency lock.

The survey's receipts retain each executed module separately, with combined
JUnit and log files. Shared tests may support several contracts; do not count
them as independent repetitions or empirical samples. The receipt JSON is a
provider artifact, not an additional MCEG schema.

## 5. Author the v0.2 records

Use a small existing provider contract such as
`exogibbs/mceg/contracts/ch4_ardia2013.yaml` as a structural example, replacing
every model-specific statement, source, identity and hash. Sun-Yao additionally
illustrates joint samples with oxide settings; ExoEOS `mass_fraction_solute.yaml`
illustrates a mathematical construction without an empirical calibration.

| Record | What to supply |
| --- | --- |
| `model`, assumptions, domains, limitations | The reviewed model identity and conventions, with Evidence references |
| `subjects` | Audited implementation revision, entry points and selected-file SHA-256 manifest |
| `contexts` | Actual execution environment, or explicit requested physical inputs and model options |
| `claims` | Propositions with revision and scope; numerical verification and physical accuracy are separate |
| `evidence` | Inspected sources and actual run records, with original results and artifact hashes |
| `conditions` | Only explicit source-scoped ranges or reviewed joint samples; omit when unavailable |
| `assessments` | Claim/Subject/Context/method-bound judgments, evidence IDs and reasons |
| `follow_ups` | Concrete action, required material and completion criterion for remaining gaps |

The survey uses `numerical_review` for its recorded numerical support and
`physical_review` for unknown empirical support. These are authored IDs, not
special engine rules. A numeric PASS cannot promote `physical_review`.

Pressure quantities keep their identity when units are converted. In particular,
`water_partial_pressure`, `water_fugacity` and `melt_total_pressure` cannot fill
in for one another. Use finite linear quantities; a log-pressure API does not
make a logarithm a pressure value. Record non-pressure inputs such as `delta_iw`
and oxide fractions in explicit Context settings when using joint samples.

## 6. Validate structure, bytes and intended outcomes

From the provider root, with the companion MCEG environment active:

```bash
mceg coverage .
mceg mceg/contracts/h2o_sun_yao2026.yaml
mceg check mceg/contracts/h2o_sun_yao2026.yaml \
  --assessment numerical_review --root .
mceg explain mceg/contracts/h2o_sun_yao2026.yaml --assessment physical_review
```

Coverage checks the inventory independently and returns 1 for known remaining
gaps; the survey's provider inventories intentionally have such gaps.
The contract-path command validates structure and references. `check` checks the
selected Subject and run-artifact hashes and reports the stored numerical
judgment; it does not rerun the solver. `explain` describes the empirical gap.
With matching files, this survey's selected numerical checks pass and physical
support stays unknown. An unrestricted check also includes source-review gaps.

Exercise at least one meaningful Context for structured Conditions:

```bash
mceg assess mceg/contracts/h2o_sun_yao2026.yaml \
  --context mceg/contexts/sun_yao_formula_sample.json --subject survey_20261020 \
  --output /tmp/sun-yao-assessed.yaml
mceg check /tmp/sun-yao-assessed.yaml
```

The supplied Context reproduces one joint formula sample. Test that a missing
water partial pressure stays unknown when only total pressure is supplied,
that changing composition loses exact sample membership, and that passing
marginal bounds does not alter the physical Assessment. Output paths must be
new; preserve the input contract.

Add a small provider-side consistency check if the repository tracks evidence
snapshots. The survey uses `tests/unittests/mceg_model_survey_test.py`, requiring
only the standard library to check hashes and receipt/JUnit agreement. General
YAML validation remains in the optional MCEG environment.

## 7. Review and update without rewriting history

Link the contract from the provider's MCEG guide and inventory. Confirm that
the tested revision is the implementation revision, not the future commit that
publishes the metadata. Review the diff for accidental scientific or dependency
changes. Contracts, receipts and checks belong in the same reviewable change.
Check `git status --untracked-files=all` and `git check-ignore -v` for every
pinned artifact. Add narrow ignore exceptions when required; otherwise a local
hash check can pass while the receipt or log is missing from the committed tree.

When code, coefficients, options or environments change, review affected Claims
and Conditions, rerun relevant tests, save a new receipt, and add the appropriate
Subject, Context and Assessment. Preserve the prior revision in archived records
or version history. Do not refresh hashes alone to make an old pass appear fresh.
When only a citation becomes available, update its inspection/comparison evidence
without inventing a new numerical run or upgrading physical support.

This procedure is complete for a model when its scope and remaining unknowns
are explicit, references and pins validate, the declared checks have actual
outcomes, and a later maintainer can repeat the review. Complete scientific
validation is a separate claim that may remain unresolved.
