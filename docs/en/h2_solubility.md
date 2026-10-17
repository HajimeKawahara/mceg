# Worked example: pure-H2 fugacity to dissolved H2

At **1700 K and 7500 bar**, the solubility law's reported temperature and
total-pressure intervals include the inputs, while the upstream EOS is evaluated
outside its reported pure-H2 PVT data envelope. The accuracy of the resulting
dissolved-H2 concentration remains **unknown**. This is the first concrete MCEG
case: a successful calculation can contain both extrapolation and missing evidence.

## Calculation and artifacts

The case follows the H2 path of ExoGibbs's existing
[`compare_solubility_laws.py`](https://github.com/HajimeKawahara/exogibbs/blob/6b4cef45d2a6f1eb1462afd6cb6d3f1c77dba8ea/examples/comparisons/compare_solubility_laws.py).
It assumes pure molecular H2, with gas mole fraction 1 and the `vapor` root
selector. The actual melt composition is unspecified. This evaluates a law;
it does not solve gas-magma equilibrium, speciation, or phase stability.

1. ExoGibbs's pure-gas adapter converts 7500 bar to 7.5e8 Pa for ExoEOS's
   `ZhangDuanEOS.from_species(("H2",))` and obtains `ln(phi_H2)` at 1700 K.
2. Pure-gas fugacity is `f_H2_bar = exp(ln(phi_H2)) * 7500`.
3. ExoGibbs evaluates `X_H2 = f_H2_bar * exp(-11.403 - 0.76 * 0.75)`.
   Here 0.75 GPa is the **actual melt pressure**, independently of fugacity.

`X_H2` is dissolved H2 mole fraction. Temperature enters the EOS; the solubility
function has no temperature or melt-composition argument. Their absence does not
remove the empirical law's temperature and composition restrictions.

The two model contracts are [pure-H2 EOS](../../contracts/zhang_duan_h2.yaml) and
[H2 solubility](../../contracts/h2_solubility.yaml).
[`case.yaml`](../../examples/h2_solubility/case.yaml) records the inputs,
connection, and nine **manually authored** assessments. It is an example-specific
format, not a new contract schema; do not pass it to the `mceg` CLI.
[`run.py`](../../examples/h2_solubility/run.py) replays the fixed calculation,
and [`result.json`](../../examples/h2_solubility/result.json) records numerical
outputs, checks, environment, upstream revisions, and selected source hashes.
The runner does not compute or update the scientific classifications.

The recorded CPU/float64 run on 2026-10-15 JST produced:

| Quantity | Computed value |
| --- | --- |
| H2 fugacity coefficient, `phi` | 2.256112 |
| H2 fugacity | 16920.84 bar |
| Dissolved H2 mole fraction | 0.106811 |
| Ideal-fugacity control, `f = P` | 0.0473427 |
| Nonideal/ideal concentration ratio | 2.256112 |

The ratio follows from the law's linear dependence on fugacity at fixed melt
pressure. It is a numerical model consequence, not a validated physical prediction.

## Manual applicability assessment

| Scope | Classification | Basis and limit |
| --- | --- | --- |
| EOS temperature | Extrapolation | 1700 K exceeds the reported pure-H2 PVT data interval, 250–423 K. |
| EOS pressure | Extrapolation | 750 MPa exceeds the reported pure-H2 PVT interval, 2–700 MPa. |
| Solubility temperature, metadata | Within reported range | 1700 K lies in 1673–1773 K. |
| Solubility temperature, formulation | Within reported range | 1700 K also lies in Seo's narrower 1673–1723 K interval. |
| Solubility total pressure | Within reported range | 0.75 GPa lies in 0.7–3 GPa; the original abstract also confirms that study-wide envelope. |
| Solubility H2 fugacity | Unknown | Experimental fugacity coverage was not established. |
| Melt composition | Unknown | Seo specifies basaltic silicate; this case supplies no actual composition. |
| Retained solubility calibration | Unknown | A later calibration challenges the older concentration scale. |
| Accuracy of the complete connection | Unknown | No experimental comparison or uncertainty bound was established for this case. |

The EOS bounds come from [Zhang and Duan (2009), Table 5](https://doi.org/10.1016/j.gca.2009.01.021).
They describe PVT comparison data, not a fundamental EOS limit or a demonstrated
fugacity-error bound. Separate temperature and pressure bounds do not establish
coverage throughout their rectangle. The broader mixture ranges do not establish
pure-H2 accuracy at this state.

The two solubility temperature intervals are retained with their own sources:
[upstream metadata](https://github.com/HajimeKawahara/exogibbs/blob/6b4cef45d2a6f1eb1462afd6cb6d3f1c77dba8ea/src/exogibbs/solubility/volatile.py#L68-L88)
and [Seo et al. (2024), Section II.3 and Eq. 6](https://arxiv.org/html/2408.17056v1#S2.SS3).
Their difference does not change this case's temperature classification, but
must not be silently reconciled. Inclusion in either interval is insufficient
to classify the complete solubility calculation as physically applicable.

Seo is a secondary source for the experimental conditions. Its paragraph was
inspected, but the original basalt-specific run table was not checked against
it. The [source trace](provenance.md) records that missing comparison explicitly;
`within_reported_range` is not a claim of validation by original experiments.

The [primary-source audit](h2_primary_audit.md) confirms the study-wide pressure
envelope and separate basalt/andesite series directly from the original abstract.
It records the metadata temperature difference and the match between code and
Seo's expression, while retaining the uninspected original fit. A later caption
suggests a material-specific explanation of the temperature difference; it remains
a secondary account. These findings change the evidence trail, not the nine
classifications or the computed result.

[Chaudhari et al. (2025)](https://doi.org/10.1007/s00410-025-02272-y) challenges
the older infrared concentration calibration. That finding does not supply a
uniform correction for this case; the result is **not divided by ten**.

## Partial automatic range assessment

[`assess.py`](../../examples/h2_solubility/assess.py) evaluates three marginal
intervals in [`conditions.yaml`](../../examples/h2_solubility/conditions.yaml),
separately from the fixed EOS calculation and its manual assessments. These are
example-only formats, not additions to the v0.1 contract or public API. Neither
provider nor JAX is needed. No new experimental evidence is asserted.

The conditions retain each source's scope: implementation temperature metadata,
Seo's basaltic temperature interval, and the original abstract's study-wide
pressure envelope. Source selection is manual; numerical interval comparison
is automatic. The differing temperature bounds are not merged, intersected,
or interpreted as a demonstrated error in either source.

```bash
PYTHONPATH=src python examples/h2_solubility/assess.py --temperature-k 1750 --melt-pressure 7500 --pressure-unit bar --output /tmp/h2-assessment.json
```

| Context | Metadata temperature | Seo temperature | Study-wide pressure |
| --- | --- | --- | --- |
| 1700 K, 7500 bar | Within | Within | Within |
| 1750 K, 7500 bar | Within | Outside | Within |
| 1800 K, 7500 bar | Outside | Outside | Within |
| 1700 K, 5000 bar | Within | Within | Outside |
| Temperature omitted, 7500 bar | Unknown | Unknown | Within |

The [saved assessment](../../examples/h2_solubility/assessment.json) is the actual
output of the 1750 K command. It contains no EOS or concentration result at that
temperature. Its three `range_membership` assessments include condition IDs,
evidence references, scopes, converted values, classifications and reasons.
The report binds the context, conditions, evaluator and contract with SHA-256,
and records the implementation revision described by that contract. This is
assessment against the pinned audit, not a check of installed provider code.

Temperatures use K. Pressures accept Pa, bar, MPa or GPa; the command defaults to
bar. `--melt-pressure` means actual total melt pressure. For the original interface
case it is assumed equal to the total gas pressure; supply that physical quantity
explicitly. H2 fugacity is a distinct quantity even when expressed in bar.
The Python `run(inputs)` entry point can record `hydrogen_fugacity`, but never
uses it to fill a missing `melt_total_pressure`.

Each missing quantity yields `classification: unknown` with `reason: missing_input`.
Nonfinite values, nonpositive absolute temperatures, negative pressures, boolean
or string values, unsupported units, and misspelled fields are input errors.
They do not receive scientific classifications. Uncertainty-bearing inputs and
Celsius conversion are outside this small example and are rejected.

Bounds use closed intervals over the recorded decimal endpoints. Decimal unit
scaling preserves boundary inclusion; it adds no experimental precision or
uncertainty tolerance. `outside_reported_range` means outside that source's
recorded projection, not physically impossible. `within_reported_range` does
not establish composition agreement, joint coverage, or a physical error bound.
The output explicitly leaves these questions unevaluated and physical validation
unknown. In particular, a basaltic temperature comparison can be within range
while the melt's composition is unspecified.

The conditions pin the source contract's hash. If it changes, review the selected
evidence, values and scopes before updating the conditions and replaying this
assessment. Merely replacing the hash is not a source review. Tests also compare
the original 1700 K case with the recorded manual projections, and reproduce the
saved assessment including all hashes. The original `case.yaml`, numerical
`run.py`, and numerical receipts retain their existing meaning.

## Verification

All five model contracts pass the core validator. MCEG tests cover
manual-reference checks, source tracing, and execution-record consistency.
Those tests require neither upstream package nor JAX.

The recorded upstream runs used Python 3.12.7, JAX 0.6.2, NumPy 2.1.0,
pytest 8.3.3, CPU, and x64. The ExoEOS published-parameter factory test passed
**1 test**. The ExoGibbs scalar-law reference tests, broadcast-law test, and
example's fugacity-unit/melt-pressure test passed **8 tests** in total.
These verify constants, formulas, and connection conventions; they do not
validate the final concentration against experiments.

From the MCEG repository root, using the audited sibling checkouts and an
environment containing their dependencies:

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=src:../exoeos/src:../exogibbs/src:../exogibbs
export JAX_PLATFORMS=cpu JAX_ENABLE_X64=1
python -m pytest -q -p no:cacheprovider ../exoeos/tests/unittests/zhang_duan_test.py::test_published_species_factory_inserts_table_parameters
python -m pytest -q -p no:cacheprovider ../exogibbs/tests/unittests/solubility/meltyq_test.py::test_meltyq_laws_match_independent_reference_values ../exogibbs/tests/unittests/solubility/meltyq_test.py::test_laws_broadcast_array_inputs ../exogibbs/tests/unittests/examples/solubility_comparison_test.py::test_exoeos_fugacity_units_and_actual_melt_pressure
python examples/h2_solubility/run.py --output /tmp/h2-solubility-result.json
```

The runner's four checks passed: adapter agreement with a direct EOS call, EOS
pressure round-trip, and both solubility formulas using actual melt pressure.
It also computes an ideal-fugacity control at the same actual pressure. These
are numerical checks sharing upstream implementations, not independent physical
evidence. ExoEOS and ExoGibbs remain optional for this example and are not MCEG
runtime dependencies. Source tracing is an optional addition to the core schema.

## What to investigate next

1. Establish experimental H2 fugacity, composition, and redox coverage for the
   solubility formulation, and reconcile the source-specific temperature bounds.
2. Assess a current concentration calibration and an EOS supported at the
   target H2 state, including uncertainty in fugacity and dissolved concentration.
3. Specify an actual melt and compare the complete calculation with measurements.
4. Use the partial range assessment to refine source-scoped conditions and the
   [Claim/Evidence/Assessment separation](design_questions.md#claim-evidence-and-assessment-separation).
   A general evaluator or aggregate applicability score is premature.

The [design questions](design_questions.md) discuss the remaining schema gaps.
