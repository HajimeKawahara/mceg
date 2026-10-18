"""An archived pass cannot silently become support for changed inputs or context."""

import importlib.util
import json
from pathlib import Path

import pytest

from mceg import load_contract


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/curated_gas"
SPEC = importlib.util.spec_from_file_location("curated_assessment", EXAMPLE / "assess.py")
ASSESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASSESS)


def write_json(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n")


@pytest.fixture
def example(tmp_path):
    """Synthetic files test bookkeeping only; no provider or numerical run is used."""
    provider = tmp_path / "provider"
    review = json.loads((EXAMPLE / "review.json").read_text())
    context = json.loads((EXAMPLE / "context.json").read_text())
    source = provider / ASSESS.IMPLEMENTATION
    source.parent.mkdir(parents=True)
    source.write_text("Synthetic implementation fixture.\n")
    receipt_path = provider / review["receipt"]["path"]
    artifact = receipt_path.parent / "fixture.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("Synthetic outcome fixture; no numerical execution.\n")
    receipt = {
        **{key: context[key] for key in ("python", "jax", "backend", "dtype", "epsilon_crit")},
        "temperature_K": [1500, 1735, 2000, 2517, 3000, 3973, 4000],
        "pressure_bar": [1e-6, 1e-4, .01, 1, 100],
        "cases_passed": 70, "fastchem_cases_passed": 70, "fastchem": "passed",
        "selected_file_sha256": {ASSESS.IMPLEMENTATION: ASSESS.sha256(source)},
        "output_sha256": {"fixture.txt": ASSESS.sha256(artifact)},
    }
    write_json(receipt_path, receipt)
    contract = {
        "schema_version": "0.1",
        "model": {"id": "exogibbs.curated_gas.v1", "name": "Synthetic fixture",
                  "description": "Bookkeeping fixture, not scientific evidence.",
                  "implementation": {"repository": review["repository"],
                                     "revision": "sha256:" + ASSESS.sha256(source),
                                     "entry_points": [ASSESS.IMPLEMENTATION + ":chemsetup"]}},
        "assumptions": [], "limitations": [],
        "domains": [{"kind": "scientific_applicability", "status": "unknown",
                     "description": "No physical evidence.", "conditions": [], "evidence": ["verification"]}],
        "claims": [{"id": "equilibrium_verification", "kind": "numerical_verification",
                    "status": "supported", "statement": "Synthetic fixture claim.",
                    "scope": "Fixture scope.", "evidence": ["verification"]}],
        "evidence": [{"id": "verification", "kind": "benchmark", "result": "passed",
                      "summary": "Synthetic outcome fixture.", "sources": [review["receipt"]["path"]],
                      "scope": "Fixture scope."}],
    }
    write_json(provider / review["contract"]["path"], contract)
    for key in ("contract", "receipt"):
        review[key]["sha256"] = ASSESS.sha256(provider / review[key]["path"])
    review["rationale"] = "Synthetic fixture review; no scientific assessment."
    review_path = tmp_path / "review.json"
    write_json(review_path, review)
    return provider, context, review_path


def test_reviewed_declaration_has_a_separate_scoped_assessment(example):
    provider, context, review = example
    report = ASSESS.run(provider, context, review)
    assert report["assessments"][2]["status"] == "supported"
    assert report["assessments"][2]["reasons"] == ["reviewed_declaration_reused"]
    assert report["imported_declaration"]["origin"] == "imported_v0.1_declaration"
    assert report["evidence"]["result"] == "passed"
    assert report["physical_validation"] == "unknown"
    assert "source_adoption_choices" in report["not_evaluated"]


@pytest.mark.parametrize("change,interval,sample", [
    ({"temperature_K": 1750}, "within_reported_range", "not_sampled"),
    ({"pressure_bar": .001}, "within_reported_range", "not_sampled"),
    ({"temperature_K": 4001}, "outside_reported_range", "not_sampled"),
    ({"temperature_K": None}, "unknown", "unknown"),
    ({"composition": "different_budget"}, "within_reported_range", "at_recorded_sample"),
    ({"composition": None}, "within_reported_range", "at_recorded_sample"),
    ({"jax": "different_version"}, "within_reported_range", "at_recorded_sample"),
    ({"epsilon_crit": 1e-8}, "within_reported_range", "at_recorded_sample"),
    ({"dtype": "float32"}, "within_reported_range", "at_recorded_sample"),
    ({"backend": "gpu"}, "within_reported_range", "at_recorded_sample"),
])
def test_ranges_samples_and_context_do_not_promote_support(example, change, interval, sample):
    provider, context, review = example
    report = ASSESS.run(provider, {**context, **change}, review)
    assert [a["classification"] for a in report["assessments"][:2]] == [interval, sample]
    assert report["assessments"][2]["status"] == "unknown"
    assert report["evidence"]["result"] == "passed"
    assert report["imported_declaration"]["claim"]["status"] == "supported"


@pytest.mark.parametrize("network", ["ions", "neutral"])
@pytest.mark.parametrize("temperature", [1500, 4000])
def test_closed_bounds_and_both_recorded_networks(example, network, temperature):
    provider, context, review = example
    report = ASSESS.run(provider, {**context, "network": network, "temperature_K": temperature}, review)
    assert report["assessments"][2]["status"] == "supported"


@pytest.mark.parametrize("kind,missing", [("input", False), ("output", False), ("input", True), ("output", True)])
def test_changed_files_leave_historical_evidence_intact(example, kind, missing):
    provider, context, review_path = example
    review = json.loads(review_path.read_text())
    original = {key: (provider / review[key]["path"]).read_bytes() for key in ("contract", "receipt")}
    path = provider / (ASSESS.IMPLEMENTATION if kind == "input" else
                       str(Path(review["receipt"]["path"]).parent / "fixture.txt"))
    if missing:
        path.unlink()
    else:
        path.write_text("Changed fixture.\n")
    report = ASSESS.run(provider, context, review_path)
    assert report["assessments"][2]["status"] == "unknown"
    assert "selected_files_changed_or_missing" in report["assessments"][2]["reasons"]
    assert not report["integrity"]["selected_files_match"]
    assert report["evidence"]["result"] == "passed"
    assert all((provider / review[key]["path"]).read_bytes() == value for key, value in original.items())


@pytest.mark.parametrize("key", ["contract", "receipt"])
def test_changed_reviewed_records_require_explicit_review(example, key):
    provider, context, review_path = example
    review = json.loads(review_path.read_text())
    path = provider / review[key]["path"]
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="Reviewed record changed"):
        ASSESS.run(provider, context, review_path)


def test_repinning_an_unexecuted_receipt_does_not_create_support(example):
    provider, context, review_path = example
    review = json.loads(review_path.read_text())
    path = provider / review["receipt"]["path"]
    receipt = json.loads(path.read_text())
    receipt.update(fastchem="not_run", fastchem_cases_passed=0)
    write_json(path, receipt)
    review["receipt"]["sha256"] = ASSESS.sha256(path)
    write_json(review_path, review)
    report = ASSESS.run(provider, context, review_path)
    assert report["assessments"][2]["status"] == "unknown"
    assert "recorded_support_incomplete" in report["assessments"][2]["reasons"]


@pytest.mark.parametrize("change", [{"temperature_K": True}, {"temperature_K": float("nan")},
                                   {"pressure_bar": -1}, {"temperature_K": "1735"},
                                   {"temperature_C": 1461.85}, {"network": "other"}])
def test_invalid_inputs_are_errors_instead_of_unknown(example, change):
    provider, context, review = example
    with pytest.raises(ValueError):
        ASSESS.run(provider, {**context, **change}, review)


def test_evidence_paths_stay_within_the_selected_repository(tmp_path):
    for path in ("../outside", str(tmp_path / "absolute")):
        with pytest.raises(ValueError):
            ASSESS.local_path(tmp_path, path)


@pytest.mark.parametrize("bounds", [[4000, 1500], [0, 4000], [1500, float("inf")]])
def test_invalid_reviewed_bounds_are_rejected(example, bounds):
    provider, context, review_path = example
    review = json.loads(review_path.read_text())
    review["numerical_temperature_K"] = bounds
    write_json(review_path, review)
    with pytest.raises(ValueError):
        ASSESS.run(provider, context, review_path)


def test_cli_writes_an_assessment_and_leaves_invalid_inputs_without_a_report(example, tmp_path):
    provider, context, review_path = example
    # Exercise CLI argument handling with the synthetic review, not a provider import.
    original_run = ASSESS.run
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(ASSESS, "run", lambda root, inputs: original_run(root, inputs, review_path))
        path = tmp_path / "context.json"
        output = tmp_path / "assessment.json"
        write_json(path, context)
        ASSESS.main(["--exogibbs", str(provider), "--context", str(path), "--output", str(output)])
        assert json.loads(output.read_text())["assessments"][2]["status"] == "supported"
        invalid_output = tmp_path / "invalid.json"
        write_json(path, {**context, "pressure_bar": -1})
        with pytest.raises(SystemExit) as error:
            ASSESS.main(["--exogibbs", str(provider), "--context", str(path), "--output", str(invalid_output)])
        assert error.value.code == 2
        assert not invalid_output.exists()


def test_saved_assessment_is_pinned_and_v01_remains_separate():
    report = json.loads((EXAMPLE / "assessment.json").read_text())
    assert report["review"] == json.loads((EXAMPLE / "review.json").read_text())
    assert report["review_sha256"] == ASSESS.sha256(EXAMPLE / "review.json")
    assert report["evaluator_sha256"] == ASSESS.sha256(EXAMPLE / "assess.py")
    assert report["context"] == json.loads((EXAMPLE / "context.json").read_text())
    assert all(f["expected_sha256"] == f["actual_sha256"] for f in report["integrity"]["files"])
    assert report["assessments"][2]["status"] == "supported"
    assert report["physical_validation"] == "unknown"
    with pytest.raises(ValueError):
        load_contract(EXAMPLE / "review.json")
