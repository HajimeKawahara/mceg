# MCEG for MCEG

This is a small, repository-only self-description: three design principles and
one existing feature, `src/mceg/validator.py:read_document`. The `model` record
describes software behavior here, not a physical model. The inventory covers
only that feature's defining file, not the whole package or the example contracts.

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

## Inspect the pilot

From the repository root, using the development environment described in the
[main README](../README.md#install):

```bash
python -m mceg check mceg/contracts/mceg.read_document.yaml --assessment regression_review --root .
python -m mceg explain mceg/contracts/mceg.read_document.yaml --assessment regression_review --investigation
python -m mceg coverage .
python -m mceg graph mceg/contracts/mceg.read_document.yaml --provider mceg > /tmp/mceg-self-graph.json
```

The [contract](contracts/mceg.read_document.yaml) links the principles, inspected
implementation and seven executed regression cases. It reuses schema 0.2's
`numerical_verification` / `numerical_test` types for software regression checks;
no physical applicability or general parser security is asserted. The
[receipt](evidence/read_document/receipt.json) retains the exact command and
selected file hashes, and [pytest output](evidence/read_document/pytest.txt)
retains the result. Reading these records does not rerun the tests.

Coverage deliberately exits **1** with `unreviewed_model` until a maintainer
reviews the feature boundary and contract links. Follow the recorded
`review_boundary` task before clearing `review_pending` in [models.yaml](models.yaml).
The inspected source file also contains schema dispatch, which is outside this
pilot; its file hash is a change detector, not a claim to cover every function.

After implementation or test changes, inspect the changes, rerun the receipt's
command and retain a new receipt and scoped assessment. Preserve earlier evidence
when its subject changes; updating a hash alone does not renew support. The
selected pins are not a complete dependency or environment lock.
