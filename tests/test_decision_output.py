"""Decision output retains choices, their historical basis and separate unknowns."""

from copy import deepcopy
import importlib.util
import json
import subprocess
import sys

import pytest

from mceg import documentation as docs
from mceg.graph import build_graph
from mceg.schema_v04 import ContractV04, decision_basis_digest
from test_equation_schema import example_data as equation_data


def decision_data():
    data = equation_data()
    data["schema_version"] = "0.4"
    data["assessments"][0]["status"] = "unknown"
    data["assessments"][0]["reasons"] = ["Physical validation remains incomplete."]
    contract = ContractV04.model_validate(data)
    basis = [{"kind": kind, "id": key, "sha256": decision_basis_digest(contract, kind, key)}
             for kind, key in (("evidence", "derivation"), ("assessment", "formulation_review"))]
    old = {
        "id": "source_choice", "revision": "1", "question": "Which formulation should be used?",
        "scope": "Illustrative source choice only.",
        "options": [{"id": "old", "description": "Earlier formulation."},
                    {"id": "candidate", "description": "Reviewed candidate formulation."}],
        "selected": "old", "reasons": ["Retain the earlier formulation pending review."],
        "basis": basis, "limitations": ["No atmospheric accuracy is established."],
        "reconsider_when": ["Independent measurements become available."],
        "subject": "implementation", "context": "review",
    }
    new = deepcopy(old)
    new.update(revision="2", selected="candidate", reasons=["Use the candidate provisionally."],
               supersedes={"id": old["id"], "revision": old["revision"]})
    data["decisions"] = [old, new]
    return data


def write_contract(tmp_path, data):
    path = tmp_path / "decision.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_graph_retains_exact_choice_revisions_basis_and_supersession(tmp_path):
    data = decision_data()
    other = deepcopy(data["decisions"][0])
    other["id"] = "other_choice"
    data["decisions"].append(other)
    source = write_contract(tmp_path, data)
    before = source.read_bytes()
    report = build_graph(paths=[source], root=tmp_path)
    assert report == build_graph(paths=[source], root=tmp_path)
    nodes = {node["id"]: node for node in report["nodes"]}
    decisions = [node for node in nodes.values() if node["type"] == "decision"]
    options = [node for node in nodes.values() if node["type"] == "decision_option"]
    assert len(decisions) == 3 and len(options) == 6
    for node in decisions:
        edges = [edge for edge in report["edges"] if edge["source"] == node["id"]]
        selected = [edge for edge in edges if edge["type"] == "selects"]
        assert len(selected) == 1
        option = nodes[selected[0]["target"]]
        assert option["ref"]["id"] == node["record"]["selected"]
        assert option["ref"]["parent"] == {"id": node["ref"]["id"],
                                              "revision": node["ref"]["revision"]}
        pins = [edge for edge in edges if edge["type"] == "based_on"]
        assert {edge["data"]["sha256"] for edge in pins} == {
            pin["sha256"] for pin in node["record"]["basis"]}
    replacements = [edge for edge in report["edges"] if edge["type"] == "supersedes"]
    assert len(replacements) == 1
    assert nodes[replacements[0]["source"]]["ref"]["revision"] == "2"
    assert nodes[replacements[0]["target"]]["ref"]["revision"] == "1"
    assessment = next(node for node in nodes.values() if node["type"] == "assessment")
    assert assessment["record"]["status"] == "unknown"
    assert report["selections"] == []
    assert not {"supports", "current", "implements"} & {e["type"] for e in report["edges"]}
    assert source.read_bytes() == before


@pytest.mark.parametrize("changed", [False, True])
def test_docs_separate_choices_outcomes_and_stale_basis_without_rewriting(tmp_path, changed):
    data = decision_data()
    if changed:
        data["evidence"][0]["summary"] = "A newly revised evidence statement."
    source = write_contract(tmp_path, data)
    before = source.read_bytes()
    catalog = docs.build([{"provider": "fixture", "root": tmp_path, "paths": [source.name]}],
                         [], tmp_path / "generated", source_root=tmp_path)
    entry = catalog.entries[("fixture", source.name)]
    page = (catalog.output / (entry.page + "-decisions.rst")).read_text()
    for decision in entry.contract.decisions:
        assert f".. _{entry.anchor('decision', decision.id, decision.revision)}:" in page
        assert f"Recorded choice: **{decision.selected}**" in page
        for reason in decision.reasons:
            assert docs.text(reason) in page
        for pin in decision.basis:
            assert entry.link(pin.kind, pin.id) in page and pin.sha256 in page
    assert "unknown" in page and "no current choice is inferred" in (
        catalog.output / (entry.page + ".rst")).read_text()
    assert ("changed since recorded pin" if changed else "matches recorded pin") in page
    assert entry.link("decision", "source_choice", "1",
                      label="source_choice (revision 1)") in page
    assert "No atmospheric accuracy is established" in page
    assert "Independent measurements become available" in page
    assert source.read_bytes() == before


def test_docs_expose_empty_basis_as_unknown(tmp_path):
    data = decision_data()
    data["decisions"][0]["basis"] = []
    source = write_contract(tmp_path, data)
    catalog = docs.Catalog(tmp_path / "generated")
    entry = catalog.add("fixture", tmp_path, source.name)
    assert "No basis is recorded. Support for this choice remains unknown." in docs.decisions_page(entry)


@pytest.mark.skipif(importlib.util.find_spec("sphinx") is None, reason="Optional Sphinx is unavailable")
def test_decision_pages_build_with_resolved_revision_and_basis_links(tmp_path):
    source = write_contract(tmp_path, decision_data())
    docs.build([{"provider": "fixture", "root": tmp_path, "paths": [source.name]}],
               [], tmp_path / "generated", source_root=tmp_path)
    (tmp_path / "conf.py").write_text(
        "extensions = ['sphinx.ext.graphviz', 'sphinx.ext.mathjax']\n"
        "root_doc = 'index'\nexclude_patterns = ['html']\n", encoding="utf-8")
    (tmp_path / "index.rst").write_text(
        "Choices\n=======\n\n.. toctree::\n\n   generated/catalog\n", encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "sphinx", "-n", "-W", "-b", "html",
                             str(tmp_path), str(tmp_path / "html")],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    rendered = "\n".join(path.read_text() for path in (tmp_path / "html/generated").glob("*-decisions.html"))
    assert "source_choice (revision 1)" in rendered
    assert "source_choice (revision 2)" in rendered
    assert "unknown" in rendered
