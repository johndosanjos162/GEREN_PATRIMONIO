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
# DARK MATTER LAB
# Modelos NFW/SIDM, velocidades, curvas de rotacao, feedback,
# integracao numerica de tracadores, historico, PDF e
# assistente de configuracao por linguagem natural.
# ============================================================

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


# FIX: helper global para normalizar qualquer coisa em ndarray 1-D.
# Resolve o crash "All arrays must be of the same length" que ocorria
# quando alguma combinacao de parametros devolvia escalar 0-d ou shape
# divergente do resto do diagnostico.
def as_1d(value):
    return np.atleast_1d(np.asarray(value, dtype=float)).ravel()


# --------------- DEFAULTS DOS WIDGETS (FONTE UNICA) ---------
# Valores calibrados para o caso classico da Via Lactea: a curva de
# rotacao so fica PLANA (~220 km/s ate ~30 kpc) porque existe materia
# escura. Sem ME, a curva cairia como Kepler apos o raio visivel.
DEFAULT_WIDGET_STATE = {
    "candidate": "Materia escura autointeragente (SIDM)",
    "halo_model": "NFW",
    "log_m200": 12.0,
    "concentration": 10.0,
    "log_mbaryon": 10.7,
    "a_baryon": 3.0,
    "core_radius_kpc": 3.0,
    "r_plot_max": 40.0,
    "sigma_over_m": 1.0,
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
    "sim_status": "Nao iniciada",
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
}

for _key, _value in DEFAULT_WIDGET_STATE.items():
    if _key not in st.session_state:
        st.session_state[_key] = _value

MAX_SIMULATION_HISTORY = 5000

CANDIDATE_OPTIONS = [
    "WIMPs",
    "Axions",
    "Neutrinos estereis",
    "Materia escura autointeragente (SIDM)",
    "Materia escura generica",
]
HALO_MODEL_OPTIONS = ["NFW", "SIDM (nucleo fenomenologico)"]
DENSITY_MODEL_OPTIONS = ["NFW", "SIDM"]
SIM_HALO_MODEL_OPTIONS = ["NFW", "SIDM"]


# ============================================================
# ASSISTENTE DE LINGUAGEM NATURAL
# ============================================================
def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value).lower())
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text).strip()


def _to_float(token: str):
    if token is None:
        return None
    try:
        return float(str(token).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _find_m200_log(text: str):
    m = re.search(r"m[_\s]?200\s*(?:de|=|:|com)?\s*10\s*\^?\s*(-?\d+(?:[.,]\d+)?)", text)
    if m:
        return _to_float(m.group(1))
    m = re.search(r"m[_\s]?200\s*(?:de|=|:|com)?\s*(\d+(?:[.,]\d+)?)\s*[eE]\s*(-?\d+)", text)
    if m:
        base = _to_float(m.group(1))
        exp = _to_float(m.group(2))
        if base is not None and exp is not None and base > 0:
            return float(np.log10(base)) + exp
    m = re.search(
        r"log\s*(?:10\s*)?(?:de\s*|da\s*)?(?:massa\s*|m[_\s]?200\s*)?(?:m[_\s]?200\s*)?(?:=|:)?\s*(-?\d+(?:[.,]\d+)?)",
        text,
    )
    if m:
        return _to_float(m.group(1))
    return None


def _find_mbaryon_log(text: str):
    m = re.search(r"bari[o]?nic[ao]\s*(?:de|=|:|com)?\s*10\s*\^?\s*(-?\d+(?:[.,]\d+)?)", text)
    if m:
        return _to_float(m.group(1))
    m = re.search(r"bari[o]?nic[ao]\s*(?:de|=|:|com)?\s*(\d+(?:[.,]\d+)?)\s*[eE]\s*(-?\d+)", text)
    if m:
        base = _to_float(m.group(1))
        exp = _to_float(m.group(2))
        if base is not None and exp is not None and base > 0:
            return float(np.log10(base)) + exp
    m = re.search(r"log\s*(?:10\s*)?(?:da\s*)?(?:massa\s*)?bari[o]?nic[ao]\s*(?:=|:)?\s*(-?\d+(?:[.,]\d+)?)", text)
    if m:
        return _to_float(m.group(1))
    return None


def parse_natural_language_config(text: str):
    if not text or not text.strip():
        return {}, []
    t = _normalize_text(text)
    changes: dict = {}
    matches: list = []

    if re.search(r"\b(via lactea|milky way|tipo via lactea|similar a via lactea|galaxia espiral)\b", t):
        changes.update({
            "log_m200": 12.0, "concentration": 10.0, "log_mbaryon": 10.7,
            "a_baryon": 3.0, "core_radius_kpc": 3.0, "sigma_v": 120.0, "sigma_over_m": 1.0,
        })
        matches.append("preset: Via Lactea")
    elif re.search(r"\b(galaxia an[a]?|dwarf galaxy|anao|ana|enana)\b", t):
        changes.update({
            "log_m200": 9.5, "concentration": 15.0, "log_mbaryon": 8.5,
            "a_baryon": 1.0, "core_radius_kpc": 0.5, "sigma_v": 40.0, "sigma_over_m": 3.0,
        })
        matches.append("preset: Galaxia ana")
    elif re.search(r"\b(aglomerado|cluster|agrupamento)\b", t):
        changes.update({
            "log_m200": 14.0, "concentration": 5.0, "log_mbaryon": 13.0,
            "a_baryon": 30.0, "core_radius_kpc": 20.0, "sigma_v": 800.0,
        })
        matches.append("preset: Aglomerado")

    cand_map = [
        ("WIMPs", r"\bwimp"),
        ("Axions", r"\baxi[o]?n"),
        ("Neutrinos estereis", r"neutrino.{0,20}(esteril|estereis|sterile)"),
        ("Materia escura autointeragente (SIDM)", r"\bsidm\b|autointeragente|self[\s-]?interact"),
        ("Materia escura generica", r"materia escura generica|generic dark matter"),
    ]
    for label, pattern in cand_map:
        if re.search(pattern, t):
            changes["candidate"] = label
            matches.append(f"candidato -> {label}")
            break

    if re.search(r"\bsidm\b|nucleo fenomenologico|perfil sidm|core\s*sidm", t):
        changes["halo_model"] = "SIDM (nucleo fenomenologico)"
        changes["sim_halo_model"] = "SIDM"
        changes["density_model"] = "SIDM"
        matches.append("perfil -> SIDM")
    elif re.search(r"\bnfw\b|perfil nfw", t):
        changes["halo_model"] = "NFW"
        changes["sim_halo_model"] = "NFW"
        changes["density_model"] = "NFW"
        matches.append("perfil -> NFW")

    log_m200 = _find_m200_log(t)
    if log_m200 is not None:
        changes["log_m200"] = log_m200
        matches.append(f"log_m200 -> {log_m200:.3f}")

    log_mb = _find_mbaryon_log(t)
    if log_mb is not None:
        changes["log_mbaryon"] = log_mb
        matches.append(f"log_mbaryon -> {log_mb:.3f}")

    m = re.search(
        r"concentra[c]?[a]?[o]?\s*(?:do\s*halo\s*)?(?:de|=|:|com)?\s*(?:c\s*)?(?:=|:)?\s*(\d+(?:[.,]\d+)?)",
        t,
    ) or re.search(r"\bc\s*(?:do\s*halo)?\s*(?:=|:)\s*(\d+(?:[.,]\d+)?)", t)
    if m:
        val = _to_float(m.group(1))
        if val is not None:
            changes["concentration"] = val
            matches.append(f"concentration -> {val}")

    m = re.search(
        r"(?:escala|raio)\s*bari[o]?nic[ao]\s*(?:de|=|:|com)?\s*(\d+(?:[.,]\d+)?)",
        t,
    ) or re.search(r"\ba[_\s]?baryon\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)", t)
    if m:
        val = _to_float(m.group(1))
        if val is not None:
            changes["a_baryon"] = val
            matches.append(f"a_baryon -> {val}")

    m = re.search(
        r"(?:raio\s*(?:do\s*)?)?nucleo\s*(?:sidm\s*)?(?:de|=|:|com)?\s*(\d+(?:[.,]\d+)?)",
        t,
    ) or re.search(r"\bcore\s*(?:radius)?\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)", t)
    if m:
        val = _to_float(m.group(1))
        if val is not None:
            changes["core_radius_kpc"] = val
            matches.append(f"core_radius_kpc -> {val}")

    m = re.search(
        r"(?:raio\s*maximo|r[_\s]?plot[_\s]?max|max\s*radius)\s*(?:de|=|:|com)?\s*(\d+(?:[.,]\d+)?)",
        t,
    )
    if m:
        val = _to_float(m.group(1))
        if val is not None:
            changes["r_plot_max"] = val
            matches.append(f"r_plot_max -> {val}")

    m = (
        re.search(r"sigma\s*/\s*m\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)", t)
        or re.search(r"sigma\s*por\s*massa\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)", t)
        or re.search(r"se[c]?[a]?[o]?\s*de\s*choque\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)", t)
        or re.search(r"cross\s*section\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)", t)
    )
    if m:
        val = _to_float(m.group(1))
        if val is not None:
            changes["sigma_over_m"] = val
            matches.append(f"sigma_over_m -> {val}")

    m = re.search(
        r"(?:sigma[_\s]*v|dispers[a]?[o]?\s*(?:de\s*)?velocidade)\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)",
        t,
    )
    if m:
        val = _to_float(m.group(1))
        if val is not None:
            changes["sigma_v"] = val
            matches.append(f"sigma_v -> {val}")

    m = re.search(
        r"(?:intensidade\s*(?:do\s*)?)?feedback\s*(?:strength)?\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)",
        t,
    )
    if m:
        val = _to_float(m.group(1))
        if val is not None:
            changes["feedback_strength"] = val
            matches.append(f"feedback_strength -> {val}")

    m = re.search(
        r"(?:escala\s*(?:radial\s*)?(?:do\s*)?feedback|feedback\s*scale)\s*(?:=|:|com)?\s*(\d+(?:[.,]\d+)?)",
        t,
    )
    if m:
        val = _to_float(m.group(1))
        if val is not None:
            changes["feedback_scale_kpc"] = val
            matches.append(f"feedback_scale_kpc -> {val}")

    m = re.search(r"(\d+)\s*(?:particulas?|tracadores?|particles?|tracers?)", t)
    if m:
        changes["n_particles"] = int(m.group(1))
        matches.append(f"n_particles -> {changes['n_particles']}")

    m = re.search(r"(\d+)\s*(?:passos?|steps?)", t)
    if m:
        changes["n_steps"] = int(m.group(1))
        matches.append(f"n_steps -> {changes['n_steps']}")

    m = re.search(r"(?:passo\s*temporal|delta\s*t|\bdt\b)\s*(?:=|:|com)?\s*([\d.,]+)", t)
    if m:
        val = _to_float(m.group(1))
        if val is not None:
            changes["dt"] = val
            matches.append(f"dt -> {val}")

    m = re.search(r"\bg\s*(?:adimensional|dimensionless)?\s*(?:=|:|com)?\s*([\d.,]+)", t)
    if m:
        val = _to_float(m.group(1))
        if val is not None:
            changes["g_dimless"] = val
            matches.append(f"g_dimless -> {val}")

    m = re.search(r"(?:semente|seed)\s*(?:=|:|com)?\s*(\d+)", t)
    if m:
        changes["sim_seed"] = int(m.group(1))
        matches.append(f"sim_seed -> {changes['sim_seed']}")

    m = re.search(r"(?:suaviza[c]?[a]?[o]?|softening|epsilon)\s*(?:=|:|com)?\s*([\d.,]+)", t)
    if m:
        val = _to_float(m.group(1))
        if val is not None:
            changes["softening"] = val
            matches.append(f"softening -> {val}")

    m = re.search(r"registrar\s*(?:a\s*cada)?\s*(\d+)", t)
    if m:
        changes["record_every"] = int(m.group(1))
        matches.append(f"record_every -> {changes['record_every']}")

    filtered: dict = {}
    for key, value in changes.items():
        current = st.session_state.get(key)
        if isinstance(value, float) and isinstance(current, (int, float)):
            if abs(float(value) - float(current)) > 1e-12:
                filtered[key] = value
        elif value != current:
            filtered[key] = value
    return filtered, matches


_NL_NUM_RULES = {
    "log_m200": (8.0, 14.0, 0.1, False),
    "concentration": (2.0, 25.0, 0.5, False),
    "log_mbaryon": (6.0, 12.0, 0.1, False),
    "a_baryon": (0.2, 15.0, 0.1, False),
    "core_radius_kpc": (0.1, 30.0, 0.1, False),
    "r_plot_max": (5.0, 100.0, 1.0, False),
    "sigma_over_m": (0.0, 100.0, 0.1, False),
    "sigma_v": (20.0, 300.0, 5.0, False),
    "n_velocity_samples": (500, 20000, 500, True),
    "seed_velocity": (0, 2_147_483_647, None, True),
    "feedback_strength": (0.0, 0.9, 0.05, False),
    "feedback_scale_kpc": (0.2, 20.0, 0.2, False),
    "n_particles": (100, 2000, 100, True),
    "n_steps": (100, 10000, 100, True),
    "g_dimless": (0.001, 2.0, 0.005, False),
    "dt": (0.0001, 0.1, 0.001, False),
    "softening": (0.001, 0.5, 0.005, False),
    "sim_seed": (0, 2_147_483_647, None, True),
    "record_every": (10, 500, 10, True),
}
_NL_STR_KEYS = {"candidate", "halo_model", "density_model", "sim_halo_model"}


def apply_nl_changes(changes: dict):
    if not changes:
        return [], []
    applied: list = []
    skipped: list = []
    for key, value in changes.items():
        if key in _NL_NUM_RULES:
            lo, hi, step, is_int = _NL_NUM_RULES[key]
            try:
                num = float(value)
            except (TypeError, ValueError):
                skipped.append(f"{key}={value!r} (nao numerico)")
                continue
            num = max(lo, min(hi, num))
            if is_int:
                num = int(round(num))
            elif step:
                num = round(round(num / step) * step, 6)
            st.session_state[key] = num
            applied.append(f"{key} = {num}")
        elif key in _NL_STR_KEYS:
            text = str(value)
            valid_options = {
                "candidate": CANDIDATE_OPTIONS,
                "halo_model": HALO_MODEL_OPTIONS,
                "density_model": DENSITY_MODEL_OPTIONS,
                "sim_halo_model": SIM_HALO_MODEL_OPTIONS,
            }.get(key, [])
            if valid_options and text not in valid_options:
                skipped.append(f"{key}={text!r} (opcao invalida)")
                continue
            st.session_state[key] = text
            applied.append(f"{key} = {text}")
        else:
            skipped.append(f"{key} (desconhecido)")
    return applied, skipped


_pending = st.session_state.pop("nl_pending_changes", None)
if _pending:
    _applied, _skipped = apply_nl_changes(_pending)
    st.session_state["nl_last_applied"] = _applied
    st.session_state["nl_last_skipped"] = _skipped
    st.session_state["nl_last_timestamp"] = datetime.now().strftime("%H:%M:%S")
    st.session_state["nl_apply_count"] = int(st.session_state.get("nl_apply_count", 0)) + 1


# ----------------------- MODELOS FISICOS --------------------
def nfw_f(x):
    x = np.maximum(np.asarray(x, dtype=float), 1e-12)
    return np.log1p(x) - x / (1.0 + x)


def nfw_parameters(m200_msun, concentration):
    r200 = (3.0 * m200_msun / (4.0 * np.pi * 200.0 * RHO_CRIT)) ** (1.0 / 3.0)
    rs = r200 / concentration
    rho_s = m200_msun / (4.0 * np.pi * rs**3 * nfw_f(concentration))
    return r200, rs, rho_s


def halo_shape(x, model="NFW", core_x=0.15, feedback_strength=0.0, feedback_scale_x=0.15):
    x = np.asarray(x, dtype=float)
    x_safe = np.maximum(x, 1e-10)
    if model.upper().startswith("SIDM"):
        shape = 1.0 / ((x_safe + max(core_x, 1e-5)) * (1.0 + x_safe) ** 2)
    else:
        shape = 1.0 / (x_safe * (1.0 + x_safe) ** 2)
    scale = max(float(feedback_scale_x), 1e-5)
    suppression = 1.0 - np.clip(float(feedback_strength), 0.0, 0.9) * np.exp(-x / scale)
    return shape * suppression


def profile_density(radius_kpc, m200_msun, concentration, core_radius_kpc=3.0,
                    model="NFW", feedback_strength=0.0, feedback_scale_kpc=3.0):
    r200, rs, _ = nfw_parameters(m200_msun, concentration)
    x_core = max(core_radius_kpc / rs, 1e-5)
    x_fb = max(feedback_scale_kpc / rs, 1e-5)
    x_norm = np.linspace(0.0, concentration, 4000)
    shape_norm = halo_shape(x_norm, model, x_core, feedback_strength, x_fb)
    integral = trapezoid_compat(shape_norm * x_norm**2, x_norm)
    rho0 = m200_msun / (4.0 * np.pi * rs**3 * max(integral, 1e-30))
    radius = np.asarray(radius_kpc, dtype=float)
    x = np.maximum(radius / rs, 1e-10)
    return rho0 * halo_shape(x, model, x_core, feedback_strength, x_fb)


def build_profile_lookup(concentration, model="NFW", core_x=0.15,
                          feedback_strength=0.0, feedback_scale_x=0.15, grid_size=3500):
    c = float(concentration)
    x_grid = np.unique(np.concatenate(([0.0], np.geomspace(1e-6, c, grid_size))))
    shape = halo_shape(x_grid, model, core_x, feedback_strength, feedback_scale_x)
    integrand = x_grid**2 * shape
    dx = np.diff(x_grid)
    increments = 0.5 * (integrand[1:] + integrand[:-1]) * dx
    cumulative = np.concatenate(([0.0], np.cumsum(increments)))
    norm = max(float(cumulative[-1]), 1e-30)
    mass_fraction = np.clip(cumulative / norm, 0.0, 1.0)
    dmdx = integrand / norm
    kernel = np.zeros_like(x_grid)
    np.divide(dmdx, x_grid, out=kernel, where=x_grid > 0)
    if len(kernel) > 1:
        kernel[0] = kernel[1]
    outer_integral = np.zeros_like(x_grid)
    reverse_increments = 0.5 * (kernel[1:] + kernel[:-1]) * dx
    outer_integral[:-1] = np.cumsum(reverse_increments[::-1])[::-1]
    potential = -(mass_fraction / np.maximum(x_grid, 1e-8) + outer_integral)
    potential[0] = potential[1] if len(potential) > 1 else -1.0
    return x_grid, mass_fraction, potential


def _mass_fraction(radius_over_rs, concentration, model, core_radius_kpc,
                   rs, feedback_strength=0.0, feedback_scale_kpc=3.0):
    if model.upper().startswith("NFW") and feedback_strength <= 0:
        return nfw_f(np.minimum(np.maximum(radius_over_rs, 1e-12), concentration)) / nfw_f(concentration)
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
    """Curva de rotacao de halo + componente barionica de Hernquist.

    Retorna tambem M_DM(<r) e M_baryon(<r) para diagnostico de fracao.
    """
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


# --------------------- CSV OBSERVACIONAL --------------------
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
    attempts = [(",", "virgula"), (";", "ponto e virgula"), ("\t", "tab"), (None, "auto")]
    token_to_standard = {}
    for standard, aliases in HEADER_ALIASES.items():
        token_to_standard[_header_token(standard)] = standard
        for alias in aliases:
            token_to_standard[_header_token(alias)] = standard
    best_columns = []
    best_frame = None
    best_separator = "desconhecido"
    best_score = (-1, -1)
    parse_errors = []
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
                best_frame = frame.copy()
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
        except Exception as exc:
            parse_errors.append(str(exc))
            continue
    detected_tokens = {_header_token(col) for col in best_columns}
    looks_like_simulation_history = (
        any(token in detected_tokens for token in {"tempoadimensional", "time", "timeadimensional"})
        and any(token in detected_tokens for token in {"energiaespecificamediaproxy", "energy", "totalenergy", "energyproxy"})
    )
    header_text = repr(best_columns or "nao foi possivel ler o cabecalho")
    if looks_like_simulation_history:
        raise ValueError(
            "Este arquivo parece ser um historico da simulacao (tempo versus energia), "
            "nao dados observacionais de curva de rotacao. Cabecalhos detectados: "
            f"{header_text}. Para comparar a curva de rotacao, use as colunas obrigatorias "
            "radius_kpc e v_obs_kms; v_err_kms e opcional."
        )
    if {"radius_kpc", "v_obs_kms"}.issubset({token_to_standard.get(_header_token(c)) for c in best_columns}):
        reason = "As colunas foram reconhecidas, mas nao encontrei linhas numericas validas."
    else:
        reason = "Nao encontrei as colunas obrigatorias de raio e velocidade observada."
    raise ValueError(f"{reason} Cabecalhos detectados: {header_text}.")


# ------------------ SIMULACAO DE TRACADORES -----------------
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


def tracer_acceleration(positions, g_dimless, mass_x, mass_fraction, softening):
    r = np.linalg.norm(positions, axis=1)
    r_safe = np.maximum(r, 1e-10)
    enclosed = np.interp(r_safe, mass_x, mass_fraction, left=0.0, right=1.0)
    denom = (r_safe**2 + softening**2) ** 1.5
    return -g_dimless * enclosed[:, None] * positions / denom[:, None]


def tracer_energy_proxy(positions, velocities, g_dimless, mass_x, potential_x):
    r = np.maximum(np.linalg.norm(positions, axis=1), 1e-8)
    kinetic = 0.5 * np.sum(velocities**2, axis=1)
    phi = np.interp(r, mass_x, potential_x, left=potential_x[0], right=np.nan)
    outside = r > mass_x[-1]
    if np.any(outside):
        phi[outside] = -1.0 / r[outside]
    return float(np.mean(kinetic + g_dimless * phi))


def explain_simulation_physics(step, time_value, params, energy, energy_drift, velocity_rms,
                               radius_rms, mean_radius, event_type, status):
    n_steps = max(int(params.get("n_steps", 1)), 1)
    progress = 100.0 * min(max(int(step), 0), n_steps) / n_steps
    drift_abs = abs(float(energy_drift)) if np.isfinite(energy_drift) else float("nan")
    if not np.isfinite(drift_abs):
        energy_comment = "A variacao relativa da energia nao pode ser avaliada porque a energia inicial e proxima de zero."
    elif drift_abs < 1.0:
        energy_comment = "O desvio relativo da energia proxy e pequeno (<1%); o diagnostico e consistente com boa estabilidade numerica."
    elif drift_abs < 5.0:
        energy_comment = "O desvio relativo da energia proxy e moderado (1-5%); vale testar passo temporal menor."
    else:
        energy_comment = "O desvio relativo da energia proxy supera 5%; recomenda-se reduzir o passo temporal."
    g_value = float(params.get("g_dimless", float("nan")))
    dt_value = float(params.get("dt", float("nan")))
    if str(event_type).lower() in {"inicializacao", "reinicializacao", "reinicio_apos_conclusao"}:
        phase = "As condicoes iniciais foram sorteadas a partir da semente definida."
    elif str(event_type).lower() in {"pausa", "retomada", "inicio", "conclusao"}:
        phase = f"Evento de controle: {event_type}. Tracadores em potencial fixo."
    else:
        phase = "O estado foi amostrado no intervalo de registro configurado."
    drift_text = f"{float(energy_drift):+.4g}%" if np.isfinite(energy_drift) else "N/D"
    return (
        f"Evento={event_type}; estado={status}; passo={int(step)}/{n_steps} ({progress:.1f}%); "
        f"tempo adimensional t={float(time_value):.6g}. {phase} "
        f"G adimensional={g_value:.5g}, delta t={dt_value:.5g}; "
        f"energia especifica media proxy={float(energy):.7g}; desvio desde o inicio={drift_text}. "
        f"Velocidade RMS={float(velocity_rms):.6g}; raio RMS={float(radius_rms):.6g}; "
        f"raio medio={float(mean_radius):.6g}. {energy_comment}"
    )


def record_simulation_history(event_type="snapshot", positions=None, velocities=None, energy=None,
                              params=None, status=None, step=None):
    if positions is None:
        positions = st.session_state.get("sim_positions")
    if velocities is None:
        velocities = st.session_state.get("sim_velocities")
    if positions is None or velocities is None:
        return
    positions = np.asarray(positions, dtype=float)
    velocities = np.asarray(velocities, dtype=float)
    params = dict(params or st.session_state.get("sim_params", {}))
    if not params:
        return
    if step is None:
        step = int(st.session_state.get("sim_step", 0))
    step = int(step)
    time_value = float(step * float(params.get("dt", 0.0)))
    if energy is None:
        mass_x = st.session_state.get("sim_mass_x")
        potential_x = st.session_state.get("sim_potential_x")
        if mass_x is not None and potential_x is not None:
            energy = tracer_energy_proxy(positions, velocities, params["g_dimless"], mass_x, potential_x)
        else:
            energy = float("nan")
    energy = float(energy)
    energy_series = st.session_state.get("sim_energy", [])
    energy_initial = float(energy_series[0]) if len(energy_series) else float("nan")
    if np.isfinite(energy_initial) and abs(energy_initial) > 1e-12 and np.isfinite(energy):
        energy_drift = 100.0 * (energy - energy_initial) / abs(energy_initial)
    else:
        energy_drift = float("nan")
    velocity_rms = float(np.sqrt(np.mean(np.sum(velocities ** 2, axis=1))))
    radii = np.linalg.norm(positions, axis=1)
    radius_rms = float(np.sqrt(np.mean(radii ** 2)))
    mean_radius = float(np.mean(radii))
    status_value = str(status if status is not None else st.session_state.get("sim_status", "Desconhecido"))
    physics_log = explain_simulation_physics(
        step, time_value, params, energy, energy_drift, velocity_rms,
        radius_rms, mean_radius, event_type, status_value,
    )
    entry = {
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "run_id": int(st.session_state.get("simulation_run_counter", 0)),
        "event_type": str(event_type),
        "step": step,
        "n_steps": int(params.get("n_steps", 0)),
        "time_adimensional": time_value,
        "status": status_value,
        "energy_specific_mean_proxy": energy,
        "energy_initial_proxy": energy_initial,
        "energy_delta_proxy": float(energy - energy_initial) if np.isfinite(energy) and np.isfinite(energy_initial) else float("nan"),
        "energy_drift_percent": float(energy_drift),
        "velocity_rms": velocity_rms,
        "radius_rms": radius_rms,
        "mean_radius": mean_radius,
        "parameters": params.copy(),
        "physics_log": physics_log,
    }
    history = list(st.session_state.get("simulation_history", []))
    history.append(entry)
    st.session_state["simulation_history"] = history[-MAX_SIMULATION_HISTORY:]
    st.session_state["simulation_history_version"] = int(st.session_state.get("simulation_history_version", 0)) + 1
    st.session_state["latest_physics_log"] = physics_log


def record_current_simulation_event(event_type, status=None):
    if not all(key in st.session_state for key in ("sim_positions", "sim_velocities", "sim_params")):
        return
    params = st.session_state.sim_params
    record_simulation_history(
        event_type=event_type,
        positions=st.session_state.sim_positions,
        velocities=st.session_state.sim_velocities,
        params=params, status=status, step=st.session_state.get("sim_step", 0),
    )


def history_dataframe(history):
    columns = [
        "recorded_at", "run_id", "event_type", "step", "n_steps", "time_adimensional", "status",
        "energy_specific_mean_proxy", "energy_initial_proxy", "energy_delta_proxy", "energy_drift_percent",
        "velocity_rms", "radius_rms", "mean_radius", "parameters_json", "physics_log",
    ]
    rows = []
    for item in history:
        row = {key: item.get(key) for key in columns if key != "parameters_json"}
        row["parameters_json"] = json.dumps(item.get("parameters", {}), ensure_ascii=False, sort_keys=True)
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def cached_history_dataframe(history):
    version = int(st.session_state.get("simulation_history_version", 0))
    if st.session_state.get("simulation_history_dataframe_cache_version") != version:
        st.session_state["simulation_history_dataframe_cache"] = history_dataframe(history)
        st.session_state["simulation_history_dataframe_cache_version"] = version
    return st.session_state.get("simulation_history_dataframe_cache", pd.DataFrame())


def initialise_simulation(params, event_type="inicializacao"):
    lookup = build_profile_lookup(
        concentration=params["concentration"], model=params["halo_model"],
        core_x=params["core_radius_over_rs"], feedback_strength=params["feedback_strength"],
        feedback_scale_x=params["feedback_scale_over_rs"],
    )
    mass_x, mass_fraction, potential_x = lookup
    positions, velocities = create_initial_tracers(
        params["n_particles"], params["seed"], params["concentration"], mass_x, mass_fraction, params["g_dimless"]
    )
    accelerations = tracer_acceleration(positions, params["g_dimless"], mass_x, mass_fraction, params["softening"])
    st.session_state.sim_positions = positions
    st.session_state.sim_velocities = velocities
    st.session_state.sim_accelerations = accelerations
    st.session_state.sim_mass_x = mass_x
    st.session_state.sim_mass_fraction = mass_fraction
    st.session_state.sim_potential_x = potential_x
    st.session_state.sim_step = 0
    st.session_state.sim_snapshots = [positions.copy()]
    st.session_state.sim_times = [0.0]
    st.session_state.sim_energy = [tracer_energy_proxy(positions, velocities, params["g_dimless"], mass_x, potential_x)]
    st.session_state.sim_status = "Pronta para executar"
    st.session_state.sim_params = params.copy()
    st.session_state.simulation_run_counter = int(st.session_state.get("simulation_run_counter", 0)) + 1
    record_simulation_history(
        event_type=event_type, positions=positions, velocities=velocities,
        energy=st.session_state.sim_energy[0], params=params,
        status=st.session_state.sim_status, step=0,
    )


def integrate_chunk(params, max_chunk=200):
    remaining = params["n_steps"] - st.session_state.sim_step
    if remaining <= 0:
        st.session_state.sim_status = "Concluida"
        return
    count = min(max_chunk, remaining)
    pos = st.session_state.sim_positions
    vel = st.session_state.sim_velocities
    acc = st.session_state.sim_accelerations
    mass_x = st.session_state.sim_mass_x
    mass_fraction = st.session_state.sim_mass_fraction
    potential_x = st.session_state.sim_potential_x
    dt = params["dt"]
    for _ in range(count):
        vel_half = vel + 0.5 * dt * acc
        pos = pos + dt * vel_half
        acc_new = tracer_acceleration(pos, params["g_dimless"], mass_x, mass_fraction, params["softening"])
        vel = vel_half + 0.5 * dt * acc_new
        acc = acc_new
        st.session_state.sim_step += 1
        if (st.session_state.sim_step % max(1, params["record_every"]) == 0
                or st.session_state.sim_step == params["n_steps"]):
            st.session_state.sim_snapshots.append(pos.copy())
            st.session_state.sim_times.append(st.session_state.sim_step * dt)
            energy_now = tracer_energy_proxy(pos, vel, params["g_dimless"], mass_x, potential_x)
            st.session_state.sim_energy.append(energy_now)
            record_simulation_history(
                event_type="instantaneo_periodico", positions=pos, velocities=vel,
                energy=energy_now, params=params,
                status=st.session_state.sim_status, step=st.session_state.sim_step,
            )
    st.session_state.sim_positions = pos
    st.session_state.sim_velocities = vel
    st.session_state.sim_accelerations = acc
    if st.session_state.sim_step >= params["n_steps"] and st.session_state.sim_status != "Concluida":
        st.session_state.sim_status = "Concluida"
        record_current_simulation_event("conclusao", status="Concluida")


# -------------------------- RELATORIO PDF -------------------
def _pdf_ascii(value):
    text = str(value).replace("\ufeff", "")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text.replace("\u2022", "-").replace("\u2013", "-").replace("\u2014", "-")


class DarkMatterPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(115, 140, 190)
        self.cell(0, 7, "DARK MATTER LAB | RELATORIO CIENTIFICO", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(95, 115, 160)
        self.line(10, 18, 200, 18)
        self.ln(5)

    def footer(self):
        self.set_y(-13)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 140, 160)
        self.cell(0, 8, f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} | Pagina {self.page_no()}", align="C")


def generate_pdf_report(report_data, figures=None, rotation_figure=None):
    pdf = DarkMatterPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    pdf.set_text_color(25, 35, 55)
    pdf.set_font("Helvetica", "B", 19)
    pdf.multi_cell(0, 10, "Laboratorio de Materia Escura", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        0, 6,
        "Relatorio reproduzivel de parametros, modelos, diagnosticos numericos, historico e visualizacoes cientificas.",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(3)

    def section(title):
        pdf.ln(2)
        pdf.set_fill_color(229, 235, 247)
        pdf.set_text_color(28, 49, 87)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, _pdf_ascii(title), fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(35, 42, 55)

    def table(rows):
        pdf.set_font("Helvetica", "", 9)
        for key, value in rows:
            key_text = _pdf_ascii(key)
            value_text = _pdf_ascii(value)
            key_width = 69
            value_width = pdf.w - pdf.r_margin - pdf.l_margin - key_width
            key_lines = max(1, len(pdf.multi_cell(key_width, 5.5, key_text, dry_run=True, output="LINES")))
            value_lines = max(1, len(pdf.multi_cell(value_width, 5.5, value_text, dry_run=True, output="LINES")))
            row_height = max(key_lines, value_lines) * 5.5 + 1
            if pdf.get_y() + row_height > pdf.h - pdf.b_margin:
                pdf.add_page()
            x, y = pdf.get_x(), pdf.get_y()
            pdf.set_font("Helvetica", "B", 9)
            pdf.multi_cell(key_width, 5.5, key_text, border=1, new_x="RIGHT", new_y="TOP")
            pdf.set_xy(x + key_width, y)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(value_width, 5.5, value_text, border=1, new_x="LMARGIN", new_y="NEXT")
            pdf.set_y(y + row_height)

    section("1. Modelos teoricos e parametros fisicos")
    table(report_data.get("physics_rows", []))

    section("2. Curvas de rotacao e dados")
    table(report_data.get("rotation_rows", []))

    if report_data.get("dm_diagnostic_rows"):
        section("3. Diagnostico de materia escura")
        table(report_data.get("dm_diagnostic_rows", []))

    figure_warnings = []
    named_figures = dict(figures or {})
    if rotation_figure is not None and not named_figures:
        named_figures["Curva de rotacao"] = rotation_figure

    if named_figures:
        section("4. Visualizacoes cientificas (PNG via Kaleido)")
        for figure_title, figure in named_figures.items():
            temp_path = None
            try:
                static_figure = go.Figure(figure)
                static_figure.update_layout(
                    width=1400, height=800, autosize=False,
                    template="plotly_white", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
                    font=dict(family="Arial, sans-serif", size=15, color="#182235"),
                    title=dict(font=dict(size=23, color="#182235")),
                    margin=dict(l=105, r=55, t=110, b=105),
                    legend=dict(bgcolor="rgba(255,255,255,0.88)", bordercolor="#d4dae5", borderwidth=1),
                )
                image_bytes = static_figure.to_image(format="png", width=1400, height=800, scale=1, engine="kaleido")
                with tempfile.NamedTemporaryFile(prefix="dark_matter_plot_", suffix=".png", delete=False) as temp_img:
                    temp_img.write(image_bytes)
                    temp_path = temp_img.name
                image_width_mm = 180.0
                image_height_mm = image_width_mm * 800.0 / 1400.0
                if pdf.get_y() + 9.0 + 8.0 + image_height_mm + 5 > pdf.h - pdf.b_margin:
                    pdf.add_page()
                pdf.set_text_color(28, 49, 87)
                pdf.set_font("Helvetica", "B", 11)
                pdf.multi_cell(0, 7, _pdf_ascii(figure_title), new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(65, 75, 95)
                pdf.set_font("Helvetica", "", 8)
                pdf.multi_cell(
                    0, 4.2,
                    "Imagem estatica exportada em 1400 x 800 px; titulo, eixos, graduacoes e legenda fazem parte do PNG.",
                    new_x="LMARGIN", new_y="NEXT",
                )
                pdf.image(temp_path, x=15, w=image_width_mm)
                pdf.ln(4)
            except Exception as exc:
                warning = (
                    f"{figure_title}: falha na exportacao PNG via Kaleido. Verifique Plotly/Kaleido "
                    f"e a instalacao indicada no requirements.txt. Detalhe: {str(exc)[:240]}"
                )
                figure_warnings.append(warning)
                pdf.set_text_color(120, 45, 45)
                pdf.set_font("Helvetica", "B", 9)
                pdf.multi_cell(0, 5.2, _pdf_ascii("Grafico nao incorporado: " + warning), new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(35, 42, 55)
            finally:
                if temp_path:
                    try:
                        Path(temp_path).unlink(missing_ok=True)
                    except Exception:
                        pass

    section("5. Configuracao e estado da simulacao")
    table(report_data.get("simulation_rows", []))

    section("6. Historico de instantaneos da simulacao")
    history_rows = report_data.get("history_rows", [])
    if history_rows:
        table(history_rows)
    else:
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5.5, "Nenhum instantaneo foi registrado nesta sessao.", new_x="LMARGIN", new_y="NEXT")

    section("7. Log automatico: interpretacao fisica de cada momento")
    logs = report_data.get("physics_log", [])
    if logs:
        pdf.set_font("Helvetica", "", 8.5)
        for item in logs:
            pdf.multi_cell(0, 4.8, _pdf_ascii(item), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
    else:
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5.5, "O log sera preenchido quando a simulacao for inicializada e avancar.", new_x="LMARGIN", new_y="NEXT")

    section("8. Interpretacao e limitacoes cientificas")
    pdf.set_font("Helvetica", "", 9)
    notes = [
        "O perfil NFW e parametrizado por massa M200 e concentracao; R200 e rs sao derivados com H0 de referencia igual a 70 km/s/Mpc.",
        "O perfil SIDM com nucleo e o efeito de feedback sao parametrizacoes fenomenologicas para exploracao; nao sao simulacoes hidrodinamicas nem solucoes completas de transporte colisional.",
        "A distribuicao de velocidades e uma amostra Maxwelliana idealizada com dispersao por componente. Nao equivale a uma solucao completa da equacao de Jeans.",
        "Os pontos observacionais sao sinteticos quando nenhum CSV valido e carregado. Os resultados quantitativos nao devem ser interpretados como descoberta ou limite experimental.",
        "A integracao acompanha tracadores em potencial fixo. As particulas-tracadoras nao interagem umas com as outras, e a suavizacao e a interpolacao podem introduzir desvios no diagnostico energetico.",
        "A secao de choque por massa e reportada em cm^2/g. O comprimento livre medio calculado na escala rs e apenas uma estimativa local com a densidade do perfil adotado.",
        "A energia registrada e uma proxy de energia especifica media do modelo numerico, nao uma medicao experimental nem a energia total de um sistema autogravitante completo.",
        "O assistente de linguagem natural apenas escreve nas chaves do st.session_state; toda a fisica e a numerica permanecem as mesmas do modelo.",
        "A fracao de materia escura exibida e M_DM(<r) / [M_DM(<r) + M_baryon(<r)] para um halo NFW/SIDM normalizado a M200 dentro de R200. Nao inclui correcoes de selecao observacional.",
    ]
    for note in notes:
        pdf.multi_cell(0, 5.5, _pdf_ascii("- " + note), new_x="LMARGIN", new_y="NEXT")

    output = pdf.output()
    pdf_bytes = output.encode("latin-1") if isinstance(output, str) else bytes(output)
    return pdf_bytes, (figure_warnings or None)


# ---------------------- CABECALHO ---------------------------
st.title("🌌 Dark Matter Lab")
st.markdown(
    '<p class="lab-subtitle">Laboratorio interativo para halos NFW, materia escura autointeragente, '
    'dinamica estelar, feedback barionico, simulacoes numericas e assistente de configuracao por IA.</p>',
    unsafe_allow_html=True,
)
st.caption("Modelagem astrofisica + graficos Plotly + integracao numerica + historico + PDF + linguagem natural")

# -------------------------- ABAS ----------------------------
tab_dm, tab_model, tab_rotation, tab_feedback, tab_sim, tab_assistant = st.tabs([
    "⑥ O que é matéria escura?",
    "① Modelos teoricos e particulas",
    "② Curvas de rotacao",
    "③ Feedback barionico e densidade",
    "④ Simulacao, calculadora e relatorio",
    "⑤ Assistente IA (linguagem natural)",
])

# ============================================================
# ABA ⑥ - O QUE E MATERIA ESCURA?
# ============================================================
with tab_dm:
    st.subheader("🌌 O que é matéria escura?")
    st.markdown(
        """
        <div class="dm-callout">
        <b>Matéria escura</b> é uma forma de matéria que <b>não emite, absorve ou reflete luz</b> de forma
        detectável — ela interage gravitacionalmente com a matéria comum, mas é transparente para radiação
        eletromagnética. Sabemos que ela existe porque <b>a matéria que vemos não explica os movimentos
        que medimos</b>.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Por que precisamos dela? As evidências")
    ev1, ev2, ev3 = st.columns(3)
    with ev1:
        st.markdown("#### 🔭 Curvas de rotação")
        st.markdown(
            "Em galáxias espirais, a velocidade orbital do gás e das estrelas **não cai** depois que "
            "a matéria visível acaba. Sem matéria escura, deveria cair como `v ∝ 1/√r` (Kepler). "
            "Ela fica **plana** em ~220 km/s até dezenas de kpc."
        )
    with ev2:
        st.markdown("#### 🔍 Lentes gravitacionais")
        st.markdown(
            "A luz de galáxias distantes é curvada por massas que **não vemos** — o Bullet Cluster "
            "mostra a massa total separada do gás quente, indicando matéria escura colisionalmente livre."
        )
    with ev3:
        st.markdown("#### 📡 CMB e estrutura")
        st.markdown(
            "As anisotropias do fundo cósmico de micro-ondas e a formação de estruturas em larga escala "
            "só batem com o modelo ΛCDM se ~85% da matéria for **fria e não-bariônica**."
        )

    st.divider()
    st.markdown("### Demonstração numérica com os parâmetros atuais")
    st.caption(
        "Os valores padrão do app estão calibrados para a **Via Láctea**: M200 = 10¹² M☉, "
        "concentração c = 10, massa bariônica M_bárion ≈ 5×10¹⁰ M☉. Os controles na aba ① permitem "
        "alterar cada um destes parâmetros; o diagnóstico abaixo é recalculado automaticamente."
    )

    m200_now = 10.0 ** st.session_state["log_m200"]
    m_baryon_now = 10.0 ** st.session_state["log_mbaryon"]
    c_now = st.session_state["concentration"]
    a_now = st.session_state["a_baryon"]
    core_now = st.session_state["core_radius_kpc"]
    rmax_now = st.session_state["r_plot_max"]
    model_now = "SIDM" if st.session_state["halo_model"].upper().startswith("SIDM") else "NFW"
    fb_now = st.session_state["feedback_strength"]
    fbs_now = st.session_state["feedback_scale_kpc"]

    r200_dm, rs_dm, _ = nfw_parameters(m200_now, c_now)

    # FIX: constroi r_diag garantindo tamanho consistente e sempre >= 1 elemento.
    r_diag_candidates = np.array([8.0, 15.0, 30.0], dtype=float)
    r_diag = r_diag_candidates[r_diag_candidates <= max(rmax_now, 30.0)]
    if r_diag.size == 0:
        r_diag = np.array([max(rmax_now * 0.5, 5.0)], dtype=float)
    r_diag = as_1d(r_diag)

    # FIX: normaliza todas as saidas para 1-D antes de qualquer operacao.
    v_dm_d, v_b_d, v_tot_d, _, _, m_dm_d, m_b_d = rotation_components(
        r_diag, m200_now, c_now, m_baryon_now, a_now,
        model=model_now, core_radius_kpc=core_now,
        feedback_strength=fb_now, feedback_scale_kpc=fbs_now,
    )
    v_dm_d = as_1d(v_dm_d)
    v_b_d = as_1d(v_b_d)
    v_tot_d = as_1d(v_tot_d)
    m_dm_d = as_1d(m_dm_d)
    m_b_d = as_1d(m_b_d)
    dm_frac_d = m_dm_d / np.maximum(m_dm_d + m_b_d, 1e-30)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("M200 (halo total)", f"{m200_now:.2e} M☉")
    col2.metric("M_bárion (visível)", f"{m_baryon_now:.2e} M☉")
    col3.metric("Razão M200 / M_bárion", f"{m200_now / max(m_baryon_now, 1e-30):.1f}")
    r30 = min(30.0, rmax_now)
    _, _, f30 = dark_matter_fraction_at_radius(
        np.array([r30]), m200_now, c_now, m_baryon_now, a_now,
        model=model_now, core_radius_kpc=core_now,
        feedback_strength=fb_now, feedback_scale_kpc=fbs_now,
    )
    col4.metric(f"Fração de ME em {r30:.0f} kpc", f"{float(as_1d(f30)[0]) * 100:.1f}%")

    radii_dm = np.linspace(max(0.2, rmax_now / 200.0), rmax_now, 300)
    v_nfw_d, v_bar_d, v_tot_d_full, _, _, _, _ = rotation_components(
        radii_dm, m200_now, c_now, m_baryon_now, a_now,
        model="NFW", core_radius_kpc=core_now,
        feedback_strength=0.0, feedback_scale_kpc=fbs_now,
    )
    v_kepler = np.sqrt(G_ASTRO * m_baryon_now / np.maximum(radii_dm, 1e-8))

    fig_dm = go.Figure()
    fig_dm.add_trace(go.Scatter(
        x=radii_dm, y=v_tot_d_full, mode="lines", name="Com matéria escura (NFW+bárions)",
        line=dict(color="#8b7cff", width=4),
    ))
    fig_dm.add_trace(go.Scatter(
        x=radii_dm, y=v_bar_d, mode="lines", name="SÓ bárions (sem ME)",
        line=dict(color="#ffbd69", width=3, dash="dash"),
    ))
    fig_dm.add_trace(go.Scatter(
        x=radii_dm, y=v_kepler, mode="lines", name="Expectativa Kepleriana (v ∝ 1/√r)",
        line=dict(color="#f472b6", width=2, dash="dot"),
    ))
    fig_dm.update_layout(
        template="plotly_dark", height=480,
        title="Diagnóstico: por que a matéria escura é necessária",
        xaxis_title="Raio galactocêntrico (kpc)", yaxis_title="Velocidade circular (km/s)",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
        legend=dict(orientation="h", y=1.13),
    )
    st.plotly_chart(fig_dm, use_container_width=True)

    st.markdown(
        """
        <div class="dm-callout">
        <b>Leitura do gráfico:</b> a curva <span style="color:#8b7cff"><b>roxa</b></span> (com ME) permanece
        aproximadamente plana. A curva <span style="color:#ffbd69"><b>laranja</b></span> (só bárions) e a
        <span style="color:#f472b6"><b>rosa pontilhada</b></span> (Kepler) caem após o raio visível.
        Sem matéria escura, as estrelas nas partes externas da galáxia deveriam orbitar muito mais devagar
        — mas elas não orbitam. A discrepância é a <b>evidência clássica</b> de matéria escura.
        </div>
        """,
        unsafe_allow_html=True,
    )

    r_frac = np.linspace(max(0.5, rmax_now / 100.0), rmax_now, 200)
    _, _, frac_dm_curve = dark_matter_fraction_at_radius(
        r_frac, m200_now, c_now, m_baryon_now, a_now,
        model=model_now, core_radius_kpc=core_now,
        feedback_strength=fb_now, feedback_scale_kpc=fbs_now,
    )
    frac_dm_curve = as_1d(frac_dm_curve)
    fig_frac = go.Figure()
    fig_frac.add_trace(go.Scatter(
        x=r_frac, y=100.0 * frac_dm_curve, mode="lines",
        name="Fração de matéria escura",
        line=dict(color="#58c4dd", width=3),
        fill="tozeroy", fillcolor="rgba(88,196,221,0.15)",
    ))
    fig_frac.add_hline(y=50, line=dict(color="#aabbd7", dash="dot", width=1),
                       annotation_text="50% (equipartição)", annotation_position="top left")
    fig_frac.update_layout(
        template="plotly_dark", height=380,
        title="Quanto da massa dentro de cada raio é matéria escura?",
        xaxis_title="Raio galactocêntrico (kpc)", yaxis_title="M_DM / M_total (%)",
        yaxis_range=[0, 100],
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
    )
    st.plotly_chart(fig_frac, use_container_width=True)
    st.caption(
        "No centro da galáxia, os bárions dominam; na periferia, a matéria escura representa "
        "mais de 80–90% da massa total. Esta transição é a assinatura observacional do halo."
    )

    # ============================================================
    # FIX PRINCIPAL: tabela de diagnóstico defensiva.
    # Normaliza todas as colunas para 1-D e alinha ao menor comprimento
    # comum. Se algo divergir, mostramos um aviso tecnico em vez de
    # derrubar o app com "All arrays must be of the same length".
    # ============================================================
    st.markdown("### Tabela de diagnóstico")

    _cols = {
        "Raio (kpc)": as_1d(r_diag),
        "v_DM (km/s)": as_1d(v_dm_d),
        "v_bárion (km/s)": as_1d(v_b_d),
        "v_total (km/s)": as_1d(v_tot_d),
        "M_DM (<r) [M☉]": as_1d(m_dm_d),
        "M_bárion (<r) [M☉]": as_1d(m_b_d),
        "Fração de ME": as_1d(dm_frac_d),
    }
    _sizes = {name: arr.size for name, arr in _cols.items()}
    n_rows = int(min(_sizes.values())) if _sizes else 0

    if n_rows == 0:
        st.warning("Diagnóstico de matéria escura indisponível com os parâmetros atuais.")
    else:
        if len(set(_sizes.values())) > 1:
            st.caption(
                "Nota técnica: comprimentos internos "
                + ", ".join(f"{k}={v}" for k, v in _sizes.items())
                + f"; a tabela usa o mínimo comum ({n_rows}). Isso não afeta os gráficos."
            )
        diag_df = pd.DataFrame({
            "Raio (kpc)": _cols["Raio (kpc)"][:n_rows],
            "v_DM (km/s)": _cols["v_DM (km/s)"][:n_rows],
            "v_bárion (km/s)": _cols["v_bárion (km/s)"][:n_rows],
            "v_total (km/s)": _cols["v_total (km/s)"][:n_rows],
            "M_DM (<r) [M☉]": _cols["M_DM (<r) [M☉]"][:n_rows],
            "M_bárion (<r) [M☉]": _cols["M_bárion (<r) [M☉]"][:n_rows],
            "Fração de ME": [f"{x*100:.1f}%" for x in _cols["Fração de ME"][:n_rows]],
        })
        st.dataframe(diag_df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### O que a matéria escura NÃO é")
    nao1, nao2, nao3 = st.columns(3)
    with nao1:
        st.markdown(
            "**Não é modificação da gravidade**  \n"
            "Alternativas como MOND explicam curvas de rotação, mas falham em lentes "
            "do Bullet Cluster e no CMB."
        )
    with nao2:
        st.markdown(
            "**Não é antimatéria**  \n"
            "Antimatéria aniquilaria com matéria comum, produzindo raios γ que não observamos."
        )
    with nao3:
        st.markdown(
            "**Não é buraco negro comum**  \n"
            "Buracos negros primordiais (MACHOs) foram descartados por microlentes em "
            "larga escala."
        )

    st.markdown("### O que ela PODERIA ser")
    st.markdown(
        "- **WIMPs**: partículas massivas que interagem pela força fraca.\n"
        "- **Axions**: partículas ultraleves previstas para resolver o problema CP forte da QCD.\n"
        "- **Neutrinos estéreis**: neutrinos pesados que não interagem pela força fraca padrão.\n"
        "- **SIDM**: matéria escura que colide consigo mesma, resolvendo problemas de pequena escala.\n"
        "- **Outros**: supersimetria, dimensões extras, etc."
    )
    st.info(
        "Nenhuma dessas hipóteses foi confirmada. A natureza microscópica da matéria escura é um dos "
        "maiores problemas abertos da física contemporânea."
    )

# ============================================================
# ABA 1 - MODELOS TEORICOS
# ============================================================
with tab_model:
    st.subheader("Modelos teoricos: NFW e materia escura autointeragente")
    st.write(
        "Configure o halo, as propriedades do candidato de materia escura e a distribuicao de velocidades. "
        "O perfil SIDM usa um nucleo fenomenologico ajustavel; a secao de choque e apresentada tambem por "
        "meio de uma estimativa local de comprimento livre medio."
    )
    st.caption(
        "**Nota pedagógica:** com os valores padrão, você está modelando a Via Láctea. "
        "Se você reduzir `log_m200` para 10 (galáxia anã) ou aumentar para 14 (aglomerado), "
        "a curva de rotação e a fração de matéria escura mudam drasticamente."
    )
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        candidate = st.selectbox("Candidato / cenario microscopico", CANDIDATE_OPTIONS, key="candidate")
        halo_model = st.selectbox("Perfil de halo para analises complementares", HALO_MODEL_OPTIONS, key="halo_model")
        log_m200 = st.slider("Log10 da massa M200 (massas solares)", 8.0, 14.0, step=0.1, key="log_m200")
        concentration = st.slider("Concentracao do halo c", 2.0, 25.0, step=0.5, key="concentration")
    with col_b:
        log_mbaryon = st.slider("Log10 da massa barionica (massas solares)", 6.0, 12.0, step=0.1, key="log_mbaryon")
        a_baryon = st.slider("Escala barionica a (kpc)", 0.2, 15.0, step=0.1, key="a_baryon")
        core_radius_kpc = st.slider("Raio do nucleo SIDM (kpc)", 0.1, 30.0, step=0.1, key="core_radius_kpc")
        r_plot_max = st.slider("Raio maximo dos graficos (kpc)", 5.0, 100.0, step=1.0, key="r_plot_max")
    with col_c:
        sigma_over_m = st.number_input(
            "Secao de choque por massa sigma/m (cm^2/g)",
            min_value=0.0, max_value=100.0, step=0.1, key="sigma_over_m",
            help="Parametro descritivo de autointeracao; nao e usado para inferir automaticamente o raio do nucleo.",
        )
        sigma_v = st.slider("Dispersao de velocidade por componente (km/s)", 20.0, 300.0, step=5.0, key="sigma_v")
        n_velocity_samples = st.slider("Amostras para a distribuicao de velocidades", 500, 20000, step=500, key="n_velocity_samples")
        seed_velocity = st.number_input("Semente das velocidades", 0, 2_147_483_647, step=1, key="seed_velocity")

    m200 = 10.0**log_m200
    m_baryon = 10.0**log_mbaryon
    r200, rs, rho_s = nfw_parameters(m200, concentration)
    feedback_strength_current = float(st.session_state.get("feedback_strength", 0.25))
    feedback_scale_current = float(st.session_state.get("feedback_scale_kpc", 3.0))

    mm1, mm2, mm3, mm4, mm5 = st.columns(5)
    mm1.metric("M200", f"{m200:.2e} M☉")
    mm2.metric("R200", f"{r200:.1f} kpc")
    mm3.metric("Raio de escala rs", f"{rs:.2f} kpc")
    mm4.metric("Concentracao c", f"{concentration:.1f}")
    if sigma_over_m > 0:
        rho_local = density_at_scale_radius_g_cm3(
            m200, concentration, halo_model, core_radius_kpc,
            feedback_strength_current, feedback_scale_current,
        )
        mean_free_path_kpc = 1.0 / max(rho_local * sigma_over_m * KPC_CM, 1e-300)
        mfp_label = f"{mean_free_path_kpc:.2g} kpc"
    else:
        mean_free_path_kpc = float("inf")
        mfp_label = "Infinito"
    mm5.metric("Livre medio estimado em rs", mfp_label)

    if sigma_over_m > 0 and np.isfinite(mean_free_path_kpc) and np.isfinite(r200):
        if mean_free_path_kpc > 5 * r200:
            st.warning(
                f"⚠️ Consistência SIDM: o livre caminho médio estimado ({mean_free_path_kpc:.0f} kpc) é muito maior "
                f"que R200 ({r200:.0f} kpc). Neste regime, a matéria escura é **colisionalmente livre** e "
                f"um núcleo de {core_radius_kpc:.1f} kpc não seria produzido por autointeração."
            )
        elif mean_free_path_kpc > r200:
            st.info(
                f"ℹ️ SIDM marginal: λ ≈ {mean_free_path_kpc:.0f} kpc > R200 = {r200:.0f} kpc. O núcleo é "
                f"fenomenológico; a autointeração é subdominante no halo."
            )
        else:
            st.success(
                f"✅ SIDM colisional: λ ≈ {mean_free_path_kpc:.1f} kpc < R200 = {r200:.0f} kpc. Neste regime, "
                f"o núcleo é consistente com a seção de choque."
            )

    st.markdown("#### Perfil de densidade: NFW versus SIDM")
    r_density = np.geomspace(0.03, max(r_plot_max, 0.1), 300)
    rho_nfw = profile_density(r_density, m200, concentration, core_radius_kpc, "NFW")
    rho_sidm = profile_density(r_density, m200, concentration, core_radius_kpc, "SIDM")
    fig_density_compare = go.Figure()
    fig_density_compare.add_trace(go.Scatter(x=r_density, y=rho_nfw, mode="lines", name="NFW", line=dict(width=3, color="#8b7cff")))
    fig_density_compare.add_trace(go.Scatter(x=r_density, y=rho_sidm, mode="lines", name="SIDM com nucleo", line=dict(width=3, color="#58c4dd")))
    fig_density_compare.update_layout(
        template="plotly_dark", height=410, title="Perfis de densidade do halo",
        xaxis_title="Raio r (kpc)", yaxis_title="Densidade (M☉/kpc³)",
        xaxis_type="log", yaxis_type="log", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
    )
    st.plotly_chart(fig_density_compare, use_container_width=True)
    st.caption(
        "O perfil NFW tem densidade que diverge no centro (`ρ ∝ 1/r`). O perfil SIDM com núcleo achata "
        "a densidade central. Observações de galáxias anãs favorecem núcleos, o que motivou modelos SIDM."
    )

    st.markdown("#### Distribuicao de velocidades")
    rng_velocity = np.random.default_rng(int(seed_velocity))
    velocity_vectors = rng_velocity.normal(0.0, sigma_v, size=(int(n_velocity_samples), 3))
    speeds = np.linalg.norm(velocity_vectors, axis=1)
    v_grid = np.linspace(0.0, max(4.5 * sigma_v, float(np.max(speeds)) * 1.03), 350)
    speed_pdf = maxwell_speed_pdf(v_grid, sigma_v)
    fig_velocity = go.Figure()
    fig_velocity.add_trace(go.Histogram(x=speeds, histnorm="probability density", nbinsx=45,
                                        name="Amostras numericas", opacity=0.62, marker_color="#58c4dd"))
    fig_velocity.add_trace(go.Scatter(x=v_grid, y=speed_pdf, mode="lines", name="Maxwell teorica",
                                      line=dict(color="#ffbd69", width=3)))
    fig_velocity.update_layout(
        template="plotly_dark", height=420, barmode="overlay", title="Distribuicao dos modulos de velocidade",
        xaxis_title="Velocidade (km/s)", yaxis_title="Densidade de probabilidade",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
    )
    st.plotly_chart(fig_velocity, use_container_width=True)
    v1, v2, v3 = st.columns(3)
    v1.metric("Velocidade media amostrada", f"{np.mean(speeds):.1f} km/s")
    v2.metric("Velocidade RMS", f"{np.sqrt(np.mean(speeds**2)):.1f} km/s")
    v3.metric("Media teorica de Maxwell", f"{2*np.sqrt(2/np.pi)*sigma_v:.1f} km/s")
    st.caption(
        "A distribuicao de Maxwell e uma idealizacao cinetica. O modelo SIDM com nucleo e fenomenologico."
    )

# ============================================================
# ABA 2 - CURVAS DE ROTACAO
# ============================================================
with tab_rotation:
    st.subheader("Curvas de rotacao: previsoes teoricas versus dados")
    st.write(
        "Compare um halo NFW com um perfil SIDM com nucleo e feedback barionico. Os pontos podem ser "
        "importados de um CSV; o aplicativo tambem possui dados sinteticos demonstrativos."
    )
    st.caption(
        "**Chave para entender matéria escura:** a curva **sem matéria escura** (apenas bárions) "
        "cai após o raio visível, enquanto a curva **com matéria escura** permanece plana."
    )
    uploaded = st.file_uploader(
        "Carregar dados observacionais em CSV (opcional)", type=["csv", "txt"],
        help="Colunas canonicas: radius_kpc e v_obs_kms. v_err_kms e opcional.",
        key="observational_csv",
    )
    st.caption(
        "Formato canonico: radius_kpc,v_obs_kms,v_err_kms. Tambem sao aceitos cabecalhos como R_kpc, raio_kpc, "
        "v_obs, velocity_kms ou velocidade_km_s, inclusive com ponto e virgula."
    )
    sample_rotation_csv = (
        "radius_kpc,v_obs_kms,v_err_kms\n"
        "1.0,72.0,5.0\n"
        "2.0,96.0,5.0\n"
        "4.0,118.0,6.0\n"
        "6.0,132.0,6.0\n"
        "8.0,140.0,7.0\n"
        "12.0,180.0,8.0\n"
        "20.0,210.0,10.0\n"
        "30.0,220.0,12.0\n"
    )
    st.download_button(
        "Baixar CSV-modelo para curvas de rotacao",
        data=sample_rotation_csv.encode("utf-8"),
        file_name="modelo_curva_rotacao.csv", mime="text/csv",
        key="download_rotation_template",
    )

    feedback_strength_current = float(st.session_state.get("feedback_strength", 0.25))
    feedback_scale_current = float(st.session_state.get("feedback_scale_kpc", 3.0))
    radii = np.linspace(max(0.15, r_plot_max / 150.0), r_plot_max, 240)
    v_nfw_dm, v_baryon, v_nfw_total, _, rs, m_dm_arr, m_b_arr = rotation_components(
        radii, m200, concentration, m_baryon, a_baryon, model="NFW",
    )
    v_sidm_dm, _, v_sidm_total, _, _, _, _ = rotation_components(
        radii, m200, concentration, m_baryon, a_baryon,
        model="SIDM", core_radius_kpc=core_radius_kpc,
        feedback_strength=feedback_strength_current, feedback_scale_kpc=feedback_scale_current,
    )
    v_kepler = np.sqrt(G_ASTRO * m_baryon / np.maximum(radii, 1e-8))

    selected_curve = st.radio(
        "Modelo usado para calcular os residuos",
        ["NFW + barions", "SIDM + feedback barionico"], horizontal=True,
    )

    obs_df = None
    csv_error = None
    source_label = "Dados sinteticos demonstrativos"
    original_headers = []
    separator_used = "n/a"
    if uploaded is not None:
        try:
            obs_df, original_headers, separator_used = load_observational_csv(uploaded)
            uploaded_name = str(getattr(uploaded, "name", "")).lower()
            if any(marker in uploaded_name for marker in ("modelo", "exemplo", "sintetico", "sintetico")):
                source_label = "Dados sinteticos de exemplo (CSV)"
            else:
                source_label = "Dados carregados do CSV"
        except ValueError as exc:
            csv_error = str(exc)
            st.error(f"CSV invalido: {csv_error}")
        except Exception as exc:
            csv_error = f"Falha ao ler o arquivo: {exc}"
            st.error(f"CSV invalido: {csv_error}")

    if obs_df is None:
        rng_obs = np.random.default_rng(2025)
        r_obs = np.linspace(max(0.8, r_plot_max / 20.0), r_plot_max * 0.9, 14)
        _, _, v_model_obs, _, _, _, _ = rotation_components(
            r_obs, m200, concentration, m_baryon, a_baryon, model="NFW",
        )
        errors = np.maximum(5.0, 0.04 * v_model_obs)
        v_observed = np.maximum(0.0, v_model_obs + rng_obs.normal(0.0, errors))
        obs_df = pd.DataFrame({"radius_kpc": r_obs, "v_obs_kms": v_observed, "v_err_kms": errors})
        if csv_error:
            source_label = "Dados sinteticos (CSV rejeitado)"

    fig_rot = go.Figure()
    fig_rot.add_trace(go.Scatter(x=radii, y=v_nfw_total, mode="lines", name="Com ME: NFW + bárions",
                                 line=dict(color="#8b7cff", width=3.5)))
    fig_rot.add_trace(go.Scatter(x=radii, y=v_sidm_total, mode="lines", name="Com ME: SIDM + feedback",
                                 line=dict(color="#58c4dd", width=3)))
    fig_rot.add_trace(go.Scatter(x=radii, y=v_baryon, mode="lines", name="SEM matéria escura (só bárions)",
                                 line=dict(color="#ffbd69", width=3, dash="dash")))
    fig_rot.add_trace(go.Scatter(x=radii, y=v_kepler, mode="lines", name="Expectativa Kepler (v ∝ 1/√r)",
                                 line=dict(color="#f472b6", width=1.8, dash="dot")))
    fig_rot.add_trace(go.Scatter(x=radii, y=v_nfw_dm, mode="lines", name="Componente escura NFW (só DM)",
                                 line=dict(color="#b5aaff", width=1.4, dash="longdash")))
    marker_kwargs = {
        "x": obs_df["radius_kpc"], "y": obs_df["v_obs_kms"], "mode": "markers",
        "name": source_label,
        "marker": dict(color="#f472b6", size=8, symbol="circle-open", line=dict(width=2)),
    }
    if "v_err_kms" in obs_df.columns and obs_df["v_err_kms"].notna().any():
        marker_kwargs["error_y"] = dict(type="data", array=obs_df["v_err_kms"].fillna(0), visible=True, thickness=1.2)
    fig_rot.add_trace(go.Scatter(**marker_kwargs))
    fig_rot.update_layout(
        template="plotly_dark", height=560, title="Curva de rotacao galactica: com vs sem materia escura",
        xaxis_title="Raio galactocentrico (kpc)", yaxis_title="Velocidade circular (km/s)",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
        legend=dict(orientation="h", y=1.13),
    )
    st.plotly_chart(fig_rot, use_container_width=True)

    with st.expander("🧪 Diagnóstico de matéria escura em função do raio", expanded=True):
        _, _, dm_frac_curve = dark_matter_fraction_at_radius(
            radii, m200, concentration, m_baryon, a_baryon,
            model="NFW", core_radius_kpc=core_radius_kpc,
            feedback_strength=feedback_strength_current, feedback_scale_kpc=feedback_scale_current,
        )
        dm_frac_curve = as_1d(dm_frac_curve)
        fig_frac = go.Figure()
        fig_frac.add_trace(go.Scatter(
            x=radii, y=100.0 * dm_frac_curve, mode="lines",
            name="Fração M_DM / M_total",
            line=dict(color="#58c4dd", width=3),
            fill="tozeroy", fillcolor="rgba(88,196,221,0.15)",
        ))
        fig_frac.add_hline(y=50, line=dict(color="#aabbd7", dash="dot", width=1))
        fig_frac.update_layout(
            template="plotly_dark", height=340,
            title="Fração de matéria escura dentro de cada raio",
            xaxis_title="Raio galactocêntrico (kpc)", yaxis_title="M_DM / M_total (%)",
            yaxis_range=[0, 100],
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
        )
        st.plotly_chart(fig_frac, use_container_width=True)
        idx_30 = int(np.argmin(np.abs(radii - min(30.0, r_plot_max))))
        f30 = float(dm_frac_curve[idx_30])
        idx_8 = int(np.argmin(np.abs(radii - min(8.0, r_plot_max))))
        f8 = float(dm_frac_curve[idx_8])
        v30 = float(v_nfw_total[idx_30])
        vk30 = float(v_kepler[idx_30])
        c1, c2, c3 = st.columns(3)
        c1.metric("Fração de ME em 8 kpc", f"{f8*100:.1f}%")
        c2.metric(f"Fração de ME em {radii[idx_30]:.0f} kpc", f"{f30*100:.1f}%")
        c3.metric(
            f"v({radii[idx_30]:.0f} kpc): observado vs Kepler",
            f"{v30:.0f} vs {vk30:.0f} km/s",
            delta=f"+{(v30 - vk30):.0f} km/s",
        )
        st.caption(
            "Se não houvesse matéria escura, a velocidade em 30 kpc seria Kepleriana "
            f"(~{vk30:.0f} km/s). A observação mostra ~{v30:.0f} km/s — a diferença é a massa escura faltante."
        )

    if uploaded is None:
        st.info("Os pontos sao sinteticos e servem apenas para demonstracao.")
    elif csv_error:
        st.warning("O arquivo nao foi usado no ajuste. O grafico usa dados sinteticos como alternativa.")
    else:
        if "sinteticos de exemplo" in source_label:
            st.info(f"Arquivo de exemplo validado: {len(obs_df)} linhas sinteticas. Separador: {separator_used}.")
        else:
            st.success(f"CSV validado: {len(obs_df)} linhas validas. Separador: {separator_used}.")

    if selected_curve == "NFW + barions":
        v_selected = v_nfw_total
    else:
        v_selected = v_sidm_total
    v_fit = np.interp(obs_df["radius_kpc"].to_numpy(), radii, v_selected)
    residuals = obs_df["v_obs_kms"].to_numpy() - v_fit
    rmse = float(np.sqrt(np.mean(residuals**2))) if len(residuals) else float("nan")
    mae = float(np.mean(np.abs(residuals))) if len(residuals) else float("nan")
    if "v_err_kms" in obs_df.columns:
        valid_err = obs_df["v_err_kms"].notna().to_numpy() & (obs_df["v_err_kms"].to_numpy() > 0)
    else:
        valid_err = np.zeros(len(obs_df), dtype=bool)
    chi2_red = float(np.mean((residuals[valid_err] / obs_df.loc[valid_err, "v_err_kms"].to_numpy())**2)) if np.any(valid_err) else float("nan")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Pontos usados", f"{len(obs_df)}")
    k2.metric("RMSE", f"{rmse:.2f} km/s")
    k3.metric("Erro absoluto medio", f"{mae:.2f} km/s")
    k4.metric("Qui-quadrado medio", f"{chi2_red:.2f}" if np.isfinite(chi2_red) else "N/D")
    if np.isfinite(chi2_red):
        if chi2_red < 2:
            st.success(f"χ² ≈ {chi2_red:.2f} → ajuste bom")
        elif chi2_red < 5:
            st.info(f"χ² ≈ {chi2_red:.2f} → ajuste aceitável")
        else:
            st.warning(f"χ² ≈ {chi2_red:.2f} → ajuste ruim: modelo incompatível com os dados dentro das barras de erro")

    st.session_state["rotation_metrics"] = {
        "source": source_label,
        "model": selected_curve,
        "n_points": int(len(obs_df)),
        "rmse_kms": rmse,
        "mae_kms": mae,
        "chi2_reduced": chi2_red,
        "csv_valid": bool(uploaded is not None and csv_error is None),
        "csv_error": csv_error or "",
        "original_headers": ", ".join(original_headers),
        "separator": separator_used,
    }

    with st.expander("Ver dados e residuos"):
        data_show = obs_df.copy()
        data_show["v_model_kms"] = v_fit
        data_show["residuo_kms"] = residuals
        st.dataframe(data_show, use_container_width=True, hide_index=True)
        st.download_button(
            "Baixar dados, modelo e residuos (CSV)",
            data=data_show.to_csv(index=False).encode("utf-8"),
            file_name="comparacao_curva_rotacao.csv", mime="text/csv",
        )

# ============================================================
# ABA 3 - FEEDBACK BARIONICO E DENSIDADE
# ============================================================
with tab_feedback:
    st.subheader("Feedback barionico e estrutura espacial")
    st.write(
        "Ajuste uma supressao central fenomenologica para representar redistribuicao de materia escura associada "
        "a processos barionicos. O perfil e renormalizado para preservar M200 dentro de R200."
    )
    fb1, fb2, fb3 = st.columns(3)
    with fb1:
        feedback_strength = st.slider(
            "Intensidade do feedback (0 = desligado)", 0.0, 0.9, step=0.05,
            key="feedback_strength",
            help="Controla a reducao relativa central antes da renormalizacao da massa do halo.",
        )
    with fb2:
        feedback_scale = st.slider(
            "Escala radial do feedback (kpc)", 0.2, 20.0, step=0.2,
            key="feedback_scale_kpc",
        )
    with fb3:
        density_model = st.selectbox(
            "Perfil usado no mapa de densidade", DENSITY_MODEL_OPTIONS,
            key="density_model",
        )

    rr_feedback = np.geomspace(0.03, max(r_plot_max, 0.1), 320)
    rho_base = profile_density(
        rr_feedback, m200, concentration, core_radius_kpc, density_model, 0.0, feedback_scale,
    )
    rho_modified = profile_density(
        rr_feedback, m200, concentration, core_radius_kpc, density_model, feedback_strength, feedback_scale,
    )
    fb_fig = go.Figure()
    fb_fig.add_trace(go.Scatter(x=rr_feedback, y=rho_base, mode="lines", name="Sem feedback",
                                line=dict(color="#ffbd69", width=2, dash="dash")))
    fb_fig.add_trace(go.Scatter(x=rr_feedback, y=rho_modified, mode="lines", name="Com feedback",
                                line=dict(color="#8b7cff", width=3)))
    fb_fig.update_layout(
        template="plotly_dark", height=420, title="Efeito fenomenologico sobre o perfil radial",
        xaxis_title="Raio r (kpc)", yaxis_title="Densidade (M☉/kpc³)",
        xaxis_type="log", yaxis_type="log", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
    )
    st.plotly_chart(fb_fig, use_container_width=True)
    st.caption(
        "O feedback barionico (supernovas, AGN, ventos) pode **remover** matéria escura do centro da galáxia, "
        "transformando um perfil NFW pontudo em um perfil com núcleo."
    )

    st.markdown("#### Mapa espacial 2D da densidade")
    st.caption("Mapa de corte de densidade volumetrica. Nao e um mapa de lentes gravitacionais.")
    extent = min(max(3.0 * rs, 5.0), r_plot_max)
    grid = np.linspace(-extent, extent, 120)
    xx, yy = np.meshgrid(grid, grid)
    rr = np.sqrt(xx**2 + yy**2)
    rho_map = profile_density(
        np.maximum(rr, 0.03), m200, concentration, core_radius_kpc, density_model,
        feedback_strength, feedback_scale,
    )
    zz = np.log10(np.maximum(rho_map, 1e-30))
    fig_map = go.Figure(data=go.Heatmap(
        x=grid, y=grid, z=zz, colorscale="Magma", colorbar=dict(title="log10 rho"),
        hovertemplate="x=%{x:.2f} kpc<br>y=%{y:.2f} kpc<br>log10 rho=%{z:.2f}<extra></extra>",
    ))
    fig_map.add_shape(type="circle", x0=-a_baryon, y0=-a_baryon, x1=a_baryon, y1=a_baryon,
                      line=dict(color="#58c4dd", dash="dash", width=2))
    fig_map.update_layout(
        template="plotly_dark", height=500,
        title=f"Densidade {density_model} com feedback (circulo = escala barionica aproximada)",
        xaxis_title="x (kpc)", yaxis_title="y (kpc)",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
    )
    fig_map.update_yaxes(scaleanchor="x", scaleratio=1)
    st.plotly_chart(fig_map, use_container_width=True)
    f1, f2, f3 = st.columns(3)
    f1.metric("Intensidade do feedback", f"{feedback_strength:.2f}")
    f2.metric("Escala radial", f"{feedback_scale:.1f} kpc")
    f3.metric("Perfil de densidade", density_model)

# ============================================================
# ABA 4 - SIMULACAO
# ============================================================
with tab_sim:
    st.subheader("Calculadora e execucao da simulacao")
    st.write(
        "Integracao leapfrog de tracadores em um potencial fixo. Selecione o perfil do potencial, o numero de tracadores, "
        "a resolucao temporal e a semente para repetir o experimento."
    )

    s1, s2, s3 = st.columns(3)
    with s1:
        n_particles = st.slider("Numero de particulas-tracadoras", 100, 2000, step=100, key="n_particles")
        n_steps = st.slider("Passos de integracao", 100, 10000, step=100, key="n_steps")
        sim_halo_model = st.selectbox("Perfil do potencial da simulacao", SIM_HALO_MODEL_OPTIONS, key="sim_halo_model")
    with s2:
        g_dimless = st.number_input("Intensidade gravitacional adimensional", 0.001, 2.0, step=0.005, format="%.3f", key="g_dimless")
        dt = st.number_input("Passo temporal adimensional delta t", 0.0001, 0.1, step=0.001, format="%.4f", key="dt")
        softening = st.number_input("Suavizacao numerica epsilon", 0.001, 0.5, step=0.005, format="%.3f", key="softening")
    with s3:
        sim_seed = st.number_input("Semente aleatoria da simulacao", 0, 2_147_483_647, step=1, key="sim_seed")
        record_every = st.slider("Registrar a cada N passos", 10, 500, step=10, key="record_every")
        st.metric("Tempo final nominal", f"{n_steps * dt:.2f}")

    _, rs_sim, _ = nfw_parameters(m200, concentration)
    current_params = {
        "n_particles": int(n_particles), "n_steps": int(n_steps),
        "g_dimless": float(g_dimless), "dt": float(dt), "seed": int(sim_seed),
        "softening": float(softening), "concentration": float(concentration),
        "record_every": int(record_every), "halo_model": sim_halo_model,
        "core_radius_over_rs": float(core_radius_kpc / rs_sim),
        "feedback_strength": float(feedback_strength),
        "feedback_scale_over_rs": float(feedback_scale / rs_sim),
        "sigma_over_m_cm2_g": float(sigma_over_m),
    }

    have_sim = all(k in st.session_state for k in [
        "sim_positions", "sim_velocities", "sim_accelerations", "sim_params", "sim_mass_x", "sim_potential_x"
    ])
    config_changed = have_sim and st.session_state.sim_params != current_params

    if config_changed:
        st.warning("Os parametros foram alterados desde a inicializacao. Reinicie a simulacao para aplicar a nova configuracao.")

    ctrl1, ctrl2, ctrl3 = st.columns(3)
    with ctrl1:
        start_clicked = st.button("▶ Iniciar / continuar", type="primary", use_container_width=True,
                                  disabled=bool(config_changed))
    with ctrl2:
        pause_clicked = st.button("⏸ Pausar", use_container_width=True,
                                  disabled=(not have_sim or st.session_state.sim_status != "Executando"))
    with ctrl3:
        reset_clicked = st.button("↺ Reiniciar", use_container_width=True)

    if reset_clicked:
        initialise_simulation(current_params, event_type="reinicializacao")
        st.session_state.sim_status = "Pausada"
        record_current_simulation_event("reinicio_pronto", status="Pausada")
        st.rerun()

    if start_clicked:
        was_paused = bool(have_sim and not config_changed and st.session_state.sim_status == "Pausada")
        if not have_sim or config_changed or st.session_state.sim_status in ["Nao iniciada", "Concluida"]:
            event_type = "reinicio_apos_conclusao" if have_sim and st.session_state.sim_status == "Concluida" else "inicializacao"
            initialise_simulation(current_params, event_type=event_type)
        st.session_state.sim_status = "Executando"
        record_current_simulation_event("retomada" if was_paused else "inicio", status="Executando")
        st.rerun()

    if pause_clicked:
        st.session_state.sim_status = "Pausada"
        record_current_simulation_event("pausa", status="Pausada")
        st.rerun()

    status = st.session_state.sim_status
    status_color = "#72d6a4" if status == "Concluida" else ("#ffbd69" if status == "Executando" else "#aabbd7")
    st.markdown(
        f'<div class="lab-card"><b>Estado:</b> <span style="color:{status_color}">{status}</span>'
        + (f' · Passo {st.session_state.sim_step:,} / {current_params["n_steps"]:,}' if have_sim else "")
        + "</div>",
        unsafe_allow_html=True,
    )

    @st.fragment(run_every=0.1 if st.session_state.sim_status == "Executando" else None)
    def simulation_live_panel():
        has_state = all(k in st.session_state for k in [
            "sim_positions", "sim_velocities", "sim_accelerations", "sim_params", "sim_mass_x", "sim_potential_x"
        ])
        if not has_state:
            st.info("A simulacao ainda nao foi inicializada.")
            return
        params = st.session_state.sim_params
        if st.session_state.sim_status == "Executando":
            integrate_chunk(params, max_chunk=200)
            if st.session_state.sim_status == "Concluida":
                st.rerun()

        step = st.session_state.sim_step
        pos_now = st.session_state.sim_positions
        vel_now = st.session_state.sim_velocities
        times = np.asarray(st.session_state.sim_times)
        energies = np.asarray(st.session_state.sim_energy)
        completion = 100.0 * step / max(params["n_steps"], 1)
        st.progress(min(1.0, completion / 100.0), text=f"Progresso: {completion:.1f}%")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Passo atual", f"{step:,} / {params['n_steps']:,}")
        m2.metric("Tempo adimensional", f"{step * params['dt']:.3f}")
        m3.metric("Velocidade RMS", f"{np.sqrt(np.mean(np.sum(vel_now**2, axis=1))):.4f}")
        if len(energies) > 0 and abs(energies[0]) > 1e-12:
            drift = 100.0 * (energies[-1] - energies[0]) / abs(energies[0])
            m4.metric("Variacao da energia proxy", f"{drift:+.3g}%")
        else:
            drift = float("nan")
            m4.metric("Variacao da energia proxy", "N/D")
        st.session_state["simulation_metrics"] = {
            "step": int(step), "n_steps": int(params["n_steps"]),
            "time": float(step * params["dt"]),
            "velocity_rms": float(np.sqrt(np.mean(np.sum(vel_now**2, axis=1)))),
            "energy_drift_percent": float(drift), "status": st.session_state.sim_status,
        }

        sim_col1, sim_col2 = st.columns([1.1, 1])
        with sim_col1:
            fig_particles = go.Figure()
            fig_particles.add_trace(go.Scattergl(
                x=pos_now[:, 0], y=pos_now[:, 1], mode="markers", name="Tracadores",
                marker=dict(size=4, color=np.linalg.norm(pos_now, axis=1), colorscale="Viridis",
                            showscale=True, colorbar=dict(title="r / rs")),
            ))
            fig_particles.update_layout(
                template="plotly_dark", height=430, title="Configuracao instantanea (unidades de rs)",
                xaxis_title="x / rs", yaxis_title="y / rs",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
            )
            fig_particles.update_yaxes(scaleanchor="x", scaleratio=1)
            st.plotly_chart(fig_particles, use_container_width=True)
        with sim_col2:
            fig_e = go.Figure()
            fig_e.add_trace(go.Scatter(x=times, y=energies, mode="lines+markers", name="Energia proxy media"))
            fig_e.update_layout(
                template="plotly_dark", height=430, title="Diagnostico de energia",
                xaxis_title="Tempo adimensional", yaxis_title="Energia especifica (proxy)",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
            )
            st.plotly_chart(fig_e, use_container_width=True)
        if st.session_state.sim_status == "Executando":
            st.caption("Integracao em lotes de 200 passos.")
        elif st.session_state.sim_status == "Concluida":
            st.success("Integracao concluida.")

        df_history = pd.DataFrame({
            "tempo_adimensional": times,
            "energia_especifica_media_proxy": energies,
        })
        st.download_button(
            "⬇️ Exportar historico fisico da simulacao (CSV)",
            data=df_history.to_csv(index=False).encode("utf-8"),
            file_name="historico_simulacao_energia.csv", mime="text/csv",
            key="download_sim_history",
        )

        all_history = st.session_state.get("simulation_history", [])
        with st.expander(f"🧭 Historico automatico e log fisico ({len(all_history)} registros)", expanded=False):
            if all_history:
                show_history_details = st.checkbox(
                    "Carregar tabela detalhada, logs e exportacao completa",
                    value=False, key="show_history_details",
                )
                if show_history_details:
                    history_df = cached_history_dataframe(all_history)
                    visible_cols = [
                        "recorded_at", "run_id", "event_type", "step", "time_adimensional", "status",
                        "energy_specific_mean_proxy", "energy_drift_percent", "velocity_rms", "radius_rms",
                    ]
                    st.dataframe(history_df[visible_cols].tail(30), use_container_width=True, hide_index=True)
                    st.download_button(
                        "Baixar historico completo com parametros e log (CSV)",
                        data=history_df.to_csv(index=False).encode("utf-8"),
                        file_name="historico_fisico_dark_matter_lab.csv", mime="text/csv",
                        key="download_full_simulation_history",
                    )
                    st.markdown("**Log fisico mais recente**")
                    for record in all_history[-8:][::-1]:
                        st.write(f"**Execucao {record['run_id']} · passo {record['step']} · {record['event_type']}** — {record['physics_log']}")
                else:
                    st.caption("O historico esta sendo armazenado automaticamente.")
            else:
                st.info("O historico sera preenchido automaticamente quando voce iniciar ou reinicializar uma simulacao.")

    simulation_live_panel()

    st.markdown("#### Resumo dos parametros ativos")
    df_active = pd.DataFrame({
        "Parametro": [
            "Candidato", "Perfil selecionado", "M200 (Msun)", "Concentracao c", "Secao de choque / massa (cm2/g)",
            "Dispersao de velocidade (km/s)", "Feedback", "Particulas-tracadoras", "Passos", "G adimensional",
            "Delta t", "Semente", "Suavizacao epsilon",
        ],
        "Valor": [
            candidate, sim_halo_model, f"{m200:.4e}", f"{concentration:.2f}", f"{sigma_over_m:.3f}",
            f"{sigma_v:.1f}", f"{feedback_strength:.2f}", n_particles, n_steps, g_dimless, dt, sim_seed, softening,
        ],
    })
    st.dataframe(df_active, use_container_width=True, hide_index=True)

    rotation_metrics = st.session_state.get("rotation_metrics", {})
    simulation_metrics = st.session_state.get("simulation_metrics", {})

    def _fmt_metric(key, suffix=""):
        value = rotation_metrics.get(key)
        return f"{value:.4g}{suffix}" if isinstance(value, (int, float, np.number)) and np.isfinite(value) else "N/D"

    r30_report = min(30.0, r_plot_max)
    _, _, f30_report = dark_matter_fraction_at_radius(
        np.array([r30_report]), m200, concentration, m_baryon, a_baryon,
        model="SIDM" if halo_model.upper().startswith("SIDM") else "NFW",
        core_radius_kpc=core_radius_kpc,
        feedback_strength=feedback_strength, feedback_scale_kpc=feedback_scale,
    )
    # FIX: protege contra escalar 0-d vindo de numpy
    f30_report = as_1d(f30_report)
    v_obs_30 = float(np.interp(r30_report, radii, v_nfw_total))
    v_kep_30 = float(np.interp(r30_report, radii, v_kepler))

    physics_rows = [
        ("Candidato", candidate), ("Modelo / perfil selecionado", halo_model),
        ("Massa M200", f"{m200:.5e} massas solares"), ("R200", f"{r200:.4g} kpc"),
        ("Raio de escala rs", f"{rs:.4g} kpc"), ("Concentracao c", f"{concentration:.3g}"),
        ("Massa barionica", f"{m_baryon:.5e} massas solares"), ("Escala barionica", f"{a_baryon:.4g} kpc"),
        ("Raio maximo dos graficos", f"{r_plot_max:.4g} kpc"), ("Intensidade do feedback", f"{feedback_strength:.4g}"),
        ("Escala radial do feedback", f"{feedback_scale:.4g} kpc"), ("Livre medio estimado em rs", mfp_label),
        ("Raio do nucleo SIDM", f"{core_radius_kpc:.4g} kpc"), ("Secao de choque por massa", f"{sigma_over_m:.4g} cm^2/g"),
        ("Dispersao de velocidade", f"{sigma_v:.4g} km/s"), ("Amostras de velocidade", str(n_velocity_samples)),
        ("Semente das velocidades", str(seed_velocity)),
    ]
    rotation_rows = [
        ("Origem do conjunto de dados", rotation_metrics.get("source", "Nao calculado nesta sessao")),
        ("Modelo comparado", rotation_metrics.get("model", "N/D")),
        ("Pontos usados", str(rotation_metrics.get("n_points", "N/D"))),
        ("RMSE", _fmt_metric("rmse_kms", " km/s")),
        ("Erro absoluto medio", _fmt_metric("mae_kms", " km/s")),
        ("Qui-quadrado medio", _fmt_metric("chi2_reduced")),
        ("CSV validado", str(rotation_metrics.get("csv_valid", False))),
        ("Cabecalhos CSV", rotation_metrics.get("original_headers", "N/D")),
    ]
    dm_diagnostic_rows = [
        ("M200 (halo total)", f"{m200:.4e} M☉"),
        ("M_bárion (visível)", f"{m_baryon:.4e} M☉"),
        ("Razão M200 / M_bárion", f"{m200 / max(m_baryon, 1e-30):.2f}"),
        (f"Fração de ME em {r30_report:.0f} kpc", f"{float(f30_report[0])*100:.2f}%"),
        (f"v observado em {r30_report:.0f} kpc", f"{v_obs_30:.1f} km/s"),
        (f"v Kepleriano em {r30_report:.0f} kpc", f"{v_kep_30:.1f} km/s"),
        ("Diferença (v_obs − v_Kepler)", f"{v_obs_30 - v_kep_30:+.1f} km/s"),
    ]
    sim_rows = [
        ("Estado", simulation_metrics.get("status", st.session_state.sim_status)),
        ("Particulas-tracadoras", str(n_particles)), ("Passos previstos", str(n_steps)),
        ("Passo atual", str(simulation_metrics.get("step", st.session_state.sim_step))),
        ("Tempo final nominal", f"{n_steps * dt:.5g}"), ("G adimensional", f"{g_dimless:.5g}"),
        ("Delta t", f"{dt:.5g}"), ("Semente", str(sim_seed)),
        ("Perfil do potencial", sim_halo_model), ("Intensidade do feedback", f"{feedback_strength:.3g}"),
        ("Raio RMS de velocidade atual", f"{simulation_metrics.get('velocity_rms', float('nan')):.5g}" if np.isfinite(simulation_metrics.get('velocity_rms', float('nan'))) else "N/D"),
        ("Variacao da energia proxy", f"{simulation_metrics.get('energy_drift_percent', float('nan')):.5g}%" if np.isfinite(simulation_metrics.get('energy_drift_percent', float('nan'))) else "N/D"),
    ]

    if st.button(
        "📄 Gerar relatorio PDF completo",
        type="primary", use_container_width=True,
        help="Compila parametros, graficos Plotly em PNG, diagnostico energetico, historico e log fisico.",
        key="generate_dark_matter_pdf",
    ):
        report_figures = {
            "Perfis de densidade: NFW versus SIDM": fig_density_compare,
            "Distribuicao de velocidades": fig_velocity,
            "Curva de rotacao: com versus sem materia escura": fig_rot,
            "Perfil radial com feedback barionico": fb_fig,
            "Mapa espacial 2D de densidade": fig_map,
        }
        if have_sim:
            report_pos = st.session_state.sim_positions
            report_fig_particles = go.Figure()
            report_fig_particles.add_trace(go.Scattergl(
                x=report_pos[:, 0], y=report_pos[:, 1], mode="markers", name="Tracadores",
                marker=dict(size=4, color=np.linalg.norm(report_pos, axis=1), colorscale="Viridis",
                            showscale=True, colorbar=dict(title="r / rs")),
            ))
            report_fig_particles.update_layout(
                template="plotly_dark", title="Configuracao instantanea de tracadores",
                xaxis_title="x / rs", yaxis_title="y / rs", height=430,
            )
            report_fig_particles.update_yaxes(scaleanchor="x", scaleratio=1)
            report_fig_energy = go.Figure()
            report_fig_energy.add_trace(go.Scatter(
                x=st.session_state.sim_times, y=st.session_state.sim_energy,
                mode="lines+markers", name="Energia proxy media",
            ))
            report_fig_energy.update_layout(
                template="plotly_dark", title="Diagnostico de energia da simulacao",
                xaxis_title="Tempo adimensional", yaxis_title="Energia especifica (proxy)", height=430,
            )
            report_figures["Estado atual dos tracadores"] = report_fig_particles
            report_figures["Evolucao temporal da energia"] = report_fig_energy

        all_history = st.session_state.get("simulation_history", [])
        history_rows = []
        for item in all_history[-24:]:
            drift_text = f"{item['energy_drift_percent']:+.4g}%" if np.isfinite(item.get("energy_drift_percent", float("nan"))) else "N/D"
            params_json = json.dumps(item.get("parameters", {}), ensure_ascii=True, sort_keys=True)
            history_rows.append((
                f"Execucao {item['run_id']} · passo {item['step']}",
                f"{item['recorded_at']} | {item['event_type']} | t={item['time_adimensional']:.5g} | "
                f"Eproxy={item['energy_specific_mean_proxy']:.6g} | E0={item.get('energy_initial_proxy', float('nan')):.6g} | "
                f"deltaE={item.get('energy_delta_proxy', float('nan')):.5g} | drift={drift_text} | "
                f"vRMS={item['velocity_rms']:.5g} | Rrms={item['radius_rms']:.5g} | estado={item['status']} | "
                f"Parametros deste instantaneo: {params_json}"
            ))
        physics_log_rows = [
            f"[{item['recorded_at']}] Execucao {item['run_id']}, passo {item['step']}: {item['physics_log']}"
            for item in all_history[-30:]
        ]
        with st.spinner("Gerando PDF, exportando figuras em PNG e compilando o historico..."):
            pdf_bytes, pdf_chart_warnings = generate_pdf_report(
                {
                    "physics_rows": physics_rows,
                    "rotation_rows": rotation_rows,
                    "dm_diagnostic_rows": dm_diagnostic_rows,
                    "simulation_rows": sim_rows,
                    "history_rows": history_rows,
                    "physics_log": physics_log_rows,
                },
                figures=report_figures,
            )
            st.session_state["dark_matter_pdf_bytes"] = pdf_bytes
            st.session_state["dark_matter_pdf_chart_warning"] = pdf_chart_warnings
            st.session_state["dark_matter_pdf_generated_at"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    if st.session_state.get("dark_matter_pdf_bytes"):
        st.success(
            "Relatorio gerado em "
            + st.session_state.get("dark_matter_pdf_generated_at", "esta sessao")
            + ". Baixe o arquivo abaixo."
        )
        st.download_button(
            "⬇️ Baixar relatorio PDF",
            data=st.session_state["dark_matter_pdf_bytes"],
            file_name="relatorio_dark_matter_lab.pdf", mime="application/pdf",
            use_container_width=True, key="download_dark_matter_pdf",
        )
        if st.session_state.get("dark_matter_pdf_chart_warning"):
            warnings = st.session_state["dark_matter_pdf_chart_warning"]
            if isinstance(warnings, str):
                warnings = [warnings]
            st.warning("O PDF foi criado, mas algumas figuras nao puderam ser incorporadas:")
            for warning in warnings:
                st.caption(warning)

# ============================================================
# ABA 5 - ASSISTENTE DE LINGUAGEM NATURAL
# ============================================================
with tab_assistant:
    st.subheader("🤖 Assistente de configuracao por linguagem natural")
    st.markdown(
        '<div class="nl-hint">Descreva livremente um cenario fisico ou cole uma instrucao de outra IA. '
        'O parser reconhece PT/EN, normaliza acentos e mapeia os termos diretamente para as chaves do '
        '<code>st.session_state</code> que alimentam todos os sliders, selectboxes e numeros do app.</div>',
        unsafe_allow_html=True,
    )

    st.markdown("##### Exemplos de instrucoes que o parser entende")
    st.markdown(
        "- *\"Configure uma galaxia parecida com a Via Lactea, com secao de choque SIDM de 1.5 e concentracao 12\"*\n"
        "- *\"Galaxia ana com M200 de 10^9.5, nucleo SIDM de 0.8 kpc e sigma/m 2.0\"*\n"
        "- *\"Aglomerado de galaxias com massa M200 de 1e15, concentracao 4, feedback 0.4\"*\n"
        "- *\"Use NFW, M200 10^12.5, bariônica 10^11, escala barionica 4 kpc, dispersão 150 km/s\"*\n"
        "- *\"Simulacao com 2000 particulas, 5000 passos, dt 0.005, g 0.08, seed 123\"*"
    )

    nl_text = st.text_area(
        "Instrucao (PT/EN):",
        value=st.session_state.get("nl_last_input", ""),
        height=120, key="nl_assistant_input",
        placeholder="Ex.: Galaxia tipo Via Lactea com SIDM sigma/m 1.5, concentracao 12, feedback 0.3 e 2000 particulas.",
    )

    col_apply, col_reset, col_clear = st.columns([1.2, 1, 1])
    with col_apply:
        apply_clicked = st.button("🎯 Aplicar configuracao", type="primary", use_container_width=True, key="nl_apply_button")
    with col_reset:
        reset_clicked = st.button("🔄 Restaurar padroes", use_container_width=True, key="nl_reset_button")
    with col_clear:
        clear_clicked = st.button("🧹 Limpar campo", use_container_width=True, key="nl_clear_button")

    if clear_clicked:
        st.session_state["nl_assistant_input"] = ""
        st.rerun()

    if reset_clicked:
        for key, value in DEFAULT_WIDGET_STATE.items():
            if key in {"simulation_history", "simulation_run_counter", "sim_status", "sim_step"}:
                continue
            st.session_state[key] = value
        st.session_state["nl_last_matches"] = ["reset: valores padrao restaurados"]
        st.session_state["nl_last_applied"] = []
        st.session_state["nl_last_skipped"] = []
        st.session_state["nl_last_timestamp"] = datetime.now().strftime("%H:%M:%S")
        st.rerun()

    if apply_clicked:
        changes, matches = parse_natural_language_config(nl_text or "")
        st.session_state["nl_last_input"] = nl_text or ""
        st.session_state["nl_last_matches"] = matches
        if changes:
            st.session_state["nl_pending_changes"] = changes
        else:
            st.session_state["nl_last_applied"] = []
            st.session_state["nl_last_skipped"] = []
            st.session_state["nl_last_timestamp"] = datetime.now().strftime("%H:%M:%S")
        st.rerun()

    last_ts = st.session_state.get("nl_last_timestamp", "")
    applied = st.session_state.get("nl_last_applied", [])
    skipped = st.session_state.get("nl_last_skipped", [])
    matches = st.session_state.get("nl_last_matches", [])
    if last_ts:
        st.markdown(f"##### Ultima aplicacao as {last_ts}")
        if applied:
            st.success(f"{len(applied)} parametro(s) atualizados no `st.session_state`.")
            st.markdown("**Alteracoes efetivas (apos clamp/snap):**")
            for item in applied:
                st.markdown(f"- `{item}`")
        else:
            st.info("Nenhum parametro numerico ou textual foi alterado.")
        if matches:
            with st.expander("Termos reconhecidos no texto", expanded=False):
                for item in matches:
                    st.markdown(f"- {item}")
        if skipped:
            with st.expander("Termos ignorados (fora de range ou nao reconhecidos)", expanded=False):
                for item in skipped:
                    st.markdown(f"- `{item}`")

    with st.expander("🔎 Inspecionar estado atual dos parametros (session_state)", expanded=False):
        state_rows = []
        for key in DEFAULT_WIDGET_STATE.keys():
            if key in {"simulation_history", "dark_matter_pdf_bytes", "dark_matter_pdf_chart_warning",
                       "nl_last_input", "nl_last_matches", "nl_last_applied", "nl_last_skipped",
                       "nl_last_timestamp"}:
                continue
            value = st.session_state.get(key)
            if isinstance(value, float):
                value = f"{value:.6g}"
            state_rows.append({"chave": key, "valor": str(value)})
        st.dataframe(pd.DataFrame(state_rows), use_container_width=True, hide_index=True)

        st.download_button(
            "⬇️ Baixar estado atual (JSON)",
            data=json.dumps(
                {k: (v if not isinstance(v, (np.generic,)) else float(v))
                 for k, v in st.session_state.items()
                 if k in DEFAULT_WIDGET_STATE and k not in {"simulation_history", "dark_matter_pdf_bytes"}},
                indent=2, ensure_ascii=False, default=str,
            ).encode("utf-8"),
            file_name="estado_dark_matter_lab.json", mime="application/json",
            key="download_state_json",
        )

    st.markdown("##### Como o parser decide")
    st.markdown(
        "1. **Presets** (*Via Lactea*, *galaxia ana*, *aglomerado*) definem um ponto de partida.\n"
        "2. **Parametros explicitos** no texto sobrescrevem o preset.\n"
        "3. **Clamp/snap**: cada chave tem range e passo (ex.: `sigma_v` multiplo de 5).\n"
        "4. **Selectboxes** aceitam apenas opcoes validas.\n"
        "5. **Staging + rerun**: o botao grava em `nl_pending_changes` e chama `st.rerun()`; o topo do script "
        "drena esse buffer **antes** de qualquer widget."
    )

# ------------------------- RODAPE ---------------------------
st.divider()
st.markdown(
    "**Notas cientificas e limitacoes**  \n"
    "- O perfil NFW e uma parametrizacao empirica de halo. WIMPs, axions, neutrinos estereis e SIDM representam hipoteses microscopicas diferentes.  \n"
    "- O perfil SIDM com nucleo e o feedback barionico sao modelos fenomenologicos ajustaveis, nao simulacoes completas de materia escura autointeragente ou hidrodinamica.  \n"
    "- Curvas observacionais so sao reais quando fornecidas por um conjunto externo validado via CSV; os dados sinteticos sao apenas demonstrativos.  \n"
    "- O mapa espacial mostra um corte da densidade e nao calcula lentes gravitacionais.  \n"
    "- A integracao acompanha tracadores em potencial fixo; tracadores nao interagem entre si. O diagnostico energetico e uma aproximacao numerica.  \n"
    "- O assistente de linguagem natural apenas escreve nas chaves do `st.session_state`; toda a fisica e a numerica permanecem identicas as do modelo manual.  \n"
    "- A fracao de materia escura exibida e M_DM(<r) / [M_DM(<r) + M_baryon(<r)] para um halo NFW/SIDM normalizado a M200 dentro de R200."
)
