# MCEG: Model Contracts and Evidence Graphs

MCEG describes scientific models, assumptions, applicability domains, claims,
evidence, and limitations in machine-readable YAML. The long-term aim is to
identify incompatible model combinations, unsupported applications, and missing
evidence across scientific packages.

This repository contains the **experimental v0.2 release candidate** (`0.2.0rc2`).
It reads both the frozen v0.1 contracts and the new v0.2 records, which separate
scientific Claims from context-specific Assessments. It checks structure and
source records, compares explicitly supplied conditions, and explains remaining
work. These checks do not establish scientific validity or package compatibility.
See the [version policy](docs/en/versioning.md) and [v0.2 guide](docs/en/v02.md).
The `v0.1.0` baseline and its schema meanings remain unchanged.

## Design principles

- Keep MCEG independent of the packages it describes. Providers own their model
  contracts and scientific reviews. MCEG supplies generic schemas and checks;
  archived provider examples are fixtures, not runtime dependencies.
- Separate scientific applicability from the domain where equations can be
  evaluated numerically. A finite result is not an accuracy guarantee.
- Separate numerical **verification** from physical **validation** against
  experiments or observations. Agreement with another implementation is verification.
- Record the evidence actually inspected, its scope, and its provenance.
  Do not invent claims, test outcomes, references, or applicability bounds.
- Trace adopted numbers and conditions to original sources. Distinguish locating
  a citation, inspecting its relevant content, and comparing it with a later use.
- Record missing knowledge explicitly as `unknown`. Unknown does not mean false,
  physically invalid, or universally applicable.
- Keep model definitions, test conditions, and physical calibration distinct.
- Start small: no graph database, reasoning engine, or automatic scientific-model inference.
  Automatic evidence reuse is limited to explicitly reviewed cases. Upstream
  execution is confined to optional examples.

## Install

Python 3.10+ is required. Runtime dependencies are Pydantic 2 and PyYAML 6.

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m mceg contracts/*.yaml
.venv/bin/python -m pytest
```

The installed `mceg` command is equivalent to `python -m mceg`.

## Quick usage

Activate the MCEG environment and run `mceg check` from a provider checkout or
its `mceg/contracts` directory. Contracts and available checks are discovered
automatically, like a test runner:

```bash
source /path/to/mceg/.venv/bin/activate
cd /path/to/exogibbs

mceg check                               # Check all discovered contracts
mceg check -k curated                    # Select curated gas
mceg check -k curated --temperature 1750  # Change the requested temperature (K)
mceg check -k curated --plain             # Use the original text layout
mceg check -k curated --lang ja           # Use Japanese UI messages
mceg check -k curated -v                  # Show audit gaps and recorded claims
mceg check -k curated --json              # Emit the full JSON report
mceg coverage .                          # Check the provider's model inventory
mceg -h                                 # Show commands and usage examples
```

Terminal output shows green `✓ PASS`, red `✗ FAIL`, yellow `? UNKNOWN`, and a
summary. `UNKNOWN` marks missing support or review gaps, not a failed claim.
Pipes and redirected output automatically use the plain layout; `NO_COLOR=1`
disables color while keeping the terminal layout.

Curated gas uses the bundled **archived example context** by default. At 1750 K,
the temperature is in range but is not an archived sample, so evidence reuse is
`UNKNOWN`. Use `--context context.json` to supply your own context. These checks
inspect saved evidence without running a solver or detecting installed Python/JAX
versions. See `mceg check --help` and the [check command guide](docs/en/checks.md)
for all options, scope, and exit codes.

Providers can publish `mceg/models.yaml` to map scientific models to code and
contracts, including multiple model choices within one function. `mceg coverage`
reports uncontracted models, broken mappings, and new or changed source/data
files requiring review. It checks registration and review coverage, independently
of numerical or physical support; see the [inventory guide](docs/en/coverage.md).

### Follow an UNKNOWN result

`check` adds one `Next steps:` command. Copy it to inspect the same selection and
requested conditions, then select an Evidence, Claim, or Assessment ID:

```bash
mceg explain -k curated --temperature 1750
mceg explain -k curated --evidence source_choices
mceg explain -k curated --plain          # Keep the original text layout
mceg explain -h                          # Show options and examples
mceg explain /path/to/mceg/examples/v02/h2_solubility.yaml --evidence experimental_fit
```

`explain` shows the recorded gap, source locations and inspection notes, the next
action, required material, and completion criteria. For the H2 original fit it
shows the paper's DOI, the previously recorded access barrier, and the equations,
concentration basis and transformations still requiring inspection. Institutional
library access or an authorized author copy may be needed. Obtaining a paper does
not automatically complete its inspection or support a Claim.

Recorded curator instructions and generic suggestions are labeled separately.
On a terminal, colored status markers and numbered tasks separate the next
action, required material and completion criteria. Record fields use readable
labels; file hashes, artifacts and sample lists are summarized by count.
`--plain` preserves the original text layout, also used automatically in pipes.
`NO_COLOR=1` keeps the terminal layout without colors.
Use `--claim ID` or `--assessment ID` for their scope, evidence and next steps;
`--json` retains full records. No source is downloaded or evidence changed.

For v0.2, `mceg check contract.yaml --assessment ID` audits that Assessment's
Evidence and provenance dependencies. Its next-step command retains the ID.
Without a selector, checks explicitly include historical records. Authored
`follow_up_resolutions` move completed tasks out of pending instructions and
link their completion evidence; historical inspection and support stay intact.
The new optional field requires rc2 or later; rc1 rejects it. See the
[v0.2 guide](docs/en/v02.md#record-completed-work).

Add `--root /path/to/provider` with `--assessment ID` to verify the selected
Subject's file hashes and its Evidence artifact hashes. The same option works
with `explain`. This checks local bytes without changing historical support;
see [local file verification](docs/en/checks.md#verify-local-file-hashes).

Both `check` and `explain` accept `--lang ja` for Japanese headings, check
messages and suggested work (`--lang en` is the default). Follow-up commands
retain the chosen language. This is a display-only translation catalog: contract
text, authored follow-ups, IDs, status tokens and JSON reports stay original.
It adds no translated fields to scientific records and needs no translation
service. For example:

```bash
mceg explain -k curated --temperature 1750 --lang ja
```

### Try the v0.2 format

From this repository, preserve an old contract in the common format, or evaluate
the source-specific conditions already recorded in the H2 example:

```bash
mceg migrate contracts/h2_solubility.yaml --output /tmp/h2-migrated.yaml
mceg assess examples/v02/h2_solubility.yaml \
  --context examples/v02/h2_context.json --subject imported \
  --output /tmp/h2-assessed.yaml
mceg check /tmp/h2-assessed.yaml
mceg explain /tmp/h2-assessed.yaml --assessment imported:physical_accuracy

mceg assess --curated /path/to/exogibbs \
  --context examples/curated_gas/context.json --output /tmp/curated-v02.yaml
mceg explain /tmp/curated-v02.yaml
```

Outputs must be new files. Migration preserves old declarations without
inventing structured conditions. Assessment adds separate records; the H2
example deliberately reports conflicting temperature intervals at 1750 K and
leaves physical accuracy unknown. The curated adapter exports the existing
reviewed reuse policy without running a solver. See the [v0.2 guide](docs/en/v02.md)
for Context inputs, identity rules, and the distinction between range membership
and scientific support.

## Validation and source tracing

For the original structural validator, pass one or more YAML paths.
Each file receives a `VALID ... (structure only)` or `INVALID`
message; the exit code is 0 if all pass, 1 if any fail, and 2 for CLI usage errors.
Validation is offline and never imports or executes referenced implementations.

Trace the recorded origin of a specific fact:

```bash
python -m mceg --trace metadata_pressure contracts/h2_solubility.yaml
python -m mceg --trace formulation_temperature contracts/h2_solubility.yaml
python -m mceg --trace implementation contracts/h2_solubility.yaml
```

The pressure-envelope comparison reaches an inspected original abstract.
The temperature and empirical-coefficient traces retain uninspected original
content. `recorded_audit_complete` summarizes supplied inspection/comparison
records, not physical validity. See
[source tracing](docs/en/provenance.md) ([Japanese](docs/ja/provenance.md)).

```python
from mceg import load_contract

contract = load_contract("contracts/second_virial.yaml")
for claim in contract.claims:
    print(claim.kind, claim.status, claim.statement)
```

For development with dependencies already installed:

```bash
PYTHONPATH=src python -m mceg contracts/*.yaml
python -m pytest
```

## Examples and evidence

| Contract | Model selected | What it demonstrates |
| --- | --- | --- |
| [Ideal gas](contracts/ideal_gas.yaml) | `exoeos.IdealEOS` | Zero residual Helmholtz energy, ideal pressure and fugacity identities |
| [Second virial](contracts/second_virial.yaml) | `exoeos.SecondVirialEOS` | Constant pair coefficients, density truncation, low-density root |
| [Peng–Robinson](contracts/peng_robinson.yaml) | `exoeos.PengRobinsonEOS` | PR76 conventions, mixing and root selection, frozen independent-code reference |
| [Pure-H2 Zhang–Duan](contracts/zhang_duan_h2.yaml) | `ZhangDuanEOS.from_species(("H2",))` | Species-specific PVT evidence coverage and unknown extrapolation accuracy |
| [H2 solubility](contracts/h2_solubility.yaml) | `exogibbs.solubility.h2_hirschmann2012` | Experimental/formulation provenance, differing reported intervals, calibration revisions |

The first three use the same residual Helmholtz interface. `IdealGas`, a separate
constant-heat-capacity caloric model in ExoEOS, is deliberately not conflated with
`IdealEOS`. These contracts describe implementation families, not calibrated
models for arbitrary materials. The synthetic test parameters and particular
mixtures appear only in scoped evidence.

The [evidence audit](docs/en/evidence_audit.md) records inspected revisions, actual
test runs, saved upstream results, literature, and ExoGibbs integration findings.
Physical validation and quantitative scientific applicability remain `unknown`
for those initial contracts. No empirical evidence was established by that audit.

## Worked connection: H2 solubility

The [worked example](docs/en/h2_solubility.md) ([Japanese](docs/ja/h2_solubility.md))
evaluates a pure-H2 EOS-to-solubility connection at **1700 K and 7500 bar**.
It records numerical outputs and manually distinguishes inclusion in reported
temperature/pressure intervals, extrapolation beyond pure-H2 PVT data, and
unknown composition, fugacity coverage, and combined physical accuracy.

- [case.yaml](examples/h2_solubility/case.yaml): fixed inputs, two contract
  references, unit connection, and scoped manual assessments.
- [result.json](examples/h2_solubility/result.json): actual outputs, numerical
  checks, versions, revisions, and selected source hashes.
- [run.py](examples/h2_solubility/run.py): optional replay using the audited
  sibling checkouts. It does not infer the manual classifications.

`case.yaml` is example-specific data, **not a contract accepted by the MCEG CLI**.
The two model contracts use the experimental v0.1 schema. Core validation and tests
still require neither upstream package nor JAX. The guide describes replaying
the calculation with those optional dependencies.

The separate [range assessment](examples/h2_solubility/assess.py) compares supplied
temperature and actual melt pressure with three
[source-specific intervals](examples/h2_solubility/conditions.yaml). At 1750 K,
the metadata interval includes the temperature while Seo's interval excludes it.
The [saved assessment](examples/h2_solubility/assessment.json) preserves both
outcomes and leaves physical validation unknown. Run it without provider packages:

```bash
PYTHONPATH=src python examples/h2_solubility/assess.py --temperature-k 1750 --melt-pressure 7500 --pressure-unit bar --output /tmp/h2-assessment.json
```

Omitting either quantity returns `unknown` for its comparisons. This example
does not change v0.1 Claim statuses. See the
[assessment design and migration proposal](docs/en/design_questions.md#claim-evidence-and-assessment-separation).

The [primary-source audit](docs/en/h2_primary_audit.md)
([Japanese](docs/ja/h2_primary_audit.md)) records what was confirmed, the original
full-text access gap, a possible material-specific explanation of the temperature
difference, and the inherited infrared-calibration problem. Scientific accuracy
remains unknown; no empirical coefficient or computed concentration was corrected.

## Provider adoption trials

The [provider authoring procedure](docs/en/provider_onboarding.md) describes how
to add a v0.2 model contract, from model identity and source review to numerical
receipts, file verification and later updates. It was exercised on six ExoGibbs
solubility laws and eight ExoEOS magma, fluid, alloy and solute constructions.
Each provider's `mceg/model_inventory.md` lists coverage and remaining work.
The new pressure quantity names are described in the [v0.2 guide](docs/en/v02.md).

The [three trials](docs/en/provider_trials.md) ([Japanese](docs/ja/provider_trials.md))
use the frozen v0.1 format to test a second connection and provider-side workflows:

- [Mixture case](examples/virial_mixture/case.yaml): actual ExoEOS/ExoGibbs
  callbacks at two temperatures with `extrapolate` and `hold_2000`, two scoped
  contracts, manual assessments, and a saved execution with 35 numerical checks.
- [Placement and revision trial](examples/provider_workflow/run.py): copy five
  baseline contracts and their local evidence into temporary provider layouts,
  detect missing references, and retain historical evidence during a synthetic
  implementation change. [Saved report](examples/provider_workflow/result.json).

These are example scripts, not additions to the core API or schema. The placement
and revision trials operate on temporary copies. Existence checks leave external citations and
fragments unchecked; implementation changes require manual claim review.

The [provider-owned H2 pilot](docs/en/provider_pilot.md)
([Japanese](docs/ja/provider_pilot.md)) reads contracts directly from separate
ExoEOS and ExoGibbs checkouts. It replays the original case and distinguishes
the audited implementation revision from the later contract-publication commit
by checking selected source hashes against both the receipt and Git objects.

## Schema and open questions

The [curated-gas assessment experiment](docs/en/curated_assessment.md) reads
ExoGibbs's provider-owned contract and 70-case numerical receipt without
importing the provider. It separates continuous temperature bounds, discrete
test coverage and reuse of one reviewed Claim declaration. Changed selected
files or a different context leave support unknown while preserving historical
outcomes. Its [saved assessment](examples/curated_gas/assessment.json) and
synthetic regression fixtures inform v0.2. The `mceg check` command and v0.2
curated adapter share its evaluator; the original v0.1 contract is preserved.

The [assessment lifecycle trial](docs/en/assessment_lifecycle.md) adds actual
70-case reruns under two JAX versions, lossless declaration-migration checks for
H2 and curated gas, and a scoped source-adoption dependency probe. It preserves
old results while adding assessments for the newly executed environments.

The [v0.1 schema guide](docs/en/schema.md) and [v0.2 guide](docs/en/v02.md)
describe the supported formats. Their executable definitions are
[schema.py](src/mceg/schema.py) and [schema_v02.py](src/mceg/schema_v02.py).
In v0.2, Assessments link Claim revisions, evaluated Subjects, Contexts and
Evidence. Conditions record closed intervals or explicit joint samples;
provenance links retain scoped original-source comparisons. Equations are
descriptive text and are never executed by MCEG.

The main unresolved questions are parameter and species identity, units and
reference states, nonrectangular applicability domains, uncertainty, evidence
independence, and the difference between a test definition and a reproducible run.
See [design questions in English](docs/en/design_questions.md) or
[Japanese](docs/ja/design_questions.md).

The mixture trial additionally exposes policy-dependent model identity, full-gas
composition conventions, source relocation, and evidence freshness. These remain
explicit review concerns rather than automatic scientific judgments.
