# SymPy as the mathematical source

Schema `"0.6"` chooses a source **for each Equation**:

| Recorded definition | Authoritative source | Displayed mathematics |
| --- | --- | --- |
| `sympy` is present | The serialized SymPy expression | LaTeX generated from that expression |
| No `sympy` definition | The authored `latex` | That LaTeX unchanged |

This choice depends on the record, not on whether SymPy happens to be installed.
A model can mix both kinds. If both fields are supplied for one Equation,
`sympy` wins: canonical serialization omits the ignored `latex`. A missing
SymPy backend or unsupported expression produces an explicit error; MCEG never silently uses
an old LaTeX formula instead.

Install the optional backend in the **authoring/checking environment**:

```bash
python -m pip install -e '.[symbolic]'
```

The initial codec targets SymPy 1.14.x. The scientific provider's runtime still
needs neither MCEG nor SymPy. Reading LaTeX-only records also needs no SymPy.

## Choose an editing workflow

The source rule above applies to the **record that MCEG reads, hashes and
displays**. It does not require a second Python file containing the same
equation, or prescribe where a repository's authors edit expressions. Choose
and document one editing location for each equation:

| Workflow | Where the expression is maintained | What is stored in the contract |
| --- | --- | --- |
| Contract only | The Equation's `sympy` field; temporary Python operations may help edit it | The maintained expression, together with its meanings and assumptions |
| Optional generated expression | A named Python authoring script | The generated `sympy` field, plus separately maintained semantic metadata |

For a shared library aiming to keep each equation in one maintained location,
the contract-only workflow avoids a parallel formula registry and synchronization
step. Load the contract with `load_contract` and select the Equation by ID and
revision. Recover its expression with `to_sympy(equation.sympy)`, and use SymPy
to inspect or edit that object. Serialize
an edited object with `from_sympy(expression).model_dump(mode="json")` and save
the result in the selected Equation's `sympy` field. The temporary editing code
does not need to become another maintained definition. The construction example
below also applies to this workflow.

If a repository chooses the generated-expression workflow, edit the expression
only in its documented authoring script. Regenerate the corresponding `sympy`
field; do not edit that generated field independently. Meanings, units,
assumptions and any LaTeX-only equations may still be maintained in the contract.
The worked example below uses this optional workflow. It is not a required
architecture for libraries or numerical providers using MCEG.

Both workflows require review of definition revisions and evidence when the
recorded expression or its meaning changes. Changing the editing workflow alone
need not change the recorded definition, but source-file pins must be reviewed
if they name an authoring script that is changed or removed.

## Author an expression

Construct expressions in trusted Python, then serialize them with `from_sympy`:

```python
import sympy as sp

from mceg.symbolic import from_sympy

P, rho, R, T = sp.symbols("P rho R T")
source = from_sympy(sp.Eq(P, rho * R * T, evaluate=False))
print(source.model_dump())
```

The corresponding Equation stores the expression and its meanings together:

```yaml
- id: ideal_gas
  revision: '1'
  sympy:
    format: sympy-srepr-v1
    expression: "Equality(Symbol('P'), Mul(Symbol('R'), Symbol('T'), Symbol('rho')))"
  description: Ideal gas with a fixed specific gas constant.
  scope: Gas pressure, mass density and temperature at the same location.
  symbols:
    P: {latex: P, description: Gas pressure, unit: Pa}
    rho: {latex: '\rho', description: Mass density, unit: kg m^-3}
    R: {latex: R, description: Specific gas constant, unit: J kg^-1 K^-1}
    T: {latex: T, description: Gas temperature, unit: K}
```

All symbol and undefined-function names must be declared in `symbols`. For
example, `Function('P')(Symbol('z'))` needs entries for both `P` and `z`.
Use actual functions and derivatives for fields; do not encode `dP/dz` as a
single symbol with that label. Units, domains and physical assumptions remain
authored metadata. MCEG does not infer dimensional consistency or physical
meaning from the expression tree.

The portable serialized expression is the definition read by MCEG in either
workflow. Contract loading never imports or executes an authoring script.

## A model with SymPy and LaTeX equations

The [worked example](../../examples/symbolic/atmosphere.yaml) assembles:

| Relation | Source | Meaning |
| --- | --- | --- |
| {math}`P(z)=\rho(z)R T(z)` | SymPy | Ideal-gas state relation |
| {math}`dP/dz=-\rho(z)g` | SymPy | Hydrostatic balance |
| {math}`y(z)\mid P(z),\sigma\sim\mathcal N(P(z),\sigma^2)` | LaTeX | A prescribed Gaussian pressure-observation law |

The distribution is retained as LaTeX because this first codec does not cover
SymPy's statistics objects. All three relations share explicit quantity IDs.
Temperature and boundary conditions are deliberately unspecified, so this
authoring example is not a closed atmosphere solver or a validated likelihood.

```bash
mceg examples/symbolic/atmosphere.yaml
mceg model examples/symbolic/atmosphere.yaml --model atmosphere --format json
mceg model examples/symbolic/atmosphere.yaml --model atmosphere \
  --format tex --output /tmp/symbolic-model.tex
```

These validation and rendering commands use the contract alone. They do not
require a generation step.

### Optional generator used by this example

This example also retains a trusted [authoring script](../../examples/symbolic/define.py)
to demonstrate the generated-expression workflow. To change this example's
symbolic relations, edit that script, then run it without `--check` to update
their stored expressions. Edit the LaTeX relation and semantic metadata in the
contract. Do not independently edit its generated `sympy` fields.

```bash
python examples/symbolic/define.py --check
```

This optional check compares the generated expressions with the committed
record. It detects drift; it does not show that keeping both representations
is necessary, or establish mathematical consistency or scientific support.
The [example guide](https://github.com/HajimeKawahara/mceg/blob/main/examples/symbolic/README.md)
records its editing locations.

## What MCEG checks

Equation and model pins include the selected definition and its semantic
metadata. A symbolic expression change makes an earlier pin stale. So does a
change to a quantity's meaning or a relation's quantity mapping. Editing an
ignored `latex` field on a SymPy Equation does not change its identity. Migrating
an Equation from LaTeX to SymPy changes its definition identity even if both
displays look the same; MCEG does not certify their algebraic equivalence.

TeX exports, model graphs and generated documentation derive their
display from the same source. The existing `--check` export mode detects stale
generated files. Equation Bindings still declare the correspondence to provider
code; AST inspection checks those declarations, while actual mathematical
correspondence needs scoped tests and reviewed evidence. No new scientific
support is inferred from successful symbolic decoding or pretty printing.

## A bounded expression format

The `sympy-srepr-v1` format accepts a limited constructor vocabulary for scalar
algebra, functions, relations, derivatives and selected calculus constructs. It
does not promise to load every SymPy object. Unsupported constructors, Python
attributes, imports and expressions exceeding the codec's resource bounds are
rejected explicitly.

SymPy documents that its general-purpose
[`parse_expr` uses `eval`](https://docs.sympy.org/latest/modules/parsing.html).
MCEG instead decodes an explicit constructor tree without `eval`, string
`sympify`, `parse_expr`, pickle, or provider imports. This limits what a stored
document can request; it is not a proof of exhaustive parser security or a
general sandbox for running symbolic computations.

SymPy's [printing documentation](https://docs.sympy.org/latest/modules/printing.html)
describes expression representations and LaTeX generation. MCEG does not parse
old LaTeX into SymPy automatically. Author the intended expression explicitly,
preserve any unsupported relation as LaTeX, and review the resulting definition.
