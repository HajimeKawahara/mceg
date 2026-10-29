# MCEG: Model Contracts and Evidence Graphs

MCEG records scientific models, their assumptions, applicability and evidence in
YAML. It checks contracts, explains missing support, and maps models to code.
Providers own their scientific records; core checks work without importing or
running provider implementations.

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

## Main commands

The package command above reads an installed distribution. Run the repository
commands below from a provider checkout after installing MCEG.

| Task | Command |
| --- | --- |
| Start a model contract and inventory entry | `mceg init MODEL_ID --source PATH --symbol NAME` |
| Check discovered contracts and saved evidence | `mceg check` |
| Explain gaps and the next review steps | `mceg explain` |
| Discover an installed provider's model evidence | `mceg explain --package exogibbs` |
| Find inventory, contract and source-review gaps | `mceg coverage .` |
| Generate RST for repository documentation | `mceg docs --config mceg/docs.yaml` |
| Validate one contract's structure | `mceg path/to/contract.yaml` |
| Compare recorded conditions with a context | `mceg assess CONTRACT --context CONTEXT --subject ID --output NEW_FILE` |
| Preserve a v0.1 contract in v0.2 format | `mceg migrate CONTRACT --output NEW_FILE` |
| Trace an evidence record's sources | `mceg --trace EVIDENCE_ID CONTRACT` |

Use `mceg COMMAND -h` for options. `check`, `explain` and `coverage` offer JSON
reports; `check` and `explain` also accept `--lang ja`.

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

## Start your first model

Choose the model boundary and a local Python definition. Different model choices
may share one function; record the selected choice explicitly.

```bash
cd /path/to/provider
mceg init mypkg.water.power_law \
  --source src/mypkg/water.py --symbol gibbs_j \
  --setting water_model=power_law

mceg check mceg/contracts/mypkg.water.power_law.yaml
mceg explain mceg/contracts/mypkg.water.power_law.yaml --evidence implementation
mceg coverage .
```

`init` creates a v0.2 draft under `mceg/contracts/` and adds its code/contract
mapping to `mceg/models.yaml`. Existing contracts, inventory records and comments
are preserved. Review the draft's `TODO` fields and evidence before adding
assessments. A new model has `review_pending: true`, unknown applicability and no
recorded test results or file-review hashes.

The initial inventory scans the selected file only. Expand `source_roots` to
cover the intended package, classify its files and review model boundaries.
`coverage` returns **1** while review or registration gaps remain; clearing the
model's pending flag is a human review step. See the [init guide](docs/en/initialization.md)
and [provider authoring workflow](docs/en/provider_onboarding.md).

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

## Documentation and examples

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
| Model registration | [Init](docs/en/initialization.md), [inventory coverage](docs/en/coverage.md), [provider workflow](docs/en/provider_onboarding.md) |
| Checks and source review | [CLI checks](docs/en/checks.md), [provenance](docs/en/provenance.md), [evidence audit](docs/en/evidence_audit.md) |
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
