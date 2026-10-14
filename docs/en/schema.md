# Experimental v0.1 YAML schema

The executable definition is [schema.py](../../src/mceg/schema.py).
The [model contracts](../../contracts) are complete examples.
There are no ExoFamily-specific fields or required scientific vocabularies.
The format and its documented semantics are frozen with package `0.1.0`;
see the [version policy](versioning.md) for compatibility and evidence updates.

## Fields

| Top-level field | Content |
| --- | --- |
| `schema_version` | The quoted string `"0.1"`; a numeric YAML value is rejected |
| `model` | `id`, `name`, `description`, and `implementation` |
| `assumptions` | List of `{statement, evidence}` records |
| `domains` | Nonempty list of domain records |
| `claims` | Nonempty list of claim records |
| `evidence` | Nonempty list of evidence records |
| `limitations` | List of `{statement, evidence}` records |

All top-level fields are required. `assumptions` and `limitations` may be empty;
an empty list records no entries, not a guarantee that none exist. Every text
field must be a nonblank string. Unknown fields are rejected at every level,
and values are not coerced from numbers or booleans into text.

`implementation` has `repository`, `revision`, and a nonempty `entry_points`
list. These are descriptive strings; revisions need not be Git hashes and entry
points need not use Python syntax. The examples pin inspected Git revisions and
identify both the model class and shared evaluators. They are not automatically
resolved or compared with the installed software.

## Domains

Each domain has `kind`, `status`, `description`, `conditions`, and `evidence`:

- `kind`: `scientific_applicability` or `numerical_evaluation`.
- `status`: `documented` or `unknown`.
- `conditions`: a list of descriptive strings. A documented domain requires at
  least one; an unknown domain requires an empty list.
- `evidence`: one or more local evidence IDs giving the source or audit scope.

Several records of the same kind are permitted. For example, the virial contract
records a documented qualitative low-density restriction and an unknown
quantitative material/temperature/pressure range. `documented` means a condition
is stated in a source, not that MCEG has established its truth or completeness.
Numerical preconditions are not guarantees of finite or accurate arithmetic at
every floating-point input. No expression in `conditions` is executed.

## Claims

A claim has `id`, `statement`, `kind`, `status`, `scope`, and `evidence`.

| `kind` | Meaning | Evidence required when `status: supported` |
| --- | --- | --- |
| `theoretical` | A property of specified equations under stated assumptions | At least one `theory` item |
| `numerical_verification` | A scoped numerical comparison or implementation check | A `numerical_test` or `benchmark` with `result: passed` |
| `physical_validation` | Comparison with the physical system | At least one `experiment` or `observation` item |

`status` is `supported` or `unknown`. An unknown claim may have an empty evidence
list. A supported claim needs matching evidence as above. This is a **declared
evidence-category check**, not an assessment of correctness, relevance, strength,
or coverage. A theoretical identity and its finite-point numerical test are
separate claims with separate scopes. A literature citation alone cannot label a
physical-validation claim as supported: a specific measurement comparison would
need its own experiment/observation evidence record.

## Evidence and provenance

Each evidence item has `id`, `kind`, `summary`, `sources`, and `scope`.
Kinds are `implementation`, `theory`, `numerical_test`, `benchmark`, `experiment`,
`observation`, and `literature`. `sources` is a nonempty list of locators. Absolute
URLs may include a revision and line fragment. Relative locators in this
repository are relative to the **repository root**, optionally with a Markdown
anchor; they are identifiers, not paths relative to each YAML file.

Optional `provenance` records a scoped source `role`, `location`, `inspection`,
`note`, and `derived_from` links. Each link identifies local `evidence`, a manual
`comparison` (`not_checked`, `consistent`, or `discrepancy`), and a `note`.
See the [source-tracing guide](provenance.md) for enums and interpretation.
An absent provenance record remains unknown to the tracer; it is not a primary
source by default. Optional provenance is included in the frozen v0.1 format.

Numerical tests and benchmarks additionally require `result`: `passed`, `failed`,
`not_run`, or `unknown`. Other kinds omit `result` (or use null). `not_run` means
the cited test was identified but has no execution result supplied in that
record; `unknown` means the outcome is undetermined. Saved upstream results and
newly executed tests must describe their different provenance in `sources` and
`scope`. A source file containing assertions is not itself a successful run.

IDs must be unique across claims and evidence within one contract. Assumptions,
domains, claims, and limitations can reference only evidence IDs in that same
contract. Cross-contract edges are not implemented in the core schema. The
[H2 case](../../examples/h2_solubility/case.yaml) explores explicit references
in separate, manually reviewed example data; it is not a core contract format.

## Validator boundary

The loader rejects unsafe YAML tags, duplicate mapping keys (including overriding
merge keys), multiple documents, unknown fields, wrong types, missing fields,
duplicate IDs, dangling links, and the category/result mismatches above. It
also rejects duplicate/cyclic provenance links and completed comparisons whose
endpoints are not both declared inspected. A recorded discrepancy remains valid
data. `--trace EVIDENCE_ID` reports all recorded ancestors and audit gaps, without
promoting any scientific claim. The validator does
not fetch sources, execute tests, check revision existence, parse units or
conditions, reconcile contradictory evidence, or determine whether an asserted
claim follows from a cited source.

The implementation uses [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/)
for structural validation. An optional JSON Schema view can be generated without
maintaining a second schema file:

```bash
python -c 'import json; from mceg import Contract; print(json.dumps(Contract.model_json_schema(), indent=2))'
```

That JSON Schema represents fields and types; the Python validators for ID links
and category/result rules still require MCEG. Known representation gaps are
recorded in [design questions](design_questions.md).
