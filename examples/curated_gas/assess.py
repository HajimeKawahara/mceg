"""Reuse one reviewed numerical declaration under its recorded conditions.

This provider-free experiment is not a v0.2 schema or a general support rule.
It checks archived files; it does not execute ExoGibbs or FastChem.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mceg import load_contract
from mceg.schema import Text


HERE = Path(__file__).resolve().parent
IMPLEMENTATION = "src/exogibbs/presets/curated.py"
METHOD = "reviewed_curated_receipt_reuse_v1"


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Context(Record):
    temperature_K: float | None = Field(default=None, gt=0)
    pressure_bar: float | None = Field(default=None, gt=0)
    network: Literal["ions", "neutral"] | None = None
    composition: Text | None = None
    python: Text | None = None
    jax: Text | None = None
    backend: Text | None = None
    dtype: Text | None = None
    epsilon_crit: float | None = Field(default=None, gt=0)


class FilePin(Record):
    path: Text
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Review(Record):
    format: Literal["curated_receipt_review_v1"]
    repository: Text
    audited_revision: Text
    contract: FilePin
    receipt: FilePin
    composition: Literal["asplund_2021_normalized_nuclear"]
    numerical_temperature_K: list[float] = Field(min_length=2, max_length=2)
    rationale: Text

    @model_validator(mode="after")
    def ordered_temperature_bounds(self):
        lower, upper = self.numerical_temperature_K
        if not 0 < lower <= upper:
            raise ValueError("Numerical temperature bounds must be positive and ordered")
        return self


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_path(root, name):
    if Path(name).is_absolute():
        raise ValueError("Evidence paths must be repository-relative")
    path = (root / name).resolve()
    path.relative_to(root.resolve())
    return path


def checked_pin(root, pin):
    path = local_path(root, pin.path)
    if sha256(path) != pin.sha256:
        raise ValueError(f"Reviewed record changed; review scope before repinning: {pin.path}")
    return path


def run(provider, inputs, review_path=HERE / "review.json"):
    provider = Path(provider).resolve()
    context = Context.model_validate(inputs)
    review = Review.model_validate(json.loads(review_path.read_text()))
    contract = load_contract(checked_pin(provider, review.contract))
    receipt_path = checked_pin(provider, review.receipt)
    receipt = json.loads(receipt_path.read_text())
    if contract.model.id != "exogibbs.curated_gas.v1":
        raise ValueError("This experiment requires the curated gas v1 contract")
    if contract.model.implementation.repository != review.repository:
        raise ValueError("The reviewed provider identity differs from the contract")
    claim = next(c for c in contract.claims if c.id == "equilibrium_verification")
    evidence = next(e for e in contract.evidence if e.id == "verification")
    if (claim.kind != "numerical_verification" or evidence.id not in claim.evidence
            or review.receipt.path not in evidence.sources):
        raise ValueError("The reviewed Claim/Evidence/receipt links must be preserved")
    expected = receipt["selected_file_sha256"]
    if contract.model.implementation.revision != "sha256:" + expected[IMPLEMENTATION]:
        raise ValueError("Contract implementation and receipt identities differ")

    files = []
    for kind, hashes, prefix in (("input", expected, Path()),
                                ("output", receipt["output_sha256"], Path(review.receipt.path).parent)):
        if not hashes:
            raise ValueError("A reviewed receipt needs input and output hashes")
        for name, digest in hashes.items():
            path = local_path(provider, str(prefix / name))
            actual = sha256(path) if path.is_file() else None
            files.append({"kind": kind, "path": path.relative_to(provider).as_posix(),
                          "expected_sha256": digest, "actual_sha256": actual,
                          "matches": actual == digest})
    intact = all(item["matches"] for item in files)
    temperature = context.temperature_K
    # The reviewed preset's continuous evaluation domain is distinct from its grid.
    lower, upper = review.numerical_temperature_K
    interval = ("unknown" if temperature is None else "within_reported_range"
                if lower <= temperature <= upper else "outside_reported_range")
    sampled = ("unknown" if any(getattr(context, key) is None for key in
                               ("temperature_K", "pressure_bar", "network"))
               else "at_recorded_sample" if temperature in receipt["temperature_K"]
               and context.pressure_bar in receipt["pressure_bar"] else "not_sampled")
    missing = [key for key in Context.model_fields if getattr(context, key) is None]
    settings = {key: receipt[key] for key in ("python", "jax", "backend", "dtype", "epsilon_crit")}
    settings["composition"] = review.composition
    different = [key for key, value in settings.items()
                 if getattr(context, key) is not None and getattr(context, key) != value]
    completed = (receipt["fastchem"] == "passed"
                 and receipt["cases_passed"] == receipt["fastchem_cases_passed"] == 70)
    reasons = []
    if not intact:
        reasons.append("selected_files_changed_or_missing")
    if not completed or evidence.result != "passed" or claim.status != "supported":
        reasons.append("recorded_support_incomplete")
    if missing:
        reasons.append("missing_context")
    if different:
        reasons.append("unreviewed_context")
    if sampled != "at_recorded_sample":
        reasons.append("no_recorded_sample")
    if interval == "outside_reported_range":
        reasons.append("outside_evaluation_domain")
    context_record = context.model_dump(exclude_none=True)
    return {
        "format": "curated_receipt_assessment_v1",
        "review": review.model_dump(), "review_sha256": sha256(review_path),
        "evaluator_sha256": sha256(Path(__file__)),
        "context": context_record,
        "context_sha256": hashlib.sha256(json.dumps(context_record, sort_keys=True).encode()).hexdigest(),
        "imported_declaration": {"origin": "imported_v0.1_declaration", "claim": claim.model_dump()},
        "evidence": {"id": evidence.id, "result": evidence.result,
                     "fastchem": receipt["fastchem"], "fastchem_cases_passed": receipt["fastchem_cases_passed"],
                     "scope": evidence.scope},
        "integrity": {"selected_files_match": intact, "files": files},
        "assessments": [
            {"kind": "range_membership", "condition": "reviewed_numerical_temperature",
             "interval": {"lower": lower, "upper": upper, "unit": "K", "closure": "closed"},
             "classification": interval},
            {"kind": "sample_membership", "evidence": evidence.id,
             "classification": sampled, "interpolation": "not_assessed"},
            {"kind": "evidence_support", "method": METHOD,
             "target": {"claim": claim.id, "contract_sha256": review.contract.sha256,
                        "implementation_sha256": {item["path"]: item["actual_sha256"]
                                                  for item in files if item["kind"] == "input"}},
             "evidence": [evidence.id], "status": "unknown" if reasons else "supported",
             "reasons": reasons or ["reviewed_declaration_reused"],
             "missing_context": missing, "different_context": different},
        ],
        "physical_validation": "unknown",
        "not_evaluated": ["new_numerical_execution", "complete_transitive_dependencies",
                          "other_claims", "source_adoption_choices", "physical_accuracy"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exogibbs", type=Path, required=True)
    parser.add_argument("--context", type=Path, default=HERE / "context.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run(args.exogibbs, json.loads(args.context.read_text()))
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}; archived numerical evidence only; physical validation unknown")


if __name__ == "__main__":
    main()
