"""Check pinned equation definitions and Python declarations without execution."""

import ast
from pathlib import Path
from urllib.parse import urlsplit

from .schema_v03 import binding_digest, equation_digest


def _check(name, outcomes, message):
    statuses = {status for status, _ in outcomes}
    status = ("FAIL" if "FAIL" in statuses else
              "UNKNOWN" if not outcomes or "UNKNOWN" in statuses else "PASS")
    return {"name": name, "status": status, "message": message,
            "details": [detail for _, detail in outcomes]}


def _scope_nodes(body):
    """Visit one lexical scope, retaining nested definition nodes, not bodies."""
    for node in body:
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef, ast.Lambda)):
            yield from _scope_nodes(ast.iter_child_nodes(node))


def _attribute_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _attribute_name(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


def _function(tree, symbol, *, allow_decorators=False):
    """Locate an unambiguous lexical declaration, without resolving Python."""
    body = tree.body
    parts = symbol.split(".")
    for index, part in enumerate(parts):
        nodes = list(_scope_nodes(body))
        definitions = [node for node in nodes
                       if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                       and node.name == part]
        writes = [node for node in nodes
                  if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
                  and node.id == part]
        imports = [node for node in nodes if isinstance(node, ast.alias)
                   and (node.asname or node.name.split(".")[0]) in {part, "*"}]
        captures = any(
            (isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar))
             and node.name == part)
            or (isinstance(node, ast.MatchMapping) and node.rest == part)
            for node in nodes
        )
        selected = ".".join(parts[index:])
        attributes = any(
            isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del))
            and (selected == _attribute_name(node)
                 or selected.startswith((_attribute_name(node) or "\0") + "."))
            for node in nodes
        )
        dynamic = any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in {"exec", "globals", "locals", "setattr", "delattr"}
            for node in nodes
        )
        if dynamic or writes or imports or captures or attributes or len(definitions) > 1:
            return None, "UNKNOWN", f"Ambiguous or dynamically rebound declaration: {symbol}"
        if not definitions:
            return None, "FAIL", f"Function declaration not found: {symbol}"
        declaration = definitions[0]
        if declaration not in body or (declaration.decorator_list and not allow_decorators):
            return None, "UNKNOWN", f"Conditional or decorated declaration: {symbol}"
        if index < len(parts) - 1:
            body = declaration.body
        elif isinstance(declaration, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return declaration, "PASS", f"Function declaration found: {symbol}"
        else:
            return None, "FAIL", f"Selected declaration is not a function: {symbol}"


def _binding_source(binding, root, *, allow_decorators=False):
    label = f"{binding.id}: {binding.source}:{binding.symbol}"
    if root is None:
        return "UNKNOWN", f"{label}: no file root supplied"
    try:
        root = Path(root).resolve()
        source = Path(binding.source)
        if urlsplit(binding.source).scheme or source.is_absolute():
            return "FAIL", f"{label}: source must be a relative local path"
        path = (root / source).resolve()
        if not path.is_relative_to(root):
            return "FAIL", f"{label}: source resolves outside the file root"
        if not path.is_file():
            return "FAIL", f"{label}: source is missing or is not a regular file"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=binding.source)
    except (OSError, ValueError, RuntimeError, SyntaxError) as exc:
        return "FAIL", f"{label}: cannot inspect source: {exc}"
    declaration, status, message = _function(tree, binding.symbol, allow_decorators=allow_decorators)
    if declaration is None:
        return status, f"{label}: {message}"
    args = declaration.args
    parameters = {arg.arg for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]}
    parameters.update(arg.arg for arg in (args.vararg, args.kwarg) if arg is not None)
    missing = set(binding.arguments) - parameters
    if missing:
        return "FAIL", f"{label}: arguments not declared: {', '.join(sorted(missing))}"
    suffix = "; decorators are not evaluated" if allow_decorators else ""
    return "PASS", f"{label}: function and {len(binding.arguments)} mapped arguments declared{suffix}"


def equation_checks(contract, assessment, root=None):
    """Inspect one assessment's pins; never renew or reinterpret its support."""
    if assessment.kind != "evidence_support":
        return []
    claim = next(c for c in contract.claims
                 if (c.id, c.revision) == (assessment.claim, assessment.claim_revision))
    references = getattr(claim, "equations", [])
    checks = mathematical_model_checks(contract, assessment, claim)
    if not references:
        return checks
    equations = {(e.id, e.revision): e for e in contract.equations}
    equation_pins = {(p.id, p.revision): p.sha256
                     for p in assessment.equation_pins}
    definitions = []
    for reference in references:
        key = reference.id, reference.revision
        expected = equation_pins.get(key)
        label = f"{reference.id}@{reference.revision}"
        if expected is None:
            definitions.append(("UNKNOWN", f"{label}: no reviewed definition hash recorded"))
        elif equation_digest(equations[key]) != expected:
            definitions.append(("FAIL", f"{label}: definition hash differs from the recorded review"))
        else:
            definitions.append(("PASS", f"{label}: definition hash matches"))
    checks.append(_check("equation_definitions", definitions,
                         "Equation bytes and metadata, not mathematical equivalence"))
    if assessment.binding_pins:
        bindings = {binding.id: binding for binding in contract.bindings}
        pinned = [bindings[pin.id] for pin in assessment.binding_pins]
        outcomes = [("PASS", f"{pin.id}: binding hash matches")
                    if binding_digest(bindings[pin.id]) == pin.sha256 else
                    ("FAIL", f"{pin.id}: binding hash differs from the recorded review")
                    for pin in assessment.binding_pins]
        checks.append(_check("binding_definitions", outcomes,
                             "Recorded equation-to-code mappings, not implementation correctness"))
        checks.append(_check("binding_source", [
            _binding_source(b, root, allow_decorators=True) for b in pinned
        ], "Python declarations and arguments before decoration; no runtime signature, "
           "provider execution or constant evaluation"))
    return checks


def mathematical_model_checks(contract, assessment, claim):
    """Compare a whole declared model with its reviewed snapshot, without solving it."""
    references = getattr(claim, "mathematical_models", [])
    if not references:
        return []
    from .schema_v05 import mathematical_model_digest

    pins = {(pin.id, pin.revision): pin.sha256
            for pin in getattr(assessment, "mathematical_model_pins", [])}
    outcomes = []
    for reference in references:
        expected = pins.get((reference.id, reference.revision))
        label = f"{reference.id}@{reference.revision}"
        if expected is None:
            outcomes.append(("UNKNOWN", f"{label}: no reviewed model hash recorded"))
        elif mathematical_model_digest(contract, reference.id, reference.revision) != expected:
            outcomes.append(("FAIL", f"{label}: quantities, relations or connections changed since review"))
        else:
            outcomes.append(("PASS", f"{label}: mathematical model snapshot matches"))
    return [_check("mathematical_model_definitions", outcomes,
                   "Declared quantities, adopted relations and connections; not completeness or code equivalence")]
