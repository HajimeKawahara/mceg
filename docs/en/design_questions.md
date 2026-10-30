# Design questions for experimental v0.1

MCEG v0.1 tests whether existing scientific models can be described honestly
with a small contract. It is not a final standard or a scientific approval.
The initial examples are the residual Helmholtz models `IdealEOS`,
`SecondVirialEOS`, and `PengRobinsonEOS` in ExoEOS. `IdealEOS` supplies zero
residual energy; the separate caloric `IdealGas` supplies additional ideal
thermodynamics. A residual EOS alone does not specify total heat capacities,
absolute enthalpy, or entropy. These capabilities must not be conflated.

## Design principles

- An LLM without the previous conversation must be able to follow recorded evidence and resume an investigation.
- Humans must also be able to inspect the evidence and model contracts, including what remains unknown. The optional [MCEG Viewer](../../viewer/README.md) makes these records navigable without adding a viewer dependency to the core.
- Keep MCEG independent of provider packages; add no dependencies to ExoEOS or ExoGibbs.
- Separate scientific applicability from conditions for numerical evaluation.
- Separate numerical verification from validation against experiments or observations.
- Attach evidence and its scope to claims; do not invent bounds, results, or citations.
- State missing knowledge as `unknown`, with an explanation of what is missing.
- Prefer the smallest useful structure. Defer databases, inference engines, and provider execution in the core.
- Treat v0.1 as an experiment that can change when real descriptions expose shortcomings.

## What is straightforward, and what is difficult?

Source symbols, revisions, formulas, input conventions, test identifiers, and
explicit implementation restrictions can be recorded directly. The three
examples share a residual free-energy interface, so this requires little
abstraction. Claim-to-evidence identifiers already give a useful audit trail.

Scientific applicability is harder: a formula or a converged calculation does
not provide a calibrated error bound. Test points do not establish every point
between them, and a class with arbitrary coefficients has no universal range
of accuracy for real substances. Missing higher virial coefficients cannot be
turned into a numerical truncation threshold without additional evidence.

## What the frozen v0.1 statuses mean

The v0.1 executable schema is [schema.py](../../src/mceg/schema.py). Domains have
kind `scientific_applicability` or `numerical_evaluation`, and status
`documented` or `unknown`. `documented` means conditions were recorded with
evidence; it does not mean that every condition is checked by the provider or
that experiments established the domain. An `unknown` domain has no asserted
conditions and explains the missing information in its description.

Claims distinguish `theoretical`, `numerical_verification`, and
`physical_validation`, with status `supported` or `unknown`. The validator
requires matching evidence categories for a supported claim: theory, a passed
numerical test or benchmark, or experiment/observation, respectively. This is
a consistency check on declarations. It does not prove that the evidence
actually entails the claim, covers its scope, or is independent.

Numerical evidence records `passed`, `failed`, `not_run`, or `unknown`.
`not_run` describes a known test with no execution result supplied in that record;
`unknown` means the result is not established. Test source is not a passing
result. `unknown` is not a synonym for false, safe, or inapplicable. The current
claim statuses cannot express conflicting evidence or partial support precisely.

## Claim, Evidence, and Assessment separation

The [H2 range experiment](h2_solubility.md#partial-automatic-range-assessment)
tested a small step toward separating assertions from their assessment. The
[v0.2 candidate](v02.md) now implements the common records and migration described
below; v0.1 fields and meanings remain frozen. The original example and its
source-specific conditions remain available as historical artifacts.

| Concept | Responsibility | H2 example |
| --- | --- | --- |
| Claim | State the proposition, subject, assumptions and scope | Implementation reproduces specified formula values within the declared numerical tolerance |
| Evidence | Record the inspected source or observation, including execution outcome and scope | A saved test execution against a particular implementation revision |
| Assessment | Record a judgment with its target, evidence, method, context and rationale | That execution supports the numerical Claim for the tested revision and points |

An Evidence `result: passed` is a historical execution outcome. Whether that run
supports a Claim about a different implementation or context is a separate
Assessment. Updating an assessment must not rewrite the earlier outcome.
Claim statements should describe propositions rather than contain their current
evaluation, such as "passed" or "accuracy is unknown".

Two assessment kinds have different targets and result vocabularies:

- `evidence_support` targets a Claim and relates supporting evidence to that
  Claim's scope. The proposed initial outcomes are `supported` and `unknown`.
  Source relevance and coverage still require review; merely finding a passed
  test or an experimental citation cannot establish support. `unknown` is not
  a rejection or a declaration of contradictory evidence.
- `range_membership` targets a recorded Condition and uses a supplied Context.
  The example computes `within_reported_range`, `outside_reported_range`, or
  `unknown` for missing input. Invalid or unsupported inputs raise errors.
  It never promotes an `evidence_support` assessment.

Conditions hold quantities, units, endpoints, boundary rules, marginal coverage,
source references and scope. They remain distinct from the claim that a model
is physically accurate over a joint domain. At 1750 K the metadata and Seo
conditions give different outcomes; both are retained. Their difference alone
does not establish contradictory experimental evidence, since their material
scopes may differ. Composition matching remains unevaluated even when the
temperature lies inside a basalt-specific reported interval.

The prototype records context, rule and evaluator identities, the contract hash,
its implementation revision, and individual reasons. It requires a condition
review if the contract changes. These identities make a result reproducible;
they do not prove that the chosen interval was transcribed or scoped correctly.
There is no aggregate applicability flag or automatic preferred-source policy.

### Migration requirements implemented in v0.2

1. Keep the v0.1 contract and its hash as the original record. The v0.2 reader
   dispatches on the version explicitly; v0.1 readers continue to reject new
   fields. The core CLI implements this; old example scripts remain unchanged.
2. Move each Claim's `status` and evaluative `evidence` links into a separate
   `evidence_support` Assessment targeting the Claim's identified version and
   scope. Mark it as an imported v0.1 declaration, with its original contract
   and implementation identity, rather than a new assessment at current inputs.
3. Keep Evidence IDs, scopes, provenance and historical execution outcomes.
   Retain inspection and source-comparison records with their existing meaning;
   this experiment does not redesign that provenance model.
4. Review Claim text that already embeds an outcome. For H2, the formula-test
   statement and the `physical_accuracy` statement need this review. Changing
   a proposition requires an explicit revision; do not silently turn an
   "unknown accuracy" statement into a quantitative accuracy claim. Missing
   measurement criteria and tolerances remain missing until supplied.
5. Keep range assessments linked to Conditions and Contexts, separately from
   Claim support. Preserve multiple assessments and their methods. Any displayed
   summary status must identify the selected assessment; it must not become a
   second independently editable status on Claim.

The core migration has fixtures demonstrating preservation of historical
declarations, coexistence of assessments for different revisions, and continued
v0.1 compatibility. Conflict resolution, quantitative confidence, uncertain
inputs, joint regions and general unit algebra are deferred until concrete
models require them. The interval prototype covers only the H2 checks. The
separate [lifecycle trial](assessment_lifecycle.md) now tests lossless declaration
extraction on H2 and curated gas, an explicit curated Claim revision, and
coexisting assessments for two freshly executed numerical environments.

## Open questions exposed by the examples

The [curated-gas assessment experiment](curated_assessment.md) exercises these
requirements on ExoGibbs's merged source-adoption and numerical-verification
workflow. It preserves an imported v0.1 declaration and historical execution
outcome while assessing reuse against observed input/output hashes and a supplied
context. A changed implementation, untested grid point, different composition,
or different numerical environment leaves current-context support unknown.
Continuous evaluation bounds and discrete sampled coverage have separate
assessments. Source-adoption preferences remain separate decisions. This is an
example-specific reviewed policy, not a v0.2 reader or generic support inference.

The two experiments now supply concrete migration requirements: preserve
historical outcomes, identify the target implementation and context, keep
range/sample membership separate from support, and require explicit review when
the contract or recorded run changes. The core now accepts v0.1 and v0.2
explicitly, while these scientific review questions remain open.

1. **What identifies a model?** A class, coefficient set, component ordering,
   mixing rule, root selector, and software revision can each change its
   meaning. v0.1 identifies an implementation but has no typed parameter-set
   identity or inheritance between general models and configured instances.
2. **How should domains become executable?** `conditions` are descriptive
   strings, not predicates. Second Virial's positive discriminant and low-density
   approximation have different meanings. PR root availability, root smoothness,
   and empirical accuracy also differ. A future predicate language needs units,
   compositions, conditional regions, strict boundaries, and unknown outcomes.
   v0.1 neither evaluates a scenario nor automatically labels extrapolation.
3. **How should units and conventions compose?** ExoEOS uses Pa and molar density;
   the ExoGibbs adapter receives pressure in bar and returns natural logarithms
   of dimensionless coefficients.
   Correct dimensions alone do not distinguish mass/molar bases, logarithm bases,
   residual/total energies, or reference pressures. v0.1 records these in prose
   and does not convert or compare them automatically.
4. **How should species and standard states match?** Ordered arrays do not prove
   that each coefficient belongs to the declared substance. Solution activity
   coefficients also require a compatible standard chemical potential; an
   activity convention label alone is insufficient. A consistent change can
   require compensating changes to both standard potentials and activities.
5. **What does evidence cover?** Analytic identities hold under their assumptions;
   synthetic fixtures and finite grids verify specified numerical cases. A
   comparison with another implementation is not a measurement. A literature
   citation may explain a model without establishing the accuracy of the local
   implementation or a new parameter set. Experimental/observational support
   needs the actual data, conditions, and discrepancy criteria. These are not
   inferred from a citation or a `passed` result.
6. **How can results stay reproducible?** Revision-pinned sources help, but dtype,
   backend, dependencies, test selection, parameters, and execution receipts can
   matter. v0.1 has source and scope strings rather than a structured execution
   record or artifact hashes. The validator does not execute tests, retrieve
   sources, verify their existence, or certify that recorded results are current.
7. **How should failures and uncertainty propagate?** A selected liquid/vapor root
   is not a proof of global phase stability. Small residuals and successful
   differentiation do not quantify physical error. v0.1 lacks uncertainty
   propagation, evidence independence, conflicting-claim resolution, and
   automatic compatibility checks across contracts. Missing evidence should
   remain visible instead of becoming an implied guarantee.

## Connection examples beyond the initial three contracts

The first connection is now implemented as a separate
[H2 solubility case](h2_solubility.md), using the pure adapter described below.
Its manual assessment format is exploratory and does not extend the core schema.

[The pure-component ExoGibbs adapter][adapter] used in this case
converts bar to Pa, preserves species order, and requires an explicit policy
for missing species. Its mock-provider tests verify interface behavior, not
physical accuracy. The gallery uses zero standard chemical potentials, so
its demonstration pressures are not an applicability range for abundances.

[The M2 mixture provider integration][mixture] supplies the second connection. It uses
Second Virial pair coefficients with explicit extrapolation or `hold_2000`
policies and zero coefficients for unmodelled pairs. Zero-pair trace species
still receive the full-mixture correction, rather than an independent ideal
species correction. Its iteration tolerance is not a measured uncertainty.
Thus the pure-component public adapter's restriction must not be generalized
to all ExoGibbs examples. The [provider trials](provider_trials.md) now describe
this connection with two contracts and a fixed-composition replay; the complete
parcel solver and planetary calculation remain outside the trial.

Further configured calculations should record parameter provenance and evidence
gaps before motivating a general rule engine. [The residual API
documentation][residual] and [the standard-state mapping][standards] provide
concrete cases for evaluating such a design.

[residual]: https://github.com/HajimeKawahara/exoeos/blob/d7681db4393fd85904846b083013230d81d45d4e/README.md#residual-helmholtz-api
[adapter]: https://github.com/HajimeKawahara/exogibbs/blob/6b4cef45d2a6f1eb1462afd6cb6d3f1c77dba8ea/src/exogibbs/interop/exoeos.py
[mixture]: https://github.com/HajimeKawahara/exogibbs/blob/6b4cef45d2a6f1eb1462afd6cb6d3f1c77dba8ea/examples/metal_silicate/m2_gas_eos.md
[standards]: https://github.com/HajimeKawahara/exogibbs/blob/6b4cef45d2a6f1eb1462afd6cb6d3f1c77dba8ea/documents/metal_silicate_reference.rst

## Questions exposed by the H2 connection

The fixed 1700 K, 7500 bar calculation produced finite numerical outputs while
its EOS input exceeded the reported pure-H2 PVT comparison envelope. The
solubility temperature and total pressure fell inside recorded intervals, but
the actual melt composition and experimental fugacity coverage remained unknown.
The [manual case](../../examples/h2_solubility/case.yaml) makes those separate
judgments visible without assigning one overall applicability flag.

- **What does a bound describe?** The EOS bounds describe volume-comparison
  evidence, not a measured fugacity error. Two one-dimensional projections do
  not define a complete joint domain. A future representation needs the
  observable, evidence basis, source, and kind of coverage attached to each bound.
- **Which source defines the scope?** ExoGibbs metadata records 1673–1773 K;
  the basaltic formulation source reports 1673–1723 K. Both contain this case,
  so the discrepancy does not change its temperature classification. It still
  prevents silently replacing source-specific domains with one authoritative range.
- **How can omitted arguments constrain use?** The solubility callable accepts
  fugacity and total pressure only. Temperature and basaltic melt composition
  remain relevant scientific conditions. An API signature cannot fully specify
  a scientific contract, and an unspecified composition is not a matching one.
- **How should revised evidence be represented?** The 2025 recalibration raises
  a problem for the retained older concentration scale. The present claim
  statuses cannot encode a scoped challenge or supersession. It also does not
  justify dividing this calculation by ten without further evidence.
- **Where should calculations live?** Each model fits the existing contract.
  The connection, exact inputs, manual classifications, and execution receipt
  need another object. This example keeps them in separate YAML/JSON files,
  linked by references and hashes, rather than designing a general workflow graph.

The next useful refinement is a small source-scoped bound record and explicit
unknown inputs. Automatic inference and global compatibility decisions should
wait until more manually reviewed calculations establish the required semantics.

## Returning to original sources

The optional [provenance records](provenance.md) now identify a scoped original
source, its inspection state, and manual comparisons along the citation chain.
The H2 temperature example distinguishes an inspected secondary statement from
an uninspected original experimental table. Structural checks and a trace report
expose that gap without declaring the secondary statement correct or incorrect.

Remaining questions include how to record transformations or intentional
approximations, compare units and material-specific domains, and invalidate old
comparisons after a source or its interpretation changes. Inspection is relative
to the recorded scope, not the whole paper. An abstract read does not imply a
table read, and source agreement is not physical validation. Primary sources can
also contain errors or depend on a subsequently revised calibration.

Shared local ancestors are traceable, but different identifiers for the same
experiment are not resolved. Citation counts cannot serve as independent evidence
counts. Full-text acquisition and reliable extraction remain separate work;
merely adding a DOI does not complete an audit. Existing scope strings still
carry most of these scientific distinctions, rather than executable rules.

## Lessons from attempting the primary-source audit

The [H2 audit](h2_primary_audit.md) reached the original abstract but could not
obtain the original run tables or fit. It also inspected the later calibration
study. Existing fields were sufficient to record the partial result without
changing a physical claim. Four limitations became concrete:

- **Source access is not source inspection.** A valid DOI, a successful metadata
  download, and an open-access discovery label do not establish that the relevant
  content was read. v0.1 records retrieval failures in notes; access receipts and
  content-version identity have no dedicated structure.
- **A comparison needs a precisely limited subject.** Equal study-wide pressure
  endpoints do not preserve material-specific applicability. Different temperature
  endpoints may reflect different experimental subsets rather than copying errors.
  Numeric agreement, scope agreement, and an explanation of a difference currently
  share one comparison status plus prose; they are not independently executable.
- **Primary is a role, not the end of all dependencies.** A concentration measurement
  may depend on an inherited infrared coefficient. The newer calibration is itself
  measured in one glass and transferred to others. `derived_from` cannot distinguish
  citation, calibration, unit conversion, fitting, and material transfer except in
  its note. Signals, calibration coefficients, and derived concentrations should
  eventually be distinguishable without an unlimited graph of every instrument.
- **Inspection does not reproduce a result.** Reading the new reported regression
  does not refit it, and reading a reanalysis does not independently verify the older
  data it reuses. A scoped record can be fully inspected while those separate tasks
  remain undone. The trace's completion flag must retain this limited meaning.

No confirmed transcription error or corrected empirical coefficient resulted
from this attempt. An unresolved source difference and an incomplete audit are
useful outcomes in their own right and must survive into the machine-readable data.

## Lessons from the provider adoption trials

The [three trials](provider_trials.md) use the frozen v0.1 schema unchanged.
They expose operational gaps rather than a need for immediate schema expansion:

- **Configured-model identity includes policy.** The same class and revision
  yield different coefficients under `extrapolate` and `hold_2000`. Species order,
  parameters, standard potentials and full-mixture normalization also matter.
  v0.1 can describe them in scoped prose and case files but has no typed identity
  for a configured model or compatibility rule between two instances.
- **A numerical policy does not extend evidence coverage.** Holding a 2000 K
  coefficient while evaluating gas at 2173.15 K is still use beyond the source's
  reported temperature coverage. The small difference from analytic continuation
  is not an uncertainty bound. Unknown pair interactions set to zero remain
  assumptions; the resulting trace-species correction is still `-ln(Z)`.
- **A source string has several possible meanings.** Actual contracts mix
  revision-pinned URLs, repository-relative paths, fragments and free-text
  bibliography. Copying YAML alone can break references while validation passes.
  The trial's explicit repository root and limited file-prefix resolver suffice
  for this layout; a general typed locator and immutable artifact convention
  remain undecided. Existing files are not proof of inspected content.
- **Freshness is separate from a historical result.** A revision-only edit can
  retain stale `supported` claims and still pass the core validator. The synthetic
  trial preserves the old `passed`, records current tests as `not_run`, and marks
  current numerical support `unknown`. Algebraic support survives only after
  manual review, and source-formula agreement changes to a scoped discrepancy.
  No automatic dependency or affected-claim analysis is implemented.
- **Implementation and contract revisions are different.** A contract may describe
  code from commit A while being published in commit B. Requiring its own future
  commit hash creates a circular requirement. A whole-repository HEAD change can
  also be a documentation-only edit; file changes and scientific impact are not
  equivalent. v0.1 leaves that review to authors rather than inventing a universal
  staleness status or automatically transferring old evidence.
- **Evidence ownership is not independence.** Two contracts can point to the same
  execution receipt. Moving a provider's ledger or copying its primary-source
  inspection notes does not constitute a new independent run or source inspection.
  The mixture ledger remains secondary evidence in this trial. Cross-contract
  evidence identity and deduplication remain unresolved.

The [provider-owned H2 pilot](provider_pilot.md) now uses the existing schema with
an explicit repository root, saved audit records and a manual update procedure.
Its replay succeeds after contract-publication commits change both HEADs while
selected audited files remain unchanged. ExoGibbs also had a real intervening
adapter update; source review and fresh scoped tests preceded adoption.
General graph storage, automatic scientific decisions and a new schema version
were not needed to test this workflow.

## Investigations by human and LLM reviewers

MCEG should help a reviewer resume a scientific investigation, identify the next
useful comparison, and connect its result to a model decision. Humans and LLMs
are both consumers of that interface. A useful outcome can be a justified model
change or an explicit unresolved question, even when an offline check continues
to report `UNKNOWN`. Design success therefore includes the quality of the
investigation that the records enable.

### Concrete case: the ExoEOS oxygen coefficient

The 2026-10-29 review led to the provisional change proposed in
[ExoEOS PR #92](https://github.com/HajimeKawahara/exoeos/pull/92).
Its [decision record](https://github.com/HajimeKawahara/exoeos/blob/9ed2c72c58ad45003fce11141a32ce9b9ecbeaba/results/mceg/20261029_badro_default/decision.json)
connects the inspected Badro supplement and pinned Young code to the choice of
`epsilon_OO=-1873/T`. The distinct `ln_gamma0_O=4.29-16500/T` term is retained.
The printed/code difference, missing source inspection, implementation choice
and future author clarification were separable review tasks.

This case has several simultaneous outcomes: the coefficient choice is made
provisionally, the printed equation still differs, author confirmation is absent,
and empirical accuracy remains unknown. A later reviewer should recover that
state without repeating the completed coefficient review or treating an optional
author reply as a prerequisite for the provisional choice. Provider-side file
checks also detected changes to the old evidence snapshot; the PR records exact
reviewed transitions and a separate numerical receipt while retaining history.
Source interpretation and adoption were review judgments, not automatic MCEG
inferences.

### Use the existing records as durable investigation context

Store the conclusions and their support so that another reviewer can continue
without the original conversation. The current format already supplies most
of the necessary pieces:

| Investigation need | Existing record and authoring practice |
| --- | --- |
| State the question and when it is answered | A targeted FollowUp with required material and a concrete completion criterion |
| Locate and compare the evidence | Evidence scope, exact source location, inspection state, artifact identity and `derived_from` comparisons |
| Separate observations, interpretation and adoption | Inspection/comparison Evidence, scoped Assessment reasons, and a linked provider decision artifact recording alternatives and the selected implementation |
| Resume completed and pending work | FollowUpResolution links to the actual completion evidence; separate FollowUps for remaining questions |
| Reconsider a provisional choice | An explicit future trigger and required evidence, such as an attributable reply or correction |
| Identify what must be checked after a change | Subject file pins, inventory bindings, affected Assessments and fresh provider receipts |

A decision artifact should explain which uncertainty matters to the choice,
which findings support it, what remains unknown and what would change the
decision. It is a small provider-owned record, as in the ExoEOS example; this
proposal adds no generic Decision schema. Scope a FollowUp to the actual decision
so that its completion does not require resolving every physical-validation gap.
Keep new hypotheses distinguishable from inspected source statements and reviewed
support. Preserve dated access outcomes so a failed retrieval can be resumed
without presenting that old outcome as current availability.

### First implementation candidate: improve the selected `explain` view

`explain --json` already returns authored FollowUps, resolved work, generated
suggestions, comparisons and navigation commands. The next small increment to
evaluate is a compact investigation view assembled from those existing records,
starting from a selected Claim, Evidence or Assessment. This is proposed work,
not an existing additional CLI mode.

The selected view should bring together the question, Subject/Context, relevant
source excerpts or locators, comparison outcomes, completion records, decision
artifact links and remaining tasks. Include relevant agreeing evidence as well
as gaps. Distinguish authored tasks from generated suggestions, and preserve
record IDs and source locations so every summary can be checked. If a decision
has not been recorded, say so; do not infer the preferred coefficient from the
number of agreeing citations or from publication order.

Present completed work and its outcome before suggesting that the same question
be investigated again. Keep an unresolved discrepancy visible, with a link to
the recorded adoption decision and any separately scoped remaining question.
An unresolved author-intent claim does not itself reopen a completed provisional
selection. Any blocker or priority label must come from an explicit scoped
review instruction; it cannot be inferred from `UNKNOWN` alone. A compact view
must state its selection boundary and leave the complete records accessible.

Pilot this with existing JSON output and provider authoring conventions before
adding fields or flags. The core continues to assemble records and check explicit
relationships. The surrounding reviewer obtains sources, interprets them,
proposes changes and executes provider tests, then records the resulting evidence
and judgments. This workflow requires no LLM dependency or provider execution in
the core.

### Subsequent candidate: show the declared impact of a change

Within one provider, an initial impact report could follow a changed selected
file to its Subjects and Assessments and use inventory bindings to locate the
models requiring review. Report a candidate review set, with the exact links used.
File overlap does not establish a scientific dependency, and the declared graph
does not cover unregistered callers. In the oxygen example, review must include
the dry model, ideal-H wrapper and corresponding standard-state shifts; the
coefficient and standard convention must describe the same selected model.

Cross-provider connections can later record the consumed quantity, units,
composition basis, standard-state conversion, implementation selection and
supporting evidence. Those links would help a reviewer examine ExoEOS-to-ExoGibbs
or ExoInventory use. They require their own reviewed scope; source agreement
within ExoEOS does not establish a downstream connection's validity. Start with
the actual affected connection before introducing general compatibility rules.

### Evaluate investigation outcomes

Use frozen records from the oxygen review and the existing evidence-reuse trial
as small evaluation cases. A reviewer starting a new session should be able to:

- Locate the disputed term and distinguish it from the separate infinite-dilution term.
- Recover both the evidence for a choice and its remaining limitations.
- Resume the next unfinished task without repeating a completed source comparison.
- Explain which new evidence would confirm or revise a provisional decision.
- Recognize changed implementation pins and obtain scoped replacement evidence
  while preserving the original outcomes.

Measure source-location accuracy, unsupported assertions, missed discrepancies
and repeated completed work, alongside commands or tokens needed to answer the
question. Faster summaries are useful only when scope and uncertainty survive.
Implement the selected-view improvement first if these cases show a navigation
or handoff gap; broaden the schema only when a concrete record cannot express
the required distinction.
