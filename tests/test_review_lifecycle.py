"""Authored task completion uses synthetic records and preserves their history."""

from copy import deepcopy
import json
import shlex
import sys

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


@pytest.fixture
def compared(reviewed):
    path, contract, _, _ = reviewed
    data = contract.model_dump()
    for source in data["evidence"]:
        source["provenance"]["inspection"] = "inspected"
        source["artifacts"] = [{"source": "https://example.org/source", "sha256": "a" * 64}]
    review = {
        "id": "old-review", "kind": "implementation", "summary": "Synthetic implementation review.",
        "sources": ["model.py"], "scope": "Synthetic equation convention.",
        "provenance": {"role": "implementation", "location": "model.py:pressure",
                       "inspection": "inspected", "note": "Historical comparison gap.",
                       "derived_from": [{"evidence": "original-source", "comparison": "not_checked",
                                         "note": "Equivalence had not been checked."}]},
    }
    data["evidence"].append(review)
    updated = deepcopy(review)
    updated.update(id="follow-up-review", summary="Source audit")
    updated["provenance"]["derived_from"] = [
        {"evidence": "reviewed-source", "comparison": "discrepancy", "note": "A convention differs."}]
    data["evidence"].append(updated)
    data["follow_ups"][0].update(id="compare-source", target="old-review",
                                 action="Compare the equation convention.", completion="Record the comparison.")
    data["follow_ups"].append({
        "id": "clarify-difference", "target_kind": "evidence", "target": "follow-up-review",
        "action": "Clarify the differing convention.", "completion": "Record its intended definition.",
    })
    data["follow_up_resolutions"][0].update(follow_up="compare-source", evidence=["follow-up-review"],
                                           note="Compared; the convention still needs clarification.")
    data["assessments"][-1]["evidence"] = ["follow-up-review"]
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    return path, data


@pytest.mark.parametrize("identity", ["id", "hash"])
@pytest.mark.parametrize("outcome", ["consistent", "discrepancy"])
def test_completed_comparison_routes_to_results_without_rewriting_history(compared, identity, outcome):
    path, data = compared
    link = data["evidence"][-1]["provenance"]["derived_from"][0]
    link["comparison"] = outcome
    if identity == "id":
        link["evidence"] = "original-source"
        for source in data["evidence"][:2]:
            source["artifacts"] = []
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    before = path.read_bytes()
    trace = trace_provenance(load_contract(path), "old-review")
    item = explain_contract(path, {}, evidence_id="old-review")["items"][0]
    assert item["suggested_steps"] == item["recorded_follow_ups"] == []
    assert item["issues"] == ["comparison_not_checked"]
    assert item["comparisons"][0]["comparison"] == "not_checked"
    assert item["historical_steps"][0]["comparison_targets"][0]["evidence"] == "original-source"
    assert item["completed_comparisons"][0]["comparison"] == outcome
    assert item["completed_comparisons"][0]["source"] == link["evidence"]
    commands = [shlex.split(c) for c in item["next_commands"]]
    assert commands[0][-2:] == ["--assessment", "current-review"]
    assert commands[1][-2:] == ["--evidence", "follow-up-review"]
    follow_up = explain_contract(path, {}, evidence_id="follow-up-review")["items"][0]
    assert follow_up["recorded_follow_ups"][0]["id"] == "clarify-difference"
    assessment = explain_contract(path, {}, assessment_id="current-review")["items"][0]
    assert assessment["record"]["status"] == "unknown"
    assert trace_provenance(load_contract(path), "old-review") == trace
    assert not trace["recorded_audit_complete"]
    assert path.read_bytes() == before


@pytest.mark.parametrize("gap", ["url_only", "different_bytes", "source_only",
                                "unchecked", "no_resolution", "open_task"])
def test_completion_does_not_hide_comparisons_without_scoped_review(compared, gap):
    path, data = compared
    if gap == "url_only":
        data["evidence"][1]["artifacts"] = []
    elif gap == "different_bytes":
        data["evidence"][1]["artifacts"][0]["sha256"] = "b" * 64
    elif gap == "source_only":
        data["follow_up_resolutions"][0]["evidence"] = ["reviewed-source"]
    elif gap == "unchecked":
        data["evidence"][-1]["provenance"]["derived_from"][0]["comparison"] = "not_checked"
    elif gap == "no_resolution":
        data["follow_up_resolutions"] = []
    else:
        task = deepcopy(data["follow_ups"][0])
        task["id"] = "another-comparison"
        data["follow_ups"].append(task)
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    item = explain_contract(path, {}, evidence_id="old-review")["items"][0]
    assert item["suggested_steps"][0]["comparison_targets"][0]["evidence"] == "original-source"
    assert not item.get("historical_steps")
    assert not item.get("completed_comparisons")


def test_completion_keeps_unrelated_unchecked_sources_and_discrepancies(compared):
    path, data = compared
    links = data["evidence"][-2]["provenance"]["derived_from"]
    for key, outcome, digest in [("another-source", "not_checked", "b"),
                                 ("differing-source", "discrepancy", "c")]:
        source = deepcopy(data["evidence"][0])
        source["id"] = key
        source["artifacts"][0]["sha256"] = digest * 64
        data["evidence"].append(source)
        links.append({"evidence": key, "comparison": outcome, "note": "A separate review gap."})
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    item = explain_contract(path, {}, evidence_id="old-review")["items"][0]
    targets = [t["evidence"] for s in item["suggested_steps"] for t in s["comparison_targets"]]
    assert targets == ["another-source", "differing-source"]
    assert item["historical_steps"][0]["comparison_targets"][0]["evidence"] == "original-source"
    assert item["comparisons"] == links


def test_completed_comparison_explains_progress_in_both_languages_and_layouts(compared, monkeypatch, capsys):
    path, _ = compared
    before = path.read_bytes()
    args = ["explain", str(path), "--evidence", "old-review"]
    assert main([*args, "--json"]) == 0
    machine_report = capsys.readouterr().out
    assert main([*args, "--json", "--lang", "ja"]) == 0
    assert capsys.readouterr().out == machine_report
    monkeypatch.setenv("NO_COLOR", "1")
    for lang in ("en", "ja"):
        for terminal in (False, True):
            monkeypatch.setattr(sys.stdout, "isatty", lambda: terminal)
            assert main([*args, "--lang", lang]) == 0
            output = capsys.readouterr().out
            compact = "".join(output.split())
            heading = "Review progress" if lang == "en" else "確認作業の進み具合"
            history = "Original record (history retained)" if lang == "en" else "元の記録（当時の状態を保持）"
            assert output.index(heading) < output.index(history)
            explanation = ("Compared; differences remain to be explained." if lang == "en"
                           else "比較済み：違いが見つかり、その理由や扱いの確認が残っています。")
            assert "".join(explanation.split()) in compact
            assert "Source audit" in output  # Authored result summaries remain original.
            assert "not_checked" in output  # The historical link remains available.
            assert "Suggested next step" not in output and "提案する次の作業" not in output
            commands = [line.split(": ", 1)[1] for line in output.splitlines() if ": mceg explain " in line]
            assert len(commands) == 2
            for command in commands:
                options = shlex.split(command)[1:]
                assert options[:2] == ["explain", str(path)]
                assert options[4:] == (["--lang", "ja"] if lang == "ja" else [])
                assert main(options) == 0
                capsys.readouterr()
    assert path.read_bytes() == before


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
