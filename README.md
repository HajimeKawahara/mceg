# MCEG: Model Contracts and Evidence Graphs

**Model Contracts and Evidence Graphs (MCEG)** is a framework for making the claims, assumptions, applicability domains, and supporting evidence of computational scientific models explicit, traceable, and auditable by both humans and AI systems.

By systematically representing what a scientific model claims, under which conditions those claims hold, and what evidence supports them, MCEG facilitates scientifically informed decisions throughout model development, validation, and use.

Rather than automatically guaranteeing the correctness of scientific models, MCEG provides a transparent foundation for humans and AI systems to continuously examine their scientific validity, limitations, and supporting evidence.

Human and LLM reviewers also use these records to resume investigations, compare
sources and justify model changes. The [investigation design](docs/en/design_questions.md#investigations-by-human-and-llm-reviewers)
describes this workflow and the proposed next improvements.

Two design commitments guide that workflow: an LLM without the previous
conversation must be able to follow the evidence and resume an investigation;
humans must also be able to inspect the evidence and model contracts themselves.
[MCEG Viewer](viewer/README.md) provides a small bilingual interface for that
inspection. It consumes exported Graph JSON; MCEG itself does not depend on it.

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
[investigation guide](docs/en/checks.md#resume-an-investigation) for selection
boundaries and the distinction between completed work and scientific support.

The package commands above work from any directory and require a provider version that
includes an evidence catalog. For editable installations or explicit catalog
files, see [packaged evidence catalogs](docs/en/package_evidence.md).
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
| Explain gaps and the next review steps | `mceg explain` |
| Discover an installed provider's model evidence | `mceg explain --package exogibbs` |
| Resume a recorded investigation | `mceg explain CONTRACT --evidence EVIDENCE_ID --investigation --json` |
| Find inventory, contract and source-review gaps | `mceg coverage .` |
| Generate RST for repository documentation | `mceg docs --config mceg/docs.yaml` |
| Export an installed provider's graph | `mceg graph --package exogibbs` |
| Export one contract's graph | `mceg graph CONTRACT` |
| Export a calculation's graph | `mceg graph --case CASE` |
| Validate one contract's structure | `mceg path/to/contract.yaml` |
| Compare recorded conditions with a context | `mceg assess CONTRACT --context CONTEXT --subject ID --output NEW_FILE` |
| Preserve a v0.1 contract in v0.2 format | `mceg migrate CONTRACT --output NEW_FILE` |
| Trace an evidence record's sources | `mceg --trace EVIDENCE_ID CONTRACT` |

Use `mceg COMMAND -h` for options. `check`, `explain` and `coverage` offer JSON
reports; `check` and `explain` also accept `--lang ja`.
The [Graph JSON API](docs/en/graph.md) exports contracts, scoped judgments,
investigation records and calculation connections for viewers and other tools.

[Packaged evidence catalogs](docs/en/package_evidence.md) let users inspect a
provider's model/species records without cloning its repository or importing its
code. The provider supplies the catalog as data and need not depend on MCEG.
This reports recorded evidence; it does not evaluate a user's run conditions.

## Install

From this checkout, using Python 3.10+:

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
from the provider's docs. See the [setup guide](docs/en/initialization.md) for both
workflows and the [provider workflow](docs/en/provider_onboarding.md) for evidence
review. Installed-package discovery additionally needs a
[packaged catalog](docs/en/package_evidence.md).

## Inspect existing contracts

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
its selected source and artifact hashes; see the [check guide](docs/en/checks.md).

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

Use `mceg graph --catalog PATH` for an explicit catalog, including editable
provider checkouts. Local contract and case paths resolve from `--root`, which
defaults to the current directory. JSON retains source identities, scoped
judgments and explicit selections for viewers and LLM tools. See the
[Graph JSON API](docs/en/graph.md) for Python examples and relationship meanings.

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
[viewer guide](viewer/README.md) for navigation and interpretation boundaries.

To publish the viewer on a static web server, run this from the same `viewer/`
directory:

```bash
npm run build
```

Upload **all contents of `viewer/dist/`** (`index.html`, `assets/` and
`example-graph.json`) to the server's public directory. PHP, Node.js, Python and
MCEG are not required on the server. Visitors open their graph JSON in the
browser; the build does not bundle a graph previously opened in the viewer.
See [static hosting instructions](viewer/README.md#static-hosting) for deployment
and local preview.

For a browsable model catalog and linked calculation/evidence graphs, see the
[HTML guide](docs/en/html.md). Build it with Graphviz installed:

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
| Model registration | [LLM and manual setup](docs/en/initialization.md), [inventory coverage](docs/en/coverage.md), [provider workflow](docs/en/provider_onboarding.md) |
| Checks and source review | [CLI checks](docs/en/checks.md), [provenance](docs/en/provenance.md), [evidence audit](docs/en/evidence_audit.md) |
| Relationship graphs | [Graph JSON API](docs/en/graph.md), [HTML documentation](docs/en/html.md) |
| Contract formats | [v0.2](docs/en/v02.md), [v0.1](docs/en/schema.md), [compatibility](docs/en/versioning.md) |
| Worked connections | [H2 solubility](docs/en/h2_solubility.md), [provider trials](docs/en/provider_trials.md), [provider-owned pilot](docs/en/provider_pilot.md) |
| Evidence studies | [H2 sources](docs/en/h2_primary_audit.md), [curated gas](docs/en/curated_assessment.md), [assessment lifecycle](docs/en/assessment_lifecycle.md) |
| Design questions | [English](docs/en/design_questions.md), [Japanese](docs/ja/design_questions.md) |

Browse [example contracts](contracts) and [saved examples](examples).
The current package is the experimental **`0.2.0rc2`** candidate. It reads both
v0.1 and v0.2 contracts; the frozen `v0.1.0` baseline remains unchanged.
See the [changelog](CHANGELOG.md) for candidate-format extensions.

## Development

```bash
python -m pip install -e '.[test]'
python -m pytest
```
