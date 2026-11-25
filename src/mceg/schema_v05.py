"""Version 0.5 quantities and explicitly assembled mathematical models."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Annotated, Literal

from pydantic import Field, model_serializer, model_validator

from .schema import Text
from .schema_v02 import Digest, RangeAssessment, Record, SampleAssessment
from .schema_v03 import (
    Claim as ClaimV03,
    EquationRef,
    Key,
    SupportAssessment as SupportV03,
    _equation_key,
    _unique,
)
from .schema_v04 import ContractV04


class QuantityRef(EquationRef):
    """Refer to one semantic quantity definition and revision."""


class QuantityDefinition(QuantityRef):
    """An authored physical or mathematical meaning, not a numerical value."""

    latex: Text
    description: Text
    unit: Text
    domain: Text
    coordinates: list[QuantityRef] = Field(default_factory=list)


class ModelQuantity(Record):
    """A quantity's role in one model, independent of its definition."""

    quantity: QuantityRef
    role: Literal["coordinate", "input", "parameter", "unknown", "derived"]


class RelationInstance(Record):
    """Adopt an Equation and connect its local symbols to model quantities."""

    id: Key
    equation: EquationRef
    kind: Literal["equation", "constraint", "distribution", "optimization"] = "equation"
    role: Text
    quantities: dict[Key, Key]


class MathematicalModelRef(EquationRef):
    """Refer to one declared assembly and revision."""


class MathematicalModel(MathematicalModelRef):
    """An incidence graph, without an execution order or a support status."""

    description: Text
    scope: Text
    quantities: dict[Key, ModelQuantity] = Field(min_length=1)
    relations: list[RelationInstance] = Field(min_length=1)


class MathematicalModelPin(MathematicalModelRef):
    sha256: Digest


class Claim(ClaimV03):
    mathematical_models: list[MathematicalModelRef] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def preserve_legacy_snapshot(self, handler):
        data = handler(self)
        if not self.mathematical_models:
            data.pop("mathematical_models", None)
        return data


class SupportAssessment(SupportV03):
    mathematical_model_pins: list[MathematicalModelPin] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def preserve_legacy_snapshot(self, handler):
        data = handler(self)
        if not self.mathematical_model_pins:
            data.pop("mathematical_model_pins", None)
        return data


Assessment = Annotated[
    SupportAssessment | RangeAssessment | SampleAssessment,
    Field(discriminator="kind"),
]


class ContractV05(ContractV04):
    schema_version: Literal["0.5"]
    quantities: list[QuantityDefinition] = Field(default_factory=list)
    mathematical_models: list[MathematicalModel] = Field(default_factory=list)
    claims: list[Claim] = Field(min_length=1)
    assessments: list[Assessment] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_mathematical_links(self):
        _unique((_equation_key(q) for q in self.quantities), "quantity (ID, revision) pairs")
        _unique((_equation_key(m) for m in self.mathematical_models),
                "mathematical model (ID, revision) pairs")
        quantities = {_equation_key(q): q for q in self.quantities}
        models = {_equation_key(m): m for m in self.mathematical_models}
        equations = {_equation_key(e): e for e in self.equations}
        coordinates = {}
        for key, quantity in quantities.items():
            coordinates[key] = _unique((_equation_key(c) for c in quantity.coordinates),
                                       "quantity coordinate references")
            if coordinates[key] - quantities.keys():
                raise ValueError("Unknown quantity coordinate revision")

        # Coordinate definitions are hierarchical; physical relation cycles are allowed.
        pending = dict(coordinates)
        while pending:
            roots = {key for key, refs in pending.items() if not refs & pending.keys()}
            if not roots:
                raise ValueError("Quantity coordinate definitions must not contain a cycle")
            pending = {key: refs for key, refs in pending.items() if key not in roots}

        for model in self.mathematical_models:
            referenced = _unique((_equation_key(q.quantity) for q in model.quantities.values()),
                                 "quantity references within a mathematical model")
            if referenced - quantities.keys():
                raise ValueError("Unknown mathematical model quantity revision")
            for key in referenced:
                if coordinates[key] - referenced:
                    raise ValueError("Quantity coordinates must be present in the mathematical model")
            _unique((r.id for r in model.relations), "relation instance IDs within a mathematical model")
            for relation in model.relations:
                equation = equations.get(_equation_key(relation.equation))
                if equation is None:
                    raise ValueError("Unknown relation Equation revision")
                if relation.quantities.keys() != equation.symbols.keys():
                    raise ValueError("Relation mappings must cover exactly every declared Equation symbol")
                if set(relation.quantities.values()) - model.quantities.keys():
                    raise ValueError("Unknown model quantity alias in relation mapping")
                for symbol, alias in relation.quantities.items():
                    quantity = quantities[_equation_key(model.quantities[alias].quantity)]
                    if equation.symbols[symbol].unit != quantity.unit:
                        raise ValueError(
                            "Relation symbol and quantity unit strings must match exactly; "
                            "automatic unit conversion is not performed"
                        )

        claims = {(c.id, c.revision): c for c in self.claims}
        for claim in self.claims:
            referenced = _unique((_equation_key(m) for m in claim.mathematical_models),
                                 "Claim mathematical model references")
            if referenced - models.keys():
                raise ValueError("Unknown Claim mathematical model revision")
        for assessment in self.assessments:
            if not isinstance(assessment, SupportAssessment):
                continue
            claim = claims[assessment.claim, assessment.claim_revision]
            referenced = {_equation_key(m) for m in claim.mathematical_models}
            pinned = _unique((_equation_key(p) for p in assessment.mathematical_model_pins),
                             "mathematical model pins")
            if pinned - referenced:
                raise ValueError("Mathematical model pins must refer to assessed Claim models")
            if assessment.status in {"supported", "contradicted"} and pinned != referenced:
                raise ValueError(
                    f"{assessment.status.capitalize()} assessments must pin every Claim mathematical model"
                )
        return self


def mathematical_model_records(contract: ContractV05, model_id: str, revision: str) -> list[dict]:
    """Return the selected definition closure, without interpreting mathematics."""
    models = {_equation_key(m): m for m in contract.mathematical_models}
    model = models.get((model_id, revision))
    if model is None:
        raise ValueError(f"Unknown mathematical model revision: {model_id}@{revision}")
    quantities = {_equation_key(q): q for q in contract.quantities}
    equations = {_equation_key(e): e for e in contract.equations}
    records = {("mathematical_model", model.id, model.revision): model}
    pending = [_equation_key(q.quantity) for q in model.quantities.values()]
    while pending:
        key = pending.pop()
        record_key = ("quantity", *key)
        if record_key in records:
            continue
        quantity = quantities[key]
        records[record_key] = quantity
        pending.extend(_equation_key(ref) for ref in quantity.coordinates)
    for relation in model.relations:
        equation = equations[_equation_key(relation.equation)]
        records["equation", equation.id, equation.revision] = equation
    return [
        {"kind": kind, "id": identifier, "revision": version,
         "record": record.model_dump(mode="json")}
        for (kind, identifier, version), record in sorted(records.items())
    ]


def mathematical_model_digest(contract: ContractV05, model_id: str, revision: str) -> str:
    """Hash the model, mappings and referenced definitions; not their validity."""
    snapshot = mathematical_model_records(contract, model_id, revision)
    data = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)
    return sha256(data.encode("utf-8")).hexdigest()
