"""Check provider identity and receipt consistency without provider imports."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest
import yaml

from mceg import load_contract


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/provider_h2"
SPEC = importlib.util.spec_from_file_location("provider_h2", EXAMPLE / "run.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def git(root, *args):
    return subprocess.check_output([
        "git", "-C", str(root), "-c", "user.name=MCEG Test", "-c", "user.email=test@example.invalid",
        "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args,
    ], stderr=subprocess.DEVNULL).decode().strip()


@pytest.fixture
def source_history(tmp_path):
    git(tmp_path, "init")
    model = tmp_path / "model.py"
    model.write_text("coefficient = 1.0\n")
    git(tmp_path, "add", "model.py")
    git(tmp_path, "commit", "-m", "Add model")
    revision = git(tmp_path, "rev-parse", "HEAD")
    hashes = {"model.py": hashlib.sha256(model.read_bytes()).hexdigest()}
    (tmp_path / "contract.txt").write_text("Metadata added without changing the model.\n")
    git(tmp_path, "add", "contract.txt")
    git(tmp_path, "commit", "-m", "Add metadata")
    return tmp_path, revision, hashes


def test_contract_commit_does_not_change_selected_implementation_identity(source_history):
    report = RUNNER.verify_snapshot(*source_history)
    assert report["audited_revision"] != report["checkout_revision"]
    assert report["selected_files_match_audit"]


@pytest.mark.parametrize("committed", [False, True])
def test_modified_source_requires_review_even_if_contract_and_receipt_still_parse(source_history, committed):
    root, revision, hashes = source_history
    (root / "model.py").write_text("coefficient = 2.0\n")
    if committed:
        git(root, "add", "model.py")
        git(root, "commit", "-m", "Change model")
    with pytest.raises(ValueError, match="Review and rerun"):
        RUNNER.verify_snapshot(root, revision, hashes)


def test_replacing_hashes_does_not_relabel_the_audited_revision(source_history):
    root, revision, hashes = source_history
    model = root / "model.py"
    model.write_text("coefficient = 2.0\n")
    hashes["model.py"] = hashlib.sha256(model.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="Review and rerun"):
        RUNNER.verify_snapshot(root, revision, hashes)


def test_reusing_manual_assessment_requires_same_scientific_declarations():
    original = load_contract(ROOT / "contracts/h2_solubility.yaml")
    changed = original.model_copy(deep=True)
    changed.domains[0].conditions[0] = "Different temperature range."
    assert RUNNER.scientific_record(original) != RUNNER.scientific_record(changed)


def test_saved_provider_execution_binds_the_consumer_and_retains_nine_assessments():
    record = json.loads((EXAMPLE / "result.json").read_text())
    case = yaml.safe_load(RUNNER.CASE.read_text())
    assert record["inputs"] == case["inputs"]
    assert record["case_sha256"] == RUNNER.sha256(RUNNER.CASE)
    assert record["runner_sha256"] == RUNNER.sha256(EXAMPLE / "run.py")
    for name, digest in {**record["helper_sha256"], **record["baseline_contract_sha256"]}.items():
        assert digest == RUNNER.sha256(ROOT / name)
    assert len(record["assessments"]) == 9
    for old, current in zip(case["assessments"], record["assessments"]):
        assert {k: v for k, v in old.items() if k != "evidence"} == {
            k: v for k, v in current.items() if k != "evidence"}
        assert all(ref["provider"] in record["providers"] for ref in current["evidence"])
    for provider in record["providers"].values():
        assert provider["selected_files_match_audit"]
        assert provider["audited_revision"] != provider["checkout_revision"]
        assert provider["reference_checks"]["local_files_complete"]
    assert len(record["numerical_checks"]) == 4
    assert all(check["passed"] for check in record["numerical_checks"])
    assert record["physical_validation"] == "unknown"
