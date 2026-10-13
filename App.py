from __future__ import annotations

import io
import json
import re
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from fpdf import FPDF

# ============================================================
# NUMBA — COMPILAÇÃO JIT
# ============================================================
try:
    from numba import njit
    NUMBA_AVAILABLE = True
except ImportError:  # pragma: no cover
    NUMBA_AVAILABLE = False

    def njit(func=None, **kwargs):
        if func is None:
            def wrapper(f):
                return f
            return wrapper
        return func

st.set_page_config(
    page_title="Dark Matter Lab",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .stApp { background: linear-gradient(145deg,#0a1020 0%,#10192d 58%,#111827 100%); }
      h1,h2,h3 { color:#e8efff !important; }
      [data-testid="stMetric"] { background:rgba(35,49,75,.62); border:1px solid rgba(125,160,220,.22); padding:13px; border-radius:12px; }
      .lab-subtitle { color:#aabbd7; font-size:1.02rem; }
      .lab-card { background:rgba(35,49,75,.48); border:1px solid rgba(125,160,220,.23); border-radius:14px; padding:16px 18px; }
      .muted { color:#aabbd7; font-size:.86rem; }
      .nl-hint { background:rgba(35,49,75,.40); border-left:3px solid #58c4dd; padding:10px 14px; border-radius:6px; color:#c9d6f0; font-size:.9rem; }
      .dm-callout { background:linear-gradient(135deg,rgba(139,124,255,.15),rgba(88,196,221,.10)); border:1px solid rgba(139,124,255,.35); border-radius:12px; padding:16px 20px; margin:10px 0; }
      .dm-callout b { color:#c9b8ff; }
      .insight-box { background:rgba(88,196,221,.10); border-left:3px solid #58c4dd; padding:10px 14px; border-radius:6px; color:#c9d6f0; font-size:.9rem; margin:6px 0; }
      .sync-banner { background:linear-gradient(90deg,rgba(139,124,255,.18),rgba(88,196,221,.12)); border:1px solid rgba(139,124,255,.35); border-radius:8px; padding:8px 14px; color:#d0daf2; font-size:.86rem; margin-bottom:6px; }
      .free-input-note { background:rgba(255,189,105,.10); border-left:3px solid #ffbd69; padding:8px 12px; border-radius:6px; color:#f0d9b0; font-size:.84rem; }
      .numba-badge { background:linear-gradient(90deg,rgba(88,196,221,.20),rgba(139,124,255,.15)); border:1px solid rgba(88,196,221,.35); border-radius:6px; padding:4px 10px; color:#a9e5f0; font-size:.8rem; display:inline-block; margin-left:8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------- CONSTANTES / UNIDADES --------------------
G_ASTRO = 4.30091e-6
H0_KMS_MPC = 70.0
H0_KMS_KPC = H0_KMS_MPC / 1000.0
RHO_CRIT = 3 * H0_KMS_KPC**2 / (8 * np.pi * G_ASTRO)


def trapezoid_compat(y, x):
    integrator = getattr(np, "trapezoid", None)
    if integrator is None:
        integrator = np.trapz
    return integrator(y, x)


MSUN_G = 1.98847e33
KPC_CM = 3.085677581e21


def as_1d(value):
    return np.atleast_1d(np.asarray(value, dtype=float)).ravel()


# --------------- FAIXAS AMPLAS DOS CAMPOS LIVRES ------------
FREE_RANGES = {
    "log_m200":            (-30.0, 30.0, 0.01),
    "concentration":       (0.01, 1000.0, 0.01),
    "log_mbaryon":         (-30.0, 30.0, 0.01),
    "a_baryon":            (0.0001, 100000.0, 0.01),
    "core_radius_kpc":     (0.0001, 100000.0, 0.01),
    "r_plot_max":          (0.001, 1000000.0, 0.1),
    "sigma_over_m":        (0.0, 100000.0, 0.01),
    "sigma_v":             (0.001, 100000.0, 0.1),
    "feedback_strength":   (0.0, 100.0, 0.001),
    "feedback_scale_kpc":  (0.0001, 100000.0, 0.01),
    "g_dimless":           (1e-9, 1000.0, 1e-6),
    "dt":                  (1e-9, 1000.0, 1e-7),
    "softening":           (1e-9, 1000.0, 1e-6),
}

FREE_INT_RANGES = {
    "n_velocity_samples":  (1, 10000000, 1),
    "seed_velocity":       (0, 2_147_483_647, 1),
    "n_particles":         (1, 1000000, 1),
    "n_steps":             (1, 10000000, 1),
    "sim_seed":            (0, 2_147_483_647, 1),
    "record_every":        (1, 1000000, 1),
}

TYPICAL_VIA_LACTEA = {
    "candidate": "Matéria escura autointeragente (SIDM)",
    "halo_model": "NFW",
    "log_m200": 12.0,
    "concentration": 9.4,
    "log_mbaryon": 10.78,
    "a_baryon": 3.0,
    "core_radius_kpc": 3.0,
    "r_plot_max": 40.0,
    "sigma_over_m": 0.5,
    "sigma_v": 120.0,
    "n_velocity_samples": 5000,
    "seed_velocity": 42,
    "feedback_strength": 0.25,
    "feedback_scale_kpc": 3.0,
    "density_model": "NFW",
    "n_particles": 1000,
    "n_steps": 10000,
    "sim_halo_model": "NFW",
    "g_dimless": 0.05,
    "dt": 0.01,
    "softening": 0.02,
    "sim_seed": 42,
    "record_every": 100,
}

DEFAULT_WIDGET_STATE = {
    **TYPICAL_VIA_LACTEA,
    "sim_status": "Não iniciada",
    "sim_step": 0,
    "simulation_history": [],
    "simulation_run_counter": 0,
}

for _key, _value in DEFAULT_WIDGET_STATE.items():
    if _key not in st.session_state:
        st.session_state[_key] = _value

CANDIDATE_OPTIONS = [
    "WIMPs", "Axions", "Neutrinos estéreis",
    "Matéria escura autointeragente (SIDM)", "Matéria escura genérica",
]
HALO_MODEL_OPTIONS = ["NFW", "SIDM (núcleo fenomenológico)"]
SIM_HALO_MODEL_OPTIONS = ["NFW", "SIDM"]


def free_number(label, key, help_text="", fmt="%.6g", step=None):
    lo, hi, default_step = FREE_RANGES[key]
    return st.number_input(
        label, min_value=float(lo), max_value=float(hi),
        step=float(step if step is not None else default_step),
        format=fmt, key=key,
        help=help_text or f"Faixa ampla: [{lo}, {hi}]. Digite qualquer valor.",
    )


def free_int(label, key, help_text=""):
    lo, hi, default_step = FREE_INT_RANGES[key]
    return st.number_input(
        label, min_value=int(lo), max_value=int(hi),
        step=int(default_step), key=key,
        help=help_text or f"Faixa ampla: [{lo}, {hi}]. Digite qualquer inteiro.",
    )


# ============================================================
# MODELOS FÍSICOS
# ============================================================
def nfw_f(x):
    x = np.maximum(np.asarray(x, dtype=float), 1e-12)
    return np.log1p(x) - x / (1.0 + x)


def nfw_parameters(m200_msun, concentration):
    r200 = (3.0 * m200_msun / (4.0 * np.pi * 200.0 * RHO_CRIT)) ** (1.0 / 3.0)
    rs = r200 / max(float(concentration), 1e-6)
    rho_s = m200_msun / (4.0 * np.pi * rs**3 * max(float(nfw_f(concentration)), 1e-30))
    return r200, rs, rho_s


# ============================================================
# KERNELS NUMBA — FÍSICA DA MATÉRIA ESCURA
# ============================================================
@njit(cache=True)
def _halo_shape_numba(x, use_sidm, core_x, feedback_strength, feedback_scale_x):
    n = x.shape[0]
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        xi = x[i]
        xi_safe = xi if xi > 1e-10 else 1e-10
        if use_sidm:
            shape = 1.0 / ((xi_safe + core_x) * (1.0 + xi_safe) ** 2)
        else:
            shape = 1.0 / (xi_safe * (1.0 + xi_safe) ** 2)
        suppression = 1.0 - feedback_strength * np.exp(-xi / feedback_scale_x)
        out[i] = shape * suppression
    return out


@njit(cache=True)
def _integrate_profile_core(x_grid, shape):
    n = x_grid.shape[0]
    integrand = np.empty(n, dtype=np.float64)
    for i in range(n):
        x = x_grid[i]
        integrand[i] = x * x * shape[i]

    mass_fraction = np.empty(n, dtype=np.float64)
    potential = np.empty(n, dtype=np.float64)

    if n == 1:
        mass_fraction[0] = 1.0
        potential[0] = -1.0 / max(x_grid[0], 1e-8)
        return mass_fraction, potential

    cumulative = np.empty(n, dtype=np.float64)
    cumulative[0] = 0.0
    for i in range(1, n):
        dx = x_grid[i] - x_grid[i - 1]
        cumulative[i] = cumulative[i - 1] + 0.5 * (integrand[i] + integrand[i - 1]) * dx

    norm = cumulative[n - 1]
    if norm < 1e-30:
        norm = 1e-30

    for i in range(n):
        mf = cumulative[i] / norm
        mass_fraction[i] = 0.0 if mf < 0.0 else (1.0 if mf > 1.0 else mf)

    kernel = np.empty(n, dtype=np.float64)
    for i in range(n):
        x = x_grid[i]
        kernel[i] = (integrand[i] / norm) / x if x > 0.0 else 0.0
    kernel[0] = kernel[1]

    outer_integral = np.zeros(n, dtype=np.float64)
    acc = 0.0
    for i in range(n - 2, -1, -1):
        dx = x_grid[i + 1] - x_grid[i]
        acc += 0.5 * (kernel[i + 1] + kernel[i]) * dx
        outer_integral[i] = acc

    for i in range(n):
        x_safe = x_grid[i] if x_grid[i] > 1e-8 else 1e-8
        potential[i] = -(mass_fraction[i] / x_safe + outer_integral[i])
    potential[0] = potential[1]

    return mass_fraction, potential


def halo_shape(x, model="NFW", core_x=0.15, feedback_strength=0.0, feedback_scale_x=0.15):
    x_arr = np.ascontiguousarray(np.atleast_1d(np.asarray(x, dtype=np.float64)).ravel())
    use_sidm = bool(model.upper().startswith("SIDM"))
    return _halo_shape_numba(x_arr, use_sidm, max(float(core_x), 1e-5), min(max(float(feedback_strength), 0.0), 100.0), max(float(feedback_scale_x), 1e-5))


def build_profile_lookup(concentration, model="NFW", core_x=0.15, feedback_strength=0.0, feedback_scale_x=0.15, grid_size=3500):
    c = max(float(concentration), 1e-3)
    x_grid = np.unique(np.concatenate(([0.0], np.geomspace(1e-6, c, grid_size))))
    shape = halo_shape(x_grid, model, core_x, feedback_strength, feedback_scale_x)
    mass_fraction, potential = _integrate_profile_core(
        np.ascontiguousarray(x_grid, dtype=np.float64),
        np.ascontiguousarray(shape, dtype=np.float64),
    )
    return x_grid, mass_fraction, potential


def _mass_fraction(radius_over_rs, concentration, model, core_radius_kpc, rs, feedback_strength=0.0, feedback_scale_kpc=3.0):
    if model.upper().startswith("NFW") and feedback_strength <= 0:
        return nfw_f(np.minimum(np.maximum(radius_over_rs, 1e-12), concentration)) / max(float(nfw_f(concentration)), 1e-30)
    lookup = build_profile_lookup(
        concentration=concentration, model=model,
        core_x=max(core_radius_kpc / rs, 1e-5),
        feedback_strength=feedback_strength,
        feedback_scale_x=max(feedback_scale_kpc / rs, 1e-5),
        grid_size=2200,
    )
    x_grid, frac, _ = lookup
    return np.interp(np.asarray(radius_over_rs), x_grid, frac, left=0.0, right=1.0)


def rotation_components(radius_kpc, m200_msun, concentration, m_baryon_msun, a_baryon_kpc, model="NFW", core_radius_kpc=3.0, feedback_strength=0.0, feedback_scale_kpc=3.0):
    r200, rs, _ = nfw_parameters(m200_msun, concentration)
    r = np.maximum(np.asarray(radius_kpc, dtype=float), 1e-8)
    fraction = _mass_fraction(r / rs, concentration, model, core_radius_kpc, rs, feedback_strength, feedback_scale_kpc)
    m_dm = m200_msun * np.asarray(fraction, dtype=float)
    v_dm = np.sqrt(np.maximum(G_ASTRO * m_dm / r, 0.0))
    a_safe = max(float(a_baryon_kpc), 1e-8)
    m_b_enclosed = m_baryon_msun * r**2 / (r + a_safe) ** 2
    v_b = np.sqrt(np.maximum(G_ASTRO * m_b_enclosed / r, 0.0))
    v_total = np.sqrt(v_dm**2 + v_b**2)
    return v_dm, v_b, v_total, r200, rs, m_dm, m_b_enclosed


# ============================================================
# SIMULAÇÃO DE TRAÇADORES — NUMBA
# ============================================================
def create_initial_tracers(n, seed, concentration, mass_x, mass_fraction, g_dimless):
    rng = np.random.default_rng(seed)
    radius = np.clip(rng.lognormal(mean=np.log(2.0), sigma=0.38, size=n), 0.15, 0.95 * concentration)
    phi = rng.uniform(0.0, 2.0 * np.pi, size=n)
    positions = np.column_stack((radius * np.cos(phi), radius * np.sin(phi)))
    enclosed_fraction = np.interp(radius, mass_x, mass_fraction, left=0.0, right=1.0)
    vc = np.sqrt(np.maximum(g_dimless * enclosed_fraction / np.maximum(radius, 1e-8), 0.0))
    tangential = vc * rng.normal(1.0, 0.08, size=n)
    radial = vc * rng.normal(0.0, 0.12, size=n)
    vx = radial * np.cos(phi) - tangential * np.sin(phi)
    vy = radial * np.sin(phi) + tangential * np.cos(phi)
    return positions, np.column_stack((vx, vy))


@njit(cache=True)
def tracer_acceleration(positions, g_dimless, mass_x, mass_fraction, softening):
    n = positions.shape[0]
    out = np.empty((n, 2), dtype=np.float64)
    eps2 = softening * softening
    for i in range(n):
        x = positions[i, 0]
        y = positions[i, 1]
        r = np.sqrt(x * x + y * y)
        r_safe = r if r > 1e-10 else 1e-10
        enclosed = np.interp(r_safe, mass_x, mass_fraction)
        denom = (r_safe * r_safe + eps2) ** 1.5
        factor = -g_dimless * enclosed / denom
        out[i, 0] = factor * x
        out[i, 1] = factor * y
    return out


@njit(cache=True)
def update_tracers_numba(positions, velocities, dt, g_dimless, mass_x, mass_fraction, softening):
    n = positions.shape[0]
    acc = tracer_acceleration(positions, g_dimless, mass_x, mass_fraction, softening)
    for i in range(n):
        velocities[i, 0] += acc[i, 0] * dt
        velocities[i, 1] += acc[i, 1] * dt
        positions[i, 0] += velocities[i, 0] * dt
        positions[i, 1] += velocities[i, 1] * dt
    return positions, velocities


# ============================================================
# INTERFACE GRÁFICA STREAMLIT
# ============================================================
st.title("🌌 Dark Matter Lab — Simulação Cosmológica SIDM")
st.markdown("<p class='lab-subtitle'>Ambiente de dinâmica de galáxias otimizado com Numba JIT.</p>", unsafe_allow_html=True)

st.sidebar.header("⚙️ Parâmetros do Halo")
log_m200 = free_number("Log₁₀(M₂₀₀ / M_sun)", "log_m200")
concentration = free_number("Concentração (c)", "concentration")
log_mbaryon = free_number("Log₁₀(M_baryon / M_sun)", "log_mbaryon")
a_baryon = free_number("Escala Bariônica a (kpc)", "a_baryon")
model = st.sidebar.selectbox("Modelo de Halo", HALO_MODEL_OPTIONS, key="halo_model")
core_radius = free_number("Raio do Núcleo SIDM (kpc)", "core_radius_kpc")
feedback_str = free_number("Força de Feedback", "feedback_strength")
feedback_scale = free_number("Escala de Feedback (kpc)", "feedback_scale_kpc")

st.sidebar.markdown("---")
st.sidebar.header("🎯 Parâmetros da Simulação")
n_particles = free_int("Número de Partículas", "n_particles")
n_steps = free_int("Número de Passos", "n_steps")
dt = free_number("Passo Temporal (dt)", "dt")
softening = free_number("Suavização (Softening)", "softening")
g_dimless = free_number("Constante Gravitacional Adimensional", "g_dimless")

m200_val = 10.0 ** log_m200
mbaryon_val = 10.0 ** log_mbaryon

tab1, tab2 = st.tabs(["📈 Curva de Rotação", "🚀 Simulação de Traçadores"])

with tab1:
    st.subheader("Curva de Rotação Circular")
    r_max = st.slider("Raio Máximo de Plotagem (kpc)", 10.0, 200.0, float(st.session_state.get("r_plot_max", 40.0)))
    r_vals = np.linspace(0.5, r_max, 300)
    v_dm, v_b, v_tot, r200, rs, _, _ = rotation_components(
        r_vals, m200_val, concentration, mbaryon_val, a_baryon,
        model, core_radius, feedback_str, feedback_scale
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=r_vals, y=v_tot, mode="lines", name="Velocidade Total", line=dict(color="#58c4dd", width=3)))
    fig.add_trace(go.Scatter(x=r_vals, y=v_dm, mode="lines", name="Matéria Escura", line=dict(color="#8b7cff", dash="dash")))
    fig.add_trace(go.Scatter(x=r_vals, y=v_b, mode="lines", name="Bárions", line=dict(color="#ffbd69", dash="dot")))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(35,49,75,0.3)",
        xaxis_title="Raio Galacêntrico (kpc)",
        yaxis_title="Velocidade Circular (km/s)",
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Dinâmica de Partículas em Tempo Real")
    if st.button("▶ Executar Simulação"):
        mass_x, mass_frac, _ = build_profile_lookup(concentration, model, core_radius / rs, feedback_str, feedback_scale / rs)
        pos, vel = create_initial_tracers(int(n_particles), int(st.session_state["sim_seed"]), concentration, mass_x, mass_frac, g_dimless)
        
        progress_bar = st.progress(0)
        chart_placeholder = st.empty()

        for step in range(min(int(n_steps), 200)):
            pos, vel = update_tracers_numba(pos, vel, dt, g_dimless, mass_x, mass_frac, softening)
            if step % 10 == 0:
                progress_bar.progress((step + 1) / min(int(n_steps), 200))
                fig_sim = go.Figure()
                fig_sim.add_trace(go.Scatter(x=pos[:, 0], y=pos[:, 1], mode="markers", marker=dict(size=3, color="#58c4dd")))
                fig_sim.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(35,49,75,0.3)",
                    xaxis=dict(range=[-concentration, concentration]),
                    yaxis=dict(range=[-concentration, concentration]),
                    width=500, height=500,
                )
                chart_placeholder.plotly_chart(fig_sim, use_container_width=True)
        st.success("Simulação concluída com sucesso com o ganho de performance do Numba!")
