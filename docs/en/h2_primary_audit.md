# H2 primary-source audit

The initial audit below is retained as a historical record. The
[2026-10-19 full-text update trial](#full-text-update-trial-2026-10-19) adds a
scoped review using an institutionally authorized private PDF and tests the
v0.2 update procedure. The original PDF is not distributed by this repository.

Audit date: 2026-10-15. This is a **partial audit**, not a completed check of
Hirschmann et al. (2012). It updates the [contract](../../contracts/h2_solubility.yaml)
and [manual case](../../examples/h2_solubility/case.yaml) using the existing v0.1
provenance fields. No schema extension or upstream change was needed.

## What could be checked

| Fact | Directly inspected source | Outcome |
| --- | --- | --- |
| Implemented expression and units | Pinned ExoGibbs function and [Seo (2024), Eq. 6][seo] | Consistent: fugacity in bar, pressure in GPa, output mole fraction. Original coefficient derivation remains unchecked. |
| Study-wide total pressure | [Hirschmann (2012), original abstract][original] | 0.7–3 GPa agrees with metadata. It does not establish a basalt-specific or joint domain. |
| Experimental materials | Same original abstract | Separate synthetic basalt + COH and andesite + OH series; this does not specify the example's melt. |
| Temperature metadata | Metadata versus Seo's paragraph before Eq. 6 | Upper bounds differ: 1773 versus 1723 K. Both sources were read; the cause remains unresolved. |
| Original temperature runs and empirical fit | Hirschmann full text not obtained | Uninspected; no original table values or equation locations invented. |
| New infrared calibration | [Chaudhari (2025), methods and Fig. 5][calibration] | Primary evidence for its new calibration; not validation of the retained solubility function. |

The original authors' abstract is primary for the statements it actually
contains. Reading an institution's reproduction of it does not make an unseen
table inspected. The same DOI therefore has both inspected and uninspected
evidence items, depending on the fact being audited.

## Findings and their limits

**The temperature difference may describe different materials.** The
[2025 Fig. 8 caption][comparison] describes selected older experiments mostly
at 1400 degC, with basalt runs at 1450 degC and andesite runs at 1500 degC.
These convert to 1673.15, 1723.15, and 1773.15 K. This suggests a possible
explanation of the two upper bounds. However, that caption is secondary for
the 2012 runs and covers a selected buffer subset. It cannot settle the full
basaltic domain or prove that the metadata is wrong. `temperature_crosscheck`
therefore retains a `not_checked` link to the original temperature record.

**A primary experiment can inherit a calibration.** The 2025 study measured
a new infrared coefficient of 2.12 +/- 0.05 L mol^-1 cm^-1 using haplogranitic
glasses and two calibration methods. Its account of the earlier work attributes
a coefficient of 0.26 L mol^-1 cm^-1 to Shelby (1994), used by Hirschmann (2012).
That older attribution is still secondary in this audit. The candidate earlier
source is recorded with unknown role and uninspected content, rather than
being silently treated as a verified experimental endpoint.

The new measurement is primary evidence for its stated glass and measurement.
The paper itself discusses systematic error when transferring that coefficient
to other glasses. This, together with the selected conditions in the comparison
to old data, prevents treating the new coefficient as a universal correction
for the present pure-H2 calculation. No correction or replacement law is applied.

**Formula transcription and empirical ancestry are different checks.** The
implementation matches Seo Eq. 6, but that does not establish how the original
data led to -11.403 and 0.76. The original concentration convention, units,
reference state, and any temperature approximation still need inspection.
No transcription error in Seo has been established by this audit.

## Machine-readable outcomes

From the repository root:

```bash
python -m mceg --trace metadata_pressure contracts/h2_solubility.yaml
python -m mceg --trace metadata_temperature contracts/h2_solubility.yaml
python -m mceg --trace implementation contracts/h2_solubility.yaml
python -m mceg --trace historical_calibration contracts/h2_solubility.yaml
```

| Trace | `recorded_audit_complete` | Meaning |
| --- | --- | --- |
| `metadata_pressure` | true | Numeric study-wide pressure envelope agrees with the original abstract. |
| `metadata_temperature` | false | Observed source difference plus unchecked original temperature runs. |
| `implementation` | false | Expression agrees with Seo; original empirical fit is uninspected. |
| `historical_calibration` | false | Earlier coefficient attribution has not reached a directly inspected source. |

`true` concerns only the declared source comparison. It cannot promote the
contract's `physical_accuracy` claim, which remains `unknown`. The nine case
classifications and numerical output remain unchanged: EOS extrapolation,
inclusion in reported solubility intervals, and missing evidence can coexist.

## Access record and next concrete checks

The original DOI is [10.1016/j.epsl.2012.06.031][doi]. Its abstract was read at
the authors' institution. On the audit date, publisher HTML/PDF requests returned
HTTP 403. The publisher article API returned bibliographic XML only; requesting
the full view returned an authentication error. Author and repository searches
did not yield an inspectable full text. An open-access label in discovery
metadata did not change this outcome. These are retrieval outcomes in this
environment, not evidence that no accessible copy exists elsewhere.

The specific remaining work is to obtain the original full text and:

1. Identify individual basalt/andesite runs, their temperatures, pressures,
   compositions, fugacities, and buffers. Preserve missing or excluded runs.
2. Reconstruct the fit and transformations into Seo Eq. 6, including concentration
   basis, fugacity convention, and temperature treatment.
3. Inspect the adopted infrared calibration and its earlier source, separating
   measured signals, conversion coefficients, and derived concentrations.
4. Compare the complete calculation with suitable measurements before changing
   any physical-accuracy classification or applying a numerical correction.

The EOS side of the case is unchanged; this audit does not trace the original
PVT datasets behind Zhang and Duan's comparison table. That is a separate task.

## Full-text update trial (2026-10-19)

The user supplied an authorized institutional copy of Hirschmann et al. (2012).
The [authored review](../../examples/h2_literature_update/review.json) records
the inspected locations, concise factual findings, access limitation and PDF
SHA-256. It contains no PDF, extracted article text, page images or private local
path. Supporting information and Shelby (1994) were not supplied or inspected.
Equations, plot labels and table units were checked on rendered pages as well
as extracted text; text extraction alone garbled the plotted coefficients and
the uncertainty sign.

The [replay script](../../examples/h2_literature_update/update.py) uses the
v0.2 records and evaluator, including the explicit task completions added in
package rc2. The
[saved result](../../examples/h2_literature_update/result.json) records the
actual before/after traces, assessments and completed tasks. The initial trial
identified the workflow gaps described below; the replay now exercises the
first two fixes. The original contracts, provider code, computed
concentrations and archived numerical results remain historical inputs.

### Findings from the supplied paper

Page numbers below are the printed journal pages (PDF pages 2, 3, 5 and 6
correspond to pp. 39, 40, 42 and 43).

| Finding | Inspected location | Consequence |
| --- | --- | --- |
| The basalt line is `ln K = -11.403 - 0.76 P(GPa)`; `K = X_H2/f_H2`, with fugacity in bar. | Fig. 4 label/caption, p. 43; Table 2, p. 40 | Exponentiation directly gives the expression in [Seo Eq. 6][seo] and the pinned callable. The coefficient ancestry is now located; no coefficient correction is indicated by this transcription check. |
| `X_H2` uses oxide-component mole fractions including H2O. | Table 2 footnote c; Fig. 4 caption | This resolves the original concentration convention, but does not audit the downstream conversion for an arbitrary melt. |
| The general law uses `T0 = 1400 degC`, `P0 = 100 kPa`, and enthalpy/volume terms. The temperature spread did not allow enthalpy calibration. | Section 4, Eq. 6, p. 42 | The temperature-free regression does not establish temperature independence. Do not add a second reference-pressure correction to the printed empirical line. |
| Basalt + COH: 1400-1450 degC, 0.7-3 GPa. Andesite + OH: 1400-1500 degC, 1-3 GPa. | Table 1, p. 39 | The different temperature maxima describe different materials. The metadata's 1773 K upper bound reaches andesite, while the callable uses basalt coefficients. Provider intent remains to be reviewed. |
| A882 and A950 were excluded from calibration; A949 still reaches 1500 degC. B340 H2 is reported as a non-detection. | Section 3.1, p. 42; Tables 1-2 | A listed run is not automatically a fit datum. No numeric concentration is invented for B340. |
| The authors adopted Shelby's SiO2-glass infrared calibration. | Section 2.4, p. 40 | Adoption is directly confirmed. The older coefficient's numeric value and measurement convention still require its original source. The inspected passage does not print the later paper's `0.26` value. |
| The paper discusses possibly greater than 100% uncertainty from calibration transfer, then suggests perhaps +/-50% from its SIMS/FTIR comparison. | Section 3.2 and Fig. 3, p. 42 | These are the authors' estimates, not a calibrated error model for this callable or a universal correction using the 2025 coefficient. |
| Fugacities were calculated using Zhang and Duan (2009); melt compositions are in supplementary data. | Section 2.3, p. 40; Fig. 4 caption | The calibration inherits an EOS and analytical conversions. Reading the printed line does not independently reconstruct these dependencies or validate the pure-H2 example. |

The implemented expression agrees with the original **published regression**.
Reconstructing that regression from measurements is a separate unfinished task,
requiring supplementary compositions, the fugacity calculation, selection rules
and analytical calibration. This distinction determines the scope of the
completed source trace.

### Reproduce the update

From the repository root, using the MCEG environment:

```bash
python examples/h2_literature_update/update.py \
  --output /tmp/h2-full-text.yaml > /tmp/h2-full-text-report.json
python -m mceg /tmp/h2-full-text.yaml
python -m mceg check /tmp/h2-full-text.yaml
python -m mceg explain /tmp/h2-full-text.yaml --evidence implementation_full_text
python -m mceg explain /tmp/h2-full-text.yaml --evidence metadata_temperature_full_text
python -m mceg explain /tmp/h2-full-text.yaml --evidence calibration_adoption_full_text
python -m mceg explain /tmp/h2-full-text.yaml --assessment physical_accuracy:full_text:2026-10-19
```

Use package `0.2.0rc2` or later. The output must be a new file. Replay requires
no private paper, network or provider installation; it reuses the authored
inspection. Optionally add
`--pdf /authorized/path/hirschmann_2012.pdf` to check the local copy's byte
identity. A matching hash does not repeat inspection. The artifact locator is
a content-addressed `urn:sha256:...`; the DOI locates the publication, not a
publicly hosted copy of those PDF bytes. A different legitimate PDF copy may
have a different hash and needs its own source record.

The procedure pins the baseline contract hash, adds six Evidence records and
four material-specific marginal Conditions, then adds a reviewed support
Assessment and four range Assessments for the existing 1750 K / 7500 bar
Context. Conditions and the review method identify the review-file hash.
Earlier records are retained, and v0.1 restoration remains equal. Neither the
implementation nor the physical proposition changed, so the existing Subject
and Claim revision are reused. A changed formula would instead require a new
Subject; a changed proposition would require a new Claim revision.
Two `follow_up_resolutions` record completion of the original fit and run-table
inspection tasks, linking the new Evidence and noting the remaining work.

| Trace in the new review | Prior audit complete | New audit complete |
| --- | --- | --- |
| Published fit, original run envelope, formulation, implementation | false | true, for the stated source-comparison scope |
| Temperature metadata | false | false: material-scope discrepancy remains |
| Inherited calibration | false | false: Shelby source and transfer remain unresolved |

At the recorded 1750 K and 0.75 GPa, the new Conditions give:

| Material | Temperature envelope (K) | Temperature membership | Pressure envelope (GPa) | Pressure membership |
| --- | --- | --- | --- | --- |
| Basalt + COH | 1673.15-1723.15 | outside | 0.7-3 | within |
| Andesite + OH | 1673.15-1773.15 | within | 1-3 | outside |

The materials cannot be combined to manufacture a jointly covered rectangle.
Composition and actual hydrogen fugacity are still unspecified. Physical
accuracy remains `unknown` in both the imported and the new reviewed
Assessments. The original 1700 K worked calculation is not rerun or relabeled.

`check` reports **5 passed, 3 failed, 2 unknown**, with exit code 1. The failures
are interval comparisons (including the historical Seo interval), not invalid
schema or established physical falsity. Source tracing reports 8/24 records
complete, and still includes old uninspected records. This is an expected
result of retaining history, not an attempt to make every check green.

### Select the reviewed Assessment and completed tasks

```bash
python -m mceg check /tmp/h2-full-text.yaml \
  --assessment physical_accuracy:full_text:2026-10-19
python -m mceg explain /tmp/h2-full-text.yaml \
  --assessment physical_accuracy:full_text:2026-10-19
python -m mceg explain /tmp/h2-full-text.yaml --evidence experimental_fit
```

The selected check reports **1 passed, 0 failed, 2 unknown**, with exit code 0:
structure passes, 5/7 relevant source traces are complete, and the stored
physical support remains unknown. The unresolved source branch is the inherited
calibration. The selection does not evaluate the separate range Assessments;
their results remain available in the all-records check above. Both commands
show the selected Subject/Context and follow only its Evidence dependencies.

The old `experimental_fit` view still displays its historical inspection fields,
but now shows `Completed follow-up: inspect-original-fit` and links to the new
fit/formulation evidence. It no longer asks to acquire the same paper. The
independent reconstruction, inherited calibration and provider metadata tasks
remain pending. Resolution records do not change `--trace` results or the
original Assessment statuses. This closes the reading tasks without establishing
physical validation or a general evidence replacement policy.

### Procedure gaps exposed by this trial

| Gap | Initial behavior | Implemented response or remaining work |
| --- | --- | --- |
| Evidence replacement and current-view selection | New IDs close the reviewed chain, but the old `implementation -> formulation -> experimental_fit` chain remains incomplete. Aggregate checks retain old domains and limitations stating that inspection is pending. | `check --assessment` and `explain --assessment` now select an explicit judgment and its dependencies. All-records output is labeled as including history. General evidence supersession remains deferred. |
| Follow-up completion | `explain --evidence experimental_fit` kept asking to obtain the paper, with no formal completion record. | `follow_up_resolutions` now records the task, completion Evidence and note. Completed instructions are displayed separately; new reconstruction and calibration tasks remain pending. |
| Material and joint-domain matching | Range comparison ignores material text and Context settings. An andesite temperature PASS is displayed for the basalt Subject. At 1750 K / 0.75 GPa each material misses one marginal bound. | Keep the source scopes visible. Use existing joint samples only after reviewing a complete inventory, or define an explicit material prerequisite; do not infer a rectangular validated domain. |
| Rounding and uncertainty | At 1723.15 K the original basalt bound includes the temperature while Seo's 1723 K interval excludes it. Celsius conversion is authored; the evaluator has no rounding tolerance. | Preserve both recorded precisions and state the comparison policy. The extra 0.15 K from unit conversion is not measurement precision. |
| Private-source reproducibility | CI can replay records and verify their structure without the PDF, but cannot independently confirm the reading. Generic validation does not retrieve or hash an external artifact. | Keep DOI, pages, inspected scope, access note and copy fingerprint; use an optional local identity check. Hashes are not access rights or reviewer attestations. |
| Transcription versus measurement support | The formula trace can be complete while the calibration branch is incomplete. A paper can be primary for its printed regression and depend on older calibration and EOS models. | Keep these scopes separate and follow the measurement dependencies before changing physical support or applying a correction. |

The first two fixes support routine literature upkeep using explicit assessment
selection and authored task completion. Tests cover preservation of history,
private-free replay, scoped dependency audits, pending/completed work, invalid
resolution references, material/rounding limitations, and rejection of changed
baseline bytes, an unreviewed PDF or an existing output file. They do not certify
the paper's scientific content. Supplementary-data reconstruction, the inherited
calibration audit, and provider metadata review remain distinct follow-ups.

[seo]: https://arxiv.org/html/2408.17056v1#S2.SS3
[original]: https://experts.umn.edu/en/publications/solubility-of-molecular-hydrogen-in-silicate-melts-and-consequenc/
[doi]: https://doi.org/10.1016/j.epsl.2012.06.031
[calibration]: https://link.springer.com/article/10.1007/s00410-025-02272-y#Fig5
[comparison]: https://link.springer.com/article/10.1007/s00410-025-02272-y#Fig8
