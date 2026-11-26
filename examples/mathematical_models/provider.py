"""An analytic profile for the declared isothermal atmosphere example."""

from math import exp


def pressure(height_m, gas_constant, temperature_k, base_pressure_pa, gravity_m_s2):
    """Return gas pressure in Pa; the caller supplies positive constants."""
    return base_pressure_pa * exp(-gravity_m_s2 * height_m / (gas_constant * temperature_k))
