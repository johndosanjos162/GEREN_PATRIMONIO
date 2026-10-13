from __future__ import annotations

import io
import json
import re
import tempfile
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from fpdf import FPDF

# ============================================================
# NUMBA — compilacao JIT
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

# ============================================================
# CELERY + REDIS — deteccao automatica
# ============================================================
ASYNC_MODE = False
REDIS_CLIENT = None
celery_app = None
run_simulation = None

try:
    import redis as _redis_module
    from tasks import celery_app as _celery_app, run_simulation as _rs, REDIS_URL as _REDIS_URL
    _client = _redis_module.Redis.from_url(_REDIS_URL, decode_responses=False)
    _client.ping()
    REDIS_CLIENT = _client
    celery_app = _celery_app
    run_simulation = _rs
    ASYNC_MODE = True
except Exception:
    ASYNC_MODE = False
    REDIS_CLIENT = None
    celery_app = None
    run_simulation = None

# Fallback local (ThreadPoolExecutor)
_LOCAL_EXECUTOR = ThreadPoolExecutor(max_workers=1)
_LOCAL_TASKS: dict = {}

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
      .async-badge { background:linear-gradient(90deg,rgba(114,214,164,.20),rgba(88,196,221,.15)); border:1px solid rgba(114,214,164,.40); border-radius:6px; padding:4px 10px; color:#a9e5c4; font-size:.8rem; display:inline-block; margin-left:8px; }
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
    "candidate": "Materia escura autointeragente (SIDM)",
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
    "latest_contextual_insight": "",
    "ai_last_source": "",
    "ai_apply_count": 0,
    "async_task_id": None,
    "async_history": [],
    "async_elapsed": 0.0,
    "async_kdtree_rebuilds": 0,
    "async_started_at": 0.0,
    "auto_record": True,
}

for _key, _value in DEFAULT_WIDGET_STATE.items():
    if _key not in st.session_state:
        st.session_state[_key] = _value

MAX_SIMULATION_HISTORY = 5000

CANDIDATE_OPTIONS = [
    "WIMPs", "Axions", "Neutrinos estereis",
    "Materia escura autointeragente (SIDM)", "Materia escura generica",
]
HALO_MODEL_OPTIONS = ["NFW", "SIDM (nucleo fenomenologico)"]
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
    st.session_state["nl_last_matches"] = [f"preset {message}: valores tipicos restaurados"]
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
        matches.append("preset: Via Lactea")
    elif re.search(r"\b(galaxia an[a]?|dwarf galaxy|anao|ana|enana)\b", t):
        changes.update(TYPICAL_DWARF)
        matches.append("preset: Galaxia ana")
    elif re.search(r"\b(aglomerado|cluster|agrupamento)\b", t):
        changes.update(TYPICAL_CLUSTER)
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
    grab(r"(\d+)\s*(?:particulas?|tracadores?|particles?|tracers?)", "n_particles")
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


def parse_research_json_or_csv(raw_text: str):
    changes: dict = {}
    matches: list = []
    text = (raw_text or "").strip()
    if not text:
        return changes, ["entrada vazia"]

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in FREE_RANGES or k in FREE_INT_RANGES or k in {
                    "candidate", "halo_model", "density_model", "sim_halo_model"
                }:
                    changes[k] = v
                    matches.append(f"JSON {k}={v}")
            return changes, matches
    except (json.JSONDecodeError, TypeError):
        pass

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*[,=:]\s*(.+)$", line)
        if not m:
            continue
        key = m.group(1).strip()
        raw_val = m.group(2).strip().strip('"').strip("'")
        if key in FREE_RANGES:
            v = _to_float(raw_val)
            if v is not None:
                changes[key] = v
                matches.append(f"CSV {key}={v}")
        elif key in FREE_INT_RANGES:
            try:
                changes[key] = int(float(raw_val))
                matches.append(f"CSV {key}={changes[key]}")
            except (TypeError, ValueError):
                pass
        elif key in {"candidate", "halo_model", "density_model", "sim_halo_model"}:
            changes[key] = raw_val
            matches.append(f"CSV {key}={raw_val}")

    return changes, matches


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
                skipped.append(f"{key}={value!r} (nao numerico)")
                continue
            num = max(lo, min(hi, num))
            st.session_state[key] = num
            applied.append(f"{key} = {num}")
        elif key in FREE_INT_RANGES:
            lo, hi, _ = FREE_INT_RANGES[key]
            try:
                num = int(round(float(value)))
            except (TypeError, ValueError):
                skipped.append(f"{key}={value!r} (nao inteiro)")
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
                skipped.append(f"{key}={text!r} (opcao invalida)")
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
# MODELOS FISICOS
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
# KERNELS NUMBA — FISICA DA MATERIA ESCURA
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


@njit(cache=True, fastmath=False)
def _leapfrog_batch(pos, vel, acc, mass_x, mass_fraction,
                     g_dimless, softening, dt, n_inner):
    """Roda n_inner passos de leapfrog dentro do worker (compilado)."""
    eps2 = softening * softening
    n = pos.shape[0]
    for _ in range(n_inner):
        for i in range(n):
            vel[i, 0] += 0.5 * dt * acc[i, 0]
            vel[i, 1] += 0.5 * dt * acc[i, 1]
        for i in range(n):
            pos[i, 0] += dt * vel[i, 0]
            pos[i, 1] += dt * vel[i, 1]
        for i in range(n):
            x = pos[i, 0]
            y = pos[i, 1]
            r = np.sqrt(x * x + y * y)
            r_safe = r if r > 1e-10 else 1e-10
            enclosed = np.interp(r_safe, mass_x, mass_fraction)
            denom = (r_safe * r_safe + eps2) ** 1.5
            factor = -g_dimless * enclosed / denom
            acc[i, 0] = factor * x
            acc[i, 1] = factor * y
        for i in range(n):
            vel[i, 0] += 0.5 * dt * acc[i, 0]
            vel[i, 1] += 0.5 * dt * acc[i, 1]
    return pos, vel, acc


@njit(cache=True, fastmath=False)
def _energy_proxy_batch(pos, vel, g_dimless, mass_x, potential_x):
    n = pos.shape[0]
    r_max = mass_x[-1]
    total = 0.0
    for i in range(n):
        x = pos[i, 0]
        y = pos[i, 1]
        r = np.sqrt(x * x + y * y)
        r_safe = r if r > 1e-8 else 1e-8
        kinetic = 0.5 * (vel[i, 0] ** 2 + vel[i, 1] ** 2)
        if r_safe > r_max:
            phi = -1.0 / r_safe
        else:
            phi = np.interp(r_safe, mass_x, potential_x)
        total += kinetic + g_dimless * phi
    return total / n


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
    attempts = [(",", "virgula"), (";", "ponto e virgula"), ("\t", "tab"), (None, "auto")]
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
    header_text = repr(best_columns or "nao foi possivel ler o cabecalho")
    raise ValueError(
        f"Nao encontrei as colunas obrigatorias. Colunas obrigatorias: radius_kpc e v_obs_kms. "
        f"Colunas detectadas: {header_text}."
    )


# ============================================================
# RESUMO ESTATISTICO + CHUNK ADAPTATIVO + SPATIAL INDEX
# ============================================================
def summarize_particle_state(positions, velocities, n_bins=50, r_extent=None):
    """Resumo compacto por snapshot (~1 KB) em vez de array completo (~8 MB)."""
    r = np.linalg.norm(positions, axis=1)
    speed_sq = np.sum(velocities ** 2, axis=1)
    if r_extent is None:
        r_extent = float(np.max(r)) if r.size else 1.0
    r_extent = max(r_extent, 1e-6)
    hist, edges = np.histogram(r, bins=n_bins, range=(0.0, r_extent))
    return {
        "r_hist": hist.astype(np.int32).tolist(),
        "r_hist_edges": edges.astype(np.float32).tolist(),
        "r_mean": float(np.mean(r)) if r.size else 0.0,
        "r_rms": float(np.sqrt(np.mean(r ** 2))) if r.size else 0.0,
        "r_max": float(np.max(r)) if r.size else 0.0,
        "r_p10": float(np.percentile(r, 10)) if r.size else 0.0,
        "r_p50": float(np.percentile(r, 50)) if r.size else 0.0,
        "r_p90": float(np.percentile(r, 90)) if r.size else 0.0,
        "v_mean": float(np.mean(np.sqrt(speed_sq))) if r.size else 0.0,
        "v_rms": float(np.sqrt(np.mean(speed_sq))) if r.size else 0.0,
    }


def compute_adaptive_chunk(n_particles, target_ops=50_000):
    """Bloco adaptativo: escala com 1/N para manter a UI responsiva."""
    try:
        n = max(int(n_particles), 1)
    except (TypeError, ValueError):
        n = 1
    return max(5, min(500, int(target_ops / n)))


try:
    from scipy.spatial import cKDTree
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    cKDTree = None


class SpatialIndex:
    """KDTree com reconstrucao adaptativa (so quando os pontos se movem)."""

    def __init__(self, tolerance=0.01):
        self.tree = None
        self.ref_positions = None
        self.tolerance = tolerance
        self.n_rebuilds = 0

    def build(self, positions):
        if not SCIPY_AVAILABLE:
            return
        self.tree = cKDTree(positions)
        self.ref_positions = positions.copy()
        self.n_rebuilds += 1

    def maybe_rebuild(self, positions):
        if not SCIPY_AVAILABLE:
            return False
        if self.tree is None:
            self.build(positions)
            return True
        drift = float(np.max(np.linalg.norm(positions - self.ref_positions, axis=1)))
        if drift > self.tolerance:
            self.build(positions)
            return True
        return False


# ============================================================
# SIMULACAO LOCAL (executa em thread ou Celery worker)
# ============================================================
def _build_mass_lookup_sim(concentration, model, core_x, fb, fb_scale_x, grid_size=3000):
    return build_profile_lookup(
        concentration=concentration, model=model,
        core_x=core_x, feedback_strength=fb,
        feedback_scale_x=fb_scale_x, grid_size=grid_size,
    )


def _run_simulation_local(params, seed):
    """Executa a simulacao completa. Usada como fallback (thread local)."""
    rng = np.random.default_rng(seed)
    n = int(params["n_particles"])
    n_steps = int(params["n_steps"])
    dt = float(params["dt"])
    g = float(params["g_dimless"])
    eps = float(params["softening"])

    mass_x, mass_frac, pot_x = _build_mass_lookup_sim(
        concentration=float(params["concentration"]),
        model=params["halo_model"],
        core_x=float(params["core_radius_over_rs"]),
        fb=float(params["feedback_strength"]),
        fb_scale_x=float(params["feedback_scale_over_rs"]),
    )

    radius = np.clip(rng.lognormal(np.log(2.0), 0.38, size=n),
                      0.15, 0.95 * float(params["concentration"]))
    phi = rng.uniform(0.0, 2.0 * np.pi, size=n)
    pos = np.column_stack((radius * np.cos(phi), radius * np.sin(phi)))
    enc = np.interp(radius, mass_x, mass_frac, left=0.0, right=1.0)
    vc = np.sqrt(np.maximum(g * enc / np.maximum(radius, 1e-8), 0.0))
    vt = vc * rng.normal(1.0, 0.08, size=n)
    vr = vc * rng.normal(0.0, 0.12, size=n)
    vel = np.column_stack((
        vr * np.cos(phi) - vt * np.sin(phi),
        vr * np.sin(phi) + vt * np.cos(phi),
    ))
    acc = np.empty_like(pos)

    chunk = compute_adaptive_chunk(n)
    spatial = SpatialIndex(tolerance=0.01)

    e0 = float(_energy_proxy_batch(pos, vel, g, mass_x, pot_x))
    history = []
    record_every = max(1, int(params.get("record_every", 100)))

    initial = summarize_particle_state(pos, vel)
    initial.update({
        "step": 0, "time": 0.0, "energy": e0, "energy_initial": e0,
        "energy_drift": 0.0, "status": "Executando",
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    })
    history.append(initial)

    step_done = 0
    t0 = time.time()
    while step_done < n_steps:
        count = min(chunk, n_steps - step_done)
        pos, vel, acc = _leapfrog_batch(pos, vel, acc, mass_x, mass_frac,
                                          g, eps, dt, count)
        step_done += count
        if step_done % record_every < count or step_done == n_steps:
            e_now = float(_energy_proxy_batch(pos, vel, g, mass_x, pot_x))
            summary = summarize_particle_state(pos, vel)
            summary.update({
                "step": int(step_done), "time": float(step_done * dt),
                "energy": e_now, "energy_initial": e0,
                "energy_drift": float(100.0 * (e_now - e0) / abs(e0)) if abs(e0) > 1e-12 else 0.0,
                "status": "Executando",
                "recorded_at": datetime.now().isoformat(timespec="seconds"),
            })
            history.append(summary)
        spatial.maybe_rebuild(pos)

    elapsed = time.time() - t0
    final = summarize_particle_state(pos, vel)
    e_final = float(_energy_proxy_batch(pos, vel, g, mass_x, pot_x))
    final.update({
        "step": int(n_steps), "time": float(n_steps * dt),
        "energy": e_final, "energy_initial": e0,
        "energy_drift": float(100.0 * (e_final - e0) / abs(e0)) if abs(e0) > 1e-12 else 0.0,
        "status": "Concluida",
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    })
    history.append(final)

    return {
        "status": "Concluida",
        "n_steps": n_steps,
        "n_particles": n,
        "elapsed_seconds": elapsed,
        "history": history,
        "n_kdtree_rebuilds": spatial.n_rebuilds,
    }


# ============================================================
# ORQUESTRACAO ASSINCRONA
# ============================================================
def submit_simulation_async(params: dict, seed: int) -> str:
    if ASYNC_MODE and run_simulation is not None:
        task = run_simulation.delay(params, seed)
        return task.id
    fut = _LOCAL_EXECUTOR.submit(_run_simulation_local, params, seed)
    tid = f"local-{int(time.time() * 1000)}"
    _LOCAL_TASKS[tid] = fut
    return tid


def poll_simulation(task_id: str) -> dict:
    if ASYNC_MODE and run_simulation is not None:
        try:
            from celery.result import AsyncResult
            res = AsyncResult(task_id, app=celery_app)
            if res.state == "PENDING":
                return {"status": "Pendente", "progress": 0.0, "history": []}
            if res.state == "PROGRESS":
                meta = res.info or {}
                return {
                    "status": "Executando",
                    "progress": float(meta.get("progress", 0.0)),
                    "step": int(meta.get("step", 0)),
                    "n_steps": int(meta.get("n_steps", 0)),
                    "history": [],
                    "last_summary": meta.get("last_summary", {}),
                }
            if res.state == "SUCCESS":
                payload = res.result or {}
                return {"status": "Concluida", "progress": 100.0, **payload}
            return {"status": res.state, "progress": 0.0, "history": []}
        except Exception as exc:
            return {"status": "Erro", "progress": 0.0, "history": [], "error": str(exc)}

    fut = _LOCAL_TASKS.get(task_id)
    if fut is None:
        return {"status": "Nao encontrado", "progress": 0.0, "history": []}
    if fut.done():
        try:
            return {"status": "Concluida", "progress": 100.0, **(fut.result() or {})}
        except Exception as exc:
            return {"status": "Erro", "progress": 0.0, "history": [], "error": str(exc)}
    return {"status": "Executando", "progress": 50.0, "history": []}


# ============================================================
# LOG E SINTESE CIENTIFICA
# ============================================================
def explain_simulation_physics(step, time_value, params, energy, energy_drift, velocity_rms,
                               radius_rms, mean_radius, event_type, status):
    n_steps = max(int(params.get("n_steps", 1)), 1)
    progress = 100.0 * min(max(int(step), 0), n_steps) / n_steps
    drift_abs = abs(float(energy_drift)) if np.isfinite(energy_drift) else float("nan")
    if not np.isfinite(drift_abs):
        energy_comment = "A variacao relativa da energia nao pode ser avaliada."
    elif drift_abs < 1.0:
        energy_comment = "Desvio relativo da energia <1%; boa estabilidade numerica."
    elif drift_abs < 5.0:
        energy_comment = "Desvio relativo da energia 1-5%; vale testar passo temporal menor."
    else:
        energy_comment = "Desvio relativo da energia >5%; recomenda-se reduzir dt."
    g_value = float(params.get("g_dimless", float("nan")))
    dt_value = float(params.get("dt", float("nan")))
    if str(event_type).lower() in {"inicializacao", "reinicializacao", "reinicio_apos_conclusao"}:
        phase = "Condicoes iniciais sorteadas a partir da semente."
    elif str(event_type).lower() in {"pausa", "retomada", "inicio", "conclusao"}:
        phase = f"Evento de controle: {event_type}."
    else:
        phase = "Estado amostrado no intervalo de registro configurado."
    drift_text = f"{float(energy_drift):+.4g}%" if np.isfinite(energy_drift) else "N/D"
    return (
        f"Evento={event_type}; estado={status}; passo={int(step)}/{n_steps} ({progress:.1f}%); "
        f"t={float(time_value):.6g}. {phase} G={g_value:.5g}, dt={dt_value:.5g}; "
        f"E_proxy={float(energy):.7g}; desvio={drift_text}. "
        f"vRMS={float(velocity_rms):.6g}; Rrms={float(radius_rms):.6g}; "
        f"Rmedio={float(mean_radius):.6g}. {energy_comment}"
    )


def generate_contextual_insight(params, step=None, n_steps=None,
                                energy_drift=None, event_type="snapshot"):
    if not params:
        return ""
    model = str(params.get("halo_model", "NFW")).upper()
    fb_strength = float(params.get("feedback_strength", 0.0) or 0.0)
    sigma_m = float(params.get("sigma_over_m_cm2_g", 0.0) or 0.0)
    log_m200 = float(params.get("log_m200", 12.0) or 12.0)
    lines = []
    if log_m200 < 10.0:
        scale = "galaxia ana"
        detail = "sistemas de baixa massa; autointeracao mais relevante."
    elif log_m200 < 12.5:
        scale = "galaxia tipo Via Lactea"
        detail = "maior parte da massa dinamica fora do disco estelar."
    elif log_m200 < 13.5:
        scale = "grupo de galaxias"
        detail = "materia escura domina o potencial."
    else:
        scale = "aglomerado de galaxias"
        detail = "materia escura praticamente colisionalmente livre."
    lines.append(f"Escala: {scale} (M200 ~ 10^{log_m200:.2f} Msun). {detail}")

    if model.startswith("NFW"):
        lines.append("Perfil NFW: cuspide central.")
    else:
        lines.append("Perfil SIDM com nucleo: rho ~ 1/[(r+rc)(1+r/rs)^2].")

    if sigma_m <= 0:
        lines.append("sigma/m = 0: ME puramente gravitacional.")
    elif sigma_m < 1.0:
        lines.append(f"sigma/m ~ {sigma_m:.2f} cm^2/g: faixa tipica para nucleos em anas.")
    elif sigma_m < 10.0:
        lines.append(f"sigma/m ~ {sigma_m:.2f} cm^2/g: fronteira superior de aglomerados.")
    else:
        lines.append(f"sigma/m ~ {sigma_m:.2f} cm^2/g: ja excluido por aglomerados.")

    if fb_strength <= 0:
        lines.append("Sem feedback barionico.")
    elif fb_strength < 0.4:
        lines.append(f"Feedback moderado ({fb_strength:.2f}).")
    else:
        lines.append(f"Feedback forte ({fb_strength:.2f}).")

    if step is not None and n_steps:
        try:
            frac = 100.0 * float(step) / max(float(n_steps), 1.0)
            lines.append(f"Progresso: passo {int(step)}/{int(n_steps)} ({frac:.1f}%).")
        except Exception:
            pass

    if energy_drift is not None and np.isfinite(energy_drift):
        if abs(energy_drift) < 1.0:
            lines.append(f"Energia: deriva {energy_drift:+.3g}% - integracao estavel.")
        elif abs(energy_drift) < 5.0:
            lines.append(f"Energia: deriva {energy_drift:+.3g}% - atencao a resolucao temporal.")
        else:
            lines.append(f"Energia: deriva {energy_drift:+.3g}% - resultados comprometidos.")

    if model.startswith("NFW") and sigma_m <= 0 and fb_strength <= 0:
        lines.append("Interpretacao: cenario CDM puro.")
    elif model.startswith("SIDM") or fb_strength > 0:
        lines.append("Interpretacao: modificacao de CDM.")

    return " ".join(lines)


def build_scientific_synthesis(params, rotation_metrics=None, simulation_metrics=None,
                               history=None, m200_msun=None, m_baryon_msun=None,
                               r200_kpc=None, rs_kpc=None):
    params = dict(params or {})
    rotation_metrics = dict(rotation_metrics or {})
    simulation_metrics = dict(simulation_metrics or {})
    history = list(history or [])
    log_m200 = float(params.get("log_m200", 12.0) or 12.0)
    log_mb = float(params.get("log_mbaryon", 10.5) or 10.5)
    sigma_m = float(params.get("sigma_over_m_cm2_g", 0.0) or 0.0)
    m200 = float(m200_msun) if m200_msun is not None else 10.0 ** log_m200
    m_b = float(m_baryon_msun) if m_baryon_msun is not None else 10.0 ** log_mb
    ratio = m200 / max(m_b, 1e-30)
    paragraphs = []

    paragraphs.append(
        "A pergunta central deste relatorio e: o que e a materia escura? Os testes "
        "exploraram tres hipoteses: (i) halo frio sem colisoes (NFW puro), (ii) materia "
        "escura autointeragente (SIDM), e (iii) o papel do feedback barionico."
    )

    if log_m200 < 10.0:
        escala = "galaxia ana"
    elif log_m200 < 12.5:
        escala = "galaxia tipo Via Lactea"
    elif log_m200 < 13.5:
        escala = "grupo de galaxias"
    else:
        escala = "aglomerado de galaxias"

    paragraphs.append(
        f"Massa. Halo com M200 = {m200:.3e} Msun (log10 M200 = {log_m200:.2f}), escala de {escala}. "
        f"Componente barionica = {m_b:.3e} Msun; razao M200/M_b = {ratio:.2f}."
    )

    chi2 = rotation_metrics.get("chi2_reduced")
    rmse = rotation_metrics.get("rmse_kms")
    n_pts = rotation_metrics.get("n_points", "N/D")
    chi2_txt = f"{chi2:.2f}" if isinstance(chi2, (int, float, np.number)) and np.isfinite(chi2) else "N/D"
    rmse_txt = f"{rmse:.2f} km/s" if isinstance(rmse, (int, float, np.number)) and np.isfinite(rmse) else "N/D"
    paragraphs.append(
        f"Comportamento gravitacional. Ajuste (n = {n_pts} pontos): RMSE = {rmse_txt}, chi^2 = {chi2_txt}. "
        "Sem ME, a velocidade deveria cair apos o raio visivel. Ela nao cai."
    )

    if sigma_m <= 0:
        sigma_txt = "sigma/m = 0 (puramente gravitacional)."
    elif sigma_m < 1.0:
        sigma_txt = f"sigma/m = {sigma_m:.2f} cm^2/g (faixa tipica para anas)."
    elif sigma_m < 10.0:
        sigma_txt = f"sigma/m = {sigma_m:.2f} cm^2/g (proximo ao limite de aglomerados)."
    else:
        sigma_txt = f"sigma/m = {sigma_m:.2f} cm^2/g (excluido por aglomerados)."
    paragraphs.append(
        f"Natureza colisional. {sigma_txt} Faixa viavel combinando observacoes: 0.1-1 cm^2/g."
    )

    paragraphs.append(
        "Diferenca da materia barionica. A materia visivel emite, absorve e reflete luz. "
        "A materia escura so interage gravitacionalmente; efeitos aparecem de forma indireta."
    )

    n_hist = len(history)
    if n_hist:
        drift = simulation_metrics.get("energy_drift_percent")
        drift_txt = (f"{drift:+.3g}%" if isinstance(drift, (int, float, np.number))
                     and np.isfinite(drift) else "N/D")
        paragraphs.append(
            f"Sintese dos testes. {n_hist} instantaneos acumulados. Variacao de energia = {drift_txt}."
        )
    else:
        paragraphs.append("Sintese dos testes. Nenhuma simulacao executada; diagnostico analitico.")

    paragraphs.append(
        "O que permanece aberto. A ME e identificada pelo que faz (gravitar), nao pelo que e. "
        "WIMPs, axions, neutrinos estereis, SIDM e outras hipoteses sao candidatos."
    )
    return paragraphs


# ============================================================
# PDF
# ============================================================
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
    pdf.multi_cell(0, 6,
                   "Relatorio reproduzivel: parametros, modelos, diagnosticos, historico, "
                   "esclarecimento progressivo e sintese cientifica.",
                   new_x="LMARGIN", new_y="NEXT")
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
                pdf.multi_cell(0, 4.2, "Imagem estatica 1400 x 800 px.", new_x="LMARGIN", new_y="NEXT")
                pdf.image(temp_path, x=15, w=image_width_mm)
                pdf.ln(4)
            except Exception as exc:
                warning = (f"{figure_title}: falha Kaleido. Detalhe: {str(exc)[:200]}")
                figure_warnings.append(warning)
                pdf.set_text_color(120, 45, 45)
                pdf.set_font("Helvetica", "B", 9)
                pdf.multi_cell(0, 5.2, _pdf_ascii("Grafico nao incorporado: " + warning),
                               new_x="LMARGIN", new_y="NEXT")
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
        pdf.multi_cell(0, 5.5, "Nenhum instantaneo registrado.", new_x="LMARGIN", new_y="NEXT")

    section("7. Log automatico e esclarecimento progressivo sobre a materia escura")
    logs = report_data.get("physics_log", [])
    insights = report_data.get("contextual_insights", [])
    if logs:
        pdf.set_font("Helvetica", "", 8.5)
        for i, item in enumerate(logs):
            pdf.multi_cell(0, 4.8, _pdf_ascii(item), new_x="LMARGIN", new_y="NEXT")
            if i < len(insights) and insights[i]:
                pdf.set_text_color(70, 100, 155)
                pdf.set_font("Helvetica", "I", 8.5)
                pdf.multi_cell(0, 4.6, _pdf_ascii("Esclarecimento contextual: " + insights[i]),
                               new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(35, 42, 55)
                pdf.set_font("Helvetica", "", 8.5)
            pdf.ln(1)
    else:
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5.5, "O log sera preenchido quando a simulacao avancar.",
                       new_x="LMARGIN", new_y="NEXT")

    section("8. Interpretacao e limitacoes cientificas")
    pdf.set_font("Helvetica", "", 9)
    notes = [
        "O perfil NFW e parametrizado por M200 e c; R200 e rs derivados com H0 = 70 km/s/Mpc.",
        "SIDM com nucleo e feedback sao parametrizacoes fenomenologicas.",
        "Distribuicao de velocidades Maxwelliana idealizada.",
        "Pontos observacionais sao sinteticos quando nenhum CSV valido e carregado.",
        "Tracadores em potencial fixo; nao interagem entre si.",
        "sigma/m em cm^2/g; livre caminho medio estimado localmente em rs.",
        "Energia proxy nao e medicao experimental.",
        "Assistente IA escreve em st.session_state; fisica inalterada.",
        "Fracao de ME = M_DM(<r) / [M_DM(<r) + M_baryon(<r)].",
        "Campos numericos liberados; faixas amplas podem produzir configuracoes fora do regime validado.",
        "Kernels de perfil, integracao, densidade, leapfrog e energia compilados via Numba @njit(cache=True).",
        "Blocos de integracao adaptativos (1/N_particulas) e metricas resumidas por snapshot.",
        "Spatial index (KDTree) reconstruido apenas quando os pontos se movem alem da tolerancia.",
        "Arquitetura assincrona: Celery+Redis quando disponivel; fallback ThreadPoolExecutor local.",
    ]
    for note in notes:
        pdf.multi_cell(0, 5.5, _pdf_ascii("- " + note), new_x="LMARGIN", new_y="NEXT")

    synthesis_paragraphs = report_data.get("scientific_synthesis", [])
    if synthesis_paragraphs:
        pdf.add_page()
        section("9. Sintese Cientifica: O que e a Materia Escura a luz dos testes realizados")
        pdf.set_font("Helvetica", "", 9.5)
        for paragraph in synthesis_paragraphs:
            pdf.multi_cell(0, 5.4, _pdf_ascii(paragraph), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

    output = pdf.output()
    pdf_bytes = output.encode("latin-1") if isinstance(output, str) else bytes(output)
    return pdf_bytes, (figure_warnings or None)


# ============================================================
# CABECALHO
# ============================================================
st.title("🌌 Dark Matter Lab")
st.markdown(
    '<p class="lab-subtitle">Laboratorio interativo: halos NFW, SIDM, dinamica estelar, feedback '
    'barionico, simulacoes assincronas, assistente IA e campos livres.'
    + ('<span class="numba-badge">⚡ Numba JIT</span>' if NUMBA_AVAILABLE
       else '<span class="numba-badge">⚠️ Numba ausente</span>')
    + ('<span class="async-badge">🚀 Celery + Redis</span>' if ASYNC_MODE
       else '<span class="async-badge">🧵 ThreadPool local</span>')
    + '</p>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sync-banner">🔓 <b>Campos livres</b> | '
    '🤖 <b>IA propagadora</b> (aba ⑤) | '
    '⚡ <b>Kernels Numba</b> | '
    '📊 <b>Chunks adaptativos + métricas resumidas</b> | '
    '🌐 <b>KDTree adaptativo</b> | '
    '🚀 <b>' + ('Celery+Redis' if ASYNC_MODE else 'ThreadPoolExecutor local') + '</b>. '
    'Ativações da IA: <b>' + str(st.session_state.get("ai_apply_count", 0)) + '</b></div>',
    unsafe_allow_html=True,
)

# -------------------------- ABAS ----------------------------
tab_dm, tab_model, tab_rotation, tab_feedback, tab_sim, tab_assistant = st.tabs([
    "⑥ O que é matéria escura?",
    "① Modelos teoricos e particulas",
    "② Curvas de rotacao",
    "③ Feedback barionico e densidade",
    "④ Simulacao assincrona e relatorio",
    "⑤ Assistente IA / Importador de pesquisa",
])

# ============================================================
# ABA ① - MODELOS TEORICOS
# ============================================================
with tab_model:
    st.subheader("Modelos teoricos: NFW e materia escura autointeragente")
    st.markdown(
        '<div class="free-input-note">🔓 <b>Campos livres</b>: digite qualquer valor. '
        'Os botões "↺ Restaurar típicos" aplicam presets calibrados por observações.</div>',
        unsafe_allow_html=True,
    )

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("↺ Restaurar típicos: Via Láctea", use_container_width=True, key="reset_vl"):
            restore_typical(TYPICAL_VIA_LACTEA, "Via Láctea")
            st.rerun()
    with b2:
        if st.button("↺ Restaurar típicos: Anã", use_container_width=True, key="reset_dw"):
            restore_typical(TYPICAL_DWARF, "Galáxia anã")
            st.rerun()
    with b3:
        if st.button("↺ Restaurar típicos: Aglomerado", use_container_width=True, key="reset_cl"):
            restore_typical(TYPICAL_CLUSTER, "Aglomerado")
            st.rerun()

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        candidate = st.selectbox("Candidato / cenario microscopico", CANDIDATE_OPTIONS, key="candidate")
        halo_model = st.selectbox("Perfil de halo", HALO_MODEL_OPTIONS, key="halo_model")
        log_m200 = free_number("Log10 da massa M200 (massas solares)", "log_m200",
                               "Típico VL: 12.0 | Anã: 9.5 | Aglomerado: 14.0")
        concentration = free_number("Concentração c", "concentration",
                                    "Típico VL: 9.4 | Anã: 15 | Aglomerado: 4")
    with col_b:
        log_mbaryon = free_number("Log10 da massa bariônica (massas solares)", "log_mbaryon",
                                  "Típico VL: 10.78 (~6e10 Msun)")
        a_baryon = free_number("Escala bariônica a (kpc)", "a_baryon")
        core_radius_kpc = free_number("Raio do núcleo SIDM (kpc)", "core_radius_kpc")
        r_plot_max = free_number("Raio máximo dos gráficos (kpc)", "r_plot_max")
    with col_c:
        sigma_over_m = free_number("Seção de choque por massa σ/m (cm²/g)", "sigma_over_m",
                                   "Bullet Cluster: σ/m ≲ 0.6 | Anãs: 0.1–10")
        sigma_v = free_number("Dispersão de velocidade σ_v (km/s)", "sigma_v")
        n_velocity_samples = free_int("Amostras para distribuição de velocidades", "n_velocity_samples")
        seed_velocity = free_int("Semente das velocidades", "seed_velocity")

# ============================================================
# ABA ② - CURVAS DE ROTACAO
# ============================================================
with tab_rotation:
    st.subheader("Curvas de rotacao: previsoes teoricas vs dados")
    st.markdown(
        '<div class="free-input-note">🔓 Ajuste qualquer parâmetro na aba ① — '
        'os gráficos abaixo atualizam instantaneamente.</div>',
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Carregar CSV observacional (opcional)", type=["csv", "txt"],
        key="observational_csv",
    )
    st.caption("Formato: `radius_kpc,v_obs_kms,v_err_kms`. Aliases e separadores detectados automaticamente.")
    sample_rotation_csv = (
        "radius_kpc,v_obs_kms,v_err_kms\n"
        "1.0,72.0,5.0\n2.0,96.0,5.0\n4.0,118.0,6.0\n6.0,132.0,6.0\n"
        "8.0,140.0,7.0\n12.0,180.0,8.0\n20.0,210.0,10.0\n30.0,220.0,12.0\n"
    )
    st.download_button(
        "Baixar CSV-modelo", data=sample_rotation_csv.encode("utf-8"),
        file_name="modelo_curva_rotacao.csv", mime="text/csv",
        key="download_rotation_template",
    )

# ============================================================
# ABA ③ - FEEDBACK BARIONICO
# ============================================================
with tab_feedback:
    st.subheader("Feedback barionico e estrutura espacial")
    st.markdown(
        '<div class="free-input-note">🔓 Intensidade e escala do feedback são livres; '
        'o perfil é renormalizado para preservar M200 dentro de R200.</div>',
        unsafe_allow_html=True,
    )
    fb1, fb2, fb3 = st.columns(3)
    with fb1:
        feedback_strength = free_number("Intensidade do feedback (0 = desligado)", "feedback_strength",
                                        "Típico: 0.25 (moderado) | 0.5+ (forte)")
    with fb2:
        feedback_scale = free_number("Escala radial do feedback (kpc)", "feedback_scale_kpc")
    with fb3:
        density_model = st.selectbox("Perfil usado no mapa", DENSITY_MODEL_OPTIONS, key="density_model")

# ============================================================
# ABA ④ - SIMULACAO ASSINCRONA
# ============================================================
with tab_sim:
    st.subheader("Simulação assíncrona (worker em segundo plano)")
    st.markdown(
        '<div class="free-input-note">🔓 Parâmetros livres. A simulação roda em worker '
        'assíncrono (Celery+Redis ou ThreadPool local). A UI permanece responsiva durante o cálculo. '
        'Kernels de leapfrog, energia, perfil e densidade são compilados via Numba.</div>',
        unsafe_allow_html=True,
    )

    s1, s2, s3 = st.columns(3)
    with s1:
        n_particles = free_int("Número de partículas-tracadoras", "n_particles")
        n_steps = free_int("Passos de integração", "n_steps")
        sim_halo_model = st.selectbox("Perfil do potencial", SIM_HALO_MODEL_OPTIONS, key="sim_halo_model")
    with s2:
        g_dimless = free_number("G adimensional", "g_dimless")
        dt = free_number("Passo temporal Δt", "dt")
        softening = free_number("Suavização ε", "softening")
    with s3:
        sim_seed = free_int("Semente aleatória da simulação", "sim_seed")
        auto_record = st.checkbox("Registrar automaticamente (~200 snapshots)", value=True, key="auto_record")
        if auto_record:
            record_every = max(1, int(n_steps) // 200)
            st.metric("Registrar a cada", f"{record_every} passos")
        else:
            record_every = free_int("Registrar a cada N passos", "record_every")
        st.metric("Tempo final nominal", f"{n_steps * dt:.4g}")

    st.caption(
        f"Bloco adaptativo estimado: **{compute_adaptive_chunk(n_particles)} passos** · "
        f"Snapshots esperados: **~{max(1, n_steps // max(1, record_every))}** · "
        f"Modo: **{'Celery + Redis' if ASYNC_MODE else 'ThreadPoolExecutor local'}**"
    )

# ============================================================
# VALORES COMUNS
# ============================================================
m200 = 10.0 ** log_m200
m_baryon = 10.0 ** log_mbaryon
r200, rs, rho_s = nfw_parameters(m200, concentration)

# ============================================================
# ABA ⑥ - O QUE E MATERIA ESCURA?
# ============================================================
with tab_dm:
    st.subheader("🌌 O que é matéria escura?")
    st.markdown(
        """
        <div class="dm-callout">
        <b>Matéria escura</b> é uma forma de matéria que <b>não emite, absorve ou reflete luz</b> de
        forma detectável — ela interage gravitacionalmente com a matéria comum. Sabemos que existe
        porque <b>a matéria que vemos não explica os movimentos que medimos</b>.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### As evidências")
    ev1, ev2, ev3 = st.columns(3)
    with ev1:
        st.markdown("#### 🔭 Curvas de rotação")
        st.markdown("A velocidade orbital **não cai** após a matéria visível acabar.")
    with ev2:
        st.markdown("#### 🔍 Lentes gravitacionais")
        st.markdown("Luz curvada por massas invisíveis. Bullet Cluster.")
    with ev3:
        st.markdown("#### 📡 CMB e estrutura")
        st.markdown("Anisotropias do CMB exigem ~85% de matéria fria não-bariônica.")

    st.divider()
    st.markdown("### Diagnóstico numérico com os parâmetros ativos")
    st.caption("Valores lidos do `st.session_state` — qualquer alteração nas abas ①–⑤ recalcula.")

    m200_now = 10.0 ** st.session_state["log_m200"]
    m_baryon_now = 10.0 ** st.session_state["log_mbaryon"]
    c_now = st.session_state["concentration"]
    a_now = st.session_state["a_baryon"]
    core_now = st.session_state["core_radius_kpc"]
    rmax_now = st.session_state["r_plot_max"]
    model_now = "SIDM" if st.session_state["halo_model"].upper().startswith("SIDM") else "NFW"
    fb_now = st.session_state["feedback_strength"]
    fbs_now = st.session_state["feedback_scale_kpc"]

    r_diag_candidates = np.array([8.0, 15.0, 30.0], dtype=float)
    r_diag = r_diag_candidates[r_diag_candidates <= max(rmax_now, 30.0)]
    if r_diag.size == 0:
        r_diag = np.array([max(rmax_now * 0.5, 5.0)], dtype=float)
    r_diag = as_1d(r_diag)

    v_dm_d, v_b_d, v_tot_d, _, _, m_dm_d, m_b_d = rotation_components(
        r_diag, m200_now, c_now, m_baryon_now, a_now,
        model=model_now, core_radius_kpc=core_now,
        feedback_strength=fb_now, feedback_scale_kpc=fbs_now,
    )
    v_dm_d = as_1d(v_dm_d); v_b_d = as_1d(v_b_d); v_tot_d = as_1d(v_tot_d)
    m_dm_d = as_1d(m_dm_d); m_b_d = as_1d(m_b_d)
    dm_frac_d = m_dm_d / np.maximum(m_dm_d + m_b_d, 1e-30)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("M200 (halo total)", f"{m200_now:.2e} M☉")
    col2.metric("M_bárion (visível)", f"{m_baryon_now:.2e} M☉")
    col3.metric("Razão M200 / M_bárion", f"{m200_now / max(m_baryon_now, 1e-30):.2f}")
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
    fig_dm.add_trace(go.Scatter(x=radii_dm, y=v_tot_d_full, mode="lines",
                                name="Com ME (NFW+bárions)", line=dict(color="#8b7cff", width=4)))
    fig_dm.add_trace(go.Scatter(x=radii_dm, y=v_bar_d, mode="lines",
                                name="SÓ bárions (sem ME)", line=dict(color="#ffbd69", width=3, dash="dash")))
    fig_dm.add_trace(go.Scatter(x=radii_dm, y=v_kepler, mode="lines",
                                name="Kepler (v ∝ 1/√r)", line=dict(color="#f472b6", width=2, dash="dot")))
    fig_dm.update_layout(
        template="plotly_dark", height=480,
        title="Diagnóstico: por que a matéria escura é necessária",
        xaxis_title="Raio (kpc)", yaxis_title="Velocidade circular (km/s)",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
        legend=dict(orientation="h", y=1.13),
    )
    st.plotly_chart(fig_dm, use_container_width=True)

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
        name="Fração de ME", line=dict(color="#58c4dd", width=3),
        fill="tozeroy", fillcolor="rgba(88,196,221,0.15)",
    ))
    fig_frac.add_hline(y=50, line=dict(color="#aabbd7", dash="dot", width=1))
    fig_frac.update_layout(
        template="plotly_dark", height=380,
        title="Fração de ME dentro de cada raio",
        xaxis_title="Raio (kpc)", yaxis_title="M_DM / M_total (%)",
        yaxis_range=[0, 100],
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
    )
    st.plotly_chart(fig_frac, use_container_width=True)

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
        st.warning("Diagnóstico indisponível com os parâmetros atuais.")
    else:
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
    st.markdown("### Prévia da Síntese Científica (seção 9 do PDF)")
    _preview_params = {
        "halo_model": st.session_state.get("halo_model", "NFW"),
        "feedback_strength": float(st.session_state.get("feedback_strength", 0.0) or 0.0),
        "sigma_over_m_cm2_g": float(st.session_state.get("sigma_over_m", 0.0) or 0.0),
        "log_m200": float(st.session_state.get("log_m200", 12.0) or 12.0),
        "log_mbaryon": float(st.session_state.get("log_mbaryon", 10.5) or 10.5),
        "concentration": float(st.session_state.get("concentration", 10.0) or 10.0),
    }
    try:
        _preview_paragraphs = build_scientific_synthesis(
            params=_preview_params,
            rotation_metrics=st.session_state.get("rotation_metrics", {}),
            simulation_metrics=st.session_state.get("simulation_metrics", {}),
            history=st.session_state.get("async_history", []),
            m200_msun=10.0 ** _preview_params["log_m200"],
            m_baryon_msun=10.0 ** _preview_params["log_mbaryon"],
        )
        for i, para in enumerate(_preview_paragraphs, start=1):
            with st.expander(f"§{i} — {para.split('.')[0][:80]}...", expanded=(i == 1)):
                st.markdown(para)
    except Exception as _exc:
        st.warning(f"Prévia indisponível: {_exc}")

# ============================================================
# CONTEUDO DAS ABAS 1, 2, 3
# ============================================================
with tab_model:
    r200_m, rs_m, _ = nfw_parameters(m200, concentration)
    fb_now_m = float(st.session_state.get("feedback_strength", 0.25))
    fbs_now_m = float(st.session_state.get("feedback_scale_kpc", 3.0))

    mm1, mm2, mm3, mm4, mm5 = st.columns(5)
    mm1.metric("M200", f"{m200:.2e} M☉")
    mm2.metric("R200", f"{r200_m:.2f} kpc")
    mm3.metric("Raio de escala rs", f"{rs_m:.3f} kpc")
    mm4.metric("Concentração c", f"{concentration:.2f}")
    if sigma_over_m > 0:
        rho_local = density_at_scale_radius_g_cm3(
            m200, concentration, halo_model, core_radius_kpc, fb_now_m, fbs_now_m,
        )
        mean_free_path_kpc = 1.0 / max(rho_local * sigma_over_m * KPC_CM, 1e-300)
        mfp_label = f"{mean_free_path_kpc:.2g} kpc"
    else:
        mean_free_path_kpc = float("inf")
        mfp_label = "Infinito"
    mm5.metric("Livre médio estimado em rs", mfp_label)

    if sigma_over_m > 0 and np.isfinite(mean_free_path_kpc) and np.isfinite(r200_m):
        if mean_free_path_kpc > 5 * r200_m:
            st.warning(f"⚠️ SIDM: λ ≈ {mean_free_path_kpc:.0f} kpc ≫ R200 = {r200_m:.0f} kpc.")
        elif mean_free_path_kpc > r200_m:
            st.info(f"ℹ️ SIDM marginal: λ ≈ {mean_free_path_kpc:.0f} kpc > R200.")
        else:
            st.success(f"✅ SIDM colisional: λ ≈ {mean_free_path_kpc:.1f} kpc < R200.")

    st.markdown("#### Perfil de densidade: NFW vs SIDM")
    r_density = np.geomspace(max(0.001, r_plot_max / 10000.0), max(r_plot_max, 0.01), 300)
    rho_nfw = profile_density(r_density, m200, concentration, core_radius_kpc, "NFW")
    rho_sidm = profile_density(r_density, m200, concentration, core_radius_kpc, "SIDM")
    fig_density_compare = go.Figure()
    fig_density_compare.add_trace(go.Scatter(x=r_density, y=rho_nfw, mode="lines",
                                             name="NFW", line=dict(width=3, color="#8b7cff")))
    fig_density_compare.add_trace(go.Scatter(x=r_density, y=rho_sidm, mode="lines",
                                             name="SIDM com núcleo", line=dict(width=3, color="#58c4dd")))
    fig_density_compare.update_layout(
        template="plotly_dark", height=410, title="Perfis de densidade do halo",
        xaxis_title="Raio r (kpc)", yaxis_title="Densidade (M☉/kpc³)",
        xaxis_type="log", yaxis_type="log",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
    )
    st.plotly_chart(fig_density_compare, use_container_width=True)

    st.markdown("#### Distribuição de velocidades")
    rng_velocity = np.random.default_rng(int(seed_velocity))
    velocity_vectors = rng_velocity.normal(0.0, sigma_v, size=(int(n_velocity_samples), 3))
    speeds = np.linalg.norm(velocity_vectors, axis=1)
    v_grid = np.linspace(0.0, max(4.5 * sigma_v, float(np.max(speeds)) * 1.03), 350)
    speed_pdf = maxwell_speed_pdf(v_grid, sigma_v)
    fig_velocity = go.Figure()
    fig_velocity.add_trace(go.Histogram(x=speeds, histnorm="probability density", nbinsx=45,
                                        name="Amostras numéricas", opacity=0.62, marker_color="#58c4dd"))
    fig_velocity.add_trace(go.Scatter(x=v_grid, y=speed_pdf, mode="lines", name="Maxwell teórica",
                                      line=dict(color="#ffbd69", width=3)))
    fig_velocity.update_layout(
        template="plotly_dark", height=420, barmode="overlay",
        title="Distribuição dos módulos de velocidade",
        xaxis_title="Velocidade (km/s)", yaxis_title="Densidade de probabilidade",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
    )
    st.plotly_chart(fig_velocity, use_container_width=True)
    v1, v2, v3 = st.columns(3)
    v1.metric("Velocidade média", f"{np.mean(speeds):.1f} km/s")
    v2.metric("Velocidade RMS", f"{np.sqrt(np.mean(speeds**2)):.1f} km/s")
    v3.metric("Média teórica Maxwell", f"{2*np.sqrt(2/np.pi)*sigma_v:.1f} km/s")

with tab_rotation:
    fb_now = float(st.session_state.get("feedback_strength", 0.25))
    fbs_now = float(st.session_state.get("feedback_scale_kpc", 3.0))
    radii = np.linspace(max(0.01, r_plot_max / 10000.0), r_plot_max, 240)
    v_nfw_dm, v_baryon, v_nfw_total, _, rs_r, m_dm_arr, m_b_arr = rotation_components(
        radii, m200, concentration, m_baryon, a_baryon, model="NFW",
    )
    v_sidm_dm, _, v_sidm_total, _, _, _, _ = rotation_components(
        radii, m200, concentration, m_baryon, a_baryon,
        model="SIDM", core_radius_kpc=core_radius_kpc,
        feedback_strength=fb_now, feedback_scale_kpc=fbs_now,
    )
    v_kepler = np.sqrt(G_ASTRO * m_baryon / np.maximum(radii, 1e-8))

    selected_curve = st.radio(
        "Modelo usado para resíduos",
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
            source_label = "Dados do CSV"
        except Exception as exc:
            csv_error = str(exc)
            st.error(f"CSV invalido: {csv_error}")

    if obs_df is None:
        rng_obs = np.random.default_rng(2025)
        r_obs = np.linspace(max(0.01, r_plot_max / 100.0), r_plot_max * 0.9, 14)
        _, _, v_model_obs, _, _, _, _ = rotation_components(
            r_obs, m200, concentration, m_baryon, a_baryon, model="NFW",
        )
        errors = np.maximum(5.0, 0.04 * v_model_obs)
        v_observed = np.maximum(0.0, v_model_obs + rng_obs.normal(0.0, errors))
        obs_df = pd.DataFrame({"radius_kpc": r_obs, "v_obs_kms": v_observed, "v_err_kms": errors})
        if csv_error:
            source_label = "Sinteticos (CSV rejeitado)"

    fig_rot = go.Figure()
    fig_rot.add_trace(go.Scatter(x=radii, y=v_nfw_total, mode="lines", name="Com ME: NFW+bárions",
                                 line=dict(color="#8b7cff", width=3.5)))
    fig_rot.add_trace(go.Scatter(x=radii, y=v_sidm_total, mode="lines", name="Com ME: SIDM+feedback",
                                 line=dict(color="#58c4dd", width=3)))
    fig_rot.add_trace(go.Scatter(x=radii, y=v_baryon, mode="lines", name="SEM ME (só bárions)",
                                 line=dict(color="#ffbd69", width=3, dash="dash")))
    fig_rot.add_trace(go.Scatter(x=radii, y=v_kepler, mode="lines", name="Kepler (v ∝ 1/√r)",
                                 line=dict(color="#f472b6", width=1.8, dash="dot")))
    marker_kwargs = {
        "x": obs_df["radius_kpc"], "y": obs_df["v_obs_kms"], "mode": "markers",
        "name": source_label,
        "marker": dict(color="#f472b6", size=8, symbol="circle-open", line=dict(width=2)),
    }
    if "v_err_kms" in obs_df.columns and obs_df["v_err_kms"].notna().any():
        marker_kwargs["error_y"] = dict(type="data", array=obs_df["v_err_kms"].fillna(0),
                                        visible=True, thickness=1.2)
    fig_rot.add_trace(go.Scatter(**marker_kwargs))
    fig_rot.update_layout(
        template="plotly_dark", height=560,
        title="Curva de rotação: com vs sem matéria escura",
        xaxis_title="Raio (kpc)", yaxis_title="Velocidade circular (km/s)",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
        legend=dict(orientation="h", y=1.13),
    )
    st.plotly_chart(fig_rot, use_container_width=True)

    with st.expander("🧪 Fração de ME por raio", expanded=True):
        _, _, dm_frac_curve = dark_matter_fraction_at_radius(
            radii, m200, concentration, m_baryon, a_baryon,
            model="NFW", core_radius_kpc=core_radius_kpc,
            feedback_strength=fb_now, feedback_scale_kpc=fbs_now,
        )
        dm_frac_curve = as_1d(dm_frac_curve)
        fig_frac = go.Figure()
        fig_frac.add_trace(go.Scatter(
            x=radii, y=100.0 * dm_frac_curve, mode="lines",
            name="Fração ME", line=dict(color="#58c4dd", width=3),
            fill="tozeroy", fillcolor="rgba(88,196,221,0.15)",
        ))
        fig_frac.update_layout(
            template="plotly_dark", height=340,
            title="Fração de ME dentro de cada raio",
            xaxis_title="Raio (kpc)", yaxis_title="M_DM / M_total (%)",
            yaxis_range=[0, 100],
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
        )
        st.plotly_chart(fig_frac, use_container_width=True)

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
    chi2_red = (float(np.mean((residuals[valid_err] / obs_df.loc[valid_err, "v_err_kms"].to_numpy())**2))
                if np.any(valid_err) else float("nan"))
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Pontos", f"{len(obs_df)}")
    k2.metric("RMSE", f"{rmse:.2f} km/s")
    k3.metric("MAE", f"{mae:.2f} km/s")
    k4.metric("χ² médio", f"{chi2_red:.2f}" if np.isfinite(chi2_red) else "N/D")

    st.session_state["rotation_metrics"] = {
        "source": source_label, "model": selected_curve,
        "n_points": int(len(obs_df)), "rmse_kms": rmse, "mae_kms": mae,
        "chi2_reduced": chi2_red,
        "csv_valid": bool(uploaded is not None and csv_error is None),
        "csv_error": csv_error or "",
        "original_headers": ", ".join(original_headers),
        "separator": separator_used,
    }

with tab_feedback:
    rr_feedback = np.geomspace(max(0.001, r_plot_max / 10000.0), max(r_plot_max, 0.01), 320)
    rho_base = profile_density(rr_feedback, m200, concentration, core_radius_kpc,
                               density_model, 0.0, feedback_scale)
    rho_modified = profile_density(rr_feedback, m200, concentration, core_radius_kpc,
                                   density_model, feedback_strength, feedback_scale)
    fb_fig = go.Figure()
    fb_fig.add_trace(go.Scatter(x=rr_feedback, y=rho_base, mode="lines", name="Sem feedback",
                                line=dict(color="#ffbd69", width=2, dash="dash")))
    fb_fig.add_trace(go.Scatter(x=rr_feedback, y=rho_modified, mode="lines", name="Com feedback",
                                line=dict(color="#8b7cff", width=3)))
    fb_fig.update_layout(
        template="plotly_dark", height=420, title="Efeito do feedback sobre o perfil radial",
        xaxis_title="Raio r (kpc)", yaxis_title="Densidade (M☉/kpc³)",
        xaxis_type="log", yaxis_type="log",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
    )
    st.plotly_chart(fb_fig, use_container_width=True)

    st.markdown("#### Mapa espacial 2D")
    extent = min(max(3.0 * rs, 5.0), r_plot_max)
    grid = np.linspace(-extent, extent, 120)
    xx, yy = np.meshgrid(grid, grid)
    rr = np.sqrt(xx**2 + yy**2)
    rho_map = profile_density(np.maximum(rr, 0.03), m200, concentration, core_radius_kpc,
                              density_model, feedback_strength, feedback_scale)
    zz = np.log10(np.maximum(rho_map, 1e-30))
    fig_map = go.Figure(data=go.Heatmap(
        x=grid, y=grid, z=zz, colorscale="Magma", colorbar=dict(title="log10 rho"),
        hovertemplate="x=%{x:.2f} kpc<br>y=%{y:.2f} kpc<br>log10 rho=%{z:.2f}<extra></extra>",
    ))
    fig_map.add_shape(type="circle", x0=-a_baryon, y0=-a_baryon, x1=a_baryon, y1=a_baryon,
                      line=dict(color="#58c4dd", dash="dash", width=2))
    fig_map.update_layout(
        template="plotly_dark", height=500,
        title=f"Densidade {density_model} com feedback",
        xaxis_title="x (kpc)", yaxis_title="y (kpc)",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
    )
    fig_map.update_yaxes(scaleanchor="x", scaleratio=1)
    st.plotly_chart(fig_map, use_container_width=True)

# ============================================================
# CONTEUDO DA ABA ④ - PAINEL ASSINCRONO + PDF
# ============================================================
with tab_sim:
    _, rs_sim, _ = nfw_parameters(m200, concentration)
    current_params = {
        "n_particles": int(n_particles), "n_steps": int(n_steps),
        "g_dimless": float(g_dimless), "dt": float(dt), "seed": int(sim_seed),
        "softening": float(softening), "concentration": float(concentration),
        "record_every": int(record_every), "halo_model": sim_halo_model,
        "core_radius_over_rs": float(core_radius_kpc / max(rs_sim, 1e-12)),
        "feedback_strength": float(feedback_strength),
        "feedback_scale_over_rs": float(feedback_scale / max(rs_sim, 1e-12)),
        "sigma_over_m_cm2_g": float(sigma_over_m),
        "log_m200": float(log_m200), "log_mbaryon": float(log_mbaryon),
    }

    ctrl1, ctrl2, ctrl3 = st.columns(3)
    with ctrl1:
        start_clicked = st.button("▶ Iniciar (worker assíncrono)", type="primary",
                                   use_container_width=True, key="async_start")
    with ctrl2:
        stop_clicked = st.button("⏹ Cancelar / limpar", use_container_width=True, key="async_stop")
    with ctrl3:
        st.metric("Modo", "Celery+Redis" if ASYNC_MODE else "ThreadPool")

    if start_clicked:
        task_id = submit_simulation_async(current_params, int(sim_seed))
        st.session_state["async_task_id"] = task_id
        st.session_state["async_history"] = []
        st.session_state["async_elapsed"] = 0.0
        st.session_state["async_kdtree_rebuilds"] = 0
        st.session_state["async_started_at"] = time.time()
        st.session_state["sim_status"] = "Executando"
        st.rerun()

    if stop_clicked:
        st.session_state["async_task_id"] = None
        st.session_state["async_history"] = []
        st.session_state["sim_status"] = "Nao iniciada"
        st.rerun()

    task_id = st.session_state.get("async_task_id")
    status_color = "#72d6a4" if st.session_state.get("sim_status") == "Concluida" else (
        "#ffbd69" if st.session_state.get("sim_status") == "Executando" else "#aabbd7")
    st.markdown(
        f'<div class="lab-card"><b>Task ID:</b> <code>{task_id or "—"}</code> · '
        f'<b>Estado:</b> <span style="color:{status_color}">{st.session_state.get("sim_status", "Nao iniciada")}</span>'
        + (f' · <b>Worker:</b> {"Celery" if ASYNC_MODE else "ThreadPool"}')
        + "</div>",
        unsafe_allow_html=True,
    )

    @st.fragment(run_every=1.0 if st.session_state.get("sim_status") == "Executando" else None)
    def async_simulation_panel():
        tid = st.session_state.get("async_task_id")
        if not tid:
            st.info("Nenhuma simulação ativa. Ajuste os parâmetros e clique em **Iniciar (worker assíncrono)**.")
            return

        state = poll_simulation(tid)
        status = state.get("status", "Desconhecido")
        progress = float(state.get("progress", 0.0))
        st.progress(min(1.0, progress / 100.0), text=f"{status} — {progress:.1f}%")

        # Concluida: armazena o historico completo
        if status == "Concluida":
            history = state.get("history", [])
            st.session_state["async_history"] = history
            st.session_state["async_elapsed"] = float(state.get("elapsed_seconds", 0.0))
            st.session_state["async_kdtree_rebuilds"] = int(state.get("n_kdtree_rebuilds", 0))
            st.session_state["sim_status"] = "Concluida"

        history = state.get("history", []) or st.session_state.get("async_history", [])
        if history:
            df = pd.DataFrame(history)
            last = history[-1]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Passo", f"{last.get('step', 0):,} / {state.get('n_steps', n_steps):,}")
            m2.metric("Tempo adimensional", f"{last.get('time', 0.0):.4g}")
            m3.metric("v RMS", f"{last.get('v_rms', 0.0):.4g}")
            m4.metric("Deriva de energia", f"{last.get('energy_drift', 0.0):+.3g}%")

            st.caption(
                f"Bloco adaptativo: **{compute_adaptive_chunk(n_particles)} passos** · "
                f"Snapshots: **{len(history)}** · "
                f"KDTree rebuilds: **{st.session_state.get('async_kdtree_rebuilds', 0)}** · "
                f"Tempo decorrido: **{st.session_state.get('async_elapsed', 0.0):.2f} s**"
            )

            c1, c2 = st.columns(2)
            with c1:
                fig_e = go.Figure()
                fig_e.add_trace(go.Scatter(x=df["time"], y=df["energy"],
                                            mode="lines+markers", name="Energia proxy"))
                fig_e.update_layout(
                    template="plotly_dark", height=400,
                    title="Energia específica (proxy) — worker assíncrono",
                    xaxis_title="Tempo adimensional", yaxis_title="Energia específica",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
                )
                st.plotly_chart(fig_e, use_container_width=True)
            with c2:
                fig_r = go.Figure()
                fig_r.add_trace(go.Scatter(x=df["time"], y=df["r_rms"],
                                            mode="lines+markers", name="r RMS"))
                fig_r.add_trace(go.Scatter(x=df["time"], y=df["r_max"],
                                            mode="lines", name="r max",
                                            line=dict(dash="dash")))
                fig_r.update_layout(
                    template="plotly_dark", height=400,
                    title="Raio RMS e máximo",
                    xaxis_title="Tempo adimensional", yaxis_title="Raio (unid. de rs)",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
                )
                st.plotly_chart(fig_r, use_container_width=True)

            st.markdown("### Histórico compacto (métricas resumidas)")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Exportar histórico assíncrono (CSV)",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="historico_simulacao_async.csv",
                mime="text/csv", key="download_async_history",
            )
        elif status == "Executando":
            st.info("Simulação rodando em segundo plano. Os snapshots aparecerão assim que o primeiro bloco terminar.")

    async_simulation_panel()

    # ---------------- PDF com histórico assíncrono ----------------
    rotation_metrics = st.session_state.get("rotation_metrics", {})
    async_history = st.session_state.get("async_history", [])
    last = async_history[-1] if async_history else {}
    drift_pct = last.get("energy_drift", float("nan"))
    elapsed = st.session_state.get("async_elapsed", 0.0)

    r30_report = min(30.0, r_plot_max)
    _, _, f30_report = dark_matter_fraction_at_radius(
        np.array([r30_report]), m200, concentration, m_baryon, a_baryon,
        model="SIDM" if halo_model.upper().startswith("SIDM") else "NFW",
        core_radius_kpc=core_radius_kpc,
        feedback_strength=feedback_strength, feedback_scale_kpc=feedback_scale,
    )
    f30_report = as_1d(f30_report)

    physics_rows = [
        ("Candidato", candidate), ("Modelo", halo_model),
        ("Massa M200", f"{m200:.5e} Msun"), ("R200", f"{r200:.4g} kpc"),
        ("rs", f"{rs:.4g} kpc"), ("c", f"{concentration:.4g}"),
        ("M_bárion", f"{m_baryon:.5e} Msun"), ("a_báryon", f"{a_baryon:.4g} kpc"),
        ("r_plot_max", f"{r_plot_max:.4g} kpc"), ("feedback_strength", f"{feedback_strength:.4g}"),
        ("feedback_scale", f"{feedback_scale:.4g} kpc"), ("λ em rs", mfp_label),
        ("core_radius", f"{core_radius_kpc:.4g} kpc"), ("σ/m", f"{sigma_over_m:.4g} cm²/g"),
        ("σ_v", f"{sigma_v:.4g} km/s"), ("N_vel_amostras", str(n_velocity_samples)),
        ("seed_velocity", str(seed_velocity)),
    ]
    rotation_rows = [
        ("Origem", rotation_metrics.get("source", "N/D")),
        ("Modelo", rotation_metrics.get("model", "N/D")),
        ("Pontos", str(rotation_metrics.get("n_points", "N/D"))),
        ("RMSE", f"{rotation_metrics.get('rmse_kms', float('nan')):.4g} km/s"
         if np.isfinite(rotation_metrics.get("rmse_kms", float("nan"))) else "N/D"),
        ("MAE", f"{rotation_metrics.get('mae_kms', float('nan')):.4g} km/s"
         if np.isfinite(rotation_metrics.get("mae_kms", float("nan"))) else "N/D"),
        ("χ² médio", f"{rotation_metrics.get('chi2_reduced', float('nan')):.4g}"
         if np.isfinite(rotation_metrics.get("chi2_reduced", float("nan"))) else "N/D"),
        ("CSV válido", str(rotation_metrics.get("csv_valid", False))),
    ]
    dm_diagnostic_rows = [
        ("M200", f"{m200:.4e} Msun"),
        ("M_bárion", f"{m_baryon:.4e} Msun"),
        ("M200 / M_bárion", f"{m200 / max(m_baryon, 1e-30):.2f}"),
        (f"Fração ME em {r30_report:.0f} kpc", f"{float(f30_report[0])*100:.2f}%"),
    ]
    sim_rows = [
        ("Modo", "Celery + Redis" if ASYNC_MODE else "ThreadPool local"),
        ("Task ID", str(st.session_state.get("async_task_id") or "—")),
        ("Estado", st.session_state.get("sim_status", "Nao iniciada")),
        ("N partículas", str(n_particles)), ("Passos previstos", str(n_steps)),
        ("Passo atual", str(last.get("step", 0))),
        ("Tempo final nominal", f"{n_steps * dt:.5g}"), ("g", f"{g_dimless:.5g}"),
        ("dt", f"{dt:.5g}"), ("seed", str(sim_seed)),
        ("Perfil potencial", sim_halo_model),
        ("Feedback", f"{feedback_strength:.3g}"),
        ("Kernels", "Numba njit" if NUMBA_AVAILABLE else "numpy fallback"),
        ("Bloco adaptativo", f"{compute_adaptive_chunk(n_particles)} passos"),
        ("KDTree rebuilds", str(st.session_state.get("async_kdtree_rebuilds", 0))),
        ("Tempo decorrido (s)", f"{elapsed:.3g}"),
        ("Deriva de energia", f"{drift_pct:+.3g}%" if np.isfinite(drift_pct) else "N/D"),
    ]

    if st.button("📄 Gerar relatório PDF completo", type="primary",
                 use_container_width=True, key="generate_dark_matter_pdf"):
        report_figures = {
            "Perfis de densidade: NFW vs SIDM": fig_density_compare,
            "Distribuicao de velocidades": fig_velocity,
            "Curva de rotacao: com vs sem materia escura": fig_rot,
            "Perfil radial com feedback": fb_fig,
            "Mapa espacial 2D": fig_map,
        }

        if async_history:
            df_h = pd.DataFrame(async_history)
            fig_e_rep = go.Figure()
            fig_e_rep.add_trace(go.Scatter(x=df_h["time"], y=df_h["energy"],
                                            mode="lines+markers", name="Energia proxy"))
            fig_e_rep.update_layout(
                template="plotly_dark", title="Diagnóstico de energia (worker assíncrono)",
                xaxis_title="Tempo adimensional", yaxis_title="Energia (proxy)", height=430,
            )
            fig_r_rep = go.Figure()
            fig_r_rep.add_trace(go.Scatter(x=df_h["time"], y=df_h["r_rms"],
                                            mode="lines+markers", name="r RMS"))
            fig_r_rep.add_trace(go.Scatter(x=df_h["time"], y=df_h["r_max"],
                                            mode="lines", name="r max", line=dict(dash="dash")))
            fig_r_rep.update_layout(
                template="plotly_dark", title="Raio RMS e máximo",
                xaxis_title="Tempo adimensional", yaxis_title="Raio (unid. de rs)", height=430,
            )
            report_figures["Diagnóstico de energia (assíncrono)"] = fig_e_rep
            report_figures["Raio RMS e máximo"] = fig_r_rep

        history_rows = []
        for item in async_history[-24:]:
            history_rows.append((
                f"Passo {item.get('step', '?')}",
                f"t={item.get('time', 0.0):.5g} | E={item.get('energy', 0.0):.6g} | "
                f"drift={item.get('energy_drift', 0.0):+.4g}% | "
                f"vRMS={item.get('v_rms', 0.0):.5g} | Rrms={item.get('r_rms', 0.0):.5g} | "
                f"Rmax={item.get('r_max', 0.0):.5g} | p50={item.get('r_p50', 0.0):.5g} | "
                f"p90={item.get('r_p90', 0.0):.5g} | estado={item.get('status', '?')}"
            ))
        physics_log_rows = [
            f"[{item.get('recorded_at', '?')}] {explain_simulation_physics(item.get('step', 0), item.get('time', 0.0), current_params, item.get('energy', 0.0), item.get('energy_drift', 0.0), item.get('v_rms', 0.0), item.get('r_rms', 0.0), item.get('r_mean', 0.0), 'instantaneo_periodico', item.get('status', '?'))}"
            for item in async_history[-30:]
        ]
        contextual_insights_rows = [
            generate_contextual_insight(current_params, step=item.get("step", 0),
                                         n_steps=n_steps, energy_drift=item.get("energy_drift", 0.0),
                                         event_type="instantaneo_periodico")
            for item in async_history[-30:]
        ]
        synthesis_paragraphs = build_scientific_synthesis(
            params=current_params, rotation_metrics=rotation_metrics,
            simulation_metrics={"energy_drift_percent": drift_pct, "velocity_rms": last.get("v_rms", 0.0), "status": st.session_state.get("sim_status", "Nao iniciada")},
            history=async_history,
            m200_msun=m200, m_baryon_msun=m_baryon, r200_kpc=r200, rs_kpc=rs,
        )

        with st.spinner("Gerando PDF..."):
            pdf_bytes, pdf_chart_warnings = generate_pdf_report(
                {
                    "physics_rows": physics_rows,
                    "rotation_rows": rotation_rows,
                    "dm_diagnostic_rows": dm_diagnostic_rows,
                    "simulation_rows": sim_rows,
                    "history_rows": history_rows,
                    "physics_log": physics_log_rows,
                    "contextual_insights": contextual_insights_rows,
                    "scientific_synthesis": synthesis_paragraphs,
                },
                figures=report_figures,
            )
            st.session_state["dark_matter_pdf_bytes"] = pdf_bytes
            st.session_state["dark_matter_pdf_chart_warning"] = pdf_chart_warnings
            st.session_state["dark_matter_pdf_generated_at"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    if st.session_state.get("dark_matter_pdf_bytes"):
        st.success("Relatório gerado em "
                   + st.session_state.get("dark_matter_pdf_generated_at", "esta sessão") + ".")
        st.download_button(
            "⬇️ Baixar relatório PDF",
            data=st.session_state["dark_matter_pdf_bytes"],
            file_name="relatorio_dark_matter_lab.pdf", mime="application/pdf",
            use_container_width=True, key="download_dark_matter_pdf",
        )
        if st.session_state.get("dark_matter_pdf_chart_warning"):
            warnings = st.session_state["dark_matter_pdf_chart_warning"]
            if isinstance(warnings, str):
                warnings = [warnings]
            st.warning("PDF criado; algumas figuras não incorporadas:")
            for w in warnings:
                st.caption(w)

# ============================================================
# ABA ⑤ - ASSISTENTE IA / IMPORTADOR DE PESQUISA
# ============================================================
with tab_assistant:
    st.subheader("🤖 Assistente IA e Importador de Pesquisa")
    st.markdown(
        '<div class="nl-hint">Duas formas de atualizar os parâmetros:<br>'
        '&nbsp;&nbsp;1. <b>Linguagem natural</b> (PT/EN) — descreva o cenário.<br>'
        '&nbsp;&nbsp;2. <b>Importar pesquisa</b> — cole JSON ou CSV de um paper/outra IA.<br>'
        'Em ambos os casos, todas as abas (①–⑥) são atualizadas automaticamente.</div>',
        unsafe_allow_html=True,
    )

    st.markdown("### Modo 1 — Linguagem natural")
    st.markdown(
        "Exemplos suportados:\n"
        "- *\"Configure uma galaxia parecida com a Via Lactea, com secao de choque SIDM de 1.5 e concentracao 12\"*\n"
        "- *\"Galaxia ana com M200 de 10^9.5, nucleo SIDM de 0.8 kpc e sigma/m 2.0\"*\n"
        "- *\"Aglomerado de galaxias com massa M200 de 1e15, concentracao 4, feedback 0.4\"*\n"
        "- *\"Use NFW, M200 10^12.5, barionica 10^11, escala barionica 4 kpc, dispersao 150 km/s\"*\n"
        "- *\"Simulacao com 2000 particulas, 5000 passos, dt 0.005, g 0.08, seed 123\"*"
    )
    nl_text = st.text_area(
        "Instrução:",
        value=st.session_state.get("nl_last_input", ""),
        height=110, key="nl_assistant_input",
        placeholder="Ex.: Galáxia tipo Via Láctea com SIDM sigma/m 1.5, concentração 12, feedback 0.3 e 2000 partículas.",
    )
    a1, a2 = st.columns([2, 1])
    with a1:
        apply_nl = st.button("🎯 Aplicar (linguagem natural)", type="primary",
                             use_container_width=True, key="nl_apply_button")
    with a2:
        if st.button("🧹 Limpar", use_container_width=True, key="nl_clear_button"):
            st.session_state["nl_assistant_input"] = ""
            st.rerun()

    if apply_nl:
        changes, matches = parse_natural_language_config(nl_text or "")
        st.session_state["nl_last_input"] = nl_text or ""
        st.session_state["nl_last_matches"] = matches
        st.session_state["ai_last_source"] = "linguagem natural"
        if changes:
            st.session_state["nl_pending_changes"] = changes
        else:
            st.session_state["nl_last_applied"] = []
            st.session_state["nl_last_skipped"] = []
            st.session_state["nl_last_timestamp"] = datetime.now().strftime("%H:%M:%S")
        st.rerun()

    st.divider()
    st.markdown("### Modo 2 — Importar pesquisa (JSON ou CSV)")
    st.markdown(
        "Cole dados estruturados. **Formato JSON**: `{\"log_m200\": 12.5, \"concentration\": 8.4}`  \n"
        "**Formato CSV**: `log_m200,12.5` (uma por linha)"
    )
    research_text = st.text_area(
        "Dados de pesquisa:", value="", height=160, key="research_input",
        placeholder='{"log_m200": 12.5, "concentration": 8.4, "sigma_over_m": 0.5}',
    )
    r1, r2, r3 = st.columns([2, 1, 1])
    with r1:
        apply_research = st.button("🔬 Importar e aplicar", type="primary",
                                   use_container_width=True, key="apply_research_button")
    with r2:
        if st.button("📥 Exemplo JSON", use_container_width=True, key="example_json_button"):
            st.session_state["research_input"] = json.dumps({
                "log_m200": 12.5, "concentration": 8.4, "log_mbaryon": 11.0,
                "sigma_over_m": 0.5, "sigma_v": 180, "feedback_strength": 0.3,
            }, indent=2)
            st.rerun()
    with r3:
        if st.button("🧹 Limpar JSON", use_container_width=True, key="clear_research_button"):
            st.session_state["research_input"] = ""
            st.rerun()

    if apply_research:
        changes, matches = parse_research_json_or_csv(research_text or "")
        st.session_state["nl_last_matches"] = matches
        st.session_state["ai_last_source"] = "importacao de pesquisa"
        if changes:
            st.session_state["nl_pending_changes"] = changes
        else:
            st.session_state["nl_last_applied"] = []
            st.session_state["nl_last_skipped"] = []
            st.session_state["nl_last_timestamp"] = datetime.now().strftime("%H:%M:%S")
        st.rerun()

    st.divider()
    st.markdown("### Presets rápidos (calibrados por observações)")
    p1, p2, p3 = st.columns(3)
    with p1:
        if st.button("🌌 Via Láctea (M200=1e12, c=9.4)", use_container_width=True, key="preset_vl"):
            restore_typical(TYPICAL_VIA_LACTEA, "Via Láctea")
            st.rerun()
    with p2:
        if st.button("🔵 Anã (M200=1e9.5, c=15)", use_container_width=True, key="preset_dw"):
            restore_typical(TYPICAL_DWARF, "Galáxia anã")
            st.rerun()
    with p3:
        if st.button("🟠 Aglomerado (M200=1e14, c=4)", use_container_width=True, key="preset_cl"):
            restore_typical(TYPICAL_CLUSTER, "Aglomerado")
            st.rerun()

    st.divider()
    st.markdown("### Última aplicação")
    last_ts = st.session_state.get("nl_last_timestamp", "")
    applied = st.session_state.get("nl_last_applied", [])
    skipped = st.session_state.get("nl_last_skipped", [])
    matches = st.session_state.get("nl_last_matches", [])
    source = st.session_state.get("ai_last_source", "")
    if last_ts:
        st.caption(f"Origem: **{source or 'manual'}** | Hora: {last_ts}")
        if applied:
            st.success(f"{len(applied)} parâmetro(s) atualizados.")
            with st.expander("Alterações aplicadas", expanded=True):
                for item in applied:
                    st.markdown(f"- `{item}`")
        else:
            st.info("Nenhum parâmetro alterado.")
        if matches:
            with st.expander("Termos reconhecidos"):
                for item in matches:
                    st.markdown(f"- {item}")
        if skipped:
            with st.expander("Termos ignorados"):
                for item in skipped:
                    st.markdown(f"- `{item}`")

    st.markdown("### Estado atual dos parâmetros")
    with st.expander("Ver todas as chaves", expanded=False):
        state_rows = []
        for key in DEFAULT_WIDGET_STATE.keys():
            if key in {"simulation_history", "dark_matter_pdf_bytes",
                       "dark_matter_pdf_chart_warning", "nl_last_input",
                       "nl_last_matches", "nl_last_applied", "nl_last_skipped",
                       "nl_last_timestamp", "latest_contextual_insight", "ai_last_source",
                       "async_history"}:
                continue
            value = st.session_state.get(key)
            if isinstance(value, float):
                value = f"{value:.6g}"
            state_rows.append({"chave": key, "valor": str(value)})
        st.dataframe(pd.DataFrame(state_rows), use_container_width=True, hide_index=True)

# ------------------------- RODAPE ---------------------------
st.divider()
st.markdown(
    "**Notas científicas e limitações**  \n"
    "- O perfil NFW é parametrizado por M200 e c; R200 e rs derivados com H0 = 70 km/s/Mpc.  \n"
    "- Perfil SIDM com núcleo e feedback são parametrizações fenomenológicas.  \n"
    "- Campos numéricos liberados; faixas amplas podem produzir configurações fora do regime validado.  \n"
    "- O assistente IA escreve apenas em `st.session_state`; a física e a numérica permanecem inalteradas.  \n"
    "- Presets calibrados por: Cautun et al. (2020) para Via Láctea; Antlia B para anãs; Umetsu et al. (2020) para aglomerados; Bullet Cluster para σ/m.  \n"
    "- **Numba JIT**: kernels de perfil, integração, densidade, leapfrog e energia compilados via `@njit(cache=True)`.  \n"
    "- **Chunks adaptativos**: `compute_adaptive_chunk` escala com 1/N_partículas.  \n"
    "- **Métricas resumidas**: histórico armazena histograma + momentos (~1 KB) em vez de arrays completos.  \n"
    "- **Spatial index**: KDTree com reconstrução adaptativa (drift > 1% do raio típico).  \n"
    "- **Arquitetura assíncrona**: Celery + Redis quando disponível; fallback automático para `ThreadPoolExecutor` local.  \n"
    "- Sem Numba, o app funciona com numpy puro (fallback automático). Sem Celery/Redis, roda em thread local.  \n"
    "- Para ativar modo distribuído: `docker-compose up -d redis worker` (ver `tasks.py` e `docker-compose.yml`)."
)
