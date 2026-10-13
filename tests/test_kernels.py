import numpy as np
import pytest

from app.kernels import (
    _halo_shape_numba, _integrate_profile_core,
    _leapfrog_batch, _energy_proxy_batch,
)


def test_halo_shape_matches_numpy():
    """Kernel Numba deve reproduzir exatamente a versão vetorizada."""
    x = np.linspace(0.01, 10.0, 500)
    core_x, fb, scale = 0.1, 0.25, 0.15

    # Numba
    shape_nb = _halo_shape_numba(x, True, core_x, fb, scale)

    # Numpy de referência
    x_safe = np.maximum(x, 1e-10)
    shape_np = 1.0 / ((x_safe + core_x) * (1.0 + x_safe) ** 2)
    shape_np *= 1.0 - fb * np.exp(-x / scale)

    np.testing.assert_allclose(shape_nb, shape_np, rtol=1e-14)


def test_integrate_profile_mass_conservation():
    """M(<R200) deve ser exatamente 1 após normalização."""
    x_grid = np.unique(np.concatenate(([0.0], np.geomspace(1e-6, 10.0, 3000))))
    shape = _halo_shape_numba(x_grid, False, 0.15, 0.0, 0.15)
    mass, _ = _integrate_profile_core(x_grid, shape)
    assert abs(mass[-1] - 1.0) < 1e-12


def test_leapfrog_energy_conservation():
    """Energia deve ser conservada para <0.01% em 100 passos."""
    n = 500
    rng = np.random.default_rng(42)
    pos = rng.normal(0, 1, (n, 2))
    vel = rng.normal(0, 0.05, (n, 2))
    acc = np.zeros_like(pos)
    mass_x = np.linspace(0, 10, 1000)
    mass_frac = mass_x**2 / mass_x[-1]**2

    e0 = _energy_proxy_batch(pos, vel, 0.05, mass_x, -mass_frac)
    pos, vel, acc = _leapfrog_batch(pos, vel, acc, mass_x, mass_frac, 0.05, 0.02, 0.01, 100)
    e1 = _energy_proxy_batch(pos, vel, 0.05, mass_x, -mass_frac)

    drift = abs(e1 - e0) / abs(e0)
    assert drift < 1e-4
