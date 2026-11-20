"""A standalone provider example; no MCEG dependency."""

from math import pi


def density(radius_cm, velocity_kms, mass_loss_g_s):
    """Return mass density [g/cm^3]; equation continuity, revision 1."""
    return mass_loss_g_s / (4 * pi * radius_cm**2 * velocity_kms * 1e5)
