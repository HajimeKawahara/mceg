"""Language selection changes presentation, not evidence or machine interfaces."""

import json
from pathlib import Path
import shlex

import pytest

from mceg import _curated, load_contract
from mceg.__main__ import main
from mceg.explain import SOURCE_ACTIONS
from test_curated_assessment import example


ROOT = Path(__file__).resolve().parents[1]
H2 = ROOT / "examples/v02/h2_solubility.yaml"


@pytest.mark.parametrize("command,options,code", [("check", [], 1),
                                                ("explain", ["--evidence", "experimental_fit"], 0)])
def test_language_does_not_change_json_or_exit_status(command, options, code, capsys):
    args = [command, str(H2), *options, "--json"]
    assert main(args) == code
    original = capsys.readouterr().out
    for language in ("en", "ja"):
        assert main([*args, "--lang", language]) == code
        assert capsys.readouterr().out == original


def test_japanese_handoff_preserves_language_context_and_quoted_paths(example, monkeypatch, capsys):
    provider, _, review = example
    moved = provider.with_name("provider with spaces")
    provider.rename(moved)
    original = _curated.run
    monkeypatch.setattr(_curated, "run", lambda root, inputs: original(root, inputs, review))
    assert main(["check", str(moved), "-k", "curated", "--temperature", "1750", "--lang", "ja"]) == 0
    text = capsys.readouterr().out
    hint = next(line.removeprefix("次の作業: ") for line in text.splitlines() if line.startswith("次の作業: "))
    args = shlex.split(hint)[1:]
    assert str(moved) in args and args[-2:] == ["--lang", "ja"]
    assert main(args) == 0
    text = capsys.readouterr().out
    assert "temperature_K: 1750.0" in text and "数値検証を実行" in text
    link = next(line.strip().removeprefix("詳しく確認: ") for line in text.splitlines()
                if line.strip().startswith("詳しく確認: "))
    assert shlex.split(link)[-2:] == ["--lang", "ja"]
    assert main(shlex.split(link)[1:]) == 0
    assert "提案する次の作業" in capsys.readouterr().out


def test_authored_text_is_never_translated_even_if_it_matches_a_ui_message(tmp_path, capsys):
    data = load_contract(H2).model_dump()
    authored = SOURCE_ACTIONS["source_not_fully_inspected"]["action"]
    data["follow_ups"][0]["action"] = authored
    path = tmp_path / "authored.json"
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    assert main(["explain", str(path), "--evidence", "experimental_fit", "--lang", "ja"]) == 0
    text = " ".join(capsys.readouterr().out.split())
    assert "記録された次の作業（原文）: " + authored in text
    assert "提案する次の作業: 必要な本文やデータ" in text
    assert path.read_bytes() == before
