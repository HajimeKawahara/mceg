# Record a model choice

Experimental schema `"0.4"` adds **Decision** records: which option a reviewer
selected, why, and what would make them reconsider. Records stay in the provider
repository. MCEG reads them without importing the provider or choosing a model.

Evidence, Assessment and Decision answer different questions:

| Record | Question | Source-selection example |
| --- | --- | --- |
| Evidence | What was inspected or measured? | A source table and a comparison with the earlier data |
| Assessment | What does that evidence support, for this target and context? | Complete high-temperature support remains `unknown` |
| Decision | Which option will we use, and why? | Adopt the reviewed candidate with stated limitations |

For example, [ExoGibbs's C2H review](https://github.com/HajimeKawahara/exogibbs/blob/main/documents/presets/curated_c2h.rst)
selected NASA thermal functions and an ATcT
energy estimate while retaining gaps in high-temperature validation. ExoEOS's
oxygen [review](https://github.com/HajimeKawahara/exoeos/blob/9ed2c72c58ad45003fce11141a32ce9b9ecbeaba/results/mceg/20261029_badro_default/decision.json)
provisionally selected `epsilon_OO=-1873/T` while author intent and
physical accuracy remained separate questions. These are useful patterns for a
Decision; recording one does not establish that the implementation was changed
or that its predictions are accurate. The corresponding implementation and
validation Claims still need their own Evidence and Assessments.

## What a Decision contains

The executable definition is [schema_v04.py](../../src/mceg/schema_v04.py).
`ContractV04` extends v0.3 with `decisions`, which defaults to an empty list.

| Field | Meaning |
| --- | --- |
| `id`, `revision` | Exact identity of this authored choice |
| `question`, `scope` | What is being decided and where the choice applies |
| `options` | Alternatives, each with an `id` and `description` |
| `selected` | The ID of one recorded option |
| `reasons` | Nonempty explanation of the choice |
| `basis` | Evidence or Assessment references, each with `kind`, `id`, `sha256` |
| `limitations` | Remaining uncertainty; an empty list means none was recorded |
| `reconsider_when` | Conditions for revisiting the choice, written as text |
| `subject`, `context` | Optional links to the implementation snapshot and review conditions |
| `supersedes` | Optional `{id, revision}` of an earlier Decision retained in this contract |

`basis`, `limitations` and `reconsider_when` default to empty lists. A choice can
have an empty basis or cite an `unknown` Assessment. MCEG preserves these states
instead of requiring a scientific claim to become supported before a reviewer
can make a provisional choice. `reconsider_when` is not executable and creates
no FollowUp automatically.

Option IDs are local to one Decision revision. The selected option must exist;
basis, Subject, Context and supersession references must resolve. Duplicate
Decision identities and supersession cycles are rejected. The schema does not
rank alternatives, resolve competing choices or infer the current choice from
dates, order or revision names.

## Preserve what the reviewer used

A basis pin hashes the referenced record **and its declared local dependencies**.
For an Assessment this includes its target Claim or Condition, Subject, Context,
Evidence ancestry, and referenced equation and binding definitions. An Evidence
basis includes its recorded provenance ancestry and any linked Subject/Context.
This catches a changed premise even when the top-level Assessment text stays the
same. Unrelated records do not change the pin.

Use `decision_basis_digest(contract, kind, record_id)` from `mceg.schema_v04` when
authoring a new record. It identifies recorded content, not the truth of a source
or the current bytes of an external file. Existing pins are never renewed during
validation, checking or documentation generation.

`mceg check` reports matching recorded basis, missing basis, or changed basis.
A changed pin leaves the historical choice intact and calls for review; it does
not switch the chosen option. A matching pin does not turn an `unknown`
Assessment into `supported`. Record a new Decision revision after a new review,
retaining the old premises under distinct record IDs when they have changed.

## Read the choices

Try the [C2H](../../examples/decisions/c2h.yaml) and
[oxygen coefficient](../../examples/decisions/oxygen.yaml) examples:

```bash
mceg check examples/decisions/c2h.yaml --decision c2h_thermochemistry
mceg explain examples/decisions/c2h.yaml --decision c2h_thermochemistry --investigation
mceg graph examples/decisions/c2h.yaml examples/decisions/oxygen.yaml
```

Select a Decision with `--decision ID` in `mceg check` or `mceg explain`.
`--decision-revision REV` selects one exact revision; without it, all retained
revisions of that ID are shown. `mceg explain --investigation` also follows the
selected Decision's basis. No revision is chosen as the latest automatically.
`--root` remains an Assessment-only option for existing implementation-file
checks; Decision basis checks compare recorded dependency content without
reading or executing provider files.

[Graph JSON](graph.md) exports Decisions, their options, basis pins and explicit
supersession. Generated [Sphinx documentation](html.md) separates the chosen
option, reasons, cited Assessment outcomes, remaining limitations and review
conditions. It shows changed basis identities without rewriting them.

The examples accompanying this feature are illustrative transcriptions for
trying the format. They do not adopt new production data or replace the original
ExoGibbs or ExoEOS review records.

Existing v0.1–v0.3 contracts keep their meanings. They do not accept Decision
fields; select `schema_version: "0.4"` explicitly to use this format. Existing
provider decision JSON files remain readable as Evidence artifacts and are not
automatically converted or treated as scientific support.
