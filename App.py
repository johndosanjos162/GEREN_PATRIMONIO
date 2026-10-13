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
# NUMBA — compilação JIT
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

TYPICAL_DWARF = {
    "log_m200": 9.5, "concentration": 15.0,
    "log_mbaryon": 8.5, "a_baryon": 1.0,
    "core_radius_kpc": 0.8, "sigma_v": 40.0,
    "sigma_over_m": 2.0,
}

TYPICAL_CLUSTER = {
    "log_m200": 14.0, "concentration": 4.0,
    "log_mbaryon": 13.0, "a_baryon": 30.0,
    "core_radius_kpc": 20.0, "sigma_v": 800.0,
    "sigma_over_m": 0.3,
}

DEFAULT_WIDGET_STATE = {
    **TYPICAL_VIA_LACTEA,
    "sim_status": "Não iniciada",
    "sim_step": 0,
    "simulation_history": [],
    "simulation_run_counter": 0,
    "dark_matter_pdf_bytes": None,
    "dark_matter_pdf_chart_warning": None,
    "nl_last_input": "",
    "nl_last_matches": [],
    "nl_last_applied": [],
    "nl_last_skipped": [],
    "nl_last_timestamp": "",
    "latest_contextual_insight": "",
    "ai_last_source": "",
    "ai_apply_count": 0,
}

for _key, _value in DEFAULT_WIDGET_STATE.items():
    if _key not in st.session_state:
        st.session_state[_key] = _value

MAX_SIMULATION_HISTORY = 5000

CANDIDATE_OPTIONS = [
    "WIMPs", "Axions", "Neutrinos estéreis",
    "Matéria escura autointeragente (SIDM)", "Matéria escura genérica",
]
HALO_MODEL_OPTIONS = ["NFW", "SIDM (núcleo fenomenológico)"]
DENSITY_MODEL_OPTIONS = ["NFW", "SIDM"]
SIM_HALO_MODEL_OPTIONS = ["NFW", "SIDM"]


# ============================================================
# HELPERS DE CAMPO LIVRE
# ============================================================
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


def restore_typical(preset_dict, message):
    for k, v in preset_dict.items():
        st.session_state[k] = v
    st.session_state["ai_last_source"] = f"preset: {message}"
    st.session_state["nl_last_matches"] = [f"preset {message}: valores típicos restaurados"]
    st.session_state["nl_last_applied"] = list(preset_dict.keys())
    st.session_state["nl_last_skipped"] = []
    st.session_state["nl_last_timestamp"] = datetime.now().strftime("%H:%M:%S")


# ============================================================
# ASSISTENTE DE LINGUAGEM NATURAL E IMPORTADOR DE PESQUISA
# ============================================================
def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value).lower())
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text).strip()


def _to_float(token):
    if token is None:
        return None
    try:
        return float(str(token).replace(",", "."))
    except (TypeError, ValueError):
        return None


def parse_natural_language_config(text: str):
    if not text or not text.strip():
        return {}, []
    t = _normalize_text(text)
    changes: dict = {}
    matches: list = []

    if re.search(r"\b(via lactea|milky way|tipo via lactea|similar a via lactea|galaxia espiral)\b", t):
        changes.update({"log_m200": 12.0, "concentration": 9.4, "log_mbaryon": 10.78,
                        "a_baryon": 3.0, "core_radius_kpc": 3.0, "sigma_v": 120.0, "sigma_over_m": 0.5})
        matches.append("preset: Via Láctea")
    elif re.search(r"\b(galaxia an[a]?|dwarf galaxy|anao|ana|enana)\b", t):
        changes.update(TYPICAL_DWARF)
        matches.append("preset: Galáxia anã")
    elif re.search(r"\b(aglomerado|cluster|agrupamento)\b", t):
        changes.update(TYPICAL_CLUSTER)
        matches.append("preset: Aglomerado")

    cand_map = [
        ("WIMPs", r"\bwimp"),
        ("Axions", r"\baxi[o]?n"),
        ("Neutrinos estéreis", r"neutrino.{0,20}(esteril|estereis|sterile)"),
        ("Matéria escura autointeragente (SIDM)", r"\bsidm\b|autointeragente|self[\s-]?interact"),
        ("Matéria escura genérica", r"materia escura generica|generic dark matter"),
    ]
    for label, pattern in cand_map:
        if re.search(pattern, t):
            changes["candidate"] = label
            matches.append(f"candidato -> {label}")
            break

    if re.search(r"\bsidm\b|nucleo fenomenologico|perfil sidm|core\s*sidm", t):
        changes["halo_model"] = "SIDM (núcleo fenomenológico)"
        changes["sim_halo_model"] = "SIDM"
        changes["density_model"] = "SIDM"
        matches.append("perfil -> SIDM")
    elif re.search(r"\bnfw\b|perfil nfw", t):
        changes["halo_model"] = "NFW"
        changes["sim_halo_model"] = "NFW"
        changes["density_model"] = "NFW"
        matches.append("perfil -> NFW")

    def grab(pattern, key, label=None):
        m = re.search(pattern, t)
        if not m:
            return
        val = _to_float(m.group(1))
        if val is None:
            return
        changes[key] = val
        matches.append(f"{label or key} -> {val}")

    def grab_log(pattern, key):
        m = re.search(pattern, t)
        if not m:
            return
        base = _to_float(m.group(1))
        exp = _to_float(m.group(2))
        if base is None or exp is None or base <= 0:
            return
        val = float(np.log10(base)) + exp
        changes[key] = val
        matches.append(f"{key} -> {val:.3f} (de {base}^{exp})")

    grab_log(r"m[_\s]?200\s*(?:de|=|:|com)?\s*(\d+(?:[.,]\d+)?)\s*[eE]\s*(-?\d+)", "log_m200")
    grab(r"m[_\s]?200\s*(?:de|=|:|com)?\s*10\s*\^?\s*(-?\d+(?:[.,]\d+)?)", "log_m200", "log_m200")
    grab(r"log\s*(?:10\s*)?(?:de\s*|da\s*)?m[_\s]?200\s*(?:=|:)?\s*(-?\d+(?:[.,]\d+)?)", "log_m200", "log_m200")

    grab_log(r"bari[o]?nic[ao]\s*(?:de|=|:|com)?\s*(\d+(?:[.,]\d+)?)\s*[eE]\s*(-?\d+)", "log_mbaryon")
    grab(r"bari[o]?nic[ao]\s*(?:de|=|:|com)?\s*10\s*\^?\s*(-?\d+(?:[.,]\d+)?)", "log_mbaryon", "log_mbaryon")

    grab(r"concentra[c]?[a]?[o]?\s*(?:do\s*halo\s*)?(?:de|=|:|com)?\s*(?:c\s*)?(?:=|:)?\s*(\d+(?:[.,]\d+)?)", "concentration")
    grab(r"(?:escala|raio)\s*bari[o]?nic[ao]\s*(?:de|=|:|com)?\s*(\d+(?:[.,]\d+)?)", "a_baryon")
    grab(r"(?:raio\s*(?:do\s*)?)?nucleo\s*(?:sidm\s*)?(?:de|=|:|com)?\s*(\d+(?:[.,]\d+)?)", "core_radius_kpc")
    grab(r"(?:raio\s*maximo|r[_\s]?plot[_\s]?max|max\s*radius)\s*(?:de|=|:|com)?\s*(\d+(?:[.,]\d+)?)", "r_plot_max")
    grab(r"sigma\s*/\s*m\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)", "sigma_over_m")
    grab(r"sigma\s*por\s*massa\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)", "sigma_over_m")
    grab(r"se[c]?[a]?[o]?\s*de\s*choque\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)", "sigma_over_m")
    grab(r"dispers[a]?[o]?\s*(?:de\s*)?velocidade\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)", "sigma_v")
    grab(r"sigma[_\s]*v\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)", "sigma_v")
    grab(r"feedback\s*(?:strength)?\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)", "feedback_strength")
    grab(r"(?:escala\s*(?:radial\s*)?(?:do\s*)?feedback)\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)", "feedback_scale_kpc")
    grab(r"(\d+)\s*(?:particulas?|traçadores?|particles?|tracers?)", "n_particles")
    grab(r"(\d+)\s*(?:passos?|steps?)", "n_steps")
    grab(r"(?:passo\s*temporal|delta\s*t|\bdt\b)\s*(?:=|:|com)?\s*([\d.,]+)", "dt")
    grab(r"\bg\s*(?:adimensional|dimensionless)?\s*(?:=|:|com)?\s*([\d.,]+)", "g_dimless")
    grab(r"(?:semente|seed)\s*(?:=|:|com)?\s*(\d+)", "sim_seed")
    grab(r"(?:suaviza[c]?[a]?[o]?|softening|epsilon)\s*(?:=|:|com)?\s*([\d.,]+)", "softening")
    grab(r"registrar\s*(?:a\s*cada)?\s*(\d+)", "record_every")

    for k in FREE_INT_RANGES:
        if k in changes:
            try:
                changes[k] = int(round(float(changes[k])))
            except (TypeError, ValueError):
                pass

    filtered: dict = {}
    for key, value in changes.items():
        current = st.session_state.get(key)
        if isinstance(value, float) and isinstance(current, (int, float)):
            if abs(float(value) - float(current)) > 1e-12:
                filtered[key] = value
        elif value != current:
            filtered[key] = value
    return filtered, matches


def apply_ai_changes(changes: dict):
    if not changes:
        return [], []
    applied: list = []
    skipped: list = []
    for key, value in changes.items():
        if key in FREE_RANGES:
            lo, hi, _ = FREE_RANGES[key]
            try:
                num = float(value)
            except (TypeError, ValueError):
                skipped.append(f"{key}={value!r} (não numérico)")
                continue
            num = max(lo, min(hi, num))
            st.session_state[key] = num
            applied.append(f"{key} = {num}")
        elif key in FREE_INT_RANGES:
            lo, hi, _ = FREE_INT_RANGES[key]
            try:
                num = int(round(float(value)))
            except (TypeError, ValueError):
                skipped.append(f"{key}={value!r} (não inteiro)")
                continue
            num = max(lo, min(hi, num))
            st.session_state[key] = num
            applied.append(f"{key} = {num}")
        elif key in {"candidate", "halo_model", "density_model", "sim_halo_model"}:
            text = str(value)
            valid_options = {
                "candidate": CANDIDATE_OPTIONS,
                "halo_model": HALO_MODEL_OPTIONS,
                "density_model": DENSITY_MODEL_OPTIONS,
                "sim_halo_model": SIM_HALO_MODEL_OPTIONS,
            }.get(key, [])
            if valid_options and text not in valid_options:
                skipped.append(f"{key}={text!r} (opção inválida)")
                continue
            st.session_state[key] = text
            applied.append(f"{key} = {text}")
        else:
            skipped.append(f"{key} (desconhecido)")
    return applied, skipped


_pending = st.session_state.pop("nl_pending_changes", None)
if _pending:
    _applied, _skipped = apply_ai_changes(_pending)
    st.session_state["nl_last_applied"] = _applied
    st.session_state["nl_last_skipped"] = _skipped
    st.session_state["nl_last_timestamp"] = datetime.now().strftime("%H:%M:%S")
    st.session_state["ai_apply_count"] = int(st.session_state.get("ai_apply_count", 0)) + 1


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
        if mf < 0.0:
            mass_fraction[i] = 0.0
        elif mf > 1.0:
            mass_fraction[i] = 1.0
        else:
            mass_fraction[i] = mf

    kernel = np.empty(n, dtype=np.float64)
    for i in range(n):
        x = x_grid[i]
        if x > 0.0:
            kernel[i] = (integrand[i] / norm) / x
        else:
            kernel[i] = 0.0
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


@njit(cache=True)
def _profile_density_numba(x_query, x_norm, use_sidm, core_x, feedback_strength,
                           feedback_scale_x, m200_over_4pi_rs3):
    n = x_norm.shape[0]

    shape_norm = np.empty(n, dtype=np.float64)
    for i in range(n):
        xi = x_norm[i]
        xi_safe = xi if xi > 1e-10 else 1e-10
        if use_sidm:
            shape_i = 1.0 / ((xi_safe + core_x) * (1.0 + xi_safe) ** 2)
        else:
            shape_i = 1.0 / (xi_safe * (1.0 + xi_safe) ** 2)
        suppression = 1.0 - feedback_strength * np.exp(-xi / feedback_scale_x)
        shape_norm[i] = shape_i * suppression

    integral = 0.0
    for i in range(n - 1):
        dx = x_norm[i + 1] - x_norm[i]
        f0 = x_norm[i] * x_norm[i] * shape_norm[i]
        f1 = x_norm[i + 1] * x_norm[i + 1] * shape_norm[i + 1]
        integral += 0.5 * (f0 + f1) * dx

    if integral < 1e-30:
        integral = 1e-30
    rho0 = m200_over_4pi_rs3 / integral

    m = x_query.shape[0]
    out = np.empty(m, dtype=np.float64)
    for i in range(m):
        xi = x_query[i]
        xi_safe = xi if xi > 1e-10 else 1e-10
        if use_sidm:
            shape_i = 1.0 / ((xi_safe + core_x) * (1.0 + xi_safe) ** 2)
        else:
            shape_i = 1.0 / (xi_safe * (1.0 + xi_safe) ** 2)
        suppression = 1.0 - feedback_strength * np.exp(-xi / feedback_scale_x)
        out[i] = rho0 * shape_i * suppression

    return out


# ============================================================
# WRAPPERS PYTHON
# ============================================================
def halo_shape(x, model="NFW", core_x=0.15, feedback_strength=0.0, feedback_scale_x=0.15):
    x_arr = np.ascontiguousarray(np.atleast_1d(np.asarray(x, dtype=np.float64)).ravel())
    use_sidm = bool(model.upper().startswith("SIDM"))
    core_x_safe = max(float(core_x), 1e-5)
    fb_clamped = min(max(float(feedback_strength), 0.0), 100.0)
    scale_safe = max(float(feedback_scale_x), 1e-5)
    return _halo_shape_numba(x_arr, use_sidm, core_x_safe, fb_clamped, scale_safe)


def profile_density(radius_kpc, m200_msun, concentration, core_radius_kpc=3.0,
                    model="NFW", feedback_strength=0.0, feedback_scale_kpc=3.0):
    r200, rs, _ = nfw_parameters(m200_msun, concentration)
    x_core = max(core_radius_kpc / rs, 1e-5)
    x_fb = max(feedback_scale_kpc / rs, 1e-5)

    x_norm = np.ascontiguousarray(np.linspace(0.0, float(concentration), 4000), dtype=np.float64)

    radius = np.asarray(radius_kpc, dtype=np.float64)
    original_shape = radius.shape
    radius_flat = radius.ravel()
    x_query = np.ascontiguousarray(np.maximum(radius_flat / rs, 1e-10), dtype=np.float64)

    use_sidm = bool(model.upper().startswith("SIDM"))
    core_x_safe = max(float(x_core), 1e-5)
    fb_clamped = min(max(float(feedback_strength), 0.0), 100.0)
    scale_safe = max(float(x_fb), 1e-5)
    prefactor = float(m200_msun / (4.0 * np.pi * rs**3))

    rho_flat = _profile_density_numba(
        x_query, x_norm, use_sidm, core_x_safe, fb_clamped, scale_safe, prefactor,
    )
    return rho_flat.reshape(original_shape)


def build_profile_lookup(concentration, model="NFW", core_x=0.15,
                         feedback_strength=0.0, feedback_scale_x=0.15, grid_size=3500):
    c = max(float(concentration), 1e-3)
    x_grid = np.unique(np.concatenate(([0.0], np.geomspace(1e-6, c, grid_size))))
    shape = halo_shape(x_grid, model, core_x, feedback_strength, feedback_scale_x)
    mass_fraction, potential = _integrate_profile_core(
        np.ascontiguousarray(x_grid, dtype=np.float64),
        np.ascontiguousarray(shape, dtype=np.float64),
    )
    return x_grid, mass_fraction, potential


def _mass_fraction(radius_over_rs, concentration, model, core_radius_kpc,
                   rs, feedback_strength=0.0, feedback_scale_kpc=3.0):
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


def rotation_components(radius_kpc, m200_msun, concentration, m_baryon_msun,
                        a_baryon_kpc, model="NFW", core_radius_kpc=3.0,
                        feedback_strength=0.0, feedback_scale_kpc=3.0):
    r200, rs, _ = nfw_parameters(m200_msun, concentration)
    r = np.maximum(np.asarray(radius_kpc, dtype=float), 1e-8)
    fraction = _mass_fraction(
        r / rs, concentration, model, core_radius_kpc, rs,
        feedback_strength, feedback_scale_kpc,
    )
    fraction = np.asarray(fraction, dtype=float)
    m_dm = m200_msun * fraction
    v_dm = np.sqrt(np.maximum(G_ASTRO * m_dm / r, 0.0))
    a_safe = max(float(a_baryon_kpc), 1e-8)
    m_b_enclosed = m_baryon_msun * r**2 / (r + a_safe) ** 2
    v_b = np.sqrt(np.maximum(G_ASTRO * m_b_enclosed / r, 0.0))
    v_total = np.sqrt(v_dm**2 + v_b**2)
    return v_dm, v_b, v_total, r200, rs, m_dm, m_b_enclosed


def dark_matter_fraction_at_radius(radius_kpc, m200_msun, concentration, m_baryon_msun,
                                   a_baryon_kpc, model="NFW", core_radius_kpc=3.0,
                                   feedback_strength=0.0, feedback_scale_kpc=3.0):
    _, _, _, _, _, m_dm, m_b = rotation_components(
        radius_kpc, m200_msun, concentration, m_baryon_msun, a_baryon_kpc,
        model, core_radius_kpc, feedback_strength, feedback_scale_kpc,
    )
    total = m_dm + m_b
    frac = np.where(total > 0, m_dm / total, 0.0)
    return m_dm, m_b, frac


def maxwell_speed_pdf(speed, sigma):
    v = np.maximum(np.asarray(speed, dtype=float), 0.0)
    sigma_safe = max(float(sigma), 1e-8)
    return np.sqrt(2.0 / np.pi) * v**2 / sigma_safe**3 * np.exp(-(v**2) / (2.0 * sigma_safe**2))


def density_at_scale_radius_g_cm3(m200_msun, concentration, model, core_radius_kpc,
                                  feedback_strength=0.0, feedback_scale_kpc=3.0):
    _, rs, _ = nfw_parameters(m200_msun, concentration)
    rho_msun_kpc3 = float(profile_density(
        np.array([rs]), m200_msun, concentration, core_radius_kpc, model,
        feedback_strength, feedback_scale_kpc,
    )[0])
    return rho_msun_kpc3 * MSUN_G / (KPC_CM**3)


# ============================================================
# CSV OBSERVACIONAL
# ============================================================
def _header_token(value):
    text = str(value).replace("\ufeff", "").strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", text)


HEADER_ALIASES = {
    "radius_kpc": {
        "radiuskpc", "rkpc", "radius", "r", "raiokpc", "raio", "raioskpc",
        "galactocentricradiuskpc", "galactocentricradius", "radialdistancekpc",
    },
    "v_obs_kms": {
        "vobskms", "vobs", "observedvelocitykms", "velocitykms", "circularvelocitykms",
        "vrotkms", "vrot", "velocidadekms", "velocidadeobservadakms", "velocidadekmps",
        "observedvelocity", "velocityobservedkms",
    },
    "v_err_kms": {
        "verrkms", "verr", "velocityerrorkms", "velocityuncertaintykms", "errorvelocitykms",
        "sigma_vkms", "sigma_v", "errovelocidadekms", "incertezavelocidadekms", "errorbar",
    },
}


def load_observational_csv(uploaded_file):
    raw = uploaded_file.getvalue()
    attempts = [(",", "vírgula"), (";", "ponto e vírgula"), ("\t", "tab"), (None, "auto")]
    token_to_standard = {}
    for standard, aliases in HEADER_ALIASES.items():
        token_to_standard[_header_token(standard)] = standard
        for alias in aliases:
            token_to_standard[_header_token(alias)] = standard
    best_columns = []
    best_separator = "desconhecido"
    best_score = (-1, -1)
    for separator, separator_name in attempts:
        try:
            kwargs = {"sep": separator, "engine": "python", "encoding": "utf-8-sig"}
            if separator == ";":
                kwargs["decimal"] = ","
            frame = pd.read_csv(io.BytesIO(raw), **kwargs)
            original_columns = [str(c).replace("\ufeff", "").strip() for c in frame.columns]
            recognized = [token_to_standard.get(_header_token(col)) for col in frame.columns]
            score = (sum(value is not None for value in recognized), len(original_columns))
            if score > best_score:
                best_score = score
                best_columns = original_columns
                best_separator = separator_name
            rename_map = {}
            for col in frame.columns:
                standard = token_to_standard.get(_header_token(col))
                if standard:
                    rename_map[col] = standard
            normalized = frame.rename(columns=rename_map)
            normalized = normalized.loc[:, ~normalized.columns.duplicated()].copy()
            if {"radius_kpc", "v_obs_kms"}.issubset(normalized.columns):
                normalized["radius_kpc"] = pd.to_numeric(normalized["radius_kpc"], errors="coerce")
                normalized["v_obs_kms"] = pd.to_numeric(normalized["v_obs_kms"], errors="coerce")
                if "v_err_kms" in normalized.columns:
                    normalized["v_err_kms"] = pd.to_numeric(normalized["v_err_kms"], errors="coerce")
                    normalized.loc[normalized["v_err_kms"] <= 0, "v_err_kms"] = np.nan
                normalized = normalized.dropna(subset=["radius_kpc", "v_obs_kms"])
                normalized = normalized[(normalized["radius_kpc"] > 0) & (normalized["v_obs_kms"] >= 0)]
                if not normalized.empty:
                    return normalized.reset_index(drop=True), original_columns, separator_name
        except Exception:
            continue
    header_text = repr(best_columns or "não foi possível ler o cabeçalho")
    raise ValueError(
        f"Não encontrei as colunas obrigatórias. Colunas obrigatórias: radius_kpc e v_obs_kms. "
        f"Colunas detectadas: {header_text}."
    )


# ============================================================
# SIMULAÇÃO DE TRAÇADORES — KERNELS NUMBA OTIMIZADOS
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
