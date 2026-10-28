# Inspect an installed model's evidence

A provider can distribute scientific records alongside its numerical package.
Users can install MCEG only when they want to inspect those records. The provider
does not need to import or depend on MCEG to supply JSON and YAML data.

For an ExoGibbs distribution containing the curated/HCN catalog:

```bash
mceg explain --package exogibbs --model exogibbs.curated_gas.v1 --species HCN
```

Omit `--model` to inspect all models in the catalog, or omit `--species` to see
all indexed records. Terminals highlight headings, support judgments and open
follow-ups, and wrap explanatory prose to the terminal width. Commands and URLs
remain on single physical lines for copying. `--plain` and redirected output
retain the plain layout; `NO_COLOR` and `TERM=dumb` disable color. `--json`
retains full records and stable field names, and `--lang ja` translates the
interface labels. Authored scientific content retains its original language.

This lookup reads the installed distribution's file list using Python package
metadata. It does **not** import the provider, call its code, download evidence,
or run calculations. Installing MCEG does not update a provider's scientific
records. The report identifies the evidence snapshot and its SHA-256 separately
from the installed package version.

For a repository checkout or an editable installation, supply the catalog:

```bash
mceg explain --catalog /path/to/exogibbs/src/exogibbs/data/mceg/index.json --species HCN
```

An editable distribution may not list its source data in its installed metadata.
MCEG reports this and suggests `--catalog`; it does not import the provider to
guess its source directory.

## Reading the report

The report shows the provider's declared model identity, species mapping,
recorded numerical and physical claims, explicitly selected assessments,
limitations, and open/completed follow-ups. Species-specific records appear
before general model records. HCN and HNC are different identities: MCEG uses
only exact IDs and authored aliases, never molecular-formula matching.

The user's conditions are **not evaluated** by this command. A matching catalog
name is not a check of a user's live setup, modified coefficients, or saved
calculation. Claims and assessment statuses apply only to their recorded subjects
and contexts. In particular, a reported difference between databases is not an
accuracy ranking, calibrated error bar, or uncertainty distribution. The command
does not propagate it to a spectrum or inferred parameter.

Package/catalog mode rejects context arguments such as `--temperature`, rather
than silently implying that these conditions have been evaluated. To investigate
a record further, follow its `mceg explain CONTRACT --assessment ID` command.
Existing [condition assessment](v02.md) and source inspection remain available
as separate operations. Run-receipt matching is outside this first interface.

Contract and explicitly bundled artifact hashes are checked before the record
is shown. The original scientific input/output paths inside a contract remain
provider-repository references: they are not rewritten to the installed package
or falsely reported as checked. No scientific execution is repeated. For a full
hash audit, use an explicit assessment and the provider checkout as `--root`.

No matching record means **missing assessment coverage**, not absence of model
uncertainty. Exit status is 0 when records are shown, 5 when none match, and 2 for
an invalid catalog, missing/mismatched bundled file, or invalid CLI selection.

## Provider catalog format

Package exactly one file whose installed path ends in `/mceg/index.json`, with
its referenced records. Catalog format `1` is a small discovery index, separate
from scientific contract schema versions `0.1` and `0.2`.

```json
{
  "schema_version": "1",
  "provider": "example-provider",
  "record_version": "2026-10-28",
  "models": [{
    "id": "example.gas.v1",
    "label": "Example gas model",
    "dataset": "gas-v1",
    "identity": {"data_sha256": "...", "settings": {"ions": true}},
    "species": [{"id": "C1H1N1_hcn", "aliases": ["HCN"]}],
    "records": [{
      "id": "hcn-study",
      "path": "contracts/hcn.yaml",
      "sha256": "<64 lowercase hexadecimal characters>",
      "species": ["C1H1N1_hcn"],
      "assessments": ["numerical-review", "physical-review"],
      "summary": "Provider-authored synopsis of the recorded comparison.",
      "links": ["https://example.org/model-review"],
      "artifacts": [{
        "path": "summary.json",
        "sha256": "<64 lowercase hexadecimal characters>"
      }]
    }]
  }]
}
```

`dataset`, `identity`, `aliases`, `summary`, `links`, and `artifacts` are optional.
Use `species: ["*"]` for a general model record. Model/species/record IDs must be
unique in their respective scopes, aliases must be unambiguous, and indexed
species must exist. File paths are relative to the catalog directory and must
remain within it. Hashes must match the distributed bytes. Installed lookup
also checks that `provider` names the selected distribution.

`assessments` names explicit v0.2 assessment IDs. An empty selection does not
automatically select the newest or most favorable assessment. A v0.1 record
uses its historical claim declarations and must not select assessment IDs.
Catalog summaries and relevance mappings are provider-owned declarations; the
copied scientific contracts remain authoritative about their scope and evidence.

Maintain one source of scientific records. Generate the distribution's copies
and index from reviewed repository records, including numerical synopsis values
from pinned summaries. A new evidence snapshot can describe unchanged model
data. Preserve its version/hash and historical assessments instead of changing
the model or granting new support merely to refresh the report.
