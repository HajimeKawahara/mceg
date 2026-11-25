# MCEG for MCEG

These optional, repository-only records describe two selected software features:
local document loading and mathematical model assembly/export. Here a `model`
record describes software behavior, not a physical model. The inventory covers
selected files and functions; it is not package-wide verification.

## Design principles

1. **Keep execution independent of evidence records.** A provider runs without
   MCEG installed. For MCEG itself, this means imports, CLI startup and document
   loading do not require this directory or a successful self-check. These files
   are optional development records, not a runtime gate or a new dependency.
2. **Separate structure from scientific support.** Parsing and schema validation
   do not establish scientific truth. Passing software tests supports only their
   stated behavior and scope.
3. **Make evidence inspectable and work resumable.** Record the implementation,
   test command, environment, results and file hashes; keep limitations and
   concrete review tasks visible to humans and later assistants.

These are design commitments, not three automatically verified guarantees.

## Recorded features

| Contract | What the recorded tests check | What they do not establish |
| --- | --- | --- |
| [Document loading](contracts/mceg.read_document.yaml) | Seven existing cases reject duplicate or unsafe inputs and retain a JSON exponent value. | Exhaustive parser security, input limits or all schema behavior. |
| [Mathematical models](contracts/mceg.mathematical_model.yaml) | Explicit quantity references and mappings, incidence export, definition snapshots, and stale Assessment/Decision/Use dependencies. | Physical completeness, a unique solution, algebraic equivalence, or general MCEG correctness. |

The mathematical self-model records software quantities: a validated record
catalog, the selected model ID/revision, its incidence graph, its definition
closure, and the closure digest. Its relations describe how these objects are
connected. Equation Bindings point to `model_graph`, `mathematical_model_records`
and `mathematical_model_digest`. Finite regression results support the separate
software Claim; merely declaring this graph does not validate its implementation.

## Inspect the records

From the repository root, using the development environment described in the
[main README](../README.md#install):

```bash
python -m mceg check mceg/contracts/mceg.read_document.yaml --assessment regression_review_20261126 --root .
python -m mceg check mceg/contracts/mceg.mathematical_model.yaml --assessment mathematical_model_review --root .
python -m mceg explain mceg/contracts/mceg.mathematical_model.yaml --assessment mathematical_model_review --investigation
python -m mceg model mceg/contracts/mceg.mathematical_model.yaml --model declared_model_identity --format mermaid
python -m mceg coverage .
```

The original [document-loading receipt](evidence/read_document/receipt.json) and
assessment are preserved. Adding schema 0.5 changed `validator.py`, so the same
seven tests were run again and recorded under a new Subject, Evidence and
Assessment, with a [new receipt](evidence/read_document_20261126/receipt.json).
The selected loader bodies were also compared against the original revision.
The historical assessment still refers to its historical Subject; checking that
Subject against today's source tree reports the changed file rather than
silently refreshing its hash or changing its stored support status.

The [mathematical-model receipt](evidence/mathematical_model_20261126/receipt.json)
retains the actual command, environment, source revision, selected source/test
hashes and captured test output. Reading either contract or receipt does not
rerun tests. The finite software assessments use the existing
`numerical_verification` / `numerical_test` record types; they make no physical
applicability claim.

Coverage deliberately reports **two `unreviewed_model` items** and exits 1 until
a maintainer reviews both feature boundaries and contract links. Follow each
recorded `review_boundary` task before clearing `review_pending` in
[models.yaml](models.yaml). No runtime action is gated on that review. File pins
are change detectors, not proof that every function in each file is covered.

After implementation or test changes, inspect the changes, rerun the receipt's
command and retain a new receipt and scoped assessment. Preserve earlier evidence
when its subject changes; updating a hash alone does not renew support. The
selected pins are not a complete dependency or environment lock.
