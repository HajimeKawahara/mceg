"""Equation identities survive existing readers, reviews and migrations."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from mceg import assess_conditions, load_contract, migrate_contract, restore_v01
from mceg.catalog import CatalogRecord, load_record, record_report
from mceg.check import check_contract
from mceg.explain import explain_contract
from mceg.schema_v02 import Context
from mceg.schema_v03 import ContractV03

from test_equation_schema import example_data


ROOT = Path(__file__).resolve().parents[1]


def write_provider(tmp_path):
    """This provider cannot be imported, but its declarations can be inspected."""
    source = tmp_path / "src/provider.py"
    source.parent.mkdir()
    source.write_text(
        'raise RuntimeError("Provider code must never run during inspection")\n'
        "PROTON_MASS_CGS = 1.6726e-24\n\n"
        "def hydrogen_nuclei_density(radius_cm, velocity_kms, mass_loss_g_s):\n"
        "    return mass_loss_g_s / (4 * 3.14159 * radius_cm**2 * velocity_kms * 1e5 * PROTON_MASS_CGS)\n"
    )
    data = example_data()
    data["subjects"][0]["selected_files"]["src/provider.py"] = sha256(source.read_bytes()).hexdigest()
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(data))
    return path, source, data


def statuses(report, collection):
    return {item["name"]: item["status"] for item in report[collection] if "name" in item}


def test_selected_check_and_explain_inspect_v03_without_importing_provider(tmp_path):
    path, _, data = write_provider(tmp_path)
    before = path.read_bytes()
    contract = load_contract(path)
    assert isinstance(contract, ContractV03)
    report = check_contract(path, {}, "formulation_review", root=tmp_path)
    checks = statuses(report, "checks")
    assert checks["selected_files"] == "PASS"
    assert checks["equation_definitions"] == "PASS"
    assert checks["binding_definitions"] == "PASS"
    assert checks["binding_source"] == "PASS"
    assert report["assessments"][0]["equation_pins"] == data["assessments"][0]["equation_pins"]
    explanation = explain_contract(path, {}, assessment_id="formulation_review", root=tmp_path)
    assert statuses(explanation, "items")["binding_source"] == "PASS"
    assert path.read_bytes() == before


def test_stale_definitions_fail_selected_views_without_rewriting_history(tmp_path):
    path, _, data = write_provider(tmp_path)
    original_assessment = deepcopy(data["assessments"][0])
    data["equations"][0]["assumptions"].append("A changed physical assumption.")
    data["bindings"][0]["arguments"]["velocity_kms"]["scale"] = 1.0
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    report = check_contract(path, {}, "formulation_review", root=tmp_path)
    checked = statuses(report, "checks")
    assert checked["equation_definitions"] == checked["binding_definitions"] == "FAIL"
    assert checked["recorded_support"] == "PASS"
    assert report["assessments"][0]["status"] == "supported"
    explanation = explain_contract(path, {}, assessment_id="formulation_review", root=tmp_path)
    explained = statuses(explanation, "items")
    assert explained["equation_definitions"] == explained["binding_definitions"] == "FAIL"
    assert json.loads(path.read_text())["assessments"][0] == original_assessment
    assert path.read_bytes() == before


def test_source_changes_fail_hash_and_declared_argument_checks(tmp_path):
    path, source, _ = write_provider(tmp_path)
    source.write_text("def hydrogen_nuclei_density(radius_cm, speed_kms, mass_loss_g_s):\n    return 0.0\n")
    report = check_contract(path, {}, "formulation_review", root=tmp_path)
    checked = statuses(report, "checks")
    assert checked["selected_files"] == checked["binding_source"] == "FAIL"
    assert checked["equation_definitions"] == checked["binding_definitions"] == "PASS"
    assert load_contract(path).assessments[0].status == "supported"


def test_no_root_leaves_source_correspondence_unchecked(tmp_path):
    path, _, _ = write_provider(tmp_path)
    report = check_contract(path, {}, "formulation_review")
    checked = statuses(report, "checks")
    assert checked["binding_source"] == "UNKNOWN"
    assert checked["equation_definitions"] == checked["binding_definitions"] == "PASS"
    assert "selected_files" not in checked


@pytest.mark.parametrize("path", sorted((ROOT / "contracts").glob("*.yaml")))
def test_v03_still_restores_original_v01_declarations(path):
    original = load_contract(path)
    data = migrate_contract(path).model_dump()
    data["schema_version"] = "0.3"
    # New definitions do not alter the frozen imported claims or judgments.
    equation = deepcopy(example_data()["equations"][0])
    equation["evidence"] = []
    data["equations"] = [equation]
    modern = ContractV03.model_validate(data)
    assert restore_v01(modern).model_dump() == original.model_dump()
    modern.claims[0].statement = "A different historical statement."
    with pytest.raises(ValueError, match="content changed"):
        restore_v01(modern)


def test_condition_assessment_preserves_equations_and_historical_pins():
    data = example_data()
    data["conditions"] = [{
        "id": "temperature", "revision": "1", "kind": "range", "quantity": "temperature",
        "interval": {"lower": 3000.0, "upper": 10000.0, "unit": "K"},
        "coverage": "marginal", "scope": "Synthetic interval for a lifecycle test only.",
        "evidence": ["derivation"],
    }]
    contract = ContractV03.model_validate(data)
    before = contract.model_dump()
    context = Context(id="new_request", scope="Synthetic requested temperature.",
                      quantities={"temperature": {"value": 5000.0, "unit": "K"}})
    assessed = assess_conditions(contract, context, "implementation")
    assert isinstance(assessed, ContractV03)
    assert assessed.schema_version == "0.3"
    assert contract.model_dump() == before
    assert assessed.equations == contract.equations
    assert assessed.bindings == contract.bindings
    assert assessed.claims == contract.claims
    assert assessed.evidence == contract.evidence
    assert assessed.assessments[0] == contract.assessments[0]
    assert assessed.assessments[-1].classification == "within_reported_range"
    assert assess_conditions(assessed, context, "implementation") == assessed


def test_package_catalog_retains_equation_references_without_claiming_recheck(tmp_path):
    path, _, data = write_provider(tmp_path)
    record = CatalogRecord(id="continuity", path=path.name, sha256=sha256(path.read_bytes()).hexdigest(),
                           species=["H"], assessments=["formulation_review"])
    _, contract, selected, checks = load_record(tmp_path, record)
    assert isinstance(contract, ContractV03)
    assert selected[0].equation_pins[0].sha256 == data["assessments"][0]["equation_pins"][0]["sha256"]
    assert checks[0]["status"] == "PASS"
    report = record_report(tmp_path, record)
    assert report["claims"][0]["record"]["equations"] == data["claims"][0]["equations"]
    assert report["scientific_files"] == "not_checked"
