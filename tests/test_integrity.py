"""Optional file verification is scoped, offline, and independent of stored support."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shlex

import pytest

from mceg import ContractV02, load_contract
from mceg.__main__ import main
from mceg.check import check_contract


@pytest.fixture
def pinned(tmp_path):
    root = tmp_path / "provider checkout"
    root.mkdir()
    contents = {"model.py": b"current source\n", "result.json": b'{"result": "passed"}\n',
                "reference.dat": b"archived reference\n"}
    for name, content in contents.items():
        (root / name).write_bytes(content)
    hashes = {name: hashlib.sha256(content).hexdigest() for name, content in contents.items()}
    implementation = {"repository": "https://example.org/fixture", "revision": "current",
                      "entry_points": ["fixture:evaluate"]}

    def evidence(key, source, kind):
        return {"id": key, "kind": kind, "summary": "Synthetic file fixture.",
                "scope": "File integrity only.", "sources": [source],
                "provenance": {"role": "primary", "location": source, "inspection": "inspected",
                               "note": "Synthetic inspected record."},
                "artifacts": [{"source": source, "sha256": hashes[source]}]}

    reference = evidence("reference", "reference.dat", "implementation")
    run = evidence("run", "result.json", "numerical_test")
    run.update(result="passed", subject="current", context="review")
    run["provenance"]["derived_from"] = [
        {"evidence": "reference", "comparison": "consistent", "note": "Synthetic comparison."}]
    historical = deepcopy(run)
    historical.update(id="historical-run", subject="historical")
    historical["artifacts"] = [{"source": "absent-old-result.json", "sha256": "0" * 64}]
    assessment = {"id": "current-review", "kind": "evidence_support", "subject": "current", "context": "review",
                  "method": {"id": "manual-review", "revision": "1", "description": "Synthetic recorded review."},
                  "evidence": ["run"], "reasons": ["Recorded review, not fresh verification."],
                  "claim": "numerical-check", "claim_revision": "1", "status": "supported", "origin": "reviewed"}
    data = {
        "schema_version": "0.2",
        "model": {"id": "fixture", "name": "File fixture", "description": "Synthetic contract.",
                  "implementation": implementation},
        "assumptions": [], "limitations": [],
        "domains": [{"kind": "scientific_applicability", "status": "unknown", "conditions": [],
                     "description": "Not evaluated.", "evidence": ["run"]}],
        "claims": [{"id": "numerical-check", "revision": "1", "kind": "numerical_verification",
                    "statement": "The recorded comparison meets its criterion.", "scope": "Synthetic scope."}],
        "evidence": [reference, run, historical],
        "subjects": [
            {"id": "historical", "implementation": {**implementation, "revision": "old"},
             "selected_files": {"model.py": "0" * 64}},
            {"id": "current", "implementation": implementation, "selected_files": {"model.py": hashes["model.py"]}},
        ],
        "contexts": [{"id": "review", "scope": "Synthetic archived context."}],
        "assessments": [assessment, {**assessment, "id": "old-review", "subject": "historical",
                                     "evidence": ["historical-run"]}],
    }
    path = tmp_path / "contract.json"
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    return path, root


def test_selection_checks_current_subject_and_transitive_artifacts(pinned, capsys, monkeypatch):
    path, root = pinned
    before = path.read_bytes()
    monkeypatch.chdir(root.parent)
    assert main(["check", str(path), "--assessment", "current-review", "--root", root.name, "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    entry = report["contracts"][0]
    assert report["summary"] == {"PASS": 5, "FAIL": 0, "UNKNOWN": 0}
    integrity = entry["integrity"]
    assert integrity["root"] == str(root)
    assert integrity["subject"] == "current"
    assert len(integrity["selected_files"]) == 1
    assert {r["evidence"] for r in integrity["artifact_hashes"]} == {"run", "reference"}
    assert len(integrity["artifact_hashes"]) == 2
    assert all(r["expected_sha256"] == r["actual_sha256"] for r in integrity["artifact_hashes"])
    args = shlex.split(report["explain_command"])[1:]
    assert args[args.index("--root") + 1] == root.name
    assert main([*args, "--json"]) == 0
    explanation = json.loads(capsys.readouterr().out)["contracts"][0]
    assert explanation["integrity"] == integrity
    assert all(item["suggested_steps"] == [] for item in explanation["items"][-2:])
    assert path.read_bytes() == before
    assert main(["check", str(path), "--assessment", "old-review", "--root", str(root), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["summary"]["FAIL"] == 2


@pytest.mark.parametrize("source,check", [("model.py", "selected_files"), ("result.json", "artifact_hashes"),
                                         ("reference.dat", "artifact_hashes")])
@pytest.mark.parametrize("change", ["changed", "missing", "directory"])
def test_file_failures_do_not_rewrite_historical_results(pinned, capsys, source, check, change):
    path, root = pinned
    before = path.read_bytes()
    if change == "changed":
        (root / source).write_bytes(b"changed bytes\n")
    else:
        (root / source).unlink()
        if change == "directory":
            (root / source).mkdir()
    args = [str(path), "--assessment", "current-review", "--root", str(root)]
    assert main(["check", *args, "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    entry = report["contracts"][0]
    assert next(c for c in entry["checks"] if c["name"] == check)["status"] == "FAIL"
    failed = next(r for r in entry["integrity"][check] if r["source"] == source)
    assert failed["status"] == "FAIL"
    assert (failed["actual_sha256"] is not None) == (change == "changed")
    assert entry["assessments"][0]["status"] == "supported"
    assert main(["explain", *args, "--json"]) == 0
    explanation = json.loads(capsys.readouterr().out)["contracts"][0]
    item = next(i for i in explanation["items"] if i.get("name") == check)
    assert item["status"] == "FAIL" and item["suggested_steps"]
    assert source in " ".join(item["details"])
    assert main(["check", *args, "--plain"]) == 1
    assert source in capsys.readouterr().out
    assert main(["check", str(path), "--assessment", "current-review", "--json"]) == 0
    assert "integrity" not in json.loads(capsys.readouterr().out)["contracts"][0]
    assert path.read_bytes() == before
    assert next(e for e in load_contract(path).evidence if e.id == "run").result == "passed"


@pytest.mark.parametrize("case", ["null_digest", "empty_manifests", "remote_artifact"])
def test_unverified_files_stay_unknown(pinned, case):
    path, root = pinned
    data = load_contract(path).model_dump()
    if case == "null_digest":
        data["subjects"][1]["selected_files"]["model.py"] = None
    elif case == "empty_manifests":
        data["subjects"][1]["selected_files"] = {}
        for evidence in data["evidence"]:
            evidence["artifacts"] = []
    else:
        data["evidence"][0]["artifacts"][0]["source"] = "https://example.org/reference.dat"
    data["assessments"][0]["status"] = "unknown"
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    entry = check_contract(path, {}, "current-review", root=root)
    checks = {c["name"]: c["status"] for c in entry["checks"]}
    assert checks["artifact_hashes" if case == "remote_artifact" else "selected_files"] == "UNKNOWN"
    assert checks["recorded_support"] == "UNKNOWN"
    assert "FAIL" not in checks.values()


@pytest.mark.parametrize("case", ["absolute", "parent", "symlink"])
def test_paths_cannot_read_outside_the_root(pinned, case, monkeypatch):
    path, root = pinned
    outside = root.parent / "outside.dat"
    outside.write_bytes(b"outside\n")
    if case == "symlink":
        (root / "link.dat").symlink_to(outside)
    source = {"absolute": str(outside), "parent": "../outside.dat", "symlink": "link.dat"}[case]
    data = load_contract(path).model_dump()
    data["subjects"][1]["selected_files"] = {source: hashlib.sha256(b"outside\n").hexdigest()}
    path.write_text(ContractV02.model_validate(data).model_dump_json())
    original_open = Path.open

    def guarded_open(target, *args, **kwargs):
        assert target.resolve() != outside
        return original_open(target, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    entry = check_contract(path, {}, "current-review", root=root)
    record = entry["integrity"]["selected_files"][0]
    assert record["status"] == "FAIL" and record["actual_sha256"] is None


def test_unreadable_file_reports_failure_without_aborting_other_checks(pinned, monkeypatch):
    path, root = pinned
    original_open = Path.open

    def unreadable(target, *args, **kwargs):
        if target == root / "model.py":
            raise PermissionError("Synthetic unreadable file")
        return original_open(target, *args, **kwargs)

    monkeypatch.setattr(Path, "open", unreadable)
    entry = check_contract(path, {}, "current-review", root=root)
    assert entry["integrity"]["selected_files"][0]["status"] == "FAIL"
    assert all(r["status"] == "PASS" for r in entry["integrity"]["artifact_hashes"])


@pytest.mark.parametrize("command", ["check", "explain"])
@pytest.mark.parametrize("case", ["no_assessment", "missing_root", "file_root", "missing_assessment", "v01"])
def test_root_requires_a_directory_and_a_valid_v02_assessment(pinned, capsys, command, case):
    path, root = pinned
    selection = ["--assessment", "current-review"]
    if case == "no_assessment":
        selection = []
    elif case == "missing_root":
        root /= "missing"
    elif case == "file_root":
        root /= "model.py"
    elif case == "missing_assessment":
        selection = ["--assessment", "missing"]
    elif case == "v01":
        path = Path(__file__).resolve().parents[1] / "contracts/ideal_gas.yaml"
    with pytest.raises(SystemExit) as error:
        main([command, str(path), *selection, "--root", str(root), "--json"])
    assert error.value.code == 2
    assert not capsys.readouterr().out


def test_empty_selection_and_invalid_contract_keep_existing_exit_codes(pinned, tmp_path, capsys):
    path, root = pinned
    empty = tmp_path / "empty"
    empty.mkdir()
    options = ["--assessment", "current-review", "--root", str(root), "--json"]
    assert main(["check", str(empty), *options]) == 5
    capsys.readouterr()
    broken = tmp_path / "broken.yaml"
    broken.write_text("schema_version: [unterminated\n")
    assert main(["check", str(path), str(broken), *options]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["summary"]["FAIL"] == 1
    assert len(report["contracts"]) == 2
