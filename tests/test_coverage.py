"""Registration gaps and changed scientific code must not produce green coverage."""

import copy
import hashlib
import json
from pathlib import Path
import shutil

import pytest
import yaml

from mceg.__main__ import main
from mceg.coverage import Inventory, check_coverage
from mceg.validator import load_contract


CONTRACT = Path(__file__).resolve().parents[1] / "contracts/ideal_gas.yaml"


@pytest.fixture
def provider(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "mceg/contracts").mkdir(parents=True)
    (tmp_path / "src/law.py").write_text(
        "raise RuntimeError('Coverage must never import providers')\n"
        "def concentration(pressure, law='linear'):\n"
        "    return pressure if law == 'linear' else pressure ** 0.5\n"
        "class Host:\n    def response(self):\n        return 1\n"
    )
    (tmp_path / "src/coefficients.json").write_text('{"capacity": 1.0}\n')
    (tmp_path / "src/support.py").write_text('"""Public exports are kept here."""\n')
    shutil.copyfile(CONTRACT, tmp_path / "mceg/contracts/family.yaml")
    files = {}
    for path in sorted((tmp_path / "src").iterdir()):
        files[path.relative_to(tmp_path).as_posix()] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "role": "support" if path.name == "support.py" else "model",
            "note": "Reviewed fixture model boundaries, including both law choices.",
        }
    models = [{
        "id": f"water.{law}", "description": f"Water with {law} concentration law.",
        "bindings": [
            {"path": "src/law.py", "symbol": "concentration", "settings": {"law": law}},
            {"path": "src/law.py", "symbol": "Host.response"},
            {"path": "src/coefficients.json"},
        ],
        "contracts": [{"path": "mceg/contracts/family.yaml", "model_id": load_contract(CONTRACT).model.id}],
    } for law in ("linear", "square_root")]
    return tmp_path, {
        "inventory_version": "0.1", "scope": "Two law options and their coefficient data.",
        "source_roots": ["src"], "contract_roots": ["mceg/contracts"],
        "files": files, "models": models,
    }


def audit(provider):
    root, data = provider
    return check_coverage(root, Inventory.model_validate(data))


def kinds(report):
    return {issue["kind"] for issue in report["issues"]}


def test_many_to_many_registration_is_not_scientific_support(provider):
    report = audit(provider)
    assert report["status"] == "complete"
    assert report["summary"]["registered_models"] == 2
    assert report["summary"]["discovered_contracts"] == 1
    assert "physical" not in report
    assert report == audit(provider)


def test_uncontracted_variant_is_visible_even_when_the_same_function_is_registered(provider):
    provider[1]["models"][1]["contracts"] = []
    report = audit(provider)
    assert report["status"] == "gaps"
    assert report["summary"]["registered_models"] == 1
    assert report["summary"]["uncontracted_models"] == 1
    assert kinds(report) == {"uncontracted_model"}


@pytest.mark.parametrize("path,extra", [
    ("src/law.py", "\ndef new_model():\n    return 42\n"),
    ("src/law.py", "\n# A changed branch or coefficient also requires review.\n"),
    ("src/coefficients.json", " "),
    ("src/support.py", "def implicit_law(p):\n    return p ** 0.5\n"),
])
def test_edits_require_review_even_in_previously_support_only_files(provider, path, extra):
    target = provider[0] / path
    target.write_text(target.read_text() + extra)
    report = audit(provider)
    assert kinds(report) == {"changed_file"}
    assert report["summary"]["files_needing_review"] == 1


def test_new_untracked_source_and_data_are_not_hidden_by_contract_manifests(provider):
    for name in ("new_model.py", "new_coefficients.csv", ".hidden_coefficients"):
        (provider[0] / "src" / name).write_text("")
    report = audit(provider)
    assert kinds(report) == {"unreviewed_file"}
    assert report["summary"]["files_needing_review"] == 3


def test_removed_model_and_contract_mappings_have_separate_diagnostics(provider):
    provider[1]["models"] = []
    report = audit(provider)
    assert kinds(report) == {"unlisted_contract", "unbound_model_file"}


@pytest.mark.parametrize("mutation,expected", [
    ("missing", {"invalid_contract", "contract_mismatch"}),
    ("malformed", {"invalid_contract", "contract_mismatch"}),
    ("wrong_id", {"contract_mismatch"}),
])
def test_missing_invalid_and_wrong_contracts_fail(provider, mutation, expected):
    path = provider[0] / "mceg/contracts/family.yaml"
    if mutation == "missing":
        path.unlink()
    elif mutation == "malformed":
        path.write_text("schema_version: [broken\n")
    else:
        provider[1]["models"][0]["contracts"][0]["model_id"] = "different.model"
    report = audit(provider)
    assert kinds(report) == expected
    assert report["summary"]["invalid_models"] >= 1


def test_symbol_deletion_is_detected_even_if_someone_refreshes_a_hash(provider):
    path = provider[0] / "src/law.py"
    path.write_text("def renamed():\n    pass\n")
    provider[1]["files"]["src/law.py"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = audit(provider)
    assert kinds(report) == {"missing_symbol"}
    assert all(model["source_status"] == "needs_review" for model in report["models"])


def test_syntax_error_and_missing_sources_are_not_silently_skipped(provider):
    (provider[0] / "src/law.py").write_text("def broken(\n")
    (provider[0] / "src/coefficients.json").unlink()
    assert {"changed_file", "unreadable_source", "missing_symbol", "missing_source"} <= kinds(audit(provider))


def test_binding_needs_a_model_file_review_and_scope(provider):
    provider[1]["files"]["src/law.py"]["role"] = "support"
    provider[1]["source_roots"] = ["src/support.py"]
    assert {"unreviewed_binding", "file_outside_scope"} <= kinds(audit(provider))


def test_python_cache_only_is_ignored_and_overlapping_scopes_are_deduplicated(provider):
    root, data = provider
    (root / "src/__pycache__").mkdir()
    (root / "src/__pycache__/cache.py").write_text("not Python")
    (root / "src/cache.pyc").write_bytes(b"cache")
    data["source_roots"].append("src/law.py")
    report = audit(provider)
    assert report["status"] == "complete"
    assert report["summary"]["source_files"] == 3


@pytest.mark.parametrize("path", ["../outside", "/outside", "src/../outside", "./src/law.py",
                                  "src//law.py", "src\\law.py", "https://example.com", "."])
def test_nonlocal_paths_are_invalid_inventory(provider, path):
    provider[1]["models"][0]["bindings"][0]["path"] = path
    with pytest.raises(ValueError):
        audit(provider)


@pytest.mark.parametrize("where", ["source_file", "source_directory", "contract"])
def test_symlinks_are_reported_without_following_targets(provider, tmp_path, where):
    root, _ = provider
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "model.py").write_text("def should_not_be_read():\n    pass\n")
    if where == "source_file":
        (root / "src/link.py").symlink_to(outside / "model.py")
    elif where == "source_directory":
        (root / "src/link").symlink_to(outside, target_is_directory=True)
    else:
        (root / "mceg/contracts/link.yaml").symlink_to(CONTRACT)
    report = audit(provider)
    assert report["status"] == "gaps"
    assert any(issue["kind"].endswith("scan_error") for issue in report["issues"])
    assert not any(item["path"].endswith("link/model.py") for item in report["files"])


def test_missing_scan_roots_do_not_report_empty_success(provider):
    provider[1]["source_roots"] = ["missing"]
    provider[1]["contract_roots"] = ["missing_contracts"]
    assert {"source_scan_error", "contract_scan_error"} <= kinds(audit(provider))


@pytest.mark.parametrize("mutation", ["duplicate_id", "unknown_field", "empty_roots", "nan"])
def test_strict_inventory_prevents_ambiguous_or_empty_scope(provider, mutation):
    data = provider[1]
    if mutation == "duplicate_id":
        data["models"].append(copy.deepcopy(data["models"][0]))
    elif mutation == "unknown_field":
        data["models"][0]["contract"] = "a typo"
    elif mutation == "empty_roots":
        data["source_roots"] = []
    else:
        data["models"][0]["bindings"][0]["settings"]["coefficient"] = float("nan")
    with pytest.raises(ValueError):
        audit(provider)


def test_cli_exit_codes_json_text_and_no_writes(provider, capsys, monkeypatch):
    root, data = provider
    path = root / "mceg/models.yaml"
    path.write_text(yaml.safe_dump(data))
    before = path.read_bytes()
    monkeypatch.chdir(root)
    assert main(["coverage", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"
    (root / "src/new.py").write_text("")
    assert main(["coverage", str(root)]) == 1
    assert "unreviewed_file src/new.py" in capsys.readouterr().out
    assert before == path.read_bytes()
    path.write_text("inventory_version: '0.1'\ninventory_version: '0.1'\n")
    assert main(["coverage", "--json"]) == 2
    assert "Duplicate mapping key" in capsys.readouterr().err
    path.unlink()
    assert main(["coverage"]) == 2
    assert "INVALID inventory" in capsys.readouterr().err


def test_json_inventory_and_legacy_file_named_coverage(provider, monkeypatch, capsys):
    root, data = provider
    (root / "mceg/models.json").write_text(json.dumps(data))
    assert main(["coverage", str(root), "--inventory", "mceg/models.json"]) == 0
    assert "COMPLETE" in capsys.readouterr().out
    shutil.copyfile(CONTRACT, root / "coverage")
    monkeypatch.chdir(root)
    assert main(["coverage"]) == 0
    assert "VALID coverage (structure only)" in capsys.readouterr().out
