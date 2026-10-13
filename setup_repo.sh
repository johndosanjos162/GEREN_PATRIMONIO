#!/usr/bin/env bash
# ============================================================
# setup_repo.sh — cria a estrutura completa do Dark Matter Lab
# ============================================================
#
# Uso:
#   chmod +x setup_repo.sh
#   ./setup_repo.sh                          # cria em ./dark-matter-lab
#   ./setup_repo.sh minha-pasta              # cria em ./minha-pasta
#   GH_USER=meu-user ./setup_repo.sh         # define usuário GitHub
#
# Pré-requisitos:
#   - git instalado
#   - gh (GitHub CLI) instalado e autenticado: `gh auth login`
# ============================================================

set -euo pipefail

PROJECT_NAME="${1:-dark-matter-lab}"
GH_USER="${GH_USER:-$(gh api user --jq .login 2>/dev/null || echo "")}"
REPO_VISIBILITY="${REPO_VISIBILITY:-public}"

if [ -z "$GH_USER" ]; then
    echo "❌ GitHub CLI não autenticado. Rode: gh auth login"
    exit 1
fi

echo "📦 Criando estrutura em: ./$PROJECT_NAME"
mkdir -p "$PROJECT_NAME"
cd "$PROJECT_NAME"

# ------------------------------------------------------------
# 1. Diretórios
# ------------------------------------------------------------
mkdir -p .github/workflows
mkdir -p .github/ISSUE_TEMPLATE
mkdir -p .streamlit
mkdir -p app
mkdir -p worker
mkdir -p tests
mkdir -p docs/SCREENSHOTS
mkdir -p data/examples

# ------------------------------------------------------------
# 2. Arquivos Python — app/
# ------------------------------------------------------------
cat > app/__init__.py << 'EOF'
"""Dark Matter Lab — pacote principal."""
__version__ = "1.0.0"
EOF

cat > app/kernels.py << 'PYEOF'
"""Kernels Numba JIT compartilhados entre UI e worker."""
from __future__ import annotations

import numpy as np

try:
    from numba import njit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

    def njit(func=None, **kwargs):
        if func is None:
            return lambda f: f
        return func


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
        out[i] = shape * (1.0 - feedback_strength * np.exp(-xi / feedback_scale_x))
    return out


@njit(cache=True)
def _integrate_profile_core(x_grid, shape):
    n = x_grid.shape[0]
    integrand = x_grid ** 2 * shape
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
    norm = max(cumulative[n - 1], 1e-30)
    for i in range(n):
        mass_fraction[i] = min(max(cumulative[i] / norm, 0.0), 1.0)
    kernel = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        kernel[i] = (integrand[i] / norm) / x_grid[i]
    kernel[0] = kernel[1] if n > 1 else 0.0
    outer = np.zeros(n, dtype=np.float64)
    acc = 0.0
    for i in range(n - 2, -1, -1):
        dx = x_grid[i + 1] - x_grid[i]
        acc += 0.5 * (kernel[i + 1] + kernel[i]) * dx
        outer[i] = acc
    for i in range(n):
        xs = x_grid[i] if x_grid[i] > 1e-8 else 1e-8
        potential[i] = -(mass_fraction[i] / xs + outer[i])
    potential[0] = potential[1]
    return mass_fraction, potential


@njit(cache=True)
def _leapfrog_batch(pos, vel, acc, mass_x, mass_frac, g, softening, dt, n_inner):
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
            x = pos[i, 0]; y = pos[i, 1]
            r = np.sqrt(x * x + y * y)
            r_safe = r if r > 1e-10 else 1e-10
            enc = np.interp(r_safe, mass_x, mass_frac)
            denom = (r_safe * r_safe + eps2) ** 1.5
            factor = -g * enc / denom
            acc[i, 0] = factor * x
            acc[i, 1] = factor * y
        for i in range(n):
            vel[i, 0] += 0.5 * dt * acc[i, 0]
            vel[i, 1] += 0.5 * dt * acc[i, 1]
    return pos, vel, acc


@njit(cache=True)
def _energy_proxy_batch(pos, vel, g, mass_x, potential_x):
    n = pos.shape[0]
    r_max = mass_x[-1]
    total = 0.0
    for i in range(n):
        x = pos[i, 0]; y = pos[i, 1]
        r = np.sqrt(x * x + y * y)
        r_safe = r if r > 1e-8 else 1e-8
        kinetic = 0.5 * (vel[i, 0] ** 2 + vel[i, 1] ** 2)
        phi = -1.0 / r_safe if r_safe > r_max else np.interp(r_safe, mass_x, potential_x)
        total += kinetic + g * phi
    return total / n
PYEOF

cat > app/orchestrator.py << 'PYEOF'
"""Orquestração assíncrona: Celery+Redis ou ThreadPool local."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

ASYNC_MODE = False
REDIS_CLIENT = None
celery_app = None
run_simulation = None

try:
    import redis as _redis
    from worker.celery_app import celery_app as _ca
    from worker.tasks import run_simulation as _rs
    from worker.celery_app import REDIS_URL as _url
    _c = _redis.Redis.from_url(_url)
    _c.ping()
    REDIS_CLIENT = _c
    celery_app = _ca
    run_simulation = _rs
    ASYNC_MODE = True
except Exception:
    pass

_LOCAL_EXECUTOR = ThreadPoolExecutor(max_workers=1)
_LOCAL_TASKS: dict = {}


def submit_simulation_async(params: dict, seed: int) -> str:
    if ASYNC_MODE and run_simulation is not None:
        return run_simulation.delay(params, seed).id
    from app.simulation import run_simulation_local
    fut = _LOCAL_EXECUTOR.submit(run_simulation_local, params, seed)
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
                return {"status": "Executando", "progress": float(meta.get("progress", 0.0)),
                        "step": int(meta.get("step", 0)), "history": [],
                        "last_summary": meta.get("last_summary", {})}
            if res.state == "SUCCESS":
                return {"status": "Concluida", "progress": 100.0, **(res.result or {})}
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
PYEOF

cat > app/simulation.py << 'PYEOF'
"""Execução local da simulação (usada como fallback)."""
from __future__ import annotations

import time
from datetime import datetime

import numpy as np

from app.kernels import (
    _halo_shape_numba, _integrate_profile_core,
    _leapfrog_batch, _energy_proxy_batch,
)


def compute_adaptive_chunk(n, target_ops=50_000):
    return max(5, min(500, int(target_ops / max(n, 1))))


def build_profile_lookup(concentration, model, core_x, fb, fb_scale_x, grid_size=3000):
    c = max(float(concentration), 1e-3)
    x = np.unique(np.concatenate(([0.0], np.geomspace(1e-6, c, grid_size))))
    use_sidm = model.upper().startswith("SIDM")
    shape = _halo_shape_numba(x, use_sidm, core_x, fb, fb_scale_x)
    mass, potential = _integrate_profile_core(x, shape)
    return x, mass, potential


def summarize(pos, vel, n_bins=50):
    r = np.linalg.norm(pos, axis=1)
    v2 = np.sum(vel ** 2, axis=1)
    hist, edges = np.histogram(r, bins=n_bins, range=(0.0, max(float(np.max(r)), 1e-6)))
    return {
        "r_hist": hist.astype(np.int32).tolist(),
        "r_hist_edges": edges.astype(np.float32).tolist(),
        "r_mean": float(np.mean(r)), "r_rms": float(np.sqrt(np.mean(r ** 2))),
        "r_max": float(np.max(r)), "r_p50": float(np.percentile(r, 50)),
        "r_p90": float(np.percentile(r, 90)),
        "v_rms": float(np.sqrt(np.mean(v2))),
    }


def run_simulation_local(params, seed):
    rng = np.random.default_rng(seed)
    n, n_steps = int(params["n_particles"]), int(params["n_steps"])
    dt, g, eps = float(params["dt"]), float(params["g_dimless"]), float(params["softening"])

    mass_x, mass_frac, pot_x = build_profile_lookup(
        params["concentration"], params["halo_model"],
        params["core_radius_over_rs"], params["feedback_strength"],
        params["feedback_scale_over_rs"],
    )
    radius = np.clip(rng.lognormal(np.log(2.0), 0.38, size=n), 0.15,
                     0.95 * float(params["concentration"]))
    phi = rng.uniform(0.0, 2.0 * np.pi, size=n)
    pos = np.column_stack((radius * np.cos(phi), radius * np.sin(phi)))
    enc = np.interp(radius, mass_x, mass_frac, left=0.0, right=1.0)
    vc = np.sqrt(np.maximum(g * enc / np.maximum(radius, 1e-8), 0.0))
    vt = vc * rng.normal(1.0, 0.08, size=n)
    vr = vc * rng.normal(0.0, 0.12, size=n)
    vel = np.column_stack((vr * np.cos(phi) - vt * np.sin(phi),
                            vr * np.sin(phi) + vt * np.cos(phi)))
    acc = np.empty_like(pos)

    chunk = compute_adaptive_chunk(n)
    e0 = float(_energy_proxy_batch(pos, vel, g, mass_x, pot_x))
    record_every = max(1, int(params.get("record_every", 100)))
    history = [dict(summarize(pos, vel), step=0, time=0.0, energy=e0,
                     energy_initial=e0, energy_drift=0.0, status="Executando",
                     recorded_at=datetime.now().isoformat(timespec="seconds"))]

    step_done = 0
    t0 = time.time()
    while step_done < n_steps:
        count = min(chunk, n_steps - step_done)
        pos, vel, acc = _leapfrog_batch(pos, vel, acc, mass_x, mass_frac, g, eps, dt, count)
        step_done += count
        if step_done % record_every < count or step_done == n_steps:
            e = float(_energy_proxy_batch(pos, vel, g, mass_x, pot_x))
            s = summarize(pos, vel)
            s.update(step=int(step_done), time=float(step_done * dt), energy=e,
                     energy_initial=e0,
                     energy_drift=float(100.0 * (e - e0) / abs(e0)) if abs(e0) > 1e-12 else 0.0,
                     status="Executando",
                     recorded_at=datetime.now().isoformat(timespec="seconds"))
            history.append(s)

    return {"status": "Concluida", "n_steps": n_steps, "n_particles": n,
            "elapsed_seconds": time.time() - t0, "history": history}
PYEOF

# ------------------------------------------------------------
# 3. Worker Celery
# ------------------------------------------------------------
cat > worker/__init__.py << 'EOF'
"""Dark Matter Lab — worker Celery."""
EOF

cat > worker/celery_app.py << 'PYEOF'
"""Configuração do Celery."""
from __future__ import annotations

import os

try:
    from celery import Celery
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    Celery = None

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

if CELERY_AVAILABLE:
    celery_app = Celery("dark_matter_lab", broker=REDIS_URL, backend=REDIS_URL)
    celery_app.conf.update(
        task_serializer="pickle",
        result_serializer="pickle",
        accept_content=["pickle", "json"],
        result_expires=3600,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        task_track_started=True,
    )
else:
    celery_app = None
PYEOF

cat > worker/tasks.py << 'PYEOF'
"""Task Celery principal."""
from __future__ import annotations

from datetime import datetime

import numpy as np

from app.kernels import (
    _halo_shape_numba, _integrate_profile_core,
    _leapfrog_batch, _energy_proxy_batch,
)
from app.simulation import compute_adaptive_chunk, summarize, build_profile_lookup
from worker.celery_app import celery_app, CELERY_AVAILABLE

if not CELERY_AVAILABLE:
    def run_simulation(params, seed):
        from app.simulation import run_simulation_local
        return run_simulation_local(params, seed)
else:
    @celery_app.task(bind=True, name="run_simulation")
    def run_simulation(self, params, seed):
        rng = np.random.default_rng(seed)
        n, n_steps = int(params["n_particles"]), int(params["n_steps"])
        dt, g, eps = float(params["dt"]), float(params["g_dimless"]), float(params["softening"])

        mass_x, mass_frac, pot_x = build_profile_lookup(
            params["concentration"], params["halo_model"],
            params["core_radius_over_rs"], params["feedback_strength"],
            params["feedback_scale_over_rs"],
        )
        radius = np.clip(rng.lognormal(np.log(2.0), 0.38, size=n), 0.15,
                         0.95 * float(params["concentration"]))
        phi = rng.uniform(0.0, 2.0 * np.pi, size=n)
        pos = np.column_stack((radius * np.cos(phi), radius * np.sin(phi)))
        enc = np.interp(radius, mass_x, mass_frac, left=0.0, right=1.0)
        vc = np.sqrt(np.maximum(g * enc / np.maximum(radius, 1e-8), 0.0))
        vt = vc * rng.normal(1.0, 0.08, size=n)
        vr = vc * rng.normal(0.0, 0.12, size=n)
        vel = np.column_stack((vr * np.cos(phi) - vt * np.sin(phi),
                                vr * np.sin(phi) + vt * np.cos(phi)))
        acc = np.empty_like(pos)

        chunk = compute_adaptive_chunk(n)
        e0 = float(_energy_proxy_batch(pos, vel, g, mass_x, pot_x))
        record_every = max(1, int(params.get("record_every", 100)))
        history = [dict(summarize(pos, vel), step=0, time=0.0, energy=e0,
                         energy_initial=e0, energy_drift=0.0, status="Executando",
                         recorded_at=datetime.now().isoformat(timespec="seconds"))]

        step_done = 0
        while step_done < n_steps:
            count = min(chunk, n_steps - step_done)
            pos, vel, acc = _leapfrog_batch(pos, vel, acc, mass_x, mass_frac, g, eps, dt, count)
            step_done += count
            if step_done % record_every < count or step_done == n_steps:
                e = float(_energy_proxy_batch(pos, vel, g, mass_x, pot_x))
                s = summarize(pos, vel)
                s.update(step=int(step_done), time=float(step_done * dt), energy=e,
                         energy_initial=e0,
                         energy_drift=float(100.0 * (e - e0) / abs(e0)) if abs(e0) > 1e-12 else 0.0,
                         status="Executando",
                         recorded_at=datetime.now().isoformat(timespec="seconds"))
                history.append(s)
                self.update_state(state="PROGRESS", meta={
                    "step": step_done, "n_steps": n_steps,
                    "progress": 100.0 * step_done / n_steps,
                    "last_summary": s,
                })

        final = summarize(pos, vel)
        e_final = float(_energy_proxy_batch(pos, vel, g, mass_x, pot_x))
        final.update(step=n_steps, time=float(n_steps * dt), energy=e_final,
                     energy_initial=e0,
                     energy_drift=float(100.0 * (e_final - e0) / abs(e0)) if abs(e0) > 1e-12 else 0.0,
                     status="Concluida",
                     recorded_at=datetime.now().isoformat(timespec="seconds"))
        history.append(final)
        return {"status": "Concluida", "n_steps": n_steps, "n_particles": n,
                "history": history}
PYEOF

# ------------------------------------------------------------
# 4. Testes
# ------------------------------------------------------------
cat > tests/__init__.py << 'EOF'
EOF

cat > tests/test_kernels.py << 'PYEOF'
import numpy as np
from app.kernels import _halo_shape_numba, _integrate_profile_core


def test_halo_shape_matches_numpy():
    x = np.linspace(0.01, 10.0, 500)
    core_x, fb, scale = 0.1, 0.25, 0.15
    shape_nb = _halo_shape_numba(x, True, core_x, fb, scale)
    x_safe = np.maximum(x, 1e-10)
    shape_np = 1.0 / ((x_safe + core_x) * (1.0 + x_safe) ** 2)
    shape_np *= 1.0 - fb * np.exp(-x / scale)
    np.testing.assert_allclose(shape_nb, shape_np, rtol=1e-13)


def test_mass_conservation():
    x = np.unique(np.concatenate(([0.0], np.geomspace(1e-6, 10.0, 3000))))
    shape = _halo_shape_numba(x, False, 0.15, 0.0, 0.15)
    mass, _ = _integrate_profile_core(x, shape)
    assert abs(mass[-1] - 1.0) < 1e-12
PYEOF

cat > tests/test_simulation.py << 'PYEOF'
from app.simulation import run_simulation_local


def test_small_simulation_runs():
    params = {
        "n_particles": 100, "n_steps": 50, "dt": 0.01,
        "g_dimless": 0.05, "softening": 0.02,
        "concentration": 9.4, "halo_model": "NFW",
        "core_radius_over_rs": 0.1, "feedback_strength": 0.0,
        "feedback_scale_over_rs": 0.15, "record_every": 10,
    }
    result = run_simulation_local(params, seed=42)
    assert result["status"] == "Concluida"
    assert result["n_steps"] == 50
    assert len(result["history"]) >= 1
PYEOF

# ------------------------------------------------------------
# 5. App.py (entry point minimalista)
# ------------------------------------------------------------
cat > App.py << 'PYEOF'
"""Entry point do Streamlit. A lógica principal vive em app/ui.py."""
# Placeholder: substitua por `from app.ui import main; main()`
import streamlit as st
st.title("🌌 Dark Matter Lab")
st.info("Substitua este App.py pelo conteúdo completo da UI (app/ui.py).")
PYEOF

# ------------------------------------------------------------
# 6. .github/workflows
# ------------------------------------------------------------
cat > .github/workflows/ci.yml << 'YMLEOF'
name: CI
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/ -v
YMLEOF

# ------------------------------------------------------------
# 7. Arquivos de configuração
# ------------------------------------------------------------
cat > .streamlit/config.toml << 'TOMLEOF'
[theme]
base = "dark"
primaryColor = "#8b7cff"
backgroundColor = "#0a1020"
secondaryBackgroundColor = "#10192d"
textColor = "#e8efff"

[server]
headless = true
maxUploadSize = 50

[browser]
gatherUsageStats = false
TOMLEOF

cat > .streamlit/secrets.toml.example << 'TOMLEOF'
# Copie para secrets.toml (NÃO versione)
# REDIS_URL = "redis://default:senha@host:porta/0"
TOMLEOF

cat > requirements.txt << 'TXTEOF'
numpy>=1.24,<2.2
scipy>=1.10
pandas>=2.0,<2.3
plotly>=5.18,<6.0
streamlit>=1.30,<1.40
kaleido==0.2.1
fpdf2>=2.7,<3.0
numba>=0.58,<0.62
llvmlite>=0.41,<0.44
celery>=5.3,<5.5
redis>=5.0,<6.0
TXTEOF

cat > requirements-dev.txt << 'TXTEOF'
-r requirements.txt
pytest>=7.4
pytest-cov>=4.1
ruff>=0.1
black>=23.12
TXTEOF

cat > .gitignore << 'GIEOF'
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
env/
__numba_cache__/
*.nbi
*.nbc
.streamlit/secrets.toml
.env
.vscode/
.idea/
.DS_Store
.pytest_cache/
.coverage
htmlcov/
*.pdf
*.png
!docs/SCREENSHOTS/*.png
GIEOF

cat > .dockerignore << 'DIEOF'
__pycache__
__numba_cache__
.git
.github
.venv
venv
.pytest_cache
docs
tests
*.md
!README.md
.streamlit/secrets.toml
.env
DIEOF

cat > .env.example << 'ENVEOF'
REDIS_URL=redis://localhost:6379/0
CELERY_CONCURRENCY=4
STREAMLIT_SERVER_PORT=8501
ENVEOF

cat > Dockerfile << 'DOCKEOF'
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY worker/ ./worker/
COPY App.py .
COPY .streamlit/ ./.streamlit/
ENV NUMBA_CACHE_DIR=/app/__numba_cache__
RUN mkdir -p /app/__numba_cache__
EXPOSE 8501
CMD ["streamlit", "run", "App.py", "--server.port=8501", "--server.address=0.0.0.0"]
DOCKEOF

cat > docker-compose.yml << 'DCEOF'
version: "3.9"
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: [redis_data:/data]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 5
  worker:
    build: .
    command: celery -A worker.celery_app worker --loglevel=info --concurrency=4
    depends_on:
      redis: {condition: service_healthy}
    environment:
      - REDIS_URL=redis://redis:6379/0
    volumes: [numba_cache:/app/__numba_cache__]
  streamlit:
    build: .
    command: streamlit run App.py --server.port=8501 --server.address=0.0.0.0
    depends_on:
      redis: {condition: service_healthy}
    environment:
      - REDIS_URL=redis://redis:6379/0
    ports: ["8501:8501"]
volumes:
  redis_data:
  numba_cache:
DCEOF

cat > LICENSE << 'LICE'
MIT License

Copyright (c) 2026 Dark Matter Lab Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
LICE

cat > README.md << 'READEOF'
# 🌌 Dark Matter Lab

[![CI](https://github.com/USER/dark-matter-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/USER/dark-matter-lab/actions)

Laboratório interativo para estudo de **matéria escura** via halos NFW/SIDM,
dinâmica estelar, feedback bariônico e simulações numéricas assíncronas.

## ✨ Funcionalidades

- **6 abas** cobrindo teoria, curvas de rotação, feedback e simulação
- **Assistente IA** em linguagem natural (PT/EN)
- **Kernels Numba JIT** para física e integração
- **Arquitetura assíncrona** (Celery + Redis, com fallback ThreadPool)
- **Relatório PDF** com síntese científica

## 🚀 Instalação

```bash
git clone https://github.com/USER/dark-matter-lab.git
cd dark-matter-lab
pip install -r requirements.txt
streamlit run App.py
