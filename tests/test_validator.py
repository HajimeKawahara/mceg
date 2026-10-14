"""Structural errors must not silently become scientific evidence."""

from pathlib import Path
import copy
import json

import pytest
import yaml
from pydantic import ValidationError

from mceg import Contract, load_contract, trace_provenance
from mceg.__main__ import main


CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


@pytest.fixture
def document():
    return {
        "schema_version": "0.1",
        "model": {
            "id": "example.diffusion",
            "name": "Diffusion model",
            "description": "A non-EOS schema fixture, not a scientific contract.",
            "implementation": {
                "repository": "https://example.org/diffusion",
                "revision": "fixture-revision",
                "entry_points": ["solver.py:solve"],
            },
        },
        "assumptions": [],
        "domains": [{
            "kind": "scientific_applicability",
            "status": "unknown",
            "description": "No physical applicability evidence supplied.",
            "conditions": [],
            "evidence": ["source"],
        }],
        "claims": [{
            "id": "accuracy",
            "statement": "Accuracy against measurement is unknown.",
            "kind": "physical_validation",
            "status": "unknown",
            "scope": "No measurements supplied.",
            "evidence": [],
        }],
        "evidence": [{
            "id": "source",
            "kind": "implementation",
            "summary": "A fixture locator, never executed or fetched.",
            "sources": ["solver.py"],
            "scope": "Schema testing only.",
        }],
        "limitations": [],
    }


def test_all_example_contracts_load():
    paths = sorted(CONTRACTS.glob("*.yaml"))
    assert {path.name for path in paths} == {
        "ideal_gas.yaml", "second_virial.yaml", "peng_robinson.yaml",
        "zhang_duan_h2.yaml", "h2_solubility.yaml",
    }
    for path in paths:
        contract = load_contract(path)
        assert contract.schema_version == "0.1"


def test_non_eos_contract_can_record_unknown(document):
    contract = Contract.model_validate(document)
    assert contract.claims[0].status == "unknown"
    assert contract.claims[0].evidence == []


@pytest.mark.parametrize("kind,evidence_kind,result", [
    ("theoretical", "theory", None),
    ("numerical_verification", "numerical_test", "passed"),
    ("numerical_verification", "benchmark", "passed"),
    ("physical_validation", "experiment", None),
    ("physical_validation", "observation", None),
])
def test_supported_claim_requires_matching_evidence(document, kind, evidence_kind, result):
    document["claims"][0].update(kind=kind, status="supported", evidence=["source"])
    document["evidence"][0].update(kind=evidence_kind, result=result)
    Contract.model_validate(document)


@pytest.mark.parametrize("kind,evidence_kind,result", [
    ("theoretical", "implementation", None),
    ("numerical_verification", "numerical_test", "not_run"),
    ("numerical_verification", "numerical_test", "unknown"),
    ("numerical_verification", "numerical_test", "failed"),
    ("physical_validation", "numerical_test", "passed"),
    ("physical_validation", "literature", None),
])
def test_wrong_evidence_cannot_promote_a_claim(document, kind, evidence_kind, result):
    document["claims"][0].update(kind=kind, status="supported", evidence=["source"])
    document["evidence"][0].update(kind=evidence_kind, result=result)
    with pytest.raises(ValidationError, match="lacks matching evidence"):
        Contract.model_validate(document)


@pytest.mark.parametrize("section", ["assumptions", "domains", "claims", "limitations"])
def test_dangling_evidence_links_are_rejected(document, section):
    if section in {"assumptions", "limitations"}:
        document[section] = [{"statement": "Example", "evidence": ["missing"]}]
    else:
        document[section][0]["evidence"] = ["missing"]
    with pytest.raises(ValidationError, match="Unknown evidence"):
        Contract.model_validate(document)


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(schema_version="0.2"),
    lambda d: d.update(schema_version=0.1),
    lambda d: d.pop("assumptions"),
    lambda d: d["model"].update(typo="unrecognized"),
    lambda d: d["model"].update(id="  "),
    lambda d: d["model"].update(name=True),
    lambda d: d["evidence"].append(d["evidence"][0].copy()),
    lambda d: d["claims"][0].update(id="source"),
    lambda d: d["claims"][0].update(status="supported"),
    lambda d: d["domains"][0].update(status="documented"),
    lambda d: d["domains"][0].update(conditions=["T > 0"]),
    lambda d: d["evidence"][0].update(kind="numerical_test"),
    lambda d: d["evidence"][0].update(result="passed"),
])
def test_malformed_records_are_rejected(document, mutation):
    mutation(document)
    with pytest.raises(ValidationError):
        Contract.model_validate(document)


@pytest.mark.parametrize("content", [
    "schema_version: '0.1'\nschema_version: '0.2'\n",
    "model:\n  id: first\n  id: second\n",
    "!!python/object/apply:builtins.print ['must not run']",
    "schema_version: [unterminated",
    "---\n{}\n---\n{}\n",
    "? [unhashable, key]\n: value\n",
])
def test_ambiguous_or_unsafe_yaml_is_rejected(tmp_path, content):
    path = tmp_path / "bad.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        load_contract(path)


def test_cli_reports_each_file_and_returns_failure(tmp_path, capsys):
    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    missing = tmp_path / "missing.yaml"
    valid = CONTRACTS / "ideal_gas.yaml"
    assert main([str(empty), str(missing), str(valid)]) == 1
    captured = capsys.readouterr()
    assert "VALID" in captured.out and "structure only" in captured.out
    assert captured.err.count("INVALID") == 2
    assert "Traceback" not in captured.err
    assert main([str(valid)]) == 0


@pytest.fixture
def source_chain(document):
    """Synthetic ancestry only; these records are not scientific evidence."""
    for key, role, parent in (("source", "implementation", "secondary"),
                              ("secondary", "secondary", "primary"),
                              ("primary", "primary", None)):
        item = copy.deepcopy(document["evidence"][0])
        item.update(id=key, kind="literature")
        item["provenance"] = {
            "role": role, "location": f"Fixture passage: {key}",
            "inspection": "inspected", "note": "Synthetic review record.",
            "derived_from": [] if parent is None else [{
                "evidence": parent, "comparison": "consistent",
                "note": "Fixture value, unit, and scope were compared.",
            }],
        }
        if key == "source":
            document["evidence"][0] = item
        else:
            document["evidence"].append(item)
    return document


def test_trace_follows_sources_without_promoting_physical_claim(source_chain):
    contract = Contract.model_validate(source_chain)
    report = trace_provenance(contract, "source")
    assert [item["id"] for item in report["nodes"]] == ["source", "secondary", "primary"]
    assert report["primary_sources"] == ["primary"]
    assert report["recorded_audit_complete"]
    assert report["issues"] == []
    assert contract.claims[0].status == "unknown"


@pytest.mark.parametrize("inspection", ["partial", "not_inspected"])
def test_identified_primary_is_not_a_completed_audit(source_chain, inspection):
    source_chain["evidence"][2]["provenance"]["inspection"] = inspection
    source_chain["evidence"][1]["provenance"]["derived_from"][0]["comparison"] = "not_checked"
    report = trace_provenance(Contract.model_validate(source_chain), "source")
    assert report["primary_sources"] == ["primary"]
    assert not report["recorded_audit_complete"]
    assert {issue["issue"] for issue in report["issues"]} == {
        "comparison_not_checked", "source_not_fully_inspected",
    }


@pytest.mark.parametrize("note", [
    "Synthetic transcription discrepancy: primary 600 K, secondary 6000 K.",
    "Synthetic scope discrepancy: a pure-species range was assigned to a mixture.",
])
def test_recorded_discrepancies_remain_data_and_are_reported(source_chain, note):
    link = source_chain["evidence"][1]["provenance"]["derived_from"][0]
    link.update(comparison="discrepancy", note=note)
    report = trace_provenance(Contract.model_validate(source_chain), "source")
    assert not report["recorded_audit_complete"]
    assert report["issues"] == [{"evidence": "secondary", "upstream": "primary",
                                 "issue": "comparison_discrepancy"}]
    assert report["links"][1]["note"] == note


@pytest.mark.parametrize("target,pattern", [
    ("missing", "Unknown provenance"),
    ("source", "cycle"),
    ("secondary", "cycle"),
])
def test_bad_ancestry_references_are_rejected(source_chain, target, pattern):
    source_chain["evidence"][1]["provenance"]["derived_from"][0]["evidence"] = target
    with pytest.raises(ValidationError, match=pattern):
        Contract.model_validate(source_chain)


def test_duplicate_source_links_are_rejected(source_chain):
    links = source_chain["evidence"][0]["provenance"]["derived_from"]
    links.append(links[0].copy())
    with pytest.raises(ValidationError, match="Duplicate provenance"):
        Contract.model_validate(source_chain)


@pytest.mark.parametrize("index,inspection", [(0, "partial"), (1, "not_inspected"), (2, None)])
def test_comparison_cannot_be_recorded_without_inspecting_both_sources(source_chain, index, inspection):
    if inspection is None:
        source_chain["evidence"][index].pop("provenance")
    else:
        source_chain["evidence"][index]["provenance"]["inspection"] = inspection
    with pytest.raises(ValidationError, match="both sources to be inspected"):
        Contract.model_validate(source_chain)


def test_a_primary_branch_does_not_hide_an_unresolved_branch(source_chain):
    unresolved = copy.deepcopy(source_chain["evidence"][2])
    unresolved.update(id="unresolved")
    unresolved["provenance"].update(role="unknown", inspection="partial")
    source_chain["evidence"].append(unresolved)
    source_chain["evidence"][0]["provenance"]["derived_from"].append({
        "evidence": "unresolved", "comparison": "not_checked", "note": "Origin not established.",
    })
    report = trace_provenance(Contract.model_validate(source_chain), "source")
    assert report["primary_sources"] == ["primary"]
    assert not report["recorded_audit_complete"]
    assert {item["issue"] for item in report["issues"]} >= {
        "unknown_source_role", "primary_source_not_identified",
    }


def test_shared_primary_is_reported_once(source_chain):
    source_chain["evidence"][0]["provenance"]["derived_from"].append({
        "evidence": "primary", "comparison": "consistent", "note": "Also compared directly.",
    })
    report = trace_provenance(Contract.model_validate(source_chain), "source")
    assert len(report["nodes"]) == 3
    assert len(report["links"]) == 3
    assert report["primary_sources"] == ["primary"]


def test_secondary_leaf_and_missing_provenance_are_not_treated_as_primary(source_chain):
    source_chain["evidence"][1]["provenance"]["derived_from"] = []
    report = trace_provenance(Contract.model_validate(source_chain), "source")
    assert not report["recorded_audit_complete"]
    assert report["primary_sources"] == []
    legacy = load_contract(CONTRACTS / "ideal_gas.yaml")
    report = trace_provenance(legacy, legacy.evidence[0].id)
    assert report["issues"][0]["issue"] == "missing_provenance"


def test_h2_secondary_temperature_retains_unchecked_original():
    report = trace_provenance(load_contract(CONTRACTS / "h2_solubility.yaml"), "formulation_temperature")
    assert report["primary_sources"] == ["experimental_temperature"]
    assert not report["recorded_audit_complete"]
    assert report["links"][0]["comparison"] == "not_checked"
    assert report["nodes"][1]["provenance"]["inspection"] == "not_inspected"


def test_h2_inspected_pressure_does_not_complete_other_facts_or_validate_model():
    contract = load_contract(CONTRACTS / "h2_solubility.yaml")
    pressure = trace_provenance(contract, "metadata_pressure")
    assert pressure["recorded_audit_complete"]
    assert pressure["primary_sources"] == ["experimental_pressure"]
    assert pressure["issues"] == []
    assert not trace_provenance(contract, "formulation_temperature")["recorded_audit_complete"]
    assert next(claim for claim in contract.claims if claim.id == "physical_accuracy").status == "unknown"


def test_h2_actual_source_difference_and_uninspected_original_are_both_visible():
    report = trace_provenance(load_contract(CONTRACTS / "h2_solubility.yaml"), "metadata_temperature")
    assert not report["recorded_audit_complete"]
    assert {issue["issue"] for issue in report["issues"]} == {
        "comparison_discrepancy", "comparison_not_checked", "source_not_fully_inspected",
    }
    assert [link["comparison"] for link in report["links"]] == ["discrepancy", "not_checked"]


def test_h2_matching_formula_does_not_hide_uninspected_empirical_fit():
    report = trace_provenance(load_contract(CONTRACTS / "h2_solubility.yaml"), "implementation")
    assert [node["id"] for node in report["nodes"]] == ["implementation", "formulation", "experimental_fit"]
    assert [link["comparison"] for link in report["links"]] == ["consistent", "not_checked"]
    assert not report["recorded_audit_complete"]


def test_h2_new_measurement_does_not_verify_reported_older_calibration():
    contract = load_contract(CONTRACTS / "h2_solubility.yaml")
    new_measurement = trace_provenance(contract, "infrared_recalibration")
    historical = trace_provenance(contract, "historical_calibration")
    assert new_measurement["primary_sources"] == ["infrared_recalibration"]
    assert historical["primary_sources"] == []
    assert not historical["recorded_audit_complete"]
    assert {issue["issue"] for issue in historical["issues"]} >= {
        "comparison_not_checked", "unknown_source_role", "source_not_fully_inspected",
    }


def test_cli_trace_reports_gaps_as_json_and_rejects_unknown_id(capsys):
    path = str(CONTRACTS / "h2_solubility.yaml")
    assert main(["--trace", "formulation_temperature", path]) == 0
    report = json.loads(capsys.readouterr().out)
    assert not report["recorded_audit_complete"]
    assert main(["--trace", "missing", path]) == 1
    assert "Unknown evidence ID" in capsys.readouterr().err
