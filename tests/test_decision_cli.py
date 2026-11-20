"""Choice inspection preserves historical decisions and scoped scientific support."""

from copy import deepcopy
import json

import pytest

from mceg import ContractV04
from mceg.__main__ import main
from mceg.decisions import decision_basis_checks
from mceg.explain import explain_contract
from mceg.investigation import build_investigation
from test_decision_schema import example_data


@pytest.fixture
def recorded(tmp_path):
    data = example_data()
    path = tmp_path / "decision.json"
    path.write_text(json.dumps(data))
    return path, data


def run_json(capsys, path, command="explain", *options):
    code = main([command, str(path), *options, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_choice_with_unknown_support_has_matching_basis(recorded, capsys):
    path, _ = recorded
    before = path.read_bytes()
    code, report = run_json(capsys, path, "check", "--decision", "density_model")
    assert code == 0
    entry = report["contracts"][0]
    assert entry["decisions"][0]["selected"] == "continuity"
    assert entry["audit_scope"] == {"kind": "decision", "decisions": [
        {"id": "density_model", "revision": "1"}]}
    assert next(c for c in entry["checks"] if c["name"] == "decision_basis")["status"] == "PASS"
    _, report = run_json(capsys, path, "explain", "--decision", "density_model")
    item = report["contracts"][0]["items"][0]
    assert item["basis_assessments"][0]["status"] == "unknown"
    assert "status" not in item["record"]
    assert "Review" not in str(item["suggested_steps"])
    assert path.read_bytes() == before


def test_changed_upstream_source_fails_pin_check_without_changing_history(recorded, capsys):
    path, data = recorded
    original = deepcopy(data["decisions"])
    data["evidence"][0]["summary"] = "A changed upstream source statement."
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    code, report = run_json(capsys, path, "check", "--decision", "density_model")
    assert code == 1
    check = next(c for c in report["contracts"][0]["checks"] if c["name"] == "decision_basis")
    assert check["status"] == "FAIL"
    assert all(pin["status"] == "FAIL" for pin in check["pins"])
    assert json.loads(path.read_text())["decisions"] == original
    assert path.read_bytes() == before


def test_empty_basis_is_unknown_not_accepted_or_rejected(recorded, capsys):
    path, data = recorded
    data["decisions"][0]["basis"] = []
    path.write_text(json.dumps(data))
    code, report = run_json(capsys, path, "check", "--decision", "density_model")
    assert code == 0
    assert report["summary"]["UNKNOWN"] > 0
    check = next(c for c in report["contracts"][0]["checks"] if c["name"] == "decision_basis")
    assert check["status"] == "UNKNOWN"
    assert report["contracts"][0]["audited_evidence"] == []


def test_retained_revisions_are_explicit_and_do_not_imply_current_implementation(recorded, capsys):
    path, data = recorded
    newer = deepcopy(data["decisions"][0])
    newer.update(revision="draft-a", selected="power_law",
                 supersedes={"id": "density_model", "revision": "1"})
    data["decisions"].insert(0, newer)
    path.write_text(json.dumps(data))
    _, report = run_json(capsys, path, "explain", "--decision", "density_model")
    choices = [item for item in report["contracts"][0]["items"] if "record" in item]
    assert [i["record"]["revision"] for i in choices] == ["draft-a", "1"]
    assert choices[1]["superseded_by"] == [{"id": "density_model", "revision": "draft-a"}]
    assert "current" not in choices[0] and "current" not in choices[1]
    code, report = run_json(capsys, path, "check", "--decision", "density_model", "--decision-revision", "1")
    assert code == 0
    assert len(report["contracts"][0]["decisions"]) == 1
    assert report["contracts"][0]["decisions"][0]["selected"] == "continuity"


def test_decision_investigation_keeps_exact_basis_without_sibling_assessments(recorded, capsys):
    path, data = recorded
    unrelated = deepcopy(data["assessments"][0])
    unrelated["id"] = "unrelated_review"
    data["assessments"].append(unrelated)
    path.write_text(json.dumps(data))
    _, report = run_json(capsys, path, "explain", "--decision", "density_model", "--investigation")
    bundle = report["contracts"][0]["investigation"]
    assert bundle["selection"][0]["kind"] == "decision"
    assert bundle["selection"][0]["revision"] == "1"
    assert {a["id"] for a in bundle["assessments"]} == {"formulation_review"}
    assert {e["id"] for e in bundle["evidence"]} == {"review_notes", "derivation"}
    assert bundle["assessments"][0]["record"]["status"] == "unknown"
    assert [d["id"] for d in bundle["decisions"]] == ["density_model"]


def test_related_choice_does_not_broaden_selected_assessment_audit(recorded, capsys):
    path, data = recorded
    data["evidence"][1]["summary"] = "Changed evidence outside the selected Assessment."
    path.write_text(json.dumps(data))
    contract = ContractV04.model_validate(data)
    assert decision_basis_checks(contract, contract.decisions[0])[0]["status"] == "FAIL"
    code, report = run_json(capsys, path, "check", "--assessment", "formulation_review")
    assert code == 0
    assert not any(c["name"] == "decision_basis" for c in report["contracts"][0]["checks"])
    _, report = run_json(capsys, path, "explain", "--assessment", "formulation_review", "--investigation")
    entry = report["contracts"][0]
    assert entry["audit_scope"]["kind"] == "assessment"
    assert entry["audited_evidence"] == ["derivation"]
    assert entry["investigation"]["decisions"][0]["record"]["selected"] == "continuity"
    assert "review_notes" not in {e["id"] for e in entry["investigation"]["evidence"]}


def test_overview_and_plain_output_expose_choices_and_unknown_support(recorded, capsys):
    path, _ = recorded
    _, report = run_json(capsys, path)
    assert report["contracts"][0]["decisions"][0]["selected"] == "continuity"
    assert main(["explain", str(path), "--decision", "density_model", "--plain"]) == 0
    text = capsys.readouterr().out
    assert "selected: continuity" in text
    assert "Referenced Assessment: formulation_review; unknown" in text
    assert main(["explain", str(path), "--decision", "density_model", "--investigation", "--plain"]) == 0
    text = capsys.readouterr().out
    assert "Decision: density_model@1" in text and "unknown" in text


def test_investigation_retains_missing_basis_action_and_claim_navigation(recorded, capsys):
    path, data = recorded
    _, report = run_json(capsys, path, "explain", "--claim", "equation_implementation", "--investigation")
    assert report["contracts"][0]["investigation"]["decisions"][0]["id"] == "density_model"
    data["decisions"][0]["basis"] = []
    path.write_text(json.dumps(data))
    _, report = run_json(capsys, path, "explain", "--decision", "density_model", "--investigation")
    steps = report["contracts"][0]["investigation"]["suggested_steps"]
    assert len(steps) == 1
    assert steps[0]["target_kind"] == "decision" and steps[0]["revision"] == "1"
    assert "missing or changed basis" in steps[0]["action"]


@pytest.mark.parametrize("command", ["check", "explain"])
@pytest.mark.parametrize("options", [
    ["--decision-revision", "1"],
    ["--decision", "absent"],
    ["--decision", "density_model", "--decision-revision", "absent"],
    ["--decision", "density_model", "--assessment", "formulation_review"],
    ["--decision", "density_model", "--root", "."],
    ["--decision", "density_model", "--temperature", "1750"],
])
def test_invalid_selection_does_not_silently_fall_back(recorded, command, options):
    path, _ = recorded
    with pytest.raises(SystemExit) as error:
        main([command, str(path), *options])
    assert error.value.code == 2


def test_python_selectors_reject_conflicting_targets(recorded):
    path, data = recorded
    with pytest.raises(ValueError, match="Select one"):
        explain_contract(path, {}, assessment_id="formulation_review", decision_id="density_model")
    with pytest.raises(ValueError, match="exactly one"):
        build_investigation(ContractV04.model_validate(data), path,
                            evidence_id="derivation", decision_id="density_model")
