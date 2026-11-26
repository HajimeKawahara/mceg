"""The adopted symbolic definition controls display and review identity."""

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

from pydantic import ValidationError
import pytest

sp = pytest.importorskip("sympy")

from mceg import documentation as docs
from mceg.check import check_contract
from mceg.decisions import decision_basis_checks
from mceg.equations import equation_latex, render_equations
from mceg.mathematical import model_graph, render_model_tex
from mceg.readiness import check_readiness
from mceg.schema_v03 import equation_digest
from mceg.schema_v04 import decision_basis_digest
from mceg.schema_v05 import ContractV05, mathematical_model_digest
from mceg.schema_v06 import ContractV06, Equation
from mceg.symbolic import from_sympy, to_sympy
from mceg.validator import load_contract
from test_mathematical_lifecycle import statuses, write_model
from test_mathematical_schema import mathematical_data


def source(factor=4):
    n, mdot, r, v, mass = sp.symbols("n_h mass_loss radius velocity proton_mass")
    return from_sympy(sp.Eq(n, mdot / (factor * sp.pi * r**2 * v * mass)))


def symbolic_data():
    data = mathematical_data()
    data["schema_version"] = "0.6"
    data["equations"][0]["sympy"] = source().model_dump()
    data["equations"][0]["latex"] = "STALE DISPLAY"
    return data


def test_source_priority_and_roundtrip_preserve_only_the_canonical_definition():
    contract = ContractV06.model_validate(symbolic_data())
    equation = contract.equations[0]
    dumped = contract.model_dump(mode="json")
    assert "latex" not in dumped["equations"][0]
    assert "STALE DISPLAY" not in render_equations(contract)
    assert "STALE DISPLAY" not in render_model_tex(contract, "wind")
    assert r"n_{\mathrm H}" in equation_latex(equation)
    restored = ContractV06.model_validate_json(contract.model_dump_json())
    assert to_sympy(restored.equations[0].sympy) == to_sympy(equation.sympy)
    assert equation_digest(restored.equations[0]) == equation_digest(equation)
    graph = model_graph(contract, "wind")
    relation = next(node for node in graph["nodes"] if node["type"] == "relation")
    assert relation["display_latex"] == equation_latex(equation)
    assert "latex" not in relation["equation"]


def test_latex_only_upgrade_preserves_all_existing_definition_and_review_digests():
    data = mathematical_data()
    old = ContractV05.model_validate(data)
    data["schema_version"] = "0.6"
    new = ContractV06.model_validate(data)
    assert new.equations[0].model_dump() == old.equations[0].model_dump()
    assert equation_digest(new.equations[0]) == equation_digest(old.equations[0])
    assert mathematical_model_digest(new, "wind", "1") == mathematical_model_digest(old, "wind", "1")
    assert decision_basis_digest(new, "assessment", "formulation_review") == (
        decision_basis_digest(old, "assessment", "formulation_review"))


@pytest.mark.parametrize("change,match", [
    (lambda e: (e.pop("sympy"), e.pop("latex")), "needs a SymPy definition or LaTeX"),
    (lambda e: e["symbols"].pop("velocity"), "Undeclared SymPy"),
    (lambda e: e["sympy"].update(expression="__import__('os')"), "Unsupported SymPy"),
    (lambda e: e["sympy"].update(format="python"), "sympy-srepr-v1"),
])
def test_invalid_symbolic_source_never_falls_back_to_latex(change, match):
    data = symbolic_data()["equations"][0]
    change(data)
    with pytest.raises(ValidationError, match=match):
        Equation.model_validate(data)


def test_unknown_function_heads_and_bound_coordinates_require_declared_meaning():
    r = sp.Symbol("radius")
    expression = sp.Eq(sp.Derivative(sp.Function("n_h")(r), r), sp.Symbol("missing"))
    data = symbolic_data()["equations"][0]
    data["sympy"] = from_sympy(expression).model_dump()
    with pytest.raises(ValidationError, match="missing"):
        Equation.model_validate(data)


def test_old_schema_does_not_accept_symbolic_fields():
    data = symbolic_data()
    data["schema_version"] = "0.5"
    with pytest.raises(ValidationError):
        ContractV05.model_validate(data)


def write_symbolic_model(tmp_path):
    path, use_path, data = write_model(tmp_path)
    data["schema_version"] = "0.6"
    data["equations"][0]["sympy"] = source().model_dump()
    data["equations"][0]["latex"] = "STALE DISPLAY"
    contract = ContractV06.model_validate(data)
    assessment = data["assessments"][0]
    assessment["equation_pins"][0]["sha256"] = equation_digest(contract.equations[0])
    assessment["mathematical_model_pins"][0]["sha256"] = mathematical_model_digest(contract, "wind", "1")
    contract = ContractV06.model_validate(data)
    snapshot = decision_basis_digest(contract, "assessment", "formulation_review")
    data["decisions"][0]["basis"][0]["sha256"] = snapshot
    path.write_text(json.dumps(data))
    use = json.loads(use_path.read_text())
    use["requirements"][0]["sha256"] = snapshot
    use_path.write_text(json.dumps(use))
    return path, use_path, data


@pytest.mark.parametrize("change,stale", [
    (lambda e: e.update(latex="ANOTHER IGNORED DISPLAY"), False),
    (lambda e: e.update(sympy=source(8).model_dump()), True),
    (lambda e: e["assumptions"].append("An additional physical assumption."), True),
    (lambda e: e["symbols"]["velocity"].update(description="A different velocity."), True),
])
def test_source_changes_propagate_to_assessment_decision_and_use(tmp_path, change, stale):
    path, use_path, data = write_symbolic_model(tmp_path)
    assert check_readiness(use_path, root=tmp_path)["ready"]
    previous = deepcopy(data["assessments"])
    change(data["equations"][0])
    path.write_text(json.dumps(data))
    before_bytes = path.read_bytes()
    contract = load_contract(path)
    report = check_contract(path, {}, "formulation_review", root=tmp_path)
    checks = statuses(report, "checks")
    assert checks["equation_definitions"] == ("FAIL" if stale else "PASS")
    assert checks["mathematical_model_definitions"] == ("FAIL" if stale else "PASS")
    assert checks["recorded_support"] == "PASS"
    assert any(c["status"] == "FAIL" for c in decision_basis_checks(contract, contract.decisions[0])) == stale
    assert check_readiness(use_path, root=tmp_path)["ready"] is not stale
    assert json.loads(path.read_text())["assessments"] == previous
    assert path.read_bytes() == before_bytes


def test_generated_documentation_uses_sympy_and_labels_the_chosen_source(tmp_path):
    path, _, _ = write_symbolic_model(tmp_path)
    catalog = docs.Catalog(tmp_path / "generated")
    entry = catalog.add("fixture", tmp_path, path.name)
    records = docs.records_page(catalog, entry)
    assert "STALE DISPLAY" not in records
    assert "Definition source: SymPy (LaTeX generated)." in records
    assert equation_latex(entry.contract.equations[0]) in records


def test_base_install_reads_latex_but_rejects_symbolic_without_optional_backend(tmp_path):
    plain = tmp_path / "plain.json"
    plain.write_text(json.dumps(mathematical_data()))
    symbolic = tmp_path / "symbolic.json"
    symbolic.write_text(json.dumps(symbolic_data()))
    code = """
import sys
class NoSympy:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'sympy' or fullname.startswith('sympy.'):
            raise ImportError('backend deliberately unavailable')
sys.meta_path.insert(0, NoSympy())
from mceg import load_contract
from mceg.equations import render_equations
assert render_equations(load_contract(sys.argv[1]))
assert 'sympy' not in sys.modules
try:
    load_contract(sys.argv[2])
except ValueError as exc:
    assert 'mceg[symbolic]' in str(exc), str(exc)
else:
    raise AssertionError('Must not silently use the stale LaTeX')
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    result = subprocess.run([sys.executable, "-c", code, str(plain), str(symbolic)],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
