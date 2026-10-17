"""Source-specific range checks must not become physical-support decisions."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/h2_solubility"
SPEC = importlib.util.spec_from_file_location("h2_assessment", EXAMPLE / "assess.py")
ASSESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASSESS)
WITHIN, OUTSIDE, UNKNOWN = "within_reported_range", "outside_reported_range", "unknown"


def inputs(temperature, pressure, unit="bar"):
    return {"temperature": None if temperature is None else {"value": temperature, "unit": "K"},
            "melt_total_pressure": None if pressure is None else {"value": pressure, "unit": unit}}


@pytest.mark.parametrize("temperature,pressure,expected", [
    (1700, 7500, [WITHIN, WITHIN, WITHIN]),
    (1750, 7500, [WITHIN, OUTSIDE, WITHIN]),
    (1800, 7500, [OUTSIDE, OUTSIDE, WITHIN]),
    (1700, 5000, [WITHIN, WITHIN, OUTSIDE]),
    (1700, 35000, [WITHIN, WITHIN, OUTSIDE]),
    (None, 7500, [UNKNOWN, UNKNOWN, WITHIN]),
    (1700, None, [WITHIN, WITHIN, UNKNOWN]),
    (None, None, [UNKNOWN, UNKNOWN, UNKNOWN]),
    (1673, 7000, [WITHIN, WITHIN, WITHIN]),
    (1723, 30000, [WITHIN, WITHIN, WITHIN]),
    (1773, 7500, [WITHIN, OUTSIDE, WITHIN]),
    (1723.01, 7500, [WITHIN, OUTSIDE, WITHIN]),
    (1773.01, 7500, [OUTSIDE, OUTSIDE, WITHIN]),
])
def test_source_specific_outcomes_and_closed_boundaries(temperature, pressure, expected):
    report = ASSESS.run(inputs(temperature, pressure))
    assert [item["classification"] for item in report["assessments"]] == expected
    assert report["physical_validation"] == "unknown"
    assert {"material_scope_match", "hydrogen_fugacity_coverage", "joint_domain_coverage"} <= report["not_evaluated"].keys()


@pytest.mark.parametrize("pressure,unit", [(750000000, "Pa"), (7500, "bar"), (750, "MPa"), (0.75, "GPa")])
def test_equivalent_pressures_have_equal_comparisons_but_preserve_inputs(pressure, unit):
    report = ASSESS.run(inputs(1700, pressure, unit))
    baseline = ASSESS.run(inputs(1700, 0.75, "GPa"))
    assert report["assessments"] == baseline["assessments"]
    assert report["context"]["melt_total_pressure"] == {"value": pressure, "unit": unit}


def test_fugacity_cannot_supply_missing_total_pressure():
    report = ASSESS.run({"temperature": {"value": 1700, "unit": "K"},
                         "hydrogen_fugacity": {"value": 7500, "unit": "bar"}})
    assert report["assessments"][2]["classification"] == UNKNOWN
    assert report["assessments"][2]["reason"] == "missing_input"


@pytest.mark.parametrize("context", [
    {"temperature": {"value": True, "unit": "K"}},
    {"temperature": {"value": "1700", "unit": "K"}},
    {"temperature": {"value": float("nan"), "unit": "K"}},
    {"temperature": {"value": float("inf"), "unit": "K"}},
    {"temperature": {"value": 0, "unit": "K"}},
    {"temperature": {"value": 1700, "unit": "bar"}},
    {"temperature": {"value": 1426.85, "unit": "degC"}},
    {"melt_total_pressure": {"value": -1, "unit": "bar"}},
    {"melt_total_pressure": {"value": 7500, "unit": "K"}},
    {"hydrogen_fugacity": {"value": float("nan"), "unit": "bar"}},
    {"temperature": {"value": 1700, "unit": "K", "uncertainty": 10}},
    {"temperatur": {"value": 1700, "unit": "K"}},
])
def test_invalid_or_unsupported_inputs_raise_instead_of_becoming_classifications(context):
    with pytest.raises(ValueError):
        ASSESS.run(context)


def write_conditions(tmp_path, mutation):
    record = yaml.safe_load((EXAMPLE / "conditions.yaml").read_text())
    mutation(record)
    path = tmp_path / "conditions.yaml"
    path.write_text(yaml.safe_dump(record))
    return path


@pytest.mark.parametrize("mutation", [
    lambda r: r["conditions"][0]["interval"].update(lower=1800),
    lambda r: r["conditions"][0]["interval"].update(upper=float("nan")),
    lambda r: r["conditions"][0]["interval"].update(unit="bar"),
    lambda r: r["conditions"][0]["interval"].update(closure="open"),
    lambda r: r["conditions"][0].update(quantity="hydrogen_fugacity"),
    lambda r: r["conditions"][0].update(evidence=["missing"]),
    lambda r: r["conditions"].append(copy.deepcopy(r["conditions"][0])),
    lambda r: r.update(contract="../outside.yaml"),
])
def test_invalid_conditions_are_rejected(tmp_path, mutation):
    path = write_conditions(tmp_path, mutation)
    with pytest.raises(ValueError):
        ASSESS.run(inputs(1700, 7500), path)


def test_duplicate_yaml_bounds_are_rejected(tmp_path):
    text = (EXAMPLE / "conditions.yaml").read_text().replace("lower: 1673", "lower: 1600, lower: 1673", 1)
    path = tmp_path / "conditions.yaml"
    path.write_text(text)
    with pytest.raises(yaml.YAMLError, match="Duplicate"):
        ASSESS.run(inputs(1700, 7500), path)


def test_changed_contract_requires_review(tmp_path, monkeypatch):
    path = tmp_path / "contracts/h2_solubility.yaml"
    path.parent.mkdir()
    path.write_bytes((ROOT / "contracts/h2_solubility.yaml").read_bytes() + b"\n# Changed source record.\n")
    monkeypatch.setattr(ASSESS, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="Contract changed; review"):
        ASSESS.run(inputs(1700, 7500))


def test_original_case_matches_manual_projections_without_changing_claims():
    contract_path = ROOT / "contracts/h2_solubility.yaml"
    original = contract_path.read_bytes()
    case = yaml.safe_load((EXAMPLE / "case.yaml").read_text())
    report = ASSESS.run(inputs(case["inputs"]["temperature_K"], case["inputs"]["total_pressure_bar"]))
    manual = {item["id"]: item for item in case["assessments"]}
    for calculated, name in zip(report["assessments"], ["solubility_metadata_temperature",
                                                       "solubility_formulation_temperature",
                                                       "solubility_total_pressure"]):
        assert calculated["classification"] == manual[name]["classification"]
        assert {k: v for k, v in calculated["interval"].items() if k != "closure"} == manual[name]["reported_range"]
    assert contract_path.read_bytes() == original


def test_saved_assessment_replays_with_the_same_inputs_sources_and_evaluator():
    record = json.loads((EXAMPLE / "assessment.json").read_text())
    assert record == ASSESS.run(record["context"])
    assert record["context"] == inputs(1750, 7500)
    assert record["assessments"][0]["evidence"] != record["assessments"][1]["evidence"]


def test_cli_works_outside_checkout_without_provider_packages(tmp_path):
    output = tmp_path / "assessment.json"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run([sys.executable, str(EXAMPLE / "assess.py"), "--temperature-k", "1750",
                    "--melt-pressure", "750", "--pressure-unit", "MPa", "--output", str(output)],
                   cwd=tmp_path, env=env, check=True, capture_output=True, text=True)
    report = json.loads(output.read_text())
    assert [a["classification"] for a in report["assessments"]] == [WITHIN, OUTSIDE, WITHIN]


def test_cli_invalid_input_does_not_write_an_assessment(tmp_path):
    path = tmp_path / "invalid.json"
    with pytest.raises(SystemExit) as exc:
        ASSESS.main(["--temperature-k", "nan", "--output", str(path)])
    assert exc.value.code == 2
    assert not path.exists()
