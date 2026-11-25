"""Explicit quantity sharing, assembly revisions and historical review identity."""

from copy import deepcopy
import json

from pydantic import ValidationError
import pytest

from mceg.schema_v03 import equation_digest
from mceg.schema_v04 import ContractV04, decision_basis_digest
from mceg.schema_v05 import (
    ContractV05,
    mathematical_model_digest,
    mathematical_model_records,
)
from mceg.validator import load_contract
from test_equation_schema import example_data


def mathematical_data():
    """Extend a reviewed continuity equation without changing its old definition."""
    data = example_data()
    data["schema_version"] = "0.5"
    symbols = data["equations"][0]["symbols"]
    data["quantities"] = [
        {"id": name, "revision": "1", **symbol,
         "domain": "A steady pure-hydrogen spherical atmosphere.",
         "coordinates": [{"id": "radius", "revision": "1"}]
         if name in {"n_h", "velocity"} else []}
        for name, symbol in symbols.items()
    ]
    model = {
        "id": "wind", "revision": "1",
        "description": "Density from a specified velocity and mass-loss rate.",
        "scope": "Continuity only; no momentum or energy closure is claimed.",
        "quantities": {
            name: {"quantity": {"id": name, "revision": "1"},
                   "role": "coordinate" if name == "radius" else
                   "unknown" if name == "n_h" else "input"}
            for name in symbols
        },
        "relations": [{"id": "continuity", "equation": {"id": "continuity", "revision": "1"},
                       "role": "mass conservation", "quantities": {name: name for name in symbols}}],
    }
    data["mathematical_models"] = [model]
    data["claims"][0]["mathematical_models"] = [{"id": "wind", "revision": "1"}]
    pin = {"id": "wind", "revision": "1", "sha256": "0" * 64}
    data["assessments"][0]["mathematical_model_pins"] = [pin]
    contract = ContractV05.model_validate(data)
    pin["sha256"] = mathematical_model_digest(contract, "wind", "1")
    return data


def test_assembly_maps_local_symbols_to_semantic_quantities(tmp_path):
    data = mathematical_data()
    path = tmp_path / "model.json"
    path.write_text(json.dumps(data))
    contract = load_contract(path)
    model = contract.mathematical_models[0]
    assert isinstance(contract, ContractV05)
    assert model.relations[0].quantities["n_h"] == "n_h"
    assert model.quantities["n_h"].role == "unknown"
    assert "status" not in model.model_dump()
    assert contract.quantities[0].coordinates[0].id == "radius"
    assert mathematical_model_digest(contract, "wind", "1") == (
        contract.assessments[0].mathematical_model_pins[0].sha256
    )


@pytest.mark.parametrize("change", [
    lambda d: d["quantities"].append(deepcopy(d["quantities"][0])),
    lambda d: d["mathematical_models"].append(deepcopy(d["mathematical_models"][0])),
    lambda d: d["quantities"][0].update(id="bad quantity"),
    lambda d: d["quantities"][0].update(status="supported"),
    lambda d: d["quantities"][0]["coordinates"][0].update(revision="absent"),
    lambda d: d["quantities"][0]["coordinates"].append({"id": "radius", "revision": "1"}),
    lambda d: d["quantities"][2].update(coordinates=[{"id": "n_h", "revision": "1"}]),
    lambda d: d["mathematical_models"][0].update(quantities={}),
    lambda d: d["mathematical_models"][0].update(relations=[]),
    lambda d: d["mathematical_models"][0]["quantities"]["n_h"]["quantity"].update(revision="absent"),
    lambda d: d["mathematical_models"][0]["quantities"]["n_h"].update(role="supported"),
    lambda d: d["mathematical_models"][0]["quantities"].update(
        other=deepcopy(d["mathematical_models"][0]["quantities"]["n_h"])),
    lambda d: d["mathematical_models"][0]["relations"].append(
        deepcopy(d["mathematical_models"][0]["relations"][0])),
    lambda d: d["mathematical_models"][0]["relations"][0]["equation"].update(revision="absent"),
    lambda d: d["mathematical_models"][0]["relations"][0]["quantities"].pop("velocity"),
    lambda d: d["mathematical_models"][0]["relations"][0]["quantities"].update(extra="velocity"),
    lambda d: d["mathematical_models"][0]["relations"][0]["quantities"].update(velocity="absent"),
    lambda d: d["quantities"][3].update(unit="km s^-1"),
    lambda d: d["claims"][0]["mathematical_models"][0].update(revision="absent"),
    lambda d: d["claims"][0]["mathematical_models"].append({"id": "wind", "revision": "1"}),
    lambda d: d["assessments"][0].update(mathematical_model_pins=[]),
    lambda d: d["assessments"][0]["mathematical_model_pins"][0].update(revision="absent"),
    lambda d: d["assessments"][0]["mathematical_model_pins"].append(
        deepcopy(d["assessments"][0]["mathematical_model_pins"][0])),
])
def test_invalid_references_mappings_coordinates_and_review_pins(change):
    data = mathematical_data()
    change(data)
    with pytest.raises(ValidationError):
        ContractV05.model_validate(data)


def test_field_coordinates_must_be_bound_in_the_model():
    data = mathematical_data()
    data["quantities"].append({"id": "time", "revision": "1", "latex": "t", "unit": "s",
                               "description": "Time", "domain": "Nonnegative time."})
    data["quantities"][0]["coordinates"].append({"id": "time", "revision": "1"})
    with pytest.raises(ValidationError, match="coordinates must be present"):
        ContractV05.model_validate(data)


def test_unknown_support_may_leave_models_unpinned():
    data = mathematical_data()
    data["assessments"][0].update(status="unknown", mathematical_model_pins=[])
    assert ContractV05.model_validate(data).assessments[0].status == "unknown"


def test_contradicted_support_also_requires_model_pins():
    data = mathematical_data()
    data["assessments"][0].update(status="contradicted", mathematical_model_pins=[])
    with pytest.raises(ValidationError, match="Contradicted assessments must pin"):
        ContractV05.model_validate(data)


def test_repeated_relation_instances_and_incidence_cycles_are_allowed():
    data = mathematical_data()
    other = deepcopy(data["mathematical_models"][0]["relations"][0])
    other["id"] = "another_use"
    data["mathematical_models"][0]["relations"].append(other)
    contract = ContractV05.model_validate(data)
    # Both relations touch the same density and velocity, producing an incidence cycle.
    assert len(contract.mathematical_models[0].relations) == 2
    assert mathematical_model_digest(contract, "wind", "1") != (
        contract.assessments[0].mathematical_model_pins[0].sha256
    )


def test_same_spelling_and_units_do_not_merge_quantities():
    data = mathematical_data()
    other = deepcopy(data["quantities"][0])
    other.update(id="other_n_h", description="Hydrogen nuclei density of another atmosphere.")
    data["quantities"].append(other)
    model = data["mathematical_models"][0]
    model["quantities"]["other_n_h"] = {
        "quantity": {"id": "other_n_h", "revision": "1"}, "role": "unknown"}
    second = deepcopy(model["relations"][0])
    second["id"] = "other_atmosphere"
    second["quantities"]["n_h"] = "other_n_h"
    model["relations"].append(second)
    contract = ContractV05.model_validate(data)
    mapped = [r.quantities["n_h"] for r in contract.mathematical_models[0].relations]
    assert mapped == ["n_h", "other_n_h"]


@pytest.mark.parametrize("kind", ["constraint", "distribution", "optimization"])
def test_relation_kinds_declare_intent_without_executing_math(kind):
    data = mathematical_data()
    data["mathematical_models"][0]["relations"][0]["kind"] = kind
    assert ContractV05.model_validate(data).mathematical_models[0].relations[0].kind == kind


@pytest.mark.parametrize("change", [
    lambda d: d["quantities"][0].update(description="Ion density, not total nuclei density."),
    lambda d: d["quantities"][0].update(domain="A different atmosphere."),
    lambda d: d["equations"][0].update(latex="n=0"),
    lambda d: d["equations"][0]["assumptions"].append("Additional authored assumption."),
    lambda d: d["mathematical_models"][0].update(scope="A new adopted scope."),
    lambda d: d["mathematical_models"][0]["quantities"]["velocity"].update(role="unknown"),
])
def test_model_digest_covers_definitions_scope_roles_and_retains_history(change):
    data = mathematical_data()
    pin = data["assessments"][0]["mathematical_model_pins"][0]["sha256"]
    change(data)
    contract = ContractV05.model_validate(data)
    assert mathematical_model_digest(contract, "wind", "1") != pin
    assert contract.assessments[0].status == "supported"
    assert contract.assessments[0].mathematical_model_pins[0].sha256 == pin


def test_model_digest_ignores_unrelated_definitions_and_mapping_order():
    data = mathematical_data()
    before = mathematical_model_digest(ContractV05.model_validate(data), "wind", "1")
    unrelated = deepcopy(data["quantities"][1])
    unrelated["id"] = "unrelated"
    data["quantities"].append(unrelated)
    relation = data["mathematical_models"][0]["relations"][0]
    relation["quantities"] = dict(reversed(list(relation["quantities"].items())))
    relation["kind"] = "equation"
    contract = ContractV05.model_validate(data)
    assert mathematical_model_digest(contract, "wind", "1") == before
    records = mathematical_model_records(contract, "wind", "1")
    assert not any(r["id"] == "unrelated" for r in records)
    assert {r["kind"] for r in records} == {"quantity", "equation", "mathematical_model"}


def test_old_records_keep_their_serialization_and_digests_on_empty_upgrade():
    data = example_data()
    data["schema_version"] = "0.4"
    old = ContractV04.model_validate(data)
    data["schema_version"] = "0.5"
    new = ContractV05.model_validate(data)
    assert new.claims[0].model_dump(mode="json") == old.claims[0].model_dump(mode="json")
    assert new.assessments[0].model_dump(mode="json") == old.assessments[0].model_dump(mode="json")
    assert equation_digest(new.equations[0]) == equation_digest(old.equations[0])
    assert decision_basis_digest(new, "assessment", "formulation_review") == (
        decision_basis_digest(old, "assessment", "formulation_review")
    )


def test_new_model_revision_needs_its_own_review_pin():
    data = mathematical_data()
    new = deepcopy(data["mathematical_models"][0])
    new.update(revision="2", description="A new adopted model revision.")
    data["mathematical_models"].append(new)
    ContractV05.model_validate(data)
    data["claims"][0]["mathematical_models"][0]["revision"] = "2"
    with pytest.raises(ValidationError, match="pins must refer"):
        ContractV05.model_validate(data)


def test_old_reader_rejects_new_schema_and_new_definition_fields():
    data = mathematical_data()
    with pytest.raises(ValidationError):
        ContractV04.model_validate(data)
    data["schema_version"] = "0.4"
    with pytest.raises(ValidationError):
        ContractV04.model_validate(data)


def test_digest_requires_an_explicit_existing_model_revision():
    contract = ContractV05.model_validate(mathematical_data())
    with pytest.raises(ValueError, match="Unknown mathematical model revision"):
        mathematical_model_digest(contract, "wind", "absent")
