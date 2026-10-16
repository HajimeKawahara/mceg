# Provider adoption trials using frozen v0.1

These three experiments add examples and review tools without changing the
v0.1 schema, public API, package dependencies, or either provider checkout.
They test a second connection, provider-local placement, and implementation
updates before adopting contracts in ExoEOS or ExoGibbs.

The case, execution receipts and workflow reports are example-specific formats.
Only the model contracts use the frozen MCEG schema. No new applicability
engine, source locator standard, or automatic evidence invalidation is implied.

## 1. A mixture connection with explicit approximation policies

The [case](../../examples/virial_mixture/case.yaml) uses the actual ExoGibbs
`m2_gas_eos.build_gas_eos` and `with_gas_residual` functions to connect the
ExoEOS full-catalog major-gas provider to an ideal gas scalar. This is distinct
from the public pure-species adapter used by the H2 solubility example.

Inputs are 1500 and 2173.15 K, 270 bar, and ordered amounts
`[0.75, 0.17, 0.06, 0.012, 0.008]` mol for `[H2, He1, H2O1, O2, Mg1]`.
The synthetic composition follows the upstream provider tests. Standard
potentials are explicitly zero with a 1 bar standard pressure. This tests a
fixed-composition callback, not chemical abundances, parcel equilibrium or a
planetary atmosphere. The constant H2-He coefficient is the declared sensitivity
choice of 10 cm3/mol. Every pair involving O2 or Mg1 is explicitly zero.

The [provider contract](../../examples/virial_mixture/provider.yaml) and
[connection contract](../../examples/virial_mixture/adapter.yaml) separate the
recipe's scientific assumptions from the adapter's numerical responsibilities.
Their shared run receipt counts as one execution, not independent evidence twice.

### Numerical results

The [saved execution](../../examples/virial_mixture/result.json) passed 35
checks using CPU and binary64. These compare density and pressure with scalar
virial expressions, callback energy and chemical potentials with analytic
values, the independent amount derivative with chemical potentials, and the
two coefficient policies with their declared behavior.

| Temperature (K) | Water-cross policy | Z | ln(phi) for each of O2 and Mg1 |
| --- | --- | ---: | ---: |
| 1500 | extrapolate | 1.0271722732 | -0.0268096610 |
| 1500 | hold_2000 | 1.0271722732 | -0.0268096610 |
| 2173.15 | extrapolate | 1.0179722652 | -0.0178126733 |
| 2173.15 | hold_2000 | 1.0179837779 | -0.0178239828 |

At fixed T/P, `ln(phi_i) = 2 rho (B x)_i - ln(Z)`. A zero coefficient row
therefore leaves `-ln(Z)`. Dropping a trace species from the denominator or
setting its correction to zero would implement a different scalar model.

### Manual applicability findings

| Question | Assessment | Meaning |
| --- | --- | --- |
| Provider's 1000-3000 K interval | Within recorded interval | Numerical evaluation conditions only |
| Water cross coefficients at 1500 K | Within recorded intervals | H2-H2O: 200-2000 K; He-H2O: 100-2000 K |
| Water cross coefficients at 2173.15 K, extrapolate | Extrapolation | Analytic continuation above the reported upper temperature |
| Water cross coefficients at 2173.15 K, hold_2000 | Extrapolation | Applying a boundary coefficient at a higher physical temperature |
| He-He table subset | Within recorded interval | Theoretical table coverage, with no interpolation-error bound supplied here |
| Physical errors of pure pairs, H2-He input, zero pairs and higher virials | Unknown | No new empirical error bound |
| Combined chemical-potential accuracy | Unknown | Numerical consistency is not physical validation |

`hold_2000` holds only H2-H2O and He-H2O. It does not change the gas temperature,
extend experimental coverage, or remove the omitted higher virials. The small
difference between the two outputs is a policy sensitivity, not an uncertainty
interval or evidence that either policy is accurate.

These source intervals come from the inspected upstream
`gas_virial_sources.json` ledger. The ledger contains original-paper identifiers,
PDF hashes and inspection reports, but this trial did not reacquire or inspect
those original PDFs. Its MCEG evidence therefore remains secondary, and its
provenance trace remains incomplete. This preserves the distinction learned
from the [H2 primary-source audit](h2_primary_audit.md).

### Replay

Use the same source revisions as the baseline: ExoEOS
`d7681db4393fd85904846b083013230d81d45d4e` and ExoGibbs
`6b4cef45d2a6f1eb1462afd6cb6d3f1c77dba8ea`. The runner requires clean tracked
files and refuses changed case inputs before importing optional providers.

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src:../exoeos/src:../exogibbs/src \
JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 \
python examples/virial_mixture/run.py --output /tmp/mceg-virial-result.json
```

JAX, NumPy, SciPy and the provider checkouts are optional replay dependencies.
The receipt preserves versions, source revisions, selected file hashes and
input/runner/contract hashes. It is not a complete environment archive. The
existing upstream tests were read, but are marked `not_run` in these new records;
the actual execution evidence is this 35-check replay.

## 2. Provider-local contract placement

The [workflow runner](../../examples/provider_workflow/run.py) reads pinned Git
objects from the providers and creates partial source snapshots under a new
output directory. It copies all five baseline contracts into:

```text
providers/exoeos/mceg/contracts/       # four EOS contracts
providers/exogibbs/mceg/contracts/     # one solubility contract
providers/<owner>/mceg/evidence/       # copied MCEG audit documents
```

Implementation and test files retain their original paths under each provider
root. Own-repository GitHub source URLs become repository-relative file locators.
MCEG audit-document locators move to `mceg/evidence/docs/en/...`. The runner
checks each recognized file locator against an explicitly supplied repository
root, independently of the working directory and the YAML's location.

The [saved report](../../examples/provider_workflow/result.json) records two outcomes:

1. Simply copying the H2 contract passes MCEG structural validation but leaves
   `docs/en/h2_solubility.md#verification` missing at the new root.
2. After localizing references and copying the documents, all five contracts
   pass structural validation and their recognized local evidence files exist.
   The report records the original/exported contract hashes and file hashes.

This deliberately small resolver recognizes the baseline's `src/`, `tests/`,
`documents/`, `docs/`, `examples/` and `mceg/` prefixes. `sources` also contains
plain bibliographic citations; those are reported as opaque and unchecked.
Remote URLs, fragments such as line ranges or Markdown anchors, Python entry
points, and links inside copied Markdown are also unchecked. File existence
does not mean that a citation is correct or that the relevant passage was read.
The snapshots are not installable providers or complete offline archives.

Run from the MCEG root, choosing a directory that does not already exist:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python examples/provider_workflow/run.py --output-dir /tmp/mceg-provider-trial
```

`--exoeos` and `--exogibbs` accept alternative checkout locations. The recorded
trial was executed with `/tmp` as the current directory, using absolute script
and import paths. It needs Git and MCEG, but never imports the providers or JAX.
The sibling checkouts are only read; generated files stay in the output directory.

## 3. An implementation update without inherited passing evidence

The same runner makes a separate `candidate/` copy and changes one H2 expression
from `exp(-11.403 - 0.76 * P)` to `exp(-11.303 - 0.76 * P)`. This arbitrary change
is a synthetic review exercise, not a discovered error, a proposed correction,
or a provider release. No candidate calculation is executed.

The candidate's revision is `synthetic-sha256:<source digest>`, not a Git commit.
The parent contract and source remain byte-for-byte unchanged. The saved report
identifies the changed evidence file and compares both source digests.

A negative control changes only the implementation revision in the old contract.
The core validator accepts that record while its old numerical claim remains
`supported`. This confirms that v0.1 does not establish evidence freshness.
The separate [candidate template](../../examples/provider_workflow/candidate.yaml)
records a deliberately reviewed alternative:

| Record | Parent | Candidate | Review reason |
| --- | --- | --- | --- |
| Fixed-pressure linearity | supported | supported | The algebraic form remains linear in fugacity |
| Numerical formula checks | supported / passed | unknown / not_run | The old execution did not test the candidate |
| Historical numerical evidence | passed | passed, scoped to parent | A source change does not erase a historical result |
| Formula comparison with Seo Eq. 6 | consistent | discrepancy | The deliberate constant change differs from the previously inspected expression |
| Physical accuracy | unknown | unknown | No empirical validation was added |
| Calibration domains | Original source-scoped records | unknown for candidate | The altered law cannot inherit calibration coverage automatically |

The candidate template is a manual review, not a claim-impact algorithm. Its
historical passing evidence does not support the current numerical claim. The
candidate's trace exposes the deliberate discrepancy without calling it a new
scientific discovery. The unchanged parent remains under `providers/exogibbs/`.

For a real update, preserve the old receipt, inspect the implementation and
parameter diff, identify affected claims and source comparisons, review scientific
scope, rerun appropriate tests, and save a new versioned record. A failing test
requires recording the failure; `not_run` is only for an unexecuted test. Do not
change a reference value merely to restore a pass.

## What this establishes before adoption

The frozen schema can record these distinctions without new fields. New
operational conventions are still needed for repository roots, immutable audit
artifacts, configured-model identity and review after a source change. A contract
commit is distinct from the revision of the implementation it describes; trying
to put a commit's own hash in that same commit creates a circular requirement.

Limited provider-side adoption can start with one reviewed contract per package
and an explicit reference/review convention. No schema expansion is required
for that pilot. General source resolution, automatic affected-claim discovery,
and cross-package applicability decisions remain deferred.

Validation for this work: **68 MCEG tests passed**, eight YAML contracts/templates
passed structural validation, the mixture replay passed **35 numerical checks**,
and the separate placement/revision trial completed. The tests do not require
either provider or JAX. The original five contracts, H2 example and frozen core
remain unchanged. Physical validation of the new mixture remains unknown.
