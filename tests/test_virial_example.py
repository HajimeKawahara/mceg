"""Validate mixture audit records without importing either provider or JAX."""

import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pytest
import yaml

from mceg import load_contract, trace_provenance


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/virial_mixture"


def test_manual_scope_and_contract_links():
    case = yaml.safe_load((EXAMPLE / "case.yaml").read_text())
    assert case["assessment_method"] == "manual"
    contracts = {path: load_contract(ROOT / path) for path in case["components"].values()}
    for row in case["assessments"]:
        assert row["scope"] and row["reason"]
        for reference in row["evidence"]:
            path, evidence = reference.split("#")
            assert evidence in {item.id for item in contracts[path].evidence}
    rows = {row["id"]: row for row in case["assessments"]}
    assert rows["water_cross_1500K"]["classification"] == "within_reported_range"
    for key in ("water_cross_2173K_extrapolate", "water_cross_2173K_hold"):
        assert rows[key]["classification"] == "extrapolation"
    for key in ("hydrogen_helium_pair", "zero_pairs", "higher_virials", "combined_accuracy"):
        assert rows[key]["classification"] == "unknown"
    provider = contracts[case["components"]["eos"]]
    assert trace_provenance(provider, "source_ledger")["recorded_audit_complete"] is False


def test_execution_receipt_is_bound_and_preserves_full_mixture_corrections():
    case = yaml.safe_load((EXAMPLE / "case.yaml").read_text())
    result = json.loads((EXAMPLE / "result.json").read_text())
    assert result["inputs"] == case["inputs"]
    paths = {"examples/virial_mixture/case.yaml": result["case_sha256"],
             "examples/virial_mixture/run.py": result["runner_sha256"], **result["contract_sha256"]}
    for path, digest in paths.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    for owner, role in (("exoeos", "eos"), ("exogibbs", "adapter")):
        assert result["upstream"][owner]["revision"] == load_contract(
            ROOT / case["components"][role]).model.implementation.revision
    assert {(row["temperature_K"], row["policy"]) for row in result["states"]} == {
        (t, p) for t in case["inputs"]["temperatures_K"] for p in case["inputs"]["water_cross_policies"]}
    for row in result["states"]:
        assert row["pressure_Pa"] == case["inputs"]["pressure_bar"] * 1e5
        assert all(value == 0 for pair in row["coefficients_m3_mol"][3:] for value in pair)
        for value in row["lnphi"][3:]:
            assert value != 0
            assert math.isclose(value, -math.log(row["Z"]), abs_tol=1e-13)
    assert result["numerical_checks"]
    assert all(c["passed"] and c["max_absolute_error"] <= c["absolute_tolerance"]
               for c in result["numerical_checks"])
    assert result["physical_validation"] == "unknown"


def test_changed_case_requires_review_before_optional_imports(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("virial_example", EXAMPLE / "run.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    case = yaml.safe_load((EXAMPLE / "case.yaml").read_text())
    case["inputs"]["h2_he_cm3_mol"] = 20.0
    changed = tmp_path / "case.yaml"
    changed.write_text(yaml.safe_dump(case))
    monkeypatch.setattr(runner, "CASE", changed)
    with pytest.raises(ValueError, match="new manual audit"):
        runner.run()
