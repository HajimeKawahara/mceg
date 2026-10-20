# Evidence audit for the v0.1 examples

Audit date: 2026-10-15. The source repositories were read without editing them.

| Repository | Inspected revision | Initial worktree |
| --- | --- | --- |
| [ExoEOS](https://github.com/HajimeKawahara/exoeos) | `d7681db4393fd85904846b083013230d81d45d4e` | No tracked changes; pre-existing untracked `memo.txt`, not used |
| [ExoGibbs](https://github.com/HajimeKawahara/exogibbs) | `6b4cef45d2a6f1eb1462afd6cb6d3f1c77dba8ea` | Clean |

This is a targeted audit, not a claim that no other evidence exists. Unknown
physical validation means no such evidence was established for the selected
contracts from the inspected materials.

## Model selection and scientific content

The three residual EOS models share `alphar(T, rho, x)` and
`state_trho`/`state_tp`. This avoids mixing thermodynamic closures in the first
comparison. ExoEOS's separate `IdealGas` supplies constant-cp total caloric
properties and reference enthalpy/entropy; those assumptions do not belong to
the selected `IdealEOS` contract.

| Model | Assumptions and mathematical properties | Scientific applicability and limits |
| --- | --- | --- |
| IdealEOS | `alphar=0`; `P=rho R T`, `Z=1`, `lnphi=0`, zero residual Gibbs | Quantitative real-material domain unknown; residual-only model; vapor selector only |
| SecondVirialEOS | Constant symmetric `B_ij`; `B_mix=x^T B x`; `alphar=rho B_mix`; `Z=1+rho B_mix`; low-density TP root | Higher density terms omitted; their negligibility and coefficient temperature relevance must be established separately; quantitative range unknown |
| PengRobinsonEOS | PR76 alpha, exact critical-condition constants, quadratic attraction/linear covolume mixing, constant `k_ij` | Parameter/mixture calibration unknown; root selection does not establish phase stability; repeated-root derivatives not guaranteed |

Source equations, numeric preconditions, and test scopes are recorded in the
model contracts, including the [ideal-gas contract](../../contracts/ideal_gas.yaml). The common
[upstream interface document](https://github.com/HajimeKawahara/exoeos/blob/d7681db4393fd85904846b083013230d81d45d4e/documents/thermodynamic_state_contract.md)
distinguishes residual quantities, input shape checks, caller-owned numerical
domains, and the absence of absolute caloric information.

The test points are verification coverage, not physical validity bounds:

| Test group | Selected states and assertions |
| --- | --- |
| IdealEOS in `helmholtz_test.py` | 600 K, 40 mol/m3, x=[0.25,0.75]; ideal identities. TP at 2e5 Pa, pressure derivative, JIT/vmap, dtype checks. Other tests in this file use a synthetic virial test double. |
| `second_virial_test.py` | 700 K, 50 mol/m3, x=[0.4,0.6], B=[[1e-4,2e-5],[2e-5,8e-5]] m3/mol; analytic identities and TP round trip. Zero-B ideal limit and negative-B stable root are separate cases. |
| `peng_robinson_test.py` | Analytic pressure and energy, liquid/vapor roots, low-density coefficients, gradients and dtype cases. Frozen teqp comparison at 300 K, 4e6 Pa, CO/H2O/CO2/H2=[0.4,0.4,0.1,0.1], zero kij, vapor root; rtol=2e-10, atol=2e-12. |

Unless explicitly overridden in those tests, `jnp.allclose` uses its library
defaults. The test environment is recorded below; no universal accuracy or
uncertainty bound is inferred from tolerances.

## Existing saved results

The upstream [fixed-composition comparison](https://github.com/HajimeKawahara/exoeos/blob/d7681db4393fd85904846b083013230d81d45d4e/documents/tutorials/fixed_composition_cho_eos_comparison.rst)
has saved successful identity/finite-value checks at 1000 K and 301 pressures
from 1e-3 to 1e3 bar for CO/H2O/CO2/H2=[0.4,0.4,0.1,0.1]. Its second-virial
coefficients are derived from the same PR model at that temperature. This is
not independent experimental evidence; the tutorial explicitly warns against
treating the high-pressure virial values as quantitatively reliable.

The [fixed-state teqp reference](https://github.com/HajimeKawahara/exoeos/blob/d7681db4393fd85904846b083013230d81d45d4e/documents/tutorials/peng_robinson_fixed_state_reference.rst)
contains saved comparisons against teqp 0.23.2, revision
`5f62a6f515d517e39c3fb035c11a03524ffa3ad6`. Both implementations use identical
parameters and PR76 conventions. Frozen reference values include
rho=2073.221567707672 mol/m3, Z=0.7734973557808338 and
gres/(RT)=-0.2088751492653717. Agreement checks the implementation, not the
physical quality of the supplied mixture model. The canonical teqp PR helper's
high-acentric-factor convention differs, so the notebook uses a generalized
cubic with a specified alpha function.

These notebooks were inspected, not rerun here. Their saved outputs lack a
complete execution environment and original execution revision. The new run
below reruns the **frozen-reference unit test**, not teqp itself.

## Literature

No model-specific primary literature citation was found in the selected generic
IdealEOS or constant SecondVirialEOS implementation/interface/unit-test sources.
Their literature provenance is unknown in this audit; no textbook attribution
has been guessed. Their theoretical records cite explicit upstream equations.

The PR tutorial cites Peng and Robinson (1976), *A New Two-Constant Equation of
State*, Industrial & Engineering Chemistry Fundamentals 15(1), 59–64,
[DOI 10.1021/i160057a011](https://doi.org/10.1021/i160057a011). The bibliography
was checked, but the full original paper was not available in this audit.
The tutorial also attributes the critical-condition constants to Bell and
Deiters (2021), *Superancillary Equations for Cubic Equations of State*,
[DOI 10.1021/acs.iecr.1c00847](https://doi.org/10.1021/acs.iecr.1c00847), with an
[author record at NIST](https://www.nist.gov/publications/super-ancillary-equations-cubic-equations-state).
These citations are model provenance, not physical validation of every parameter set.

The linked NIST TDE PR explanation describes a volume-translated variant with
rounded constants. It is not an exact specification of this implementation.
Bundled CoolProp-derived critical properties likewise do not calibrate binary
interaction parameters or establish high-temperature mixture applicability.

## ExoGibbs integration findings

The [public adapters](https://github.com/HajimeKawahara/exogibbs/blob/6b4cef45d2a6f1eb1462afd6cb6d3f1c77dba8ea/src/exogibbs/interop/exoeos.py)
expose constraints that a later compatibility checker would need:

- `make_pure_lnphi_func` receives scalar K/bar, converts bar to Pa once, evaluates
  each model at x=[1], and returns dimensionless natural-log fugacity coefficients
  in `source_species` order. Species-to-parameter identity is caller-owned.
- Missing species default to an error; an ideal fallback must be explicit.
  This public callback rejects composition-dependent mixture mode.
- `make_solution_lngamma_func` requires matched component sets, mole-fraction
  activity basis and symmetric standard-state convention. The actual reference
  chemical potentials must still agree; matching convention labels is insufficient.
- Adapter tests use mock EOS objects, while gas-equilibrium tests use synthetic
  chemical systems. They establish wiring, derivatives, and numerical identities.
  They do not establish physical validation or certify arbitrary EOS/solver combinations.

The [pure-fugacity gallery](https://github.com/HajimeKawahara/exogibbs/blob/6b4cef45d2a6f1eb1462afd6cb6d3f1c77dba8ea/examples/plot_exoeos_pure_fugacity.py)
sets standard chemical potentials to zero for an explanatory calculation.
Its 1500 K, 100–5000 bar grid is not a physical validation region.

For a next PoC, the public pure adapter is a small compatibility example. The
[example-level mixture provider](https://github.com/HajimeKawahara/exogibbs/blob/6b4cef45d2a6f1eb1462afd6cb6d3f1c77dba8ea/examples/metal_silicate/m2_gas_eos.md)
is more directly relevant to extrapolation: H2/He/H2O virial coefficients, explicit
zero trace pairs, and `extrapolate` versus `hold_2000` policies. It also shows why
the pure public callback's restriction must not be generalized to all ExoGibbs.

## Test execution

Executed during this audit on Linux x86_64: Python 3.12.7, NumPy 2.1.0,
JAX 0.6.2, jaxlib 0.6.2, pytest 8.3.3. CPU execution and x64 were explicitly
enabled; tests that explicitly select float32 retain that dtype. Commands were
run from MCEG. Bytecode and pytest cache writes were disabled to keep both
source repositories unchanged. Only these selected upstream suites were run.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../exoeos/src \
JAX_PLATFORMS=cpu JAX_PLATFORM_NAME=cpu JAX_ENABLE_X64=1 \
python -m pytest -q -p no:cacheprovider \
  ../exoeos/tests/unittests/helmholtz_test.py \
  ../exoeos/tests/unittests/second_virial_test.py \
  ../exoeos/tests/unittests/peng_robinson_test.py
```

Observed result: **50 passed in 10.19s** (exit 0).

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../exogibbs/src:../exoeos/src \
JAX_PLATFORMS=cpu JAX_PLATFORM_NAME=cpu JAX_ENABLE_X64=1 \
python -m pytest -q -p no:cacheprovider \
  ../exogibbs/tests/unittests/interop/exoeos_test.py \
  ../exogibbs/tests/unittests/interop/exoeos_solution_test.py \
  ../exogibbs/tests/unittests/equilibrium/gas/fugacity_test.py
```

Observed result: **56 passed in 4.41s** (exit 0). The invocations used absolute
checkout paths; equivalent sibling-relative paths are shown for reproducibility.
These are human-readable execution receipts, not signed or exhaustive provenance.

### MCEG checks

`python -m pytest -q` completed with **37 passed** using Pydantic 2.13.5 and
PyYAML 6.0.2. The tests cover the three real contracts, a non-EOS fixture,
unknown knowledge, evidence-category mismatches, missing and duplicate IDs,
malformed/unsafe YAML, and CLI reporting. These checks do not require either
upstream package.

An editable installation in the local `.venv` succeeded using the existing
dependency environment. Both the installed console command and `python -I -m
mceg` worked outside the repository; all three contracts passed structural
validation. Upstream tracked files remained unchanged, and ExoEOS retained only
its pre-existing untracked `memo.txt`.
