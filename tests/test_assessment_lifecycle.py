"""Preserve declarations and distinguish new execution, reuse and source review."""

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from mceg import load_contract
from test_curated_assessment import example, write_json


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/curated_gas"
sys.path.insert(0, str(EXAMPLE))
import reassess as LIFECYCLE
sys.path.pop(0)


@pytest.fixture
def execution(example, tmp_path, monkeypatch):
    """Synthetic bookkeeping around copied CSVs; this does not run either solver."""
    provider, _, review_path = example
    here, run = tmp_path / "policy", tmp_path / "run"
    here.mkdir()
    run.mkdir()
    saved = EXAMPLE / "runs/jax-0.6.2"
    record = json.loads((saved / "execution.json").read_text())
    for name in record["selected_input_sha256"]:
        path = provider / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Synthetic input, not executable scientific code.\n")
    write_json(provider / LIFECYCLE.ADOPTION, {"decision": "Synthetic adoption record"})
    write_json(provider / LIFECYCLE.DATA, {
        "source_sha256": {LIFECYCLE.ADOPTION: LIFECYCLE.sha256(provider / LIFECYCLE.ADOPTION)}})
    record["selected_input_sha256"] = {p: LIFECYCLE.sha256(provider / p)
                                       for p in record["selected_input_sha256"]}
    receipt = json.loads((saved / "receipt.json").read_text())
    receipt["selected_file_sha256"] = {p: record["selected_input_sha256"][p]
                                       for p in receipt["selected_file_sha256"]}
    for name in receipt["output_sha256"]:
        (run / name).write_bytes((saved / name).read_bytes() if name.endswith(".csv") else b"Synthetic artifact.\n")
    (run / "execution.log").write_text("Synthetic execution fixture; no numerical run.\n")
    record["log_sha256"] = LIFECYCLE.sha256(run / "execution.log")
    write_json(run / "receipt.json", receipt)
    write_json(run / "execution.json", record)
    update_artifact_pins(run)
    review = json.loads(review_path.read_text())
    archive = provider / review["receipt"]["path"]
    original = json.loads(archive.read_text())
    original["selected_file_sha256"] = receipt["selected_file_sha256"]
    write_json(archive, original)
    review["receipt"]["sha256"] = LIFECYCLE.sha256(archive)
    write_json(here / "review.json", review)
    claim = json.loads((EXAMPLE / "claim_revision.json").read_text())
    claim["revises"]["contract_sha256"] = review["contract"]["sha256"]
    write_json(here / "claim_revision.json", claim)
    policy = json.loads((EXAMPLE / "rerun_review.json").read_text())
    policy.update(claim_revision_sha256=LIFECYCLE.sha256(here / "claim_revision.json"),
                  reviewed_script_sha256=record["selected_input_sha256"][LIFECYCLE.SCRIPT],
                  extra_input_sha256={p: record["selected_input_sha256"][p] for p in LIFECYCLE.EXTRA_INPUTS})
    write_json(here / "rerun_review.json", policy)
    monkeypatch.setattr(LIFECYCLE, "HERE", here)
    return provider, run


def update_artifact_pins(run):
    receipt = json.loads((run / "receipt.json").read_text())
    receipt["output_sha256"] = {p: LIFECYCLE.sha256(run / p) for p in receipt["output_sha256"]}
    write_json(run / "receipt.json", receipt)
    record = json.loads((run / "execution.json").read_text())
    record["receipt_sha256"] = LIFECYCLE.sha256(run / "receipt.json")
    write_json(run / "execution.json", record)


@pytest.mark.parametrize("name", ["h2", "curated"])
def test_migration_round_trip_preserves_declarations_and_evidence(example, name, tmp_path):
    provider, _, review_path = example
    review = json.loads(review_path.read_text())
    path = ROOT / "contracts/h2_solubility.yaml" if name == "h2" else provider / review["contract"]["path"]
    before = path.read_bytes()
    original = load_contract(path).model_dump()
    draft = LIFECYCLE.migrate(path)
    restored = {k: deepcopy(draft[k]) for k in original if k != "schema_version"}
    restored["schema_version"] = "0.1"
    for claim, assessment in zip(restored["claims"], draft["assessments"]):
        assert "status" not in claim and "evidence" not in claim
        assert assessment["target"]["claim_revision"] == claim.pop("revision")
        assert assessment["context"]["structured_conditions"] is None
        claim.update(status=assessment["status"], evidence=assessment["evidence"])
    assert restored == original
    assert path.read_bytes() == before
    draft_path = tmp_path / "draft.json"
    write_json(draft_path, draft)
    with pytest.raises(ValueError):
        load_contract(draft_path)


def test_old_environment_does_not_support_new_environment_but_new_execution_does(execution):
    provider, run = execution
    fresh = LIFECYCLE.assess_execution(provider, run)
    different = deepcopy(fresh["assessment"]["context"]["environment"])
    different["packages"]["jax"] = "another-version"
    reused = LIFECYCLE.assess_execution(provider, run, different)
    assert fresh["assessment"]["status"] == "supported"
    assert reused["assessment"]["status"] == "unknown"
    assert "environment_not_covered_by_execution" in reused["assessment"]["reasons"]
    assert fresh["assessment"]["id"] != reused["assessment"]["id"]
    assert fresh["evidence"] == reused["evidence"]
    assert fresh["imported_assessments"] == reused["imported_assessments"]
    assert reused["evidence"]["result"] == reused["historical_evidence"]["result"] == "passed"


@pytest.mark.parametrize("change", ["failed_gate", "missing_sample", "nan", "duplicate"])
def test_failure_missing_coverage_and_malformed_evidence_are_distinct(execution, change):
    provider, run = execution
    path = run / "fastchem_parity.csv"
    lines = path.read_text().splitlines()
    if change in ("failed_gate", "nan"):
        columns = lines[1].split(",")
        columns[3] = "0.01" if change == "failed_gate" else "nan"
        lines[1] = ",".join(columns)
    elif change == "missing_sample":
        lines.pop()
    else:
        lines.append(lines[-1])
    path.write_text("\n".join(lines) + "\n")
    update_artifact_pins(run)
    if change in ("nan", "duplicate"):
        with pytest.raises(ValueError):
            LIFECYCLE.assess_execution(provider, run)
        return
    report = LIFECYCLE.assess_execution(provider, run)
    assert report["assessment"]["status"] == "unknown"
    assert report["evidence"]["result"] == ("failed" if change == "failed_gate" else "unknown")
    assert report["historical_evidence"]["result"] == "passed"


def test_adoption_change_and_packaged_model_change_affect_different_assessments(execution):
    provider, run = execution
    original = LIFECYCLE.assess_execution(provider, run)
    (provider / LIFECYCLE.ADOPTION).write_text("Changed synthetic source-adoption decision.\n")
    source_changed = LIFECYCLE.assess_execution(provider, run)
    assert source_changed["dependency_review"]["source_alignment"] == "review_required"
    assert source_changed["assessment"]["status"] == "supported"
    data = json.loads((provider / LIFECYCLE.DATA).read_text())
    data["synthetic_coefficient_change"] = 1
    write_json(provider / LIFECYCLE.DATA, data)
    model_changed = LIFECYCLE.assess_execution(provider, run)
    assert model_changed["dependency_review"]["numerical_target"] == "review_required"
    assert model_changed["assessment"]["status"] == "unknown"
    assert model_changed["assessment"]["target"] != original["assessment"]["target"]
    assert model_changed["evidence"] == original["evidence"]


@pytest.mark.parametrize("name", ["receipt.json", "ions.npz", "execution.log"])
def test_changed_archives_are_rejected_without_rewriting_the_original(execution, name):
    provider, run = execution
    path = run / name
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="artifact changed"):
        LIFECYCLE.assess_execution(provider, run)


def test_execution_failure_is_not_a_scientific_refutation(execution):
    provider, run = execution
    record = json.loads((run / "execution.json").read_text())
    record["exit_code"] = 1
    write_json(run / "execution.json", record)
    report = LIFECYCLE.assess_execution(provider, run)
    assert report["evidence"]["result"] == "failed"
    assert report["assessment"]["status"] == report["physical_validation"] == "unknown"
    assert "execution_failed" in report["assessment"]["reasons"]
    assert "numerical_comparison_failed" not in report["assessment"]["reasons"]


@pytest.mark.parametrize("key", ["provider_revision", "fastchem_binary_sha256"])
def test_a_different_execution_procedure_requires_review(execution, key):
    provider, run = execution
    record = json.loads((run / "execution.json").read_text())
    record[key] = "unreviewed"
    write_json(run / "execution.json", record)
    with pytest.raises(ValueError, match="new review"):
        LIFECYCLE.assess_execution(provider, run)


def test_missing_current_packaged_data_keeps_archived_execution(execution):
    provider, run = execution
    (provider / LIFECYCLE.DATA).unlink()
    report = LIFECYCLE.assess_execution(provider, run)
    assert report["assessment"]["status"] == "unknown"
    assert report["evidence"]["result"] == "passed"
    assert report["dependency_review"]["source_alignment"] == "unknown"


def test_saved_transition_report_keeps_distinct_evidence_and_evaluator_identity():
    report = json.loads((EXAMPLE / "lifecycle.json").read_text())
    assert report["generator_sha256"] == LIFECYCLE.sha256(EXAMPLE / "lifecycle.py")
    assert report["evaluator_sha256"] == LIFECYCLE.sha256(EXAMPLE / "reassess.py")
    assert report["review_sha256"] == LIFECYCLE.sha256(EXAMPLE / "rerun_review.json")
    transition = report["environment_transition"]
    old, before, after = (transition[k] for k in ("baseline", "new_environment_before_rerun", "new_environment_after_rerun"))
    assert old["evidence_id"] == before["evidence_id"] != after["evidence_id"]
    assert [old["status"], before["status"], after["status"]] == ["supported", "unknown", "supported"]
    assert report["physical_validation"] == "unknown"


def test_saved_actual_executions_cover_both_networks_and_differ_only_in_jax_stack():
    claim = json.loads((EXAMPLE / "claim_revision.json").read_text())
    environments = []
    for version in ("0.6.2", "0.10.2"):
        run = EXAMPLE / "runs" / ("jax-" + version)
        record = json.loads((run / "execution.json").read_text())
        assert record["exit_code"] == 0 and record["inputs_unchanged_during_execution"]
        assert record["capture_sha256"] == LIFECYCLE.sha256(EXAMPLE / "rerun.py")
        receipt_path = LIFECYCLE.checked_artifact(run, "receipt.json", record["receipt_sha256"])
        LIFECYCLE.checked_artifact(run, "execution.log", record["log_sha256"])
        receipt = json.loads(receipt_path.read_text())
        for path, digest in receipt["output_sha256"].items():
            LIFECYCLE.checked_artifact(run, path, digest)
        for table, limits in (("diagnostics.csv", "exogibbs_maxima"), ("fastchem_parity.csv", "fastchem_maxima")):
            check = LIFECYCLE.table_checks(run / table, claim["scope"], claim["scope"][limits])
            assert check["complete"] and check["samples"] == 70 and not check["failures"]
        env = deepcopy(record["environment"])
        for key in ("jax", "jaxlib"):
            assert env["packages"].pop(key) == version
        environments.append(env)
    assert environments[0] == environments[1]
