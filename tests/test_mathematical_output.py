"""Mathematical views retain explicit identity and do not infer computation."""

import copy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from mceg.__main__ import main as cli
from mceg.mathematical import main, model_graph, render_mermaid, render_model_tex
from mceg.schema_v05 import ContractV05, mathematical_model_digest
from mceg.validator import load_contract, read_document


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/mathematical_models/isothermal.yaml"


def example_data():
    return read_document(EXAMPLE)


def write_contract(tmp_path, data=None):
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(example_data() if data is None else data), encoding="utf-8")
    return path


def test_incidence_reuses_shared_quantities_and_preserves_a_physical_cycle():
    contract = load_contract(EXAMPLE)
    graph = model_graph(contract, "atmosphere")
    assert graph["directed"] is False
    assert graph["sha256"] == mathematical_model_digest(contract, "atmosphere", "1")
    nodes = {node["id"]: node for node in graph["nodes"]}
    assert len(nodes) == 12
    assert len(graph["edges"]) == 14
    assert {edge["relation"] for edge in graph["edges"]
            if edge["quantity"] == "quantity:pressure"} == {
                "relation:eos", "relation:balance", "relation:pressure_boundary"}
    # eos -- P -- balance -- rho -- eos is a valid incidence cycle.
    for relation in ("eos", "balance"):
        assert {"quantity:pressure", "quantity:density"} <= {
            edge["quantity"] for edge in graph["edges"] if edge["relation"] == "relation:" + relation}
    assert not any("status" in node for node in nodes.values())
    mermaid = render_mermaid(graph)
    assert " --> " not in mermaid and mermaid.count(" ---|") == 14


def test_same_symbol_and_unit_do_not_merge_distinct_pressure_quantities():
    data = example_data()
    total = copy.deepcopy(next(item for item in data["quantities"] if item["id"] == "atmosphere.gas_pressure"))
    total["id"] = "atmosphere.total_pressure"
    total["description"] = "Total pressure including radiation pressure."
    data["quantities"].append(total)
    model = data["mathematical_models"][0]
    model["quantities"]["total_pressure"] = {
        "quantity": {"id": total["id"], "revision": "1"}, "role": "unknown"}
    model["relations"][1]["quantities"]["P"] = "total_pressure"
    graph = model_graph(ContractV05.model_validate(data), "atmosphere")
    pressure_edges = {edge["relation"]: edge["quantity"] for edge in graph["edges"] if edge["symbol"] == "P"}
    assert pressure_edges["relation:eos"] == "quantity:pressure"
    assert pressure_edges["relation:balance"] == "quantity:total_pressure"
    assert len([node for node in graph["nodes"] if node["type"] == "quantity"]) == 9


def test_reused_relation_is_two_instances_with_distinct_tex_labels():
    data = example_data()
    relation = copy.deepcopy(data["mathematical_models"][0]["relations"][0])
    relation["id"] = "second_eos"
    data["mathematical_models"][0]["relations"].append(relation)
    contract = ContractV05.model_validate(data)
    graph = model_graph(contract, "atmosphere")
    instances = [node for node in graph["nodes"] if node["type"] == "relation" and node["equation"]["id"] == "ideal_gas"]
    assert {node["instance"] for node in instances} == {"eos", "second_eos"}
    rendered = render_model_tex(contract, "atmosphere")
    labels = [line for line in rendered.splitlines() if line.startswith(r"\label{")]
    assert len(labels) == len(set(labels)) == 5


def test_selected_model_keeps_scope_quantity_meanings_and_adopted_math_only():
    contract = load_contract(EXAMPLE)
    rendered = render_model_tex(contract, "atmosphere")
    assert "excluding radiation pressure" in rendered
    assert "coordinates:" in rendered and "atmosphere.height (1)" in rendered
    assert "Role: unknown; unit: Pa" in rendered
    assert r"P(0)=P_0" in rendered
    assert r"z \textgreater{}= 0" in rendered
    assert r"\mapsto" in rendered
    # The implementation's analytic expression is separately recorded, not adopted.
    assert "analytic_pressure" not in rendered


def test_no_silent_revision_selection(tmp_path, capsys):
    data = example_data()
    second = copy.deepcopy(data["mathematical_models"][0])
    second["revision"] = "2"
    second["scope"] = "A separately authored revision."
    data["mathematical_models"].append(second)
    path = write_contract(tmp_path, data)
    assert main([str(path), "--model", "atmosphere"]) == 1
    assert "Ambiguous" in capsys.readouterr().err
    assert main([str(path), "--model", "atmosphere", "--revision", "2"]) == 0
    assert json.loads(capsys.readouterr().out)["model"]["revision"] == "2"
    assert main([str(path), "--model", "missing"]) == 1
    assert main([str(ROOT / "examples/equations/continuity.yaml"), "--model", "atmosphere"]) == 1


@pytest.mark.parametrize("format", ["json", "mermaid", "tex"])
def test_cli_exports_and_checks_without_rewriting_contract_or_stale_output(tmp_path, capsys, format):
    path = write_contract(tmp_path)
    original = path.read_bytes()
    output = tmp_path / "generated" / ("model." + format)
    args = [str(path), "--model", "atmosphere", "--format", format, "--output", str(output)]
    assert cli(["model", *args, "--check"]) == 1
    assert not output.parent.exists()
    assert cli(["model", *args]) == 0
    expected = output.read_bytes()
    assert main([*args, "--check"]) == 0
    assert "generated bytes only; no scientific assessment" in capsys.readouterr().out
    output.write_bytes(expected + b"\nmanual edit\n")
    assert main([*args, "--check"]) == 1
    assert output.read_bytes() == expected + b"\nmanual edit\n"
    assert path.read_bytes() == original


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_cli_does_not_overwrite_input_aliases(tmp_path, alias):
    path = write_contract(tmp_path)
    output = path if alias == "same" else tmp_path / "output"
    if alias == "symlink":
        output.symlink_to(path)
    elif alias == "hardlink":
        output.hardlink_to(path)
    before = path.read_bytes()
    assert main([str(path), "--model", "atmosphere", "--output", str(output)]) == 1
    assert path.read_bytes() == before


def test_mermaid_escapes_labels_and_tex_escapes_prose():
    data = example_data()
    relation = data["mathematical_models"][0]["relations"][0]
    relation["role"] = 'A "quoted" <label> & #tag with 50% and \\input{secret}'
    contract = ContractV05.model_validate(data)
    rendered = render_mermaid(model_graph(contract, "atmosphere"))
    assert '#34;quoted#34;' in rendered and '#60;label#62;' in rendered
    assert '#92;input' in rendered
    assert '"quoted"' not in rendered
    tex = render_model_tex(contract, "atmosphere")
    assert r"50\%" in tex and r"\input{secret}" not in tex
    assert r"\textbackslash{}input\{secret\}" in tex


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="Optional TeX compiler unavailable")
def test_model_fragment_compiles_in_a_provider_document(tmp_path):
    (tmp_path / "model_definition.tex").write_text(
        render_model_tex(load_contract(EXAMPLE), "atmosphere"), encoding="utf-8")
    shutil.copyfile(EXAMPLE.with_name("model.tex"), tmp_path / "model.tex")
    result = subprocess.run(
        ["pdflatex", "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "model.tex"],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout
    assert (tmp_path / "model.pdf").is_file()
