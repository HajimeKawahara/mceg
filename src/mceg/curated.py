"""Adapt the reviewed curated-gas policy to common v0.2 records."""

import itertools
import json
from pathlib import Path

from . import _curated
from .assessment import assess_conditions
from .migration import content_hash, migrate_contract
from .schema_v02 import Context, ContractV02


def assess_curated(provider, inputs, review_path=None) -> ContractV02:
    """Reuse the existing pinned policy; do not execute a solver or rank sources."""
    provider = Path(provider).resolve()
    report = (_curated.run(provider, inputs) if review_path is None else
              _curated.run(provider, inputs, review_path))
    data = migrate_contract(provider / report["review"]["contract"]["path"]).model_dump()
    files = report["integrity"]["files"]
    expected = {f["path"]: f["expected_sha256"] for f in files if f["kind"] == "input"}
    observed = {f["path"]: f["actual_sha256"] for f in files if f["kind"] == "input"}
    data["subjects"][0]["selected_files"] = expected
    current_id = "evaluated:" + content_hash(observed)
    implementation = dict(data["model"]["implementation"])
    current = observed[_curated.IMPLEMENTATION]
    implementation["revision"] = "sha256:" + current if current else "missing:" + _curated.IMPLEMENTATION
    data["subjects"].append({"id": current_id, "implementation": implementation, "selected_files": observed})
    quantities = {name: {"value": report["context"][key], "unit": unit}
                  for key, name, unit in (("temperature_K", "temperature", "K"), ("pressure_bar", "pressure", "bar"))
                  if key in report["context"]}
    context = Context(id="requested:" + report["context_sha256"], scope="Requested curated-gas calculation.",
                      quantities=quantities, settings={k: v for k, v in report["context"].items()
                                                       if k not in {"temperature_K", "pressure_bar"}})
    # This is the same archived execution, enriched with inspected metadata, not new evidence.
    receipt_path = _curated.checked_pin(provider, _curated.FilePin.model_validate(report["review"]["receipt"]))
    receipt = json.loads(receipt_path.read_text())
    archive = Context(id="archived-grid", scope="Both networks at the 70 explicitly enumerated samples.",
                      settings={**{k: receipt[k] for k in ("python", "jax", "backend", "dtype", "epsilon_crit")},
                                "composition": report["review"]["composition"]})
    data["contexts"].append(archive.model_dump())
    verification = next(e for e in data["evidence"] if e["id"] == "verification")
    verification.update(subject="imported", context=archive.id, artifacts=[
        {"source": report["review"]["receipt"]["path"], "sha256": report["review"]["receipt"]["sha256"]},
        *[{"source": f["path"], "sha256": f["expected_sha256"]} for f in files if f["kind"] == "output"],
    ])
    revision = "sha256:" + report["review_sha256"]
    lower, upper = report["review"]["numerical_temperature_K"]
    samples = [{"id": f"sample:{i}", "scope": "One archived joint numerical sample.",
                "quantities": {"temperature": {"value": t, "unit": "K"}, "pressure": {"value": p, "unit": "bar"}},
                "settings": {"network": network}}
               for i, (t, p, network) in enumerate(itertools.product(
                   receipt["temperature_K"], receipt["pressure_bar"], ("ions", "neutral")))]
    data["conditions"] = [
        {"id": "curated_temperature", "revision": revision, "kind": "range", "quantity": "temperature",
         "interval": {"lower": lower, "upper": upper, "unit": "K", "closure": "closed"},
         "coverage": "numerical_evaluation", "scope": "Reviewed numerical evaluation interval; no physical accuracy inference.",
         "evidence": ["implementation", "verification"]},
        {"id": "curated_samples", "revision": revision, "kind": "samples", "samples": samples,
         "scope": "Enumerated joint T/P/network samples; interpolation and other context settings are not evaluated here.",
         "evidence": ["verification"]},
    ]
    evaluated = assess_conditions(ContractV02.model_validate(data), context, current_id)
    data = evaluated.model_dump()
    support = report["assessments"][2]
    assessment = {
        "kind": "evidence_support", "claim": "equilibrium_verification",
        "claim_revision": "sha256:" + report["review"]["contract"]["sha256"],
        "subject": current_id, "context": context.id, "evidence": ["verification"],
        "status": support["status"], "origin": "reviewed",
        "method": {"id": _curated.METHOD,
                   "revision": "evaluator-sha256:" + report["evaluator_sha256"] + ";review-sha256:" + report["review_sha256"],
                   "description": report["review"]["rationale"]},
        "reasons": [*support["reasons"],
                    *["Missing context: " + key for key in support["missing_context"]],
                    *["Different context: " + key for key in support["different_context"]],
                    *[f"Changed or missing recorded file: {f['path']}; expected={f['expected_sha256']}; observed={f['actual_sha256']}"
                      for f in files if not f["matches"]]],
    }
    assessment["id"] = "support:" + content_hash(assessment)
    data["assessments"].append(assessment)
    return ContractV02.model_validate(data)
