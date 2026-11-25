"""A handled gap or an unrelated solver pass cannot authorize a requested use."""

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from mceg import ContractV04
from mceg.__main__ import main
from mceg.readiness import UseManifest, check_readiness, decision_digest
from mceg.schema_v04 import decision_basis_digest

from test_handling import add_decision, add_task, data  # noqa: F401


@pytest.fixture
def setup(data, tmp_path):
    source = tmp_path / "src/model.py"
    source.parent.mkdir()
    # If imported instead of parsed, this fixture fails immediately.
    source.write_text("raise RuntimeError('Never execute provider code')\n\ndef calculate():\n    return 1\n")
    data["subjects"][0]["selected_files"] = {"src/model.py": sha256(source.read_bytes()).hexdigest()}
    artifact = tmp_path / "result.json"
    artifact.write_text('{"fixture": true}\n')
    data["evidence"][0]["artifacts"] = [{"source": "result.json", "sha256": sha256(artifact.read_bytes()).hexdigest()}]
    data["assessments"][0]["status"] = "supported"
    return data, tmp_path


def write_use(setup, *, mode="scientific", decision=False):
    data, directory = setup
    contract = ContractV04.model_validate(data)
    requirement = {"assessment": "field_review", "role": "physical_support",
                   "sha256": decision_basis_digest(contract, "assessment", "field_review")}
    if decision:
        chosen = contract.decisions[0]
        requirement["exploration_decision"] = {
            "id": chosen.id, "revision": chosen.revision, "selected": chosen.selected,
            "sha256": decision_digest(chosen)}
    manifest = {"schema_version": "0.1", "id": "fixture.use", "purpose": "Evaluate this fixture only.",
                "mode": mode, "target": {"contract": "contract.json", "subject": "model",
                                            "context": "review", "entry_point": "src/model.py:calculate"},
                "requirements": [requirement]}
    path = directory / "use.json"
    path.write_text(json.dumps(manifest))
    (directory / "contract.json").write_text(json.dumps(data))
    return path, manifest


def update_json(path, update):
    data = json.loads(path.read_text())
    update(data)
    path.write_text(json.dumps(data))


def test_ready_requires_current_pinned_sources_and_scoped_support(setup, capsys):
    path, _ = write_use(setup)
    before = {p: p.read_bytes() for p in path.parent.rglob("*") if p.is_file()}
    assert main(["readiness", str(path), "--root", str(path.parent), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ready"] and report["outcome"] == "requirements_met"
    assert report["requirements"][0]["accepted_by"] == "supported_assessment"
    assert all(p.read_bytes() == content for p, content in before.items())
    assert not check_readiness(path)["ready"]


@pytest.mark.parametrize("status", ["unknown", "contradicted"])
@pytest.mark.parametrize("completed", [False, True])
def test_task_handling_and_completion_do_not_establish_readiness(setup, status, completed):
    data, directory = setup
    data["assessments"][0]["status"] = status
    add_task(data, completed=completed)
    path, _ = write_use(setup)
    report = check_readiness(path, root=directory)
    assert not report["ready"]
    assert report["requirements"][0]["recorded_support"] == status


@pytest.mark.parametrize("field", ["subject", "context"])
def test_supported_component_does_not_validate_the_requested_observer(setup, field):
    data, directory = setup
    # Even a newly pinned, supported Assessment is unsuitable in a different scope.
    data["assessments"][0][field] = "other"
    path, _ = write_use(setup)
    report = check_readiness(path, root=directory)
    assert not report["ready"]
    assert next(c for c in report["requirements"][0]["checks"] if c["name"] == "scope")["status"] == "FAIL"


def test_explicit_exploration_preserves_unknown_and_cannot_authorize_scientific_use(setup, capsys):
    data, directory = setup
    data["assessments"][0]["status"] = "unknown"
    add_decision(data)
    path, _ = write_use(setup, mode="exploration", decision=True)
    report = check_readiness(path, root=directory)
    assert report["ready"] and report["outcome"] == "exploration_permitted"
    assert report["requirements"][0]["recorded_support"] == "unknown"
    assert main(["readiness", str(path), "--root", str(directory), "--plain"]) == 0
    output = capsys.readouterr().out
    assert "EXPLORATION_PERMITTED" in output and "No physical inference" in output
    update_json(path, lambda d: d.update(mode="scientific"))
    with pytest.raises(ValueError, match="exploration mode"):
        check_readiness(path, root=directory)
    path, _ = write_use(setup)
    assert not check_readiness(path, root=directory)["ready"]


@pytest.mark.parametrize("change", [
    lambda d: d["decisions"][0].update(subject="other"),
    lambda d: d["decisions"][0].update(context="other"),
    lambda d: d["decisions"][0].update(limitations=[]),
    lambda d: d["decisions"][0].update(reconsider_when=[]),
    lambda d: d["decisions"][0].update(basis=[]),
    lambda d: d["decisions"][0]["basis"][0].update(sha256="0" * 64),
])
def test_exploration_requires_a_scoped_current_decision(setup, change):
    data, directory = setup
    data["assessments"][0]["status"] = "unknown"
    add_decision(data)
    change(data)
    path, _ = write_use(setup, mode="exploration", decision=True)
    assert not check_readiness(path, root=directory)["ready"]


def test_superseded_choice_or_changed_choice_does_not_permit_exploration(setup):
    data, directory = setup
    data["assessments"][0]["status"] = "unknown"
    add_decision(data)
    path, _ = write_use(setup, mode="exploration", decision=True)
    replacement = deepcopy(data["decisions"][0])
    replacement.update(revision="2", supersedes={"id": "field_use", "revision": "1"})
    update_json(directory / "contract.json", lambda d: d["decisions"].append(replacement))
    assert not check_readiness(path, root=directory)["ready"]
    path, _ = write_use(setup, mode="exploration", decision=True)
    update_json(directory / "contract.json", lambda d: d["decisions"][0].update(reasons=["A different reason."]))
    assert not check_readiness(path, root=directory)["ready"]


@pytest.mark.parametrize("change", [
    lambda d: d["target"].update(subject="missing"),
    lambda d: d["target"].update(context="missing"),
    lambda d: d["target"].update(entry_point="src/model.py:missing"),
    lambda d: d["requirements"][0].update(assessment="missing"),
    lambda d: d["requirements"][0].update(sha256="0" * 64),
])
def test_missing_or_stale_required_targets_fail(setup, change):
    path, _ = write_use(setup)
    update_json(path, change)
    assert not check_readiness(path, root=path.parent)["ready"]


@pytest.mark.parametrize("file", ["src/model.py", "result.json"])
def test_changed_file_bytes_fail_without_changing_support(setup, file):
    path, _ = write_use(setup)
    (path.parent / file).write_text("# Changed after review\n")
    report = check_readiness(path, root=path.parent)
    assert not report["ready"]
    assert report["requirements"][0]["recorded_support"] == "supported"


@pytest.mark.parametrize("change", [
    lambda d: d["contexts"][0].update(scope="A new physical context."),
    lambda d: d["evidence"][0].update(summary="A new comparison."),
    lambda d: d["claims"][0].update(statement="A broader assertion."),
])
def test_changed_assessment_dependency_requires_review(setup, change):
    path, _ = write_use(setup)
    update_json(path.parent / "contract.json", change)
    assert not check_readiness(path, root=path.parent)["ready"]


def test_readiness_requires_all_requirements_and_does_not_follow_unrelated_passes(setup):
    data, directory = setup
    other = deepcopy(data["assessments"][0])
    other.update(id="structural_review", status="unknown")
    data["assessments"].append(other)
    path, manifest = write_use(setup)
    contract = ContractV04.model_validate(data)
    manifest["requirements"].append({"assessment": "structural_review", "role": "implementation",
                                      "sha256": decision_basis_digest(contract, "assessment", "structural_review")})
    path.write_text(json.dumps(manifest))
    report = check_readiness(path, root=directory)
    assert [r["ready"] for r in report["requirements"]] == [True, False]
    assert not report["ready"]


def test_no_empty_requirements_duplicate_or_implementation_override(setup):
    path, manifest = write_use(setup)
    for requirements in ([], manifest["requirements"] * 2):
        with pytest.raises(ValueError):
            UseManifest.model_validate({**manifest, "requirements": requirements})
    data, _ = setup
    add_decision(data)
    _, manifest = write_use(setup, mode="exploration", decision=True)
    manifest["requirements"][0]["role"] = "implementation"
    with pytest.raises(ValueError, match="physical_support"):
        UseManifest.model_validate(manifest)


def test_source_scope_requires_pins_and_static_declarations(setup):
    data, directory = setup
    data["subjects"][0]["selected_files"].clear()
    path, _ = write_use(setup)
    assert not check_readiness(path, root=directory)["ready"]
    source = directory / "src/model.py"
    source.write_text("def another():\n    return 1\n")
    data["subjects"][0]["selected_files"]["src/model.py"] = sha256(source.read_bytes()).hexdigest()
    path, _ = write_use(setup)
    assert not check_readiness(path, root=directory)["ready"]


def test_source_symlink_cannot_escape_the_selected_root(setup, tmp_path_factory):
    data, directory = setup
    source = directory / "src/model.py"
    outside = tmp_path_factory.mktemp("outside") / "model.py"
    outside.write_bytes(source.read_bytes())
    source.unlink()
    source.symlink_to(outside)
    path, _ = write_use(setup)
    assert not check_readiness(path, root=directory)["ready"]


def test_decorated_entry_point_is_only_a_lexical_declaration(setup):
    data, directory = setup
    source = directory / "src/model.py"
    source.write_text("raise RuntimeError('Never import this provider')\n"
                      "class Atmosphere:\n"
                      "    @partial(jax.jit, static_argnums=0)\n"
                      "    def spectrum(self):\n"
                      "        return 1\n")
    data["subjects"][0]["selected_files"]["src/model.py"] = sha256(source.read_bytes()).hexdigest()
    data["subjects"][0]["implementation"]["entry_points"] = ["src/model.py:Atmosphere.spectrum"]
    path, manifest = write_use(setup)
    manifest["target"]["entry_point"] = "src/model.py:Atmosphere.spectrum"
    path.write_text(json.dumps(manifest))
    report = check_readiness(path, root=directory)
    assert report["ready"]
    check = next(c for c in report["checks"] if c["name"] == "entry_point_source")
    assert "decorators are not evaluated" in check["message"]


@pytest.mark.parametrize("status", ["supported", "unknown", "contradicted"])
def test_decorated_equation_binding_does_not_replace_scientific_support(tmp_path, status):
    from test_equation_schema import example_data

    data = example_data()
    data["schema_version"] = "0.4"
    source = tmp_path / "src/provider.py"
    source.parent.mkdir()
    source.write_text(
        "raise RuntimeError('Never execute provider code or decorators')\n"
        "@partial(jax.jit, static_argnums=0)\n"
        "def hydrogen_nuclei_density(radius_cm, velocity_kms, mass_loss_g_s):\n"
        "    return 0\n"
    )
    data["subjects"][0]["selected_files"]["src/provider.py"] = sha256(source.read_bytes()).hexdigest()
    data["assessments"][0]["status"] = status
    contract = ContractV04.model_validate(data)
    manifest = {
        "schema_version": "0.1", "id": "fixture.binding_use", "mode": "scientific",
        "purpose": "Check authored declaration correspondence in a synthetic fixture only.",
        "target": {"contract": "contract.json", "subject": "implementation",
                   "context": "review", "entry_point": "src/provider.py:hydrogen_nuclei_density"},
        "requirements": [{"assessment": "formulation_review", "role": "implementation",
                          "sha256": decision_basis_digest(contract, "assessment", "formulation_review")}],
    }
    path = tmp_path / "use.json"
    path.write_text(json.dumps(manifest))
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(data))
    before = contract_path.read_bytes()
    report = check_readiness(path, root=tmp_path)
    requirement = report["requirements"][0]
    assert next(c for c in requirement["checks"] if c["name"] == "binding_source")["status"] == "PASS"
    assert requirement["recorded_support"] == status
    assert report["ready"] == (status == "supported")
    assert contract_path.read_bytes() == before


def test_unknown_source_audit_is_not_waived_by_an_exploration_decision(setup):
    data, directory = setup
    data["assessments"][0]["status"] = "unknown"
    data["evidence"][0]["provenance"]["inspection"] = "not_inspected"
    add_decision(data)
    path, _ = write_use(setup, mode="exploration", decision=True)
    report = check_readiness(path, root=directory)
    assert not report["ready"]
    checks = {c["name"]: c["status"] for c in report["requirements"][0]["checks"]}
    assert checks["exploration_decision"] == "PASS"
    assert checks["source_audit"] == "UNKNOWN"


def test_cli_exit_codes_distinguish_not_ready_and_invalid_manifest(setup, capsys):
    data, directory = setup
    data["assessments"][0]["status"] = "unknown"
    path, _ = write_use(setup)
    assert main(["readiness", str(path), "--root", str(directory), "--json"]) == 1
    assert not json.loads(capsys.readouterr().out)["ready"]
    path.write_text("unknown_key: true\n")
    with pytest.raises(SystemExit) as error:
        main(["readiness", str(path)])
    assert error.value.code == 2
