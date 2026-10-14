"""Audit-record checks that need neither ExoEOS nor ExoGibbs installed."""

import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pytest
import yaml

from mceg import load_contract


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/h2_solubility"


def read_case():
    return yaml.safe_load((EXAMPLE / "case.yaml").read_text())


def test_manual_case_links_and_scoped_classifications():
    case = read_case()
    assert case["assessment_method"] == "manual"
    assert len({item["id"] for item in case["assessments"]}) == len(case["assessments"])
    contracts = {path: load_contract(ROOT / path) for path in case["components"].values()}
    for item in case["assessments"]:
        assert item["scope"] and item["reason"] and item["evidence"]
        assert item["classification"] in {"within_reported_range", "extrapolation", "unknown"}
        for reference in item["evidence"]:
            path, evidence_id = reference.split("#")
            assert evidence_id in {evidence.id for evidence in contracts[path].evidence}
        if "reported_range" in item:
            bounds = item["reported_range"]
            inside = bounds["lower"] <= item["value"] <= bounds["upper"]
            assert inside == (item["classification"] == "within_reported_range")
    # Unknown physical questions remain visible despite successful arithmetic.
    by_id = {item["id"]: item for item in case["assessments"]}
    for name in ("solubility_fugacity", "melt_composition", "calibration_accuracy", "combined_accuracy"):
        assert by_id[name]["classification"] == "unknown"


def test_saved_execution_is_bound_to_inputs_sources_and_units():
    case = read_case()
    result = json.loads((EXAMPLE / "result.json").read_text())
    assert result["case_id"] == case["id"]
    assert result["inputs"] == case["inputs"]
    paths = {"case.yaml": result["case_sha256"], "run.py": result["runner_sha256"]}
    for path, digest in paths.items():
        assert hashlib.sha256((EXAMPLE / path).read_bytes()).hexdigest() == digest
    for path, digest in result["contract_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    for package, role in (("exoeos", "eos"), ("exogibbs", "solubility")):
        contract = load_contract(ROOT / case["components"][role])
        assert result["upstream"][package]["revision"] == contract.model.implementation.revision
    output = result["outputs"]
    pressure = case["inputs"]["total_pressure_bar"]
    assert output["pressure_Pa"] == pressure * 1e5
    assert output["melt_pressure_GPa"] == pressure / 1e4
    assert math.isclose(output["fugacity_H2_bar"], pressure * math.exp(output["lnphi_H2"]), rel_tol=1e-12)
    assert math.isclose(output["nonideal_to_ideal_ratio"], output["phi_H2"], rel_tol=1e-12)
    assert result["physical_validation"] == "unknown"
    assert result["numerical_checks"]
    for check in result["numerical_checks"]:
        assert check["passed"]
        assert math.isclose(check["actual"], check["expected"], rel_tol=check["rtol"], abs_tol=check["atol"])


def test_replay_refuses_changed_inputs_before_importing_providers(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("h2_example", EXAMPLE / "run.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    changed = read_case()
    changed["inputs"]["temperature_K"] = 2000.0
    path = tmp_path / "changed.yaml"
    path.write_text(yaml.safe_dump(changed))
    monkeypatch.setattr(runner, "CASE", path)
    with pytest.raises(ValueError, match="new manual audit"):
        runner.run()
