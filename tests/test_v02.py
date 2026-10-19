"""Version dispatch, historical identity, and limited automatic assessment."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import runpy

import pytest
from pydantic import ValidationError

from mceg import (Contract, ContractV02, assess_conditions, load_contract,
                  migrate_contract, restore_v01, trace_provenance)
from mceg.__main__ import main
from mceg.assessment import compare_condition
from mceg.schema_v02 import Context, RangeCondition, SampleCondition
from mceg.validator import read_document


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/v02/h2_solubility.yaml"


@pytest.mark.parametrize("path", sorted((ROOT / "contracts").glob("*.yaml")))
def test_lossless_migration_of_all_baseline_models(path, tmp_path):
    before = path.read_bytes()
    old = load_contract(path)
    new = migrate_contract(path)
    assert isinstance(old, Contract) and isinstance(new, ContractV02)
    assert new.migration.source_sha256 == hashlib.sha256(before).hexdigest()
    assert all("status" not in c.model_dump() and "evidence" not in c.model_dump() for c in new.claims)
    assert all(a.origin == "imported_v0.1_declaration" for a in new.assessments)
    assert all(not c.quantities and not c.settings for c in new.contexts)
    assert restore_v01(new).model_dump() == old.model_dump()
    assert path.read_bytes() == before
    output = tmp_path / "new.json"
    output.write_text(new.model_dump_json())
    assert load_contract(output) == new
    with pytest.raises(ValidationError):
        Contract.model_validate(new.model_dump())
    for evidence in old.evidence:
        old_trace = trace_provenance(old, evidence.id)
        new_trace = trace_provenance(new, evidence.id)
        assert old_trace["issues"] == new_trace["issues"]
        assert old_trace["recorded_audit_complete"] == new_trace["recorded_audit_complete"]


def test_new_example_preserves_both_source_intervals_without_promoting_support():
    contract = load_contract(EXAMPLE)
    outcomes = {a.condition: a.classification for a in contract.assessments if a.kind == "range_membership"}
    assert outcomes == {"temperature_metadata": "within_reported_range", "temperature_seo": "outside_reported_range",
                        "pressure_hirschmann_abstract": "within_reported_range"}
    physical = next(a for a in contract.assessments if a.kind == "evidence_support" and a.claim == "physical_accuracy")
    assert physical.status == "unknown"
    assert restore_v01(contract) == load_contract(ROOT / "contracts/h2_solubility.yaml")
    assert runpy.run_path(str(ROOT / "examples/v02/build.py"))["build"]() == contract


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(schema_version="0.3"),
    lambda d: d["claims"][0].update(status="supported"),
    lambda d: d["claims"][0].update(evidence=["equations"]),
    lambda d: d["claims"].append(deepcopy(d["claims"][0])),
    lambda d: d["subjects"].append(deepcopy(d["subjects"][0])),
    lambda d: d["contexts"].append(deepcopy(d["contexts"][0])),
    lambda d: d["assessments"][0].update(claim_revision="missing"),
    lambda d: d["assessments"][0].update(subject="missing"),
    lambda d: d["assessments"][0].update(context="missing"),
    lambda d: d["assessments"][0].update(evidence=[]),
    lambda d: d["assessments"][-1].update(condition_revision="missing"),
    lambda d: d["assessments"][-1].update(evidence=[]),
    lambda d: d["evidence"][0].update(subject="missing"),
    lambda d: d["follow_ups"][0].update(target="missing"),
    lambda d: d["follow_ups"][-1].update(revision="missing"),
    lambda d: d["conditions"][0]["interval"].update(upper=1000),
    lambda d: d["conditions"][0]["interval"].update(unit="bar"),
    lambda d: d["conditions"][0]["interval"].update(upper=float("inf")),
    lambda d: d["contexts"][-1]["quantities"]["temperature"].update(value=True),
    lambda d: d["contexts"][-1]["settings"].update(epsilon=float("nan")),
    lambda d: d["evidence"][0]["provenance"]["derived_from"][0].update(evidence="implementation"),
    lambda d: d.update(migration=None),
])
def test_malformed_v02_records_are_not_scientific_unknown(mutate):
    data = load_contract(EXAMPLE).model_dump()
    mutate(data)
    with pytest.raises(ValueError):
        ContractV02.model_validate(data)


def test_new_claim_revision_and_context_do_not_retarget_imported_assessments():
    old = load_contract(EXAMPLE)
    data = old.model_dump()
    revision = deepcopy(data["claims"][1])
    revision.update(revision="reviewed-proposition-2", statement="An explicitly revised proposition with separately defined criteria.")
    data["claims"].append(revision)
    new = ContractV02.model_validate(data)
    changed = Context(id="different-temperature", scope="Different requested temperature.",
                      quantities={"temperature": {"value": 1700, "unit": "K"}})
    assessed = assess_conditions(new, changed, "imported")
    assert assessed.claims == new.claims
    assert assessed.assessments[:len(old.assessments)] == old.assessments
    assert assessed.evidence == old.evidence
    assert all(a.claim_revision != revision["revision"] for a in assessed.assessments if a.kind == "evidence_support")
    assert assess_conditions(assessed, changed, "imported") == assessed
    with pytest.raises(ValueError, match="new ID"):
        assess_conditions(assessed, changed.model_copy(update={"scope": "Changed meaning."}), "imported")


def test_restoration_rejects_changed_historical_content():
    data = migrate_contract(ROOT / "contracts/h2_solubility.yaml").model_dump()
    data["claims"][0]["statement"] = "A different proposition."
    with pytest.raises(ValueError, match="content changed"):
        restore_v01(ContractV02.model_validate(data))


def test_new_evidence_does_not_prevent_restoring_the_original_declarations():
    old = load_contract(EXAMPLE)
    data = old.model_dump()
    data["evidence"].append({"id": "later-inspection", "kind": "implementation",
                             "summary": "Synthetic new record.", "sources": ["fixture.py"],
                             "scope": "Migration regression fixture only."})
    assert restore_v01(ContractV02.model_validate(data)) == restore_v01(old)


def test_reassessment_does_not_silently_keep_a_conflicting_generated_id():
    data = load_contract(EXAMPLE).model_dump()
    data["assessments"][-1]["classification"] = "outside_reported_range"
    contract = ContractV02.model_validate(data)
    with pytest.raises(ValueError, match="different content"):
        assess_conditions(contract, contract.contexts[-1], "imported")


@pytest.mark.parametrize("version", ["0.3", 0.2, None])
def test_reader_rejects_unsupported_or_ambiguous_versions(version, tmp_path):
    data = load_contract(EXAMPLE).model_dump()
    data["schema_version"] = version
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_contract(path)


def test_pressure_unit_conversion_and_quantity_identity():
    condition = next(c for c in load_contract(EXAMPLE).conditions if c.quantity == "melt_total_pressure")
    for value, unit in ((7000, "bar"), (.7, "GPa"), (700, "MPa"), (700000000, "Pa")):
        context = Context(id="boundary", scope="Boundary conversion.",
                          quantities={"melt_total_pressure": {"value": value, "unit": unit}})
        assert compare_condition(condition, context)[0] == "within_reported_range"
    fugacity = Context(id="fugacity", scope="Fugacity cannot replace total pressure.",
                      quantities={"hydrogen_fugacity": {"value": 7500, "unit": "bar"}})
    assert compare_condition(condition, fugacity)[0] == "unknown"


def test_joint_samples_do_not_create_a_rectangle_or_interpolation_support():
    condition = SampleCondition(id="grid", revision="1", kind="samples", scope="Synthetic paired samples.", evidence=["fixture"], samples=[
        {"id": "a", "scope": "Synthetic sample A.", "quantities": {"temperature": {"value": 1000, "unit": "K"}, "pressure": {"value": 1, "unit": "bar"}}},
        {"id": "b", "scope": "Synthetic sample B.", "quantities": {"temperature": {"value": 2000, "unit": "K"}, "pressure": {"value": 2, "unit": "bar"}}},
    ])
    for temperature, pressure, expected in ((1000, 1, "at_recorded_sample"), (1000, 2, "not_sampled"), (1500, 1.5, "not_sampled")):
        context = Context(id="requested", scope="Synthetic request.", quantities={
            "temperature": {"value": temperature, "unit": "K"}, "pressure": {"value": pressure, "unit": "bar"}})
        assert compare_condition(condition, context)[0] == expected
    assert compare_condition(condition, Context(id="empty", scope="Missing input."))[0] == "unknown"


def test_json_exponents_and_duplicate_keys_are_handled_consistently(tmp_path):
    path = tmp_path / "context.json"
    path.write_text('{"id":"request","scope":"Example","settings":{"epsilon":1e-13}}')
    assert Context.model_validate(read_document(path)).settings["epsilon"] == 1e-13
    path.write_text('{"id":"a","id":"b"}')
    with pytest.raises(ValueError, match="Duplicate"):
        read_document(path)


def test_migration_and_assessment_cli_never_overwrite_an_existing_artifact(tmp_path, capsys):
    output = tmp_path / "migrated.yaml"
    original = ROOT / "contracts/h2_solubility.yaml"
    assert main(["migrate", str(original), "--output", str(output)]) == 0
    assert isinstance(load_contract(output), ContractV02)
    before = output.read_bytes()
    with pytest.raises(SystemExit) as error:
        main(["migrate", str(original), "--output", str(output)])
    assert error.value.code == 2 and output.read_bytes() == before
    result = tmp_path / "assessed.json"
    assert main(["assess", str(EXAMPLE), "--context", str(ROOT / "examples/v02/h2_context.json"),
                 "--subject", "imported", "--output", str(result)]) == 0
    assert load_contract(result) == load_contract(EXAMPLE)
    assert main([str(result)]) == 0
    assert "VALID" in capsys.readouterr().out


def test_v02_check_keeps_declarations_scoped_and_rejects_ignored_context_overrides(capsys):
    assert main(["check", str(EXAMPLE), "--json"]) == 1
    entry = json.loads(capsys.readouterr().out)["contracts"][0]
    assert entry["declarations"] == []
    assert any(a.get("origin") == "imported_v0.1_declaration" for a in entry["assessments"])
    with pytest.raises(SystemExit) as error:
        main(["check", str(EXAMPLE), "--temperature", "1750"])
    assert error.value.code == 2
    assert "mceg assess" in capsys.readouterr().err
