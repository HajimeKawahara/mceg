"""Known gaps keep their scientific status when work or a disposition is recorded."""

from copy import deepcopy
import json

import pytest

from mceg import ContractV04
from mceg.__main__ import main
from mceg.handling import assessment_handling
from mceg.schema_v04 import decision_basis_digest


@pytest.fixture
def data():
    implementation = {"repository": "https://example.org/model", "revision": "fixture-v1",
                      "entry_points": ["src/model.py:calculate"]}
    return {
        "schema_version": "0.4",
        "model": {"id": "example.field", "name": "Prescribed field",
                  "description": "Synthetic records; no physical solver is executed.",
                  "implementation": implementation},
        "assumptions": [], "limitations": [],
        "domains": [{"kind": "scientific_applicability", "status": "unknown",
                     "description": "The approximation is unverified.", "conditions": [],
                     "evidence": ["source_review"]}],
        "claims": [{"id": "field", "revision": "1", "kind": "theoretical",
                    "statement": "The field approximation is valid under the stated conditions.",
                    "scope": "Fixture only."}],
        "subjects": [{"id": "model", "implementation": deepcopy(implementation)},
                     {"id": "other", "implementation": deepcopy(implementation)}],
        "contexts": [{"id": "review", "scope": "The fixture use case."},
                     {"id": "other", "scope": "A different use case."}],
        "evidence": [{"id": "source_review", "kind": "theory", "summary": "A known approximation.",
                      "sources": ["doc/model.tex"], "scope": "Fixture only.",
                      "subject": "model", "context": "review",
                      "provenance": {"role": "primary", "inspection": "inspected",
                                     "location": "Fixture definition", "note": "No new measurement."}}],
        "assessments": [{"id": "field_review", "kind": "evidence_support", "claim": "field",
                         "claim_revision": "1", "subject": "model", "context": "review",
                         "status": "unknown", "origin": "reviewed",
                         "method": {"id": "review", "revision": "1", "description": "Inspect the approximation."},
                         "evidence": ["source_review"], "reasons": ["Its error is not established."]}],
    }


def add_task(data, *, target_kind="assessment", target="field_review", completed=False):
    task = {"id": "compare_fields", "target_kind": target_kind, "target": target,
            "action": "Compare fixed-field and transported-field predictions.",
            "completion": "Record the comparison and a scoped Assessment, including a remaining gap."}
    if target_kind == "claim":
        task["revision"] = "1"
    data["follow_ups"] = [task]
    if completed:
        data["follow_up_resolutions"] = [{"follow_up": "compare_fields", "evidence": ["source_review"],
                                           "note": "The comparison task ended; the error is still unknown."}]


def add_decision(data):
    contract = ContractV04.model_validate(data)
    data["decisions"] = [{
        "id": "field_use", "revision": "1", "question": "How may this approximation be used?",
        "scope": "Only the fixture use case.", "subject": "model", "context": "review",
        "options": [{"id": "exploration", "description": "Use for exploratory calculations only."}],
        "selected": "exploration", "reasons": ["The effect is not yet measured."],
        "limitations": ["No physical inference is justified by this choice."],
        "reconsider_when": ["A transported-field comparison is available."],
        "basis": [{"kind": "assessment", "id": "field_review",
                   "sha256": decision_basis_digest(contract, "assessment", "field_review")}],
    }]


def check(tmp_path, capsys, data, *, required=False, assessment="field_review"):
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    code = main(["check", str(path), "--assessment", assessment, "--json",
                 *(["--require-handling"] if required else [])])
    entry = json.loads(capsys.readouterr().out)["contracts"][0]
    assert path.read_bytes() == before
    return code, entry


def coverage(entry):
    return next(c for c in entry["checks"] if c["name"] == "handling_coverage")


def test_unhandled_unknown_is_advisory_until_explicitly_required(data, tmp_path, capsys):
    code, entry = check(tmp_path, capsys, data)
    assert code == 0 and coverage(entry)["status"] == "UNKNOWN"
    row = entry["handling"][0]
    assert row == {"assessment": "field_review", "claim": "field", "claim_revision": "1",
                   "subject": "model", "context": "review", "recorded_support": "unknown",
                   "open_follow_ups": [], "decisions": [], "handling_recorded": False}
    code, entry = check(tmp_path, capsys, data, required=True)
    assert code == 1 and coverage(entry)["status"] == "FAIL"
    assert entry["assessments"][0]["status"] == "unknown"


def test_open_assessment_task_records_handling_without_support(data, tmp_path, capsys):
    add_task(data)
    code, entry = check(tmp_path, capsys, data, required=True)
    assert code == 0 and coverage(entry)["status"] == "PASS"
    assert entry["handling"][0]["open_follow_ups"] == ["compare_fields"]
    assert entry["handling"][0]["recorded_support"] == "unknown"
    assert next(c for c in entry["checks"] if c["name"] == "recorded_support")["status"] == "UNKNOWN"


def test_completed_task_does_not_resolve_unknown_support(data, tmp_path, capsys):
    add_task(data, completed=True)
    code, entry = check(tmp_path, capsys, data, required=True)
    assert code == 1 and entry["handling"][0]["open_follow_ups"] == []
    assert entry["assessments"][0]["status"] == "unknown"


def test_shared_claim_does_not_imply_scoped_handling(data, tmp_path, capsys):
    add_task(data, target_kind="claim", target="field")
    code, entry = check(tmp_path, capsys, data, required=True)
    assert code == 1 and not entry["handling"][0]["handling_recorded"]


def test_scoped_decision_is_a_disposition_not_scientific_support(data, tmp_path, capsys):
    add_decision(data)
    code, entry = check(tmp_path, capsys, data, required=True)
    assert code == 0 and coverage(entry)["status"] == "PASS"
    assert entry["handling"][0]["decisions"] == [{"id": "field_use", "revision": "1"}]
    assert entry["handling"][0]["recorded_support"] == "unknown"


@pytest.mark.parametrize("change", [
    lambda d: d["decisions"][0].update(subject=None),
    lambda d: d["decisions"][0].update(context=None),
    lambda d: d["decisions"][0].update(subject="other"),
    lambda d: d["decisions"][0].update(context="other"),
    lambda d: d["decisions"][0].update(limitations=[]),
    lambda d: d["decisions"][0].update(reconsider_when=[]),
    lambda d: d["decisions"][0].update(basis=[]),
    lambda d: d["decisions"][0]["basis"][0].update(sha256="0" * 64),
    lambda d: d["evidence"][0].update(summary="Changed basis after the decision."),
])
def test_unscoped_or_stale_decision_does_not_cover_gap(data, tmp_path, capsys, change):
    add_decision(data)
    change(data)
    code, entry = check(tmp_path, capsys, data, required=True)
    assert code == 1 and not entry["handling"][0]["handling_recorded"]
    assert entry["handling"][0]["decisions"] == []


def test_superseded_choice_is_not_an_active_disposition(data):
    add_decision(data)
    replacement = deepcopy(data["decisions"][0])
    replacement.update(revision="replacement", context="other",
                       supersedes={"id": "field_use", "revision": "1"})
    data["decisions"].insert(0, replacement)
    contract = ContractV04.model_validate(data)
    assert not assessment_handling(contract, contract.assessments)[0]["handling_recorded"]
    assert len(contract.decisions) == 2


def test_later_supported_assessment_does_not_handle_earlier_unknown(data, tmp_path, capsys):
    newer = deepcopy(data["assessments"][0])
    newer.update(id="later_review", status="supported", subject="other", context="other")
    data["assessments"].append(newer)
    add_task(data, target="later_review")
    code, entry = check(tmp_path, capsys, data, required=True)
    assert code == 1 and not entry["handling"][0]["handling_recorded"]
    code, entry = check(tmp_path, capsys, data, required=True, assessment="later_review")
    assert code == 0 and entry["handling"] == [] and coverage(entry)["status"] == "PASS"


def test_handled_contradiction_still_fails_recorded_support(data, tmp_path, capsys):
    data["assessments"][0].update(status="contradicted", reasons=["The fixture theory contradicts this claim."])
    add_task(data)
    code, entry = check(tmp_path, capsys, data, required=True)
    assert code == 1 and coverage(entry)["status"] == "PASS"
    assert next(c for c in entry["checks"] if c["name"] == "recorded_support")["status"] == "FAIL"
    assert entry["handling"][0]["recorded_support"] == "contradicted"


def test_investigation_reports_missing_handling_and_preserves_scope(data, tmp_path, capsys):
    sibling = deepcopy(data["assessments"][0])
    sibling.update(id="sibling", context="other")
    data["assessments"].append(sibling)
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(data))
    assert main(["explain", str(path), "--assessment", "field_review", "--investigation", "--json"]) == 0
    entry = json.loads(capsys.readouterr().out)["contracts"][0]
    assert [r["assessment"] for r in entry["investigation"]["handling"]] == ["field_review"]
    assert entry["investigation"]["handling"] == entry["handling"]
    assert entry["audited_evidence"] == ["source_review"]
    assert main(["explain", str(path), "--assessment", "field_review", "--investigation", "--plain"]) == 0
    output = capsys.readouterr().out
    assert "scientific support remains unknown; response missing" in output
    assert "subject=model; context=review" in output


def test_strict_check_requires_explicit_assessment(data, tmp_path):
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(data))
    with pytest.raises(SystemExit) as error:
        main(["check", str(path), "--require-handling"])
    assert error.value.code == 2


def test_default_plain_check_identifies_missing_assessment(data, tmp_path, capsys):
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(data))
    assert main(["check", str(path), "--assessment", "field_review", "--plain"]) == 0
    output = capsys.readouterr().out
    assert "No recorded handling for: field_review" in output
