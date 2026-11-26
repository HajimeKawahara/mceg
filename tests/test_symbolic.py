"""Round trips and trust boundaries for optional symbolic model definitions."""

from __future__ import annotations

import builtins

import pytest

from mceg.symbolic import (
    MAX_AST_NODES,
    SympySource,
    from_sympy,
    latex_from_sympy,
    symbolic_names,
    to_sympy,
)


sp = pytest.importorskip("sympy")


def test_equation_and_assumptions_round_trip():
    pressure, density, gas_constant, temperature = sp.symbols("P rho R T", positive=True)
    equation = sp.Eq(pressure, density * gas_constant * temperature, evaluate=False)
    source = from_sympy(equation)
    restored = to_sympy(SympySource.model_validate_json(source.model_dump_json()))
    assert restored == equation
    assert restored.lhs.is_positive is True
    assert symbolic_names(restored) == {"P", "rho", "R", "T"}


def test_unevaluated_equation_and_arithmetic_are_preserved():
    x = sp.Symbol("x")
    for expression in [sp.Eq(x, x, evaluate=False), sp.Add(x, x, evaluate=False),
                       sp.Pow(sp.Integer(2), sp.Integer(1_000_000), evaluate=False)]:
        restored = to_sympy(from_sympy(expression))
        assert sp.srepr(restored) == sp.srepr(expression)


def test_undefined_fields_derivatives_and_bound_variables():
    z = sp.Symbol("z", real=True)
    pressure = sp.Function("P")(z)
    density = sp.Function("rho")(z)
    gravity = sp.Symbol("g", positive=True)
    equation = sp.Eq(sp.Derivative(pressure, z, evaluate=False), -density * gravity, evaluate=False)
    assert to_sympy(from_sympy(equation)) == equation
    assert symbolic_names(equation) == {"P", "rho", "z", "g"}
    integral = sp.Integral(pressure, (z, 0, 1))
    assert to_sympy(from_sympy(integral)) == integral
    assert symbolic_names(integral) == {"P", "z"}


def test_sum_substitution_and_indexed_fields():
    i, n = sp.symbols("i n", integer=True)
    array = sp.IndexedBase("A")
    expression = sp.Sum(array[i], (i, 1, n))
    assert to_sympy(from_sympy(expression)) == expression
    assert symbolic_names(expression) == {"A", "i", "n"}
    substitution = sp.Subs(sp.Function("T")(i), i, n)
    assert to_sympy(from_sympy(substitution)) == substitution


def test_float_precision_and_elementary_functions():
    x = sp.Symbol("x")
    for expression in [sp.Float("1.02", precision=80), sp.exp(x), sp.log(x), sp.sin(x),
                       sp.pi, sp.oo, sp.Rational(-3, 5)]:
        assert to_sympy(from_sympy(expression)) == expression


def test_latex_is_derived_with_declared_symbol_labels():
    n, t = sp.symbols("n_total T")
    source = from_sympy(sp.Eq(n, t, evaluate=False))
    rendered = latex_from_sympy(source, {"n_total": {"latex": r"n_{\mathrm{H}}"}})
    assert rendered == r"n_{\mathrm{H}} = T"


def test_field_labels_are_preserved_in_derivatives_and_powers():
    r = sp.Symbol("r")
    a2 = sp.Function("a2")(r)
    temperature = sp.Function("T_eff")(r)
    equation = sp.Eq(sp.Derivative(a2, r), temperature**2, evaluate=False)
    source = from_sympy(equation)
    rendered = latex_from_sympy(source, {
        "a2": {"latex": "a^2"},
        "T_eff": {"latex": r"T_{\rm eff}"},
        "r": {"latex": "z"},
    })
    assert r"\frac{d}{d z} a^2{\left(z \right)}" in rendered
    assert r"\left(T_{\rm eff}{\left(z \right)}\right)^{2}" in rendered
    assert "a_{2}" not in rendered
    assert source == from_sympy(equation)


@pytest.mark.parametrize("expression", [
    sp.Eq(sp.Symbol("T"), sp.Symbol("T", positive=True), evaluate=False),
    sp.Eq(sp.Symbol("T"), sp.Function("T")(sp.Symbol("r")), evaluate=False),
    sp.Eq(sp.Function("T")(sp.Symbol("r")),
          sp.Function("T", positive=True)(sp.Symbol("r")), evaluate=False),
])
def test_ambiguous_symbol_names_are_rejected(expression):
    with pytest.raises(ValueError, match="Distinct SymPy quantities share a name"):
        from_sympy(expression)


def test_repeated_function_head_has_one_identity():
    r, s = sp.symbols("r s")
    expression = sp.Eq(sp.Function("T")(r), sp.Function("T")(s), evaluate=False)
    assert symbolic_names(to_sympy(from_sympy(expression))) == {"T", "r", "s"}


def test_srepr_cannot_silently_drop_function_assumptions():
    expression = sp.Function("T", positive=True)(sp.Symbol("r"))
    with pytest.raises(ValueError, match="cannot round trip"):
        from_sympy(expression)


def test_srepr_commutative_order_does_not_reject_ordinary_quotients():
    r = sp.Symbol("r")
    equation = sp.Eq(sp.Function("T_eff")(r),
                     sp.Function("T")(r) / sp.Function("mu")(r), evaluate=False)
    source = from_sympy(equation)
    assert sp.srepr(to_sympy(source)) == sp.srepr(equation)


@pytest.mark.parametrize("expression", [
    "__import__('os').system('false')",
    "Symbol.__class__",
    "Symbol('x')[0]",
    "[Symbol('x') for x in range(2)]",
    "(lambda: Symbol('x'))()",
    "Add('x', Integer(1))",
    "exp('x')",
    "Symbol('x', malicious=True)",
    "Symbol('x', positive='true')",
    "Integer('1')",
    "Rational(1, 0)",
    "Float('nan')",
    "Float('1e10001')",
    "Float('1.0', precision=100000)",
    "Function('f')",
    "Symbol('x')()",
    "MatrixSymbol('M', Integer(2), Integer(2))",
    "Pow(Integer(2), Integer(10), evaluate=True)",
    "Derivative(Symbol('x'), Tuple(), Integer(1))",
    "Indexed(Integer(1))",
    "Add(Tuple(), Integer(1))",
])
def test_unsupported_or_executable_source_is_rejected(expression):
    with pytest.raises(ValueError):
        to_sympy(SympySource(expression=expression))


def test_source_never_executes_python(tmp_path):
    target = tmp_path / "should-not-exist"
    source = SympySource(expression=f"__import__('pathlib').Path({str(target)!r}).touch()")
    with pytest.raises(ValueError):
        to_sympy(source)
    assert not target.exists()


def test_tree_and_literal_limits():
    expressions = ["sin(" * 80 + "Symbol('x')" + ")" * 80,
                   "Add(" + ",".join(["Integer(1)"] * MAX_AST_NODES) + ")",
                   "Integer(" + "9" * 300 + ")"]
    for expression in expressions:
        with pytest.raises(ValueError):
            to_sympy(SympySource(expression=expression))


def test_authoring_requires_actual_sympy_objects():
    for value in ["x + 1", 1, {"expression": "Symbol('x')"}]:
        with pytest.raises(TypeError):
            from_sympy(value)


def test_missing_backend_has_actionable_error(monkeypatch):
    original = builtins.__import__

    def without_sympy(name, *args, **kwargs):
        if name == "sympy":
            raise ImportError("not installed")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_sympy)
    with pytest.raises(ValueError, match=r"install mceg\[symbolic\]"):
        to_sympy(SympySource(expression="Symbol('x')"))
