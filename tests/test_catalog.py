"""Installed provider records are discoverable without executing provider code."""

import hashlib
import json
from pathlib import Path
import sys

import pytest

from mceg.__main__ import main
from mceg.catalog import explain_catalog


ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


@pytest.fixture
def catalog(tmp_path):
    folder = tmp_path / "fixture_provider/data/mceg"
    folder.mkdir(parents=True)
    contract = folder / "study.yaml"
    contract.write_bytes((ROOT / "examples/v02/h2_solubility.yaml").read_bytes())
    summary = folder / "summary.json"
    write_json(summary, {"note": "Synthetic discovery fixture; no HCN scientific result."})
    record = {
        "id": "study", "path": "study.yaml", "sha256": hashlib.sha256(contract.read_bytes()).hexdigest(),
        "species": ["C1H1N1_hcn"],
        "assessments": ["imported:formula_evaluation", "imported:physical_accuracy"],
        "summary": "Synthetic source-selection sensitivity; not an uncertainty distribution.",
        "links": ["https://example.org/issue"],
        "artifacts": [{"path": "summary.json", "sha256": hashlib.sha256(summary.read_bytes()).hexdigest()}],
    }
    data = {
        "schema_version": "1", "provider": "fixture-provider", "record_version": "2026-10-28",
        "models": [{"id": "fixture.curated", "label": "Synthetic model", "dataset": "fixture-v1",
                    "identity": {"settings": {"ions": True}},
                    "species": [{"id": "C1H1N1_hcn", "aliases": ["HCN"]},
                                {"id": "C1H1N1_hnc", "aliases": ["HNC"]}],
                    "records": [record]}],
    }
    path = folder / "index.json"
    write_json(path, data)
    return path, data


def test_recorded_support_and_unknown_remain_scoped(catalog, capsys):
    path, _ = catalog
    assert main(["explain", "--catalog", str(path), "--species", "HCN", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["user_conditions"] == "not_evaluated"
    model = report["models"][0]
    assert model["canonical_species"] == "C1H1N1_hcn"
    assert model["identity_verification"] == "not_performed"
    record = model["records"][0]
    claims = {c["id"]: c for c in record["claims"]}
    assert claims["formula_evaluation"]["assessments"][0]["status"] == "supported"
    assert claims["physical_accuracy"]["assessments"][0]["status"] == "unknown"
    assert claims["fixed_pressure_linearity"]["assessments"] == []
    assert record["scientific_files"] == "not_checked"
    assert all(f["status"] == "PASS" for f in record["packaged_files"])
    assert record["follow_ups"] and record["evidence"]
    before = path.read_bytes()
    assert main(["explain", "--catalog", str(path), "--species", "HCN", "--plain"]) == 0
    output = capsys.readouterr().out
    assert "physical_accuracy: unknown" in output
    assert "Claim: " in output
    assert "not an uncertainty distribution" in output
    assert "Your conditions: not evaluated" in output
    assert "https://example.org/issue" in output
    assert path.read_bytes() == before


def test_species_findings_appear_before_generic_records_with_focused_navigation(catalog, capsys):
    path, data = catalog
    record = data["models"][0]["records"][0]
    data["models"][0]["records"].insert(0, {
        **record, "id": "generic", "species": ["*"], "summary": "Generic model review.",
    })
    write_json(path, data)
    report = explain_catalog(catalog=path, species="HCN")
    assert [r["id"] for r in report["models"][0]["records"]] == ["study", "generic"]
    main(["explain", "--catalog", str(path), "--species", "HCN"])
    output = capsys.readouterr().out
    assert output.index("study: Synthetic") < output.index("generic: Generic")
    # One selected assessment command per matching claim and record, not a cross-product.
    assert output.count("--assessment imported:physical_accuracy") == 2


@pytest.mark.parametrize("species,canonical", [("HNC", "C1H1N1_hnc"), ("C1H1N1", None), ("hcn", None)])
def test_exact_aliases_do_not_infer_isomer_or_absence_of_uncertainty(catalog, capsys, species, canonical):
    path, _ = catalog
    report = explain_catalog(catalog=path, species=species)
    assert report["models"][0]["canonical_species"] == canonical
    assert report["models"][0]["records"] == []
    assert main(["explain", "--catalog", str(path), "--species", species]) == 5
    output = capsys.readouterr().out
    assert "No relevant records" in output
    assert "does not establish absence of uncertainty" in output


def test_generic_records_are_separate_from_species_specific_coverage(catalog):
    path, data = catalog
    data["models"][0]["records"][0]["species"] = ["*"]
    write_json(path, data)
    model = explain_catalog(catalog=path, species="HNC")["models"][0]
    assert model["records"]
    assert model["species_specific_records"] == []


def test_installed_distribution_lookup_never_imports_provider(catalog, monkeypatch, capsys):
    path, _ = catalog
    site = path.parents[3]
    package = site / "fixture_provider"
    (package / "__init__.py").write_text("raise RuntimeError('Provider must not be imported')\n")
    metadata = site / "fixture_provider-1.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Metadata-Version: 2.1\nName: fixture-provider\nVersion: 1.0\n")
    (metadata / "RECORD").write_text("fixture_provider/data/mceg/index.json,,\n")
    monkeypatch.syspath_prepend(str(site))
    assert main(["explain", "--package", "fixture-provider", "--model", "fixture.curated",
                 "--species", "HCN", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["distribution"] == {"name": "fixture-provider", "version": "1.0"}
    assert "fixture_provider" not in sys.modules
    data = json.loads(path.read_text())
    data["provider"] = "another-provider"
    write_json(path, data)
    with pytest.raises(ValueError, match="does not match the selected distribution"):
        explain_catalog(package="fixture-provider")
    (metadata / "RECORD").write_text("__editable__.fixture_provider.pth,,\n")
    with pytest.raises(ValueError, match="use --catalog"):
        explain_catalog(package="fixture-provider")


@pytest.mark.parametrize("target", ["study.yaml", "summary.json"])
def test_changed_or_missing_packaged_files_are_rejected(catalog, target):
    path, _ = catalog
    artifact = path.parent / target
    artifact.write_text("changed\n")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        explain_catalog(catalog=path)
    artifact.unlink()
    with pytest.raises(ValueError, match="File is missing"):
        explain_catalog(catalog=path)


@pytest.mark.parametrize("change,reason", [
    ("schema", "schema_version"), ("alias", "Ambiguous species alias"),
    ("assessment", "Unknown assessment"), ("species", "Unknown species"),
    ("escape", "outside the supplied root"),
])
def test_invalid_catalogs_are_not_silently_accepted(catalog, change, reason):
    path, data = catalog
    model = data["models"][0]
    record = model["records"][0]
    if change == "schema":
        data["schema_version"] = "2"
    elif change == "alias":
        model["species"][1]["aliases"].append("HCN")
    elif change == "assessment":
        record["assessments"] = ["nonexistent"]
    elif change == "species":
        record["species"] = ["nonexistent"]
    else:
        record["path"] = "../study.yaml"
    write_json(path, data)
    with pytest.raises(ValueError, match=reason):
        explain_catalog(catalog=path)


@pytest.mark.parametrize("extra", [["--temperature", "2500"], ["--claim", "physical_accuracy"], ["contract.yaml"]])
def test_catalog_context_is_not_silently_discarded(catalog, extra, capsys):
    path, _ = catalog
    with pytest.raises(SystemExit) as error:
        main(["explain", "--catalog", str(path), *extra])
    assert error.value.code == 2
    assert "cannot be combined" in capsys.readouterr().err


def test_unknown_model_and_package_are_actionable(catalog):
    path, _ = catalog
    with pytest.raises(ValueError, match="available: fixture.curated"):
        explain_catalog(catalog=path, model="unknown")
    with pytest.raises(ValueError, match="not installed; use --catalog"):
        explain_catalog(package="mceg-nonexistent-fixture-package")
