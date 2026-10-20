"""Keep species driving pressures distinct from each other and total pressure."""

from pathlib import Path

import pytest

from mceg import assess_conditions, load_contract
from mceg.__main__ import main
from mceg.assessment import compare_condition
from mceg.schema_v02 import Context, ContractV02, RangeCondition, SampleCondition


QUANTITIES = (
    "water_partial_pressure", "carbon_dioxide_partial_pressure",
    "carbon_monoxide_fugacity", "methane_fugacity", "nitrogen_partial_pressure",
    "water_fugacity", "helium_fugacity",
)
EXAMPLE = Path(__file__).resolve().parents[1] / "examples/v02/h2_solubility.yaml"


def context(name, value, unit):
    return Context(id="request", scope="Synthetic pressure comparison.",
                   quantities={name: {"value": value, "unit": unit}})


@pytest.mark.parametrize("name", QUANTITIES)
def test_driving_quantity_ranges_convert_units_without_aliasing(name):
    condition = RangeCondition(
        id="driving_pressure", revision="1", kind="range", quantity=name,
        interval={"lower": 1., "upper": 10., "unit": "bar"},
        coverage="numerical_evaluation", scope="Synthetic numerical bounds.", evidence=["fixture"],
    )
    for value, unit in ((1., "bar"), (100000., "Pa"), (.1, "MPa"), (.0001, "GPa"), (10., "bar")):
        assert compare_condition(condition, context(name, value, unit))[0] == "within_reported_range"
    for value in (0., 10.01):
        assert compare_condition(condition, context(name, value, "bar"))[0] == "outside_reported_range"
    for other in (*QUANTITIES, "pressure", "melt_total_pressure", "hydrogen_fugacity"):
        if other != name:
            assert compare_condition(condition, context(other, 1., "bar"))[0] == "unknown"


@pytest.mark.parametrize("name", QUANTITIES)
def test_joint_samples_require_the_same_driving_quantity_and_settings(name):
    sample = context(name, 1., "bar").model_dump()
    sample["settings"] = {"oxide_basis": "dry"}
    condition = SampleCondition(id="sample", revision="1", kind="samples",
                                samples=[sample], scope="Synthetic sample.", evidence=["fixture"])
    request = context(name, .1, "MPa").model_dump()
    assert compare_condition(condition, Context.model_validate(request))[0] == "unknown"
    request["settings"] = {"oxide_basis": "dry"}
    assert compare_condition(condition, Context.model_validate(request))[0] == "at_recorded_sample"
    request["settings"] = {"oxide_basis": "wet"}
    assert compare_condition(condition, Context.model_validate(request))[0] == "not_sampled"


@pytest.mark.parametrize("name", QUANTITIES)
@pytest.mark.parametrize("value,unit", [(-1., "bar"), (1., "K"), (float("inf"), "Pa")])
def test_invalid_driving_quantities_are_errors(name, value, unit):
    with pytest.raises(ValueError):
        context(name, value, unit)


def test_assess_cli_preserves_support_and_separates_water_from_melt_pressure(tmp_path):
    original = load_contract(EXAMPLE)
    data = original.model_dump()
    data["conditions"].append({
        "id": "water_sample", "revision": "1", "kind": "samples",
        "scope": "Synthetic regression sample, not experimental evidence.",
        "evidence": [original.evidence[0].id],
        "samples": [context("water_partial_pressure", 20., "bar").model_dump()],
    })
    contract = ContractV02.model_validate(data)
    path = tmp_path / "contract.json"
    path.write_text(contract.model_dump_json())
    requested = context("water_partial_pressure", 2., "MPa")
    inputs = tmp_path / "context.json"
    inputs.write_text(requested.model_dump_json())
    output = tmp_path / "assessed.yaml"
    assert main(["assess", str(path), "--context", str(inputs), "--subject", "imported",
                 "--output", str(output)]) == 0
    assessed = load_contract(output)
    assert assessed == assess_conditions(contract, requested, "imported")
    added = {a.condition: a.classification for a in assessed.assessments[len(contract.assessments):]}
    assert added["water_sample"] == "at_recorded_sample"
    assert added["pressure_hirschmann_abstract"] == "unknown"
    assert assessed.claims == original.claims
    assert assessed.assessments[:len(original.assessments)] == original.assessments
