"""Graph exports preserve recorded scope, identity and explicit selections."""

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from mceg import load_contract
from mceg.__main__ import main
from mceg.graph import build_graph
from mceg.validator import read_document
from test_catalog import catalog
from test_html_docs import case_copy
from test_investigation import investigation


ROOT = Path(__file__).resolve().parents[1]
H2 = "examples/v02/h2_solubility.yaml"


def records(graph, kind):
    return [n for n in graph["nodes"] if n["type"] == kind]


def node(graph, kind, key, revision=None):
    return next(n for n in records(graph, kind) if (n["ref"]["id"], n["ref"]["revision"]) == (key, revision))


def relations(graph, kind):
    lookup = {n["id"]: n for n in graph["nodes"]}
    return [(lookup[e["source"]], lookup[e["target"]], e) for e in graph["edges"] if e["type"] == kind]


def test_records_and_field_origins_preserve_scoped_judgments(investigation):
    path, _ = investigation
    before = path.read_bytes()
    contract = load_contract(path)
    result = build_graph(paths=[path.name], root=path.parent, provider="fixture")
    assert result["format"] == "mceg_graph_v1"
    assert result["selections"] == []
    for kind, items in (("claim", contract.claims), ("evidence", contract.evidence),
                        ("assessment", contract.assessments), ("subject", contract.subjects),
                        ("context", contract.contexts), ("follow_up", contract.follow_ups)):
        for item in items:
            revision = getattr(item, "revision", None) if kind == "claim" else None
            exported = node(result, kind, item.id, revision)
            assert exported["record"] == item.model_dump(mode="json")
    source = result["sources"][0]
    assert source["sha256"] == hashlib.sha256(before).hexdigest()
    data = json.loads(before)
    for edge in result["edges"]:
        assert edge["origin"]["source"] == source["id"]
        value = data
        for part in edge["origin"]["pointer"].strip("/").split("/"):
            key = part.replace("~1", "/").replace("~0", "~")
            value = value[int(key)] if isinstance(value, list) else value[key]
        assert value is not None
    judged = {(a["ref"]["id"], c["ref"]["id"], c["ref"]["revision"]) for a, c, _ in relations(result, "assesses")}
    assert ("old-choice", "choice", "1") in judged and ("new-choice", "choice", "2") in judged
    assert node(result, "evidence", "verification")["record"]["result"] == "passed"
    assert node(result, "assessment", "author-review")["record"]["status"] == "unknown"
    assert any(e["data"]["comparison"] == "discrepancy" for _, _, e in relations(result, "derived_from"))
    assert node(result, "resolution", "choose-coefficient")["record"]["note"]
    assert "supports" not in {e["type"] for e in result["edges"]}
    assert not (path.parent / "results/decision.json").exists()
    assert path.read_bytes() == before
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def test_completion_cycles_and_independent_record_namespaces(investigation):
    path, data = investigation
    data["follow_ups"].append({"id": "decision", "target_kind": "evidence", "target": "decision",
                               "action": "Retain the comparison.", "completion": "Link the comparison."})
    data["follow_up_resolutions"].append({"follow_up": "decision", "evidence": ["comparison"], "note": "Retained."})
    path.write_text(json.dumps(data))
    result = build_graph(paths=[path], root=path.parent)
    identifiers = [n["id"] for n in result["nodes"]]
    assert len(identifiers) == len(set(identifiers))
    assert len(relations(result, "resolves")) == 2
    assert node(result, "evidence", "decision")["id"] != node(result, "follow_up", "decision")["id"]
    assert result == build_graph(paths=[path, path], root=path.parent)


def test_identity_is_portable_snapshot_scoped_and_deterministic(tmp_path):
    a = tmp_path / "first"
    b = tmp_path / "second"
    a.mkdir()
    b.mkdir()
    for folder in (a, b):
        shutil.copyfile(ROOT / H2, folder / "contract.yaml")
    first = build_graph(paths=["contract.yaml"], root=a, provider="fixture")
    assert first == build_graph(paths=["contract.yaml"], root=b, provider="fixture")
    second_provider = build_graph(paths=["contract.yaml"], root=a, provider="other")
    assert {n["id"] for n in first["nodes"]}.isdisjoint(n["id"] for n in second_provider["nodes"])
    (b / "contract.yaml").write_bytes((b / "contract.yaml").read_bytes() + b"\n")
    revised = build_graph(paths=["contract.yaml"], root=b, provider="fixture")
    by_ref = lambda graph: {json.dumps(n["ref"], sort_keys=True): n["id"] for n in graph["nodes"]}
    old, new = by_ref(first), by_ref(revised)
    assert old.keys() == new.keys()
    assert set(old.values()).isdisjoint(new.values())
    shutil.copyfile(a / "contract.yaml", a / "other.yaml")
    together = build_graph(paths=["contract.yaml", "other.yaml"], root=a)
    assert together == build_graph(paths=["other.yaml", "contract.yaml"], root=a)
    assert len(together["nodes"]) == 2 * len(first["nodes"])


def test_v01_is_not_migrated_or_promoted():
    result = build_graph(paths=["contracts/h2_solubility.yaml"], root=ROOT)
    original = load_contract(ROOT / "contracts/h2_solubility.yaml")
    assert not records(result, "assessment")
    assert not records(result, "resolution")
    for claim in original.claims:
        assert node(result, "claim", claim.id)["record"] == claim.model_dump(mode="json")
    assert relations(result, "uses_evidence")
    assert not relations(result, "assesses")


def test_conditions_keep_sample_contexts_nested(tmp_path):
    data = read_document(ROOT / H2)
    condition = {"id": "samples", "revision": "1", "kind": "samples",
                 "samples": [{"id": data["contexts"][0]["id"], "scope": "Synthetic sample.",
                              "settings": {"mode": "synthetic"}}],
                 "scope": "Synthetic samples only.", "evidence": [data["evidence"][0]["id"]]}
    data["conditions"].extend([condition, {**copy.deepcopy(condition), "revision": "2"}])
    path = tmp_path / "samples.json"
    path.write_text(json.dumps(data))
    contract = load_contract(path)
    result = build_graph(paths=[path], root=tmp_path)
    assert len(records(result, "context")) == len(contract.contexts)
    for condition in contract.conditions:
        assert node(result, "condition", condition.id, condition.revision)["record"] == condition.model_dump(mode="json")
    for a, condition, _ in relations(result, "assesses"):
        if a["record"]["kind"] != "evidence_support":
            assert condition["ref"]["revision"] == a["record"]["condition_revision"]


def test_cases_keep_manual_judgments_and_connection_meaning():
    result = build_graph(cases=["examples/html/case.yaml"], root=ROOT, provider="mceg")
    assert len(records(result, "model")) == 2
    assert len(records(result, "manual_assessment")) == 9
    assert not records(result, "assessment")
    consumer, dependency, edge = relations(result, "requires")[0]
    assert (consumer["ref"]["id"], dependency["ref"]["id"]) == ("solubility", "eos")
    assert edge["data"]["quantity"] == "hydrogen_fugacity"
    assert "bar to Pa" in edge["data"]["description"]
    assert all(s["assessments"] == [] for s in result["selections"])
    assert node(result, "manual_assessment", "combined_accuracy")["record"]["classification"] == "unknown"


def test_case_components_preserve_separate_selections_and_multiple_edges(case_copy):
    data, path, _ = case_copy
    data.pop("legacy_case")
    data.pop("highlights")
    contract = load_contract(ROOT / H2)
    source = path.parent / "modern.yaml"
    source.write_bytes((ROOT / H2).read_bytes())
    first = contract.assessments[0]
    component = {"provider": "mceg", "model_id": contract.model.id, "path": "modern.yaml",
                 "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                 "subject": first.subject, "context": first.context, "assessments": [first.id]}
    data["components"] = {"selected": component, "unselected": {**component, "assessments": []},
                          "missing/~": {"provider": "mceg", "model_id": "unregistered"}}
    data["connections"] = [{"consumer": "selected", "dependency": "unselected", "quantity": q,
                            "description": "Synthetic recorded connection."} for q in ("pressure", "fugacity")]
    path.write_text(json.dumps(data))
    result = build_graph(cases=[path], root=path.parent)
    assert len(records(result, "model")) == 1
    assert len(records(result, "assessment")) == len(contract.assessments)
    assert len(relations(result, "requires")) == 2
    lookup = {n["id"]: n for n in result["nodes"]}
    selections = {lookup[s["component"]]["ref"]["id"]: s for s in result["selections"]}
    assert len(selections["selected"]["assessments"]) == 1
    assert selections["unselected"]["assessments"] == []
    assert selections["missing/~"]["model"] is None
    assert selections["missing/~"]["registration"] == "unregistered"
    assert selections["missing/~"]["origin"]["pointer"] == "/components/missing~1~0"
    data["components"]["selected"]["context"] = "missing"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Unknown subject/context"):
        build_graph(cases=[path], root=path.parent)


@pytest.mark.parametrize("field,value,reason", [("sha256", "0" * 64, "hash mismatch"),
                                                ("model_id", "wrong", "Model ID mismatch")])
def test_case_pin_validation_is_shared(case_copy, field, value, reason):
    data, path, _ = case_copy
    data["components"]["eos"][field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=reason):
        build_graph(cases=[path], root=path.parent)


def test_catalog_retains_history_and_per_record_selections(catalog):
    path, data = catalog
    first = data["models"][0]["records"][0]
    data["models"][0]["records"].append({**first, "id": "second", "assessments": []})
    path.write_text(json.dumps(data))
    result = build_graph(catalog=path)
    assert len(records(result, "model")) == 1
    assert len(records(result, "assessment")) > len(first["assessments"])
    selected = {s["record"]["id"]: s for s in result["selections"]}
    assert len(selected["study"]["assessments"]) == 2
    assert selected["second"]["assessments"] == []
    assert selected["study"]["catalog_model"]["identity"] == data["models"][0]["identity"]
    (path.parent / "summary.json").write_text("changed")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        build_graph(catalog=path)


def test_package_reads_metadata_without_importing_provider(catalog, monkeypatch):
    path, data = catalog
    site = path.parents[3]
    (site / "fixture_provider/__init__.py").write_text("raise RuntimeError('Must not be imported')\n")
    metadata = site / "fixture_provider-1.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Metadata-Version: 2.1\nName: fixture-provider\nVersion: 1.0\n")
    (metadata / "RECORD").write_text("fixture_provider/data/mceg/index.json,,\n")
    monkeypatch.syspath_prepend(str(site))
    result = build_graph(package="fixture-provider")
    source = next(s for s in result["sources"] if s["kind"] == "catalog")
    assert source["distribution"] == {"name": "fixture-provider", "version": "1.0"}
    assert "fixture_provider" not in sys.modules
    data["provider"] = "another"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="does not match"):
        build_graph(package="fixture-provider")


def test_core_has_no_documentation_or_provider_imports():
    script = '''
import sys
from importlib.abc import MetaPathFinder
class Blocked(MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname in {"mceg.documentation", "mceg.explain", "mceg.investigation"} or fullname.split(".")[0] in {"sphinx", "myst_parser", "exoeos", "exogibbs", "jax", "networkx"}:
            raise ImportError(fullname)
sys.meta_path.insert(0, Blocked())
from mceg.graph import build_graph
assert build_graph(cases=["examples/html/case.yaml"])["nodes"]
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_cli_is_json_only_and_does_not_emit_partial_results(tmp_path, capsys):
    assert main(["graph", H2, "--root", str(ROOT)]) == 0
    output = capsys.readouterr()
    assert not output.err
    assert json.loads(output.out) == build_graph(paths=[H2], root=ROOT)
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema_version: invalid\n")
    with pytest.raises(SystemExit) as exc:
        main(["graph", str(ROOT / H2), str(bad), "--root", "/"])
    assert exc.value.code == 1
    output = capsys.readouterr()
    assert not output.out and "mceg graph:" in output.err


@pytest.mark.parametrize("options", [{}, {"paths": H2}, {"cases": "case.yaml"},
    {"package": "missing", "catalog": "index.json"}, {"package": "missing", "paths": [H2]},
    {"catalog": "index.json", "cases": ["case.yaml"]}, {"catalog": "index.json", "root": "/tmp"},
    {"catalog": "index.json", "provider": "ignored"}, {"paths": ["../outside.yaml"]},
    {"paths": [H2], "provider": ""}])
def test_invalid_input_modes_are_rejected(options):
    with pytest.raises(ValueError):
        build_graph(**options)


def test_local_sources_reject_symlinks_and_unknown_references(tmp_path):
    (tmp_path / "link.yaml").symlink_to(ROOT / H2)
    with pytest.raises(ValueError, match="Symlinks"):
        build_graph(paths=["link.yaml"], root=tmp_path)
    data = read_document(ROOT / H2)
    data["assessments"][0]["evidence"].append("missing")
    (tmp_path / "invalid.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Unknown evidence"):
        build_graph(paths=["invalid.json"], root=tmp_path)


def test_manual_evidence_can_reference_an_explicit_contract_outside_components(case_copy):
    data, path, _ = case_copy
    extra = path.parent / "extra.yaml"
    extra.write_bytes((ROOT / "contracts/ideal_gas.yaml").read_bytes())
    contract = load_contract(extra)
    legacy_path = path.parent / data["legacy_case"]["path"]
    legacy = read_document(legacy_path)
    legacy["assessments"][0]["evidence"].append("extra.yaml#" + contract.evidence[0].id)
    legacy_path.write_text(json.dumps(legacy))
    data["legacy_case"]["sha256"] = hashlib.sha256(legacy_path.read_bytes()).hexdigest()
    path.write_text(json.dumps(data))
    result = build_graph(paths=[extra], cases=[path], provider="mceg", root=path.parent)
    assert any(a["type"] == "manual_assessment" and e["ref"]["path"] == "extra.yaml"
               for a, e, _ in relations(result, "uses_evidence"))


def test_documentation_and_json_share_evidence_edges(tmp_path):
    from mceg import documentation as docs

    entry = docs.Catalog(tmp_path / "generated").add("mceg", ROOT, H2)
    result = build_graph(paths=[H2], provider="mceg", root=ROOT)
    rendered = docs.evidence_index(entry)
    for start, end, edge in relations(result, "derived_from"):
        assert f'{json.dumps(start["id"])} -> {json.dumps(end["id"])}' in rendered
        assert f'label={json.dumps(edge["data"]["comparison"])}' in rendered
    for item in records(result, "evidence"):
        assert entry.svg_link("evidence", item["ref"]["id"]) in rendered


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_legacy_nonfinite_values_are_not_json_payloads(case_copy, value):
    data, path, _ = case_copy
    legacy_path = path.parent / data["legacy_case"]["path"]
    legacy = read_document(legacy_path)
    legacy["inputs"]["temperature_K"] = value
    legacy_path.write_text(json.dumps(legacy))
    data["legacy_case"]["sha256"] = hashlib.sha256(legacy_path.read_bytes()).hexdigest()
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="JSON compliant"):
        build_graph(cases=[path], root=path.parent)
