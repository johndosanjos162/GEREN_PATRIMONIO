import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# ============================================================
# DARK MATTER LAB — laboratório didático de matéria escura
# Requisitos: streamlit >= 1.37, numpy, pandas, plotly
# ============================================================

st.set_page_config(
    page_title="Dark Matter Lab",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------- ESTILO -------------------------
st.markdown(
    """
    <style>
      .stApp { background: linear-gradient(145deg,#0a1020 0%,#10192d 58%,#111827 100%); }
      h1,h2,h3 { color:#e8efff !important; }
      [data-testid="stMetric"] { background:rgba(35,49,75,.62); border:1px solid rgba(125,160,220,.22); padding:13px; border-radius:12px; }
      .lab-subtitle { color:#aabbd7; font-size:1.02rem; }
      .lab-card { background:rgba(35,49,75,.48); border:1px solid rgba(125,160,220,.23); border-radius:14px; padding:16px 18px; }
      .muted { color:#aabbd7; font-size:.86rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------- CONSTANTES / UNIDADES --------------------
G_ASTRO = 4.30091e-6  # kpc (km/s)^2 / massa solar
H0_KMS_MPC = 70.0
H0_KMS_KPC = H0_KMS_MPC / 1000.0
RHO_CRIT = 3 * H0_KMS_KPC**2 / (8 * np.pi * G_ASTRO)  # Msun/kpc^3


def nfw_f(x):
    """f(x) = ln(1+x) - x/(1+x), com proteção numérica."""
    x = np.maximum(np.asarray(x, dtype=float), 1e-12)
    return np.log1p(x) - x / (1.0 + x)


def nfw_parameters(m200_msun, concentration):
    """Deriva R200, raio de escala rs e densidade característica rho_s."""
    r200 = (3.0 * m200_msun / (4.0 * np.pi * 200.0 * RHO_CRIT)) ** (1.0 / 3.0)
    rs = r200 / concentration
    rho_s = m200_msun / (4.0 * np.pi * rs**3 * nfw_f(concentration))
    return r200, rs, rho_s


def nfw_density(radius_kpc, rho_s, rs):
    x = np.maximum(np.asarray(radius_kpc, dtype=float) / rs, 1e-10)
    return rho_s / (x * (1.0 + x) ** 2)


def nfw_mass_enclosed(radius_kpc, m200_msun, r200, rs, concentration):
    radius = np.maximum(np.asarray(radius_kpc, dtype=float), 1e-12)
    x = radius / rs
    # O NFW é truncado em R200 para que M(<r>=R200) = M200.
    x_capped = np.minimum(x, concentration)
    return m200_msun * nfw_f(x_capped) / nfw_f(concentration)


def rotation_components(radius_kpc, m200_msun, concentration, m_baryon_msun, a_baryon_kpc):
    r200, rs, rho_s = nfw_parameters(m200_msun, concentration)
    r = np.maximum(np.asarray(radius_kpc, dtype=float), 1e-8)
    m_dm = nfw_mass_enclosed(r, m200_msun, r200, rs, concentration)
    v_dm = np.sqrt(np.maximum(G_ASTRO * m_dm / r, 0.0))
    # Componente bariônica aproximada por um perfil de Hernquist esférico.
    m_b_enclosed = m_baryon_msun * r**2 / (r + a_baryon_kpc) ** 2
    v_b = np.sqrt(np.maximum(G_ASTRO * m_b_enclosed / r, 0.0))
    v_total = np.sqrt(v_dm**2 + v_b**2)
    return v_dm, v_b, v_total, r200, rs, rho_s


def maxwell_speed_pdf(speed, sigma):
    """PDF de Maxwell para o módulo da velocidade, sigma = dispersão por componente."""
    v = np.maximum(np.asarray(speed, dtype=float), 0.0)
    return np.sqrt(2.0 / np.pi) * v**2 / sigma**3 * np.exp(-(v**2) / (2.0 * sigma**2))


def create_initial_tracers(n, seed, g_dimless, concentration, softening):
    """Traçadores orbitando um halo NFW fixo; partículas não interagem entre si."""
    rng = np.random.default_rng(seed)
    # Raio adimensional em unidades de rs.
    radius = np.clip(rng.lognormal(mean=np.log(2.0), sigma=0.38, size=n), 0.15, 0.95 * concentration)
    phi = rng.uniform(0.0, 2.0 * np.pi, size=n)
    positions = np.column_stack((radius * np.cos(phi), radius * np.sin(phi)))
    enclosed_fraction = nfw_f(np.minimum(radius, concentration)) / nfw_f(concentration)
    vc = np.sqrt(np.maximum(g_dimless * enclosed_fraction / np.maximum(radius, 1e-8), 0.0))
    tangential = vc * rng.normal(1.0, 0.08, size=n)
    radial = vc * rng.normal(0.0, 0.12, size=n)
    vx = radial * np.cos(phi) - tangential * np.sin(phi)
    vy = radial * np.sin(phi) + tangential * np.cos(phi)
    velocities = np.column_stack((vx, vy))
    return positions, velocities


def tracer_acceleration(positions, g_dimless, concentration, softening):
    r = np.linalg.norm(positions, axis=1)
    r_safe = np.maximum(r, 1e-10)
    mass_fraction = nfw_f(np.minimum(r_safe, concentration)) / nfw_f(concentration)
    denom = (r_safe**2 + softening**2) ** 1.5
    return -g_dimless * mass_fraction[:, None] * positions / denom[:, None]


def tracer_energy_proxy(positions, velocities, g_dimless, concentration):
    """Energia específica média aproximada; a força suavizada causa pequenos desvios."""
    r = np.maximum(np.linalg.norm(positions, axis=1), 1e-9)
    kinetic = 0.5 * np.sum(velocities**2, axis=1)
    potential = -g_dimless / nfw_f(concentration) * np.log1p(r) / r
    return float(np.mean(kinetic + potential))


def initialise_simulation(params):
    positions, velocities = create_initial_tracers(
        params["n_particles"], params["seed"], params["g_dimless"],
        params["concentration"], params["softening"]
    )
    accelerations = tracer_acceleration(
        positions, params["g_dimless"], params["concentration"], params["softening"]
    )
    st.session_state.sim_positions = positions
    st.session_state.sim_velocities = velocities
    st.session_state.sim_accelerations = accelerations
    st.session_state.sim_step = 0
    st.session_state.sim_snapshots = [positions.copy()]
    st.session_state.sim_times = [0.0]
    st.session_state.sim_energy = [tracer_energy_proxy(positions, velocities, params["g_dimless"], params["concentration"])]
    st.session_state.sim_status = "Pronta para executar"
    st.session_state.sim_params = params.copy()


def integrate_chunk(params, max_chunk=200):
    """Integra um pequeno bloco leapfrog para permitir pausa/retomada."""
    remaining = params["n_steps"] - st.session_state.sim_step
    if remaining <= 0:
        st.session_state.sim_status = "Concluída"
        return
    count = min(max_chunk, remaining)
    pos = st.session_state.sim_positions
    vel = st.session_state.sim_velocities
    acc = st.session_state.sim_accelerations
    dt = params["dt"]
    for _ in range(count):
        vel_half = vel + 0.5 * dt * acc
        pos = pos + dt * vel_half
        acc_new = tracer_acceleration(pos, params["g_dimless"], params["concentration"], params["softening"])
        vel = vel_half + 0.5 * dt * acc_new
        acc = acc_new
        st.session_state.sim_step += 1
        if (st.session_state.sim_step % max(1, params["record_every"]) == 0
                or st.session_state.sim_step == params["n_steps"]):
            st.session_state.sim_snapshots.append(pos.copy())
            st.session_state.sim_times.append(st.session_state.sim_step * dt)
            st.session_state.sim_energy.append(
                tracer_energy_proxy(pos, vel, params["g_dimless"], params["concentration"])
            )
    st.session_state.sim_positions = pos
    st.session_state.sim_velocities = vel
    st.session_state.sim_accelerations = acc
    if st.session_state.sim_step >= params["n_steps"]:
        st.session_state.sim_status = "Concluída"


# ---------------------- CABEÇALHO ---------------------------
st.title("🌌 Dark Matter Lab")
st.markdown(
    '<p class="lab-subtitle">Laboratório científico interativo para explorar halos NFW, '
    'distribuições de velocidades e curvas de rotação galáctica.</p>',
    unsafe_allow_html=True,
)
st.caption("Modelagem astrofísica + visualização Plotly + integração numérica de traçadores")

# ------------------- ESTADO INICIAL DA APP ------------------
for key, value in {
    "sim_status": "Não iniciada",
    "sim_step": 0,
}.items():
    if key not in st.session_state:
        st.session_state[key] = value

# -------------------------- ABAS ----------------------------
tab_model, tab_velocity, tab_rotation, tab_sim = st.tabs([
    "① Modelos teóricos",
    "② Dinâmica e velocidades",
    "③ Curvas e visualizações",
    "④ Simulação e resumo",
])

# ---- ABA 1: MODELO TEÓRICO NFW -----------------------------
with tab_model:
    st.subheader("Perfil de densidade Navarro–Frenk–White (NFW)")
    st.write(
        "Ajuste a massa e a concentração do halo. O perfil NFW descreve um halo escuro idealizado; "
        "a identidade microscópica da matéria escura não é determinada por este perfil macroscópico."
    )
    col_a, col_b = st.columns(2)
    with col_a:
        candidato = st.selectbox(
            "Candidato teórico (rótulo do cenário)",
            ["WIMPs", "Áxions", "Neutrinos estéreis", "Matéria escura genérica"],
            help="Esta seleção documenta a hipótese estudada; não altera automaticamente o perfil NFW.",
        )
        log_m200 = st.slider(
            "Log₁₀ da massa M₂₀₀ (massas solares)", min_value=8.0, max_value=14.0,
            value=12.0, step=0.1,
        )
        concentration = st.slider(
            "Concentração do halo (c)", min_value=2.0, max_value=25.0, value=10.0, step=0.5,
        )
    with col_b:
        log_mbaryon = st.slider(
            "Log₁₀ da massa bariônica (massas solares)", min_value=6.0, max_value=12.0,
            value=10.5, step=0.1,
        )
        a_baryon = st.slider(
            "Escala bariônica a (kpc)", min_value=0.2, max_value=15.0, value=3.0, step=0.1,
        )
        r_plot_max = st.slider(
            "Raio máximo dos gráficos (kpc)", min_value=5.0, max_value=100.0, value=40.0, step=1.0,
        )

    m200 = 10.0**log_m200
    m_baryon = 10.0**log_mbaryon
    r200, rs, rho_s = nfw_parameters(m200, concentration)
    r_density = np.geomspace(0.03, max(r_plot_max, 0.1), 280)
    rho_density = nfw_density(r_density, rho_s, rs)
    rho = rho_density

    met1, met2, met3, met4 = st.columns(4)
    met1.metric("M₂₀₀", f"{m200:.2e} M☉")
    met2.metric("R₂₀₀", f"{r200:.2f} kpc")
    met3.metric("Raio de escala rₛ", f"{rs:.2f} kpc")
    met4.metric("Densidade característica ρₛ", f"{rho_s:.2e} M☉/kpc³")

    fig_nfw = go.Figure()
    fig_nfw.add_trace(go.Scatter(
        x=r_density, y=rho_density, mode="lines", name="Densidade NFW",
        line=dict(width=3, color="#8b7cff"),
    ))
    fig_nfw.update_layout(
        template="plotly_dark", height=420,
        title="Perfil radial de densidade do halo",
        xaxis_title="Raio r (kpc)", yaxis_title="ρ(r) (M☉/kpc³)",
        xaxis_type="log", yaxis_type="log",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
    )
    st.plotly_chart(fig_nfw, use_container_width=True)
    st.markdown(
        f'<div class="lab-card"><b>Cenário selecionado:</b> {candidato}<br>'
        f'<span class="muted">Convenções: M₂₀₀ é a massa dentro do raio cuja densidade média é 200 vezes '
        f'a densidade crítica; H₀ = {H0_KMS_MPC:.0f} km/s/Mpc. Valores cosmológicos fixos são aproximações '
        f'de referência e não controles de redshift.</span></div>',
        unsafe_allow_html=True,
    )

# ---- ABA 2: VELOCIDADES ------------------------------------
with tab_velocity:
    st.subheader("Distribuição estatística de velocidades")
    st.write(
        "O módulo da velocidade de componentes gaussianas independentes segue uma distribuição de Maxwell. "
        "Este modelo simples descreve uma distribuição cinemática idealizada, não uma solução completa de equilíbrio Jeans."
    )
    vc1, vc2, vc3 = st.columns(3)
    with vc1:
        sigma_v = st.slider("Dispersão por componente σᵥ (km/s)", 20.0, 300.0, 120.0, 5.0)
    with vc2:
        n_velocity_samples = st.slider("Amostras de velocidade", 500, 20000, 5000, 500)
    with vc3:
        seed_velocity = st.number_input("Semente para velocidades", 0, 2_147_483_647, 42, 1)

    rng_velocity = np.random.default_rng(int(seed_velocity))
    velocity_vectors = rng_velocity.normal(0.0, sigma_v, size=(int(n_velocity_samples), 3))
    speeds = np.linalg.norm(velocity_vectors, axis=1)
    v_grid = np.linspace(0.0, max(4.5 * sigma_v, float(np.max(speeds)) * 1.03), 350)
    pdf = maxwell_speed_pdf(v_grid, sigma_v)

    fig_velocity = go.Figure()
    fig_velocity.add_trace(go.Histogram(
        x=speeds, histnorm="probability density", nbinsx=45,
        name="Amostras numéricas", opacity=0.62,
        marker_color="#58c4dd",
    ))
    fig_velocity.add_trace(go.Scatter(
        x=v_grid, y=pdf, mode="lines", name="Maxwell teórica",
        line=dict(color="#ffbd69", width=3),
    ))
    fig_velocity.update_layout(
        template="plotly_dark", height=450, barmode="overlay",
        title="Distribuição dos módulos de velocidade",
        xaxis_title="Velocidade (km/s)", yaxis_title="Densidade de probabilidade",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
    )
    st.plotly_chart(fig_velocity, use_container_width=True)

    mean_speed = float(np.mean(speeds))
    rms_speed = float(np.sqrt(np.mean(speeds**2)))
    vcol1, vcol2, vcol3 = st.columns(3)
    vcol1.metric("Velocidade média amostrada", f"{mean_speed:.1f} km/s")
    vcol2.metric("Velocidade RMS", f"{rms_speed:.1f} km/s")
    vcol3.metric("Média teórica de Maxwell", f"{2*np.sqrt(2/np.pi)*sigma_v:.1f} km/s")
    st.caption(
        "A curva laranja é a distribuição de Maxwell para a dispersão por componente σᵥ. "
        "A semente permite reproduzir a mesma amostra."
    )

# ---- ABA 3: CURVAS DE ROTAÇÃO E MAPAS ----------------------
with tab_rotation:
    st.subheader("Curvas de rotação: teoria versus dados")
    st.write(
        "A curva teórica soma em quadratura as contribuições de um halo NFW e de uma componente bariônica "
        "esférica de Hernquist. É possível carregar dados medidos em CSV para comparação direta."
    )
    uploaded = st.file_uploader(
        "Carregar dados observacionais em CSV (opcional)", type=["csv"],
        help="Colunas obrigatórias: radius_kpc e v_obs_kms. Coluna opcional: v_err_kms.",
        key="observational_csv",
    )
    st.caption("Formato esperado: radius_kpc,v_obs_kms,v_err_kms (erro opcional). Sem arquivo, será exibido um conjunto sintético demonstrativo, não dados reais.")

    radii = np.linspace(max(0.15, r_plot_max / 150.0), r_plot_max, 220)
    v_dm, v_baryon, v_total, _, _, _ = rotation_components(
        radii, m200, concentration, m_baryon, a_baryon
    )

    fig_rot = go.Figure()
    fig_rot.add_trace(go.Scatter(
        x=radii, y=v_total, mode="lines", name="Teoria: total",
        line=dict(color="#8b7cff", width=3),
    ))
    fig_rot.add_trace(go.Scatter(
        x=radii, y=v_dm, mode="lines", name="Halo NFW",
        line=dict(color="#58c4dd", width=2, dash="dash"),
    ))
    fig_rot.add_trace(go.Scatter(
        x=radii, y=v_baryon, mode="lines", name="Componente bariônica",
        line=dict(color="#ffbd69", width=2, dash="dot"),
    ))

    obs_label = "Dados sintéticos demonstrativos"
    obs_df = None
    if uploaded is not None:
        try:
            candidate_df = pd.read_csv(uploaded)
            required = {"radius_kpc", "v_obs_kms"}
            if not required.issubset(candidate_df.columns):
                st.error("CSV inválido: inclua as colunas obrigatórias radius_kpc e v_obs_kms.")
            else:
                candidate_df = candidate_df.copy()
                candidate_df["radius_kpc"] = pd.to_numeric(candidate_df["radius_kpc"], errors="coerce")
                candidate_df["v_obs_kms"] = pd.to_numeric(candidate_df["v_obs_kms"], errors="coerce")
                if "v_err_kms" in candidate_df.columns:
                    candidate_df["v_err_kms"] = pd.to_numeric(candidate_df["v_err_kms"], errors="coerce")
                candidate_df = candidate_df.dropna(subset=["radius_kpc", "v_obs_kms"])
                candidate_df = candidate_df[(candidate_df["radius_kpc"] > 0) & (candidate_df["v_obs_kms"] >= 0)]
                if len(candidate_df) == 0:
                    st.error("O arquivo não contém linhas válidas com raio positivo e velocidade não negativa.")
                else:
                    obs_df = candidate_df
                    obs_label = "Dados carregados"
        except Exception as exc:
            st.error(f"Não foi possível ler o CSV: {exc}")

    if obs_df is None:
        rng_obs = np.random.default_rng(2025)
        r_obs = np.linspace(max(0.8, r_plot_max / 20), r_plot_max * 0.9, 14)
        _, _, v_model_obs, _, _, _ = rotation_components(
            r_obs, m200, concentration, m_baryon, a_baryon
        )
        errors = np.maximum(5.0, 0.04 * v_model_obs)
        v_observed = np.maximum(0.0, v_model_obs + rng_obs.normal(0.0, errors))
        obs_df = pd.DataFrame({"radius_kpc": r_obs, "v_obs_kms": v_observed, "v_err_kms": errors})

    marker_kwargs = dict(x=obs_df["radius_kpc"], y=obs_df["v_obs_kms"], mode="markers", name=obs_label,
                         marker=dict(color="#f472b6", size=8, symbol="circle-open", line=dict(width=2)))
    if "v_err_kms" in obs_df.columns and obs_df["v_err_kms"].notna().any():
        marker_kwargs["error_y"] = dict(type="data", array=obs_df["v_err_kms"].fillna(0), visible=True, thickness=1.2)
    fig_rot.add_trace(go.Scatter(**marker_kwargs))
    fig_rot.update_layout(
        template="plotly_dark", height=500,
        title="Curva de rotação galáctica",
        xaxis_title="Raio galactocêntrico (kpc)", yaxis_title="Velocidade circular (km/s)",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
        legend=dict(orientation="h", y=1.12),
    )
    st.plotly_chart(fig_rot, use_container_width=True)

    if uploaded is None:
        st.info("Os pontos exibidos são sintéticos e servem apenas para demonstrar a comparação. Eles não representam observações de uma galáxia específica.")
    else:
        st.success(f"Arquivo processado: {len(obs_df)} pontos de dados válidos.")

    st.markdown("#### Mapa 2D da densidade do halo")
    st.caption("Mapa de corte da densidade volumétrica NFW em função do raio projetado no plano. Não é um mapa de lente gravitacional nem calcula convergência κ.")
    extent = min(max(3.0 * rs, 5.0), r_plot_max)
    grid = np.linspace(-extent, extent, 100)
    xx, yy = np.meshgrid(grid, grid)
    rr = np.sqrt(xx**2 + yy**2)
    zz = np.log10(nfw_density(np.maximum(rr, 0.03), rho_s, rs))
    fig_map = go.Figure(data=go.Heatmap(
        x=grid, y=grid, z=zz, colorscale="Magma", colorbar=dict(title="log₁₀ ρ"),
        hovertemplate="x=%{x:.2f} kpc<br>y=%{y:.2f} kpc<br>log₁₀ ρ=%{z:.2f}<extra></extra>",
    ))
    fig_map.add_shape(type="circle", x0=-a_baryon, y0=-a_baryon, x1=a_baryon, y1=a_baryon,
                      line=dict(color="#58c4dd", dash="dash", width=2))
    fig_map.update_layout(
        template="plotly_dark", height=470,
        title="Corte espacial do halo (círculo tracejado = escala bariônica aproximada)",
        xaxis_title="x (kpc)", yaxis_title="y (kpc)",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
    )
    fig_map.update_yaxes(scaleanchor="x", scaleratio=1)
    st.plotly_chart(fig_map, use_container_width=True)

    with st.expander("Ver tabela dos dados usados no gráfico"):
        st.dataframe(obs_df, use_container_width=True, hide_index=True)
        st.download_button(
            "Baixar dados exibidos em CSV",
            data=obs_df.to_csv(index=False).encode("utf-8"),
            file_name="dados_curva_rotacao.csv", mime="text/csv",
        )

# ---- ABA 4: INTEGRAÇÃO, CONTROLES E RESUMO -----------------
with tab_sim:
    st.subheader("Calculadora e execução da simulação")
    st.write(
        "Integração leapfrog de partículas-traçadoras em um halo NFW fixo. "
        "As partículas seguem o campo gravitacional do halo e não exercem força umas sobre as outras; "
        "portanto, esta etapa é uma aproximação de dinâmica estelar, não uma simulação N-corpos autoconsistente."
    )

    s1, s2, s3 = st.columns(3)
    with s1:
        n_particles = st.slider("Número de partículas-traçadoras", 100, 2000, 1000, 100)
        n_steps = st.slider("Passos de integração", 100, 10000, 10000, 100)
    with s2:
        g_dimless = st.number_input("Intensidade gravitacional adimensional", 0.001, 2.0, 0.05, 0.005, format="%.3f")
        dt = st.number_input("Passo temporal adimensional Δt", 0.0001, 0.1, 0.01, 0.001, format="%.4f")
    with s3:
        sim_seed = st.number_input("Semente aleatória da simulação", 0, 2_147_483_647, 42, 1, key="simulation_seed")
        softening = st.number_input("Suavização numérica ε", 0.001, 0.5, 0.02, 0.005, format="%.3f")

    record_every = st.slider("Registrar estado a cada N passos", 10, 500, 100, 10)
    current_params = {
        "n_particles": int(n_particles),
        "n_steps": int(n_steps),
        "g_dimless": float(g_dimless),
        "dt": float(dt),
        "seed": int(sim_seed),
        "softening": float(softening),
        "concentration": float(concentration),
        "record_every": int(record_every),
    }

    # A configuração do modelo é congelada no início. Se os parâmetros
    # mudarem, a interface pede reinicialização para evitar mistura de cenários.
    have_sim = all(k in st.session_state for k in [
        "sim_positions", "sim_velocities", "sim_accelerations", "sim_params"
    ])
    config_changed = have_sim and st.session_state.sim_params != current_params

    if config_changed:
        st.warning("Os parâmetros foram alterados desde a inicialização. Reinicie a simulação para aplicar a nova configuração.")

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
        initialise_simulation(current_params)
        st.session_state.sim_status = "Pausada"
        st.rerun()

    if start_clicked:
        if not have_sim or config_changed or st.session_state.sim_status in ["Não iniciada", "Concluída"]:
            initialise_simulation(current_params)
        st.session_state.sim_status = "Executando"
        st.rerun()

    if pause_clicked:
        st.session_state.sim_status = "Pausada"
        st.rerun()

    status_color = "#72d6a4" if st.session_state.sim_status == "Concluída" else ("#ffbd69" if st.session_state.sim_status == "Executando" else "#aabbd7")
    st.markdown(
        f'<div class="lab-card"><b>Estado:</b> <span style="color:{status_color}">{st.session_state.sim_status}</span>'
        + (f' · Passo {st.session_state.sim_step:,} / {current_params["n_steps"]:,}' if have_sim else "")
        + "</div>",
        unsafe_allow_html=True,
    )

    # Cada chamada temporal integra um pequeno lote, permitindo que o botão
    # Pausar seja responsivo. Requer Streamlit >= 1.37 (st.fragment).
    @st.fragment(run_every=0.1 if st.session_state.sim_status == "Executando" else None)
    def simulation_live_panel():
        have_state = all(k in st.session_state for k in [
            "sim_positions", "sim_velocities", "sim_accelerations", "sim_params"
        ])
        if not have_state:
            st.info("A simulação ainda não foi inicializada. Ajuste os parâmetros e clique em Iniciar.")
            return

        params = st.session_state.sim_params
        if st.session_state.sim_status == "Executando":
            integrate_chunk(params, max_chunk=200)
            if st.session_state.sim_status == "Concluída":
                st.rerun()

        step = st.session_state.sim_step
        pos_now = st.session_state.sim_positions
        vel_now = st.session_state.sim_velocities
        snapshots = st.session_state.sim_snapshots
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
            m4.metric("Variação da energia proxy", f"{drift:+.3g}%")
        else:
            m4.metric("Variação da energia proxy", "N/D")

        sim_col1, sim_col2 = st.columns([1.1, 1])
        with sim_col1:
            fig_particles = go.Figure()
            fig_particles.add_trace(go.Scattergl(
                x=pos_now[:, 0], y=pos_now[:, 1], mode="markers", name="Traçadores",
                marker=dict(size=4, color=np.linalg.norm(pos_now, axis=1), colorscale="Viridis",
                            showscale=True, colorbar=dict(title="r / rₛ")),
            ))
            fig_particles.update_layout(
                template="plotly_dark", height=430, title="Configuração instantânea (unidades de rₛ)",
                xaxis_title="x / rₛ", yaxis_title="y / rₛ",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
            )
            fig_particles.update_yaxes(scaleanchor="x", scaleratio=1)
            st.plotly_chart(fig_particles, use_container_width=True)
        with sim_col2:
            fig_e = go.Figure()
            fig_e.add_trace(go.Scatter(x=times, y=energies, mode="lines+markers", name="Energia específica média"))
            fig_e.update_layout(
                template="plotly_dark", height=430, title="Diagnóstico da energia",
                xaxis_title="Tempo adimensional", yaxis_title="Energia específica (proxy)",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(8,14,28,.8)",
            )
            st.plotly_chart(fig_e, use_container_width=True)
        if st.session_state.sim_status == "Executando":
            st.caption("Integração em lotes automáticos de 200 passos. Use Pausar para interromper entre lotes.")
        elif st.session_state.sim_status == "Concluída":
            st.success("Integração concluída.")
        else:
            st.caption("Execução pausada ou aguardando início. Use Iniciar / continuar para avançar.")

        # Permite exportar o resumo temporal mesmo antes do fim.
        df_history = pd.DataFrame({
            "tempo_adimensional": times,
            "energia_especifica_media_proxy": energies,
        })
        st.download_button(
            "⬇️ Exportar histórico da simulação (CSV)",
            data=df_history.to_csv(index=False).encode("utf-8"),
            file_name="historico_simulacao.csv", mime="text/csv",
            key="download_sim_history",
        )

    simulation_live_panel()

    st.markdown("#### Resumo dos parâmetros ativos")
    df_active = pd.DataFrame({
        "Parâmetro": ["Candidato selecionado", "M₂₀₀ (M☉)", "Concentração c", "Partículas-traçadoras", "Passos", "G adimensional", "Δt", "Semente", "Suavização ε"],
        "Valor": [candidato, f"{m200:.4e}", f"{concentration:.2f}", n_particles, n_steps, g_dimless, dt, sim_seed, softening],
    })
    st.dataframe(df_active, use_container_width=True, hide_index=True)

# ------------------------- RODAPÉ ---------------------------
st.divider()
st.markdown(
    "**Notas científicas e limitações**  \n"
    "• NFW é um perfil empírico de halo; WIMPs, áxions e neutrinos estéreis são candidatos microscópicos distintos.  \n"
    "• Curvas observacionais só são reais quando fornecidas por um conjunto de dados externo via CSV. O conjunto incorporado é sintético e demonstrativo.  \n"
    "• O mapa de densidade é um corte volumétrico 2D; não é um cálculo de lente gravitacional.  \n"
    "• A integração usa traçadores em um potencial NFW fixo, com unidades adimensionais para a dinâmica. Não substitui simulações cosmológicas ou N-corpos autoconsistentes.  \n"
    "• O diagnóstico de energia é aproximado quando há suavização gravitacional."
)
