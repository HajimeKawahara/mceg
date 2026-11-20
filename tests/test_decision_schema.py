"""Adoption records preserve choices and the exact evidence reviewed for them."""

from copy import deepcopy
import json
from pathlib import Path

from pydantic import ValidationError
import pytest

from mceg import (ContractV04, assess_conditions, decision_basis_digest,
                  decision_basis_records, load_contract)
from mceg.schema_v02 import Context
from mceg.schema_v03 import ContractV03

from test_equation_schema import example_data as equation_example_data


def example_data():
    """A prospective choice can cite unknown support and need no implementation."""
    data = equation_example_data()
    data["schema_version"] = "0.4"
    data["assessments"][0]["status"] = "unknown"
    data["evidence"].append({
        "id": "review_notes", "kind": "literature", "summary": "Compare the recorded derivation.",
        "sources": ["doc/review.txt"], "scope": "An illustrative source review.",
        "provenance": {"role": "secondary", "location": "Review notes", "inspection": "inspected",
                       "note": "This is not independent validation.",
                       "derived_from": [{"evidence": "derivation", "comparison": "consistent",
                                         "note": "The notes cite the same continuity relation."}]},
    })
    data["decisions"] = [{
        "id": "density_model", "revision": "1",
        "question": "Which density prescription should the example use?",
        "scope": "Steady, spherical, pure-hydrogen flow.",
        "options": [{"id": "power_law", "description": "Choose an independent density exponent."},
                    {"id": "continuity", "description": "Obtain density from mass conservation."}],
        "selected": "continuity", "reasons": ["Keep density consistent with the adopted velocity."],
        "limitations": ["This choice does not establish atmospheric accuracy."],
        "reconsider_when": ["The steady spherical assumptions change."],
    }]
    contract = ContractV04.model_validate(data)
    data["decisions"][0]["basis"] = [
        {"kind": kind, "id": key, "sha256": decision_basis_digest(contract, kind, key)}
        for kind, key in [("evidence", "review_notes"), ("assessment", "formulation_review")]
    ]
    return data


def test_choice_does_not_require_supported_assessment_or_selected_implementation(tmp_path):
    data = example_data()
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(data))
    contract = load_contract(path)
    assert isinstance(contract, ContractV04)
    assert isinstance(contract, ContractV03)
    assert contract.assessments[0].status == "unknown"
    assert contract.decisions[0].subject is None
    assert contract.decisions[0].context is None
    assert "status" not in contract.decisions[0].model_dump()
    assert contract.decisions[0].selected == "continuity"
    assert path.read_text() == json.dumps(data)


@pytest.mark.parametrize("change", [
    lambda d: d["decisions"].append(deepcopy(d["decisions"][0])),
    lambda d: d["decisions"][0].update(options=[]),
    lambda d: d["decisions"][0]["options"].append(deepcopy(d["decisions"][0]["options"][0])),
    lambda d: d["decisions"][0].update(selected="absent"),
    lambda d: d["decisions"][0].update(reasons=[]),
    lambda d: d["decisions"][0].update(subject="absent"),
    lambda d: d["decisions"][0].update(context="absent"),
    lambda d: d["decisions"][0].update(status="supported"),
    lambda d: d["decisions"][0].update(revision="bad revision"),
    lambda d: d["decisions"][0]["basis"][0].update(id="absent"),
    lambda d: d["decisions"][0]["basis"][0].update(kind="decision"),
    lambda d: d["decisions"][0]["basis"][0].update(sha256="not-a-hash"),
    lambda d: d["decisions"][0]["basis"].append(deepcopy(d["decisions"][0]["basis"][0])),
    lambda d: d["decisions"][0].update(supersedes={"id": "density_model", "revision": "absent"}),
    lambda d: d["decisions"][0].update(supersedes={"id": "absent", "revision": "1"}),
])
def test_invalid_choices_and_references_are_rejected(change):
    data = example_data()
    change(data)
    with pytest.raises(ValidationError):
        ContractV04.model_validate(data)


def test_empty_basis_and_explicit_subject_context_are_readable():
    data = example_data()
    data["decisions"][0].update(basis=[], subject="implementation", context="review")
    contract = ContractV04.model_validate(data)
    assert not contract.decisions[0].basis
    assert contract.decisions[0].subject == "implementation"


def test_exact_supersession_keeps_the_old_choice_and_does_not_rank_revisions():
    data = example_data()
    old = deepcopy(data["decisions"][0])
    newer = deepcopy(old)
    newer.update(revision="revision-a", selected="power_law",
                 supersedes={"id": "density_model", "revision": "1"},
                 reasons=["A different scoped modeling choice."])
    data["decisions"].insert(0, newer)
    contract = ContractV04.model_validate(data)
    assert contract.decisions[1].model_dump(exclude_defaults=True) == ContractV04.model_validate(
        {**data, "decisions": [old]}).decisions[0].model_dump(exclude_defaults=True)
    assert contract.decisions[1].selected == "continuity"
    assert contract.decisions[0].supersedes.revision == "1"


@pytest.mark.parametrize("size", [1, 2, 3])
def test_supersession_cycles_are_rejected(size):
    data = example_data()
    original = data["decisions"][0]
    data["decisions"] = []
    for i in range(size):
        decision = deepcopy(original)
        decision.update(revision=str(i), supersedes={"id": decision["id"], "revision": str((i + 1) % size)})
        data["decisions"].append(decision)
    with pytest.raises(ValidationError, match="cycle"):
        ContractV04.model_validate(data)


def test_assessment_basis_includes_declared_targets_equations_and_bindings():
    contract = ContractV04.model_validate(example_data())
    records = decision_basis_records(contract, "assessment", "formulation_review")
    actual = {(r["kind"], r["id"], r.get("revision")) for r in records}
    assert actual == {
        ("assessment", "formulation_review", None), ("claim", "equation_implementation", "1"),
        ("evidence", "derivation", None), ("subject", "implementation", None),
        ("context", "review", None), ("equation", "continuity", "1"),
        ("binding", "continuity_function", None),
    }
    evidence = decision_basis_records(contract, "evidence", "review_notes")
    assert {(r["kind"], r["id"]) for r in evidence} == {
        ("evidence", "review_notes"), ("evidence", "derivation"),
    }


@pytest.mark.parametrize("change", [
    lambda d: d["evidence"][0].update(summary="A revised derivation."),
    lambda d: d["claims"][0].update(statement="A revised correspondence claim."),
    lambda d: d["subjects"][0]["implementation"].update(revision="changed"),
    lambda d: d["subjects"][0]["selected_files"].update({"src/provider.py": "1" * 64}),
    lambda d: d["contexts"][0].update(scope="A different review context."),
    lambda d: d["assessments"][0].update(reasons=["A different interpretation."]),
    lambda d: d["equations"][0]["assumptions"].append("A different physical assumption."),
    lambda d: d["bindings"][0]["arguments"]["velocity_kms"].update(scale=1.0),
])
def test_changed_recorded_dependency_stales_basis_without_rewriting_choice(change):
    data = example_data()
    old_decision = deepcopy(data["decisions"][0])
    old_assessment = deepcopy(data["assessments"][0])
    pin = old_decision["basis"][1]["sha256"]
    change(data)
    contract = ContractV04.model_validate(data)
    assert decision_basis_digest(contract, "assessment", "formulation_review") != pin
    assert contract.decisions[0].model_dump(exclude_defaults=True) == ContractV04.model_validate(
        {**data, "decisions": [old_decision]}).decisions[0].model_dump(exclude_defaults=True)
    assert contract.decisions[0].basis[1].sha256 == pin
    assert contract.decisions[0].selected == "continuity"
    assert contract.assessments[0].status == old_assessment["status"]


def test_evidence_basis_recurses_through_provenance_and_optional_targets():
    data = example_data()
    data["evidence"][0].update(subject="implementation", context="review")
    contract = ContractV04.model_validate(data)
    before = decision_basis_digest(contract, "evidence", "review_notes")
    records = decision_basis_records(contract, "evidence", "review_notes")
    assert {r["kind"] for r in records} == {"evidence", "subject", "context"}
    data["contexts"][0]["scope"] = "Changed context of the cited source."
    assert decision_basis_digest(ContractV04.model_validate(data), "evidence", "review_notes") != before


@pytest.mark.parametrize("kind", ["range", "samples"])
def test_membership_basis_captures_condition_definition(kind):
    data = example_data()
    condition = {"id": "temperatures", "revision": "1", "kind": kind,
                 "scope": "Synthetic conditions only.", "evidence": ["derivation"]}
    if kind == "range":
        condition.update(quantity="temperature", coverage="numerical_evaluation",
                         interval={"lower": 1000.0, "upper": 2000.0, "unit": "K"})
        classification = "within_reported_range"
    else:
        condition["samples"] = [{"id": "one", "scope": "A synthetic sample.",
                                  "quantities": {"temperature": {"value": 1500.0, "unit": "K"}}}]
        classification = "at_recorded_sample"
    data["conditions"] = [condition]
    data["assessments"].append({
        "id": "membership", "kind": "range_membership" if kind == "range" else "sample_membership",
        "subject": "implementation", "context": "review", "condition": "temperatures",
        "condition_revision": "1", "method": {"id": "membership", "revision": "1", "description": "Check inputs."},
        "evidence": ["derivation"], "reasons": ["An illustrative check."], "classification": classification,
    })
    contract = ContractV04.model_validate(data)
    before = decision_basis_digest(contract, "assessment", "membership")
    condition["scope"] = "A revised scope."
    assert decision_basis_digest(ContractV04.model_validate(data), "assessment", "membership") != before


def test_unrelated_records_and_collection_order_do_not_stale_a_basis():
    data = example_data()
    expected = data["decisions"][0]["basis"][1]["sha256"]
    unrelated = deepcopy(data["equations"][0])
    unrelated.update(revision="unused", assumptions=["An unrelated revision."])
    data["equations"].insert(0, unrelated)
    data["evidence"][1]["summary"] = "Unrelated to the selected formulation Assessment."
    data["evidence"].reverse()
    data["decisions"][0]["reasons"] = ["Rephrased selection rationale."]
    data["bindings"][0]["arguments"] = dict(reversed(list(data["bindings"][0]["arguments"].items())))
    assert decision_basis_digest(ContractV04.model_validate(data), "assessment", "formulation_review") == expected


def test_basis_resolution_never_reads_source_files(monkeypatch):
    contract = ContractV04.model_validate(example_data())

    def forbidden(*args, **kwargs):
        raise AssertionError("Basis resolution must only inspect recorded values")

    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    assert decision_basis_digest(contract, "assessment", "formulation_review") == contract.decisions[0].basis[1].sha256


@pytest.mark.parametrize("kind, identifier", [("decision", "density_model"), ("evidence", "missing"),
                                             ("assessment", "missing")])
def test_basis_helper_rejects_unsupported_or_missing_targets(kind, identifier):
    with pytest.raises(ValueError):
        decision_basis_digest(ContractV04.model_validate(example_data()), kind, identifier)


def test_condition_assessment_preserves_decision_history():
    data = example_data()
    data["conditions"] = [{
        "id": "temperature", "revision": "1", "kind": "range", "quantity": "temperature",
        "interval": {"lower": 1000.0, "upper": 2000.0, "unit": "K"},
        "coverage": "numerical_evaluation", "scope": "A synthetic range.", "evidence": ["derivation"],
    }]
    contract = ContractV04.model_validate(data)
    before = contract.model_dump()
    context = Context(id="other", scope="Another synthetic context.",
                      quantities={"temperature": {"value": 1500.0, "unit": "K"}})
    result = assess_conditions(contract, context, "implementation")
    assert isinstance(result, ContractV04)
    assert result.decisions == contract.decisions
    assert result.assessments[:-1] == contract.assessments
    assert result.assessments[-1].classification == "within_reported_range"
    assert contract.model_dump() == before


def test_v03_reader_rejects_decisions_and_v04_can_omit_them():
    data = example_data()
    with pytest.raises(ValidationError):
        ContractV03.model_validate(data)
    data["schema_version"] = "0.3"
    with pytest.raises(ValidationError):
        ContractV03.model_validate(data)
    data["schema_version"] = "0.4"
    del data["decisions"]
    assert not ContractV04.model_validate(data).decisions
