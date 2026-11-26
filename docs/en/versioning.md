# Versions and compatibility

The current package release is `0.1.1`, with explicit readers for schemas
`"0.1"` and `"0.2"`. The development version also reads experimental `"0.3"`
[equation definitions and bindings](equations.md) and `"0.4"`
[Decision records](decisions.md), plus `"0.5"`
[mathematical model graphs](mathematical_models.md), and `"0.6"`
[optional SymPy definitions](symbolic.md). Existing contracts keep their formats and
semantics; older readers reject unsupported versions explicitly.
Package versions and contract schema versions are separate.

Schema `"0.6"` lets an Equation supply a serialized SymPy expression. When
present, it is authoritative and any supplied `latex` is ignored in canonical
serialization, rendering and definition pins. Without a symbolic definition,
LaTeX stays authoritative and the Equation's earlier digest is preserved.
Changing from LaTeX to SymPy changes the definition identity and requires a new
review, even if the formulas look equivalent. Reading symbolic definitions
requires the optional `symbolic` extra (SymPy 1.14.x); a missing backend or an
unsupported expression produces an explicit error. LaTeX-only contracts do not need SymPy.
Older readers reject schema 0.6. No automatic migration is performed.

Schema `"0.5"` adds quantity definitions and explicit mathematical model
assemblies. It reuses unchanged Equation definitions and their digests. Model
pins include the adopted equations, quantities, coordinates and connection
maps. Earlier schema readers remain available; unsupported versions are
rejected. Older contracts are not automatically migrated, and a new default
field does not renew or reinterpret an earlier review.
The `v0.1.0` baseline tag remains unchanged; the v0.2 schema remains experimental.
The [v0.2 guide](v02.md) defines the common records, limited automatic comparisons
and migration procedure.

The development reader adds the `contradicted` support-Assessment status to
experimental schemas `"0.2"`, `"0.3"` and `"0.4"`. Existing documents remain
readable; older readers reject documents using the new enum value. This is an
explicit experimental-format extension, following the optional-field and
quantity-enum extensions below. It does not change frozen v0.1 Claim statuses,
migration results, or existing `unknown` judgments. New contradictions require
an explicit scoped review; neither failed executions nor stale evidence are
automatically reclassified. See the [support-state definitions](v02.md#support-contradiction-and-missing-knowledge).

Schema `"0.4"` adds an optional `decisions` collection to v0.3 and preserves the
earlier readers. Its basis hashes identify the cited records and their declared
local dependencies. A stale basis does not rewrite a historical Decision or
change scientific support. There is no automatic migration of provider-owned
decision artifacts and no implicit current choice. The package version remains
`0.1.1` during development; a schema number is not an installable package version.

Before the first PyPI release, development snapshots used the unpublished
`0.2.0rc1` and `0.2.0rc2` package labels. Their features are included in `0.1.1`.
Users with one of those snapshots installed must select `mceg==0.1.1` explicitly,
because package installers consider `0.2.0rc2` newer than `0.1.1`.

The second development candidate added optional `follow_up_resolutions` to the
experimental v0.2 format. Existing v0.2 records remain readable; resolutions default to an
empty list. The rc1 reader rejects documents
containing the new field, including an empty list, because unknown fields are
forbidden. Such documents require the current release or the rc2 development
snapshot. This is an explicitly documented candidate-format extension, not a
change to the frozen v0.1 format or tracing
semantics. Task completion never changes historical inspection or support.

The current release also includes distinct volatile partial-pressure/fugacity
quantity names described in the [v0.2 guide](v02.md). Older readers that lack these enum
values reject contracts using them. `init` and `coverage` are additive commands;
their separate inventory format is documented in the [coverage guide](coverage.md).

## Experimental v0.1 baseline

MCEG freezes its first proof of concept on 2026-10-15. The package version and
Git tag are `0.1.0` and `v0.1.0`; contracts use `schema_version: "0.1"`.
This is a reproducible development baseline, not a final scientific standard.

## What is frozen

- The YAML fields, types, required and optional values, and enums described by
  the [schema guide](schema.md) and defined in [schema.py](../../src/mceg/schema.py).
- The meanings of domain, claim, test-result, inspection, and comparison states.
  `documented` and `supported` describe declarations with recorded evidence.
- The documented structural checks, including local references, duplicate keys,
  evidence categories, and acyclic provenance links.
- The public `Contract`, `load_contract`, and `trace_provenance` entry points,
  CLI validation and tracing behavior, exit codes, and trace report fields.
  Human-readable error wording is not a stable interface.

`recorded_audit_complete` means that the supplied records declare complete
inspection and consistent comparisons to primary sources for the traced scope.
It does not establish scientific validity, exhaustive dependencies, independent
reproduction, or applicability to a calculation. These distinctions are part
of the frozen semantics, as described in [source tracing](provenance.md).

## Changes after the baseline

The `v0.1.0` tag identifies an immutable snapshot. Later work uses new commits
and versions; the tag must not be moved to incorporate corrections.

Within package `0.1.x`, implementation fixes and documentation clarifications
may preserve conformance to the frozen schema and semantics. Record any changed
validation outcome in the changelog, including a fix for previously incorrect
acceptance or rejection. No new fields, enum values, or altered status meanings
will be introduced under `schema_version: "0.1"`.

The experimental [`mceg check`](checks.md) convenience command is additive. It
retains the original validation and trace commands, exit codes, and report fields.
Its check report is separate from those frozen interfaces and from the contract
schema. Its scoped curated evaluator reuses the reviewed example policy; it does
not change v0.1 Claim statuses or define a general scientific inference rule.

Schema extensions now use `"0.2"`, with `mceg migrate` preserving old declarations
as explicitly imported Assessments. `load_contract` dispatches on the exact
version string; `Contract` remains the v0.1 class and `ContractV02` is separate.
The v0.1 validator rejects new fields, so compatibility must not be inferred
merely because a field is optional. Unsupported versions are rejected.

Migration writes a new artifact, leaves the source untouched, and records its
byte hash and validated-content hash. `restore_v01` verifies reconstruction of
the original validated data. It does not reconstruct YAML comments or formatting.
The original source-tracing outcomes and evidence meanings are preserved.
YAML and JSON loaders reject duplicate keys; JSON is parsed as JSON so numeric
exponents such as `1e-13` retain their numeric type.

Scientific contracts and audit findings may be revised without a schema change.
Keep earlier states in Git, identify the inspected sources and scope, and explain
changed conclusions. Unknown findings may remain unknown indefinitely. Obtaining
the missing original paper is not a prerequisite for this baseline.

The five example contracts, H2 case, and saved execution receipt are part of the
tagged snapshot. The case and receipt are example-specific artifacts, not general
MCEG schema objects. If their hashed inputs or sources change, replay the example
to produce a matching receipt; do not update hashes to imply a new execution.

## Deferred work

The experimental v0.2 schema adds source-scoped closed intervals, exact joint
samples, K/pressure-unit comparison, and explicit Subject/Context-bound Assessments.
It does not infer physical applicability, general extrapolation accuracy,
source rankings or cross-contract support. The earlier H2 and lifecycle trial
formats remain historical example artifacts, not accepted core contracts.
The [partial primary-source audit](h2_primary_audit.md) records remaining evidence
gaps; `mceg explain` now exposes those gaps and next steps without changing them.
The [changelog](changelog.md) records package changes.
