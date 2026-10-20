# Start a model with `mceg init`

Use `init` after choosing a scientific model boundary and locating its Python
implementation. The command creates one editable v0.2 contract and registers a
pending model in the provider's inventory. It parses the local definition without
importing the provider or executing numerical tests.

```bash
cd /path/to/provider
mceg init mypkg.water.power_law \
  --source src/mypkg/water.py --symbol gibbs_j \
  --setting water_model=power_law
```

This creates `mceg/contracts/mypkg.water.power_law.yaml` and creates or updates
`mceg/models.yaml`. Paths are relative to the provider root; use `--root DIR`
when running elsewhere. Model IDs start with a letter or digit and contain only
letters, digits, `.`, `_` and `-`. The ID also names the contract file.

`--source` must name a local `.py` file. `--symbol` names its actual definition,
such as `gibbs_j`, `Host` or `Host.response`; use the defining module for a
re-exported API. Symlinks and paths escaping the provider root are rejected.
Additional implementation/data bindings can be added during review.

## Initial records

- The model and draft Subject identify the supplied source and symbol. Git
  origin supplies the repository when available; otherwise it is `unknown`.
  Revision is explicitly an **unreviewed working tree**, with Git HEAD as its
  base when available. `--repository` and `--revision` can provide explicit values.
- Numerical and scientific domains start as `unknown`. Numerical-verification
  and physical-accuracy Claims contain `TODO` statements with draft revisions.
- Implementation Evidence records the location with `inspection: not_inspected`.
  Assessments, Conditions and selected-file hashes start empty. The draft
  Context records supplied choices, not a calculation or execution environment.
- Follow-ups describe boundary review, numerical verification and empirical
  review. `mceg explain --evidence implementation` displays the boundary task;
  `--claim numerical_verification` and `--claim physical_accuracy` show the others.
- The inventory entry links the new contract and has `review_pending: true`.
  A reviewed shared file cannot complete review of a newly added model choice.
  No file classification or review hash is created automatically.

The new inventory scans only the supplied source file and `mceg/contracts`.
Existing roots are retained; a source outside them is added explicitly. Expand
`source_roots` to the intended package before using coverage as a package-wide
check. An initial file scope cannot discover new models in unscanned files.

## Model choices

Repeat `--setting KEY=VALUE` for identity choices:

```bash
mceg init mypkg.gas.neutral \
  --source src/mypkg/gas.py --symbol chemsetup \
  --setting ions=false --setting reference_pressure_bar=1
```

Values are JSON scalars or plain text. JSON booleans/numbers retain their types;
use `--setting 'label="1"'` for a numeric-looking string. Duplicate keys, empty
values, nulls, containers and nonfinite numbers are rejected. Settings are copied
to the inventory Binding and draft Context. They are authored identity hints:
MCEG does not validate arbitrary argument choices against the implementation.

Models sharing a function can have separate IDs and choices. `init` creates a
new contract for each new ID. When a reviewed family contract already covers a
choice, add that mapping to the inventory directly as described in the
[coverage guide](coverage.md). Existing model IDs or declared contract identities
are refused; edit their existing records instead of reinitializing them.

## Review and verify

```bash
mceg check mceg/contracts/mypkg.water.power_law.yaml
mceg explain mceg/contracts/mypkg.water.power_law.yaml --evidence implementation
mceg coverage .
```

The generated document passes structural validation while source/evidence review
remains unknown. Coverage reports `unreviewed_model` and missing file reviews;
exit code 1 is expected. Follow the [provider workflow](provider_onboarding.md)
to define conventions, inspect sources, collect evidence and write scoped
Assessments. Review inventory bindings, classify and pin the relevant files, then
clear `review_pending`. Completing inventory review does not establish physical
support or complete the contract's evidence tasks.

Existing contracts are never overwritten. Inventory updates append to its root
lists while retaining prior records, review pins and comments. Direct block/flow
YAML lists and JSON-formatted inventories are supported; aliased or merged root
lists that need modification must first be made explicit. Inputs and generated
records are validated before writing. Inventory replacement is atomic, and a
failed inventory update removes the newly created contract.

`init` exits **0** when it creates the draft, and **2** for input or write errors.
The separate coverage result describes remaining work. Run `mceg init -h` for
the complete CLI options.
