# Curated gas: scoped reuse of numerical evidence

ExoGibbs [PR #284](https://github.com/HajimeKawahara/exogibbs/pull/284) adds
source audits, adoption decisions, and a continuous gas preset. This experiment
uses the merged `e21a5d0eafd19db350c84b9a75cdd29517e367e9` snapshot to exercise
the proposed Claim/Evidence/Assessment separation. Its evaluator is shared with
the optional `mceg check` command; v0.1 contracts keep their existing fields and
meanings.

The provider owns its contract, implementation and numerical archives.
[`review.json`](../../examples/curated_gas/review.json) pins the inspected
contract and receipt, identifies the composition, and states the review's
rationale. It explicitly reviews one declaration: `equilibrium_verification`.
It is not a general rule that any passed test supports any linked Claim.

## Three distinct questions

| Question | Recorded answer |
| --- | --- |
| Is the temperature in the continuous numerical evaluation interval? | `range_membership` against the reviewed 1500--4000 K bounds |
| Is this temperature, pressure and network in the archived test grid? | `sample_membership` against seven temperatures, five pressures and two networks |
| Can the reviewed declaration be reused for this implementation and context? | A separate `evidence_support` Assessment, bound to the contract, selected input hashes and supplied context |

At 1735 K and 0.01 bar, the saved ion-inclusive context is a recorded sample.
With unchanged selected files, the normalized Asplund 2021 nuclear budget and
the recorded Python/JAX/backend/dtype/tolerance, the review is reusable.
At 1750 K the temperature remains inside the evaluation interval, but it is not
a sampled point: support for that context is `unknown`. Interpolation accuracy
and the rectangle between pressure samples are not inferred. A different or
missing composition, environment or tolerance also leaves support unknown.

The imported v0.1 declaration retains its original text, status and evidence
links, explicitly labeled `imported_v0.1_declaration`. Its numerical Evidence
retains the historical `passed` result. If an implementation or output file
changes or disappears, the current-context Assessment becomes `unknown`; the
old declaration and execution outcome are not rewritten. The report includes
expected and observed hashes so a changed implementation has a distinct target.

Changing the contract or receipt itself stops reassessment until its scope has
been reviewed and the corresponding pin updated. Repinning alone does not
turn an unexecuted FastChem comparison into support. Hash consistency is limited
to the receipt's selected files; it is not a complete dependency audit.

## Replay without provider imports

For terminal inspection, use the [check command](checks.md) from the ExoGibbs
checkout: `mceg check -k curated`, or add `--temperature 1750` to compare a
different requested temperature. The installed package bundles the reviewed pins
and archived example context, so this does not require an MCEG source checkout.

From an MCEG checkout with its normal dependencies installed:

```bash
PYTHONPATH=src python examples/curated_gas/assess.py \
  --exogibbs /path/to/exogibbs \
  --context examples/curated_gas/context.json \
  --output /tmp/curated-assessment.json
```

The context uses kelvin and bar and describes the requested target environment;
the script does not inspect the installed numerical environment or execute a
solver. Omitted context fields lead to unknown support. Invalid quantities,
unsupported fields and paths outside the checkout are errors.
[`assessment.json`](../../examples/curated_gas/assessment.json) is an actual
file-check replay against the merged provider snapshot, not a new numerical run.
Tests use explicitly synthetic fixtures and require neither ExoGibbs nor JAX.
The replay script and CLI use the same internal evaluator in
[`mceg._curated`](../../src/mceg/_curated.py). The saved assessment was replayed
after extraction to record that evaluator's hash; historical numerical evidence
and all assessment outcomes are unchanged.

## Consequences for v0.2

- Preserve imported declarations as historical assessments, with their original
  target identities. A new context needs a separately identified assessment.
- Give every support assessment a method, evidence references, context, target
  identity and reasons. A hash match is a necessary bookkeeping check for this
  reviewed reuse policy, not sufficient scientific evidence by itself.
- Keep continuous evaluation conditions, discrete test coverage and scientific
  applicability separate. Physical validation stays `unknown` in this example.
- Keep `prefer`, `prefer_conditionally` and `retain_provisionally` as source
  adoption decisions. They do not map directly to supported/unknown, and
  `inherited_unreviewed` does not mean a source is false or unusable.
- Treat cross-contract source paths as locators. Automatic propagation of
  support or limitations across source-adoption contracts remains unimplemented.

Before moving these ideas into the core, define version dispatch and migration
fixtures that preserve old declarations and allow different assessments for
different revisions and contexts. This example deliberately handles one
reviewed numerical claim; it does not define a general inference policy.
The imported Claim text still contains its old evaluative wording. Rewriting
it as an outcome-independent proposition needs an explicit Claim revision;
extracting its status must not silently change what was asserted.

The [lifecycle follow-up](assessment_lifecycle.md) now exercises migration,
fresh execution, and a single reviewed source-adoption dependency. Its numerical
runs supplement the historical receipt; this original reuse experiment remains
available with its original context and meaning.
