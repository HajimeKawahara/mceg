# Add MCEG to an existing package

For a package with no MCEG records, start with one scientific model in its source
checkout (the **provider**). An LLM can help inspect code and draft records; a
maintainer reviews the model boundaries and evidence. The manual workflow uses
the same files and checks. Keep MCEG outside the provider's runtime dependencies.

## Before you start

Use Python 3.10+ and local MCEG and provider checkouts. Create a companion MCEG
environment once, or activate an existing one:

```bash
cd /path/to/mceg
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cd /path/to/provider
```

Replace the paths with your checkouts. MCEG's metadata commands do not require
installing or importing the provider. Run its numerical tests separately in the
provider's own test environment.

## With an LLM

Use a coding assistant that can inspect both checkouts, edit the provider's files
and run commands. Replace the paths and starting model in this prompt:

```text
Add MCEG to <provider checkout>, starting with <model or module>.
Read <MCEG checkout>/docs/en/initialization.md, provider_onboarding.md,
coverage.md and v02.md in the same directory. Use that checkout's CLI/schema.

Inspect the implementation, coefficient data, docs and relevant tests. Identify
model boundaries, units, assumptions and selected options before using mceg init.
Create a v0.2 draft in mceg/contracts/ and its mapping in mceg/models.yaml;
preserve existing work and keep changes minimal, with no numerical behavior
changes or runtime MCEG dependency.

Replace TODO fields only with reviewed information. Record source locations and
actual inspection/comparison status. Run relevant existing tests in the provider's
test environment and retain commands, environment, revision, outcomes and hashes
for the evidence used. Mark unexecuted tests not_run. Keep numerical verification
separate from physical accuracy; leave unavailable support unknown with concrete
follow-ups. Do not invent citations, applicability ranges or successful results.

Expand inventory source_roots and scope to the intended package and data files.
Keep known models without contracts visible, and classify/hash only reviewed
files. Keep review_pending true until human review of model boundaries and links.
Run mceg check, mceg explain and mceg coverage . from the provider root; explain
UNKNOWN results and coverage gaps. Link the records from the provider's docs.
Report changed files, actual checks, remaining gaps and required human review.
```

Review the generated diff using the manual workflow below. A readable draft or
successful structural check alone does not complete source or scientific review.

## Manually

Read the implementation, coefficient data, docs and relevant tests. Choose a
model boundary, including units, conventions and model options; check for existing
contracts and working-tree changes before creating records. The
[provider workflow](provider_onboarding.md) gives detailed review examples.

`mceg init` creates one editable v0.2 contract and registers a pending model in
the provider's inventory. It parses the local Python definition without importing
the provider or executing numerical tests. Replace the example ID, path, symbol
and settings with your model's choices:

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

### Initial records

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

### Model choices

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

### Review and verify

Edit the contract's `TODO` fields to describe the model, assumptions, units,
numerical restrictions and scientific scope. Record the sources actually
inspected and what remains unchecked. Run relevant provider tests separately;
retain their command, environment, implementation revision, outcomes and source
and artifact hashes before writing a scoped numerical Assessment. Leave tests
not executed as `not_run`, unavailable scientific support as `unknown`, and
remaining work as concrete Follow-ups. See the [v0.2 records](v02.md) and
[provider workflow](provider_onboarding.md) for the evidence fields.

Edit `mceg/models.yaml` to set the intended `scope` and `source_roots`, for example
`source_roots: [src/mypkg]`, including any separate coefficient-data directories.
Add known models without contracts with `contracts: []`. For each reviewed file,
record its `model` or `support` role, reason and SHA-256 as described in the
[inventory guide](coverage.md); leave unreviewed files visible. Clear a model's
`review_pending` only after human review of its boundary, bindings and contract
links. Repeat `init` for additional model IDs as needed.

From the provider root, with the MCEG environment active:

```bash
mceg check mceg/contracts/mypkg.water.power_law.yaml
mceg explain mceg/contracts/mypkg.water.power_law.yaml --evidence implementation
mceg coverage .
```

An untouched draft passes structural validation while source/evidence review
remains unknown. `check` can exit **0** with `UNKNOWN` results and does not run
numerical tests. Coverage reports `unreviewed_model` and missing file reviews;
exit code **1** is expected while gaps remain. Fix invalid records and report
remaining gaps without removing models or inventing evidence to obtain a pass.
Completing inventory review does not establish physical support or complete the
contract's evidence tasks. For a recorded Assessment, use
`mceg check CONTRACT --assessment ID --root .` to audit its selected source and
artifact hashes.

Review and save the inventory, contracts and referenced evidence artifacts
together, and link them from the provider's documentation. Initial adoption is
useful even with explicit unresolved scientific questions; describe the reviewed
scope and next steps so another maintainer or LLM can continue.

### File handling

Existing contracts are never overwritten. Inventory updates append to its root
lists while retaining prior records, review pins and comments. Direct block/flow
YAML lists and JSON-formatted inventories are supported; aliased or merged root
lists that need modification must first be made explicit. Inputs and generated
records are validated before writing. Inventory replacement is atomic, and a
failed inventory update removes the newly created contract.

`init` exits **0** when it creates the draft, and **2** for input or write errors.
The separate coverage result describes remaining work. Run `mceg init -h` for
the complete CLI options.

## Optional distribution and documentation

Repository contracts are enough for local checks. To enable
`mceg explain --package YOUR_DISTRIBUTION`, additionally bundle a
[package evidence catalog](package_evidence.md) and its referenced records in the
distribution. `init` does not create that catalog. For browsable contract pages,
follow the [HTML guide](html.md) to add `mceg/docs.yaml` and integrate generation
with the provider's documentation build.
