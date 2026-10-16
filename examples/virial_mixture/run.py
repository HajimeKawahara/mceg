"""Replay a fixed mixture through the real example-level provider and callback.

Provider checkouts and JAX are optional dependencies of this example only.
Manual classifications are never inferred or updated by this runner.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

import yaml

from mceg import load_contract


ROOT = Path(__file__).resolve().parents[2]
CASE = Path(__file__).with_name("case.yaml")
AUDITED_INPUTS = {
    "temperatures_K": [1500.0, 2173.15], "pressure_bar": 270.0,
    "species": ["H2", "He1", "H2O1", "O2", "Mg1"],
    "amounts_mol": [0.75, 0.17, 0.06, 0.012, 0.008],
    "standard_potentials_rt": [0.0] * 5, "standard_pressure_bar": 1.0,
    "h2_he_cm3_mol": 10.0,
    "water_cross_policies": ["extrapolate", "hold_2000"], "trace_pair_policy": "zero",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_record(module, contract, files):
    checkout = Path(module.__file__).resolve().parents[2]
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != contract.model.implementation.revision:
        raise ValueError(f"{module.__name__}: use the audited revision")
    subprocess.run(["git", "-C", str(checkout), "diff", "--quiet", "HEAD", "--"], check=True)
    return checkout, {
        "revision": revision, "tracked_worktree_clean": True,
        "selected_file_sha256": {name: sha256(checkout / name) for name in files},
    }


def run():
    case = yaml.safe_load(CASE.read_text(encoding="utf-8"))
    if case["inputs"] != AUDITED_INPUTS:
        raise ValueError("Changed inputs need a new manual audit")
    contracts = {role: load_contract(ROOT / path) for role, path in case["components"].items()}

    import jax
    jax.config.update("jax_platforms", "cpu")
    jax.config.update("jax_enable_x64", True)
    import numpy as np
    import exoeos
    import exogibbs
    from exoeos.constants import MOLAR_GAS_CONSTANT as gas_constant

    eos_root, eos_source = source_record(exoeos, contracts["eos"], [
        "examples/m2_material/major_gas_eos.py", "examples/m2_material/gas_virial.py",
        "examples/m2_material/gas_virial_sources.json", "src/exoeos/second_virial.py",
        "src/exoeos/helmholtz.py", "src/exoeos/state.py", "src/exoeos/constants.py",
        "src/exoeos/_arrays.py",
    ])
    gibbs_root, gibbs_source = source_record(exogibbs, contracts["adapter"], [
        "examples/metal_silicate/m2_gas_eos.py", "examples/metal_silicate/full_potential.py",
        "examples/metal_silicate/local.py",
    ])
    directory = gibbs_root / "examples/metal_silicate"
    sys.path.insert(0, str(directory))
    try:
        adapter = importlib.import_module("m2_gas_eos")
        potential = importlib.import_module("full_potential")
    finally:
        sys.path.pop(0)
    for module in (adapter, potential):
        if Path(module.__file__).resolve().parent != directory:
            raise ValueError("Import the selected ExoGibbs example checkout")

    inputs = case["inputs"]
    n = np.array(inputs["amounts_mol"])
    x = n / n.sum()
    pressure_bar = inputs["pressure_bar"]
    pressure_pa = pressure_bar * 1e5
    ideal = potential.ideal_phase(
        lambda t, p: np.array(inputs["standard_potentials_rt"]), gas=True,
        standard_pressure_bar=inputs["standard_pressure_bar"],
    )
    checks = []

    def compare(name, actual, expected, atol=1e-12, rtol=1e-12):
        a, b = np.asarray(actual), np.asarray(expected)
        if a.shape != b.shape:
            raise ValueError(f"Shape mismatch: {name}")
        error = float(np.max(np.abs(a - b)))
        tolerance = float(atol + rtol * np.max(np.abs(b)))
        passed = bool(np.all(np.isfinite(a)) and error <= tolerance)
        checks.append({"id": name, "max_absolute_error": error,
                       "absolute_tolerance": tolerance, "passed": passed})
        if not passed:
            raise ValueError(f"Numerical check failed: {name}")

    states = []
    matrices = {}
    for temperature in inputs["temperatures_K"]:
        for policy in inputs["water_cross_policies"]:
            key = f"{temperature:g}K_{policy}"
            model = adapter.build_gas_eos(eos_root, inputs["species"], {
                "h2_he_cm3_mol": inputs["h2_he_cm3_mol"],
                "water_cross_temperature_policy": policy,
                "trace_pair_policy": inputs["trace_pair_policy"],
            })
            parameters = model.parameters(temperature, pressure_pa)
            matrix = np.array(parameters["coefficients_m3_mol"])
            matrices[temperature, policy] = matrix
            state = model.state(temperature, pressure_pa, x)
            callback = adapter.with_gas_residual(ideal, model)
            coupled = callback(temperature, pressure_bar, n)
            energy, gradient = callback.energy_value_and_grad_rt(temperature, pressure_bar, n)

            # Independent scalar arithmetic for the specified density virial.
            bmix = float(x @ matrix @ x)
            ideal_density = pressure_pa / (gas_constant * temperature)
            rho = 2 * ideal_density / (1 + np.sqrt(1 + 4 * ideal_density * bmix))
            z = 1 + rho * bmix
            lnphi = 2 * rho * (matrix @ x) - np.log(z)
            residual = float(n.sum() * (2 * rho * bmix - np.log(z)))
            ideal_mu = np.array(inputs["standard_potentials_rt"]) + np.log(
                x * pressure_bar / inputs["standard_pressure_bar"])
            expected_g = float(n @ ideal_mu) + residual
            compare(key + ":density", state.rho, rho)
            compare(key + ":pressure_Pa", state.P, pressure_pa)
            compare(key + ":lnphi", state.lnphi, lnphi)
            compare(key + ":chemical_potentials", coupled.mu_rt, ideal_mu + lnphi)
            compare(key + ":gibbs", coupled.gibbs_rt, expected_g)
            compare(key + ":scalar_value", energy, expected_g)
            compare(key + ":amount_gradient", gradient, coupled.mu_rt)
            compare(key + ":zero_pair_correction", np.asarray(state.lnphi)[3:],
                    np.full(2, -np.log(z)))
            if policy == "hold_2000" and temperature > 2000:
                endpoint = np.asarray(model.coefficients(2000.0))
                compare(key + ":held_water_cross", matrix[[0, 1], [2, 2]],
                        endpoint[[0, 1], [2, 2]], atol=0, rtol=0)
            states.append({
                "id": key, "temperature_K": temperature, "policy": policy,
                "pressure_Pa": pressure_pa, "coefficients_m3_mol": matrix.tolist(),
                "Bmix_m3_mol": bmix, "Z": float(state.Z), "rho_mol_m3": float(state.rho),
                "lnphi": np.asarray(state.lnphi).tolist(),
                "mu_rt": coupled.mu_rt.tolist(), "gibbs_rt": float(coupled.gibbs_rt),
                "residual_gibbs_rt": residual,
                "temperature_assumptions": parameters["temperature_assumptions"],
            })
    compare("1500K:policies_agree", matrices[1500.0, "extrapolate"],
            matrices[1500.0, "hold_2000"], atol=0, rtol=0)
    cross = np.zeros((5, 5), dtype=bool)
    cross[0, 2] = cross[2, 0] = cross[1, 2] = cross[2, 1] = True
    compare("2173K:other_pairs_unchanged", matrices[2173.15, "extrapolate"][~cross],
            matrices[2173.15, "hold_2000"][~cross], atol=0, rtol=0)
    return {
        "record_format": "virial_mixture_execution_v0.1", "case_id": case["id"],
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_sha256": sha256(CASE), "runner_sha256": sha256(Path(__file__)),
        "contract_sha256": {path: sha256(ROOT / path) for path in case["components"].values()},
        "environment": {
            "python": platform.python_version(), "backend": jax.default_backend(),
            "dtype": str(state.rho.dtype), "jax_enable_x64": jax.config.x64_enabled,
            "versions": {name: importlib.metadata.version(name) for name in
                         ("jax", "jaxlib", "numpy", "scipy", "pydantic", "PyYAML")},
        },
        "upstream": {"exoeos": eos_source, "exogibbs": gibbs_source},
        "inputs": inputs, "states": states, "numerical_checks": checks,
        "manual_assessments": "Read case.yaml; these are not computed by this runner.",
        "physical_validation": "unknown",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    encoded = json.dumps(run(), indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
        print(f"Wrote {args.output}; numerical checks passed; physical validation unknown")
    else:
        print(encoded, end="")
