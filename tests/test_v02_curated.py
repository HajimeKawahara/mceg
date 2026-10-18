"""The reviewed adapter emits common records without creating new execution evidence."""

from copy import deepcopy
import hashlib
import json

import pytest

from mceg import load_contract, restore_v01
from mceg.curated import assess_curated
from mceg import _curated
from mceg.__main__ import main
from test_curated_assessment import example


@pytest.fixture
def reviewed_example(example):
    provider, context, review_path = example
    review = json.loads(review_path.read_text())
    path = provider / review["contract"]["path"]
    data = json.loads(path.read_text())
    data["evidence"].append({"id": "implementation", "kind": "implementation",
                             "summary": "Synthetic implementation record.", "sources": ["src/exogibbs/presets/curated.py"],
                             "scope": "Fixture bookkeeping, not scientific evidence."})
    path.write_text(json.dumps(data))
    review["contract"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    review_path.write_text(json.dumps(review))
    return provider, context, review_path


@pytest.mark.parametrize("change,expected", [({}, "supported"), ({"temperature_K": 1750}, "unknown"),
                                            ({"jax": "different"}, "unknown"), ({"composition": None}, "unknown")])
def test_reviewed_curated_policy_uses_shared_records(reviewed_example, change, expected):
    provider, context, review = reviewed_example
    inputs = {**context, **change}
    before = deepcopy(inputs)
    result = assess_curated(provider, inputs, review)
    assert inputs == before
    assert result.schema_version == "0.2"
    assert result.assessments[-1].status == expected
    assert result.assessments[-1].origin == "reviewed"
    assert all(a.origin == "imported_v0.1_declaration" for a in result.assessments[:-3])
    assert next(e for e in result.evidence if e.id == "verification").result == "passed"
    assert len(result.conditions[1].samples) == 70
    original = provider / json.loads(review.read_text())["contract"]["path"]
    assert restore_v01(result) == load_contract(original)
    if change.get("temperature_K") == 1750:
        assert [a.classification for a in result.assessments[-3:-1]] == ["within_reported_range", "not_sampled"]


def test_missing_implementation_has_a_distinct_subject_without_rewriting_old_pass(reviewed_example):
    provider, context, review = reviewed_example
    old = assess_curated(provider, context, review)
    source = provider / "src/exogibbs/presets/curated.py"
    source.unlink()
    changed = assess_curated(provider, context, review)
    assert old.assessments[-1].subject != changed.assessments[-1].subject
    assert changed.assessments[-1].status == "unknown"
    assert changed.subjects[-1].selected_files["src/exogibbs/presets/curated.py"] is None
    assert changed.assessments[0] == old.assessments[0]
    assert changed.evidence == old.evidence


def test_method_identity_includes_the_review_and_changed_outputs_are_recorded(reviewed_example):
    provider, context, review_path = reviewed_example
    old = assess_curated(provider, context, review_path)
    review = json.loads(review_path.read_text())
    review["rationale"] += " A separately identified synthetic review."
    review_path.write_text(json.dumps(review))
    changed_review = assess_curated(provider, context, review_path)
    assert changed_review.assessments[-1].method.revision != old.assessments[-1].method.revision
    assert changed_review.assessments[-1].status == "supported"
    artifact = (provider / review["receipt"]["path"]).parent / "fixture.txt"
    artifact.write_text("Changed synthetic output; no execution.\n")
    changed_output = assess_curated(provider, context, review_path)
    assert changed_output.assessments[-1].status == "unknown"
    assert changed_output.evidence == old.evidence
    assert any(hashlib.sha256(artifact.read_bytes()).hexdigest() in r for r in changed_output.assessments[-1].reasons)


def test_cli_export_and_deep_inspection_preserve_unsampled_reason(reviewed_example, tmp_path, monkeypatch, capsys):
    provider, context, review = reviewed_example
    original = _curated.run
    monkeypatch.setattr(_curated, "run", lambda root, inputs: original(root, inputs, review))
    path = tmp_path / "context.json"
    path.write_text(json.dumps({**context, "temperature_K": 1750}))
    output = tmp_path / "export.yaml"
    assert main(["assess", "--curated", str(provider), "--context", str(path), "--output", str(output)]) == 0
    contract = load_contract(output)
    capsys.readouterr()
    assert main(["explain", str(output), "--assessment", contract.assessments[-1].id, "--json"]) == 0
    item = json.loads(capsys.readouterr().out)["contracts"][0]["items"][0]
    assert item["record"]["status"] == "unknown"
    assert item["context"]["quantities"]["temperature"]["value"] == 1750
    assert any("Run the provider verification" in s["action"] for s in item["suggested_steps"])
    assert main(["explain", str(output), "--assessment", contract.assessments[-2].id]) == 0
    text = capsys.readouterr().out
    assert "sample_count: 70" in text and "sample:69" not in text
