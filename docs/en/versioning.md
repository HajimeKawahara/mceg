# Experimental v0.1 baseline

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

Schema extensions go into `"0.2"` or a later version with an explicit migration
description. The v0.1 validator rejects unknown fields, so even a new optional
field would be rejected by an old reader when present. Compatibility must not
be inferred merely because a field is optional.

Scientific contracts and audit findings may be revised without a schema change.
Keep earlier states in Git, identify the inspected sources and scope, and explain
changed conclusions. Unknown findings may remain unknown indefinitely. Obtaining
the missing original paper is not a prerequisite for this baseline.

The five example contracts, H2 case, and saved execution receipt are part of the
tagged snapshot. The case and receipt are example-specific artifacts, not general
MCEG schema objects. If their hashed inputs or sources change, replay the example
to produce a matching receipt; do not update hashes to imply a new execution.

## Deferred work

Structured applicability conditions, typed evidence relationships, unit-aware
comparison, automatic extrapolation assessment, cross-contract reasoning, and
graph databases remain outside the v0.1 core. A separate
[H2 range assessment](h2_solubility.md#partial-automatic-range-assessment) now
experiments with source-specific intervals and supplied calculation conditions.
Its formats and evaluator are example-only. The
[Claim/Evidence/Assessment proposal](design_questions.md#claim-evidence-and-assessment-separation)
describes a possible later migration without changing existing Claim statuses.
The [partial primary-source audit](h2_primary_audit.md) records remaining evidence
gaps. The [changelog](../../CHANGELOG.md) records package changes.
