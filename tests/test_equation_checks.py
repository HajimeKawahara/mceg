"""Equation integrity and source declarations are checks, not provider runs."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from mceg.equation_checks import _binding_source, equation_checks
from mceg.schema_v03 import ContractV03
from test_equation_schema import example_data


def statuses(contract, root=None):
    return {item["name"]: item["status"] for item in
            equation_checks(contract, contract.assessments[0], root)}


@pytest.fixture
def recorded(tmp_path):
    contract = ContractV03.model_validate(example_data())
    binding = contract.bindings[0]
    root = tmp_path / "provider"
    source = root / binding.source
    source.parent.mkdir(parents=True)
    parameters = ", ".join(binding.arguments)
    code = f"def {binding.symbol}({parameters}):\n    return 0\n"
    source.write_text(code)
    return contract, root, source, code


def test_selected_definitions_and_declarations_match(recorded):
    contract, root, _, _ = recorded
    before = contract.model_dump()
    assert statuses(contract, root) == {
        "equation_definitions": "PASS", "binding_definitions": "PASS", "binding_source": "PASS"}
    assert contract.model_dump() == before


@pytest.mark.parametrize("change", ["latex", "unit", "assumption"])
def test_changed_definition_is_detected_without_rewriting_support(recorded, change):
    contract, root, _, _ = recorded
    data = contract.model_dump()
    equation = data["equations"][0]
    if change == "latex":
        equation["latex"] += r" + 1"
    elif change == "unit":
        next(iter(equation["symbols"].values()))["unit"] = "changed unit"
    else:
        equation["assumptions"].append("An additional approximation.")
    changed = ContractV03.model_validate(data)
    assert statuses(changed, root)["equation_definitions"] == "FAIL"
    assert changed.assessments[0].status == "supported"
    assert changed.assessments[0] == contract.assessments[0]


def test_changed_argument_conversion_invalidates_binding_pin(recorded):
    contract, root, _, _ = recorded
    data = contract.model_dump()
    next(iter(data["bindings"][0]["arguments"].values()))["scale"] *= 2
    changed = ContractV03.model_validate(data)
    assert statuses(changed, root)["binding_definitions"] == "FAIL"
    assert changed.assessments[0] == contract.assessments[0]


def test_unpinned_unknown_definition_remains_unknown(recorded):
    contract, root, _, _ = recorded
    data = contract.model_dump()
    data["assessments"][0].update(status="unknown", equation_pins=[], binding_pins=[])
    assert statuses(ContractV03.model_validate(data), root) == {"equation_definitions": "UNKNOWN"}


def test_root_is_required_only_for_source_inspection(recorded):
    contract, _, _, _ = recorded
    assert statuses(contract) == {
        "equation_definitions": "PASS", "binding_definitions": "PASS", "binding_source": "UNKNOWN"}


def test_selection_does_not_inspect_unrelated_equations_or_bindings(recorded):
    contract, root, _, _ = recorded
    data = contract.model_dump()
    unrelated = deepcopy(data["equations"][0])
    unrelated.update(id="unrelated", latex="a = b")
    data["equations"].append(unrelated)
    binding = deepcopy(data["bindings"][0])
    binding.update(id="unrelated_function", equation={"id": "unrelated", "revision": "1"},
                   symbol="absent_function")
    data["bindings"].append(binding)
    data["subjects"][0]["implementation"]["entry_points"].append(
        f"{binding['source']}:absent_function")
    scoped = ContractV03.model_validate(data)
    assert set(statuses(scoped, root).values()) == {"PASS"}


@pytest.mark.parametrize("decoration", ["", "@replace_callable\n"])
def test_deleted_argument_is_not_hidden_by_kwargs(recorded, decoration):
    contract, root, source, _ = recorded
    source.write_text(decoration + f"def {contract.bindings[0].symbol}(**kwargs):\n    return 0\n")
    assert statuses(contract, root)["binding_source"] == "FAIL"
    assert contract.assessments[0].status == "supported"


@pytest.mark.parametrize("contents", ["def other(): pass\n", "this is invalid Python!\n", ""])
def test_missing_or_unparseable_function_fails(recorded, contents):
    contract, root, source, _ = recorded
    source.write_text(contents)
    assert statuses(contract, root)["binding_source"] == "FAIL"


def test_missing_source_fails(recorded):
    contract, root, source, _ = recorded
    source.unlink()
    assert statuses(contract, root)["binding_source"] == "FAIL"


def test_provider_code_is_not_executed(recorded, tmp_path):
    contract, root, source, code = recorded
    marker = tmp_path / "should-not-exist"
    source.write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n" + code)
    assert statuses(contract, root)["binding_source"] == "PASS"
    assert not marker.exists()


def test_symlink_cannot_escape_explicit_root(recorded, tmp_path):
    contract, root, source, code = recorded
    outside = tmp_path / "outside.py"
    outside.write_text(code)
    source.unlink()
    source.symlink_to(outside)
    assert statuses(contract, root)["binding_source"] == "FAIL"


@pytest.mark.parametrize("source", ["/tmp/outside.py", "../outside.py", "https://example.org/model.py"])
def test_source_checker_defensively_rejects_nonlocal_paths(recorded, source):
    contract, root, _, _ = recorded
    binding = contract.bindings[0].model_copy(update={"source": source})
    assert _binding_source(binding, root)[0] == "FAIL"


@pytest.mark.parametrize("mode", ["duplicate", "conditional", "assignment", "dynamic"])
def test_ambiguous_python_bindings_are_unknown(recorded, mode):
    contract, root, source, code = recorded
    name = contract.bindings[0].symbol
    if mode == "duplicate":
        code += code
    elif mode == "conditional":
        code = "if condition:\n" + "\n".join("    " + line for line in code.splitlines())
    elif mode == "assignment":
        code += f"{name} = replacement\n"
    elif mode == "dynamic":
        code += f"globals()[{name!r}] = replacement\n"
    source.write_text(code)
    assert statuses(contract, root)["binding_source"] == "UNKNOWN"


def test_decorated_binding_checks_original_arguments_without_running_wrapper(recorded, tmp_path):
    contract, root, source, code = recorded
    marker = tmp_path / "decorator-ran"
    source.write_text(
        "from pathlib import Path\n"
        "def replace_callable(function):\n"
        f"    Path({str(marker)!r}).touch()\n"
        "    return lambda: None\n\n"
        "@replace_callable\n" + code
    )
    before = contract.model_dump()
    check = next(item for item in equation_checks(contract, contract.assessments[0], root)
                 if item["name"] == "binding_source")
    assert check["status"] == "PASS"
    assert "before decoration" in check["message"]
    assert "no runtime signature" in check["message"]
    assert "decorators are not evaluated" in check["details"][0]
    assert not marker.exists()
    assert contract.model_dump() == before


def test_qualified_function_and_positional_keyword_only_arguments(tmp_path):
    source = tmp_path / "model.py"
    source.write_text("class Model:\n    def evaluate(self, radius, /, *, velocity):\n        return radius\n")
    binding = SimpleNamespace(id="method", source="model.py", symbol="Model.evaluate",
                              arguments={"radius": None, "velocity": None})
    assert _binding_source(binding, tmp_path)[0] == "PASS"
    source.write_text(source.read_text() + "Model.evaluate = other\n")
    assert _binding_source(binding, tmp_path)[0] == "UNKNOWN"


def test_decorated_class_and_method_only_expose_source_declarations(tmp_path):
    source = tmp_path / "model.py"
    source.write_text("raise RuntimeError('Do not import')\n"
                      "@replace_class\nclass Model:\n"
                      "    @replace_method\n"
                      "    def evaluate(self, radius, /, *, velocity):\n"
                      "        return radius\n")
    binding = SimpleNamespace(id="method", source="model.py", symbol="Model.evaluate",
                              arguments={"radius": None, "velocity": None})
    status, message = _binding_source(binding, tmp_path, allow_decorators=True)
    assert status == "PASS" and "decorators are not evaluated" in message
    binding.arguments["absent"] = None
    assert _binding_source(binding, tmp_path, allow_decorators=True)[0] == "FAIL"
    source.write_text(source.read_text() + "Model = replacement\n")
    assert _binding_source(binding, tmp_path, allow_decorators=True)[0] == "UNKNOWN"


def test_non_equation_and_condition_assessments_have_no_extra_checks(recorded):
    contract, root, _, _ = recorded
    data = deepcopy(contract.model_dump())
    data["claims"][0]["equations"] = []
    data["assessments"][0].update(equation_pins=[], binding_pins=[])
    assert statuses(ContractV03.model_validate(data), root) == {}
    assert equation_checks(contract, SimpleNamespace(kind="range_membership"), root) == []
