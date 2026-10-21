"""Drill-down shows actionable gaps, preserving both evidence and the requested context."""

import json
from pathlib import Path
import shlex
import sys

import pytest

from mceg import _curated, load_contract
from mceg.__main__ import main
from test_curated_assessment import example, write_json


ROOT = Path(__file__).resolve().parents[1]
H2 = ROOT / "contracts/h2_solubility.yaml"
V02 = ROOT / "examples/v02/h2_solubility.yaml"


def test_recorded_access_barrier_and_required_scope_are_visible_without_mutation(capsys):
    before = H2.read_bytes()
    assert main(["explain", str(H2), "--evidence", "experimental_fit"]) == 0
    output = " ".join(capsys.readouterr().out.split())
    assert "10.1016/j.epsl.2012.06.031" in output
    assert "HTTP 403" in output and "authentication" in output
    assert "institutional library" in output and "authorized author copy" in output
    assert "equation/table/page" in output and "Completion:" in output
    assert H2.read_bytes() == before


def test_curator_authored_follow_up_and_generic_guidance_are_distinguished(capsys):
    assert main(["explain", str(V02), "--evidence", "experimental_fit", "--json"]) == 0
    item = json.loads(capsys.readouterr().out)["contracts"][0]["items"][0]
    follow_up = item["recorded_follow_ups"][0]
    assert follow_up["id"] == "inspect-original-fit"
    assert "-11.403 and 0.76" in follow_up["completion"]
    assert follow_up["requires"] and item["suggested_steps"]
    assert item["record"]["provenance"]["inspection"] == "not_inspected"


def test_upstream_gaps_have_copyable_navigation(capsys):
    assert main(["explain", str(H2), "--evidence", "implementation", "--json"]) == 0
    item = json.loads(capsys.readouterr().out)["contracts"][0]["items"][0]
    assert "experimental_fit" in item["upstream_gaps"]
    next_command = next(c for c in item["next_commands"] if c.endswith("experimental_fit"))
    assert main(shlex.split(next_command)[1:]) == 0
    assert "HTTP 403" in capsys.readouterr().out


@pytest.mark.parametrize("contract_path", [H2, V02])
def test_comparison_tasks_identify_inspected_sources_and_preserve_navigation(
        contract_path, tmp_path, monkeypatch, capsys):
    data = load_contract(contract_path).model_dump()
    links = []
    for comparison in ("not_checked", "discrepancy", "consistent"):
        key = "reference_" + comparison
        data["evidence"].append({
            "id": key, "kind": "literature", "summary": "Source audit",
            "sources": [f"https://example.org/{key}.pdf"],
            "scope": "Synthetic equation convention.",
            "provenance": {"role": "primary", "inspection": "inspected",
                           "location": f"Fixture Eq. 8: {key}", "note": "Synthetic inspection."},
        })
        links.append({"evidence": key, "comparison": comparison,
                      "note": f"Recorded comparison of physical Z: {key}"})
    data["evidence"].append({
        "id": "review", "kind": "implementation", "summary": "Synthetic source review.",
        "sources": ["src/model.py"], "scope": "Synthetic equation convention.",
        "provenance": {"role": "implementation", "inspection": "inspected",
                       "location": "model.py:pressure", "note": "Synthetic review.", "derived_from": links},
    })
    path = tmp_path / "review with spaces.json"
    write_json(path, data)
    before = path.read_bytes()
    args = ["explain", str(path), "--evidence", "review"]
    assert main([*args, "--json"]) == 0
    report = capsys.readouterr().out
    item = json.loads(report)["contracts"][0]["items"][0]
    assert item["upstream_gaps"] == []  # Both sources are inspected; their comparisons are unresolved.
    targets = [target for step in item["suggested_steps"] for target in step["comparison_targets"]]
    assert [target["evidence"] for target in targets] == ["reference_not_checked", "reference_discrepancy"]
    assert item["comparisons"] == links
    for target in targets:
        key = target["evidence"]
        assert target["sources"] == [f"https://example.org/{key}.pdf"]
        assert target["location"] == f"Fixture Eq. 8: {key}"
        assert target["inspection"] == "inspected"
        assert target["note"] == f"Recorded comparison of physical Z: {key}"
    assert main([*args, "--json", "--lang", "ja"]) == 0
    assert capsys.readouterr().out == report

    monkeypatch.setenv("NO_COLOR", "1")
    for language, terminal in (("en", False), ("ja", False), ("ja", True)):
        monkeypatch.setattr(sys.stdout, "isatty", lambda: terminal)
        assert main([*args, "--lang", language]) == 0
        output = capsys.readouterr().out
        assert ("Comparison target" if language == "en" else "比較対象") in output
        assert "Source audit" in output  # Authored values remain untranslated.
        for target in targets:
            assert target["sources"][0] in output
            assert target["location"] in " ".join(output.split())
        commands = [line.split(": ", 1)[1] for line in output.splitlines() if ": mceg explain " in line]
        assert len(commands) == 2
        for next_command, target in zip(commands, targets):
            options = shlex.split(next_command)[1:]
            assert options[:4] == ["explain", str(path), "--evidence", target["evidence"]]
            assert options[4:] == (["--lang", "ja"] if language == "ja" else [])
            assert main(options) == 0
            assert target["sources"][0] in capsys.readouterr().out
    assert path.read_bytes() == before


def test_physical_unknown_requires_physical_evidence_and_explicit_claim_review(capsys):
    assert main(["explain", str(V02), "--claim", "physical_accuracy"]) == 0
    output = " ".join(capsys.readouterr().out.split())
    assert "independent measurements" in output
    assert "explicit Claim revision" in output
    assert "numerical solver agreement alone" in output
    assert main(["explain", str(V02), "--assessment", "imported:physical_accuracy", "--json"]) == 0
    item = json.loads(capsys.readouterr().out)["contracts"][0]["items"][0]
    assert item["record"]["status"] == "unknown"
    assert item["record"]["origin"] == "imported_v0.1_declaration"
    assert item["context"]["quantities"] == {}
    assert item["subject"]["id"] == "imported"


def test_check_hint_preserves_conditions_and_explain_proposes_actual_verification(example, monkeypatch, capsys):
    provider, _, review = example
    original = _curated.run
    monkeypatch.setattr(_curated, "run", lambda root, inputs: original(root, inputs, review))
    assert main(["check", str(provider), "-k", "curated", "--temperature", "1750"]) == 0
    output = capsys.readouterr().out
    assert "institutional library" not in output
    hint = next(line.removeprefix("Next steps: ") for line in output.splitlines() if line.startswith("Next steps:"))
    assert main(shlex.split(hint)[1:]) == 0
    detail = " ".join(capsys.readouterr().out.split())
    assert "temperature_K: 1750" in detail
    assert "Run the provider verification for the requested conditions and environment" in detail
    assert "UNKNOWN" in detail


def test_cross_contract_navigation_is_a_locator_not_support_inference(example, tmp_path, capsys):
    provider, _, review = example
    path = provider / json.loads(review.read_text())["contract"]["path"]
    data = load_contract(path).model_dump()
    data["evidence"][0]["sources"].append("mceg/contracts/linked.yaml")
    write_json(path, data)
    linked = path.parent / "linked.yaml"
    linked.write_bytes(H2.read_bytes())
    assert main(["explain", str(path), "--evidence", "verification", "--json"]) == 0
    item = json.loads(capsys.readouterr().out)["contracts"][0]["items"][0]
    assert any(str(linked) in c for c in item["next_commands"])
    assert item["issues"] == ["missing_provenance"]


def test_receiving_a_source_is_not_automatically_inspection(tmp_path, capsys):
    data = load_contract(H2).model_dump()
    evidence = next(e for e in data["evidence"] if e["id"] == "experimental_fit")
    evidence["sources"].append("local-authorized-copy.pdf")
    evidence["provenance"]["note"] = "A human supplied a copy; the required equations are not yet inspected."
    path = tmp_path / "received.yaml"
    write_json(path, data)
    assert main(["explain", str(path), "--evidence", "experimental_fit", "--json"]) == 0
    item = json.loads(capsys.readouterr().out)["contracts"][0]["items"][0]
    assert "source_not_fully_inspected" in item["issues"]
    assert item["suggested_steps"]


def test_selection_errors_and_empty_discovery_are_explicit(tmp_path, capsys):
    assert main(["explain", str(tmp_path), "--json"]) == 5
    assert json.loads(capsys.readouterr().out)["contracts"] == []
    with pytest.raises(SystemExit) as error:
        main(["explain", str(H2), "--evidence", "missing"])
    assert error.value.code == 2
    assert "ID not found" in capsys.readouterr().err


def test_invalid_structure_still_has_an_actionable_explanation(tmp_path, capsys):
    path = tmp_path / "broken.yaml"
    path.write_text('schema_version: "0.3"\n')
    assert main(["explain", str(path), "--json"]) == 0
    item = json.loads(capsys.readouterr().out)["contracts"][0]["items"][0]
    assert item["status"] == "FAIL"
    assert "Correct the field or local reference" in item["suggested_steps"][0]["action"]


@pytest.mark.parametrize("language", ["en", "ja"])
def test_plain_preserves_redirected_output_on_a_terminal(language, monkeypatch, capsys):
    args = ["explain", str(V02), "--evidence", "experimental_fit", "--lang", language]
    assert main(args) == 0
    redirected = capsys.readouterr().out
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setenv("TERM", "xterm")
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert main([*args, "--plain"]) == 0
    assert capsys.readouterr().out == redirected


def test_terminal_preserves_record_values_without_turning_a_historical_pass_into_support(tmp_path, monkeypatch, capsys):
    data = load_contract(V02).model_dump()
    evidence = next(e for e in data["evidence"] if e["id"] == "numerical_tests")
    assert evidence["result"] == "passed"
    evidence["summary"] = "Source audit"  # Matches a UI translation; authored text must stay original.
    path = tmp_path / "historical.json"
    write_json(path, data)
    before = path.read_bytes()
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setenv("TERM", "xterm")
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert main(["explain", str(path), "--evidence", "numerical_tests", "--lang", "ja"]) == 0
    text = capsys.readouterr().out
    assert "Source audit" in text and "passed" in text
    assert "PASS" not in text and "\033[1;32m" not in text
    assert path.read_bytes() == before


@pytest.mark.parametrize("command", [[], ["explain"]])
@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_shows_usage_and_examples_without_reading_contracts(command, flag, tmp_path, capsys):
    missing = str(tmp_path / "missing.yaml")
    with pytest.raises(SystemExit) as result:
        main([*command, missing, flag])
    assert result.value.code == 0
    captured = capsys.readouterr()
    assert "usage: mceg" in captured.out and "Examples:" in captured.out
    assert "--plain" in captured.out and not captured.err


def test_plain_and_json_are_mutually_exclusive(capsys):
    with pytest.raises(SystemExit) as error:
        main(["explain", str(V02), "--plain", "--json"])
    assert error.value.code == 2
    assert not capsys.readouterr().out
