# Versions and compatibility

The working package version is `0.2.0rc1`, a release candidate with explicit
readers for schemas `"0.1"` and `"0.2"`. This does not move the baseline tag or
publish a final release. The [v0.2 guide](v02.md) defines the common records,
limited automatic comparisons and migration procedure.

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

The v0.2 candidate adds source-scoped closed intervals, exact joint samples,
K/pressure-unit comparison, and explicit Subject/Context-bound Assessments.
It does not infer physical applicability, general extrapolation accuracy,
source rankings or cross-contract support. The earlier H2 and lifecycle trial
formats remain historical example artifacts, not accepted core contracts.
The [partial primary-source audit](h2_primary_audit.md) records remaining evidence
gaps; `mceg explain` now exposes those gaps and next steps without changing them.
The [changelog](../../CHANGELOG.md) records package changes.
