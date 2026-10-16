# Provider-owned H2 contract pilot

The H2 EOS and solubility contracts now have provider-owned pilot copies:

| Provider | Contract | Audited implementation |
| --- | --- | --- |
| ExoEOS | `mceg/contracts/zhang_duan_h2.yaml` | `d7681db4393fd85904846b083013230d81d45d4e` on main |
| ExoGibbs | `mceg/contracts/h2_solubility.yaml` | `9990fdc2f4bd8423bdfc0cefdc1fbb8325cfe55f` on develop |

The providers retain their scientific implementations and dependencies. Each
adds a contract, a short guide, a fresh scoped test receipt and JUnit artifact
under `results/mceg/`, and a standard-library-only test for selected file hashes.
The provider suites do not import MCEG. Structural validation remains an optional
operation in the independent MCEG environment. Contracts are checkout metadata;
this pilot does not define discovery from installed wheels.

## Scope and source review

ExoEOS main matches the original audited revision. ExoGibbs develop has advanced:
its adapter gained multiphase functions, while the pure-component callback and
the H2 solubility function are unchanged. The new provider receipts record actual
executions: one published-parameter factory test in ExoEOS and eight selected
formula, broadcast and fugacity/pressure checks in ExoGibbs. The latter records
its audited ExoEOS dependency as well.

Historical evidence remains explicitly scoped to the old revision. Its original
MCEG audit uses a commit-pinned URL, so relocating the contract does not create
an accidental dependency on an MCEG checkout. The current numerical claims link
to a separate `provider_test_run` evidence entry. Original source inspections,
calibration caveats and physical `unknown` claims are preserved.

Local evidence paths resolve from the provider repository root. The
[consumer runner](../../examples/provider_h2/run.py) checks the recognized local
files, including the provider's saved numerical artifacts. It reports remote
URLs, bibliography and fragments as unchecked using the limited resolver from
the [placement trial](provider_trials.md). File existence is not inspection.

## Replay from the consumer

Use the two provider branches containing these pilot files and an environment
with their optional calculation dependencies. From an MCEG checkout:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 \
python examples/provider_h2/run.py \
  --exoeos /path/to/exoeos \
  --exogibbs /path/to/exogibbs \
  --output /tmp/provider-h2-result.json
```

Checkout arguments are explicit; they need not be siblings of MCEG. The runner
verifies the actual imported module locations. It requires the audited Git
objects to be available, so a shallow checkout without those objects is
insufficient for this example.

The unchanged [original case](../../examples/h2_solubility/case.yaml) supplies
1700 K, 7500 bar and its nine manual assessments. Before reusing them, the runner
requires the provider contracts' scientific declarations to match the baseline;
changed declarations require a new manual assessment. This equality guard does
not prove that the declarations or assessments are scientifically correct.
The output resolves each assessment's evidence IDs to the owning provider.

The [saved replay](../../examples/provider_h2/result.json) records both provider
contract hashes, execution-receipt hashes, audited source revisions, actual
checkout revisions and selected source hashes. Its four numerical checks pass,
and the outputs reproduce the original H2 calculation: phi = 2.2561116480,
fugacity = 16920.83736 bar and dissolved mole fraction = 0.1068105175. The nine
manual classifications remain unchanged. The combined physical accuracy is
still unknown.

## Implementation revision versus contract publication

Adding a contract changes repository HEAD even when the model code does not
change. The saved replay is made after the provider commits, so each
`checkout_revision` differs from its `audited_revision`. The runner accepts that
state only when selected files match both the receipt hashes and the Git objects
at the audited revision. Merely changing hashes in a receipt cannot assign new
bytes to an old audited revision.

This checks selected file identity, not the entire transitive implementation or
environment. The recorded dependency versions and explicit scope still matter.
It does not infer which claims need revision when a file changes. A source
change stops the replay for review; a new audit and receipt are then required.
The provider regression tests use the local hashes and do not require Git or
MCEG at test time.

The original MCEG contracts and H2 result remain frozen reference examples.
The provider copies own subsequent model-contract maintenance. A consumer case
and a model contract have separate owners and should not silently overwrite
each other's scientific conclusions. The new receipt format and identity guard
remain example tools, with no changes to the v0.1 schema or public API.
