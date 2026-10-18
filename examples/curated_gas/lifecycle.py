"""Reproduce the migration, environment transition and one dependency probe."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile

from mceg import load_contract
from reassess import ADOPTION, DATA, HERE, assess_execution, migrate, sha256


def compact(report):
    return {"assessment_id": report["assessment"]["id"],
            "claim_revision": report["assessment"]["target"]["claim_revision"],
            "status": report["assessment"]["status"], "reasons": report["assessment"]["reasons"],
            "evidence_id": report["evidence"]["id"], "evidence_result": report["evidence"]["result"],
            "checks": report["evidence"]["checks"],
            "environment": report["assessment"]["context"]["environment"],
            "dependency_review": report["dependency_review"]}


def migration_check(path):
    original, draft = load_contract(path).model_dump(), migrate(path)
    restored = {k: deepcopy(draft[k]) for k in original if k != "schema_version"}
    restored["schema_version"] = "0.1"
    for claim, assessment in zip(restored["claims"], draft["assessments"]):
        del claim["revision"]
        claim.update(status=assessment["status"], evidence=assessment["evidence"])
    if restored != original:
        raise ValueError("Migration lost original declarations")
    return {"contract_sha256": sha256(path), "model": original["model"]["id"],
            "claims_preserved": len(original["claims"]), "evidence_preserved": len(original["evidence"]),
            "round_trip_equal": True, "claim_text_rewritten": False}


def run(provider):
    provider = Path(provider).resolve()
    old_run, new_run = HERE / "runs/jax-0.6.2", HERE / "runs/jax-0.10.2"
    first, second = assess_execution(provider, old_run), assess_execution(provider, new_run)
    before = assess_execution(provider, old_run, second["assessment"]["context"]["environment"])
    review = json.loads((HERE / "review.json").read_text())
    paths = set(first["evidence"]["execution"]["selected_input_sha256"])
    paths.update((ADOPTION, review["contract"]["path"], review["receipt"]["path"]))
    with tempfile.TemporaryDirectory(prefix="mceg_dependency_") as temporary:
        copy = Path(temporary)
        for name in paths:
            destination = copy / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(provider / name, destination)
        adoption = json.loads((copy / ADOPTION).read_text())
        adoption["choices"]["H2O"]["status"] = "retain_provisionally"
        (copy / ADOPTION).write_text(json.dumps(adoption, indent=2) + "\n")
        source_changed = assess_execution(copy, new_run)
        data = json.loads((copy / DATA).read_text())
        species = sorted(data["nasa9_reactions"])[0]
        data["nasa9_reactions"][species][7] += 1.
        (copy / DATA).write_text(json.dumps(data, indent=2) + "\n")
        data_changed = assess_execution(copy, new_run)
    return {
        "format": "curated_lifecycle_trial_v1",
        "generator_sha256": sha256(Path(__file__)),
        "evaluator_sha256": first["evaluator_sha256"],
        "review_sha256": first["review_sha256"],
        "migration": [migration_check(HERE.parents[1] / "contracts/h2_solubility.yaml"),
                      migration_check(provider / review["contract"]["path"])],
        "historical_evidence": first["historical_evidence"],
        "environment_transition": {"baseline": compact(first), "new_environment_before_rerun": compact(before),
                                   "new_environment_after_rerun": compact(second)},
        "dependency_probe": {
            "synthetic": True,
            "mutations": ["Set the copied H2O adoption status to retain_provisionally.",
                          f"Add 1 K to the copied {species} NASA9 coefficient at index 7."],
            "source_record_changed": compact(source_changed), "packaged_data_changed": compact(data_changed),
            "interpretation": "Changes are confined to temporary copies; no altered model was executed or adopted. Old numerical outcomes remain passed. Source alignment and current numerical support are separate assessments."},
        "physical_validation": "unknown",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exogibbs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(args.exogibbs), indent=2, allow_nan=False) + "\n")
