"""Exercise reference failure and historical evidence without provider imports."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from mceg import load_contract


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/provider_workflow"
SPEC = importlib.util.spec_from_file_location("provider_workflow", EXAMPLE / "run.py")
WORKFLOW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WORKFLOW)


@pytest.fixture
def provider(tmp_path):
    """A filesystem fixture only: source bodies are placeholders, not executed."""
    root = tmp_path / "provider"
    record = load_contract(ROOT / "contracts/h2_solubility.yaml").model_dump(exclude_none=True)
    implementation = record["model"]["implementation"]
    prefix = implementation["repository"] + "/blob/" + implementation["revision"] + "/"
    for evidence in record["evidence"]:
        for index, locator in enumerate(evidence["sources"]):
            if locator.startswith(prefix):
                locator = locator[len(prefix):]
            elif locator.startswith("docs/"):
                locator = "mceg/evidence/" + locator
            else:
                continue
            path = WORKFLOW.local_path(root, locator)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Placeholder for a reference-resolution test.\n")
            evidence["sources"][index] = locator
    (root / WORKFLOW.SOURCE).write_text(WORKFLOW.OLD_EXPRESSION + "\n")
    WORKFLOW.write_yaml(root / "mceg/contracts/h2_solubility.yaml", record)
    return root


def test_sources_resolve_from_explicit_repository_root_and_missing_files_are_visible(provider, tmp_path, monkeypatch):
    contract = provider / "mceg/contracts/h2_solubility.yaml"
    monkeypatch.chdir(tmp_path)
    report = WORKFLOW.check_sources(contract, provider)
    assert report["local_files_complete"]
    assert report["external_not_checked"] and report["opaque_not_checked"]
    assert report["fragments_checked"] is False
    (provider / WORKFLOW.SOURCE).unlink()
    broken = WORKFLOW.check_sources(contract, provider)
    assert broken["schema_valid"]  # Structural success is not reference success.
    assert not broken["local_files_complete"]
    assert any(row["locator"].startswith(WORKFLOW.SOURCE) for row in broken["missing"])


def test_local_references_cannot_escape_the_selected_repository(tmp_path):
    with pytest.raises(ValueError):
        WORKFLOW.local_path(tmp_path, "docs/../../outside.txt")


def test_revision_review_preserves_parent_and_does_not_inherit_its_pass(provider, tmp_path):
    report = WORKFLOW.revision_trial(provider, tmp_path)
    assert report["changed_evidence_files"] == [WORKFLOW.SOURCE]
    assert report["source_sha256"]["before"] != report["source_sha256"]["after"]
    assert report["parent_preserved"] and not report["candidate_executed"]
    assert report["negative_control"]["revision_only_edit_schema_valid"]
    assert report["negative_control"]["stale_numerical_claim_still_supported"]
    assert report["evidence_results"] == {"current_tests": "not_run", "historical_tests": "passed"}
    after = load_contract(tmp_path / "candidate/mceg/contracts/h2_solubility.yaml")
    claims = {claim.id: claim for claim in after.claims}
    assert claims["formula_evaluation"].status == "unknown"
    assert claims["formula_evaluation"].evidence == ["current_tests"]
    assert claims["fixed_pressure_linearity"].status == "supported"
    assert claims["physical_accuracy"].status == "unknown"
    implementation = next(e for e in after.evidence if e.id == "implementation")
    assert implementation.provenance.derived_from[0].comparison == "discrepancy"
    assert not report["candidate_trace"]["recorded_audit_complete"]


def test_saved_trial_is_bound_to_the_frozen_inputs_and_scripts():
    report = json.loads((EXAMPLE / "result.json").read_text())
    assert report["runner_sha256"] == WORKFLOW.sha256(EXAMPLE / "run.py")
    assert report["candidate_template_sha256"] == WORKFLOW.sha256(EXAMPLE / "candidate.yaml")
    assert report["naive_copy"]["schema_valid"]
    assert not report["naive_copy"]["local_files_complete"]
    assert len(report["relocated_contracts"]) == 5
    for path, record in report["relocated_contracts"].items():
        source = ROOT / "contracts" / Path(path).name
        assert record["original_contract_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
        assert record["local_files_complete"] and record["local_file_sha256"]
    assert report["revision_trial"]["parent_preserved"]
