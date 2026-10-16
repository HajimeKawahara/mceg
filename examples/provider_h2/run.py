"""Replay the fixed H2 case using contracts owned by two provider checkouts.

This example checks selected source identity separately from repository HEAD.
It preserves manual scientific assessments; it does not infer applicability.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import platform
import subprocess
import sys

import yaml

from mceg import load_contract


ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "examples/h2_solubility/case.yaml"
PROVIDERS = {
    "exoeos": {"role": "eos", "contract": "mceg/contracts/zhang_duan_h2.yaml",
               "required_files": {"src/exoeos/zhang_duan.py", "src/exoeos/helmholtz.py",
                                  "src/exoeos/constants.py", "src/exoeos/_arrays.py", "src/exoeos/state.py"}},
    "exogibbs": {"role": "solubility", "contract": "mceg/contracts/h2_solubility.yaml",
                 "required_files": {"src/exogibbs/solubility/volatile.py", "src/exogibbs/interop/exoeos.py",
                                    "src/exogibbs/utils/units.py"}},
}


def load_example(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASELINE = load_example("baseline_h2", ROOT / "examples/h2_solubility/run.py")
REFERENCES = load_example("provider_references", ROOT / "examples/provider_workflow/run.py")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def verify_snapshot(root, revision, hashes):
    """Require selected files to match both the saved hashes and audited Git objects."""
    if not hashes:
        raise ValueError("No selected source files were recorded")
    for name, expected in hashes.items():
        path = REFERENCES.local_path(root, name)
        original = git(root, "show", revision + ":" + name)
        if hashlib.sha256(original).hexdigest() != expected or sha256(path) != expected:
            raise ValueError(f"Review and rerun evidence after changing {name}")
    return {"audited_revision": revision,
            "checkout_revision": git(root, "rev-parse", "HEAD").decode().strip(),
            "selected_files_match_audit": True, "selected_file_sha256": hashes}


def scientific_record(contract):
    """Compare declarations, not scientific truth, before reusing the manual assessment."""
    return {
        "id": contract.model.id,
        "assumptions": [item.model_dump() for item in contract.assumptions],
        "domains": [item.model_dump() for item in contract.domains],
        "claims": [item.model_dump() for item in contract.claims if item.kind != "numerical_verification"],
        "evidence": [item.model_dump(exclude={"sources"}) for item in contract.evidence
                     if item.kind not in {"numerical_test", "benchmark"}],
        "limitations": [item.model_dump() for item in contract.limitations],
    }


def inspect_provider(owner, root, baseline_contract):
    config = PROVIDERS[owner]
    contract_path = root / config["contract"]
    contract = load_contract(contract_path)
    if scientific_record(contract) != scientific_record(baseline_contract):
        raise ValueError(f"{owner}: changed scientific declarations need a new manual assessment")
    references = REFERENCES.check_sources(contract_path, root)
    if not references["local_files_complete"]:
        raise ValueError(f"{owner}: missing local evidence files")
    execution = next(item for item in contract.evidence if item.id == "provider_test_run")
    receipt_name = next(name for name in execution.sources if name.endswith(".json"))
    receipt_path = REFERENCES.local_path(root, receipt_name)
    receipt = json.loads(receipt_path.read_text())
    if receipt["audited_revision"] != contract.model.implementation.revision:
        raise ValueError(f"{owner}: contract and execution revision differ")
    outcome = receipt["outcome"]
    if execution.result != "passed" or outcome["passed"] <= 0 or any(outcome[k] for k in ("failed", "errors", "skipped")):
        raise ValueError(f"{owner}: the selected pilot run did not pass completely")
    hashes = receipt["selected_file_sha256"]
    if not config["required_files"] <= hashes.keys():
        raise ValueError(f"{owner}: missing required source identities")
    snapshot = verify_snapshot(root, receipt["audited_revision"], hashes)
    if sha256(REFERENCES.local_path(root, receipt["junit_xml"])) != receipt["junit_sha256"]:
        raise ValueError(f"{owner}: execution artifact changed")
    return contract, {
        **snapshot, "repository": contract.model.implementation.repository,
        "contract_path": config["contract"], "contract_sha256": sha256(contract_path),
        "execution_path": receipt_name, "execution_sha256": sha256(receipt_path),
        "reference_checks": references,
    }, receipt


def run(checkouts):
    case = yaml.safe_load(CASE.read_text())
    if case["inputs"] != BASELINE.AUDITED_INPUTS:
        raise ValueError("Changed inputs need a new manual audit")
    contracts, records, receipts = {}, {}, {}
    for owner, config in PROVIDERS.items():
        baseline = load_contract(ROOT / case["components"][config["role"]])
        contracts[owner], records[owner], receipts[owner] = inspect_provider(owner, checkouts[owner], baseline)
    dependency = receipts["exogibbs"]["dependencies"]["exoeos"]
    verify_snapshot(checkouts["exoeos"], dependency["revision"], dependency["selected_file_sha256"])

    for root in checkouts.values():
        sys.path.insert(0, str(root / "src"))
    import jax
    jax.config.update("jax_platforms", "cpu")
    jax.config.update("jax_enable_x64", True)
    import exoeos
    import exogibbs
    import jax.numpy as jnp
    from exogibbs.interop.exoeos import make_pure_lnphi_func
    from exogibbs.solubility import h2_hirschmann2012
    for module in (exoeos, exogibbs):
        if Path(module.__file__).resolve() != checkouts[module.__name__] / "src" / module.__name__ / "__init__.py":
            raise ValueError(f"Import the selected {module.__name__} checkout")

    inputs = case["inputs"]
    t, p = inputs["temperature_K"], inputs["total_pressure_bar"]
    eos = exoeos.ZhangDuanEOS.from_species(("H2",))
    callback = make_pure_lnphi_func(source_species=("H2",), eos_by_species={"H2": eos})
    lnphi = float(callback(t, p, None)[0])
    phi, pressure_gpa = math.exp(lnphi), p / 1e4
    fugacity = phi * p
    dissolved = float(h2_hirschmann2012(fugacity, pressure_gpa))
    ideal = float(h2_hirschmann2012(p, pressure_gpa))
    direct = exoeos.state_tp(eos, t, p * 1e5, jnp.array([1.0]))
    compare = BASELINE.comparison
    checks = [
        compare("adapter_matches_direct_eos_lnphi", lnphi, float(direct.lnphi[0])),
        compare("eos_pressure_round_trip_Pa", float(direct.P), p * 1e5, rtol=1e-10),
        compare("law_uses_fugacity_and_actual_pressure", dissolved, fugacity * math.exp(-11.403 - 0.76 * pressure_gpa)),
        compare("ideal_control_uses_actual_pressure", ideal, p * math.exp(-11.403 - 0.76 * pressure_gpa)),
    ]
    aliases = {case["components"][config["role"]]: owner for owner, config in PROVIDERS.items()}
    assessments = []
    for item in case["assessments"]:
        references = []
        for ref in item["evidence"]:
            old_path, evidence_id = ref.split("#")
            owner = aliases[old_path]
            if evidence_id not in {e.id for e in contracts[owner].evidence}:
                raise ValueError(f"Missing assessment evidence: {owner}#{evidence_id}")
            references.append({"provider": owner, "contract": PROVIDERS[owner]["contract"], "evidence": evidence_id})
        assessments.append({**item, "evidence": references})
    return {
        "record_format": "provider_owned_h2_execution_v0.1",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_id": case["id"], "case_sha256": sha256(CASE), "runner_sha256": sha256(Path(__file__)),
        "helper_sha256": {name: sha256(ROOT / name) for name in
                          ("examples/h2_solubility/run.py", "examples/provider_workflow/run.py")},
        "baseline_contract_sha256": {path: sha256(ROOT / path) for path in case["components"].values()},
        "providers": records, "inputs": inputs,
        "outputs": {"lnphi_H2": lnphi, "phi_H2": phi, "fugacity_H2_bar": fugacity,
                    "dissolved_H2_mole_fraction": dissolved, "ideal_fugacity_control_mole_fraction": ideal},
        "environment": {"python": platform.python_version(), "backend": jax.default_backend(),
                        "dtype": str(direct.rho.dtype), "jax_enable_x64": jax.config.x64_enabled,
                        "versions": {name: importlib.metadata.version(name) for name in ("jax", "jaxlib", "numpy")}},
        "numerical_checks": checks, "assessment_method": "manual",
        "assessments": assessments, "physical_validation": "unknown",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exoeos", type=Path, required=True)
    parser.add_argument("--exogibbs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run({"exoeos": args.exoeos.resolve(), "exogibbs": args.exogibbs.resolve()})
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(f"Wrote {args.output}; four numerical checks passed; nine manual assessments retained")
