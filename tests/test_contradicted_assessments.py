"""Scoped contrary evidence must stay distinct from missing or invalid evidence."""

from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from mceg import (Contract, ContractV02, ContractV03, ContractV04, load_contract,
                  migrate_contract, restore_v01)
from mceg.__main__ import main
from mceg import documentation as docs
from mceg.decisions import decision_basis_checks
from mceg.graph import build_graph
from mceg.schema_v04 import decision_basis_digest
from test_equation_schema import example_data as equation_data


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def contrary_data():
    """Synthetic measured threshold failure; no scientific solver is executed."""
    implementation = {"repository": "https://example.org/provider", "revision": "fixture-v1",
                      "entry_points": ["src/model.py:population"]}
    return {
        "schema_version": "0.2",
        "model": {"id": "example.truncation", "name": "Truncation criterion",
                  "description": "Synthetic assessment regression fixture.",
                  "implementation": implementation},
        "assumptions": [], "limitations": [],
        "domains": [{"kind": "scientific_applicability", "status": "unknown",
                     "description": "No whole-atmosphere validation.", "conditions": [],
                     "evidence": ["measured_failure"]}],
        "claims": [{"id": "truncation", "revision": "1", "kind": "numerical_verification",
                    "statement": "Increasing the level cutoff changes n3 by at most 5%.",
                    "scope": "The specified finite-atom calculation only."}],
        "subjects": [{"id": "atom", "implementation": deepcopy(implementation)}],
        "contexts": [{"id": "comparison", "scope": "Synthetic fixed comparison conditions."}],
        "evidence": [{"id": "measured_failure", "kind": "numerical_test", "result": "failed",
                      "summary": "Synthetic converged calculation: change 7.74%, criterion 5%.",
                      "scope": "Fixture only.", "sources": ["fixture-result.json"],
                      "subject": "atom", "context": "comparison",
                      "provenance": {"role": "primary", "inspection": "inspected",
                                     "location": "Fixture comparison", "note": "Synthetic result."}}],
        "assessments": [{"id": "truncation_review", "kind": "evidence_support",
                         "claim": "truncation", "claim_revision": "1", "subject": "atom",
                         "context": "comparison", "origin": "reviewed", "status": "contradicted",
                         "method": {"id": "threshold_review", "revision": "1",
                                    "description": "Review convergence and the measured comparison."},
                         "evidence": ["measured_failure"],
                         "reasons": ["Valid fixture comparison: 7.74% exceeds the 5% criterion."]}],
    }


@pytest.mark.parametrize("version, model", [("0.2", ContractV02), ("0.3", ContractV03),
                                           ("0.4", ContractV04)])
def test_contradicted_round_trip_in_experimental_readers(contrary_data, version, model, tmp_path):
    contrary_data["schema_version"] = version
    contract = model.model_validate(contrary_data)
    path = tmp_path / "contract.json"
    path.write_text(contract.model_dump_json(), encoding="utf-8")
    assert load_contract(path) == contract
    assert contract.assessments[0].status == "contradicted"


@pytest.mark.parametrize("field, value", [
    ("result", "passed"), ("result", "unknown"), ("result", "not_run"),
    ("kind", "implementation"), ("subject", "other"), ("context", "other"),
])
def test_contradiction_requires_matching_failed_numerical_evidence(contrary_data, field, value):
    contrary_data["subjects"].append({**contrary_data["subjects"][0], "id": "other"})
    contrary_data["contexts"].append({"id": "other", "scope": "A different comparison."})
    contrary_data["evidence"][0][field] = value
    if field == "kind":
        contrary_data["evidence"][0]["result"] = None
    with pytest.raises(ValidationError, match="Contradicted assessment lacks matching evidence"):
        ContractV02.model_validate(contrary_data)


@pytest.mark.parametrize("change, message", [
    ({"evidence": []}, "lacks matching evidence"),
    ({"origin": "imported_v0.1_declaration"}, "require an explicit review"),
    ({"reasons": []}, "at least 1 item"),
])
def test_contradiction_requires_review_evidence_and_reasons(contrary_data, change, message):
    contrary_data["assessments"][0].update(change)
    with pytest.raises(ValidationError, match=message):
        ContractV02.model_validate(contrary_data)


def test_comparator_evidence_may_have_its_own_scope(contrary_data):
    contrary_data["contexts"].append({"id": "other", "scope": "Earlier comparator context."})
    other = {**contrary_data["evidence"][0], "id": "comparator", "context": "other"}
    contrary_data["evidence"].append(other)
    contrary_data["assessments"][0]["evidence"].append("comparator")
    assert ContractV02.model_validate(contrary_data).assessments[0].status == "contradicted"


@pytest.mark.parametrize("claim_kind, evidence_kind", [
    ("theoretical", "theory"), ("physical_validation", "observation"),
    ("physical_validation", "experiment"),
])
def test_non_numerical_contradictions_retain_their_evidence_categories(
        contrary_data, claim_kind, evidence_kind):
    contrary_data["claims"][0]["kind"] = claim_kind
    with pytest.raises(ValidationError, match="lacks matching evidence"):
        ContractV02.model_validate(contrary_data)
    contrary_data["evidence"][0].update(kind=evidence_kind, result=None)
    assert ContractV02.model_validate(contrary_data).assessments[0].status == "contradicted"


@pytest.mark.parametrize("result", ["failed", "unknown", "not_run"])
def test_execution_or_coverage_failure_does_not_infer_contradiction(contrary_data, result, tmp_path, capsys):
    contrary_data["evidence"][0].update(result=result, summary="Execution or coverage failure.")
    contrary_data["assessments"][0].update(status="unknown", reasons=["No valid comparison is available."])
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contrary_data), encoding="utf-8")
    before = path.read_bytes()
    assert main(["check", str(path), "--assessment", "truncation_review", "--json"]) == 0
    entry = json.loads(capsys.readouterr().out)["contracts"][0]
    assert next(c for c in entry["checks"] if c["name"] == "recorded_support")["status"] == "UNKNOWN"
    assert entry["assessments"][0]["status"] == "unknown"
    assert path.read_bytes() == before


def test_selected_contradiction_and_repaired_support_keep_separate_history(contrary_data, tmp_path, capsys):
    repaired_subject = deepcopy(contrary_data["subjects"][0])
    repaired_subject["id"] = "repaired_atom"
    repaired_subject["implementation"]["revision"] = "fixture-v2"
    contrary_data["subjects"].append(repaired_subject)
    contrary_data["contexts"].append({"id": "recheck", "scope": "Repaired calculation."})
    repaired_evidence = {**contrary_data["evidence"][0], "id": "new_pass", "result": "passed",
                         "summary": "Synthetic converged calculation: change 2%, criterion 5%.",
                         "subject": "repaired_atom", "context": "recheck"}
    contrary_data["evidence"].append(repaired_evidence)
    repaired = {**contrary_data["assessments"][0], "id": "repaired_review", "status": "supported",
                "subject": "repaired_atom", "context": "recheck", "evidence": ["new_pass"],
                "reasons": ["A new valid comparison meets the criterion."]}
    contrary_data["assessments"].append(repaired)
    path = tmp_path / "history.json"
    path.write_text(json.dumps(contrary_data), encoding="utf-8")
    before = path.read_bytes()
    for assessment, status, exit_code in [("truncation_review", "FAIL", 1), ("repaired_review", "PASS", 0)]:
        assert main(["check", str(path), "--assessment", assessment, "--json"]) == exit_code
        entry = json.loads(capsys.readouterr().out)["contracts"][0]
        assert next(c for c in entry["checks"] if c["name"] == "recorded_support")["status"] == status
        assert [a["id"] for a in entry["assessments"]] == [assessment]
    assert main(["check", str(path), "--json"]) == 0
    entry = json.loads(capsys.readouterr().out)["contracts"][0]
    assert not any(c["name"] == "recorded_support" for c in entry["checks"])
    assert [a["status"] for a in entry["assessments"]] == ["contradicted", "supported"]
    assert main(["explain", str(path), "--assessment", "truncation_review", "--investigation", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)["contracts"][0]
    item = report["items"][0]
    assert item["record"]["status"] == "contradicted"
    assert "Investigate the recorded contradiction" in json.dumps(item["suggested_steps"])
    assert "preserving this judgment" in json.dumps(item["suggested_steps"])
    assert any(a["record"]["status"] == "contradicted" for a in report["investigation"]["assessments"])
    assert path.read_bytes() == before


def test_contradiction_pins_equations_and_detects_changed_definitions(tmp_path, capsys):
    data = equation_data()
    data["assessments"][0]["status"] = "contradicted"
    contract = ContractV03.model_validate(data)
    missing = deepcopy(data)
    missing["assessments"][0].update(equation_pins=[], binding_pins=[])
    with pytest.raises(ValidationError, match="Contradicted assessments must pin every Claim equation"):
        ContractV03.model_validate(missing)
    data["equations"][0]["latex"] = "n = 0"
    path = tmp_path / "stale.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert main(["check", str(path), "--assessment", "formulation_review", "--json"]) == 1
    entry = json.loads(capsys.readouterr().out)["contracts"][0]
    assert next(c for c in entry["checks"] if c["name"] == "equation_definitions")["status"] == "FAIL"
    assert load_contract(path).assessments == contract.assessments


def test_new_contradiction_preserves_legacy_declarations_and_restoration():
    original = load_contract(ROOT / "contracts/h2_solubility.yaml")
    migrated = migrate_contract(ROOT / "contracts/h2_solubility.yaml")
    data = migrated.model_dump()
    reviewed = deepcopy(data["assessments"][0])
    reviewed.update(id="new_review", status="contradicted", origin="reviewed",
                    method={"id": "new_review", "revision": "1", "description": "Synthetic review."})
    data["assessments"].append(reviewed)
    assert restore_v01(ContractV02.model_validate(data)) == original
    legacy = original.model_dump()
    legacy["claims"][0]["status"] = "contradicted"
    with pytest.raises(ValidationError):
        Contract.model_validate(legacy)


def test_decision_basis_detects_rewritten_status_but_not_a_new_review(contrary_data):
    contrary_data["schema_version"] = "0.4"
    contract = ContractV04.model_validate(contrary_data)
    pin = decision_basis_digest(contract, "assessment", "truncation_review")
    contrary_data["decisions"] = [{
        "id": "repair", "revision": "1", "question": "What should be investigated next?",
        "scope": "Synthetic truncation failure.", "options": [{"id": "extend", "description": "Add levels."}],
        "selected": "extend", "reasons": ["Investigate the failed truncation criterion."],
        "basis": [{"kind": "assessment", "id": "truncation_review", "sha256": pin}],
    }]
    next_review = {**contrary_data["assessments"][0], "id": "new_unknown", "status": "unknown"}
    contrary_data["assessments"].append(next_review)
    contract = ContractV04.model_validate(contrary_data)
    assert decision_basis_digest(contract, "assessment", "truncation_review") == pin
    assert decision_basis_checks(contract, contract.decisions[0])[0]["status"] == "PASS"
    contrary_data["assessments"][0]["status"] = "unknown"
    changed = ContractV04.model_validate(contrary_data)
    assert decision_basis_checks(changed, changed.decisions[0])[0]["status"] == "FAIL"


def test_graph_and_generated_docs_preserve_contradiction(contrary_data, tmp_path):
    source = tmp_path / "contract.json"
    source.write_text(json.dumps(contrary_data), encoding="utf-8")
    graph = build_graph(paths=[source], root=tmp_path)
    record = next(n["record"] for n in graph["nodes"] if n["type"] == "assessment")
    assert record["status"] == "contradicted"
    output = tmp_path / "docs"
    docs.build([{"provider": "fixture", "root": tmp_path, "paths": [source.name]}], [], output,
               source_root=tmp_path)
    rendered = "\n".join(p.read_text() for p in output.glob("*.rst"))
    assert "contradicted" in rendered and docs.text("7.74%") in rendered
