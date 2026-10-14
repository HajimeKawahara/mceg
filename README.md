# MCEG: Model Contracts and Evidence Graphs

MCEG describes scientific models, assumptions, applicability domains, claims,
evidence, and limitations in machine-readable YAML. The long-term aim is to
identify incompatible model combinations, unsupported applications, and missing
evidence across scientific packages.

This repository is an **experimental v0.1 proof of concept**, frozen as the
`v0.1.0` baseline. It is not a final standard. The [version policy](docs/en/versioning.md)
([Japanese](docs/ja/versioning.md)) defines the freeze boundary and future changes.
It contains five contracts, one worked connection example, and a small Pydantic
validator. Validation checks
structure and local evidence links. It does not decide scientific validity,
compute applicability, detect extrapolation, or certify package compatibility.

## Design principles

- Keep MCEG independent of the packages it describes. ExoEOS and ExoGibbs are
  examples, not dependencies; neither repository is modified.
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
- Start small: no graph database, reasoning engine, automatic code inspection,
  or condition evaluator. Upstream execution is confined to an optional example.

## Install and use

Python 3.10+ is required. Runtime dependencies are Pydantic 2 and PyYAML 6.

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m mceg contracts/*.yaml
.venv/bin/python -m pytest
```

The installed `mceg` command is equivalent to `python -m mceg`. Pass one or more
YAML paths. Each file receives a `VALID ... (structure only)` or `INVALID`
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

The [primary-source audit](docs/en/h2_primary_audit.md)
([Japanese](docs/ja/h2_primary_audit.md)) records what was confirmed, the original
full-text access gap, a possible material-specific explanation of the temperature
difference, and the inherited infrared-calibration problem. Scientific accuracy
remains unknown; no empirical coefficient or computed concentration was corrected.

## Schema and open questions

The [schema guide](docs/en/schema.md) describes the small YAML format.
[Pydantic models](src/mceg/schema.py) are its executable definition. Claims link
to evidence by local IDs; optional provenance links connect scoped evidence
to its recorded original sources within the same contract.
All model-specific equations and conditions remain descriptive text.

The main unresolved questions are parameter and species identity, units and
reference states, nonrectangular applicability domains, uncertainty, evidence
independence, and the difference between a test definition and a reproducible run.
See [design questions in English](docs/en/design_questions.md) or
[Japanese](docs/ja/design_questions.md).

A possible next case is the example-level mixture provider with explicit
virial-coefficient extrapolation policies. It remains outside the implemented
H2 solubility example.
