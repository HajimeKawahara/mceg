"""Assess fresh archived executions for one explicitly revised numerical Claim.

This example reads files only. Its review policy is specific to the unchanged
curated validator and data, and is not a general inference engine or v0.2 API.
"""

import argparse
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path

from assess import Review, checked_pin, local_path, sha256
from migrate import migrate
from rerun import EXTRA_INPUTS, SCRIPT


HERE = Path(__file__).resolve().parent
DATA = "src/exogibbs/data/curated/gas_v1.json"
ADOPTION = "examples/comparisons/data/major_molecule_adoption.json"
OUTPUTS = {"thermal_checks.json", "diagnostics.csv", "default_charge.csv", "ions.npz",
           "neutral.npz", "fastchem_parity.csv"}


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def checked_artifact(root, name, digest):
    path = local_path(root, name)
    if sha256(path) != digest:
        raise ValueError(f"Recorded artifact changed: {name}")
    return path


def table_checks(path, scope, limits):
    expected = set(itertools.product(scope["networks"], scope["temperature_K"], scope["pressure_bar"]))
    seen, failures = set(), []
    maxima = dict.fromkeys(limits, 0.)
    with path.open() as stream:
        for row in csv.DictReader(stream):
            point = (row["network"], float(row["temperature_K"]), float(row["pressure_bar"]))
            if point in seen or point not in expected:
                raise ValueError("Duplicate or unexpected numerical sample")
            seen.add(point)
            for key, bound in limits.items():
                value = float(row[key])
                if not math.isfinite(value) or value < 0:
                    raise ValueError("Residuals must be finite and nonnegative")
                maxima[key] = max(maxima[key], value)
                if value > bound:
                    failures.append({"point": list(point), "metric": key, "value": value, "limit": bound})
    return {"complete": seen == expected, "samples": len(seen), "maxima": maxima, "failures": failures}


def dependency_review(provider, expected_data_hash):
    """One manually inspected edge; no arbitrary cross-contract propagation."""
    data_path = provider / DATA
    data = json.loads(data_path.read_text()) if data_path.is_file() else None
    recorded = data["source_sha256"][ADOPTION] if data is not None else None
    current = sha256(provider / ADOPTION) if (provider / ADOPTION).is_file() else None
    data_hash = sha256(data_path) if data is not None else None
    return {
        "path": [ADOPTION, DATA, "equilibrium_verification"],
        "adoption": {"recorded_sha256": recorded, "observed_sha256": current},
        "packaged_data": {"recorded_sha256": expected_data_hash, "observed_sha256": data_hash},
        "source_alignment": "unknown" if recorded is None else "consistent" if recorded == current else "review_required",
        "numerical_target": "unchanged" if data_hash == expected_data_hash else "review_required",
        "interpretation": "A changed adoption record requires source review. Numerical evidence still concerns the old packaged data; changed coefficients require separate numerical evidence. Hash agreement does not validate the adoption decision.",
    }


def assess_execution(provider, directory, environment=None):
    provider, directory = Path(provider).resolve(), Path(directory).resolve()
    review = Review.model_validate(json.loads((HERE / "review.json").read_text()))
    contract_path = checked_pin(provider, review.contract)
    archive = json.loads(checked_pin(provider, review.receipt).read_text())
    claim = json.loads((HERE / "claim_revision.json").read_text())
    policy = json.loads((HERE / "rerun_review.json").read_text())
    if sha256(HERE / "claim_revision.json") != policy["claim_revision_sha256"]:
        raise ValueError("Changed Claim or criteria require a new review")
    if claim["revises"]["contract_sha256"] != review.contract.sha256:
        raise ValueError("Claim revision must identify the reviewed original declaration")
    scope = claim["scope"]
    execution_path = directory / "execution.json"
    execution = json.loads(execution_path.read_text())
    if execution["format"] != "curated_execution_v1":
        raise ValueError("Unsupported execution format")
    checked_artifact(directory, "execution.log", execution["log_sha256"])
    recorded = execution["selected_input_sha256"]
    expected = archive["selected_file_sha256"]
    if set(recorded) != set(expected) | set(EXTRA_INPUTS):
        raise ValueError("Incomplete execution input manifest")
    if (recorded[SCRIPT] != policy["reviewed_script_sha256"]
            or any(recorded[k] != v for k, v in {**expected, **policy["extra_input_sha256"]}.items())
            or execution["provider_revision"] != policy["provider_revision"]
            or execution["fastchem_binary_sha256"] != policy["fastchem"]["binary_sha256"]):
        raise ValueError("Changed validator or scientific inputs need a new review")
    observed = {p: sha256(local_path(provider, p)) if local_path(provider, p).is_file() else None
                for p in recorded}
    actual_environment = execution["environment"]
    if environment is None:
        environment = actual_environment
    reasons = []
    if observed != recorded:
        reasons.append("current_inputs_changed_or_missing")
    if environment != actual_environment:
        reasons.append("environment_not_covered_by_execution")
    if not execution["inputs_unchanged_during_execution"]:
        reasons.append("inputs_changed_during_execution")
    checks = {}
    if execution["exit_code"] != 0:
        result = "failed"
        reasons.append("execution_failed")
    else:
        receipt = json.loads(checked_artifact(directory, "receipt.json", execution["receipt_sha256"]).read_text())
        if receipt["selected_file_sha256"] != expected or set(receipt["output_sha256"]) != OUTPUTS:
            raise ValueError("Receipt inputs or output manifest differ from the reviewed procedure")
        for name, digest in receipt["output_sha256"].items():
            checked_artifact(directory, name, digest)
        if (receipt["python"] != actual_environment["python"]
                or receipt["jax"] != actual_environment["packages"]["jax"]
                or receipt["backend"] != actual_environment["backend"]
                or receipt["dtype"] != actual_environment["dtype"]
                or receipt["fastchem_binary_sha256"] != execution["fastchem_binary_sha256"]):
            raise ValueError("Receipt and observed execution environment disagree")
        if (receipt["temperature_K"] != scope["temperature_K"]
                or receipt["pressure_bar"] != scope["pressure_bar"]
                or receipt["epsilon_crit"] != scope["epsilon_crit"]
                or receipt["dataset"] != "curated-gas-v1"
                or receipt["dtype"] != "float64" or receipt["backend"] != "cpu"):
            raise ValueError("Execution conditions require separate review")
        checks = {"exogibbs": table_checks(directory / "diagnostics.csv", scope, scope["exogibbs_maxima"]),
                  "fastchem": table_checks(directory / "fastchem_parity.csv", scope, scope["fastchem_maxima"])}
        complete = (all(c["complete"] for c in checks.values())
                    and receipt["cases_passed"] == receipt["fastchem_cases_passed"] == 70
                    and receipt["fastchem"] == "passed")
        failed = any(c["failures"] for c in checks.values())
        result = "failed" if failed else "passed" if complete else "unknown"
        if failed:
            reasons.append("numerical_comparison_failed")
        if not complete:
            reasons.append("incomplete_execution_coverage")
    evidence_id = "execution:" + sha256(execution_path)
    target = {"model": claim["revises"]["model"], "repository": review.repository, "claim": claim["id"],
              "claim_revision": sha256(HERE / "claim_revision.json"),
              "implementation_inputs": observed}
    context = {"scope": scope, "environment": environment,
               "fastchem_binary_sha256": execution["fastchem_binary_sha256"]}
    assessment = {"kind": "evidence_support",
                  "method": {"id": "reviewed_curated_rerun_v1", "evaluator_sha256": sha256(Path(__file__)),
                             "review_sha256": sha256(HERE / "rerun_review.json")},
                  "target": target, "context": context, "evidence": [evidence_id],
                  "status": "unknown" if reasons else "supported",
                  "reasons": reasons or ["reviewed_execution_covers_enumerated_conditions"]}
    assessment["id"] = identity(assessment)
    return {"format": "curated_lifecycle_assessment_v1", "claim_revision": claim,
            "imported_assessments": migrate(contract_path)["assessments"],
            "evidence": {"id": evidence_id, "result": result, "checks": checks,
                         "execution": execution, "scope": scope},
            "assessment": assessment,
            "dependency_review": dependency_review(provider, recorded[DATA]),
            "historical_evidence": {"contract_sha256": review.contract.sha256,
                                    "receipt_sha256": review.receipt.sha256, "result": "passed"},
            "review_sha256": sha256(HERE / "rerun_review.json"),
            "evaluator_sha256": sha256(Path(__file__)), "physical_validation": "unknown"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exogibbs", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(assess_execution(args.exogibbs, args.run), indent=2, allow_nan=False) + "\n")
