"""Read-only reStructuredText views of selected contracts and calculation cases.

This module does not import Sphinx or scientific provider implementations.
"""

import argparse
from dataclasses import dataclass
import hashlib
import html
import json
import os
from pathlib import Path
import re
from textwrap import indent
from typing import Literal
from urllib.parse import quote

from pydantic import Field, model_validator
import yaml

from mceg import ContractV02, load_contract, trace_provenance
from mceg.coverage import LocalPath, _local
from mceg.schema import Text
from mceg.schema_v02 import Digest, Record
from mceg.validator import read_document


class ContractSource(Record):
    """A provider checkout and explicit contract paths or glob patterns."""

    provider: Text
    root: Path
    paths: list[LocalPath] = Field(min_length=1)


class DocumentationConfig(Record):
    """All paths resolve relative to this configuration file."""

    source_root: Path
    output: Path
    contracts: list[ContractSource] = Field(default_factory=list)
    cases: list[Path] = Field(default_factory=list)


class FileRef(Record):
    provider: Text
    path: LocalPath
    sha256: Digest


class Component(Record):
    provider: Text
    model_id: Text
    path: LocalPath | None = None
    sha256: Digest | None = None
    settings: dict[Text, Text | int | float | bool] = Field(default_factory=dict)
    subject: Text | None = None
    context: Text | None = None
    assessments: list[Text] = Field(default_factory=list)

    @model_validator(mode="after")
    def paired_fields(self):
        if (self.path is None) != (self.sha256 is None):
            raise ValueError("A registered component needs both path and sha256")
        if (self.subject is None) != (self.context is None):
            raise ValueError("Select both subject and context")
        if self.assessments and self.subject is None:
            raise ValueError("Assessment selection requires subject and context")
        if self.path is None and self.subject is not None:
            raise ValueError("An unregistered component cannot select contract records")
        return self


class Connection(Record):
    consumer: Text
    dependency: Text
    quantity: Text
    description: Text


class Highlight(Record):
    assessment: Text
    title: Text


class Case(Record):
    format: Literal["mceg_documentation_case_v1"]
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    title: Text
    description: Text
    inputs: dict[Text, Text | int | float | bool] = Field(default_factory=dict)
    providers: dict[Text, Text]
    components: dict[Text, Component] = Field(min_length=1)
    connections: list[Connection] = Field(default_factory=list)
    legacy_case: FileRef | None = None
    highlights: list[Highlight] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def references(self):
        for component in [*self.components.values(), *([self.legacy_case] if self.legacy_case else [])]:
            if component.provider not in self.providers:
                raise ValueError(f"Unknown provider: {component.provider}")
        for edge in self.connections:
            if edge.consumer not in self.components or edge.dependency not in self.components:
                raise ValueError("Unknown connection endpoint")
        return self


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=True).encode()).hexdigest()[:24]


def text(value):
    """Keep authored prose literal, including directive and role punctuation."""
    return re.sub(r"([\\`*_|<>{}\[\]:.])", r"\\\1", " ".join(str(value).split()))


def heading(title, level=1):
    return title + "\n" + "=-~"[level - 1] * len(title) + "\n"


def doc_link(label, page):
    return f":doc:`{text(label)} <{page}>`"


def download(label, path):
    return f":download:`{text(label)} <{path}>`"


def toctree(pages, *, hidden=False):
    pages = list(pages)
    if not pages:
        return ""
    option = ":hidden:" if hidden else ":maxdepth: 1"
    return f".. toctree::\n   {option}\n\n" + indent("\n".join(pages), "   ") + "\n"


def table(headers, rows):
    rows = list(rows)
    if not rows:
        return "None recorded.\n"
    out = [".. list-table::", "   :header-rows: 1", "   :class: mceg-table", ""]
    for row in [headers, *rows]:
        out.append("   * - " + "\n     - ".join(row))
    return "\n".join(out) + "\n"


def values(data):
    return table(["Field", "Recorded value"],
                 ((text(k), text(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v))
                  for k, v in data.items()))


def graph(nodes, edges):
    lines = ['digraph {', 'rankdir=LR;', 'graph [bgcolor="transparent"];',
             'node [shape=box, style=rounded, fontname="sans-serif", fontsize=11];',
             'edge [fontname="sans-serif", fontsize=10];']
    for key, label, href in nodes:
        attrs = {"label": label}
        if href:
            attrs.update(href=href, target="_top")
        lines.append(f'{json.dumps(key)} [{", ".join(f"{k}={json.dumps(v)}" for k, v in attrs.items())}];')
    for start, end, label in edges:
        lines.append(f'{json.dumps(start)} -> {json.dumps(end)} [label={json.dumps(label)}];')
    return (".. graphviz::\n"
            "   :alt: Recorded relationships; equivalent text links accompany the graph.\n\n"
            + indent("\n".join([*lines, "}"]), "   ") + "\n")


@dataclass
class Entry:
    provider: str
    root: Path
    path: str
    sha256: str
    contract: object

    @property
    def page(self):
        return "model-" + identity(self.provider, self.path, self.sha256)

    @property
    def references_page(self):
        return self.page + "-references"

    def record_page(self, kind, key=None):
        if kind in {"evidence", "assessment"}:
            return f"{self.page}-{kind}-{identity(key)}"
        suffix = {"claim": "assessments", "condition": "applicability",
                  "subject": "records", "context": "records"}[kind]
        return self.page + "-" + suffix

    def anchor(self, kind, key, revision=None):
        return self.page + "-" + identity(kind, key, revision)

    def link(self, kind=None, key=None, revision=None, label=None):
        label = label or key or self.contract.model.name
        if kind:
            return f":ref:`{text(label)} <{self.anchor(kind, key, revision)}>`"
        return doc_link(label, self.page)

    def svg_link(self, kind=None, key=None):
        # Sphinx Graphviz rebases page-relative links into its _images directory.
        anchor = "#" + self.anchor(kind, key) if kind else ""
        page = self.record_page(kind, key) if kind else self.page
        return f"{page}.html{anchor}"


class Catalog:
    def __init__(self, output, source_root=None):
        self.output = Path(output).resolve()
        self.source_root = Path(source_root or self.output.parent).resolve()
        if self.output == self.source_root or not self.output.is_relative_to(self.source_root):
            raise ValueError("Output must be a dedicated directory inside the Sphinx source root")
        self.entries = {}
        self.roots = {}

    def add(self, provider, root, path, sha256=None):
        root = Path(root).resolve()
        if self.roots.setdefault(provider, root) != root:
            raise ValueError(f"Ambiguous provider root: {provider}")
        source = _local(root, path)
        actual = digest(source)
        if sha256 is not None and actual != sha256:
            raise ValueError(f"Contract hash mismatch: {provider}:{path}")
        key = (provider, path)
        if key in self.entries:
            previous = self.entries[key]
            if previous.root != root or previous.sha256 != actual:
                raise ValueError(f"Ambiguous provider/path: {provider}:{path}")
            return previous
        entry = Entry(provider, root, path, actual, load_contract(source))
        self.entries[key] = entry
        return entry

    def source(self, entry, locator):
        if locator.startswith(("https://", "http://")):
            return f"`{text(locator)} <{quote(locator, safe='/:#?=&%@+~')}>`__"
        path, _, fragment = locator.partition("#")
        linked = self.entries.get((entry.provider, path))
        if linked:
            if fragment:
                if fragment not in {e.id for e in linked.contract.evidence}:
                    raise ValueError(f"Unknown evidence reference: {locator}")
                return linked.link("evidence", fragment)
            return linked.link()
        source = (entry.root / path).resolve()
        if source.is_relative_to(entry.root) and source.is_file():
            relative = Path(os.path.relpath(source, self.output)).as_posix()
            line_locator = re.fullmatch(r"L[0-9]+(?:-L?[0-9]+)?", fragment)
            if source.suffix == ".rst" and source.is_relative_to(self.source_root) and not line_locator:
                if fragment:
                    target = quote(str(Path(relative).with_suffix(".html")), safe="/") + "#" + quote(fragment)
                    return f"`{text(locator)} <{target}>`__"
                return doc_link(locator, str(Path(relative).with_suffix("")))
            # Downloads preserve source bytes; fragments of non-HTML files stay descriptive.
            return download(locator, relative)
        return text(locator) + " (unresolved locator; not inspected by this build)"


def evidence_links(entry, ids):
    return ", ".join(entry.link("evidence", key) for key in ids) or "None recorded"


def section(entry, kind, record):
    anchor = entry.anchor(kind, record.id, getattr(record, "revision", None))
    return f".. _{anchor}:\n\n" + heading(text(record.id), 3)


def folded(title, content):
    """Collapse technical metadata, keeping record anchors and cautions outside."""
    return ('.. raw:: html\n\n   <details class="mceg-details">\n'
            f'   <summary>{html.escape(title)}</summary>\n\n'
            + content + "\n\n.. raw:: html\n\n   </details>\n")


def model_header(entry, title):
    return [heading(title), "Model: " + entry.link() + "\n"]


def hidden_pages(pages):
    return toctree(pages, hidden=True)


def references_page(catalog, entry):
    """Expose recorded literature separately from implementation/test artifacts."""
    out = [*model_header(entry, "References"),
           "These are the literature references recorded in this contract. "
           "Citation does not imply source inspection or physical validation. "
           "Open an evidence record for its scope and review notes.\n"]
    records = [e for e in entry.contract.evidence if e.kind == "literature"]
    if not records:
        out.append("No literature references are recorded in this contract. "
                   f"See {doc_link('Evidence', entry.page + '-evidence')} for other source files and artifacts.\n")
    else:
        out.append(table(
            ["Reference", "Use in the contract", "Recorded role", "Recorded inspection"],
            ((catalog.source(entry, locator),
              entry.link("evidence", e.id, label=e.summary),
              text(e.provenance.role if e.provenance else "unknown"),
              text(e.provenance.inspection.replace("_", " ") if e.provenance else "unknown"))
             for e in records for locator in e.sources),
        ))
        out.append("\nMultiple records can cite the same source for different purposes; "
                   "they are not independent publications. Bibliographic details absent "
                   "from the contract are not inferred by this build.\n")
    return "\n".join(out)


def assessment_target(entry, assessment):
    kind = "claim" if assessment.kind == "evidence_support" else "condition"
    return entry.link(kind, getattr(assessment, kind), getattr(assessment, kind + "_revision"))


def assessment_table(entry, records):
    return table(
        ["Assessment", "Recorded outcome", "Target", "Subject", "Context"],
        ((entry.link("assessment", a.id), text(getattr(a, "status", getattr(a, "classification", ""))),
          assessment_target(entry, a), entry.link("subject", a.subject), entry.link("context", a.context))
         for a in records),
    )


def model_page(catalog, entry):
    """A bounded preview, without choosing a current assessment from history."""
    c = entry.contract
    out = [heading(text(c.model.name)), text(c.model.description) + "\n",
           doc_link("References", entry.references_page) + " — cited literature and source-review status.\n"]
    literature = [e for e in c.evidence if e.kind == "literature"]
    if literature:
        inspections = {}
        for e in literature:
            state = e.provenance.inspection.replace("_", " ") if e.provenance else "unknown"
            inspections[state] = inspections.get(state, 0) + 1
        out.append("Literature inspection records: " + "; ".join(
            f"**{text(state)}** ({count})" for state, count in inspections.items()) + ".\n")
    else:
        out.append("No literature references are recorded.\n")
    out.append(heading("Before use", 2))
    unknown = [d for d in c.domains if d.status == "unknown"]
    for d in unknown[:2]:
        out.append(f"- **{text(d.kind.replace('_', ' '))}: unknown.** {text(d.description)}")
    for limitation in c.limitations[:2]:
        out.append("- " + text(limitation.statement))
    out.append(f"\n{doc_link('Applicability', entry.page + '-applicability')} contains all "
               f"{len(c.domains)} domain declarations and {len(c.limitations)} limitations. "
               "This preview shows up to two unknown domains and the first two recorded limitations.\n")
    out.append(heading("Recorded support", 2))
    if isinstance(c, ContractV02):
        assessments = c.assessments
        out.append("Outcomes belong to their linked Subject and Context; none is implicitly current.\n")
        if 0 < len(assessments) <= 3:
            out.append(assessment_table(entry, assessments))
        else:
            out.append(f"{len(assessments)} assessments are recorded across "
                       f"{len({a.subject for a in assessments})} subjects and "
                       f"{len({a.context for a in assessments})} contexts. "
                       f"{doc_link('Browse scoped outcomes', entry.page + '-assessments')}; "
                       "no assessment is selected for this overview.\n")
    else:
        out.append("v0.1 declared statuses are not case-specific assessments.\n")
        if len(c.claims) <= 3:
            out.append(table(["Claim", "Declared status", "Scope"],
                             ((entry.link("claim", claim.id), text(claim.status), text(claim.scope))
                              for claim in c.claims)))
        else:
            out.append(doc_link(f"Read all {len(c.claims)} declared claims and their scopes",
                                entry.page + "-assessments") + ".\n")
    out += [heading("Explore", 2), toctree(
        entry.page + "-" + suffix for suffix in
        ("applicability", "assessments", "evidence", "references", "records"))]
    return "\n".join(out)


def applicability_page(entry):
    c = entry.contract
    out = [*model_header(entry, "Applicability"), heading("Assumptions and limitations", 2)]
    for title, records in (("Assumption", c.assumptions), ("Limitation", c.limitations)):
        out.append(table([title, "Evidence"],
                         ((text(r.statement), evidence_links(entry, r.evidence)) for r in records)))
    out.append(heading("Reported domains", 2))
    for d in c.domains:
        out += [heading(f"{text(d.kind)}: {text(d.status)}", 3), text(d.description) + "\n",
                *("- " + text(s) for s in d.conditions), "\nEvidence: " + evidence_links(entry, d.evidence) + "\n"]
    if isinstance(c, ContractV02):
        out.append(heading("Condition records", 2))
        for r in c.conditions:
            out += [section(entry, "condition", r), values(r.model_dump(exclude={"evidence", "id"})),
                    "Evidence: " + evidence_links(entry, r.evidence) + "\n"]
    return "\n".join(out)


def assessments_page(entry):
    c = entry.contract
    out = [*model_header(entry, "Assessments")]
    if isinstance(c, ContractV02):
        out += ["All recorded contexts and history are listed; none is implicitly current. "
                "Open an assessment for its reasons, evidence and method.\n",
                assessment_table(entry, c.assessments) if c.assessments else "No assessments are recorded.\n",
                hidden_pages(entry.record_page("assessment", a.id) for a in c.assessments)]
    out.append(heading("Claims", 2))
    for claim in c.claims:
        out += [section(entry, "claim", claim), text(claim.statement) + "\n",
                f"Kind: {text(claim.kind)}. Scope: {text(claim.scope)}\n"]
        if isinstance(c, ContractV02):
            assessments = [a for a in c.assessments if a.kind == "evidence_support"
                           and (a.claim, a.claim_revision) == (claim.id, claim.revision)]
            out += ["Revision: " + text(claim.revision) + "\n",
                    "Recorded assessments: " + (", ".join(entry.link("assessment", a.id) for a in assessments)
                                                or "None recorded") + "\n"]
        else:
            out += [f"v0.1 declared status: **{text(claim.status)}**. This is not a case-specific assessment.\n",
                    "Evidence: " + evidence_links(entry, claim.evidence) + "\n"]
    if isinstance(c, ContractV02) and c.follow_ups:
        out.append(heading("Recorded follow-ups", 2))
        for f in c.follow_ups:
            out += [heading(text(f.id), 3), entry.link(f.target_kind, f.target, f.revision) + "\n",
                    text(f.action) + "\n", values({"Requires": f.requires, "Completion criteria": f.completion})]
            for resolution in c.follow_up_resolutions:
                if resolution.follow_up == f.id:
                    out.append("Recorded resolution: " + text(resolution.note) + ". Evidence: "
                               + evidence_links(entry, resolution.evidence) + "\n")
    return "\n".join(out)


def assessment_page(entry, assessment):
    a = assessment
    return "\n".join([
        f".. _{entry.anchor('assessment', a.id)}:\n",
        *model_header(entry, "Assessment: " + text(a.id)),
        doc_link("All assessments", entry.page + "-assessments") + "\n",
        assessment_table(entry, [a]),
        "Kind: " + text(a.kind) + "\n",
        heading("Reasons", 2), *("- " + text(reason) for reason in a.reasons),
        "\nEvidence: " + evidence_links(entry, a.evidence) + "\n",
        folded("Assessment method", values({
            "Method": a.method.id, "Method revision": a.method.revision,
            "Method description": a.method.description,
            **({"Origin": a.origin} if a.kind == "evidence_support" else {}),
        })),
    ])


def records_page(catalog, entry):
    c = entry.contract
    source = Path(os.path.relpath(entry.root / entry.path, catalog.output)).as_posix()
    out = [*model_header(entry, "Implementation & records"),
           download("Download the source contract", source) + "\n",
           folded("Contract identity", values({
               "Model ID": c.model.id, "Provider": entry.provider, "Contract": entry.path,
               "Contract SHA-256": entry.sha256, "Schema": c.schema_version,
           })),
           heading("Implementation", 2), values(c.model.implementation.model_dump())]
    if isinstance(c, ContractV02):
        out.append(heading("Subject records", 2))
        for r in c.subjects:
            out += [section(entry, "subject", r), values(r.implementation.model_dump()),
                    folded("Selected files and recorded hashes", values(r.selected_files))]
        out.append(heading("Context records", 2))
        for r in c.contexts:
            out += [section(entry, "context", r), text(r.scope) + "\n", values(r.model_dump()["quantities"]),
                    folded("Context settings", values(r.settings))]
    return "\n".join(out)


def evidence_index(entry):
    out = [*model_header(entry, "Evidence"),
           "Open a record for its scope, sources, audit gaps and ancestry. "
           "Source inspection and numerical test results do not establish physical accuracy.\n",
           table(["Evidence", "Kind", "Recorded inspection"],
                 ((entry.link("evidence", e.id, label=e.summary), text(e.kind),
                   text(e.provenance.inspection.replace("_", " ") if e.provenance else "unknown"))
                  for e in entry.contract.evidence))]
    edges = [(e.id, r.evidence, r.comparison) for e in entry.contract.evidence if e.provenance
             for r in e.provenance.derived_from]
    if edges:
        out += [heading("Recorded dependencies", 2),
                graph([(e.id, e.id, entry.svg_link("evidence", e.id)) for e in entry.contract.evidence], edges),
                table(["Derived evidence", "Source evidence", "Comparison"],
                      ((entry.link("evidence", start), entry.link("evidence", end), text(label))
                       for start, end, label in edges))]
    out.append(hidden_pages(entry.record_page("evidence", e.id) for e in entry.contract.evidence))
    return "\n".join(out)


def evidence_page(catalog, entry, e):
    trace = trace_provenance(entry.contract, e.id)
    out = [f".. _{entry.anchor('evidence', e.id)}:\n",
           *model_header(entry, "Evidence: " + text(e.id)),
           doc_link("All evidence", entry.page + "-evidence") + "\n",
           text(e.summary) + "\n",
           f"Kind: {text(e.kind)}. Scope: {text(e.scope)}\n"]
    if e.result:
        out.append(f"Stored execution result: **{text(e.result)}**. No test was executed by this build.\n")
    if isinstance(entry.contract, ContractV02):
        if e.subject:
            out.append("Recorded subject: " + entry.link("subject", e.subject) + "\n")
        if e.context:
            out.append("Recorded context: " + entry.link("context", e.context) + "\n")
    out += [heading("Sources", 2), *("- " + catalog.source(entry, s) for s in e.sources), "",
            "Local links open build-checkout files; recorded revisions and hashes "
            "may describe earlier bytes and are not reverified by this build.\n"]
    if isinstance(entry.contract, ContractV02) and e.artifacts:
        out.append(folded("Artifact files and recorded hashes", table(
            ["Artifact", "Recorded SHA-256"],
            ((catalog.source(entry, a.source), text(a.sha256)) for a in e.artifacts),
        )))
    out.append(heading("Source review", 2))
    if e.provenance:
        out.append(values(e.provenance.model_dump(exclude={"derived_from"})))
    else:
        out.append("Provenance: **unknown**; no inspection is inferred.\n")
    out += [f"Recorded source audit complete: **{str(trace['recorded_audit_complete']).lower()}**. "
            "This describes the recorded ancestry, not physical accuracy.\n",
            table(["Evidence", "Audit gap"],
                  ((entry.link("evidence", i["evidence"]), text(i["issue"])) for i in trace["issues"]))]
    if trace["links"]:
        nodes = [(n["id"], n["id"] + "\n" + n.get("provenance", {}).get("inspection", "unknown"),
                  entry.svg_link("evidence", n["id"])) for n in trace["nodes"]]
        edges = [(r["from"], r["to"], r["comparison"]) for r in trace["links"]]
        out += [heading("Ancestry", 2), graph(nodes, edges),
                table(["Derived evidence", "Source evidence", "Comparison", "Note"],
                      ((entry.link("evidence", r["from"]), entry.link("evidence", r["to"]),
                        text(r["comparison"]), text(r["note"])) for r in trace["links"]))]
    return "\n".join(out)


def model_pages(catalog, entry):
    pages = {
        entry.page: model_page(catalog, entry),
        entry.page + "-applicability": applicability_page(entry),
        entry.page + "-assessments": assessments_page(entry),
        entry.page + "-evidence": evidence_index(entry),
        entry.references_page: references_page(catalog, entry),
        entry.page + "-records": records_page(catalog, entry),
    }
    pages.update({entry.record_page("evidence", e.id): evidence_page(catalog, entry, e)
                  for e in entry.contract.evidence})
    if isinstance(entry.contract, ContractV02):
        pages.update({entry.record_page("assessment", a.id): assessment_page(entry, a)
                      for a in entry.contract.assessments})
    return pages


def load_case(path, catalog):
    case = Case.model_validate(read_document(path))
    roots = {key: (path.parent / value).resolve() for key, value in case.providers.items()}
    entries = {}
    for key, component in case.components.items():
        if component.path is None:
            entries[key] = None
            continue
        entry = catalog.add(component.provider, roots[component.provider], component.path, component.sha256)
        if entry.contract.model.id != component.model_id:
            raise ValueError(f"Model ID mismatch: {key}")
        if component.subject is not None:
            c = entry.contract
            if not isinstance(c, ContractV02):
                raise ValueError("Subject/context selection requires a v0.2 contract")
            if component.subject not in {s.id for s in c.subjects} or component.context not in {s.id for s in c.contexts}:
                raise ValueError(f"Unknown subject/context: {key}")
            assessments = {a.id: a for a in c.assessments}
            for selected in component.assessments:
                a = assessments.get(selected)
                if a is None or (a.subject, a.context) != (component.subject, component.context):
                    raise ValueError(f"Assessment does not match selected subject/context: {selected}")
        entries[key] = entry
    legacy = None
    if case.legacy_case:
        if case.inputs:
            raise ValueError("Use legacy inputs or documentation inputs, not both")
        ref = case.legacy_case
        source = _local(roots[ref.provider], ref.path)
        if digest(source) != ref.sha256:
            raise ValueError("Legacy case hash mismatch")
        legacy = read_document(source)
        if legacy.get("case_version") != "0.1" or legacy.get("assessment_method") != "manual":
            raise ValueError("Expected a v0.1 manual example case")
        expected = {k: c.path for k, c in case.components.items() if c.path is not None}
        if legacy["components"] != expected:
            raise ValueError("Legacy case components differ from the selected contracts")
        for a in legacy["assessments"]:
            for locator in a["evidence"]:
                target, sep, key = locator.partition("#")
                entry = catalog.entries.get((ref.provider, target))
                if not sep or entry is None or key not in {e.id for e in entry.contract.evidence}:
                    raise ValueError(f"Unknown legacy evidence reference: {locator}")
    assessment_ids = [a["id"] for a in legacy["assessments"]] if legacy else []
    if len(set(assessment_ids)) != len(assessment_ids):
        raise ValueError("Duplicate legacy assessment IDs")
    for highlight in case.highlights:
        if highlight.assessment not in assessment_ids:
            raise ValueError(f"Unknown highlighted assessment: {highlight.assessment}")
    return case, entries, legacy


def case_pages(catalog, case, entries, legacy):
    """Keep the overview short; retain complete judgments on linked child pages."""
    name = "case-" + case.id
    back = doc_link("Back to case overview", name) + "\n"
    overview = [heading(text(case.title)), text(case.description) + "\n"]
    setup = [heading("Inputs and connections", 1), back,
             "Only explicitly listed components and connections are shown. "
             "Unrecorded dependencies remain unknown; this is not a completeness claim.\n"]
    assessments = [heading("Assessments", 1), back]
    records = [heading("Source records", 1), back,
               "Contract hashes identify the displayed records. Implementation revisions and "
               "scientific judgments remain in the linked model records.\n"]
    pages = {}
    manual = legacy["assessments"] if legacy else []
    manual_pages = {a["id"]: name + "-assessment-" + identity(a["id"]) for a in manual}
    by_id = {a["id"]: a for a in manual}
    if case.highlights:
        overview += [heading("Key findings", 2),
                     table(["Recorded assessment", "Outcome"],
                           ((doc_link(h.title, manual_pages[h.assessment]),
                             text(by_id[h.assessment]["classification"])) for h in case.highlights))]
    overview.append(heading("Model connections", 2))
    nodes = [("case", case.title, None)]
    edges, models, rows = [], [], []
    for key, component in case.components.items():
        entry = entries[key]
        nodes.append(("component:" + key, key + ("\nUNREGISTERED" if entry is None else ""),
                      entry.svg_link() if entry else None))
        edges.append(("case", "component:" + key, "selects"))
        model = entry.link() if entry else text(component.model_id) + " — **unregistered / unknown**"
        models.append(f"- {text(key)}: {model}")
        rows.append((text(key), model, text(component.settings)))
        records += [heading(text(key), 2),
                    values(component.model_dump(include={"provider", "model_id", "path", "sha256"}))]
    edges += [("component:" + e.consumer, "component:" + e.dependency, "requires " + e.quantity)
              for e in case.connections]
    overview += [graph(nodes, edges), *models, "\n" + heading("Details", 2),
                 toctree(name + "-" + suffix for suffix in ("assessments", "setup", "records"))]
    if legacy:
        setup += [heading("Calculation inputs", 2), values(legacy["inputs"])]
    elif case.inputs:
        setup += [heading("Calculation inputs", 2), values(case.inputs)]
    setup += [heading("Selected settings", 2), table(["Component", "Model", "Settings"], rows),
              heading("Connections", 2),
              table(["Consumer", "Dependency", "Quantity", "Transformation / scope"],
                    ((text(e.consumer), text(e.dependency), text(e.quantity), text(e.description)) for e in case.connections))]
    if legacy:
        setup += [heading("Recorded adapter", 2),
                  values({k: v for k, v in legacy["connection"].items() if k != "steps"}),
                  *[f"{i}. {text(step)}" for i, step in enumerate(legacy["connection"].get("steps", []), 1)], ""]
    if manual:
        assessments += [heading("Manual case assessments", 2),
                        "These are the judgments in the pinned example case; they are not newly executed checks. "
                        "Open an assessment for its scope, reasons and evidence.\n",
                        table(["Assessment", "Recorded outcome"],
                              ((doc_link(a["id"].replace("_", " "), manual_pages[a["id"]]),
                                text(a["classification"])) for a in manual)),
                        hidden_pages(manual_pages.values())]
    assessments.append(heading("Selected v0.2 assessments", 2))
    for key, component in case.components.items():
        entry = entries[key]
        assessments.append(heading(text(key), 3))
        if component.subject is None:
            assessments.append("No v0.2 assessment selected. Case-specific support remains **unknown**; "
                               "historical declarations on the model page are not reused automatically.\n")
        else:
            assessments += ["Subject: " + entry.link("subject", component.subject) + ". Context: "
                            + entry.link("context", component.context) + "\n",
                            "Selected assessments: " + (", ".join(entry.link("assessment", a) for a in component.assessments)
                                                        or "None; support remains unknown") + "\n"]
    for a in manual:
        refs = []
        for locator in a["evidence"]:
            path, _, key = locator.partition("#")
            refs.append(catalog.entries[(case.legacy_case.provider, path)].link("evidence", key))
        details = [heading(text(a["id"].replace("_", " ").capitalize())),
                   doc_link("All assessments", name + "-assessments") + " · " + doc_link("Case overview", name) + "\n",
                   f"Recorded outcome: **{text(a['classification'])}**\n",
                   heading("Scope", 2), text(a["scope"]) + "\n",
                   heading("Reason", 2), text(a["reason"]) + "\n"]
        metadata = {k: v for k, v in a.items() if k not in {"id", "classification", "scope", "reason", "evidence"}}
        if metadata:
            details += [heading("Recorded conditions", 2), values(metadata)]
        details += [heading("Evidence", 2), *("- " + ref for ref in refs),
                    f"\nSource: {doc_link('pinned manual case', name + '-records')}. No new assessment was made.\n"]
        pages[manual_pages[a["id"]]] = "\n".join(details)
    if legacy:
        records += [heading("Manual case snapshot", 2), values(case.legacy_case.model_dump())]
    pages.update({name: "\n".join(overview), name + "-setup": "\n".join(setup),
                  name + "-assessments": "\n".join(assessments), name + "-records": "\n".join(records)})
    return pages


def build(contract_sources: list[dict | ContractSource], case_paths: list[str | Path],
          output: str | Path, *, source_root: str | Path) -> Catalog:
    """Generate RST and CSS inside a Sphinx source tree without changing inputs.

    Paths supplied to this Python API resolve from the current directory; case
    provider roots resolve from each case file. Only files listed in our output
    manifest may be replaced or removed. Existing authored files are preserved.
    """
    catalog = Catalog(output, source_root)
    output = catalog.output
    for config in contract_sources:
        selection = ContractSource.model_validate(config)
        root = selection.root.resolve()
        for pattern in selection.paths:
            paths = sorted(root.glob(pattern))
            if not paths:
                raise ValueError(f"No contracts matched: {selection.provider}:{pattern}")
            for path in paths:
                catalog.add(selection.provider, root, path.relative_to(root).as_posix())
    case_paths = [Path(p).resolve() for p in case_paths]
    cases = [load_case(path, catalog) for path in case_paths]
    if len({c.id for c, _, _ in cases}) != len(cases):
        raise ValueError("Duplicate case IDs")
    pages = {}
    for entry in catalog.entries.values():
        pages.update(model_pages(catalog, entry))
    for path, (case, entries, legacy) in zip(case_paths, cases):
        additions = case_pages(catalog, case, entries, legacy)
        if pages.keys() & additions.keys():
            raise ValueError(f"Case page name collision: {case.id}")
        pages.update(additions)
        relative = Path(os.path.relpath(path, output)).as_posix()
        pages["case-" + case.id + "-records"] += (
            "\n" + heading("Documentation case", 2) + "\n"
            + download("Download the selected case", relative) + "\n\n"
            + values({"Case SHA-256": digest(path)})
        )
    pages["catalog"] = "\n".join([
        heading("Model catalog", 1),
        "This catalog includes the explicitly configured contracts and those selected by cases. "
        "It is not a provider inventory coverage report.\n",
        table(["Model", "Schema", "Provider", "References"],
              ((e.link(), text(e.contract.schema_version), text(e.provider),
                doc_link("References", e.references_page)) for e in catalog.entries.values())),
        hidden_pages(e.page for e in catalog.entries.values()),
    ])
    pages["cases"] = (
        ("" if cases else ":orphan:\n\n") + heading("Calculation cases") + "\n"
        + (toctree("case-" + c.id for c, _, _ in cases) if cases else "No calculation cases are configured.\n")
    )
    manifest = output / ".mceg-generated.json"
    if manifest.is_symlink():
        raise ValueError("Refusing a symlinked MCEG generated-file manifest")
    previous = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
    if not isinstance(previous, list) or any(
            not isinstance(name, str) or not (
                re.fullmatch(r"[a-z0-9_-]+\.(md|rst)", name) or name == "_static/mceg.css")
            for name in previous):
        raise ValueError("Invalid MCEG generated-file manifest")
    files = {name + ".rst": content for name, content in pages.items()}
    files["_static/mceg.css"] = (Path(__file__).parent / "_static/mceg.css").read_text(encoding="utf-8")
    for name in set(previous) | files.keys():
        path = output / name
        if path.is_symlink() or path.parent.is_symlink() or (path.exists() and name not in previous):
            raise ValueError(f"Refusing to replace an unowned output file: {path}")
    output.mkdir(parents=True, exist_ok=True)
    for name in set(previous) - files.keys():
        (output / name).unlink(missing_ok=True)
    for name, content in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
    manifest.write_text(json.dumps(sorted(files), indent=2) + "\n", encoding="utf-8")
    return catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate RST sources; the consumer builds HTML with Sphinx.")
    parser.add_argument("--config", type=Path, default=Path("mceg/docs.yaml"),
                        help="YAML configuration (default: mceg/docs.yaml); paths resolve from this file")
    args = parser.parse_args(argv)
    try:
        config_path = args.config.resolve()
        config = DocumentationConfig.model_validate_json(json.dumps(read_document(config_path)))
        root = config_path.parent
        sources = [source.model_copy(update={"root": root / source.root}) for source in config.contracts]
        catalog = build(sources, [root / path for path in config.cases], root / config.output,
                        source_root=root / config.source_root)
    except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        parser.exit(1, f"mceg docs: {exc}\n")
    print(f"Generated RST for {len(catalog.entries)} contracts and {len(config.cases)} cases in {catalog.output}")
    return 0
