"""An adopted connection is part of review identity, not merely a drawing."""

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from mceg import documentation as docs
from mceg import load_contract
from mceg.check import check_contract
from mceg.decisions import decision_basis_checks
from mceg.explain import explain_contract
from mceg.graph import build_graph
from mceg.readiness import check_readiness
from mceg.schema_v04 import decision_basis_digest
from mceg.schema_v05 import ContractV05, mathematical_model_digest
from test_mathematical_schema import mathematical_data


def write_model(tmp_path):
    data = mathematical_data()
    source = tmp_path / "src/provider.py"
    source.parent.mkdir()
    source.write_text(
        "raise RuntimeError('Inspection must not import the provider')\n"
        "def hydrogen_nuclei_density(radius_cm, velocity_kms, mass_loss_g_s):\n"
        "    return None\n"
    )
    data["subjects"][0]["selected_files"]["src/provider.py"] = sha256(source.read_bytes()).hexdigest()
    other = deepcopy(data["quantities"][0])
    other.update(id="diagnostic_density", description="A diagnostic density, not the solved density.")
    data["quantities"].append(other)
    model = data["mathematical_models"][0]
    model["quantities"]["diagnostic"] = {
        "quantity": {"id": "diagnostic_density", "revision": "1"}, "role": "input"}
    contract = ContractV05.model_validate(data)
    data["assessments"][0]["mathematical_model_pins"][0]["sha256"] = (
        mathematical_model_digest(contract, "wind", "1"))
    contract = ContractV05.model_validate(data)
    snapshot = decision_basis_digest(contract, "assessment", "formulation_review")
    data["decisions"] = [{
        "id": "adopt", "revision": "1", "question": "Which declared model should this fixture use?",
        "scope": "Synthetic review lifecycle only.",
        "options": [{"id": "wind", "description": "Adopt the reviewed wind connections."}],
        "selected": "wind", "reasons": ["Exercise dependency identity without executing physics."],
        "basis": [{"kind": "assessment", "id": "formulation_review", "sha256": snapshot}],
    }]
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(data))
    use = {
        "schema_version": "0.1", "id": "fixture.model", "purpose": "Inspect this declared correspondence.",
        "mode": "scientific",
        "target": {"contract": path.name, "subject": "implementation", "context": "review",
                   "entry_point": "src/provider.py:hydrogen_nuclei_density"},
        "requirements": [{"assessment": "formulation_review", "role": "implementation", "sha256": snapshot}],
    }
    use_path = tmp_path / "use.json"
    use_path.write_text(json.dumps(use))
    return path, use_path, data


def statuses(report, key):
    return {check["name"]: check["status"] for check in report[key] if "name" in check}


@pytest.mark.parametrize("change", [
    lambda d: d["mathematical_models"][0]["relations"][0]["quantities"].update(n_h="diagnostic"),
    lambda d: d["quantities"][0].update(description="Ion density instead of total nuclei density."),
    lambda d: d["quantities"][2].update(domain="Radius about a different physical center."),
    lambda d: d["equations"][0]["assumptions"].append("An additional closure assumption."),
    lambda d: d["mathematical_models"][0]["quantities"]["velocity"].update(role="unknown"),
])
def test_model_changes_stale_assessment_decision_and_use_without_rewriting_support(tmp_path, change):
    path, use_path, data = write_model(tmp_path)
    assert check_readiness(use_path, root=tmp_path)["ready"]
    before = deepcopy(data["assessments"])
    change(data)
    path.write_text(json.dumps(data))
    original_bytes = path.read_bytes()
    report = check_contract(path, {}, "formulation_review", root=tmp_path)
    assert statuses(report, "checks")["mathematical_model_definitions"] == "FAIL"
    assert statuses(report, "checks")["recorded_support"] == "PASS"
    explanation = explain_contract(path, {}, assessment_id="formulation_review", root=tmp_path)
    assert statuses(explanation, "items")["mathematical_model_definitions"] == "FAIL"
    contract = load_contract(path)
    assert any(c["status"] == "FAIL" for c in decision_basis_checks(contract, contract.decisions[0]))
    readiness = check_readiness(use_path, root=tmp_path)
    assert not readiness["ready"]
    checks = statuses(readiness["requirements"][0], "checks")
    assert checks["assessment_pin"] == checks["mathematical_model_definitions"] == "FAIL"
    assert json.loads(path.read_text())["assessments"] == before
    assert path.read_bytes() == original_bytes


def test_model_only_claim_is_checked_and_unknown_review_stays_unknown(tmp_path):
    path, _, data = write_model(tmp_path)
    data["claims"][0]["equations"] = []
    data["assessments"][0].update(equation_pins=[], binding_pins=[], status="unknown",
                                   mathematical_model_pins=[])
    data["decisions"] = []
    path.write_text(json.dumps(data))
    report = check_contract(path, {}, "formulation_review", root=tmp_path)
    assert statuses(report, "checks")["mathematical_model_definitions"] == "UNKNOWN"
    assert statuses(report, "checks")["recorded_support"] == "UNKNOWN"


def test_assurance_graph_retains_model_quantity_instances_and_review_links(tmp_path):
    path, _, _ = write_model(tmp_path)
    graph = build_graph(paths=[path], root=tmp_path)
    nodes = {node["id"]: node for node in graph["nodes"]}
    kinds = {node["type"] for node in nodes.values()}
    assert {"quantity", "mathematical_model", "model_quantity", "relation_instance"} <= kinds
    edges = {kind: [edge for edge in graph["edges"] if edge["type"] == kind]
             for kind in {edge["type"] for edge in graph["edges"]}}
    assert edges["refers_to_mathematical_model"] and edges["pins_mathematical_model"]
    assert len(edges["involves_quantity"]) == 5
    for edge in edges["involves_quantity"]:
        assert edge["data"]["directed"] is False
        assert nodes[edge["source"]]["type"] == "relation_instance"
        assert nodes[edge["target"]]["type"] == "model_quantity"
    assert "implements" not in edges and "supports" not in edges


def test_generated_docs_preserve_quantity_meanings_connections_and_pins(tmp_path):
    path, _, _ = write_model(tmp_path)
    catalog = docs.Catalog(tmp_path / "generated")
    entry = catalog.add("fixture", tmp_path, path.name)
    records = docs.records_page(catalog, entry)
    for quantity in entry.contract.quantities:
        assert entry.anchor("quantity", quantity.id, quantity.revision) in records
        assert docs.text(quantity.description) in records
    model = entry.contract.mathematical_models[0]
    assert entry.anchor("mathematical_model", model.id, model.revision) in records
    assert "n\\_h = n\\_h" in records
    reference = entry.link("mathematical_model", model.id, model.revision)
    assert reference in docs.assessment_page(entry, entry.contract.assessments[0])
    assert entry.link("mathematical_model", model.id, model.revision,
                      label=f"{model.id} ({model.revision})") in docs.assessments_page(entry)
