# Model inventory and coverage

`mceg coverage` checks an independent, provider-owned model inventory against
local source files and contracts. It does not import the provider, run numerical
tests, assess physical accuracy, or infer scientific models from function names.
No MCEG dependency is needed in the provider's runtime environment.

```bash
mceg coverage /path/to/provider
mceg coverage /path/to/provider --json
mceg coverage . --inventory mceg/models.yaml
```

To start a contract and its pending inventory entry, use
[`mceg init`](initialization.md). It leaves source files unclassified and model
review pending until a human records the review.

The default inventory is `mceg/models.yaml`, relative to the provider root
(current directory by default). YAML and JSON use the same strict schema and
duplicate-key checks. Exit codes are **0** for complete registration/review
within the declared scope, **1** for gaps, and **2** for invalid input. A provider
with known uncovered models should return 1; do not remove the models to pass CI.

## Inventory format

The inventory has its own `inventory_version: '0.1'`, independent of contract
schema versions. Both v0.1 and v0.2 contracts can be linked. A small example:

```yaml
inventory_version: '0.1'
scope: Water-law choices and their packaged coefficients; examples are outside scope.
source_roots: [src/provider]
contract_roots: [mceg/contracts]
files:
  src/provider/water.py:
    sha256: REPLACE_WITH_REVIEWED_FILE_SHA256
    role: model
    note: Reviewed both laws selected by the water_model argument.
  src/provider/__init__.py:
    sha256: REPLACE_WITH_REVIEWED_FILE_SHA256
    role: support
    note: Re-exports only; definitions are mapped at their implementation modules.
models:
- id: provider.water.power_law
  description: Integrated power-law water concentration with host response.
  bindings:
  - path: src/provider/water.py
    symbol: gibbs_j
    settings: {water_model: power_law}
  contracts:
  - path: mceg/contracts/water.yaml
    model_id: provider.water_family.v1
- id: provider.water.two_power_law
  description: Integrated sum of two water pressure powers.
  bindings:
  - path: src/provider/water.py
    symbol: gibbs_j
    settings: {water_model: two_power_law}
  contracts: []
```

Replace the placeholders with lowercase, 64-character SHA-256 digests after
review. The second model is deliberately uncontracted even though it shares a
function with the first. Several inventory models may link the same family
contract, and one model may link several contracts and implementation files.
Inventory IDs identify authored model boundaries; `contracts[].model_id` must
equal the linked contract's `model.id`. A link records registration, not that the
contract proves every claim about the inventory model.
Bindings are authored independently of contract `implementation.entry_points`,
which remain descriptive strings; the checker does not resolve re-export aliases
or prove that those strings describe the bound model's scientific scope.

`models[].review_pending` optionally marks a model whose boundary and contract
links still need review. It defaults to `false` for existing authored inventories;
`init` sets it to `true`. Pending models produce `unreviewed_model` even if a
shared file already has a current review hash. Clear it only after reviewing
the new model's identity and links. This flag concerns inventory review, not
scientific support or the contract's separate Follow-up records.

`source_roots` and `contract_roots` name explicit directories or individual files.
Paths are normalized, relative POSIX paths within the provider. Symlinks are
reported as gaps without reading their targets. All source files, including
untracked files, private modules, hidden files and coefficient data, are scanned;
only `__pycache__` and `.pyc`/`.pyo` entries are skipped. Contracts are discovered
recursively by `.yaml`, `.yml` or `.json` extension under their own roots.

Every file review requires a digest, a `model` or `support` role, and a reason.
Omit a file from `files` until its role and boundaries have been reviewed; the
scanner will report it as unreviewed. Do not label unfamiliar code as support.
A model binding needs a file with role `model`, and each such file must be bound
to at least one model. These pins describe the inventory review snapshot, not a
test receipt or a complete dependency lock.

`bindings[].symbol` optionally names a local Python definition (`function`,
`Class`, or `Class.method`). AST inspection checks its existence without imports;
bind re-exported APIs at their defining module. Omit `symbol` for coefficient
files or whole-module dependencies. `settings` contains flat string, number or
boolean selections. These are authored identity records: the checker does not
execute or validate arbitrary argument values, data keys or callback choices.

## What the check detects

| Gap | Diagnostic |
| --- | --- |
| An inventoried model has no contract | `uncontracted_model` |
| A model's boundary/link review is pending | `unreviewed_model` |
| A contract is missing, invalid or linked with the wrong model ID | `invalid_contract`, `contract_mismatch` |
| A discovered contract has no inventory link | `unlisted_contract` |
| A new or not-yet-classified source/data file exists | `unreviewed_file` |
| A reviewed file changed or disappeared | `changed_file`, `missing_source` |
| A bound function/class was renamed or removed | `missing_symbol` |
| A model file has no model, or a binding lacks a model-file review | `unbound_model_file`, `unreviewed_binding` |
| A scan root is missing, unreadable or symlinked | `source_scan_error`, `contract_scan_error` |

Changes anywhere in a reviewed file, including a new branch, coefficient or
function inside a previously support-only file, require review. JSON separates
each model's `registration` from its `source_status`; a registration can remain
present while the implementation needs review. Overall status is `complete`
only if no gaps remain. Results are deterministic and the command writes nothing.

This is not a proof that all implicit scientific models have been found. An
already-existing branch omitted from the initial human review, or an omitted
variant in an otherwise mapped function, cannot be inferred from a hash or a
contract. Removing just that variant from the inventory can also escape detection
if the remaining mappings still cover its file and contract. Changes outside
the declared roots are not scanned. Review the initial inventory and subsequent
inventory diffs, including scope reductions and hash refreshes. A model family
with unenumerated internal choices must say so in its description.

## Maintenance and the solubility/magma example

1. Inspect the code, data and scientific choices before creating inventory rows.
   Split materially different laws even when they share a function; keep aliases
   of one law together. Record known uncontracted families with `contracts: []`.
2. Add file classifications and pins for the reviewed snapshot. Keep unreviewed
   files visible. Bind all files needed to describe each chosen model boundary.
3. Author the contract and evidence using the [provider workflow](provider_onboarding.md).
   Link its path and exact model ID; run `mceg coverage` and the separate contract
   structure, evidence and hash checks.
4. After code/data changes, review affected model boundaries and options, update
   the inventory, and renew scientific records where needed. Refreshing a hash
   alone is not a review and does not renew an old numerical Assessment.

ExoEOS and ExoGibbs publish `mceg/models.yaml` beside their narrative inventory.
The 2026-10-20 example maps five ExoEOS water choices and four helium hosts to
their existing family contract. ExoGibbs's CO and N linear/log APIs each remain
one model, while the coupled MELTYQ boundary and IW oxygen buffer are separate
uncontracted models. The inventories scan the full packaged source trees;
ExoGibbs also lists four archived study scripts explicitly. These are partial
reviews, so coverage correctly reports gaps rather than complete packages.

The provider reports under `results/mceg/20261020_coverage/` preserve baseline
JSON and mutation checks run on temporary copies. A regression removes a
contract link from one water choice while leaving the shared function and
family contract intact. Other mutations add a source file or branch, change
coefficients, remove a definition, or break a contract ID. Baseline gaps are
kept separate from newly introduced diagnostics; all reports concern inventory
coverage only and leave physical support unchanged.
