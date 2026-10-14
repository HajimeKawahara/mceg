# Tracing evidence to original sources

MCEG can follow recorded citations back to an identified primary source and
report missing inspections or comparisons. This helps expose where a copied
number or an applicability restriction still needs checking. It does not read
papers, discover citations, compare numbers automatically, or establish that a
primary source is correct.

## Record facts at the right scope

An evidence item should describe one auditable fact or condition, with its
quantity, units, material, and relevant conditions in `summary` and `scope`.
Split records when their origins or inspection states differ. A paper can be
primary for its own calculation and secondary for the experimental data it uses.
Assign roles to the scoped evidence item, not to the whole paper.

The optional `provenance` field adds:

| Field | Meaning |
| --- | --- |
| `role` | `primary`, `secondary`, `implementation`, or `unknown`, relative to the item's scope |
| `location` | Page, table, row, equation, passage, or code location; explicitly explain an unknown location |
| `inspection` | `not_inspected`, `partial`, or `inspected`, for this scope |
| `note` | What was inspected and what remains missing |
| `derived_from` | Local evidence links, each with `evidence`, `comparison`, and `note`; defaults to empty |

Each link's `comparison` is `not_checked`, `consistent`, or `discrepancy`.
These are manually recorded comparison outcomes. `consistent` requires an
explanation covering the relevant values, units, scope, and any transformation;
equal numbers alone do not establish scope preservation. `discrepancy` retains
an observed disagreement without declaring which source is wrong. A deliberate
approximation may explain a difference and must be described in the note.

The validator requires both endpoints to declare `inspection: inspected` for
a recorded `consistent` or `discrepancy` comparison. It rejects dangling,
duplicate, and cyclic ancestry links. Missing inspections and discrepancies
are legitimate audit data, not malformed contracts.

## H2 example

The [H2 contract](../../contracts/h2_solubility.yaml) separately records:

1. `formulation_temperature`: directly inspected temperature bounds reported
   in the secondary source [Seo et al. (2024), before Eq. 6](https://arxiv.org/html/2408.17056v1#S2.SS3).
2. `experimental_temperature`: the identified original study,
   [Hirschmann et al. (2012)](https://doi.org/10.1016/j.epsl.2012.06.031).
   The basalt-specific run table has not been inspected for this fact. The
   [author-institution abstract](https://experts.umn.edu/en/publications/solubility-of-molecular-hydrogen-in-silicate-melts-and-consequenc/)
   identifies the experimental series but does not complete that inspection.

The link between them is `not_checked`. No numeric original temperature range
is invented. This trace does not establish the origin of the formula's numeric
coefficients, or adjudicate the 1723 K versus 1773 K source difference.

```bash
python -m mceg --trace formulation_temperature contracts/h2_solubility.yaml
```

The JSON output contains both nodes and their source locations, the link with
its note, and these issues:

- `comparison_not_checked`: the reported bounds have not been compared with
  the original experimental conditions.
- `source_not_fully_inspected`: the scoped primary record remains uninspected.

`primary_sources` identifies `experimental_temperature`, while
`recorded_audit_complete` is **false**. Reaching a primary citation is not
equivalent to checking it. The case's `within_reported_range` classification
continues to mean inclusion in Seo's reported interval, not validation by
original experimental data.

The subsequent [primary-source audit](h2_primary_audit.md) adds real comparisons:

| Trace target | Recorded outcome |
| --- | --- |
| `metadata_pressure` | `consistent` with the original abstract's study-wide pressure envelope; audit complete for that narrow fact. |
| `metadata_temperature` | `discrepancy` with Seo's upper bound, followed by an unchecked original source; no typo diagnosis. |
| `implementation` | `consistent` with Seo's expression and units, then `not_checked` against the original empirical fit. |
| `historical_calibration` | An inspected secondary attribution points to an uninspected earlier calibration source of unknown role. |

`infrared_recalibration` separately records primary evidence from the 2025
study's own measurements. Neither this evidence nor the completed pressure
comparison changes the physical-accuracy claim. The same paper can be primary
for a new measurement and secondary for its description of older measurements.

## Report semantics and limits

The trace follows every recorded branch. Missing provenance, unknown roles,
non-primary endpoints, incomplete inspections, unchecked comparisons, and
discrepancies prevent `recorded_audit_complete` from becoming true. Shared
ancestors are displayed once per local ID. Distinct IDs are not automatically
recognized as the same dataset; the report is not an evidence-independence score.

A true flag means only that the supplied records declare an inspected,
consistent chain to primary sources on every branch. MCEG cannot establish
whether a declaration is truthful, all dependencies were recorded, or those
sources support a physical claim. No claim or applicability status is promoted.

`--trace` emits one JSON object per valid input file. Exit code 0 means reports
were produced, even with audit gaps; 1 indicates invalid input or an unknown
evidence ID. Python callers can use `trace_provenance(contract, evidence_id)`.
Old contracts remain valid without provenance, and their trace reports
`missing_provenance` instead of assuming an original source.

The next manual task is to locate the original table, select the relevant
material and experimental runs, compare units and conditions, and record the
outcome at that scope. Full-text retrieval, automatic extraction, unit-aware
comparison, correction histories, and cross-contract source identity remain
outside this minimal implementation.
