# Check contracts from the terminal

`mceg check` discovers contracts, runs the available offline checks, and prints
each result and a summary. It requires only MCEG's normal dependencies.

```bash
source /path/to/mceg/.venv/bin/activate
cd /path/to/exogibbs
mceg check
mceg check -k curated
mceg check -k curated --temperature 1750
mceg check -k curated --jax 0.10.2
mceg check -k curated -v
mceg check -k curated --plain
mceg check -k curated --json > /tmp/curated-check.json
```

No Python snippet, JAX installation, or provider import is needed. These checks
read contracts and saved evidence; they do not execute numerical tests or modify
provider files. A `PASS` describes the named check's scope.

## Terminal display

By default, terminal output marks each result with green `✓ PASS`, red `✗ FAIL`,
or yellow `? UNKNOWN`, highlights contract paths and totals, and wraps explanations
to fit the terminal width. Status words remain visible alongside the markers.
Terminals without Unicode support use `+` and `x` instead of the check and cross.

`--plain` selects the original text layout with no colors or symbols, including
the original check identifiers such as `source_audit`. Pipes and file redirection
automatically use this plain layout. Set `NO_COLOR=1` to keep the terminal layout
and markers without ANSI colors; `TERM=dumb` also disables colors. `--json`
continues to emit only JSON, even on a terminal. `--plain` and `--json` are mutually
exclusive.

`explain` uses the same terminal/plain selection and color controls. Its terminal
view highlights unresolved checks, numbers the proposed tasks, and separates
required material from completion criteria. Record fields have readable labels;
file hashes, artifacts and joint-sample lists are summarized by count, while
missing file paths remain visible. Copyable navigation commands stay on one
physical line. Historical results retain their original tokens and do not
become new PASS badges.

`--lang ja` selects Japanese UI messages for both `check` and `explain`;
`--lang en` is the default. It works with terminal markers and `--plain`.
The next-step commands retain `--lang ja`, including when navigating to an
Evidence or Assessment. `PASS`/`FAIL`/`UNKNOWN`, IDs and paths remain unchanged.

Only application-owned headings, check messages and suggested work are
translated at display time, using a small offline catalog. Scientific contract
text and curator-authored instructions remain in their original language and
are labeled as original text in the Japanese view. JSON reports are identical
for both language choices. No schema changes, duplicate-language evidence, or
external translation service are involved. Parser help and diagnostic errors
retain their original language.

```bash
mceg check -k curated --lang ja
mceg explain -k curated --temperature 1750 --lang ja
```

## Discovery and selection

With no path, discovery starts in the current directory. From a repository root,
it searches `mceg/contracts` and/or `contracts` when present. Otherwise it searches
the supplied directory recursively for `.yaml` and `.yml` files, excluding hidden
paths. This also works directly inside `mceg/contracts`. Explicit files and
multiple paths are accepted, and overlapping discoveries are deduplicated:

```bash
mceg check /path/to/exogibbs
mceg check /path/to/exogibbs/mceg/contracts/curated_gas.yaml
```

`-k NAME` selects a case-insensitive substring of the contract path, not a pytest
boolean expression. `-v` shows source-audit gaps and recorded Claim declarations.
`--json` writes a machine-readable report to stdout, including the scoped
curated assessment and selected file hashes when available.

The existing `mceg FILE.yaml` and `mceg --trace ID FILE.yaml` commands retain their
v0.1 behavior. If a file literally named `check` exists in the current directory,
`mceg check` retains its original meaning of validating that file.

For v0.2, select the Assessment being reviewed explicitly:

```bash
mceg check contract.yaml --assessment imported:physical_accuracy
mceg explain contract.yaml --assessment imported:physical_accuracy
```

The source audit follows only that Assessment's Evidence and provenance
dependencies; its Subject and Context are displayed. Other Assessments are not
implicitly selected, even when they have the same Context. Structural validation
still checks the entire contract. Without `--assessment`, the scope is labeled
`All records, including history`. A missing Assessment ID in selected valid
contracts is a usage error (exit 2); valid contracts lacking the ID are skipped
when other selected files contain it. Invalid files still produce structure
failures. An empty file selection retains exit 5.

The JSON report records `audit_scope`, `audited_evidence` and the selected
Assessment. `explain --assessment` uses the same source audit and displays only
its dependency gaps. Context override flags apply to the curated v0.1 workflow;
use `mceg assess` to create a new v0.2 Context/Assessment instead.

## What each result means

| Check | Scope |
| --- | --- |
| `structure` | Declared v0.1/v0.2 schema and local reference consistency |
| `source_audit` | Whether supplied records declare complete primary-source inspection and comparison; unresolved traces are `UNKNOWN` |
| `recorded_support` | With `--assessment`, the selected support Assessment's stored status and origin; no new support evaluation |
| `selected_files` | Curated receipt hashes, or the selected v0.2 Subject's file hashes when `--root` is supplied |
| `artifact_hashes` | With `--root`, artifact hashes in the selected v0.2 Assessment's Evidence dependency closure |
| `temperature_range` | Whether the requested temperature is within the reviewed 1500--4000 K numerical interval |
| `sample_coverage` | Whether T/P/network matches an archived curated sample; interpolation is not assessed |
| `evidence_reuse` | Whether the explicitly reviewed numerical declaration is reusable for the selected files and requested context |
| `physical_validation` | Whole-mixture physical accuracy remains `UNKNOWN` |

All contracts receive structure and source-audit checks. The curated-specific
checks apply only to ExoGibbs's provider-owned
`mceg/contracts/curated_gas.yaml` and its pinned review. Other models report
`UNKNOWN` for evidence reuse when no Assessment is selected; they have no
automatic reuse rule yet. For a selected support Assessment, `recorded_support`
reports its declaration. For a selected range/sample Assessment, only that
membership result is recomputed. An empty Evidence list leaves `source_audit`
UNKNOWN, and a completed trace never promotes unknown support.

For the reviewed curated snapshot and default context, the terminal result
(with explanations omitted here) is:

```text
✓ PASS    Structure
? UNKNOWN Source audit
✓ PASS    Selected files
✓ PASS    Temperature range
✓ PASS    Sample coverage
✓ PASS    Evidence reuse
? UNKNOWN Physical validation

5 passed, 0 failed, 2 unknown
```

At **1750 K**, the temperature check still passes, but sample coverage and
evidence reuse become `UNKNOWN`: this temperature is between archived samples.
At **4001 K**, the numerical interval check fails. That failure says nothing
about physical validity outside the interval. Changing a selected input or
output fails its hash check and makes reuse unknown. Changing the pinned contract
or receipt makes reuse unknown and explicitly requests scope review; the command
never repins records automatically. Historical numerical passes and v0.1 Claim
statuses remain unchanged.

## Requested context

The bundled defaults describe an archived example: 1735 K, 0.01 bar, ion-inclusive
network, normalized Asplund 2021 nuclear budget, Python 3.12.3, JAX 0.11.2, CPU,
float64, and epsilon 1e-13. The terminal displays the effective context and its
origin. **Installed Python/JAX versions are not inspected.**

`--temperature K`, `--pressure BAR`, `--network ions|neutral`, and `--jax VERSION`
override individual requested values. To specify other values or start with an
incomplete context, supply a JSON object:

```json
{
  "temperature_K": 1750,
  "pressure_bar": 0.01,
  "network": "ions"
}
```

```bash
mceg check -k curated --context context.json
```

An explicit file replaces the default context; missing fields remain missing.
CLI overrides then apply to that file. Missing composition, environment, or
tolerance leaves reuse unknown. The other accepted context keys are `composition`,
`python`, `jax`, `backend`, `dtype`, and `epsilon_crit`.

This command uses the original reviewed receipt. The separate
[lifecycle experiment](assessment_lifecycle.md) contains later numerical runs;
the command does not select among those archives or launch a new run.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | At least one contract selected, with no failed check; `UNKNOWN` may remain |
| `1` | At least one check failed |
| `2` | Invalid command arguments, context, or discovery path |
| `5` | No contracts selected |

`UNKNOWN` is a visible review or coverage gap, not a failed scientific claim.
The command and JSON check report are experimental conveniences; they do not
change the frozen v0.1 validation/trace reports.

## Inspect the next step

When UNKNOWN or FAIL remains, `check` prints one `Next steps: mceg explain ...`
command preserving the selected paths, filter, Assessment ID and context overrides. Detailed
work instructions appear only when requested:

```bash
mceg explain -k curated --temperature 1750
mceg explain -k curated --evidence source_choices
mceg explain -k curated --plain
mceg explain -h
mceg explain /path/to/mceg/examples/v02/h2_solubility.yaml --evidence experimental_fit
mceg explain /path/to/mceg/examples/v02/h2_solubility.yaml --claim physical_accuracy
```

The overview lists unresolved checks and Evidence IDs. Selecting `--evidence ID`
shows its source, scope, stored inspection/access notes, upstream gaps, and
copyable navigation commands. `--claim ID` lists its revisions and associated
Assessments; `--assessment ID` shows the precise v0.2 Subject, Context, method,
evidence and reason for that judgment. `--json` includes the complete records;
`--plain` retains the original record layout and previews large joint-sample
lists. `mceg -h` lists commands and examples; `mceg explain -h` lists its selectors,
context options, language and output modes.

For an unchecked or discrepant comparison, the suggested task identifies the
upstream Evidence ID, source links, recorded page/equation location, inspection
state and comparison note. Its navigation command is shown even when the source
itself is already inspected: reading a source and comparing it with an
implementation are separate review steps.

When a completed follow-up cites an inspected comparison of the same source,
`explain` shows its result before the historical record, instead of asking for
that comparison again. Source identity must match by Evidence ID or recorded
artifact SHA-256; a shared URL alone is insufficient. The follow-up may record
agreement **or a discrepancy**: finishing a comparison does not resolve every
difference or establish physical accuracy. Commands lead to the completion
evidence and assessments that explicitly cite it. Other unchecked sources and
open tasks remain visible. JSON retains the deferred suggestions in
`historical_steps` and the source matches in `completed_comparisons`; the original
records and source audit are unchanged.

Each proposed task includes what to do, any material required, and completion
criteria. Authored v0.2 follow-ups are labeled **Recorded next step**; guidance
derived from gap categories is labeled **Suggested next step**. For example:

| Gap | Next work |
| --- | --- |
| Original H2 fit not inspected | Obtain authorized full text, possibly through a human's institution/library, then inspect the exact fit and concentration/unit transformations |
| Missing curated context | Supply the actual missing composition/environment/tolerance fields |
| 1750 K or a different environment | Obtain numerical evidence for those conditions and review its coverage; keep a separate receipt and Assessment |
| Changed selected files | Inspect the listed changes; restore the archived inputs for a replay or obtain evidence for the changed model |
| Physical accuracy unknown | Define observable, accuracy criterion and conditions, then compare independent physical measurements |

No sources are fetched, provider code executed, or evidence edited. Stored
access failures are historical notes, not fresh availability checks. A local
paper path alone does not mark it inspected. Local cross-contract commands are
navigation links; they do not propagate support between contracts.

`explain` exits 0 after inspection, even if gaps remain; 2 for invalid arguments,
an unavailable requested ID or an unreadable selected record; and 5 when no
contracts are selected. A malformed contract's overview explains its structural
error without attempting evidence inspection.

## Resume an investigation

Add `--investigation` to a selected Evidence, Claim or Assessment view to gather
the related records for a human or LLM reviewer in one read-only report:

```bash
mceg explain examples/v02/h2_solubility.yaml --evidence implementation --investigation
mceg explain examples/v02/h2_solubility.yaml --claim physical_accuracy --investigation --json
mceg explain examples/v02/h2_solubility.yaml --assessment imported:physical_accuracy --investigation --root .
```

Run these examples from the MCEG checkout. In a provider, use its contract path
and recorded IDs. Package/catalog lookup supplies those locators; investigation
requires the contract itself. The flag requires exactly one of the existing
selectors. It supports v0.1 and v0.2, with completion and Assessment records
available only when supplied by v0.2. Ordinary `explain` output is unchanged.

The text view presents completed follow-ups before pending authored tasks, then
the related judgments, implementation/context records and evidence. It retains
exact source locations and comparison notes, including agreement and discrepancy.
Generated suggestions are labeled separately from authored work. Source and
artifact locators, including provider decision records, remain available for
inspection; their contents are not fetched or interpreted.

JSON adds an `investigation` object to each selected contract's existing report:

| Field | Meaning |
| --- | --- |
| `selection`, `scope` | Selected records and the traversal boundary |
| `completed_follow_ups`, `pending_follow_ups` | Explicit completion records and outstanding authored tasks |
| `evidence`, `assessments` | Related records with their original scopes, source locations, reasons and judgments |
| `subjects`, `contexts` | Bindings from included Evidence and Assessments |
| `suggested_steps` | Generated guidance labeled with its target record |
| `excluded_evidence` | Evidence IDs outside this selected investigation |
| `next_commands` | Copyable navigation, including sources that agree |

Selection follows upstream provenance and explicit task-completion Evidence in
the same contract. Assessments for a selected Claim use its exact recorded
revision; selecting a Claim ID still includes all its recorded revisions.
Assessments citing selected Evidence or explicit completion Evidence are also
included. Merely sharing an upstream paper does not pull unrelated Assessments
into the report. Completion links are deduplicated and may refer back to an
already included record without causing a loop. External contracts remain
navigation links rather than automatically imported support.

For example, a completed coefficient-choice task can link to the record adopting
`-1873/T`, while author confirmation and physical accuracy remain unresolved.
The report preserves that completion and those remaining questions together.
It does not choose a coefficient, infer that a paper contains a typo, treat
`UNKNOWN` as a blocker, or promote an old numerical result to current support.
If an adoption decision is missing, no decision is manufactured from agreeing
sources. A discrepancy can remain visible after the scoped selection task ends.

With `--assessment ID --root DIR`, the existing audit and hash checks still
apply only to that selected Assessment's original dependency scope. The
investigation can include additional completion records for navigation; those
records are not implicitly covered by the selected hash check. JSON retains
the original `audit_scope`, `audited_evidence` and `integrity` alongside the new
investigation. Use a record's normal `explain` command for its full detail.

## Checking v0.2 artifacts

Discovery also accepts `schema_version: "0.2"`. `check` compares every stored
membership Assessment with its own Condition revision and Context, and fails
if its recorded classification disagrees. A reported interval exclusion is a
failed range check, not proof of physical invalidity. Historical assessments
remain visible when a new Context is added.

Stored support Assessments are not automatically treated as judgments about
an implicit current calculation. The reuse check stays UNKNOWN; select the
intended record with `explain --assessment ID` to see its scoped status. `-v`
also lists Assessment IDs and outcomes. The old curated context flags are
rejected for v0.2 artifacts: use `mceg assess CONTRACT --context FILE --subject ID
--output NEW_FILE` to append a new assessment. See the [v0.2 guide](v02.md).

### Verify local file hashes

Add `--root DIR` to verify the files for an explicitly selected v0.2 Assessment:

```bash
mceg check contract.yaml --assessment current-review --root /path/to/provider
mceg explain contract.yaml --assessment current-review --root /path/to/provider
```

`--root` requires `--assessment ID`. It checks only that Assessment's Subject's
`selected_files` and the `artifacts` on its Evidence and transitive provenance
dependencies. Other Subjects' manifests and unrelated Evidence are not checked.
This permits a current implementation and an archived implementation to coexist
without comparing all historical hashes against the current checkout. Free-text
`sources`, source-inspection declarations and installed providers are not verified.

Paths are relative to the explicit root, independently of the contract's location.
Absolute paths and paths or symlinks resolving outside the root fail. A missing,
unreadable or non-regular file, or a SHA-256 mismatch, also fails. URI sources
remain UNKNOWN and are never downloaded; a null selected-file digest or an empty
manifest remains UNKNOWN. Archives are hashed as files, not extracted.

The two checks report `selected_files` and `artifact_hashes` separately. JSON adds
an `integrity` record containing the resolved root, Subject, per-file expected
and observed digests, outcomes and Evidence IDs. Text shows the root and failed
paths; `-v` also shows unchecked paths. The next-step command preserves `--root`,
and `explain` uses the same file checks. `check` exits 1 on a file failure;
UNKNOWN alone still permits exit 0. `explain` retains its inspection exit codes.

Matching bytes establish file integrity only. Historical execution results and
support Assessments remain unchanged even when files fail verification; successful
hash checks do not promote unknown support. Without `--root`, generic v0.2 checks
retain their existing behavior and do not read the referenced files.

For the ExoInventory adoption, run from its repository root:

```bash
mceg check examples/subneptune_taxonomy/finite_melt/mceg/s1_adopted.yaml \
  --assessment refactor:reference-material-checks --root .
```
