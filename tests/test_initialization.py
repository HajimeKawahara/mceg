"""Initialize a usable draft without claiming review or overwriting prior work."""

import copy
import hashlib
import json
from pathlib import Path
import shutil
import textwrap

import pytest
import yaml

from mceg.__main__ import main
from mceg.check import check_contract
from mceg.coverage import Inventory, check_coverage
from mceg.initialization import initialize
from mceg.validator import load_contract, read_document


@pytest.fixture
def provider(tmp_path, monkeypatch):
    root = tmp_path / "provider"
    (root / "src/pkg").mkdir(parents=True)
    (root / "src/pkg/water.py").write_text(
        "raise RuntimeError('Do not import provider code')\n"
        "def gibbs_j(pressure, water_model='power_law'):\n    return pressure\n"
        "class Host:\n    def response(self):\n        return 1\n"
    )
    monkeypatch.setattr("mceg.initialization._git", lambda *args: "")
    return root


def start(root, model_id="pkg.water", **kwargs):
    return initialize(root, model_id, "src/pkg/water.py", "gibbs_j", **kwargs)


def inventory(root):
    return Inventory.model_validate(read_document(root / "mceg/models.yaml"))


def test_new_draft_is_valid_unassessed_and_has_actionable_followups(provider):
    path = start(provider, settings={"water_model": "power_law"})
    contract = load_contract(path)
    assert contract.schema_version == "0.2"
    assert contract.model.id == "pkg.water"
    assert contract.model.implementation.repository == "unknown"
    assert contract.model.implementation.revision == "unreviewed working tree"
    assert contract.model.implementation.entry_points == ["src/pkg/water.py:gibbs_j"]
    assert not contract.assessments and not contract.conditions
    assert all(domain.status == "unknown" for domain in contract.domains)
    assert contract.evidence[0].provenance.inspection == "not_inspected"
    assert not contract.subjects[0].selected_files
    assert contract.contexts[0].settings == {"water_model": "power_law"}
    assert {item.target for item in contract.follow_ups} == {"implementation", "numerical_verification", "physical_accuracy"}
    assert not contract.follow_up_resolutions
    checks = check_contract(path, {})["checks"]
    assert all(check["status"] == "UNKNOWN" for check in checks if check["name"] != "structure")
    ledger = inventory(provider)
    assert ledger.source_roots == ["src/pkg/water.py"] and not ledger.files
    report = check_coverage(provider, ledger)
    assert report["models"][0]["registration"] == "registered"
    assert report["models"][0]["review_pending"] is True
    assert {i["kind"] for i in report["issues"]} == {"unreviewed_model", "unreviewed_file", "unreviewed_binding"}


def test_new_variant_cannot_inherit_review_from_shared_source(provider):
    start(provider, settings={"water_model": "power_law"})
    ledger_path = provider / "mceg/models.yaml"
    data = read_document(ledger_path)
    data["models"][0]["review_pending"] = False
    data["files"]["src/pkg/water.py"] = {
        "sha256": hashlib.sha256((provider / "src/pkg/water.py").read_bytes()).hexdigest(),
        "role": "model", "note": "The power-law boundary was reviewed.",
    }
    ledger_path.write_text(yaml.safe_dump(data, sort_keys=False))
    before = copy.deepcopy(data)
    old_contract = (provider / "mceg/contracts/pkg.water.yaml").read_bytes()
    assert check_coverage(provider, inventory(provider))["status"] == "complete"
    start(provider, "pkg.water.two_power", settings={"water_model": "two_power_law"})
    updated = read_document(ledger_path)
    assert updated["models"][:-1] == before["models"]
    assert updated["files"] == before["files"]
    assert updated["source_roots"] == before["source_roots"]
    assert (provider / "mceg/contracts/pkg.water.yaml").read_bytes() == old_contract
    report = check_coverage(provider, inventory(provider))
    assert report["summary"]["registered_models"] == 2
    assert {i["kind"] for i in report["issues"]} == {"unreviewed_model"}
    assert all(m["source_status"] == "current" for m in report["models"])


@pytest.mark.parametrize("layout", ["block", "indented", "flow", "flow_trailing_comma", "json", "no_final_newline", "document_end"])
def test_append_preserves_existing_records_comments_and_scope(provider, layout):
    start(provider)
    path = provider / "mceg/models.yaml"
    data = read_document(path)
    data["source_roots"] = ["src/pkg"]
    before = copy.deepcopy(data)
    if layout == "json":
        original = json.dumps(data)
    else:
        original = yaml.safe_dump(data, sort_keys=False, default_flow_style=layout.startswith("flow"))
        if layout == "flow_trailing_comma":
            original = original.replace("source_roots: [src/pkg]", "source_roots: [src/pkg,]")
        original = "# Retain my review notes.\n" + original
        if layout == "indented":
            original = textwrap.indent(original, "  ")
        elif layout == "no_final_newline":
            original = original.rstrip("\n")
        elif layout == "document_end":
            original += "...\n"
    path.write_text(original)
    initialize(provider, "pkg.host", "src/pkg/water.py", "Host.response")
    updated = read_document(path)
    assert updated["models"][:-1] == before["models"]
    assert updated["source_roots"] == ["src/pkg"]
    assert updated["files"] == before["files"]
    if layout != "json":
        assert "# Retain my review notes." in path.read_text()


def test_empty_flow_lists_and_explicit_scope_extension(provider):
    (provider / "mceg").mkdir()
    path = provider / "mceg/models.yaml"
    path.write_text("""inventory_version: '0.1'
scope: Explicitly selected files only.
source_roots: [src/old.py] # Keep old scope.
contract_roots: [contracts]
files: {}
models: [] # This is the first model.
""")
    start(provider)
    data = read_document(path)
    assert data["source_roots"] == ["src/old.py", "src/pkg/water.py"]
    assert data["contract_roots"] == ["contracts", "mceg/contracts"]
    assert len(data["models"]) == 1
    assert "# Keep old scope." in path.read_text()
    assert "# This is the first model." in path.read_text()


def test_flow_roots_with_trailing_commas_keep_their_comments(provider):
    (provider / "mceg").mkdir()
    path = provider / "mceg/models.yaml"
    path.write_text("""inventory_version: '0.1'
scope: Explicit files only.
source_roots: [src/old.py, # A retained note.
]
contract_roots: [contracts,]
files: {}
models: []
""")
    start(provider)
    assert inventory(provider).source_roots == ["src/old.py", "src/pkg/water.py"]
    assert "# A retained note." in path.read_text()


def test_aliased_root_list_needing_extension_is_refused_without_changes(provider):
    (provider / "mceg").mkdir()
    path = provider / "mceg/models.yaml"
    original = """inventory_version: '0.1'
scope: Explicit files only.
source_roots: &shared [src/pkg]
contract_roots: *shared
files: {}
models: []
"""
    path.write_text(original)
    with pytest.raises(ValueError, match="direct YAML list"):
        start(provider)
    assert path.read_text() == original
    assert not (provider / "mceg/contracts").exists()


def test_concurrent_inventory_edit_is_retained_and_new_contract_removed(provider, monkeypatch):
    start(provider)
    path = provider / "mceg/models.yaml"
    original = path.read_bytes()
    original_chmod = Path.chmod
    def change_during_write(self, mode, **kwargs):
        original_chmod(self, mode, **kwargs)
        path.write_bytes(original + b"# A concurrent author edit.\n")
    monkeypatch.setattr(Path, "chmod", change_during_write)
    with pytest.raises(ValueError, match="Inventory changed"):
        start(provider, "pkg.second")
    assert path.read_bytes() == original + b"# A concurrent author edit.\n"
    assert not (provider / "mceg/contracts/pkg.second.yaml").exists()


def test_first_inventory_write_failure_removes_new_contract(provider, monkeypatch):
    from mceg import initialization
    original_write = initialization._write_new
    def fail_inventory(path, text):
        if path.name == "models.yaml":
            raise OSError("simulated inventory creation failure")
        original_write(path, text)
    monkeypatch.setattr(initialization, "_write_new", fail_inventory)
    with pytest.raises(OSError, match="simulated"):
        start(provider)
    assert not (provider / "mceg/contracts/pkg.water.yaml").exists()
    assert not (provider / "mceg/models.yaml").exists()


@pytest.mark.parametrize("model_id", ["../outside", "a/b", ".hidden", "", "space id", "a:b"])
def test_invalid_model_id_makes_no_files(provider, model_id):
    with pytest.raises(ValueError):
        start(provider, model_id)
    assert not (provider / "mceg").exists()


@pytest.mark.parametrize("source,symbol", [
    ("../outside.py", "gibbs_j"), ("src/missing.py", "gibbs_j"),
    ("src/pkg/water.py", "missing"), ("/outside.py", "gibbs_j"),
])
def test_missing_definition_or_nonlocal_source_makes_no_files(provider, source, symbol):
    with pytest.raises((OSError, ValueError)):
        initialize(provider, "pkg.water", source, symbol)
    assert not (provider / "mceg").exists()


def test_repeat_existing_contract_and_duplicate_identity_are_protected(provider):
    path = start(provider)
    ledger = provider / "mceg/models.yaml"
    before = ledger.read_bytes(), path.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        start(provider)
    assert (ledger.read_bytes(), path.read_bytes()) == before
    path.unlink()
    with pytest.raises(ValueError, match="already inventoried"):
        start(provider)
    data = read_document(ledger)
    data["models"][0]["id"] = "different.inventory.identity"
    ledger.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="Contract identity already inventoried"):
        start(provider)
    assert not path.exists()


@pytest.mark.parametrize("location", ["source", "mceg", "contracts", "inventory"])
def test_symlinks_are_refused_before_writing(provider, location, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    if location == "source":
        original = provider / "src/pkg/water.py"
        shutil.copyfile(original, outside / "water.py")
        original.unlink()
        original.symlink_to(outside / "water.py")
    elif location == "mceg":
        (provider / "mceg").symlink_to(outside, target_is_directory=True)
    else:
        (provider / "mceg").mkdir()
        if location == "contracts":
            (provider / "mceg/contracts").symlink_to(outside, target_is_directory=True)
        else:
            (provider / "mceg/models.yaml").symlink_to(outside / "missing.yaml")
    before = sorted(outside.iterdir())
    with pytest.raises(ValueError, match="Symlinks"):
        start(provider)
    assert sorted(outside.iterdir()) == before


@pytest.mark.parametrize("text", ["{", "inventory_version: '0.1'\ninventory_version: '0.1'\n"])
def test_invalid_inventory_is_preserved(provider, text):
    (provider / "mceg").mkdir()
    ledger = provider / "mceg/models.yaml"
    ledger.write_text(text)
    with pytest.raises((ValueError, yaml.YAMLError)):
        start(provider)
    assert ledger.read_text() == text
    assert not (provider / "mceg/contracts").exists()


def test_inventory_replace_failure_rolls_back_only_the_new_contract(provider, monkeypatch):
    old_contract = start(provider)
    ledger = provider / "mceg/models.yaml"
    before = ledger.read_bytes(), old_contract.read_bytes()
    def fail(*args):
        raise OSError("simulated replacement failure")
    monkeypatch.setattr("mceg.initialization.os.replace", fail)
    with pytest.raises(OSError, match="simulated"):
        start(provider, "pkg.second")
    assert (ledger.read_bytes(), old_contract.read_bytes()) == before
    assert not (provider / "mceg/contracts/pkg.second.yaml").exists()
    assert not list((provider / "mceg").glob(".mceg-init-*"))


def test_cli_settings_next_steps_and_explicit_repository(provider, monkeypatch, capsys):
    monkeypatch.chdir(provider)
    assert main(["init", "pkg.water", "--source", "src/pkg/water.py", "--symbol", "gibbs_j",
                 "--setting", "water_model=power_law", "--setting", "ions=false",
                 "--setting", "power=0.5", "--setting", "n=2", "--setting", 'text="2"',
                 "--repository", "https://example.test/pkg", "--revision", "review-target"]) == 0
    output = capsys.readouterr().out
    assert "review pending" in output and "mceg explain" in output and "mceg coverage" in output
    assert "--evidence implementation" in output
    contract = load_contract(provider / "mceg/contracts/pkg.water.yaml")
    assert contract.contexts[0].settings == {"water_model": "power_law", "ions": False, "power": 0.5, "n": 2, "text": "2"}
    assert contract.model.implementation.repository == "https://example.test/pkg"
    assert contract.model.implementation.revision == "review-target"
    assert main(["explain", str(provider / "mceg/contracts/pkg.water.yaml"),
                 "--evidence", "implementation", "--json"]) == 0
    explanation = json.loads(capsys.readouterr().out)
    assert explanation["contracts"][0]["items"][0]["recorded_follow_ups"][0]["id"] == "review_model"
    assert main(["coverage"]) == 1
    assert "unreviewed_model" in capsys.readouterr().out


@pytest.mark.parametrize("settings", [["x"], ["=1"], ["x="], ["x=1", "x=2"],
                                     ["x=null"], ["x=[]"], ["x={}"], ["x=NaN"], ["x=Infinity"]])
def test_invalid_cli_settings_make_no_files(provider, settings, capsys):
    argv = ["init", "pkg.water", "--root", str(provider), "--source", "src/pkg/water.py", "--symbol", "gibbs_j"]
    for value in settings:
        argv.extend(["--setting", value])
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2 and "error:" in capsys.readouterr().err
    assert not (provider / "mceg").exists()


def test_git_head_remains_explicitly_unreviewed(provider, monkeypatch):
    monkeypatch.setattr("mceg.initialization._git", lambda root, *args: "abc123" if args[0] == "rev-parse" else "https://example.test/pkg")
    contract = load_contract(start(provider))
    assert contract.model.implementation.revision == "unreviewed working tree based on abc123"
    assert contract.model.implementation.repository == "https://example.test/pkg"
    assert not contract.subjects[0].selected_files


def test_legacy_file_named_init_is_still_validated(provider, monkeypatch, capsys):
    path = start(provider)
    shutil.copyfile(path, provider / "init")
    monkeypatch.chdir(provider)
    assert main(["init"]) == 0
    assert "VALID init (structure only)" in capsys.readouterr().out
