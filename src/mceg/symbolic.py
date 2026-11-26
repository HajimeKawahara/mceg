"""Optional SymPy authoring with a bounded, non-evaluating srepr decoder.

The stored format is deliberately a subset of SymPy's constructors, not Python
source or a general-purpose SymPy parser. Unsupported mathematics can keep its
LaTeX definition instead. Decoding constructs expressions; it does not solve,
simplify, execute providers, or certify their scientific meaning.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Literal

from pydantic import Field

from .schema import Text
from .schema_v02 import Record


MAX_SOURCE_LENGTH = 65_536
MAX_AST_NODES = 4_096
MAX_AST_DEPTH = 64
MAX_LITERAL_LENGTH = 256
MAX_FLOAT_PRECISION = 1_024

_ASSUMPTIONS = frozenset(
    "commutative complex extended_real real imaginary finite infinite integer "
    "noninteger rational irrational algebraic transcendental positive negative "
    "nonpositive nonnegative zero nonzero extended_positive extended_negative "
    "extended_nonpositive extended_nonnegative extended_nonzero even odd prime "
    "composite hermitian antihermitian polar".split()
)
_CONSTANTS = frozenset("pi E I oo zoo nan EulerGamma Catalan GoldenRatio true false".split())
_UNEVALUATED = frozenset(
    "Add Mul Pow Equality Unequality StrictLessThan LessThan StrictGreaterThan "
    "GreaterThan Derivative exp log sin cos tan asin acos atan sinh cosh tanh "
    "Abs Min Max And Or Not".split()
)
_CONSTRUCTORS = _UNEVALUATED | frozenset("Tuple Integral Sum Subs IndexedBase Indexed".split())
_FLOAT = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE]([+-]?[0-9]+))?\Z")


class SympySource(Record):
    """Portable expression tree emitted from an actual SymPy expression."""

    format: Literal["sympy-srepr-v1"] = "sympy-srepr-v1"
    expression: Text = Field(max_length=MAX_SOURCE_LENGTH)


def _sympy() -> Any:
    try:
        import sympy
    except ImportError as exc:
        raise ValueError(
            "SymPy definitions require the optional backend; install mceg[symbolic]. "
            "A stored LaTeX display cannot replace the authoritative SymPy source."
        ) from exc
    return sympy


def _check_tree(tree: ast.AST) -> None:
    pending = [(tree, 0)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > MAX_AST_NODES or depth > MAX_AST_DEPTH:
            raise ValueError("SymPy source exceeds the expression tree limits")
        pending.extend((child, depth + 1) for child in ast.iter_child_nodes(node))


class _Decoder:
    def __init__(self, sp: Any):
        self.sp = sp

    @staticmethod
    def _name(value: Any) -> str:
        if not isinstance(value, str) or not value or len(value) > MAX_LITERAL_LENGTH:
            raise ValueError("A SymPy name must be a short, nonempty string")
        return value

    def _assumptions(self, node: ast.Call) -> dict[str, bool]:
        result = {}
        for kw in node.keywords:
            if kw.arg not in _ASSUMPTIONS or kw.arg in result:
                raise ValueError("Only explicit boolean SymPy assumptions are allowed")
            value = self.decode(kw.value)
            if type(value) is not bool:
                raise ValueError("SymPy assumptions must be boolean literals")
            result[kw.arg] = value
        return result

    def _function(self, node: ast.Call) -> Any:
        if len(node.args) != 1 or node.keywords:
            raise ValueError("Function requires one name; function assumptions are unsupported")
        return self.sp.Function(self._name(self.decode(node.args[0])))

    def _basic_args(self, node: ast.Call) -> list[Any]:
        if node.keywords:
            raise ValueError("Unexpected keyword in SymPy expression")
        args = [self.decode(arg) for arg in node.args]
        if not all(isinstance(arg, self.sp.Basic) for arg in args):
            raise ValueError("Expression arguments must be SymPy nodes, not Python literals")
        return args

    def decode(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            value = node.value
            if type(value) is bool:
                return value
            if type(value) is int and len(str(abs(value))) <= MAX_LITERAL_LENGTH:
                return value
            if isinstance(value, str) and len(value) <= MAX_LITERAL_LENGTH:
                return value
            raise ValueError("Unsupported or oversized SymPy literal")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            value = self.decode(node.operand)
            if type(value) is int:
                return -value
            raise ValueError("Unary minus is only allowed on integer literals")
        if isinstance(node, ast.Name) and node.id in _CONSTANTS:
            return getattr(self.sp, node.id)
        if not isinstance(node, ast.Call):
            raise ValueError("Only whitelisted SymPy constructor expressions are allowed")
        if isinstance(node.func, ast.Call):
            inner = node.func
            if not isinstance(inner.func, ast.Name) or inner.func.id != "Function":
                raise ValueError("Only an undefined Function may be applied as a nested call")
            return self._function(inner)(*self._basic_args(node))
        if not isinstance(node.func, ast.Name):
            raise ValueError("Attributes and executable call targets are not allowed")
        name = node.func.id
        if name == "Symbol":
            if len(node.args) != 1:
                raise ValueError("Symbol requires one name")
            return self.sp.Symbol(self._name(self.decode(node.args[0])), **self._assumptions(node))
        if name in {"Integer", "Rational"}:
            args = [self.decode(arg) for arg in node.args]
            if node.keywords or len(args) != (1 if name == "Integer" else 2):
                raise ValueError(f"Invalid {name} constructor")
            if not all(type(arg) is int for arg in args):
                raise ValueError(f"{name} arguments must be integer literals")
            if name == "Rational" and args[1] == 0:
                raise ValueError("A Rational denominator must be nonzero")
            return getattr(self.sp, name)(*args)
        if name == "Float":
            if len(node.args) != 1 or len(node.keywords) > 1:
                raise ValueError("Float requires one decimal string and optional precision")
            value = self.decode(node.args[0])
            match = _FLOAT.fullmatch(value) if isinstance(value, str) else None
            if match is None or (match.group(1) and abs(int(match.group(1))) > 10_000):
                raise ValueError("Float requires a bounded decimal literal")
            kwargs = {}
            for kw in node.keywords:
                precision = self.decode(kw.value)
                if kw.arg != "precision" or type(precision) is not int or not 1 <= precision <= MAX_FLOAT_PRECISION:
                    raise ValueError("Float precision is outside the supported range")
                kwargs["precision"] = precision
            return self.sp.Float(value, **kwargs)
        if name not in _CONSTRUCTORS:
            raise ValueError(f"Unsupported SymPy constructor: {name}")
        args = self._basic_args(node)
        if name in {"Add", "Mul", "Pow"} and not all(isinstance(arg, self.sp.Expr) for arg in args):
            raise ValueError(f"{name} requires scalar expression arguments")
        if name == "Indexed" and len(args) < 2:
            raise ValueError("Indexed requires a base and at least one index")
        kwargs = {"evaluate": False} if name in _UNEVALUATED else {}
        return getattr(self.sp, name)(*args, **kwargs)


def to_sympy(source: SympySource) -> Any:
    """Decode supported constructors without executing stored Python text."""
    if not isinstance(source, SympySource):
        raise TypeError("Expected a SympySource record")
    if len(source.expression) > MAX_SOURCE_LENGTH:
        raise ValueError("SymPy source exceeds the length limit")
    sp = _sympy()
    try:
        tree = ast.parse(source.expression, mode="eval")
        _check_tree(tree)
        expression = _Decoder(sp).decode(tree.body)
        if not isinstance(expression, sp.Basic):
            raise ValueError("The SymPy source must produce a symbolic expression")
        symbolic_names(expression)
        return expression
    except (SyntaxError, TypeError, AttributeError, IndexError, OverflowError, RecursionError) as exc:
        raise ValueError(f"Invalid or unsupported SymPy source: {exc}") from exc


def from_sympy(expression: Any) -> SympySource:
    """Serialize an actual expression, rejecting unsupported constructor trees."""
    sp = _sympy()
    from sympy.core.function import AppliedUndef

    if not isinstance(expression, sp.Basic):
        raise TypeError("from_sympy requires an actual SymPy expression, not text")
    symbolic_names(expression)
    # SymPy's srepr omits undefined-function assumptions (unlike Symbol
    # assumptions). Reject them rather than silently changing the definition.
    if any(function.func._kwargs for function in expression.atoms(AppliedUndef)):
        raise ValueError("Function assumptions cannot round trip through SymPy srepr")
    source = SympySource(expression=sp.srepr(expression))
    # srepr sorts commutative Add/Mul arguments even when their internal .args
    # have a different order. Compare the representation rather than .args.
    if sp.srepr(to_sympy(source)) != source.expression:
        raise ValueError(
            "This expression cannot round trip through the supported SymPy format. "
            "Unsupported function assumptions or constructor behavior may be responsible."
        )
    return source


def symbolic_names(expression: Any) -> set[str]:
    """Include declared symbols, bound coordinates, and undefined function names."""
    sp = _sympy()
    from sympy.core.function import AppliedUndef

    if not isinstance(expression, sp.Basic):
        raise TypeError("Expected a SymPy expression")
    identities: dict[str, set[Any]] = {}
    for symbol in expression.atoms(sp.Symbol):
        identities.setdefault(str(symbol.name), set()).add(symbol)
    for function in expression.atoms(AppliedUndef):
        identities.setdefault(str(function.func), set()).add(function.func)
    ambiguous = sorted(name for name, values in identities.items() if len(values) > 1)
    if ambiguous:
        raise ValueError(
            "Distinct SymPy quantities share a name: " + ", ".join(ambiguous)
            + ". Use different names or consistent assumptions."
        )
    return set(identities)


def latex_from_sympy(source: SympySource, symbols: dict[str, Any] | None = None) -> str:
    """Derive display LaTeX with declared labels for symbols and field heads."""
    sp = _sympy()
    from sympy.core.function import AppliedUndef
    from sympy.printing.latex import LatexPrinter

    expression = to_sympy(source)
    labels = {name: metadata.get("latex") if isinstance(metadata, dict) else metadata.latex
              for name, metadata in (symbols or {}).items()}
    symbol_names = {symbol: labels[symbol.name] for symbol in expression.atoms(sp.Symbol)
                    if labels.get(symbol.name)}

    class DeclaredLabelPrinter(LatexPrinter):
        def _print_Function(self, expr, exp=None):
            label = labels.get(str(expr.func)) if isinstance(expr, AppliedUndef) else None
            if not label:
                return super()._print_Function(expr, exp)
            arguments = ",".join(self._print(argument) for argument in expr.args)
            rendered = label + r"{\left(" + arguments + r" \right)}"
            if exp is not None:
                rendered = r"\left(" + rendered + r"\right)^{" + exp + "}"
            return rendered

    return DeclaredLabelPrinter({"symbol_names": symbol_names}).doprint(expression)
