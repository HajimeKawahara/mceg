# MCEG: Model Contracts and Evidence Graphs

**Model Contracts and Evidence Graphs (MCEG)** is a framework for making the claims, assumptions, applicability domains, and supporting evidence of computational scientific models explicit, traceable, and auditable by both humans and AI systems.

By systematically representing what a scientific model claims, under which conditions those claims hold, and what evidence supports them, MCEG facilitates scientifically informed decisions throughout model development, validation, and use.

Rather than automatically guaranteeing the correctness of scientific models, MCEG provides a transparent foundation for humans and AI systems to continuously examine their scientific validity, limitations, and supporting evidence.

Human and LLM reviewers also use these records to resume investigations, compare
sources and justify model changes. The [investigation design](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/design_questions.md#investigations-by-human-and-llm-reviewers)
describes this workflow and the proposed next improvements.

Two design commitments guide that workflow: an LLM without the previous
conversation must be able to follow the evidence and resume an investigation;
humans must also be able to inspect the evidence and model contracts themselves.
[MCEG Viewer](https://github.com/HajimeKawahara/mceg/blob/main/viewer/README.md) provides a small bilingual interface for that
inspection. It consumes exported Graph JSON; MCEG itself does not depend on it.

## Main record types

A **Contract** groups records describing a model, its evidence and the judgments
made about it. These are the main **record types** in schemas 0.2–0.5. Each type
has its own role; there is no single status shared by all records.

| Record type | What it records | Kinds, states and interpretation |
| --- | --- | --- |
| Model | Which model is described and its declared implementation | Identifies the model; has no overall scientific support status. |
| Claim | A proposition, its scope and revision | `kind`: `theoretical`, `numerical_verification`, or `physical_validation`. Its support is recorded in an Assessment. |
| Evidence | What was inspected or measured, with sources and provenance | Numerical tests and benchmarks have `result`: `passed`, `failed`, `not_run`, or `unknown`. Other evidence kinds have no numerical result. Source inspection is recorded separately. |
| **Assessment** | A judgment about a Claim or Condition for one Subject and Context | For `kind: evidence_support`, `status` is **`supported`** (supporting evidence), **`contradicted`** (reviewed contrary evidence), or **`unknown`** (insufficient or inconclusive evidence). Range/sample membership uses separate classifications below. |
| Decision | Which alternative was chosen, why, and when to reconsider it | `selected` identifies an authored option; there is no scientific support status. A choice can be provisional even when support is unknown. |
| Equation | A mathematical definition, symbols, units and assumptions | Has an explicit revision; defining an equation does not establish implementation correctness or physical accuracy. |
| QuantityDefinition | The meaning, unit, domain and coordinates of a mathematical quantity | Has an explicit revision; distinct from a Context's numeric value. Equal symbols or units do not imply identity. |
| MathematicalModel | Adopted relations connected through explicitly shared quantities | Has an explicit revision; records nested relation instances and model-specific quantity roles. Has no scientific support status or inferred execution order. |
| EquationBinding | The declared correspondence between an Equation and code in a Subject | Maps a function, arguments and result to mathematical symbols; has no verified/unverified status. |
| Subject | The implementation or data snapshot being evaluated | Records implementation identity and optional file hashes; matching bytes do not establish scientific support. |
| Context | The conditions and settings of an evaluation | Records quantities and settings such as temperature or software versions; has no applicability status. |
| Condition | A reported range or a set of joint samples | `kind`: `range` or `samples`. Membership for a particular Context is recorded in an Assessment. |
| Domain | The model's declared applicability or numerical evaluation domain | `status`: `documented` or `unknown`. Documented conditions do not by themselves establish physical validity. |
| FollowUp | What to investigate next, required material and completion criteria | Has no status field. It remains open until an explicit FollowUpResolution records its completion. |
| FollowUpResolution | Evidence and a note recording completion of a FollowUp | Records that the task was completed; does not change a Claim's support or erase a contradiction. |

Assessment has three distinct kinds. Their outcomes answer different questions:

| Assessment kind | Question | Outcome field and values |
| --- | --- | --- |
| `evidence_support` | Does the evidence support this Claim revision for this Subject and Context? | `status`: `supported`, `contradicted`, `unknown` |
| `range_membership` | Is the Context's quantity inside the recorded range? | `classification`: `within_reported_range`, `outside_reported_range`, `unknown` |
| `sample_membership` | Does the Context match a recorded joint sample? | `classification`: `at_recorded_sample`, `not_sampled`, `unknown` |

For example, a valid comparison exceeding a Claim's error threshold can justify
`contradicted`. A crashed calculation supplies no valid comparison and does not
establish a contradiction. Range inclusion or a completed FollowUp does not
establish scientific support either. Keep the earlier Assessment when a repair
changes the Subject, then add a new scoped judgment.

These tables describe the development reader: Equation/EquationBinding require
schema 0.3 or later, Decision requires 0.4, and QuantityDefinition/MathematicalModel
require 0.5. Older readers reject the new
`contradicted` value. Frozen v0.1 Claims retain their original status fields.
See [scoped assessments](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/v02.md),
[source provenance](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/provenance.md),
[decisions](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/decisions.md) and
[compatibility](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/versioning.md)
for the detailed rules.

Known limitations need a response as development proceeds. For example, a
prescribed radiation field can be documented as an assumption while its effect
on a spectrum remains unknown. Give that question its own scoped Claim and
Assessment, then link an Assessment-targeted FollowUp or a provisional Decision.
`mceg check` reports missing handling; providers can explicitly require it:

```bash
mceg check contract.yaml --assessment radiation_review --require-handling
mceg explain contract.yaml --assessment radiation_review --investigation
```

This checks whether a response is recorded, not whether the approximation is
accurate. Scientific support remains `unknown` or `contradicted` until separately
reviewed. See [handling known gaps](docs/en/checks.md#handling-known-gaps) for the
scope and Decision requirements. MCEG does not extract new Claims from prose
assumptions automatically, and no new record type is needed.

**Handling a gap does not make a model ready for its intended use.** A separate
use manifest selects required Assessments for the actual entry point, Subject
and Context. `mceg readiness mceg/uses/physical-spectrum.yaml --root .` requires
all selected requirements to pass, including current record and file pins.
An `unknown` radiation-feedback Assessment with an open FollowUp still means
`NOT_READY`; a supported test of an unrelated solver cannot validate the spectrum
path. An explicitly scoped Decision can permit a declared exploratory use while
preserving the unknown scientific status.

| Use-manifest field | Meaning |
| --- | --- |
| `target` | Contract, actual entry point, Subject and Context; all required Assessments must match this scope. |
| `requirements` | Pinned Assessments labeled `implementation` or `physical_support`; every requirement must be met. |
| `mode` | `scientific` requires supported Assessments; `exploration` can explicitly select a scoped Decision per physical-support requirement. |
| Report `outcome` | `requirements_met`, `exploration_permitted`, or `not_ready`; no stored Assessment is changed. |

This manifest is a provider-owned selection policy, **not a new Contract record
type** or a proof that the required physics is complete. Entry-point inspection
is static; evidence must establish actual model coupling. See
[readiness for a declared use](docs/en/readiness.md).

## Start with the package you use

After [installing MCEG](#install), start by inspecting your scientific package:

```bash
mceg explain --package exogibbs
```

This shows all models and evidence records indexed by the installed package,
including documented differences, limitations and open questions. You do not
need to know a model ID or suspect a particular molecule first.

Once you find a topic to investigate, narrow the report:

```bash
mceg explain --package exogibbs --species HCN
```

From a provider checkout, gather a selected record's related sources, completed
reviews and remaining tasks in one report:

```bash
mceg explain mceg/contracts/model.yaml --evidence source_review --investigation --json
```

Use the contract path and Evidence ID reported by your provider. See the
[investigation guide](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/checks.md#resume-an-investigation) for selection
boundaries and the distinction between completed work and scientific support.

The package commands above work from any directory and require a provider version that
includes an evidence catalog. For editable installations or explicit catalog
files, see [packaged evidence catalogs](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/package_evidence.md).
The report describes recorded evidence, not an evaluation of your calculation's
conditions. ExoGibbs itself works without MCEG installed.

If your package has no MCEG records yet, start with
[LLM or manual setup](#add-mceg-to-an-existing-package).

## Main commands

The package command above reads an installed distribution. Run the repository
commands below from a provider checkout after installing MCEG.

| Task | Command |
| --- | --- |
| Start a model contract and inventory entry | `mceg init MODEL_ID --source PATH --symbol NAME` |
| Check discovered contracts and saved evidence | `mceg check` |
| Check requirements for a declared use | `mceg readiness USE.yaml --root .` |
| Explain gaps and the next review steps | `mceg explain` |
| Discover an installed provider's model evidence | `mceg explain --package exogibbs` |
| Resume a recorded investigation | `mceg explain CONTRACT --evidence EVIDENCE_ID --investigation --json` |
| Find inventory, contract and source-review gaps | `mceg coverage .` |
| Generate RST for repository documentation | `mceg docs --config mceg/docs.yaml` |
| Export an installed provider's graph | `mceg graph --package exogibbs` |
| Export one contract's graph | `mceg graph CONTRACT` |
| Export a quantity–relation model graph | `mceg model CONTRACT --model ID --format mermaid` |
| Export a calculation's graph | `mceg graph --case CASE` |
| Validate one contract's structure | `mceg path/to/contract.yaml` |
| Compare recorded conditions with a context | `mceg assess CONTRACT --context CONTEXT --subject ID --output NEW_FILE` |
| Preserve a v0.1 contract in v0.2 format | `mceg migrate CONTRACT --output NEW_FILE` |
| Trace an evidence record's sources | `mceg --trace EVIDENCE_ID CONTRACT` |

Use `mceg COMMAND -h` for options. `check`, `explain` and `coverage` offer JSON
reports; `check` and `explain` also accept `--lang ja`.
The [Graph JSON API](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/graph.md) exports contracts, scoped judgments,
investigation records and calculation connections for viewers and other tools.

[Packaged evidence catalogs](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/package_evidence.md) let users inspect a
provider's model/species records without cloning its repository or importing its
code. The provider supplies the catalog as data and need not depend on MCEG.
This reports recorded evidence; it does not evaluate a user's run conditions.

## Install

Install from PyPI using Python 3.10+:

```bash
python -m pip install mceg
```

For development from this checkout:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Runtime dependencies are Pydantic 2 and PyYAML 6. The `mceg` command is equivalent
to `python -m mceg`.

## Add MCEG to an existing package

Work in the scientific package's source checkout (the **provider**), with the
[MCEG environment](#install) active. Keep MCEG as an optional authoring tool,
outside the provider's runtime dependencies. Start with one model.

### With an LLM

Give a coding assistant access to both checkouts and replace the placeholders:

```text
Add MCEG to <provider checkout>, starting with <model or module>.
Follow <MCEG checkout>/docs/en/initialization.md and provider_onboarding.md
in the same directory. Inspect code, data, docs and tests to identify model
boundaries and choices, then use mceg init to create a v0.2 draft and inventory.
Document model conventions and evidence from inspected sources; record only
tests actually run. Keep missing support unknown and list concrete follow-ups.
Expand source_roots to the intended package scope and keep review_pending true
until human review. Preserve numerical behavior and keep MCEG optional.
Run mceg check, mceg explain and mceg coverage . from the provider root.
Summarize changed files, checks, remaining gaps and required human review.
```

### Manually

Choose the model boundary and its local Python definition after reading the code,
data, docs and tests. Replace the example names and choices with your own:

```bash
cd /path/to/provider
mceg init mypkg.water.power_law \
  --source src/mypkg/water.py --symbol gibbs_j \
  --setting water_model=power_law
```

`init` creates a v0.2 draft under `mceg/contracts/` and adds its code/contract
mapping to `mceg/models.yaml`. Edit the draft's `TODO` fields to describe units,
assumptions, model choices and inspected evidence. Run relevant provider tests
separately and retain their results before recording numerical support; leave
missing scientific support `unknown` with follow-ups.

The initial inventory scans the selected file only. Expand `source_roots` to
cover the intended package, classify and hash reviewed files, and clear
`review_pending` only after human review of model boundaries and links. Then run:

```bash
mceg check mceg/contracts/mypkg.water.power_law.yaml
mceg explain mceg/contracts/mypkg.water.power_law.yaml --evidence implementation
mceg coverage .
```

`coverage` returns **1** while review or registration gaps remain. Structural
validation does not establish scientific support. Save the records and link them
from the provider's docs. See the [setup guide](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/initialization.md) for both
workflows and the [provider workflow](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/provider_onboarding.md) for evidence
review. Installed-package discovery additionally needs a
[packaged catalog](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/package_evidence.md).

## Inspect existing contracts

The development version also supports [equation definitions and code bindings](docs/en/equations.md)
in schema `"0.3"`. Record the math, argument units and implementation revision,
then export a TeX fragment without adding MCEG to the provider's dependencies:

```bash
python -m mceg equations examples/equations/continuity.yaml \
  --output examples/equations/equations.tex --check
```

Definition hashes and static function checks detect changes; they do not prove
that code implements an equation or that the model is physically accurate.

Schema `"0.5"` adds [mathematical model graphs](docs/en/mathematical_models.md).
Define the meanings of quantities, select Equation revisions, and explicitly
connect each local symbol to a shared quantity. A model can include physical
laws, prescribed profiles, boundary conditions and probability statements:

```bash
mceg model examples/mathematical_models/isothermal.yaml \
  --model atmosphere --format mermaid
mceg model examples/mathematical_models/isothermal.yaml --model atmosphere \
  --format tex --output examples/mathematical_models/model_definition.tex --check
```

The graph describes adopted relationships, including coupled cycles. Claims and
Assessments can pin the whole assembly, so changing a quantity's meaning or a
connection requires review even when equation text stays unchanged. Definitions
and structural checks do not prove solvability, physical completeness or code
equivalence; provider code remains independent of MCEG.

`check` and `explain` discover YAML contracts under `mceg/contracts/` or
`contracts/`. Filter by name or give an explicit path:

```bash
mceg check -k water
mceg explain -k water --lang ja
mceg check mceg/contracts/water.yaml --json
```

A **PASS** applies to the named check and its scope. **UNKNOWN** identifies missing
support or an unresolved review. Numerical agreement, registered model mappings
and physical accuracy are separate questions. A stored result is not a fresh
solver run. For a recorded v0.2 Assessment, `--assessment ID --root .` also checks
its selected source and artifact hashes; see the [check guide](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/checks.md).

## Export relationship graphs

From this MCEG checkout, export a model's evidence and judgments or a calculation's
component connections:

```bash
mceg graph examples/v02/h2_solubility.yaml --provider mceg > model-graph.json
mceg graph --case examples/html/case.yaml --provider mceg > case-graph.json
```

For an installed provider with an evidence catalog:

```bash
mceg graph --package exogibbs > package-graph.json
```

To select the catalog directly from an ExoGibbs checkout:

```bash
mceg graph --catalog /path/to/exogibbs/src/exogibbs/data/mceg/index.json > package-graph.json
```

To run MCEG directly from its checkout, prepend its `src` directory to
`PYTHONPATH`, keeping any existing entries:

```bash
PYTHONPATH="/path/to/mceg/src${PYTHONPATH:+:$PYTHONPATH}" \
  python -m mceg graph --package exogibbs > package-graph.json
```

Package lookup also handles source-manifest paths in legacy `src`-layout editable
installs. Use `mceg graph --catalog PATH` for an explicit catalog or editable
installs whose metadata does not list the catalog. Local contract and case paths
resolve from `--root`, which defaults to the current directory. JSON retains
source identities, scoped judgments and explicit selections for viewers and LLM tools. See the
[Graph JSON API](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/graph.md) for Python examples and relationship meanings.

## Documentation and examples

For interactive inspection, run the standalone viewer (Node.js 22.12+):

```bash
cd viewer
npm ci
npm run dev
```

Open the printed local URL, choose **Open graph JSON**, and select an export
from `mceg graph`. The bundled H2 example can also be opened from the welcome
screen. Switch between English and Japanese in the header. See the
[viewer guide](https://github.com/HajimeKawahara/mceg/blob/main/viewer/README.md) for navigation and interpretation boundaries.

To publish the viewer on a static web server, run this from the same `viewer/`
directory:

```bash
npm run build
```

Upload **all contents of `viewer/dist/`** (`index.html`, `assets/`,
`viewer-export.json` and `example-graph.json`) to the server's public directory.
PHP, Node.js, Python and MCEG are not required on the server. Visitors open their graph JSON in the
browser; the build does not bundle a graph previously opened in the viewer.
See [static hosting instructions](https://github.com/HajimeKawahara/mceg/blob/main/viewer/README.md#static-hosting) for deployment
and local preview.

To publish a specific graph, open it in the viewer and click **Save as HTML**.
Upload the downloaded file to the server; it includes the complete graph and
interactive viewer, so visitors do not need to select a JSON file. See the
[HTML export guide](https://github.com/HajimeKawahara/mceg/blob/main/viewer/README.md#save-a-graph-as-a-standalone-html-page).

For a browsable model catalog and linked calculation/evidence graphs, see the
[HTML guide](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/html.md). Build it with Graphviz installed:

```bash
python -m pip install -e '.[docs]'
./update_doc.sh -W --keep-going
```

Open `docs/_build/html/index.html` and select **Calculation cases** for the H2
connection. The build reads saved records; it runs no scientific calculation.
Run `mceg docs --config mceg/docs.yaml` to generate RST and CSS for a provider.
Each repository builds HTML with its own Sphinx configuration and update script.

| Topic | Guides |
| --- | --- |
| Model registration | [LLM and manual setup](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/initialization.md), [inventory coverage](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/coverage.md), [provider workflow](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/provider_onboarding.md) |
| Checks and source review | [CLI checks](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/checks.md), [provenance](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/provenance.md), [evidence audit](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/evidence_audit.md) |
| Relationship graphs | [Graph JSON API](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/graph.md), [HTML documentation](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/html.md) |
| Mathematical definitions | [Quantity–relation model graphs](docs/en/mathematical_models.md), [equations and code bindings](docs/en/equations.md) |
| Contract formats | [v0.2](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/v02.md), [v0.1](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/schema.md), [compatibility](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/versioning.md) |
| Worked connections | [H2 solubility](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/h2_solubility.md), [provider trials](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/provider_trials.md), [provider-owned pilot](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/provider_pilot.md) |
| Evidence studies | [H2 sources](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/h2_primary_audit.md), [curated gas](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/curated_assessment.md), [assessment lifecycle](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/assessment_lifecycle.md) |
| Design questions | [English](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/design_questions.md), [Japanese](https://github.com/HajimeKawahara/mceg/blob/main/docs/ja/design_questions.md) |

Browse [example contracts](https://github.com/HajimeKawahara/mceg/tree/main/contracts) and [saved examples](https://github.com/HajimeKawahara/mceg/tree/main/examples).
The current package release is **`0.1.1`**. It reads both v0.1 and v0.2 contracts;
package versions and schema versions are separate. The frozen `v0.1.0` baseline
remains unchanged, and the v0.2 schema remains experimental.
See the [changelog](https://github.com/HajimeKawahara/mceg/blob/main/CHANGELOG.md) for changes and the
[release guide](https://github.com/HajimeKawahara/mceg/blob/main/docs/en/releasing.md) for publishing instructions.

## Development

MCEG's own [minimal self-description](mceg/README.md) records three design
principles and one existing document-loading feature under `mceg/`. These are
optional development records; package execution does not depend on them.

```bash
python -m pip install -e '.[test]'
python -m pytest
```
