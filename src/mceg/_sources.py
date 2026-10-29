"""Shared contract and calculation-case readers, independent of document output."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .coverage import LocalPath, _local, _relative
from .schema import Text
from .schema_v02 import ContractV02, Digest, Record
from .validator import load_contract, read_document


class ContractSource(Record):
    """A provider checkout and explicit contract paths or glob patterns."""

    provider: Text
    root: Path
    paths: list[LocalPath] = Field(min_length=1)


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


@dataclass
class SourceEntry:
    provider: str
    root: Path
    path: str
    sha256: str
    contract: object


class SourceCatalog:
    entry_type = SourceEntry

    def __init__(self):
        self.entries = {}
        self.roots = {}

    def add(self, provider, root, path, sha256=None):
        path = _relative(path)
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
        entry = self.entry_type(provider, root, path, actual, load_contract(source))
        self.entries[key] = entry
        return entry


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
