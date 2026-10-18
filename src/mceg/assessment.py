"""Evaluate explicit conditions without inferring Claim support or physical accuracy."""

import argparse
from pathlib import Path

import yaml

from .migration import content_hash, write_document
from .schema_v02 import (Context, ContractV02, RangeCondition, canonical_quantity)
from .validator import load_contract, read_document


def compare_condition(condition, context):
    """Return a membership classification and reasons, never a support status."""
    if isinstance(condition, RangeCondition):
        quantity = context.quantities.get(condition.quantity)
        if quantity is None:
            return "unknown", [f"Missing quantity: {condition.quantity}"]
        value = canonical_quantity(condition.quantity, quantity)
        bounds = condition.interval
        lower = canonical_quantity(condition.quantity, type(quantity)(value=bounds.lower, unit=bounds.unit))
        upper = canonical_quantity(condition.quantity, type(quantity)(value=bounds.upper, unit=bounds.unit))
        classification = "within_reported_range" if lower <= value <= upper else "outside_reported_range"
        return classification, [f"{quantity.value:g} {quantity.unit} compared with closed interval "
                                f"{bounds.lower:g}--{bounds.upper:g} {bounds.unit}; {condition.coverage} coverage only."]
    first = condition.samples[0]
    missing = sorted((first.quantities.keys() - context.quantities.keys()) |
                     (first.settings.keys() - context.settings.keys()))
    if missing:
        return "unknown", ["Missing sample coordinates: " + ", ".join(missing)]
    for sample in condition.samples:
        quantities_match = all(canonical_quantity(k, value) == canonical_quantity(k, context.quantities[k])
                               for k, value in sample.quantities.items())
        settings_match = all(type(value) is type(context.settings[k]) and value == context.settings[k]
                             for k, value in sample.settings.items())
        if quantities_match and settings_match:
            return "at_recorded_sample", ["An explicitly recorded joint sample matches; other context fields are not evaluated."]
    return "not_sampled", ["No recorded joint sample matches; interpolation and physical accuracy are not assessed."]


def assess_conditions(contract: ContractV02, context: Context, subject: str) -> ContractV02:
    """Append context-bound membership assessments to a copy, preserving all history."""
    if not isinstance(contract, ContractV02):
        raise ValueError("Condition assessment requires a v0.2 contract; use mceg migrate first")
    if not contract.conditions:
        raise ValueError("No structured conditions; add reviewed source-scoped conditions before assessment")
    subjects = {s.id: s for s in contract.subjects}
    if subject not in subjects:
        raise ValueError(f"Unknown subject {subject!r}; choose from {sorted(subjects)}")
    existing = next((c for c in contract.contexts if c.id == context.id), None)
    if existing is not None and existing != context:
        raise ValueError("Context ID already describes different inputs; use a new ID to preserve history")
    data = contract.model_dump()
    if existing is None:
        data["contexts"].append(context.model_dump())
    previous = {a.id: a for a in contract.assessments}
    evidence = {e.id: e for e in contract.evidence}
    for condition in contract.conditions:
        classification, reasons = compare_condition(condition, context)
        is_range = isinstance(condition, RangeCondition)
        record = {
            "kind": "range_membership" if is_range else "sample_membership",
            "subject": subject, "context": context.id, "condition": condition.id,
            "condition_revision": condition.revision, "evidence": condition.evidence,
            "method": {"id": "closed_interval" if is_range else "exact_joint_samples", "revision": "1",
                       "description": "Compare supplied coordinates only; no scientific support inference."},
            "classification": classification, "reasons": reasons,
        }
        record["id"] = "assessment:" + content_hash({
            "assessment": record, "condition": condition.model_dump(), "context": context.model_dump(),
            "subject": subjects[subject].model_dump(),
            "evidence": [evidence[k].model_dump() for k in condition.evidence],
        })
        if record["id"] in previous and previous[record["id"]].model_dump() != record:
            raise ValueError("An existing assessment ID contains different content; preserve and review that record")
        if record["id"] not in previous:
            data["assessments"].append(record)
    return ContractV02.model_validate(data)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mceg assess", description=__doc__)
    parser.add_argument("contract", type=Path, nargs="?")
    parser.add_argument("--curated", type=Path, help="ExoGibbs checkout for the existing reviewed curated-gas reuse policy")
    parser.add_argument("--context", type=Path, required=True,
                        help="v0.2 Context, or the existing flat curated JSON context when --curated is used")
    parser.add_argument("--subject", help="Evaluated Subject ID; required for a v0.2 contract")
    parser.add_argument("--output", type=Path, required=True, help="New contract with appended assessments; never overwritten")
    args = parser.parse_args(argv)
    try:
        if bool(args.contract) == bool(args.curated):
            raise ValueError("Specify a v0.2 contract or --curated CHECKOUT, but not both")
        if args.curated:
            if args.subject:
                raise ValueError("--curated identifies its subject from the observed files; omit --subject")
            from .curated import assess_curated
            result = assess_curated(args.curated, read_document(args.context))
        else:
            if not args.subject:
                raise ValueError("A v0.2 condition assessment requires --subject ID")
            result = assess_conditions(load_contract(args.contract), Context.model_validate(read_document(args.context)),
                                       args.subject)
        write_document(result.model_dump(exclude_none=True), args.output)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        parser.error(str(exc))
    print(f"Wrote {args.output}; scoped assessments added, historical declarations preserved")
    return 0
