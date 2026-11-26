"""Version 0.4 adoption decisions, separate from evidence and scientific support."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Literal

from pydantic import Field, model_validator

from .schema import Text
from .schema_v02 import Digest, Record
from .schema_v03 import ContractV03, Key


class DecisionRef(Record):
    id: Key
    revision: Key


class DecisionOption(Record):
    """An authored alternative; an implementation need not exist yet."""

    id: Key
    description: Text


class DecisionBasis(Record):
    """Pin a recorded basis and its explicitly referenced dependency closure."""

    kind: Literal["evidence", "assessment"]
    id: Text
    sha256: Digest


class Decision(DecisionRef):
    """A scoped choice, without a scientific support or execution status."""

    question: Text
    scope: Text
    options: list[DecisionOption] = Field(min_length=1)
    selected: Key
    reasons: list[Text] = Field(min_length=1)
    basis: list[DecisionBasis] = Field(default_factory=list)
    limitations: list[Text] = Field(default_factory=list)
    reconsider_when: list[Text] = Field(default_factory=list)
    subject: Text | None = None
    context: Text | None = None
    supersedes: DecisionRef | None = None

    @model_validator(mode="after")
    def check_options(self):
        options = [option.id for option in self.options]
        if len(options) != len(set(options)):
            raise ValueError("Decision option IDs must be unique")
        if self.selected not in options:
            raise ValueError("Selected decision option must be recorded")
        basis = [(pin.kind, pin.id) for pin in self.basis]
        if len(basis) != len(set(basis)):
            raise ValueError("Duplicate decision basis references")
        return self


def decision_basis_records(contract: ContractV03, kind: str, record_id: str) -> list[dict]:
    """Resolve recorded dependencies only; never read files or execute a provider.

    Assessment targets, subjects, contexts and evidence are included, together
    with recursively declared provenance, equations and pinned bindings. The
    resulting snapshot excludes unrelated records and all Decision records.
    """
    if kind not in {"evidence", "assessment"}:
        raise ValueError("Decision basis kind must be evidence or assessment")
    collections = {
        "evidence": "evidence", "assessment": "assessments", "claim": "claims",
        "condition": "conditions", "subject": "subjects", "context": "contexts",
        "equation": "equations", "binding": "bindings",
        "mathematical_model": "mathematical_models", "quantity": "quantities",
    }
    versioned = {"claim", "condition", "equation", "mathematical_model", "quantity"}
    records = {
        (category, item.id, item.revision if category in versioned else None): item
        for category, collection in collections.items()
        for item in getattr(contract, collection, [])
    }
    pending = [(kind, record_id, None)]
    selected = {}
    while pending:
        key = pending.pop()
        if key in selected:
            continue
        record = records.get(key)
        if record is None:
            raise ValueError(f"Unknown decision basis dependency: {key}")
        category, identifier, revision = key
        entry = {"kind": category, "id": identifier, "record": record.model_dump(mode="json")}
        if revision is not None:
            entry["revision"] = revision
        selected[key] = entry
        for target in ("subject", "context"):
            identifier = getattr(record, target, None)
            if identifier is not None:
                pending.append((target, identifier, None))
        pending.extend(("evidence", identifier, None) for identifier in getattr(record, "evidence", []))
        if category == "evidence" and record.provenance is not None:
            pending.extend(("evidence", link.evidence, None) for link in record.provenance.derived_from)
        elif category == "assessment":
            target = "claim" if record.kind == "evidence_support" else "condition"
            pending.append((target, getattr(record, target), getattr(record, target + "_revision")))
            pending.extend(("equation", pin.id, pin.revision) for pin in getattr(record, "equation_pins", []))
            pending.extend(("binding", pin.id, None) for pin in getattr(record, "binding_pins", []))
            pending.extend(("mathematical_model", pin.id, pin.revision)
                           for pin in getattr(record, "mathematical_model_pins", []))
        elif category == "claim":
            pending.extend(("equation", ref.id, ref.revision) for ref in getattr(record, "equations", []))
            pending.extend(("mathematical_model", ref.id, ref.revision)
                           for ref in getattr(record, "mathematical_models", []))
        elif category == "binding":
            pending.append(("equation", record.equation.id, record.equation.revision))
        elif category == "mathematical_model":
            pending.extend(("equation", relation.equation.id, relation.equation.revision)
                           for relation in record.relations)
            pending.extend(("quantity", item.quantity.id, item.quantity.revision)
                           for item in record.quantities.values())
        elif category == "quantity":
            pending.extend(("quantity", ref.id, ref.revision) for ref in record.coordinates)
    return [selected[key] for key in sorted(selected, key=lambda key: (key[0], key[1], key[2] or ""))]


def decision_basis_digest(contract: ContractV03, kind: str, record_id: str) -> str:
    """Hash a validated record closure, not its files or its scientific validity."""
    snapshot = decision_basis_records(contract, kind, record_id)
    data = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)
    return sha256(data.encode("utf-8")).hexdigest()


class ContractV04(ContractV03):
    schema_version: Literal["0.4"]
    decisions: list[Decision] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_decision_links(self):
        decisions = {(item.id, item.revision): item for item in self.decisions}
        if len(decisions) != len(self.decisions):
            raise ValueError("Decision (ID, revision) pairs must be unique")
        subjects = {item.id for item in self.subjects}
        contexts = {item.id for item in self.contexts}
        basis = {"evidence": {item.id for item in self.evidence},
                 "assessment": {item.id for item in self.assessments}}
        predecessors = {}
        for key, decision in decisions.items():
            if decision.subject is not None and decision.subject not in subjects:
                raise ValueError("Unknown decision Subject")
            if decision.context is not None and decision.context not in contexts:
                raise ValueError("Unknown decision Context")
            for pin in decision.basis:
                if pin.id not in basis[pin.kind]:
                    raise ValueError("Unknown decision basis reference")
            if decision.supersedes is not None:
                predecessor = decision.supersedes.id, decision.supersedes.revision
                if predecessor not in decisions:
                    raise ValueError("Unknown superseded Decision revision")
                predecessors[key] = predecessor
        resolved = set()
        for start in predecessors:
            path = set()
            key = start
            while key in predecessors and key not in resolved:
                if key in path:
                    raise ValueError("Decision supersedes links must not contain a cycle")
                path.add(key)
                key = predecessors[key]
            resolved.update(path)
        return self
