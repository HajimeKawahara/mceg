"""Authored task completion uses synthetic records and preserves their history."""

from copy import deepcopy
import json
import shlex

import pytest

from mceg import ContractV02, load_contract, restore_v01, trace_provenance
from mceg.__main__ import main
from mceg.check import check_contract
from mceg.explain import SOURCE_ACTIONS, explain_contract
from mceg.migration import migrate_contract


@pytest.fixture
def reviewed(tmp_path):
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({
        "schema_version": "0.1",
        "model": {"id": "fixture", "name": "Synthetic review", "description": "No real model or publication.",
                  "implementation": {"repository": "https://example.org/fixture", "revision": "1",
                                     "entry_points": ["fixture:evaluate"]}},
        "assumptions": [], "limitations": [],
        "domains": [{"kind": "scientific_applicability", "status": "unknown", "conditions": [],
                     "description": "Not evaluated.", "evidence": ["original-source"]}],
        "claims": [{"id": "accuracy", "statement": "The model meets its accuracy criterion.",
                    "kind": "physical_validation", "status": "unknown", "scope": "Synthetic scope.",
                    "evidence": ["original-source"]}],
        "evidence": [{"id": "original-source", "kind": "literature", "summary": "Synthetic source.",
                      "sources": ["https://example.org/source"], "scope": "Source conventions only.",
                      "provenance": {"role": "primary", "location": "Synthetic section.",
                                     "inspection": "not_inspected", "note": "Historical gap."}}],
    }))
    original = migrate_contract(legacy)
    data = original.model_dump()
    source = deepcopy(data["evidence"][0])
    source["id"] = "reviewed-source"
    source["provenance"].update(inspection="inspected", note="Synthetic completed inspection.")
    data["evidence"].append(source)
    data["contexts"].append({"id": "review", "scope": "Synthetic review context."})
    data["assessments"].append({
        "id": "current-review", "kind": "evidence_support", "subject": "imported", "context": "review",
        "claim": "accuracy", "claim_revision": original.claims[0].revision,
        "status": "unknown", "origin": "reviewed", "evidence": ["reviewed-source"],
        "method": {"id": "manual-review", "revision": "1", "description": "Synthetic source review."},
        "reasons": ["Source inspection supplies no physical comparison."],
    })
    data["follow_ups"] = [
        {"id": "inspect-source", "target_kind": "evidence", "target": "original-source",
         "action": "Inspect the source conventions.", "completion": "Record the inspected scope."},
        {"id": "validate-model", "target_kind": "evidence", "target": "reviewed-source",
         "action": "Evaluate physical accuracy.", "completion": "Record an independent comparison."},
    ]
    data["follow_up_resolutions"] = [{
        "follow_up": "inspect-source", "evidence": ["reviewed-source"],
        "note": "Source conventions inspected; physical validation remains pending.",
    }]
    contract = ContractV02.model_validate(data)
    path = tmp_path / "reviewed contract.json"
    path.write_text(contract.model_dump_json())
    return path, contract, original, legacy


def test_completion_preserves_history_and_never_promotes_support(reviewed, capsys):
    path, contract, original, legacy = reviewed
    before = path.read_bytes()
    assert restore_v01(contract) == load_contract(legacy)
    assert trace_provenance(contract, "original-source") == trace_provenance(original, "original-source")
    item = explain_contract(path, {}, evidence_id="original-source")["items"][0]
    assert item["recorded_follow_ups"] == item["suggested_steps"] == []
    assert item["record"]["provenance"]["inspection"] == "not_inspected"
    assert item["issues"] == ["source_not_fully_inspected"]
    assert item["resolved_follow_ups"][0]["instruction"]["id"] == "inspect-source"
    command = next(c for c in item["next_commands"] if c.endswith("--evidence reviewed-source"))
    assert main([*shlex.split(command)[1:], "--json"]) == 0
    target = json.loads(capsys.readouterr().out)["contracts"][0]["items"][0]
    assert target["recorded_follow_ups"][0]["id"] == "validate-model"
    assert main(["explain", str(path), "--evidence", "original-source", "--plain"]) == 0
    output = capsys.readouterr().out
    assert "Completed follow-up: inspect-source" in output
    assert "Inspect the source conventions." not in output
    assert "Obtain and inspect" not in output
    checks = {c["name"]: c["status"] for c in check_contract(path, {}, "current-review")["checks"]}
    assert checks == {"structure": "PASS", "source_audit": "PASS", "recorded_support": "UNKNOWN"}
    assert all(a.status == "unknown" for a in contract.assessments)
    assert path.read_bytes() == before


def test_inspected_evidence_does_not_complete_a_task_without_a_resolution(reviewed):
    path, contract, _, _ = reviewed
    data = contract.model_dump(exclude={"follow_up_resolutions"})
    before = ContractV02.model_validate(data)
    assert before.follow_up_resolutions == []
    path.write_text(before.model_dump_json())
    item = explain_contract(path, {}, evidence_id="original-source")["items"][0]
    assert item["recorded_follow_ups"][0]["id"] == "inspect-source"
    assert "resolved_follow_ups" not in item
    assert SOURCE_ACTIONS["source_not_fully_inspected"] in item["suggested_steps"]


def test_one_completed_task_does_not_hide_other_pending_inspection_work(reviewed):
    path, contract, _, _ = reviewed
    data = contract.model_dump()
    task = deepcopy(data["follow_ups"][0])
    task.update(id="another-task", action="Inspect another explicitly unresolved aspect.")
    data["follow_ups"].append(task)
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    item = explain_contract(path, {}, evidence_id="original-source")["items"][0]
    assert [f["id"] for f in item["recorded_follow_ups"]] == ["another-task"]
    assert item["resolved_follow_ups"][0]["follow_up"] == "inspect-source"
    assert SOURCE_ACTIONS["source_not_fully_inspected"] in item["suggested_steps"]


@pytest.mark.parametrize("kind,target,selector", [("claim", "accuracy", "claim_id"),
                                                  ("assessment", "current-review", "assessment_id")])
def test_completion_also_applies_to_claim_and_assessment_tasks(reviewed, kind, target, selector):
    path, contract, _, _ = reviewed
    data = contract.model_dump()
    data["follow_ups"][0].update(target_kind=kind, target=target,
                                revision=contract.claims[0].revision if kind == "claim" else None)
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    item = explain_contract(path, {}, **{selector: target})["items"][0]
    assert item["recorded_follow_ups"] == []
    assert item["resolved_follow_ups"][0]["follow_up"] == "inspect-source"


@pytest.mark.parametrize("mutate", [
    lambda d: d[0].update(follow_up="missing"),
    lambda d: d[0].update(evidence=["missing"]),
    lambda d: d[0].update(evidence=[]),
    lambda d: d[0].update(evidence=["reviewed-source"] * 2),
    lambda d: d[0].update(note=" "),
    lambda d: d[0].update(status="supported"),
    lambda d: d.append(deepcopy(d[0])),
])
def test_invalid_completion_records_are_rejected(reviewed, mutate):
    _, contract, _, _ = reviewed
    data = contract.model_dump()
    mutate(data["follow_up_resolutions"])
    with pytest.raises(ValueError):
        ContractV02.model_validate(data)
