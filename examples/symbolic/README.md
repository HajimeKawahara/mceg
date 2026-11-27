# Symbolic atmosphere example

This example contains SymPy equations and a separate LaTeX-only relation.
It also demonstrates an **optional generated-expression workflow**. MCEG
loads, validates and renders `atmosphere.yaml` without importing `define.py`.

| Content | Edit location |
| --- | --- |
| The two symbolic expressions | `define.py`; run it to update their generated `sympy` fields |
| Symbol meanings, units, assumptions and model connections | `atmosphere.yaml` |
| The LaTeX-only observation relation | `atmosphere.yaml` |

Do not independently edit the generated `sympy` fields while using this
workflow. From the repository root, `python examples/symbolic/define.py --check`
checks agreement without changing the contract. This is a synchronization
check, not a mathematical or scientific validation.

A library can instead maintain its expressions only in its contracts, using
`to_sympy` and `from_sympy` for temporary editing operations. Keeping a Python
formula registry beside the contract is not a schema requirement. See
[the two editing workflows](../../docs/en/symbolic.md#choose-an-editing-workflow).

Review definition revisions and evidence when changing an expression or its
meaning. This example's Python and YAML files are pinned by
`mceg/contracts/mceg.symbolic_equations.yaml`; changing either also requires
review of those recorded source-file pins.
