"""Capture a fresh provider-owned benchmark in a new directory.

The supplied Python needs ExoGibbs's numerical dependencies. MCEG itself does
not import them. A successful process is evidence of execution, not validation
of a physical model. Reassessment is a separate, provider-free step.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess


SCRIPT = "examples/comparisons/validate_curated_preset.py"
EXTRA_INPUTS = (
    "src/exogibbs/data/FastChem4/logK/logK.dat",
    "src/exogibbs/data/FastChem4/element_abundances/asplund_2021.dat",
    "benchmarks/fastchem4/fastchem_executable.py",
    "benchmarks/fastchem4/comparison.py",
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(provider, python, fastchem, output):
    provider, fastchem, output = (Path(p).resolve() for p in (provider, fastchem, output))
    def git(*args):
        return subprocess.check_output(["git", "-C", str(provider), *args], text=True).strip()
    if git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Use a checkout with unchanged tracked files")
    revision = git("rev-parse", "HEAD")
    archive = json.loads((provider / "results/curated_gas_validation/receipt.json").read_text())
    paths = sorted(set(archive["selected_file_sha256"]) | set(EXTRA_INPUTS))
    before = {p: sha256(provider / p) for p in paths}
    binary = sha256(fastchem)
    settings = {"JAX_PLATFORMS": "cpu", "JAX_ENABLE_X64": "1", "OMP_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    env = {**os.environ, **settings}
    probe = (
        "import json, platform, importlib.metadata as m, jax; "
        "print(json.dumps({'python': platform.python_version(), "
        "'platform': platform.platform(), 'machine': platform.machine(), "
        "'backend': jax.default_backend(), 'dtype': 'float64' if jax.config.x64_enabled else 'float32', "
        "'packages': {p: m.version(p) for p in "
        "('jax', 'jaxlib', 'numpy', 'scipy', 'ml_dtypes', 'opt_einsum')}}))"
    )
    environment = json.loads(subprocess.check_output([str(python), "-c", probe], env=env, text=True))
    output.mkdir(parents=True, exist_ok=False)
    command = [str(python), str(provider / SCRIPT), "--fastchem-executable", str(fastchem),
               "--output-dir", str(output)]
    start = datetime.now(timezone.utc).isoformat()
    with (output / "execution.log").open("w") as log:
        completed = subprocess.run(command, cwd=provider, env=env, stdout=log, stderr=log)
    unchanged = (before == {p: sha256(provider / p) for p in paths}
                 and binary == sha256(fastchem) and revision == git("rev-parse", "HEAD")
                 and not git("status", "--porcelain", "--untracked-files=no"))
    receipt = output / "receipt.json"
    record = {
        "format": "curated_execution_v1", "started_utc": start,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "command": command, "environment": environment, "environment_variables": settings,
        "provider_revision": revision, "selected_input_sha256": before,
        "inputs_unchanged_during_execution": unchanged,
        "fastchem_binary_sha256": binary, "exit_code": completed.returncode,
        "receipt_sha256": sha256(receipt) if receipt.exists() else None,
        "log_sha256": sha256(output / "execution.log"),
        "capture_sha256": sha256(Path(__file__)),
    }
    (output / "execution.json").write_text(json.dumps(record, indent=2) + "\n")
    if not unchanged:
        raise ValueError("Inputs changed during execution; retain the record and investigate")
    return completed.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exogibbs", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--fastchem", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(capture(args.exogibbs, args.python, args.fastchem, args.output_dir))
