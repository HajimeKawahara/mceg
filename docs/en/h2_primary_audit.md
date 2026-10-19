# H2 primary-source audit

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

[seo]: https://arxiv.org/html/2408.17056v1#S2.SS3
[original]: https://experts.umn.edu/en/publications/solubility-of-molecular-hydrogen-in-silicate-melts-and-consequenc/
[doi]: https://doi.org/10.1016/j.epsl.2012.06.031
[calibration]: https://link.springer.com/article/10.1007/s00410-025-02272-y#Fig5
[comparison]: https://link.springer.com/article/10.1007/s00410-025-02272-y#Fig8
