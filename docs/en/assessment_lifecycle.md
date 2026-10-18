# Assessment lifecycle trial toward v0.2

This example tests how a new execution can supply evidence for a changed
environment while earlier Evidence and Assessments retain their identities.
It also tests lossless extraction of v0.1 declarations and one source-adoption
dependency. All formats remain example-specific. The package and core schema
are still v0.1; this is not a released v0.2 reader or a general inference rule.

## Actual executions

The unchanged ExoGibbs validator was run at
`dfb3a9e5ede8bad6e916506a51fa35afa392c764`, the develop-based #285 branch.
Its scientific inputs and validator match the merged #284 archive. Each run
covers both networks at all seven temperatures and five pressures, with the
normalized Asplund 2021 budget, CPU float64 and `epsilon_crit=1e-13`.

| Setting | Baseline run | Changed environment |
| --- | --- | --- |
| Python | 3.12.7 | 3.12.7 |
| JAX / jaxlib | 0.6.2 / 0.6.2 | 0.10.2 / 0.10.2 |
| NumPy / SciPy | 2.1.0 / 1.14.1 | 2.1.0 / 1.14.1 |
| ml_dtypes / opt_einsum | 0.5.0 / 3.4.0 | 0.5.0 / 3.4.0 |
| Equilibrium / FastChem cases | 70 / 70 passed | 70 / 70 passed |
| Maximum all-species FastChem difference | 1.221e-5 dex | 1.221e-5 dex |
| Maximum ExoGibbs element residual | 2.811e-6 | 2.811e-6 |
| Maximum ExoGibbs charge residual | 6.617e-14 | 6.286e-14 |
| Maximum ExoGibbs mass-action residual | 1.378e-12 | 1.421e-12 |

Only JAX and jaxlib differ among the recorded package versions. Both runs use
the same newly built FastChem v4.0.3 executable, from the clean pinned revision
`ae67cbd559bc64a3233a1cee6030b8e6b50520de`. Its binary hash differs from the
older provider archive. The original archive also used Python 3.12.3 and
JAX 0.11.2; it is not the baseline for a controlled JAX-only comparison here.
Build identity and the review policy are recorded in
[`rerun_review.json`](../../examples/curated_gas/rerun_review.json).

The source data bytes are identical. Evaluating and normalizing them through
the two JAX versions produces small floating-point differences: at most
5.684e-14 in `h` and 5.421e-20 in the normalized elemental budget. The stored
arrays retain these differences; no byte-identical numerical output is assumed.

The independent solver receives the same constants and composition. Its
agreement checks numerical solving; it does not independently validate those
thermochemical constants or the physical accuracy of the mixture. The recorded
interval between samples and other compositions remain unverified.

Each [run directory](../../examples/curated_gas/runs) retains the untouched
provider receipt, CSVs, compressed arrays, thermal checks and execution log.
`execution.json` additionally records the observed environment, command, process
exit code, selected input hashes, comparator hash and receipt hash. The optional
capture script runs the provider's existing validator without importing it into
MCEG. It refuses to overwrite a directory. GPU-plugin discovery warnings appear
in the logs; the observed backend was CPU and both processes exited successfully.

## What changes in an Assessment

The saved [lifecycle report](../../examples/curated_gas/lifecycle.json) contains:

| Situation | Numerical Evidence | Assessment for the target environment |
| --- | --- | --- |
| JAX 0.6.2 execution, assessed for that environment | passed | supported |
| The same execution, assessed for JAX 0.10.2 | passed, with the same identity | unknown: environment not covered |
| New JAX 0.10.2 execution, assessed for that environment | a separately identified passed execution | supported |

The second row models the knowledge available before the new run; it does not
execute anything. The third row uses actual new evidence. Both supported
Assessments coexist, bound to their own evidence and environment. Neither
replaces the original provider declaration or historical `passed` result.

The reviewed evaluator checks artifact integrity, the enumerated 70-point grid,
environment consistency, the unchanged validation procedure and the CSV gates.
A measured gate failure records failed numerical Evidence and unknown support,
with `numerical_comparison_failed` as a reason. Missing coverage is unknown
Evidence with a different reason. A nonzero process exit is `execution_failed`;
it does not by itself identify a numerical contradiction. Duplicate samples,
nonfinite residuals, or altered archived artifacts are errors. The example adds
no new Claim status for refutation or conflict resolution.

## Minimal identity and migration findings

| Record | Required distinction demonstrated here |
| --- | --- |
| Claim | Proposition, kind, scope, and an explicit revision; no mutable support status |
| Evaluated subject | Model identity and selected code, coefficient-data, abundance and adapter hashes |
| Evidence | Identified execution, observed environment, sampled conditions, procedure and outcome |
| Assessment | Claim revision, evaluated subject, context, evidence IDs, method/review identity, status and reasons |

Changing JAX changes the execution context. Changing coefficients changes the
evaluated model instance. Changing the abundance tolerance or proposition
requires a Claim revision. These are different changes even if a convenient
model name stays the same. Hashes conservatively identify bytes; they do not
establish semantic equivalence of implementations. The full provider revision
is preserved in execution provenance. Current-file comparison is limited to
the selected manifest and is not an exhaustive transitive dependency audit.

[`migrate.py`](../../examples/curated_gas/migrate.py) removes each Claim's
`status` and evaluative `evidence` links into a separate imported Assessment.
It preserves the original contract hash, implementation identity, all Claim
text and scopes, Evidence IDs, provenance and execution outcomes. Structured
conditions remain absent when the old declaration did not supply them.
Reconstructing the v0.1 data gives exactly the original validated content for:

- H2 solubility: 3 Claims and 18 Evidence records.
- Curated gas: 5 Claims and 7 Evidence records.

This extraction deliberately preserves old text that embeds outcomes. The
separate [`claim_revision.json`](../../examples/curated_gas/claim_revision.json)
explicitly revises the curated equilibrium proposition and enumerates the
inspected numerical criteria. Imported support stays attached to the old Claim
revision; new executions assess the revised proposition. H2's missing physical
accuracy criteria are not invented. Its marginal range assessments remain
separate from evidence support and never promote the physical-accuracy Claim.

The migration output uses `format: assessment_migration_draft_v1`, not
`schema_version: "0.2"`. Existing v0.1 readers reject it. Before a core v0.2
release, version dispatch and the final serialized structure still need to be
specified; this trial supplies preservation and coexistence fixtures for that
decision. No provider contract is silently migrated.

## One dependency path, two affected judgments

The inspected builder reads
`examples/comparisons/data/major_molecule_adoption.json`, incorporates decisions
into `src/exogibbs/data/curated/gas_v1.json`, and records the source hash there.
The numerical receipt in turn identifies that packaged data by hash.

The trial uses temporary copies of these actual files. First it changes the H2O
adoption status to `retain_provisionally`; then it changes one packaged NASA9
coefficient. These are synthetic mutations for bookkeeping, not proposed source
choices, physical studies or executions of an altered model.

| Mutation | Source alignment | Numerical support for the current packaged data |
| --- | --- | --- |
| None | recorded source hash agrees | supported by the fresh run |
| Adoption record changes, packaged data unchanged | review required | existing numerical evidence still applies to the fixed data |
| Packaged coefficient also changes | review required | unknown; separate numerical evidence required |

Old numerical results stay passed in all three cases. Updating an adoption
record does not retroactively make the old execution fail, and a numerical pass
does not justify adopting a source. If a source review leads to rebuilt data,
review the changed model and rerun its checks. Updating hashes alone supplies
no execution evidence. `consistent` here means hash agreement only.

This is one manually inspected dependency path. Cross-contract paths in v0.1
remain locators; no generic support propagation, automatic source ranking or
counting of independent evidence has been introduced.

## Reproduce

Reassess the stored executions, reproduce the two migrations and run the
dependency probe without importing ExoGibbs, NumPy or JAX:

```bash
PYTHONPATH=src python examples/curated_gas/lifecycle.py \
  --exogibbs /path/to/reviewed/exogibbs --output /tmp/lifecycle.json
PYTHONPATH=src python examples/curated_gas/migrate.py \
  contracts/h2_solubility.yaml --output /tmp/h2-migration.json
```

To obtain new numerical evidence, prepare two Python environments with the
versions above and a reviewed FastChem build. The controlled run here used
the same base Python packages, with JAX/jaxlib 0.10.2 supplied from an isolated
environment. No global environment was modified. Run once for each Python,
always into a new directory:

```bash
python examples/curated_gas/rerun.py \
  --exogibbs /path/to/reviewed/exogibbs \
  --python /path/to/environment/bin/python \
  --fastchem /path/to/reviewed/fastchem --output-dir /tmp/new-curated-run
PYTHONPATH=src python examples/curated_gas/reassess.py \
  --exogibbs /path/to/reviewed/exogibbs \
  --run /tmp/new-curated-run --output /tmp/new-assessment.json
```

A different validator, provider execution revision, selected scientific input,
comparator binary or Claim criterion requires a new explicit review. The
artifact hashes are bookkeeping records, not authenticated attestations.
Ordinary MCEG tests verify the saved archives and synthetic failure controls
offline; they do not rerun the numerical solvers.
