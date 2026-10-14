"""Experimental v0.1 data structure, not a scientific validity checker."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Implementation(Record):
    repository: Text
    revision: Text
    entry_points: list[Text] = Field(min_length=1)


class Model(Record):
    id: Text
    name: Text
    description: Text
    implementation: Implementation


class Statement(Record):
    statement: Text
    evidence: list[Text] = Field(min_length=1)


class Domain(Record):
    kind: Literal["scientific_applicability", "numerical_evaluation"]
    status: Literal["documented", "unknown"]
    description: Text
    conditions: list[Text]
    evidence: list[Text] = Field(min_length=1)

    @model_validator(mode="after")
    def check_conditions(self) -> "Domain":
        if self.status == "documented" and not self.conditions:
            raise ValueError("A documented domain needs conditions")
        if self.status == "unknown" and self.conditions:
            raise ValueError("An unknown domain must not assert conditions")
        return self


class SourceLink(Record):
    evidence: Text
    comparison: Literal["not_checked", "consistent", "discrepancy"]
    note: Text


class Provenance(Record):
    role: Literal["primary", "secondary", "implementation", "unknown"]
    location: Text
    inspection: Literal["not_inspected", "partial", "inspected"]
    note: Text
    derived_from: list[SourceLink] = Field(default_factory=list)


class Evidence(Record):
    id: Text
    kind: Literal[
        "implementation", "theory", "numerical_test", "benchmark",
        "experiment", "observation", "literature",
    ]
    summary: Text
    sources: list[Text] = Field(min_length=1)
    scope: Text
    result: Literal["passed", "failed", "not_run", "unknown"] | None = None
    provenance: Provenance | None = None

    @model_validator(mode="after")
    def check_result(self) -> "Evidence":
        numerical = self.kind in {"numerical_test", "benchmark"}
        if numerical != (self.result is not None):
            raise ValueError("Only numerical tests and benchmarks require a result")
        return self


class Claim(Record):
    id: Text
    statement: Text
    kind: Literal["theoretical", "numerical_verification", "physical_validation"]
    status: Literal["supported", "unknown"]
    scope: Text
    evidence: list[Text]


class Contract(Record):
    schema_version: Literal["0.1"]
    model: Model
    assumptions: list[Statement]
    domains: list[Domain] = Field(min_length=1)
    claims: list[Claim] = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)
    limitations: list[Statement]

    @model_validator(mode="after")
    def check_links(self) -> "Contract":
        ids = [item.id for item in self.evidence] + [item.id for item in self.claims]
        if len(ids) != len(set(ids)):
            raise ValueError("Claim and evidence IDs must be unique within a contract")
        evidence = {item.id: item for item in self.evidence}
        parents = {}
        for item in self.evidence:
            links = item.provenance.derived_from if item.provenance else []
            targets = [link.evidence for link in links]
            if len(targets) != len(set(targets)):
                raise ValueError(f"Duplicate provenance links for {item.id!r}")
            missing = set(targets) - evidence.keys()
            if missing:
                raise ValueError(f"Unknown provenance references: {sorted(missing)}")
            parents[item.id] = set(targets)
            for link in links:
                if link.comparison != "not_checked":
                    upstream = evidence[link.evidence].provenance
                    if (item.provenance.inspection != "inspected" or upstream is None
                            or upstream.inspection != "inspected"):
                        raise ValueError("A recorded comparison requires both sources to be inspected")
        resolved = set()
        while parents:
            ready = {key for key, targets in parents.items() if targets <= resolved}
            if not ready:
                raise ValueError("Provenance links must not contain a cycle")
            resolved.update(ready)
            for key in ready:
                del parents[key]
        for item in [*self.assumptions, *self.domains, *self.claims, *self.limitations]:
            missing = set(item.evidence) - evidence.keys()
            if missing:
                raise ValueError(f"Unknown evidence references: {sorted(missing)}")
        for claim in self.claims:
            if claim.status == "unknown":
                continue
            linked = [evidence[key] for key in claim.evidence]
            if claim.kind == "theoretical":
                supported = any(item.kind == "theory" for item in linked)
            elif claim.kind == "numerical_verification":
                supported = any(
                    item.kind in {"numerical_test", "benchmark"} and item.result == "passed"
                    for item in linked
                )
            else:
                supported = any(item.kind in {"experiment", "observation"} for item in linked)
            if not supported:
                raise ValueError(f"Supported claim {claim.id!r} lacks matching evidence")
        return self
