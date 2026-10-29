"""A selected investigation retains evidence, completed decisions and remaining work."""

import hashlib
import json
from pathlib import Path
import shlex

import pytest

from mceg import ContractV02, load_contract
from mceg.__main__ import main


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def investigation(tmp_path):
    implementation = {"repository": "https://example.org/synthetic-provider",
                      "revision": "fixture-revision", "entry_points": ["fixture:activity"]}

    def source(key, kind="literature", links=()):
        return {"id": key, "kind": kind, "summary": "Synthetic " + key,
                "sources": ["https://example.org/" + key],
                "scope": "Synthetic coefficient comparison only.",
                "provenance": {
                    "role": "implementation" if kind == "implementation" else "primary",
                    "location": key + ": Eq. 1", "inspection": "inspected",
                    "note": "Synthetic inspection, not a real publication.",
                    "derived_from": [{"evidence": target, "comparison": comparison,
                                      "note": "Synthetic " + comparison}
                                     for target, comparison in links]}}

    original = source("original")
    original.update(subject="source-snapshot", context="source-review")
    printed = source("printed")
    code = source("code", "implementation", [("original", "consistent"), ("printed", "discrepancy")])
    comparison = source("comparison", "implementation", [("code", "consistent"), ("printed", "discrepancy")])
    decision = source("decision", "implementation", [("original", "consistent"), ("code", "consistent")])
    decision.update(sources=["results/decision.json"], subject="provisional", context="review",
                    artifacts=[{"source": "results/decision.json", "sha256": "a" * 64}])
    verification = source("verification", "numerical_test", [("decision", "consistent")])
    verification.update(result="passed", subject="provisional", context="numerical")
    reply = source("reply")
    reply["provenance"].update(inspection="not_inspected", note="No author reply received.")
    claims = [
        {"id": "choice", "revision": "1", "kind": "theoretical",
         "statement": "The printed coefficient is the intended choice.", "scope": "Historical choice."},
        {"id": "choice", "revision": "2", "kind": "theoretical",
         "statement": "The provisional coefficient is the intended choice.", "scope": "Provisional choice."},
        {"id": "author", "revision": "1", "kind": "theoretical",
         "statement": "The author confirms the intended coefficient.", "scope": "Requires an author statement."},
        {"id": "numeric", "revision": "1", "kind": "numerical_verification",
         "statement": "The implementation reproduces the selected equations.", "scope": "Recorded test points."},
        {"id": "physical", "revision": "1", "kind": "physical_validation",
         "statement": "The model meets an empirical accuracy criterion.", "scope": "Requires measurements."}]

    def assessment(key, claim, revision, evidence, status="unknown", context="review"):
        return {"id": key, "kind": "evidence_support", "claim": claim, "claim_revision": revision,
                "subject": "provisional", "context": context, "status": status, "origin": "reviewed",
                "evidence": evidence, "reasons": ["Synthetic scoped review."],
                "method": {"id": "fixture-review", "revision": "1", "description": "Synthetic review."}}

    data = {
        "schema_version": "0.2",
        "model": {"id": "fixture.oxygen", "name": "Synthetic coefficient review",
                  "description": "No real scientific result.", "implementation": implementation},
        "assumptions": [], "limitations": [],
        "domains": [{"kind": "scientific_applicability", "status": "unknown", "conditions": [],
                     "description": "Not validated.", "evidence": ["original"]}],
        "claims": claims,
        "evidence": [original, printed, code, comparison, decision, verification, reply, source("unrelated")],
        "subjects": [{"id": key, "implementation": implementation}
                     for key in ("provisional", "source-snapshot")],
        "contexts": [{"id": key, "scope": "Synthetic " + key}
                     for key in ("review", "numerical", "source-review")],
        "assessments": [assessment("old-choice", "choice", "1", ["comparison"]),
                        assessment("new-choice", "choice", "2", ["decision"]),
                        assessment("author-review", "author", "1", ["decision", "reply"]),
                        assessment("numeric-review", "numeric", "1", ["decision", "verification"],
                                   "supported", "numerical"),
                        assessment("unrelated-review", "physical", "1", ["original", "unrelated"])],
        "follow_ups": [
            {"id": "choose-coefficient", "target_kind": "evidence", "target": "comparison",
             "action": "Choose the coefficient after source comparison.",
             "completion": "Record the implementation choice and its limitations."},
            {"id": "record-author-reply", "target_kind": "claim", "target": "author", "revision": "1",
             "action": "If a reply becomes available, reassess author intent.",
             "requires": ["An attributable reply."], "completion": "Record the reply and scoped reassessment."},
            {"id": "validate-physical", "target_kind": "claim", "target": "physical", "revision": "1",
             "action": "Obtain measurements.", "completion": "Record independent empirical validation."}],
        "follow_up_resolutions": [{"follow_up": "choose-coefficient", "evidence": ["decision"],
                                   "note": "Use the provisional coefficient; author intent remains unknown."}]}
    path = tmp_path / "coefficient review.json"
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    return path, data


def run_investigation(capsys, path, *selection):
    assert main(["explain", str(path), *selection, "--investigation", "--json"]) == 0
    return json.loads(capsys.readouterr().out)["contracts"][0]["investigation"]


def test_completed_choice_collects_agreeing_sources_without_promoting_author_intent(investigation, capsys):
    path, data = investigation
    before = path.read_bytes()
    result = run_investigation(capsys, path, "--evidence", "comparison")
    evidence = {item["id"]: item for item in result["evidence"]}
    assert set(evidence) == {"comparison", "original", "printed", "code", "decision", "verification", "reply"}
    assert evidence["original"]["record"]["provenance"]["location"] == "original: Eq. 1"
    assert evidence["decision"]["record"]["artifacts"] == data["evidence"][4]["artifacts"]
    assert not (path.parent / "results/decision.json").exists()  # A locator need not be opened.
    assert evidence["code"]["comparisons"] == data["evidence"][2]["provenance"]["derived_from"]
    assert evidence["reply"]["record"]["provenance"]["inspection"] == "not_inspected"
    assert {item["follow_up"] for item in result["completed_follow_ups"]} == {"choose-coefficient"}
    assert {item["id"] for item in result["pending_follow_ups"]} == {"record-author-reply"}
    assessments = {item["id"]: item["record"] for item in result["assessments"]}
    assert assessments["author-review"]["status"] == "unknown"
    assert assessments["numeric-review"]["status"] == "supported"
    assert "unrelated-review" not in assessments
    assert result["excluded_evidence"] == ["unrelated"]
    assert result["scope"]
    assert path.read_bytes() == before


def test_evidence_identity_retains_subjects_contexts_and_declared_comparisons(investigation, capsys):
    path, _ = investigation
    result = run_investigation(capsys, path, "--evidence", "comparison")
    assert {subject["id"] for subject in result["subjects"]} == {"provisional", "source-snapshot"}
    assert {context["id"] for context in result["contexts"]} == {"review", "numerical", "source-review"}
    assert [entry["id"] for entry in result["selection"]] == ["comparison"]
    assert all("target_kind" in step and "target" in step for step in result["suggested_steps"])
    assert any(step.get("comparison_targets") for step in result["suggested_steps"])


def test_assessment_selector_does_not_pull_other_revisions_or_sibling_judgments(investigation, capsys):
    path, _ = investigation
    result = run_investigation(capsys, path, "--assessment", "new-choice")
    assert [item["id"] for item in result["assessments"]] == ["new-choice"]
    assert {item["id"] for item in result["evidence"]} == {"decision", "original", "code", "printed"}
    assert not result["pending_follow_ups"]
    assert not result["completed_follow_ups"]
    target = result["assessments"][0]["claim"]
    assert (target["id"], target["revision"]) == ("choice", "2")


def test_claim_selection_keeps_all_recorded_revisions_without_picking_a_latest(investigation, capsys):
    path, _ = investigation
    result = run_investigation(capsys, path, "--claim", "choice")
    assert [(item["id"], item["revision"]) for item in result["selection"]] == [("choice", "1"), ("choice", "2")]
    assessments = {item["id"]: item["record"] for item in result["assessments"]}
    assert assessments["old-choice"]["claim_revision"] == "1"
    assert assessments["new-choice"]["claim_revision"] == "2"
    assert assessments["old-choice"]["status"] == assessments["new-choice"]["status"] == "unknown"


def test_completion_cycles_are_finite_and_shared_records_appear_once(investigation, capsys):
    path, data = investigation
    data["follow_ups"].append({"id": "link-back", "target_kind": "evidence", "target": "decision",
                              "action": "Retain the original comparison.", "completion": "Record its locator."})
    data["follow_up_resolutions"].append({"follow_up": "link-back", "evidence": ["comparison"],
                                         "note": "The original comparison is retained."})
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    result = run_investigation(capsys, path, "--evidence", "comparison")
    ids = [item["id"] for item in result["evidence"]]
    assert len(ids) == len(set(ids)) == 7
    assert {item["follow_up"] for item in result["completed_follow_ups"]} == {"choose-coefficient", "link-back"}
    assert result == run_investigation(capsys, path, "--evidence", "comparison")


def test_json_is_language_independent_and_opt_in(investigation, capsys):
    path, _ = investigation
    args = ["explain", str(path), "--evidence", "comparison", "--json"]
    assert main(args) == 0
    ordinary = json.loads(capsys.readouterr().out)
    assert "investigation" not in ordinary["contracts"][0]
    assert main([*args, "--investigation"]) == 0
    english = capsys.readouterr().out
    assert main([*args, "--investigation", "--lang", "ja"]) == 0
    assert capsys.readouterr().out == english


def test_selected_assessment_still_reports_changed_files_with_investigation(investigation, capsys):
    path, data = investigation
    model = path.parent / "model.py"
    model.write_text("coefficient = -1873\n")
    data["subjects"][0]["selected_files"] = {"model.py": hashlib.sha256(model.read_bytes()).hexdigest()}
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    args = ["explain", str(path), "--assessment", "numeric-review", "--investigation",
            "--root", str(path.parent), "--json"]
    for changed, expected in ((False, "PASS"), (True, "FAIL")):
        if changed:
            model.write_text("coefficient = -16500\n")
        assert main(args) == 0
        report = json.loads(capsys.readouterr().out)["contracts"][0]
        checks = {item["name"]: item["status"] for item in report["items"] if "name" in item}
        assert checks["selected_files"] == expected
        stored = report["investigation"]["assessments"][0]["record"]
        assert stored["status"] == "supported"  # Historical judgment remains explicitly recorded.


def test_text_displays_completed_work_before_pending_tasks_and_source_navigation(investigation, capsys):
    path, _ = investigation
    assert main(["explain", str(path), "--evidence", "comparison", "--investigation", "--plain"]) == 0
    output = capsys.readouterr().out
    assert output.index("Completed follow-up") < output.index("Recorded next step")
    assert output.index("Completed follow-up") < output.index("Synthetic comparison")
    assert "choose-coefficient" in output and "record-author-reply" in output
    assert "Use the provisional coefficient; author intent remains unknown." in " ".join(output.split())
    assert "https://example.org/original" in output and "results/decision.json" in output
    assert "original: Eq. 1" in " ".join(output.split())
    commands = [line.split(": ", 1)[1] for line in output.splitlines() if ": mceg explain " in line]
    assert commands
    for command in commands:
        assert main(shlex.split(command)[1:]) == 0
        capsys.readouterr()


@pytest.mark.parametrize("options", [[], ["--package", "not-installed"], ["--catalog", "missing.json"]])
def test_investigation_requires_a_contract_selector(options, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["explain", *options, "--investigation", "--json"])
    assert exc.value.code == 2
    assert "--investigation requires --evidence, --claim or --assessment" in capsys.readouterr().err


@pytest.mark.parametrize("catalog", [["--package", "not-installed"], ["--catalog", "missing.json"]])
def test_investigation_rejects_package_catalog_combinations(catalog, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["explain", *catalog, "--evidence", "comparison", "--investigation"])
    assert exc.value.code == 2
    assert "Package/catalog lookup cannot be combined" in capsys.readouterr().err


def test_v01_uses_declared_claim_evidence_without_inventing_completion(capsys):
    path = ROOT / "contracts/h2_solubility.yaml"
    before = path.read_bytes()
    result = run_investigation(capsys, path, "--claim", "physical_accuracy")
    assert result["selection"][0]["record"]["status"] == "unknown"
    declared = next(claim for claim in load_contract(path).claims if claim.id == "physical_accuracy").evidence
    assert set(declared) <= {item["id"] for item in result["evidence"]}
    assert result["completed_follow_ups"] == result["pending_follow_ups"] == []
    assert result["assessments"] == result["subjects"] == result["contexts"] == []
    assert path.read_bytes() == before
