# Readiness for a declared use

`mceg readiness` checks whether explicitly required evidence supports an intended
use of a particular implementation and context. It reads a small provider-owned
manifest outside the contract directory. It does not change Contract schemas,
execute a scientific model, or make the provider depend on MCEG.

For example, a spectrum model may have an `unknown` Assessment for neglecting
radiation feedback, together with an open FollowUp to investigate it. The gap is
handled, but that does not justify using the approximation for physical inference.
A supported component solver also does not establish that the actual spectrum
entry point uses that solver correctly.

| Question | Command or record | Meaning of success |
| --- | --- | --- |
| Is a response to this known gap recorded? | `check --assessment ID --require-handling` | A qualifying FollowUp or Decision exists. Scientific support may remain unknown. |
| Are the declared scientific-use requirements met? | `readiness USE.yaml --root .` with `mode: scientific` | Every selected Assessment is supported in the requested scope, with current pins and local files. |
| May this limited exploration proceed? | `readiness` with `mode: exploration` | Every requirement is supported or explicitly accepted through its scoped exploratory Decision. Support is unchanged. |

Readiness means **the authored requirements are met**, not that MCEG has proved
their completeness, the entire physical model, or equivalence to a paper. The
author must review the requirement list, error criteria and scope. The two
requirement roles, `implementation` and `physical_support`, label what is being
requested; MCEG does not infer either from a test name or Claim text. An
implementation-only list cannot establish physical accuracy.

## Declare the actual use

Place manifests in `mceg/uses/`, separate from the conventional contract discovery
directory `mceg/contracts/`. Contract paths are relative to the manifest; source
and artifact paths remain relative to the explicit `--root`.

```yaml
schema_version: "0.1"
id: escape.physical_spectrum
purpose: Interpret the hydrogen spectrum in the declared atmospheric context.
mode: scientific
target:
  contract: ../contracts/spectrum.yaml
  subject: spectrum_implementation
  context: intended_atmosphere
  entry_point: src/escape/spectrum.py:forward
requirements:
  - assessment: coupled_path_review
    role: implementation
    sha256: REPLACE_WITH_REVIEWED_ASSESSMENT_DEPENDENCY_DIGEST
  - assessment: atmosphere_review
    role: physical_support
    sha256: REPLACE_WITH_REVIEWED_ASSESSMENT_DEPENDENCY_DIGEST
```

The digest placeholders are explanatory; valid manifests require 64 lowercase
hexadecimal characters. After reviewing the Assessment and its dependencies,
compute each pin with the existing record-closure function:

```python
from mceg import load_contract
from mceg.schema_v04 import decision_basis_digest

contract = load_contract("mceg/contracts/spectrum.yaml")
print(decision_basis_digest(contract, "assessment", "coupled_path_review"))
```

This fingerprint includes the selected Assessment, Claim revision, Subject,
Context, Evidence and declared dependencies, including equations and pinned
bindings. Changing those records requires review before changing the use pin;
the command never refreshes pins automatically. Files themselves are checked
separately. Unrelated historical records do not affect the fingerprint.

All required Assessments must belong to the **same Subject and Context as the
target**. A separate solver's component tests can inform Evidence for a scoped
connection Claim, but cannot replace an Assessment of the actual spectrum path.
Use one reviewed contract for the required path-level judgments. Requirements
are all-of: every listed item must pass. If an approximation is an acceptable
alternative, assess its adequacy for the same target explicitly; there is no
automatic fallback to another implementation or Context.

The entry point must occur in the Subject's `implementation.entry_points`, have
a source-file SHA-256 in `selected_files`, and be a statically inspectable Python
function (`relative/file.py:function` or `relative/file.py:Class.method`). Missing,
conditional, dynamically rebound or ambiguous declarations are not accepted.
Decorated functions such as a JAX-jitted method are accepted as lexical
declarations; their decorators are never evaluated. This checks a declaration,
**not a runtime callable, call graph, function execution or coupling**. Those
need their own Claim, scoped Assessment and appropriate evidence. EquationBinding
checks retain their existing stricter treatment of decorators.

## Run and interpret the check

```bash
mceg readiness mceg/uses/physical-spectrum.yaml --root .
mceg readiness mceg/uses/physical-spectrum.yaml --root . --json
```

The command checks the target, Assessment scope and dependency pins, declared
source audit, equation/binding pins, the selected source files, and every artifact
in the selected Evidence closure. Empty artifact lists are allowed for evidence
that declares no file artifact. Every selected source file must have a matching
hash; the entry-point source cannot be omitted. Missing files, changed bytes,
escaping paths and unresolved hashes prevent readiness. No remote artifacts are
downloaded. Undeclared files and dependencies remain outside this integrity check.

Without `--root`, record checks are still shown, but live file integrity and entry
point inspection remain unknown, so the result is `not_ready`. `unknown` and
`contradicted` support both prevent scientific readiness. A FollowUp, its
completion, or a new supported Assessment elsewhere does not override either.

JSON includes the purpose, target, mode, per-requirement checks, unchanged
`recorded_support`, `accepted_by`, local integrity details and aggregate `ready`.
`outcome` is `requirements_met`, `exploration_permitted`, or `not_ready`. Exit
codes are 0 when requirements are met for the declared mode, 1 when not ready,
and 2 for invalid input or unreadable manifests/contracts. `--plain` is the
default text format. Reports do not claim that a calculation was executed.

## Permit explicit exploration

A provider can author a separate manifest with `mode: exploration`. On an
individual `physical_support` requirement, it may then specify:

```yaml
exploration_decision:
  id: prescribed_field_use
  revision: "1"
  selected: exploration_only
  sha256: REPLACE_WITH_REVIEWED_DECISION_DIGEST
```

Compute this second pin with `mceg.readiness.decision_digest(decision)` on the
validated Decision. It pins the full choice, reasons, limitations and scope;
the Decision's basis pins separately protect its dependencies. The selected
Decision must be active (not explicitly superseded), match the exact Subject
and Context, cite this Assessment in its current pinned basis, and declare both
limitations and reconsideration conditions. The selected option must match the
manifest. These are explicit declarations, not inferred permission from prose.

Only the requirement with that Decision can accept unsupported scientific
adequacy. It cannot waive missing targets, scope or integrity failures, source
audit gaps, equation checks, or `implementation` requirements. A manifest in
scientific mode cannot contain such an exception. If accepted, the result says
`exploration_permitted`, while `recorded_support` remains `unknown` or
`contradicted`. The Decision's limitations are included in the report.

The policy and records remain separate from the scientific runtime. A provider
may invoke this command in its review workflow or CI; MCEG does not intercept
ordinary solver calls or grant permission to change a model's scientific claims.
