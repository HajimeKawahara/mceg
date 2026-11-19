"""Equation definitions are distinct from scoped, historically pinned judgments."""

from copy import deepcopy

from pydantic import ValidationError
import pytest

from mceg.schema_v02 import ContractV02
from mceg.schema_v03 import (ContractV03, Equation, EquationBinding, binding_digest,
                             equation_digest)


def example_data():
    """A small authored correspondence, without a claimed numerical execution."""
    implementation = {
        "repository": "https://example.org/provider", "revision": "fixture-v1",
        "entry_points": ["src/provider.py:hydrogen_nuclei_density"],
    }
    equation = {
        "id": "continuity", "revision": "1",
        "latex": r"n_{\mathrm H}=\frac{\dot M}{4\pi r^2v m_{\mathrm p}}",
        "description": "Hydrogen nuclei density in a steady spherical flow.",
        "scope": "Pure hydrogen; positive radius and outward velocity.",
        "symbols": {
            "n_h": {"latex": r"n_{\mathrm H}", "description": "Hydrogen nuclei density", "unit": "cm^-3"},
            "mass_loss": {"latex": r"\dot M", "description": "Mass-loss rate", "unit": "g s^-1"},
            "radius": {"latex": "r", "description": "Radius", "unit": "cm"},
            "velocity": {"latex": "v", "description": "Outward velocity", "unit": "cm s^-1"},
            "proton_mass": {"latex": r"m_{\mathrm p}", "description": "Mass per nucleus", "unit": "g"},
        },
        "assumptions": ["Electron mass is neglected."], "evidence": ["derivation"],
    }
    binding = {
        "id": "continuity_function", "equation": {"id": "continuity", "revision": "1"},
        "subject": "implementation", "source": "src/provider.py",
        "symbol": "hydrogen_nuclei_density",
        "arguments": {
            "radius_cm": {"symbol": "radius"},
            "velocity_kms": {"symbol": "velocity", "scale": 100000.0},
            "mass_loss_g_s": {"symbol": "mass_loss"},
        },
        "result": "n_h", "constants": {"proton_mass": "PROTON_MASS_CGS"},
        "note": "The velocity argument is converted from km/s to cm/s.",
    }
    return {
        "schema_version": "0.3",
        "model": {"id": "example.continuity", "name": "Hydrogen continuity",
                  "description": "An equation-to-function correspondence example.",
                  "implementation": implementation},
        "assumptions": [],
        "domains": [{"kind": "scientific_applicability", "status": "unknown",
                     "description": "No atmospheric accuracy assessment is recorded.",
                     "conditions": [], "evidence": ["derivation"]}],
        "claims": [{"id": "equation_implementation", "revision": "1", "kind": "theoretical",
                    "statement": "The pinned function expresses the recorded continuity law.",
                    "scope": "Authored algebra and source correspondence only.",
                    "equations": [{"id": "continuity", "revision": "1"}]}],
        "evidence": [{"id": "derivation", "kind": "theory",
                      "summary": "Solve spherical mass conservation for hydrogen density.",
                      "sources": ["doc/model.tex"], "scope": "Continuity algebra only.",
                      "provenance": {"role": "primary", "location": "Equation continuity",
                                     "inspection": "inspected", "note": "Authored example derivation."}}],
        "limitations": [],
        "subjects": [{"id": "implementation", "implementation": deepcopy(implementation),
                      "selected_files": {"src/provider.py": "0" * 64}}],
        "contexts": [{"id": "review", "scope": "Illustrative authored review."}],
        "equations": [equation], "bindings": [binding],
        "assessments": [{"id": "formulation_review", "kind": "evidence_support",
                         "subject": "implementation", "context": "review",
                         "claim": "equation_implementation", "claim_revision": "1",
                         "method": {"id": "source_review", "revision": "1",
                                    "description": "Compare algebra and declared units."},
                         "evidence": ["derivation"], "reasons": ["An authored example; no solver was executed."],
                         "status": "supported", "origin": "reviewed",
                         "equation_pins": [{"id": "continuity", "revision": "1",
                                            "sha256": equation_digest(Equation.model_validate(equation))}],
                         "binding_pins": [{"id": "continuity_function",
                                           "sha256": binding_digest(EquationBinding.model_validate(binding))}]}],
    }


def test_equation_contract_retains_v02_evidence_semantics():
    contract = ContractV03.model_validate(example_data())
    assert isinstance(contract, ContractV02)
    assert contract.assessments[0].status == "supported"
    assert "status" not in contract.equations[0].model_dump()
    assert contract.bindings[0].arguments["velocity_kms"].scale == 100000.0
    assert contract.model_dump()["schema_version"] == "0.3"


@pytest.mark.parametrize("change", [
    lambda d: d["equations"].append(deepcopy(d["equations"][0])),
    lambda d: d["bindings"].append(deepcopy(d["bindings"][0])),
    lambda d: d["equations"][0].update(id=r"bad\label"),
    lambda d: d["equations"][0].update(revision="1 2"),
    lambda d: d["equations"][0].update(status="supported"),
    lambda d: d["equations"][0].update(evidence=["absent"]),
    lambda d: d["equations"][0].update(evidence=["derivation", "derivation"]),
    lambda d: d["claims"][0]["equations"][0].update(revision="2"),
    lambda d: d["claims"][0]["equations"].append({"id": "continuity", "revision": "1"}),
    lambda d: d["bindings"][0]["equation"].update(revision="2"),
    lambda d: d["bindings"][0].update(subject="absent"),
    lambda d: d["bindings"][0].update(source="../provider.py"),
    lambda d: d["bindings"][0].update(source="/src/provider.py"),
    lambda d: d["bindings"][0].update(source="src/./provider.py"),
    lambda d: d["bindings"][0].update(source=r"src\provider.py"),
    lambda d: d["bindings"][0].update(source="src/provider.txt"),
    lambda d: d["bindings"][0].update(source="src/unpinned.py"),
    lambda d: d["bindings"][0].update(symbol="unknown_function"),
    lambda d: d["bindings"][0].update(symbol="f()"),
    lambda d: d["bindings"][0]["arguments"]["radius_cm"].update(symbol="unknown"),
    lambda d: d["bindings"][0]["arguments"]["velocity_kms"].update(scale=0.0),
    lambda d: d["bindings"][0]["arguments"]["velocity_kms"].update(scale=float("inf")),
    lambda d: d["bindings"][0]["arguments"]["velocity_kms"].update(offset=float("nan")),
    lambda d: d["bindings"][0].update(result="unknown"),
    lambda d: d["bindings"][0].update(constants={"unknown": "CONST"}),
    lambda d: d["assessments"][0].update(equation_pins=[]),
    lambda d: d["assessments"][0]["equation_pins"][0].update(revision="2"),
    lambda d: d["assessments"][0]["equation_pins"].append(deepcopy(d["assessments"][0]["equation_pins"][0])),
    lambda d: d["assessments"][0]["binding_pins"][0].update(id="absent"),
    lambda d: d["assessments"][0]["binding_pins"].append(deepcopy(d["assessments"][0]["binding_pins"][0])),
    lambda d: d["assessments"][0].update(evidence=[]),
])
def test_invalid_definitions_and_correspondences_are_rejected(change):
    data = example_data()
    change(data)
    with pytest.raises(ValidationError):
        ContractV03.model_validate(data)


def test_binding_pin_cannot_reuse_another_subject():
    data = example_data()
    other = deepcopy(data["subjects"][0])
    other["id"] = "different_implementation"
    data["subjects"].append(other)
    data["assessments"][0]["subject"] = other["id"]
    with pytest.raises(ValidationError, match="Pinned binding"):
        ContractV03.model_validate(data)


def test_unknown_assessment_may_leave_equations_unreviewed():
    data = example_data()
    data["assessments"][0].update(status="unknown", equation_pins=[], binding_pins=[])
    contract = ContractV03.model_validate(data)
    assert contract.assessments[0].status == "unknown"
    data["assessments"][0]["binding_pins"] = example_data()["assessments"][0]["binding_pins"]
    with pytest.raises(ValidationError, match="Pinned binding"):
        ContractV03.model_validate(data)


def test_unbound_equations_do_not_require_an_implementation_claim():
    data = example_data()
    data["bindings"] = []
    data["assessments"] = []
    data["equations"][0]["evidence"] = []
    contract = ContractV03.model_validate(data)
    assert not contract.assessments
    assert not contract.bindings


def test_changed_definitions_stay_inspectable_with_historical_pins():
    data = example_data()
    old_equation_pin = data["assessments"][0]["equation_pins"][0]["sha256"]
    old_binding_pin = data["assessments"][0]["binding_pins"][0]["sha256"]
    data["equations"][0]["symbols"]["velocity"]["unit"] = "km s^-1"
    data["bindings"][0]["arguments"]["velocity_kms"]["scale"] = 1.0
    contract = ContractV03.model_validate(data)
    assert equation_digest(contract.equations[0]) != old_equation_pin
    assert binding_digest(contract.bindings[0]) != old_binding_pin
    assert contract.assessments[0].equation_pins[0].sha256 == old_equation_pin
    assert contract.assessments[0].status == "supported"


@pytest.mark.parametrize("change", [
    lambda e: e.update(latex="n=0"),
    lambda e: e["symbols"]["velocity"].update(description="Inward velocity"),
    lambda e: e["symbols"]["velocity"].update(unit="km s^-1"),
    lambda e: e["assumptions"].append("Ion mass is doubled."),
    lambda e: e.update(scope="A different domain."),
])
def test_equation_digest_covers_definition_not_just_formula(change):
    equation = example_data()["equations"][0]
    expected = equation_digest(Equation.model_validate(equation))
    change(equation)
    assert equation_digest(Equation.model_validate(equation)) != expected


def test_digest_uses_validated_defaults_and_stable_mapping_order():
    data = example_data()["bindings"][0]
    original = EquationBinding.model_validate(data)
    data["arguments"] = dict(reversed(list(data["arguments"].items())))
    data["arguments"]["radius_cm"].update(scale=1.0, offset=0.0)
    assert binding_digest(EquationBinding.model_validate(data)) == binding_digest(original)


def test_v02_reader_rejects_v03_and_new_fields():
    data = example_data()
    with pytest.raises(ValidationError):
        ContractV02.model_validate(data)
    data["schema_version"] = "0.2"
    with pytest.raises(ValidationError):
        ContractV02.model_validate(data)


def test_new_equation_revision_does_not_inherit_old_assessment():
    data = example_data()
    newer = deepcopy(data["equations"][0])
    newer.update(revision="2", assumptions=["A revised physical assumption."])
    data["equations"].append(newer)
    ContractV03.model_validate(data)
    data["claims"][0]["equations"][0]["revision"] = "2"
    with pytest.raises(ValidationError, match="Equation pins"):
        ContractV03.model_validate(data)
