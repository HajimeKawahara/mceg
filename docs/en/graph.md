# Graph JSON API

Export recorded model, evidence, assessment and calculation relationships for
viewers, LLM tools and programmatic inspection. The Python API and CLI return the
same `mceg_graph_v1` representation. Documentation graphs use the same construction
logic, with labels and HTML links added by the documentation renderer.

## Export a graph

```bash
mceg graph contracts/h2_solubility.yaml
mceg graph examples/v02/h2_solubility.yaml --provider mceg
mceg graph --case examples/html/case.yaml > graph.json
mceg graph --package exogibbs
mceg graph --catalog path/to/mceg/index.json
```

The CLI writes JSON to stdout. Invalid inputs produce an error on stderr and
exit status 1 without partial JSON; argparse usage errors return 2. A successful
export returns 0, including when records contain unknown judgments or explicitly
unregistered components. Graph generation does not run scientific calculations.

```python
from mceg.graph import build_graph

snapshot = build_graph(
    paths=["examples/v02/h2_solubility.yaml"],
    cases=["examples/html/case.yaml"],
    provider="mceg",
    root="/path/to/mceg",
)

by_id = {node["id"]: node for node in snapshot["nodes"]}
for edge in snapshot["edges"]:
    if edge["type"] == "assesses":
        assessment = by_id[edge["source"]]["record"]
        target = by_id[edge["target"]]["record"]
        print(assessment["id"], target["id"], assessment["reasons"])
```

`build_graph(*, paths=(), provider="local", root=".", cases=(), package=None,
catalog=None)` returns a JSON-serializable dictionary. Supply sequences for
`paths` and `cases`; the CLI accepts multiple contract paths and repeated `--case`.
Paths resolve from `root`, including case paths. Absolute paths must be inside
that root; use `--root` when invoking the CLI elsewhere. The provider name is a
namespace for these local sources, defaulting to `local`.

Case provider roots resolve from each case file, and registered components keep
their declared provider namespaces. Local loading rejects path traversal and
symlinked files. A provider alias must identify the same root throughout a build.
Case hash pins, model IDs and selected Subject/Context/Assessment references use
the same validation as [documentation generation](html.md#select-a-calculation).

`package` and `catalog` are mutually exclusive and cannot be mixed with local
inputs or nondefault `root`/`provider`. Package discovery uses distribution
metadata without importing the provider. Catalog contracts and explicitly listed
artifacts retain the existing hash checks. Every catalog record is included;
model/species filtering and graph query commands are outside this first API.

## Graph structure

The output has five required fields:

| Field | Contents |
| --- | --- |
| `format` | `mceg_graph_v1`, versioned independently of contract schemas |
| `sources` | Input snapshots: `id`, `provider`, `path`, `sha256`, `kind`, `version` |
| `nodes` | Records: `id`, `type`, `label`, `ref`, `origin`, `record` |
| `edges` | Directed relationships: `id`, `type`, `source`, `target`, `origin`, `data` |
| `selections` | Explicit catalog-record and case-component selections |

Every edge endpoint is a node ID. Every `origin` contains a source ID and an
RFC 6901 JSON pointer into that source's parsed record. The empty pointer denotes
the document root. Pointers locate fields in YAML/JSON data, not text line numbers.
For example, `/assessments/0/claim` locates the declared target of an Assessment.

Source `kind` is `contract`, `case`, `manual_case` or `catalog`; `version` retains
the input schema/format identifier. Contract and case paths are relative to their
provider roots. For catalog inputs, contract paths are relative to the catalog's
directory and the catalog source path is its filename. Catalog sources also
include `record_version` and `distribution` (name/version for package lookup,
otherwise null). SHA-256 identifies source bytes, not scientific validity.

`record` preserves the parsed input fields, including schema defaults and nulls.
The Model node holds `model`, `assumptions`, `domains`, `limitations` and any
migration metadata. Other contract collections become individual nodes. The
source table holds Contract identity; there is no additional Contract node.
Method and Artifact records stay nested, as do Context samples inside Conditions.
A sample Context is not merged with a top-level Context of the same ID.

Node types are `model`, `claim`, `evidence`, `subject`, `context`, `condition`,
`assessment`, `follow_up`, `resolution`, `case`, `component`, `manual_case` and
`manual_assessment`. The last two preserve the existing legacy manual case format
without converting its judgments into v0.2 Assessments.

| Edge type | Direction and meaning |
| --- | --- |
| `contains` | Model to its keyed records; manual case to its judgments |
| `uses_evidence` | Claim in v0.1, Condition, Assessment, Resolution or manual judgment to cited Evidence; Model to Evidence cited by an assumption, domain or limitation |
| `derived_from` | Evidence to upstream Evidence; `data` retains `comparison` and `note` |
| `assesses` | Assessment to the exact Claim or Condition revision |
| `has_subject`, `has_context` | Evidence, Assessment or selected Component to its Subject/Context |
| `targets` | FollowUp to its target, retaining the target revision |
| `resolves` | Resolution to the FollowUp it records as complete |
| `selects` | Case to Component; registered Component to Model and explicitly selected Assessments |
| `requires` | Consumer Component to dependency Component; `data` retains `quantity` and `description` |
| `uses_record` | Case to its pinned manual-case snapshot |

Other edge `data` objects are empty. Parallel edges retain distinct field
origins, such as two consumed quantities between the same components. The graph
as a whole can contain cycles; only input Evidence provenance has a DAG
constraint. Consumers should use visited sets when traversing relationships.

## Identity and selection

IDs are opaque deterministic hashes. A node ID includes its source snapshot,
record type, local ID and, for Claims/Conditions, revision. A Resolution uses its
FollowUp's ID within the separate `resolution` namespace. Labels are descriptive;
clients must use IDs for links and retain unfamiliar node/edge types when possible.

Changing any source bytes changes the IDs of that source's nodes. This prevents
accidentally combining judgments from different snapshots. `ref` contains
`provider`, `path`, `type`, local `id` and `revision`, without the snapshot hash.
A viewer may use it to find corresponding records after an update, within the
same provider/path convention. Package catalogs and checkouts can use different
path conventions; matching across them is not automatic. File renames and
provider renames also require explicit correspondence.

Graph sources, nodes, edges and selections have deterministic ordering. Authored
arrays inside records retain their order. There are no generation timestamps,
layout coordinates, colors or HTML links in the export. The graph format version
covers the envelope and relationship meanings; source schemas govern `record`.
Incompatible changes require a new graph format identifier.

All records in each selected contract are exported, including historical
Assessments and multiple Claim/Condition revisions. `selections` preserves the
narrower choices separately:

- `catalog_record`: `origin` identifies the catalog record. `catalog_model`
  preserves its model metadata without the record list, and `record` preserves
  the catalog entry. `model` and `assessments` contain graph node IDs.
- `case_component`: `origin` identifies the component. `component`, `model`,
  `subject`, `context` and `assessments` contain graph node IDs. Absent selections
  are null or empty; `registration` is `registered` or `unregistered`.

Two records/components can select the same contract with different Assessments.
These selections are never unioned into an implicit current judgment. A known
unregistered component remains a node with null model/subject/context and empty
assessments. Direct contract exports have an empty `selections` list.

## Scientific interpretation and future reasoning records

An Assessment remains a node joining its evidence, exact target revision,
Subject and Context, with the authored method and reasons intact. `uses_evidence`
means a declared reference; it does not mean that support follows automatically.
Evidence `result`, provenance `inspection`, Assessment `status` and membership
`classification` keep their different meanings. A completed FollowUp does not
establish physical accuracy or resolve separately scoped questions.

The graph retains v0.1 Claim declarations and v0.2 Assessment origins. It neither
selects the latest revision nor updates historical outcomes after an implementation
change. Source strings, external URLs and decision artifacts remain recorded
locators. They are not fetched or interpreted, and matching URLs do not merge
Evidence or count independent support. Scientific file pins outside the catalog's
explicit file checks are not reverified; use the existing assessment checks.

The full graph supports navigation through existing investigation records. It
is not the selected [investigation view](checks.md#resume-an-investigation): a
shared upstream source alone does not make all citing Assessments relevant to
one investigation. Generated suggestions are not authored graph nodes.

Future reasoning records can add explicit premise Claims, inference steps,
choices, reviewers, dates and replacement relationships when concrete cases need
them. The existing graph already preserves the scoped judgments and source
identities needed to attach those records. No inference engine or new scientific
contract schema is introduced by this export.
