"""Replay one fixed case; never infer or update its manual classifications.

ExoEOS, ExoGibbs and JAX are optional dependencies of this example only.
Run with the pinned sibling source checkouts on PYTHONPATH; see the case guide.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import subprocess
import sys

import yaml

from mceg import load_contract


ROOT = Path(__file__).resolve().parents[2]
CASE = Path(__file__).with_name("case.yaml")
AUDITED_INPUTS = {
    "temperature_K": 1700.0,
    "total_pressure_bar": 7500.0,
    "gas_mole_fractions": {"H2": 1.0},
    "phase_selector": "vapor",
    "melt_composition": "unknown",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_record(module, contract, files):
    checkout = Path(module.__file__).resolve().parents[2]
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != contract.model.implementation.revision:
        raise ValueError(f"{module.__name__}: use the audited revision {contract.model.implementation.revision}")
    subprocess.run(["git", "-C", str(checkout), "diff", "--quiet", "HEAD", "--"], check=True)
    return {
        "repository": contract.model.implementation.repository,
        "revision": revision,
        "tracked_worktree_clean": True,
        "selected_file_sha256": {name: sha256(checkout / name) for name in files},
    }


def comparison(name, actual, expected, rtol=1e-12, atol=1e-14):
    passed = math.isclose(actual, expected, rel_tol=rtol, abs_tol=atol)
    if not passed:
        raise ValueError(f"Numerical check failed: {name}: {actual} != {expected}")
    return {"id": name, "actual": actual, "expected": expected,
            "rtol": rtol, "atol": atol, "passed": passed}


def run():
    case = yaml.safe_load(CASE.read_text(encoding="utf-8"))
    if case["inputs"] != AUDITED_INPUTS:
        raise ValueError("This replay is fixed to the audited inputs; a changed case needs a new manual audit")
    contracts = {role: load_contract(ROOT / path) for role, path in case["components"].items()}

    import jax
    jax.config.update("jax_platforms", "cpu")
    jax.config.update("jax_enable_x64", True)
    import jax.numpy as jnp
    import exoeos
    import exogibbs
    from exogibbs.interop.exoeos import make_pure_lnphi_func
    from exogibbs.solubility import h2_hirschmann2012

    upstream = {
        "exoeos": source_record(exoeos, contracts["eos"], [
            "src/exoeos/zhang_duan.py", "src/exoeos/helmholtz.py",
            "src/exoeos/constants.py", "src/exoeos/_arrays.py",
        ]),
        "exogibbs": source_record(exogibbs, contracts["solubility"], [
            "src/exogibbs/interop/exoeos.py", "src/exogibbs/solubility/volatile.py",
            "src/exogibbs/utils/units.py", "examples/comparisons/compare_solubility_laws.py",
        ]),
    }
    temperature = case["inputs"]["temperature_K"]
    pressure_bar = case["inputs"]["total_pressure_bar"]
    pressure_pa, pressure_gpa = pressure_bar * 1e5, pressure_bar / 1e4
    eos = exoeos.ZhangDuanEOS.from_species(("H2",))
    callback = make_pure_lnphi_func(source_species=("H2",), eos_by_species={"H2": eos})
    lnphi = float(callback(temperature, pressure_bar, None)[0])
    phi = math.exp(lnphi)
    fugacity_bar = phi * pressure_bar
    dissolved = float(h2_hirschmann2012(fugacity_bar, pressure_gpa))
    ideal_control = float(h2_hirschmann2012(pressure_bar, pressure_gpa))
    direct = exoeos.state_tp(eos, temperature, pressure_pa, jnp.array([1.0]))
    checks = [
        comparison("adapter_matches_direct_eos_lnphi", lnphi, float(direct.lnphi[0])),
        comparison("eos_pressure_round_trip_Pa", float(direct.P), pressure_pa, rtol=1e-10),
        comparison("law_uses_fugacity_bar_and_actual_pressure_GPa", dissolved,
                   fugacity_bar * math.exp(-11.403 - 0.76 * pressure_gpa)),
        comparison("ideal_control_uses_same_actual_pressure", ideal_control,
                   pressure_bar * math.exp(-11.403 - 0.76 * pressure_gpa)),
    ]
    outputs = {
        "pressure_Pa": pressure_pa, "melt_pressure_GPa": pressure_gpa,
        "lnphi_H2": lnphi, "phi_H2": phi, "fugacity_H2_bar": fugacity_bar,
        "compressibility_factor": float(direct.Z),
        "molar_density_mol_m3": float(direct.rho),
        "dissolved_H2_mole_fraction": dissolved,
        "ideal_fugacity_control_mole_fraction": ideal_control,
        "nonideal_to_ideal_ratio": dissolved / ideal_control,
    }
    if not all(math.isfinite(value) for value in outputs.values()):
        raise ValueError("Nonfinite output in the fixed example")
    return {
        "record_format": "h2_solubility_execution_v0.1",
        "case_id": case["id"],
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": [sys.executable, *sys.argv],
        "case_path": str(CASE.relative_to(ROOT)), "case_sha256": sha256(CASE),
        "runner_sha256": sha256(Path(__file__)),
        "contract_sha256": {path: sha256(ROOT / path) for path in case["components"].values()},
        "environment": {
            "python": platform.python_version(), "platform": platform.platform(),
            "versions": {name: importlib.metadata.version(name)
                         for name in ("jax", "jaxlib", "numpy", "pydantic", "PyYAML")},
            "backend": jax.default_backend(), "dtype": str(direct.rho.dtype),
            "jax_enable_x64": jax.config.x64_enabled,
        },
        "upstream": upstream, "inputs": case["inputs"], "outputs": outputs,
        "numerical_checks": checks,
        "manual_assessments": "Read case.yaml; these are not computed by this runner.",
        "physical_validation": "unknown",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write a JSON receipt; otherwise print it")
    args = parser.parse_args()
    result = run()
    encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
        print(f"Wrote {args.output}; numerical checks passed; physical validation unknown")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
