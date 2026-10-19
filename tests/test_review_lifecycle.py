"""Assessment selection and authored task completion preserve scientific history."""

from copy import deepcopy
import json
import shlex

import pytest

from mceg import ContractV02, load_contract, restore_v01, trace_provenance
from mceg.__main__ import main
from mceg.check import check_contract
from mceg.explain import SOURCE_ACTIONS, explain_contract
from test_h2_literature_update import ROOT, TRIAL


SELECTED = "physical_accuracy:full_text:2026-10-19"


@pytest.fixture
def reviewed(tmp_path):
    path = tmp_path / "reviewed contract.json"
    contract = TRIAL["build"]()
    path.write_text(contract.model_dump_json())
    return path, contract


def test_selected_check_and_explanation_share_only_the_evidence_dependencies(reviewed, capsys):
    path, contract = reviewed
    before = path.read_bytes()
    assert main(["check", str(path), "--assessment", SELECTED, "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["summary"] == {"PASS": 1, "FAIL": 0, "UNKNOWN": 2}
    entry = report["contracts"][0]
    assert entry["audit_scope"] == {"kind": "assessment", "assessment": SELECTED,
                                    "subject": "imported", "context": "h2-1750K-7500bar"}
    assert [a["id"] for a in entry["assessments"]] == [SELECTED]
    assert set(entry["audited_evidence"]) == {
        "implementation_full_text", "formulation_full_text", "experimental_fit_full_text",
        "experimental_runs_full_text", "calibration_adoption_full_text", "original_calibration",
        "infrared_recalibration",
    }
    assert main([*shlex.split(report["explain_command"])[1:], "--json"]) == 0
    explanation = json.loads(capsys.readouterr().out)["contracts"][0]
    assert explanation["audit_scope"] == entry["audit_scope"]
    assert explanation["audited_evidence"] == entry["audited_evidence"]
    assert set(explanation["evidence_gaps"]) == {"calibration_adoption_full_text", "original_calibration"}
    assert explanation["items"][0]["record"]["status"] == "unknown"
    assert main(["check", str(path), "--json"]) == 1
    history = json.loads(capsys.readouterr().out)["contracts"][0]
    assert history["audit_scope"]["kind"] == "all_records_including_history"
    assert "experimental_fit" in history["audited_evidence"]
    assert len(history["assessments"]) == len(contract.assessments)
    assert path.read_bytes() == before


@pytest.mark.parametrize("roots,expected_audit", [(["implementation_full_text"], "PASS"), ([], "UNKNOWN")])
def test_source_audit_never_promotes_physical_support(reviewed, roots, expected_audit):
    path, contract = reviewed
    data = contract.model_dump()
    assessment = next(a for a in data["assessments"] if a["id"] == SELECTED)
    assessment["evidence"] = roots
    assessment["reasons"] = ["Synthetic scope probe; no physical comparison was performed."]
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    entry = check_contract(path, {}, SELECTED)
    checks = {c["name"]: c for c in entry["checks"]}
    assert checks["source_audit"]["status"] == expected_audit
    assert checks["recorded_support"]["status"] == "UNKNOWN"
    if not roots:
        assert entry["audited_evidence"] == []
        assert "No evidence" in checks["source_audit"]["message"]


def test_selected_membership_is_recomputed_and_does_not_collect_other_ranges(reviewed):
    path, contract = reviewed
    data = contract.model_dump()
    assessment = next(a for a in data["assessments"]
                      if a.get("condition") == "temperature_basalt_full_text")
    assessment["classification"] = "within_reported_range"
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    entry = check_contract(path, {}, assessment["id"])
    assert entry["audited_evidence"] == ["experimental_runs_full_text"]
    assert [c["name"] for c in entry["checks"]] == ["structure", "source_audit", "temperature_basalt_full_text"]
    comparison = entry["checks"][-1]
    assert comparison["status"] == "FAIL"
    assert "outside_reported_range" in comparison["message"]
    assert any("Recorded classification differs" in reason for reason in comparison["details"])


@pytest.mark.parametrize("language", ["en", "ja"])
def test_selected_navigation_retains_quoted_path_id_and_language(reviewed, capsys, language):
    path, _ = reviewed
    assert main(["check", str(path), "--assessment", SELECTED, "--lang", language, "--plain"]) == 0
    output = capsys.readouterr().out
    hint = next(line.split(": ", 1)[1] for line in output.splitlines() if ": mceg explain " in line)
    args = shlex.split(hint)[1:]
    assert str(path) in args and args[args.index("--assessment") + 1] == SELECTED
    if language == "ja":
        assert args[-2:] == ["--lang", "ja"]
    assert main([*args, "--json"]) == 0
    explanation = json.loads(capsys.readouterr().out)
    assert explanation["contracts"][0]["audit_scope"]["assessment"] == SELECTED
    assert main(["check", str(path), "--assessment", SELECTED, "--json"]) == 0
    english = capsys.readouterr().out
    assert main(["check", str(path), "--assessment", SELECTED, "--lang", language, "--json"]) == 0
    assert capsys.readouterr().out == english


@pytest.mark.parametrize("selector", ["missing", ""])
def test_missing_assessment_is_a_usage_error(reviewed, selector, capsys):
    path, _ = reviewed
    with pytest.raises(SystemExit) as error:
        main(["check", str(path), "--assessment", selector, "--json"])
    assert error.value.code == 2
    assert "Assessment ID not found" in capsys.readouterr().err


def test_selection_filters_other_valid_contracts_and_retains_structural_errors(reviewed, tmp_path, capsys):
    path, _ = reviewed
    legacy = ROOT / "contracts/h2_solubility.yaml"
    assert main(["check", str(path), str(legacy), "--assessment", SELECTED, "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["collected"] == 2 and len(report["contracts"]) == 1
    with pytest.raises(SystemExit) as error:
        main(["check", str(legacy), "--assessment", SELECTED])
    assert error.value.code == 2
    capsys.readouterr()
    with pytest.raises(SystemExit) as error:
        main(["check", str(path), "--assessment", SELECTED, "--temperature", "1750"])
    assert error.value.code == 2
    capsys.readouterr()
    broken = tmp_path / "broken.yaml"
    broken.write_text("schema_version: [unterminated\n")
    assert main(["check", str(path), str(broken), "--assessment", SELECTED, "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["summary"]["FAIL"] == 1


def test_resolution_is_explicit_and_does_not_rewrite_inspection_or_support(reviewed, capsys):
    path, contract = reviewed
    original = load_contract(TRIAL["BASELINE"])
    assert restore_v01(contract) == restore_v01(original)
    for evidence in original.evidence:
        assert trace_provenance(contract, evidence.id) == trace_provenance(original, evidence.id)
    detail = explain_contract(path, {}, evidence_id="experimental_fit")["items"][0]
    assert detail["recorded_follow_ups"] == []
    assert detail["suggested_steps"] == []
    assert detail["record"]["provenance"]["inspection"] == "not_inspected"
    assert detail["issues"] == ["source_not_fully_inspected"]
    assert detail["resolved_follow_ups"][0]["instruction"]["id"] == "inspect-original-fit"
    assert any(c.endswith("--evidence experimental_fit_full_text") for c in detail["next_commands"])
    assert main(["explain", str(path), "--evidence", "experimental_fit", "--plain"]) == 0
    output = capsys.readouterr().out
    assert "Completed follow-up: inspect-original-fit" in output
    assert "Obtain Hirschmann" not in output and "Obtain and inspect" not in output
    for evidence, pending in (("experimental_fit_full_text", "reconstruct-original-fit"),
                              ("calibration_adoption_full_text", "inspect-inherited-calibration")):
        detail = explain_contract(path, {}, evidence_id=evidence)["items"][0]
        assert detail["recorded_follow_ups"][0]["id"] == pending
    data = contract.model_dump()
    data["follow_up_resolutions"] = []
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    detail = explain_contract(path, {}, evidence_id="experimental_fit")["items"][0]
    assert detail["recorded_follow_ups"][0]["id"] == "inspect-original-fit"
    assert SOURCE_ACTIONS["source_not_fully_inspected"] in detail["suggested_steps"]


def test_one_completed_task_does_not_hide_other_pending_inspection_work(reviewed):
    path, contract = reviewed
    data = contract.model_dump()
    task = deepcopy(data["follow_ups"][0])
    task.update(id="another-task", action="Inspect another explicitly unresolved aspect.")
    data["follow_ups"].append(task)
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    item = explain_contract(path, {}, evidence_id="experimental_fit")["items"][0]
    assert [f["id"] for f in item["recorded_follow_ups"]] == ["another-task"]
    assert item["resolved_follow_ups"][0]["follow_up"] == "inspect-original-fit"
    assert SOURCE_ACTIONS["source_not_fully_inspected"] in item["suggested_steps"]


@pytest.mark.parametrize("mutate", [
    lambda d: d[0].update(follow_up="missing"),
    lambda d: d[0].update(evidence=["missing"]),
    lambda d: d[0].update(evidence=[]),
    lambda d: d[0].update(evidence=["experimental_fit_full_text"] * 2),
    lambda d: d[0].update(note=" "),
    lambda d: d[0].update(status="supported"),
    lambda d: d.append(deepcopy(d[0])),
])
def test_invalid_completion_records_are_rejected(reviewed, mutate):
    _, contract = reviewed
    data = contract.model_dump()
    mutate(data["follow_up_resolutions"])
    with pytest.raises(ValueError):
        ContractV02.model_validate(data)
