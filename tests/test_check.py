"""The human CLI discovers contracts without changing validation or declarations."""

import json
from pathlib import Path
import shutil

import pytest

from mceg.__main__ import main


CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


@pytest.mark.parametrize("directory", ["mceg/contracts", "contracts"])
def test_discovery_from_repository_and_contract_directory(tmp_path, monkeypatch, capsys, directory):
    contracts = tmp_path / directory
    contracts.mkdir(parents=True)
    shutil.copyfile(CONTRACTS / "ideal_gas.yaml", contracts / "ideal.yaml")
    (contracts / "nested").mkdir()
    shutil.copyfile(CONTRACTS / "h2_solubility.yaml", contracts / "nested/h2.yml")
    (tmp_path / "unrelated.yaml").write_text("Not a contract.\n")
    (contracts / ".hidden.yaml").write_text("Ignored.\n")
    for current in (tmp_path, contracts):
        monkeypatch.chdir(current)
        assert main(["check", "--json"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["collected"] == 2
        assert len(report["contracts"]) == 2


def test_selection_and_overlapping_paths_are_deduplicated(capsys):
    assert main(["check", str(CONTRACTS), str(CONTRACTS / "ideal_gas.yaml"),
                 "-k", "IDEAL", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["collected"] == 5
    assert len(report["contracts"]) == 1
    assert report["contracts"][0]["path"].endswith("ideal_gas.yaml")


def test_empty_selection_and_missing_path_have_distinct_exit_codes(tmp_path, capsys):
    assert main(["check", str(tmp_path), "--json"]) == 5
    assert json.loads(capsys.readouterr().out)["collected"] == 0
    assert main(["check", str(CONTRACTS), "-k", "no-match"]) == 5
    assert "No contracts selected" in capsys.readouterr().out
    with pytest.raises(SystemExit) as error:
        main(["check", str(tmp_path / "missing")])
    assert error.value.code == 2
    assert "Path does not exist" in capsys.readouterr().err


def test_invalid_contract_does_not_stop_other_checks(tmp_path, capsys):
    broken = tmp_path / "broken.yaml"
    broken.write_text("schema_version: [unterminated\n")
    assert main(["check", str(broken), str(CONTRACTS / "ideal_gas.yaml"), "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert len(report["contracts"]) == 2
    assert report["summary"]["FAIL"] == 1
    invalid = next(c for c in report["contracts"] if c["model"] is None)
    assert invalid["checks"][0]["details"]


def test_unsupported_models_leave_reuse_unknown_and_do_not_rewrite_claims(capsys):
    path = CONTRACTS / "ideal_gas.yaml"
    before = path.read_bytes()
    assert main(["check", str(path), "-v"]) == 0
    output = capsys.readouterr().out
    assert "No automatic evidence-reuse rule for this model" in output
    assert "Recorded v0.1 declarations" in output
    assert "[theoretical]" in output
    assert path.read_bytes() == before


@pytest.mark.parametrize("option,value", [("--temperature", "nan"), ("--pressure", "0"),
                                         ("--temperature", "inf"), ("--pressure", "-1")])
def test_invalid_overrides_are_usage_errors(capsys, option, value):
    with pytest.raises(SystemExit) as error:
        main(["check", str(CONTRACTS), option, value])
    assert error.value.code == 2
    assert not capsys.readouterr().out


@pytest.mark.parametrize("content", ["{", "[]", '{"temperature_C": 1750}'])
def test_invalid_context_is_a_usage_error(tmp_path, capsys, content):
    context = tmp_path / "context.json"
    context.write_text(content)
    with pytest.raises(SystemExit) as error:
        main(["check", str(CONTRACTS), "--context", str(context), "--json"])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert "error:" in captured.err


def test_legacy_file_named_check_and_trace_remain_available(tmp_path, monkeypatch, capsys):
    shutil.copyfile(CONTRACTS / "h2_solubility.yaml", tmp_path / "check")
    monkeypatch.chdir(tmp_path)
    assert main(["check"]) == 0
    assert "VALID check (structure only)" in capsys.readouterr().out
    assert main(["--trace", "metadata_pressure", "check"]) == 0
    assert json.loads(capsys.readouterr().out)["evidence"] == "metadata_pressure"
