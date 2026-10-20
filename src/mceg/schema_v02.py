"""Version 0.2 records: propositions, evaluated subjects, and scoped judgments."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from .schema import (Domain, Evidence as Evidence01, Implementation, Model,
                     Record as Record01, Statement, Text, _evidence_graph)


Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Unit = Literal["K", "Pa", "bar", "MPa", "GPa"]
QuantityName = Literal[
    "temperature", "pressure", "melt_total_pressure", "hydrogen_fugacity",
    "water_partial_pressure", "carbon_dioxide_partial_pressure",
    "carbon_monoxide_fugacity", "methane_fugacity", "nitrogen_partial_pressure",
    "water_fugacity", "helium_fugacity",
]
SCALE = {"K": 1, "Pa": 1, "bar": 100000, "MPa": 1000000, "GPa": 1000000000}


class Record(Record01):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Quantity(Record):
    value: float
    unit: Unit


def canonical_quantity(name, quantity):
    """Preserve quantity identity; total pressure and fugacity are not aliases."""
    if (name == "temperature") != (quantity.unit == "K"):
        raise ValueError(f"Incompatible unit for {name}: {quantity.unit}")
    if quantity.value < 0 or (name == "temperature" and quantity.value == 0):
        raise ValueError(f"Invalid {name}: {quantity.value}")
    return Decimal(str(quantity.value)) * SCALE[quantity.unit]


class Context(Record):
    id: Text
    scope: Text
    quantities: dict[QuantityName, Quantity] = Field(default_factory=dict)
    settings: dict[Text, Text | int | float | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_quantities(self):
        for name, value in self.quantities.items():
            canonical_quantity(name, value)
        return self


class Subject(Record):
    id: Text
    implementation: Implementation
    selected_files: dict[Text, Digest | None] = Field(default_factory=dict)


class Claim(Record):
    id: Text
    revision: Text
    statement: Text
    kind: Literal["theoretical", "numerical_verification", "physical_validation"]
    scope: Text


class Artifact(Record):
    source: Text
    sha256: Digest


class Evidence(Evidence01):
    subject: Text | None = None
    context: Text | None = None
    artifacts: list[Artifact] = Field(default_factory=list)


class Interval(Record):
    lower: float
    upper: float
    unit: Unit
    closure: Literal["closed"] = "closed"


class RangeCondition(Record):
    id: Text
    revision: Text
    kind: Literal["range"]
    quantity: QuantityName
    interval: Interval
    coverage: Literal["marginal", "numerical_evaluation"]
    scope: Text
    evidence: list[Text] = Field(min_length=1)

    @model_validator(mode="after")
    def ordered_bounds(self):
        for value in (self.interval.lower, self.interval.upper):
            canonical_quantity(self.quantity, Quantity(value=value, unit=self.interval.unit))
        if self.interval.lower > self.interval.upper:
            raise ValueError("Interval lower bound exceeds upper bound")
        return self


class SampleCondition(Record):
    id: Text
    revision: Text
    kind: Literal["samples"]
    # Every entry is one joint sample, never an implied Cartesian product.
    samples: list[Context] = Field(min_length=1)
    scope: Text
    evidence: list[Text] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent_samples(self):
        first = self.samples[0]
        if len({s.id for s in self.samples}) != len(self.samples):
            raise ValueError("Sample IDs must be unique within a condition")
        if not first.quantities and not first.settings:
            raise ValueError("A sample needs at least one quantity or setting")
        signatures = []
        for sample in self.samples:
            if sample.quantities.keys() != first.quantities.keys() or sample.settings.keys() != first.settings.keys():
                raise ValueError("Samples must describe the same quantities and settings")
            signature = (tuple((k, canonical_quantity(k, v)) for k, v in sorted(sample.quantities.items())),
                         tuple((k, type(v).__name__, v) for k, v in sorted(sample.settings.items())))
            signatures.append(signature)
        if len(signatures) != len(set(signatures)):
            raise ValueError("Duplicate numerical samples")
        return self


Condition = Annotated[RangeCondition | SampleCondition, Field(discriminator="kind")]


class Method(Record):
    id: Text
    revision: Text
    description: Text


class AssessmentBase(Record):
    id: Text
    subject: Text
    context: Text
    method: Method
    evidence: list[Text]
    reasons: list[Text] = Field(min_length=1)


class SupportAssessment(AssessmentBase):
    kind: Literal["evidence_support"]
    claim: Text
    claim_revision: Text
    status: Literal["supported", "unknown"]
    origin: Literal["imported_v0.1_declaration", "reviewed"]


class RangeAssessment(AssessmentBase):
    kind: Literal["range_membership"]
    condition: Text
    condition_revision: Text
    classification: Literal["within_reported_range", "outside_reported_range", "unknown"]


class SampleAssessment(AssessmentBase):
    kind: Literal["sample_membership"]
    condition: Text
    condition_revision: Text
    classification: Literal["at_recorded_sample", "not_sampled", "unknown"]


Assessment = Annotated[SupportAssessment | RangeAssessment | SampleAssessment, Field(discriminator="kind")]


class FollowUp(Record):
    """Human-authored work instructions; never executable code or proof of completion."""
    id: Text
    target_kind: Literal["evidence", "claim", "condition", "assessment"]
    target: Text
    revision: Text | None = None
    action: Text
    requires: list[Text] = Field(default_factory=list)
    completion: Text
    sources: list[Text] = Field(default_factory=list)


class Migration(Record):
    from_schema: Literal["0.1"]
    source_sha256: Digest
    content_sha256: Digest
    evidence_ids: list[Text] = Field(min_length=1)


class ContractV02(Record):
    schema_version: Literal["0.2"]
    model: Model
    assumptions: list[Statement]
    domains: list[Domain] = Field(min_length=1)
    claims: list[Claim] = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)
    limitations: list[Statement]
    subjects: list[Subject] = Field(min_length=1)
    contexts: list[Context] = Field(min_length=1)
    conditions: list[Condition] = Field(default_factory=list)
    assessments: list[Assessment] = Field(default_factory=list)
    follow_ups: list[FollowUp] = Field(default_factory=list)
    migration: Migration | None = None

    @model_validator(mode="after")
    def check_links(self):
        for name in ("evidence", "subjects", "contexts", "assessments", "follow_ups"):
            ids = [item.id for item in getattr(self, name)]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {name} IDs")
        claims = {(c.id, c.revision): c for c in self.claims}
        conditions = {(c.id, c.revision): c for c in self.conditions}
        if len(claims) != len(self.claims) or len(conditions) != len(self.conditions):
            raise ValueError("Claim and condition (ID, revision) pairs must be unique")
        evidence = _evidence_graph(self.evidence)
        if self.migration is not None and (
            len(set(self.migration.evidence_ids)) != len(self.migration.evidence_ids)
            or set(self.migration.evidence_ids) - evidence.keys()
        ):
            raise ValueError("Migration evidence IDs must be unique and identify retained evidence")
        if {c.id for c in self.claims} & evidence.keys():
            raise ValueError("Claim and evidence IDs must be distinct")
        subjects = {s.id for s in self.subjects}
        contexts = {c.id for c in self.contexts}
        for item in [*self.assumptions, *self.domains, *self.limitations, *self.conditions, *self.assessments]:
            if set(item.evidence) - evidence.keys():
                raise ValueError("Unknown evidence references")
        for item in self.evidence:
            if item.subject is not None and item.subject not in subjects:
                raise ValueError("Unknown evidence subject")
            if item.context is not None and item.context not in contexts:
                raise ValueError("Unknown evidence context")
        for item in self.assessments:
            if item.subject not in subjects or item.context not in contexts:
                raise ValueError("Unknown assessment subject or context")
            if isinstance(item, SupportAssessment):
                if item.origin == "imported_v0.1_declaration" and (
                    self.migration is None or item.claim_revision != "sha256:" + self.migration.source_sha256
                    or item.method.id != "import_v0.1_declaration"
                ):
                    raise ValueError("Imported assessments require the original migration identity and method")
                claim = claims.get((item.claim, item.claim_revision))
                if claim is None:
                    raise ValueError("Unknown assessed Claim revision")
                if item.status == "supported":
                    linked = [evidence[key] for key in item.evidence]
                    kinds = {"theoretical": {"theory"}, "physical_validation": {"experiment", "observation"},
                             "numerical_verification": {"numerical_test", "benchmark"}}[claim.kind]
                    if not any(e.kind in kinds and (claim.kind != "numerical_verification" or e.result == "passed")
                               for e in linked):
                        raise ValueError("Supported assessment lacks matching evidence")
            else:
                condition = conditions.get((item.condition, item.condition_revision))
                expected = "range" if isinstance(item, RangeAssessment) else "samples"
                if condition is None or condition.kind != expected:
                    raise ValueError("Unknown or incompatible assessed Condition revision")
                if set(condition.evidence) - set(item.evidence):
                    raise ValueError("Membership assessments must retain their Condition's evidence references")
        references = {"evidence": {(e.id, None) for e in self.evidence}, "claim": set(claims),
                      "condition": set(conditions), "assessment": {(a.id, None) for a in self.assessments}}
        for action in self.follow_ups:
            if (action.target, action.revision) not in references[action.target_kind]:
                raise ValueError("Unknown follow-up target; Claim/Condition targets require a revision")
        return self
