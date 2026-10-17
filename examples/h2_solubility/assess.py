"""Compare H2 inputs with source-specific intervals, independently of the EOS run.

This example produces range assessments, not Claim support or physical validation.
It uses only MCEG's existing dependencies; neither provider nor JAX is imported.
"""

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml

from mceg import load_contract
from mceg.schema import Text
from mceg.validator import _UniqueKeyLoader


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
METHOD = "closed_interval_v1"
Unit = Literal["K", "Pa", "bar", "MPa", "GPa"]
SCALE = {"K": 1, "Pa": 1, "bar": 100000, "MPa": 1000000, "GPa": 1000000000}


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Quantity(Record):
    value: float
    unit: Unit


def checked_quantity(name, quantity):
    """Check the physical quantity as well as the dimensional unit."""
    is_temperature = name == "temperature"
    if (quantity.unit == "K") != is_temperature:
        raise ValueError(f"Incompatible unit for {name}: {quantity.unit}")
    if quantity.value < 0 or (is_temperature and quantity.value == 0):
        raise ValueError(f"Invalid {name}: {quantity.value}")
    return Decimal(str(quantity.value)) * SCALE[quantity.unit]


class Context(Record):
    temperature: Quantity | None = None
    melt_total_pressure: Quantity | None = None
    hydrogen_fugacity: Quantity | None = None

    @model_validator(mode="after")
    def check_quantities(self):
        for name in type(self).model_fields:
            quantity = getattr(self, name)
            if quantity is not None:
                checked_quantity(name, quantity)
        return self


class Interval(Record):
    lower: float
    upper: float
    unit: Unit
    closure: Literal["closed"]


class Condition(Record):
    id: Text
    quantity: Literal["temperature", "melt_total_pressure"]
    interval: Interval
    coverage: Literal["marginal"]
    scope: Text
    evidence: list[Text] = Field(min_length=1)

    @model_validator(mode="after")
    def check_interval(self):
        bounds = self.interval
        for value in (bounds.lower, bounds.upper):
            checked_quantity(self.quantity, Quantity(value=value, unit=bounds.unit))
        if bounds.lower > bounds.upper:
            raise ValueError("Interval lower bound exceeds upper bound")
        return self


class Conditions(Record):
    format: Literal["h2_range_conditions_v1"]
    contract: Text
    contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    conditions: list[Condition] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_conditions(self):
        ids = [condition.id for condition in self.conditions]
        if len(ids) != len(set(ids)):
            raise ValueError("Condition IDs must be unique")
        return self


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(condition, context, contract_path):
    result = {"condition": condition.id, "kind": "range_membership", "method": METHOD,
              **condition.model_dump(exclude={"id", "evidence"}),
              "evidence": [f"{contract_path}#{key}" for key in condition.evidence]}
    quantity = getattr(context, condition.quantity)
    if quantity is None:
        return {**result, "classification": "unknown", "reason": "missing_input"}
    # Decimal scaling avoids changing boundary inclusion through unit roundoff.
    value = checked_quantity(condition.quantity, quantity) / SCALE[condition.interval.unit]
    lower, upper = Decimal(str(condition.interval.lower)), Decimal(str(condition.interval.upper))
    reason = "below_lower_bound" if value < lower else "above_upper_bound" if value > upper else "within_bounds"
    return {**result, "evaluated_value": str(value),
            "classification": "within_reported_range" if lower <= value <= upper else "outside_reported_range",
            "reason": reason}


def run(inputs, conditions_path=HERE / "conditions.yaml"):
    context = Context.model_validate(inputs)
    with conditions_path.open(encoding="utf-8") as stream:
        conditions = Conditions.model_validate(yaml.load(stream, Loader=_UniqueKeyLoader))
    contract_path = (ROOT / conditions.contract).resolve()
    contract_name = contract_path.relative_to(ROOT).as_posix()
    if sha256(contract_path) != conditions.contract_sha256:
        raise ValueError("Contract changed; review the source-specific conditions before reassessment")
    contract = load_contract(contract_path)
    if contract.model.id != "exogibbs.h2_hirschmann2012":
        raise ValueError("This example requires the H2 solubility contract")
    evidence_ids = {item.id for item in contract.evidence}
    for condition in conditions.conditions:
        missing = set(condition.evidence) - evidence_ids
        if missing:
            raise ValueError(f"Unknown condition evidence: {sorted(missing)}")
    context_record = context.model_dump(exclude_none=True)
    return {
        "format": "h2_range_assessment_v1",
        "context": context_record,
        "context_sha256": hashlib.sha256(json.dumps(context_record, sort_keys=True).encode()).hexdigest(),
        "conditions_sha256": sha256(conditions_path),
        "evaluator_sha256": sha256(Path(__file__)),
        "contract": {"path": contract_name, "sha256": conditions.contract_sha256,
                     "model": contract.model.id, "implementation": contract.model.implementation.model_dump()},
        "assessments": [compare(condition, context, contract_name) for condition in conditions.conditions],
        "physical_validation": "unknown",
        "not_evaluated": {
            "material_scope_match": "No melt composition is supplied or matched to the sources.",
            "hydrogen_fugacity_coverage": "No experimental fugacity interval is established; total pressure cannot replace it.",
            "joint_domain_coverage": "Separate marginal intervals do not establish joint calibration coverage.",
            "calibration_accuracy": "The retained concentration calibration has not been validated for this context.",
            "eos_and_combined_accuracy": "No EOS execution, measurement comparison or uncertainty bound is supplied by this assessment.",
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--temperature-k", type=float, help="Omit for an unknown temperature")
    parser.add_argument("--melt-pressure", type=float, help="Actual melt total pressure, not H2 fugacity")
    parser.add_argument("--pressure-unit", choices=["Pa", "bar", "MPa", "GPa"], default="bar")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    inputs = {}
    if args.temperature_k is not None:
        inputs["temperature"] = {"value": args.temperature_k, "unit": "K"}
    if args.melt_pressure is not None:
        inputs["melt_total_pressure"] = {"value": args.melt_pressure, "unit": args.pressure_unit}
    try:
        result = run(inputs)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}; range comparisons only; physical validation unknown")


if __name__ == "__main__":
    main()
