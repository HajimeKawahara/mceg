"""Version 0.3 equation definitions and declared implementation correspondences."""

from hashlib import sha256
import json
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .schema import Text
from .schema_v02 import (Claim as ClaimV02, ContractV02, Digest, RangeAssessment,
                         Record, SampleAssessment, SupportAssessment as SupportV02)


Key = Annotated[Text, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")]
PythonName = Annotated[Text, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]
PythonSymbol = Annotated[Text, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")]


class EquationSymbol(Record):
    latex: Text
    description: Text
    unit: Text


class EquationRef(Record):
    id: Key
    revision: Key


class Equation(EquationRef):
    """An authored definition, without a scientific support or execution state."""

    latex: Text
    description: Text
    scope: Text
    symbols: dict[Key, EquationSymbol]
    assumptions: list[Text] = Field(default_factory=list)
    evidence: list[Text] = Field(default_factory=list)


class ArgumentMapping(Record):
    """Declared conversion: mathematical symbol = scale * argument + offset."""

    symbol: Key
    scale: float = 1.0
    offset: float = 0.0

    @model_validator(mode="after")
    def nonzero_scale(self):
        if self.scale == 0:
            raise ValueError("Argument conversion scale must be nonzero")
        return self


class EquationBinding(Record):
    """A correspondence to a pinned Subject; never an executable adapter."""

    id: Key
    equation: EquationRef
    subject: Text
    source: Text
    symbol: PythonSymbol
    arguments: dict[PythonName, ArgumentMapping] = Field(default_factory=dict)
    result: Key | None = None
    constants: dict[Key, Text] = Field(default_factory=dict)
    note: Text

    @model_validator(mode="after")
    def relative_python_source(self):
        path = PurePosixPath(self.source)
        if (path.is_absolute() or path.suffix != ".py" or ".." in path.parts
                or "\\" in self.source or ":" in self.source
                or str(path) != self.source):
            raise ValueError("Binding source must be a normalized relative Python path")
        return self


class EquationPin(EquationRef):
    sha256: Digest


class BindingPin(Record):
    id: Key
    sha256: Digest


def _definition_digest(record):
    data = json.dumps(record.model_dump(mode="json"), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return sha256(data.encode("utf-8")).hexdigest()


def equation_digest(equation: Equation) -> str:
    """Hash the validated definition, including symbols, assumptions and defaults."""
    return _definition_digest(equation)


def binding_digest(binding: EquationBinding) -> str:
    """Hash the declared correspondence; this does not inspect provider code."""
    return _definition_digest(binding)


class Claim(ClaimV02):
    equations: list[EquationRef] = Field(default_factory=list)


class SupportAssessment(SupportV02):
    equation_pins: list[EquationPin] = Field(default_factory=list)
    binding_pins: list[BindingPin] = Field(default_factory=list)


Assessment = Annotated[SupportAssessment | RangeAssessment | SampleAssessment,
                       Field(discriminator="kind")]


def _equation_key(reference):
    return reference.id, reference.revision


def _unique(values, description):
    values = list(values)
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {description}")
    return set(values)


class ContractV03(ContractV02):
    schema_version: Literal["0.3"]
    equations: list[Equation] = Field(default_factory=list)
    bindings: list[EquationBinding] = Field(default_factory=list)
    claims: list[Claim] = Field(min_length=1)
    assessments: list[Assessment] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_equation_links(self):
        _unique((_equation_key(e) for e in self.equations), "equation (ID, revision) pairs")
        _unique((b.id for b in self.bindings), "binding IDs")
        equations = {_equation_key(e): e for e in self.equations}
        bindings = {b.id: b for b in self.bindings}
        subjects = {s.id: s for s in self.subjects}
        evidence = {e.id for e in self.evidence}
        for equation in self.equations:
            sources = _unique(equation.evidence, "equation evidence references")
            if sources - evidence:
                raise ValueError("Unknown equation evidence")
        for binding in self.bindings:
            equation = equations.get(_equation_key(binding.equation))
            subject = subjects.get(binding.subject)
            if equation is None or subject is None:
                raise ValueError("Unknown binding equation revision or Subject")
            if binding.source not in subject.selected_files:
                raise ValueError("Binding source must be recorded in Subject.selected_files")
            if f"{binding.source}:{binding.symbol}" not in subject.implementation.entry_points:
                raise ValueError("Binding function must be a recorded Subject entry point")
            mapped = {a.symbol for a in binding.arguments.values()} | binding.constants.keys()
            if binding.result is not None:
                mapped.add(binding.result)
            if mapped - equation.symbols.keys():
                raise ValueError("Unknown equation symbol in binding")
        claims = {(c.id, c.revision): c for c in self.claims}
        for claim in self.claims:
            referenced = _unique((_equation_key(e) for e in claim.equations), "Claim equation references")
            if referenced - equations.keys():
                raise ValueError("Unknown Claim equation revision")
        for assessment in self.assessments:
            if not isinstance(assessment, SupportAssessment):
                continue
            claim = claims[assessment.claim, assessment.claim_revision]
            referenced = {_equation_key(e) for e in claim.equations}
            pinned = _unique((_equation_key(p) for p in assessment.equation_pins), "equation pins")
            if pinned - referenced:
                raise ValueError("Equation pins must refer to assessed Claim equations")
            if assessment.status in {"supported", "contradicted"} and pinned != referenced:
                raise ValueError(f"{assessment.status.capitalize()} assessments must pin every Claim equation")
            binding_ids = _unique((p.id for p in assessment.binding_pins), "binding pins")
            if binding_ids - bindings.keys():
                raise ValueError("Unknown pinned binding")
            for key in binding_ids:
                binding = bindings[key]
                if binding.subject != assessment.subject or _equation_key(binding.equation) not in pinned:
                    raise ValueError("Pinned binding must match the assessed Subject and pinned equations")
        return self
