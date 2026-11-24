# Equation definitions and implementation bindings

Schema `"0.3"` adds mathematical definitions and explicit code mappings to the
existing Claim, Evidence, Subject and Assessment records. The new reader still
accepts v0.1 and v0.2; existing records need no migration. Older readers reject
v0.3. Package and contract schema versions are separate.

An **Equation** defines a model; it is not evidence that a provider implements
that model correctly. A **binding** declares how one equation relates to one
function at a pinned Subject. A Claim names the equation revisions it concerns,
and an Assessment records the evidence and scope of a review. None of these
declarations runs the provider or proves mathematical equivalence.

## Record a definition

Each equation has `id`, `revision`, `latex`, `description`, `scope`, `symbols`,
and optional `assumptions` and `evidence`. A symbol has a LaTeX spelling,
description and unit string. Units describe conventions; no dimensional
analysis or conversion inference is performed. IDs are local to the contract,
and symbols are local to an equation. Equation `(id, revision)` pairs are unique.

```yaml
equations:
  - id: continuity
    revision: '1'
    latex: '\rho = \frac{\dot M}{4\pi r^2 v}'
    description: Steady spherical mass continuity.
    scope: Positive radius and outward speed; prescribed mass-loss rate.
    assumptions:
      - No sources or sinks of mass between shells.
    symbols:
      rho: {latex: '\rho', description: Mass density, unit: 'g cm^-3'}
      r: {latex: 'r', description: Radius, unit: cm}
      v: {latex: 'v', description: Radial speed, unit: 'cm s^-1'}
      mdot: {latex: '\dot M', description: Mass-loss rate, unit: 'g s^-1'}
```

This is an excerpt. The complete [example contract](../../examples/equations/continuity.yaml)
also supplies the ordinary required model, evidence, domain and review records.
Equations may describe planned work; a definition does not mark that work
implemented or supported. Keep boundary conditions, closure choices and the
distinction between continuous and discrete equations explicit in the scope
and assumptions. Coupled equations need not form an acyclic dependency graph;
the existing acyclic *source-provenance* graph has a different meaning.

## Bind an equation to code

```yaml
bindings:
  - id: continuity_density
    equation: {id: continuity, revision: '1'}
    subject: example_source
    source: examples/equations/provider.py
    symbol: density
    arguments:
      radius_cm: {symbol: r}
      velocity_kms: {symbol: v, scale: 100000.0}
      mass_loss_g_s: {symbol: mdot}
    result: rho
    note: The return value already uses the equation's density units.
```

The convention is **equation value = scale × argument value + offset**, with
defaults 1 and 0. The binding's source must be listed in the Subject's
`selected_files`, and `source:symbol` in its implementation `entry_points`.
`result` identifies the mathematical symbol for the returned value in the
same units. Optional `constants` maps equation symbol IDs to descriptive code
locators. Those locators are not evaluated or resolved. Pin dependency files
in the Subject when imported constants or helpers affect the model.

One function can have several bindings; equations need not correspond
one-to-one to functions. The initial mapping covers named Python parameters
and a single returned quantity. Tuple components, implicit unit conversions,
dynamic dispatch and arbitrary executable mapping expressions are not inferred.
For an NLTE solver, record the physical equations, discretized residual and
derivative formulas separately, with scoped Claims about each connection.

`mceg check --assessment ID --root ROOT` checks the selected bindings with
Python's AST, without importing or executing the source. It checks declared
function and parameter locations **before decorators are applied**. A unique,
unconditional decorated declaration is inspected without evaluating its
decorators, even if a decorator would replace the callable or its signature.
Mapped parameters must still occur in the original declaration. Dynamic,
conditional or rebound definitions remain UNKNOWN. This does not verify the
runtime callable or its accepted arguments. Existence of a function is not
evidence that it evaluates the equation. Unit conversions, constants, returned values and scientific
correspondence still need review and meaningful provider tests.

## Pin a review without rewriting its history

Claims use `equations: [{id: continuity, revision: '1'}]`. Support Assessments
add `equation_pins` with those IDs, revisions and SHA-256 values, and optionally
`binding_pins` with binding IDs and SHA-256 values. A `supported` or `contradicted`
Assessment requires pins for every equation referenced by its Claim. An unknown
Assessment may record partial pins while a review is unfinished.

Use `equation_digest` and `binding_digest` from `mceg.schema_v03` to compute
identities **after** inspecting the definitions and mappings. The digest
covers the complete validated record, including defaults, symbol descriptions,
units, assumptions and declared evidence IDs. It does not recursively hash
the referenced evidence; use the existing source/artifact pins for that.
Fingerprinting is conservative byte identity of canonical JSON, not symbolic
equivalence. Formatting changes can require review too.

A hash mismatch is reported as FAIL by `check`; records remain readable so
the original outcome can still be inspected. Stored support statuses are never
rewritten or promoted by a hash check. Preserve the old equation revision,
binding and assessment, and add new revisions/IDs when their meaning changes.
Do not refresh hashes to imply a new review or test execution.

```bash
python -m mceg check examples/equations/continuity.yaml \
  --assessment initial_record --root .
python -m mceg explain examples/equations/continuity.yaml \
  --assessment initial_record --root .
python -m mceg graph examples/equations/continuity.yaml --root . \
  > /tmp/equations.json
```

The example intentionally retains UNKNOWN scientific support. The graph adds
equation and binding nodes with explicit references and assessment pins;
edges are authored relationships, not inferred support.

## Maintain one mathematical source

Edit `Equation.latex`, then export a TeX fragment:

```bash
python -m mceg equations examples/equations/continuity.yaml \
  --output examples/equations/equations.tex
python -m mceg equations examples/equations/continuity.yaml \
  --output examples/equations/equations.tex --check
```

`--check` fails on a missing or stale fragment without changing it. The export
is deterministic and does not invoke LaTeX. Use standard mathematical LaTeX
commands; omit the outer equation environment, labels and tags, which the
renderer supplies. The math body is placed inside `aligned`, so `&` and `\\`
can express aligned rows. Arbitrary TeX macros are not expanded or validated.

Commit the generated fragment and include it from a hand-written document,
as in [model.tex](../../examples/equations/model.tex). The provider's normal
PDF build then needs only LaTeX; its Python package needs neither MCEG nor
LaTeX. The example can be compiled from `examples/equations` using:

```bash
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=/tmp model.tex
```

Generated Sphinx records also show the equations, symbol tables and bindings.
Enable `sphinx.ext.mathjax` in the consuming documentation configuration.
Rendering does not recheck hashes. Build and inspect the resulting PDF/HTML
after changes; a successful structural check does not establish valid TeX.
