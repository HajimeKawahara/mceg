"""Documentation navigation must preserve record scope and reject broken selections."""

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

import pytest

from mceg import load_contract
from mceg import documentation as docs
from mceg.validator import read_document


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "examples/html/case.yaml"
CONTRACTS = [{"provider": "mceg", "root": ROOT,
              "paths": ["contracts/*.yaml", "examples/v02/h2_solubility.yaml"]}]


@pytest.fixture
def case_copy(tmp_path):
    data = read_document(CASE)
    for relative in [data["legacy_case"]["path"], *(c["path"] for c in data["components"].values())]:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    data["providers"] = {"mceg": str(tmp_path)}
    return data, tmp_path / "case.json", docs.Catalog(tmp_path / "generated")


def load_case_copy(case_copy):
    data, path, catalog = case_copy
    path.write_text(json.dumps(data))
    return docs.load_case(path, catalog)


def test_generation_preserves_sources_outcomes_and_stable_pages(tmp_path):
    sources = [*ROOT.glob("contracts/*.yaml"), CASE, ROOT / "examples/h2_solubility/case.yaml",
               ROOT / "examples/v02/h2_solubility.yaml"]
    before = {p: p.read_bytes() for p in sources}
    catalog = docs.build(CONTRACTS, [CASE], tmp_path, source_root=tmp_path.parent)
    generated = {p.name: p.read_bytes() for p in tmp_path.glob("*.rst")}
    docs.build(CONTRACTS, [CASE], tmp_path, source_root=tmp_path.parent)
    assert generated == {p.name: p.read_bytes() for p in tmp_path.glob("*.rst")}
    assert before == {p: p.read_bytes() for p in sources}
    case = (tmp_path / "case-h2-solubility.rst").read_text()
    assert "1700 K" in case and "1750" not in case
    assert "Combined physical accuracy" in case and "unknown" in case
    assert "EOS temperature coverage" in case and "extrapolation" in case
    assert "make\\_pure\\_lnphi\\_func" not in case and "sha256" not in case
    for suffix in ("assessments", "setup", "records"):
        assert f"case-h2-solubility-{suffix}" in case
        assert (tmp_path / f"case-h2-solubility-{suffix}.rst").exists()
    legacy = read_document(ROOT / "examples/h2_solubility/case.yaml")
    for assessment in legacy["assessments"]:
        path = tmp_path / ("case-h2-solubility-assessment-" + docs.identity(assessment["id"]) + ".rst")
        detail = path.read_text()
        assert docs.text(assessment["scope"]) in detail
        assert docs.text(assessment["reason"]) in detail
        assert docs.text(assessment["classification"]) in detail
        assert "case-h2-solubility-assessments" in detail
        assert docs.doc_link("Case overview", "case-h2-solubility") in detail
    assert len(catalog.entries) == 6
    solubility = catalog.entries[("mceg", "contracts/h2_solubility.yaml")]
    details = "\n".join(p.read_text() for p in tmp_path.glob(solubility.page + "-*.rst"))
    assert "10.1016/j.epsl.2012.06.031" in details
    assert "not\\_inspected" in details and "discrepancy" in details
    assert "Stored execution result: **passed**" in details
    assert "v0.1 declared status: **unknown**" in details


def test_references_are_discoverable_without_promoting_source_inspection(tmp_path):
    catalog = docs.build(CONTRACTS, [], tmp_path, source_root=tmp_path.parent)
    index = (tmp_path / "catalog.rst").read_text()
    for entry in catalog.entries.values():
        model = (tmp_path / (entry.page + ".rst")).read_text()
        references = (tmp_path / (entry.references_page + ".rst")).read_text()
        link = docs.doc_link("References", entry.references_page)
        assert link in index
        assert model.index(link) < model.index(docs.heading("Before use", 2))
        assert entry.link() in references
        for record in entry.contract.evidence:
            if record.kind == "literature":
                assert entry.link("evidence", record.id, label=record.summary) in references
                assert all(catalog.source(entry, source) in references for source in record.sources)
                if record.provenance:
                    assert record.provenance.inspection.replace("_", " ") in references
    assert "Bibliographic details absent" in references


def test_missing_literature_is_visible_and_never_inferred(tmp_path):
    catalog = docs.Catalog(tmp_path)
    entry = catalog.add("provider", ROOT, "contracts/h2_solubility.yaml")
    entry.contract = entry.contract.model_copy(update={
        "evidence": [e for e in entry.contract.evidence if e.kind != "literature"],
    })
    rendered = docs.references_page(catalog, entry)
    assert "No literature references are recorded" in rendered
    assert entry.link() in rendered
    assert "doi.org" not in rendered


def test_model_hierarchy_preserves_records_and_keeps_cautions_visible(tmp_path):
    catalog = docs.build(CONTRACTS, [], tmp_path, source_root=tmp_path.parent)
    for entry in catalog.entries.values():
        def page(name):
            return (tmp_path / (name + ".rst")).read_text()

        overview = page(entry.page)
        assert "<details" not in overview
        assert "Contract SHA-256" not in overview
        assert ".. graphviz::" not in overview
        for suffix in ("applicability", "assessments", "evidence", "references", "records"):
            assert entry.page + "-" + suffix in overview
            assert entry.link() in page(entry.page + "-" + suffix)
        applicability = page(entry.page + "-applicability")
        assert "<details" not in applicability
        for record in [*entry.contract.assumptions, *entry.contract.limitations]:
            assert docs.text(record.statement) in applicability
        for domain in entry.contract.domains:
            assert docs.text(domain.description) in applicability
            assert all(docs.text(condition) in applicability for condition in domain.conditions)
        for evidence in entry.contract.evidence:
            details = page(entry.record_page("evidence", evidence.id))
            assert docs.text(evidence.summary) in details
            assert docs.text(evidence.scope) in details
            assert all(catalog.source(entry, locator) in details for locator in evidence.sources)
            assert entry.anchor("evidence", evidence.id) in details
            assert docs.doc_link("All evidence", entry.page + "-evidence") in details
            if evidence.provenance:
                assert docs.text(evidence.provenance.inspection) in details
                assert docs.text(evidence.provenance.note) in details
                for link in evidence.provenance.derived_from:
                    assert docs.text(link.note) in details
                    assert entry.link("evidence", link.evidence) in details
        for assessment in getattr(entry.contract, "assessments", []):
            details = page(entry.record_page("assessment", assessment.id))
            assert entry.link("subject", assessment.subject) in details
            assert entry.link("context", assessment.context) in details
            for reason in assessment.reasons:
                assert details.index(docs.text(reason)) < details.index("<details")
            assert docs.text(assessment.method.description) in details


def test_overview_does_not_select_from_a_long_assessment_history(tmp_path):
    catalog = docs.Catalog(tmp_path)
    entry = catalog.add("provider", ROOT, "examples/v02/h2_solubility.yaml")
    assert len(entry.contract.assessments) > 3
    overview = docs.model_page(catalog, entry)
    assert "no assessment is selected for this overview" in overview
    assert f"{len(entry.contract.assessments)} assessments" in overview
    for assessment in entry.contract.assessments:
        assert entry.link("assessment", assessment.id) not in overview
        assert entry.link("assessment", assessment.id) in docs.assessments_page(entry)
    # A short list preserves both Subject and Context, including unknown support.
    records = [a for a in entry.contract.assessments if getattr(a, "status", None) == "unknown"][:2]
    assert records
    entry.contract = entry.contract.model_copy(update={"assessments": records})
    overview = docs.model_page(catalog, entry)
    assert "unknown" in overview and "none is implicitly current" in overview
    for assessment in records:
        assert entry.link("assessment", assessment.id) in overview
        assert entry.link("subject", assessment.subject) in overview
        assert entry.link("context", assessment.context) in overview


@pytest.mark.parametrize("mutation,match", [
    ("hash", "Contract hash mismatch"), ("model", "Model ID mismatch"),
    ("edge", "Unknown connection endpoint"), ("record", "Unknown legacy evidence reference"),
    ("highlight", "Unknown highlighted assessment"),
])
def test_invalid_cases_fail_before_rendering(case_copy, mutation, match):
    data, _, _ = case_copy
    if mutation == "hash":
        data["components"]["eos"]["sha256"] = "0" * 64
    elif mutation == "model":
        data["components"]["eos"]["model_id"] = "missing"
    elif mutation == "edge":
        data["connections"][0]["dependency"] = "missing"
    elif mutation == "highlight":
        data["highlights"][0]["assessment"] = "missing"
    else:
        ref = data["legacy_case"]
        path = Path(data["providers"]["mceg"]) / ref["path"]
        legacy = read_document(path)
        legacy["assessments"][0]["evidence"] = ["contracts/zhang_duan_h2.yaml#missing"]
        path.write_text(json.dumps(legacy))
        ref["sha256"] = docs.digest(path)
    with pytest.raises(ValueError, match=match):
        load_case_copy(case_copy)


def test_known_unregistered_components_remain_visible(case_copy):
    data, _, catalog = case_copy
    data["components"]["opacity"] = {"provider": "mceg", "model_id": "missing.opacity"}
    case, entries, legacy = load_case_copy(case_copy)
    rendered = docs.case_pages(catalog, case, entries, legacy)["case-" + case.id]
    assert docs.text("missing.opacity") in rendered and "UNREGISTERED" in rendered
    assert "unregistered / unknown" in rendered


def test_record_ids_are_namespaced_by_provider_contract_and_revision(tmp_path):
    catalog = docs.Catalog(tmp_path)
    first = catalog.add("one", ROOT, "contracts/h2_solubility.yaml")
    other = catalog.add("two", ROOT, "contracts/h2_solubility.yaml")
    revised = catalog.add("one", ROOT, "examples/v02/h2_solubility.yaml")
    assert len({e.anchor("evidence", "implementation") for e in (first, other, revised)}) == 3
    assert first.anchor("claim", "x", "1") != first.anchor("claim", "x", "2")


def test_provider_alias_cannot_change_roots_for_another_contract(tmp_path):
    catalog = docs.Catalog(tmp_path)
    catalog.add("one", ROOT, "contracts/h2_solubility.yaml")
    with pytest.raises(ValueError, match="Ambiguous provider root"):
        catalog.add("one", tmp_path, "different.yaml")


def test_selection_does_not_reuse_a_different_context(case_copy):
    data, path, catalog = case_copy
    data.pop("legacy_case")
    data.pop("highlights")
    data["providers"] = {"mceg": str(ROOT)}
    contract_path = ROOT / "examples/v02/h2_solubility.yaml"
    contract = load_contract(contract_path)
    selection = {
        "provider": "mceg", "model_id": contract.model.id,
        "path": "examples/v02/h2_solubility.yaml", "sha256": docs.digest(contract_path),
        "subject": "imported", "context": "h2-1750K-7500bar",
        "assessments": [a.id for a in contract.assessments if a.context == "h2-1750K-7500bar"],
    }
    data["components"] = {"solubility": selection}
    data["connections"] = []
    case, entries, legacy = load_case_copy(case_copy)
    output = docs.case_pages(catalog, case, entries, legacy)["case-" + case.id + "-assessments"]
    assert "h2-1750K-7500bar" in output
    assert "imported:formula" not in output
    selection["assessments"] = ["imported:formula_evaluation"]
    with pytest.raises(ValueError, match="does not match selected subject/context"):
        load_case_copy(case_copy)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.urls = []
        self.details_depth = 0
        self.folded_tables = 0
        self.folded_ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
            if self.details_depth:
                self.folded_ids.add(attrs["id"])
        if tag == "details":
            assert "open" not in attrs
            self.details_depth += 1
        if tag == "table" and self.details_depth:
            self.folded_tables += 1
        for key in ("href", "src", "data"):
            if key in attrs:
                self.urls.append(attrs[key])

    def handle_endtag(self, tag):
        if tag == "details":
            self.details_depth -= 1


def test_regeneration_removes_only_owned_pages(tmp_path):
    output = tmp_path / "generated"
    output.mkdir()
    note = output / "notes.md"
    note.write_text("# Authored notes\n")
    catalog = docs.build(CONTRACTS, [CASE], output, source_root=tmp_path)
    old_pages = [path for path in output.glob("*.rst") if path.name not in {"notes.md", "catalog.rst", "cases.rst"}]
    docs.build([], [], output, source_root=tmp_path)
    assert not any(path.exists() for path in old_pages)
    assert not (output / "case-h2-solubility.rst").exists()
    assert note.read_text() == "# Authored notes\n"
    (output / ".mceg-generated.json").unlink()
    with pytest.raises(ValueError, match="unowned output"):
        docs.build([], [], output, source_root=tmp_path)
    assert note.read_text() == "# Authored notes\n"


def test_rst_generation_migrates_owned_markdown_and_preserves_authored_files(tmp_path):
    output = tmp_path / "generated"
    output.mkdir()
    (output / "old-model.md").write_text("# Old generated page\n")
    (output / "notes.md").write_text("# Authored notes\n")
    (output / ".mceg-generated.json").write_text(json.dumps(["old-model.md"]))
    docs.build(CONTRACTS, [], output, source_root=tmp_path)
    assert not (output / "old-model.md").exists()
    assert (output / "notes.md").read_text() == "# Authored notes\n"
    assert (output / "catalog.rst").is_file()
    assert (output / "_static/mceg.css").read_bytes() == (ROOT / "src/mceg/_static/mceg.css").read_bytes()
    manifest = json.loads((output / ".mceg-generated.json").read_text())
    assert all(name.endswith(".rst") or name == "_static/mceg.css" for name in manifest)


def test_generation_rejects_symlinked_asset_directory_before_writing(tmp_path):
    output = tmp_path / "generated"
    output.mkdir()
    outside = tmp_path / "authored_assets"
    outside.mkdir()
    (output / "_static").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="unowned output"):
        docs.build(CONTRACTS, [], output, source_root=tmp_path)
    assert list(outside.iterdir()) == []
    assert not (output / "catalog.rst").exists()


def test_cli_generates_without_sphinx_or_provider_imports(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config = {
        "source_root": "../documents", "output": "../documents/models",
        "contracts": [{"provider": "reference", "root": str(ROOT), "paths": ["contracts/*.yaml"]}],
    }
    config_path = config_dir / "docs.yaml"
    config_path.write_text(json.dumps(config))
    code = """
import sys
from importlib.abc import MetaPathFinder
class NoDocsImports(MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in {'sphinx', 'myst_parser', 'exogibbs', 'exoeos', 'jax'}:
            raise ImportError('Source generation must not import ' + fullname)
sys.meta_path.insert(0, NoDocsImports())
from mceg.__main__ import main
raise SystemExit(main(['docs', '--config', sys.argv[1]]))
"""
    result = subprocess.run([sys.executable, "-c", code, str(config_path)], cwd=tmp_path,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Generated RST for 5 contracts" in result.stdout
    assert (tmp_path / "documents/models/catalog.rst").is_file()
    assert (tmp_path / "documents/models/_static/mceg.css").is_file()
    assert not list(tmp_path.rglob("*.html"))


@pytest.mark.parametrize("change", ["unknown_field", "outside_source", "missing_pattern"])
def test_invalid_cli_configuration_does_not_write(tmp_path, capsys, change):
    config = {
        "source_root": "documents", "output": "documents/generated",
        "contracts": [{"provider": "reference", "root": str(ROOT), "paths": ["contracts/*.yaml"]}],
    }
    if change == "unknown_field":
        config["html"] = True
    elif change == "outside_source":
        config["output"] = "outside"
    else:
        config["contracts"][0]["paths"] = ["missing/*.yaml"]
    path = tmp_path / "docs.yaml"
    path.write_text(json.dumps(config))
    with pytest.raises(SystemExit) as error:
        docs.main(["--config", str(path)])
    assert error.value.code == 1
    assert "mceg docs:" in capsys.readouterr().err
    assert not (tmp_path / config["output"]).exists()


def test_bad_configuration_fails_before_writing(tmp_path):
    with pytest.raises(ValueError, match="dedicated directory"):
        docs.build([], [], tmp_path, source_root=tmp_path)
    output = tmp_path / "generated"
    with pytest.raises(ValueError, match="No contracts matched"):
        docs.build([{"provider": "empty", "root": tmp_path, "paths": ["missing/*.yaml"]}],
                   [], output, source_root=tmp_path)
    assert not output.exists()


def test_case_names_cannot_replace_another_cases_detail_page(case_copy):
    data, path, catalog = case_copy
    path.write_text(json.dumps(data))
    data["id"] += "-setup"
    other = path.with_name("other.json")
    other.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Case page name collision"):
        docs.build([], [path, other], catalog.output, source_root=path.parent)
    assert not catalog.output.exists()


def test_nested_provider_docs_preserve_rst_and_external_download_links(tmp_path):
    pytest.importorskip("sphinx")
    if not shutil.which("dot"):
        pytest.skip("Graphviz is an optional documentation dependency")
    provider = tmp_path / "provider"
    source = provider / "documents"
    source.mkdir(parents=True)
    (provider / "notes").mkdir()
    (provider / "notes/review note.md").write_text("# Raw source, not a Sphinx page\n")
    (source / "guide.rst").write_text("Guide\n=====\n\nExisting RST documentation.\n")
    contract = read_document(ROOT / "contracts/h2_solubility.yaml")
    contract["evidence"][0]["sources"] = [
        "documents/guide.rst", "documents/guide.rst#L3-L4", "notes/review note.md",
    ]
    contract_path = provider / "contract.json"
    contract_path.write_text(json.dumps(contract))
    external = tmp_path / "external"
    external.mkdir()
    shutil.copyfile(ROOT / "contracts/zhang_duan_h2.yaml", external / "eos.yaml")
    case = {
        "format": "mceg_documentation_case_v1", "id": "connection",
        "title": "Selected connection", "description": "Physical support remains unknown.",
        "inputs": {"temperature_K": 1700},
        "providers": {"provider": ".", "external": "../external"},
        "components": {
            "solubility": {"provider": "provider", "model_id": contract["model"]["id"],
                           "path": "contract.json", "sha256": docs.digest(contract_path)},
            "eos": {"provider": "external", "model_id": "exoeos.zhang_duan_h2",
                    "path": "eos.yaml", "sha256": docs.digest(external / "eos.yaml")},
        },
        "connections": [{"consumer": "solubility", "dependency": "eos",
                         "quantity": "fugacity", "description": "Explicit adapter."}],
    }
    (provider / "case.json").write_text(json.dumps(case))
    config = {
        "source_root": "documents", "output": "documents/models/nested",
        "contracts": [{"provider": "provider", "root": ".", "paths": ["contract.json"]}],
        "cases": ["case.json"],
    }
    config_path = provider / "docs.yaml"
    config_path.write_text(json.dumps(config))
    (source / "conf.py").write_text(
        "extensions = ['sphinx.ext.graphviz']\n"
        "graphviz_output_format = 'svg'\n"
        "html_static_path = ['models/nested/_static']\n"
        "html_css_files = ['mceg.css']\n"
        "exclude_patterns = ['_build']\n"
        "import sys\n"
        "from importlib.abc import MetaPathFinder\n"
        "class NoGeneratorImports(MetaPathFinder):\n"
        "    def find_spec(self, fullname, *args):\n"
        "        if fullname.split('.')[0] in {'mceg', 'myst_parser', 'exogibbs', 'exoeos', 'jax'}:\n"
        "            raise ImportError('HTML must be independent of ' + fullname)\n"
        "sys.meta_path.insert(0, NoGeneratorImports())\n"
    )
    (source / "index.rst").write_text(
        "Provider\n========\n\n.. toctree::\n\n"
        "   guide\n   models/nested/catalog\n   models/nested/cases\n"
    )
    output = tmp_path / "html"
    command = [sys.executable, "-m", "sphinx", "-q", "-b", "html", "-W",
               "--keep-going", str(source), str(output)]
    generate = [sys.executable, "-m", "mceg", "docs", "--config", str(config_path)]
    # Invoke outside the repository; configuration paths still belong to its YAML.
    result = subprocess.run(generate, cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run(command, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert_built_links(output)
    assert list(output.glob("_downloads/*/review note.md"))
    assert list(output.glob("_downloads/*/guide.rst"))
    pages = list(output.glob("models/nested/model-*.html"))
    assert len([p for p in pages if re.fullmatch(r"model-[a-f0-9]{24}", p.stem)]) == 2
    assert any('href="../../guide.html"' in p.read_text() for p in pages)
    # Source regeneration, rather than HTML compilation, revalidates case pins.
    contract_path.write_text(contract_path.read_text() + "\n")
    result = subprocess.run(generate, text=True, capture_output=True)
    assert result.returncode != 0
    assert "Contract hash mismatch" in result.stdout + result.stderr
    config["cases"] = []
    config_path.write_text(json.dumps(config))
    result = subprocess.run(generate, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (source / "models/nested/case-connection.rst").exists()
    assert (source / "models/nested/catalog.rst").exists()


def test_built_html_and_svg_links_resolve(tmp_path):
    pytest.importorskip("sphinx")
    pytest.importorskip("myst_parser")
    if not shutil.which("dot"):
        pytest.skip("Graphviz is an optional documentation dependency")
    assert docs.main(["--config", str(ROOT / "docs/mceg.yaml")]) == 0
    output = tmp_path / "html"
    result = subprocess.run(
        [sys.executable, "-m", "sphinx", "-q", "-E", "-b", "html", "-W", "--keep-going",
         str(ROOT / "docs"), str(output)], text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert_built_links(output)
    parsed = []
    for path in (output / "_generated").glob("model-*.html"):
        page = Links()
        page.feed(path.read_text())
        assert page.details_depth == 0, path
        assert not page.folded_ids, (path, page.folded_ids)
        parsed.append(page)
    assert sum(page.folded_tables for page in parsed) > 0


def assert_built_links(output):
    parsed = {}
    for path in output.rglob("*.html"):
        page = Links()
        page.feed(path.read_text())
        parsed[path.resolve()] = page
    all_links = [(path, url) for path, page in parsed.items() for url in page.urls]
    svgs = list(output.glob("_images/*.svg"))
    assert svgs, "The case and provenance diagrams must be rendered"
    svg_links = []
    for path in svgs:
        for node in ET.parse(path).iter():
            href = node.get("{http://www.w3.org/1999/xlink}href")
            if href:
                assert node.get("target") == "_top"
                svg_links.append((path, href))
    assert len(svg_links) > 2
    all_links += svg_links
    for source, url in all_links:
        parts = urlsplit(url)
        if parts.scheme or parts.netloc:
            continue
        target = (source.parent / unquote(parts.path)).resolve() if parts.path else source.resolve()
        assert target.is_file(), (source, url)
        if parts.fragment and target.suffix == ".html":
            assert unquote(parts.fragment) in parsed[target].ids, (source, url)
