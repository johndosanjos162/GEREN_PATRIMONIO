
import streamlit as st
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================================
# LABORATÓRIO DE MATÉRIA ESCURA
# Aplicação educacional em um único arquivo: app.py
# Dependências: streamlit, numpy, plotly
# ==========================================================

st.set_page_config(
    page_title="Dark Matter Lab",
    page_icon="🌌",
    layout="wide"
)

# Constantes e unidades
G = 4.30091e-6       # kpc (km/s)^2 / massa solar
C_KMS = 299792.458   # km/s
KPC_M = 3.085677581e19

# ------------------------- VISUAL -------------------------

st.markdown("""
<style>
.stApp {
    background: linear-gradient(145deg,#080d1b,#111a31,#080e1c);
    color: #eaf1ff;
}
[data-testid="stSidebar"] {
    background: #0b1325;
    border-right: 1px solid #293c61;
}
.block-container {
    max-width: 1450px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}
h1,h2,h3 {color:#eaf2ff !important;}
[data-testid="stMetric"] {
    background: rgba(25,39,67,.85);
    border: 1px solid #344b75;
    border-radius: 13px;
    padding: 15px;
}
[data-testid="stMetricValue"] {color:#7edcff;}
[data-testid="stMetricLabel"] {color:#b9cce9;}
.stTabs [data-baseweb="tab"] {
    background: #15223b;
    border-radius: 8px 8px 0 0;
}
</style>
""", unsafe_allow_html=True)


def sci(x, unit=""):
    return f"{x:.3e} {unit}".strip()


def chart_style(fig, height=400):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(9,16,32,.8)",
        font=dict(color="#e2ebff"),
        margin=dict(l=20, r=20, t=55, b=25),
        height=height
    )
    return fig


def rotation_model(r, rho0, rc, disk_scale, disk_mass, bulge_mass):
    """
    Modelo didático:
    - halo pseudo-isotérmico
    - disco exponencial aproximado
    - componente central simplificada

    r em kpc, rho0 em massa solar/kpc³,
    massas em massas solares.
    """
    x = np.maximum(r / rc, 1e-8)

    # Massa do halo pseudo-isotérmico
    m_halo = 4 * np.pi * rho0 * rc**3 * (x - np.arctan(x))
    v_halo_sq = G * m_halo / np.maximum(r, 1e-5)

    # Aproximação esférica da massa bariônica acumulada
    # Não é uma solução exata para um disco fino.
    enclosed_disk = disk_mass * (
        1 - (1 + r / disk_scale) * np.exp(-r / disk_scale)
    )
    enclosed_bulge = bulge_mass * r**2 / (
        r**2 + 0.4**2
    )

    v_disk_sq = G * enclosed_disk / np.maximum(r, 1e-5)
    v_bulge_sq = G * enclosed_bulge / np.maximum(r, 1e-5)

    v_total = np.sqrt(np.maximum(
        v_halo_sq + v_disk_sq + v_bulge_sq, 0
    ))
    v_baryon = np.sqrt(np.maximum(
        v_disk_sq + v_bulge_sq, 0
    ))
    v_halo = np.sqrt(np.maximum(v_halo_sq, 0))

    return v_total, v_baryon, v_halo


def make_lensing_map(seed, concentration, noise):
    """
    Mapa sintético de convergência gravitacional.
    Não é um mapa observado nem uma reconstrução de lente real.
    """
    rng = np.random.default_rng(seed)
    n = 150
    x = np.linspace(-3, 3, n)
    y = np.linspace(-3, 3, n)
    X, Y = np.meshgrid(x, y)
    K = np.zeros_like(X)

    centers = [
        (-0.8, -0.3, 1.0),
        (0.7, 0.6, 0.75),
        (0.2, -1.1, 0.55),
        (-1.3, 1.2, 0.35)
    ]

    for cx, cy, amp in centers:
        sigma = 0.12 + 0.5 / max(concentration, 0.2)
        K += amp * np.exp(
            -((X - cx)**2 + (Y - cy)**2) / (2 * sigma**2)
        )

    K += noise * rng.normal(size=K.shape)
    K = np.maximum(K, 0)
    return X, Y, K


def simulate_gravity(seed, n_particles, steps, strength, dt):
    """
    Simulação newtoniana 2D de partículas com gravidade suavizada.
    Unidades adimensionais: não representa diretamente o Universo real.
    """
    rng = np.random.default_rng(seed)

    # Duas pequenas sobredensidades iniciais
    n1 = n_particles // 2
    n2 = n_particles - n1

    p1 = rng.normal(loc=(-0.8, 0.1), scale=0.38, size=(n1, 2))
    p2 = rng.normal(loc=(0.8, -0.1), scale=0.38, size=(n2, 2))
    pos = np.vstack([p1, p2])

    vel = rng.normal(0, 0.035, size=(n_particles, 2))
    masses = np.ones(n_particles) / n_particles
    softening = 0.08

    def acceleration(p):
        delta = p[None, :, :] - p[:, None, :]
        dist2 = np.sum(delta**2, axis=2) + softening**2
        inv_r3 = dist2**(-1.5)
        np.fill_diagonal(inv_r3, 0)

        # Força gravitacional newtoniana suavizada
        a = strength * np.sum(
            delta * inv_r3[:, :, None] * masses[None, :, None],
            axis=1
        )
        return a

    history = [pos.copy()]
    a = acceleration(pos)

    for i in range(steps):
        # Integração leapfrog simplificada
        pos_new = pos + vel * dt + 0.5 * a * dt**2
        a_new = acceleration(pos_new)
        vel = vel + 0.5 * (a + a_new) * dt
        pos = pos_new
        a = a_new

        # Impede que o exemplo numérico fique fora de escala
        pos = np.clip(pos, -5, 5)

        if i % max(1, steps // 8) == 0:
            history.append(pos.copy())

    return history, pos


# -------------------------- CABEÇALHO ----------------------

st.title("🌌 DARK MATTER LAB")
st.subheader("Laboratório interativo de matéria escura e cosmologia")
st.caption(
    "Modelos de partículas • Dinâmica galáctica • Lentes gravitacionais "
    "• Formação de estruturas"
)

with st.sidebar:
    st.header("🔭 Centro científico")
    st.info("Objetivo: explorar modelos e efeitos gravitacionais da matéria escura.")
    st.markdown("**Módulos**")
    st.write("01 — Modelos teóricos")
    st.write("02 — Observações e lentes")
    st.write("03 — Estrutura cósmica")
    st.divider()
    st.caption(
        "Resultados de modelos simplificados. "
        "Não substituem dados observacionais ou simulações cosmológicas profissionais."
    )

tab1, tab2, tab3 = st.tabs([
    "🧪 Modelos teóricos",
    "🔭 Observações astronômicas",
    "🌌 Simulações cosmológicas"
])

# ==========================================================
# ABA 1 — MODELOS TEÓRICOS
# ==========================================================

with tab1:
    st.header("01 · Modelos teóricos de matéria escura")

    model = st.radio(
        "Selecione a família de candidatos",
        ["WIMPs", "Áxions"],
        horizontal=True
    )

    st.write(
        "Os controles abaixo servem para explorar parâmetros ilustrativos. "
        "Eles não calculam, por si sós, a abundância cosmológica observada."
    )

    if model == "WIMPs":
        left, right = st.columns(2)

        with left:
            mass_gev = st.slider(
                "Massa da partícula (GeV/c²)",
                min_value=1.0, max_value=10000.0,
                value=100.0, step=1.0
            )
            cross_section = st.number_input(
                "Seção de choque de aniquilação ⟨σv⟩ (cm³/s)",
                min_value=1e-32, max_value=1e-20,
                value=3e-26, format="%.2e"
            )

        with right:
            density = st.number_input(
                "Densidade local adotada (GeV/cm³)",
                min_value=0.001, max_value=5.0,
                value=0.3, step=0.05
            )
            fraction = st.slider(
                "Fração hipotética da matéria escura (%)",
                0.0, 100.0, 100.0, 1.0
            )

        st.markdown("### Indicadores do modelo")

        a, b, c = st.columns(3)
        a.metric("Massa selecionada", f"{mass_gev:g} GeV/c²")
        b.metric("Seção de choque", f"{cross_section:.2e} cm³/s")
        c.metric("Fração hipotética", f"{fraction:.0f}%")

        rho_effective = density * fraction / 100
        number_density = rho_effective / mass_gev

        st.metric(
            "Densidade numérica estimada",
            sci(number_density, "partículas/cm³")
        )

        st.markdown("### Relações físicas")

        st.latex(r"n_\chi = \frac{\rho_\chi}{m_\chi}")
        st.latex(
            r"\Gamma_{\mathrm{ann}} \propto "
            r"\langle\sigma v\rangle n_\chi^2"
        )

        st.caption(
            "A taxa de aniquilação por volume depende também da convenção "
            "de contagem de pares e da distribuição espacial. A expressão "
            "acima mostra apenas a dependência proporcional."
        )

        st.info(
            "A seção de choque inserida não é uma medição automática nem "
            "uma exclusão experimental. Sua compatibilidade depende do "
            "modelo, do canal de aniquilação e dos dados observacionais."
        )

    else:
        left, right = st.columns(2)

        with left:
            axion_mass = st.number_input(
                "Massa do áxion (eV/c²)",
                min_value=1e-12, max_value=1e-2,
                value=1e-5, format="%.2e"
            )
            coupling = st.number_input(
                "Acoplamento efetivo ilustrativo (GeV⁻¹)",
                min_value=1e-20, max_value=1e-5,
                value=1e-12, format="%.2e"
            )

        with right:
            axion_fraction = st.slider(
                "Fração hipotética da matéria escura (%)",
                0.0, 100.0, 100.0, 1.0
            )
            local_rho = st.number_input(
                "Densidade local de referência (GeV/cm³)",
                min_value=0.001, max_value=5.0,
                value=0.3, step=0.05
            )

        a, b, c = st.columns(3)
        a.metric("Massa do áxion", f"{axion_mass:.2e} eV/c²")
        b.metric("Acoplamento inserido", f"{coupling:.2e} GeV⁻¹")
        c.metric("Fração hipotética", f"{axion_fraction:.0f}%")

        rho_axion = local_rho * axion_fraction / 100
        mass_gev_axion = axion_mass * 1e-9
        n_axion = rho_axion / mass_gev_axion

        st.metric(
            "Densidade numérica estimada",
            sci(n_axion, "partículas/cm³")
        )

        st.markdown("### Conceito físico")

        st.latex(r"n_a \simeq \frac{\rho_a}{m_a c^2}")
        st.markdown(
            "Em unidades naturais, com massa expressa em unidades de "
            "energia, usa-se frequentemente a forma simplificada "
            r"\(n_a \simeq \rho_a/m_a\)."
        )

        st.info(
            "O acoplamento dos áxions depende do modelo específico. "
            "O valor inserido não permite calcular sozinho a probabilidade "
            "de detecção sem especificar o experimento e sua resposta."
        )

    st.divider()
    st.markdown("### O que esses parâmetros significam?")
    st.markdown("""
    - **Massa:** determina a escala de energia e influencia a densidade
      numérica para uma densidade de massa fixada.
    - **Interação:** influencia os processos de produção, aniquilação
      ou conversão, dependendo do candidato.
    - **Fração de matéria escura:** permite explorar cenários nos quais
      um candidato constitui apenas parte da componente escura.
    - **Densidade local:** é uma referência de modelo e apresenta
      incertezas astrofísicas.
    """)

# ==========================================================
# ABA 2 — OBSERVAÇÕES E LENTES
# ==========================================================

with tab2:
    st.header("02 · Curvas de rotação e lentes gravitacionais")

    st.subheader("A. Curva de rotação galáctica")

    c1, c2, c3 = st.columns(3)

    with c1:
        rho0 = st.number_input(
            "Densidade central do halo (M☉/kpc³)",
            min_value=1e5, max_value=1e9,
            value=5e7, format="%.2e"
        )
    with c2:
        core_radius = st.slider(
            "Raio central do halo (kpc)",
            0.2, 20.0, 5.0, 0.2
        )
    with c3:
        disk_mass = st.number_input(
            "Massa do disco (M☉)",
            min_value=1e8, max_value=2e12,
            value=5e10, format="%.2e"
        )

    disk_scale = st.slider(
        "Escala radial do disco (kpc)",
        0.5, 10.0, 3.0, 0.1
    )
    bulge_mass = st.number_input(
        "Massa do bojo (M☉)",
        min_value=0.0, max_value=1e11,
        value=1e10, format="%.2e"
    )

    r = np.linspace(0.15, 30, 250)

    v_total, v_baryon, v_halo = rotation_model(
        r, rho0, core_radius, disk_scale, disk_mass, bulge_mass
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=r, y=v_total, mode="lines",
        name="Modelo total",
        line=dict(color="#79dcff", width=3)
    ))
    fig.add_trace(go.Scatter(
        x=r, y=v_baryon, mode="lines",
        name="Componente bariônica",
        line=dict(color="#ffd166", width=2, dash="dash")
    ))
    fig.add_trace(go.Scatter(
        x=r, y=v_halo, mode="lines",
        name="Halo escuro",
        line=dict(color="#c792ff", width=2, dash="dot")
    ))
    fig.update_layout(
        title="Curva de rotação calculada a partir dos parâmetros escolhidos",
        xaxis_title="Raio galactocêntrico (kpc)",
        yaxis_title="Velocidade circular (km/s)",
        legend=dict(orientation="h", y=-0.2)
    )
    st.plotly_chart(chart_style(fig, 440), use_container_width=True)

    st.latex(r"v_c(r) = \sqrt{\frac{G M(<r)}{r}}")
    st.caption(
        "Modelo de halo pseudo-isotérmico e aproximação esférica para "
        "a massa bariônica. É uma curva sintética, não um conjunto de "
        "medições de uma galáxia real."
    )

    st.divider()
    st.subheader("B. Mapa ilustrativo de lentes gravitacionais")

    l1, l2, l3 = st.columns(3)
    with l1:
        lens_seed = st.number_input(
            "Semente do mapa", 0, 10000, 7
        )
    with l2:
        concentration = st.slider(
            "Concentração dos halos",
            0.2, 5.0, 1.5, 0.1
        )
    with l3:
        noise = st.slider(
            "Ruído ilustrativo",
            0.0, 0.5, 0.03, 0.01
        )

    X, Y, K = make_lensing_map(
        int(lens_seed), concentration, noise
    )

    fig = go.Figure(go.Heatmap(
        x=X[0],
        y=Y[:, 0],
        z=K,
        colorscale="Magma",
        colorbar=dict(title="Convergência<br>relativa")
    ))
    fig.update_layout(
        title="Distribuição sintética de convergência de lente",
        xaxis_title="Coordenada angular relativa",
        yaxis_title="Coordenada angular relativa",
        yaxis=dict(scaleanchor="x", scaleratio=1)
    )
    st.plotly_chart(chart_style(fig, 500), use_container_width=True)

    st.latex(r"\kappa(\theta) = \frac{\Sigma(\theta)}{\Sigma_{\mathrm{crit}}}")

    st.warning(
        "Este mapa é uma ilustração matemática sintética, não uma imagem "
        "de telescópio nem uma reconstrução observacional. Lentes "
        "gravitacionais medem os efeitos da distribuição total de massa "
        "ao longo da linha de visada; a inferência de matéria escura "
        "depende de modelos e dados adicionais."
    )

# ==========================================================
# ABA 3 — SIMULAÇÕES DE ESTRUTURA CÓSMICA
# ==========================================================

with tab3:
    st.header("03 · Formação de estruturas cósmicas")

    st.write(
        "Execute um modelo newtoniano simplificado de partículas "
        "gravitacionais para visualizar a evolução de duas sobredensidades."
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        n_particles = st.slider(
            "Número de partículas",
            30, 180, 80, 10
        )
    with c2:
        steps = st.slider(
            "Passos de integração",
            5, 100, 35, 5
        )
    with c3:
        gravity_strength = st.slider(
            "Intensidade gravitacional adimensional",
            0.0, 3.0, 0.8, 0.1
        )

    dt = st.slider(
        "Passo temporal adimensional",
        0.005, 0.08, 0.025, 0.005
    )
    seed = st.number_input(
        "Semente aleatória",
        0, 100000, 42
    )

    if st.button("▶ Executar simulação", type="primary"):
        history, final_pos = simulate_gravity(
            int(seed),
            n_particles,
            steps,
            gravity_strength,
            dt
        )

        initial = history[0]
        final = final_pos

        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=("Condição inicial", "Estado final")
        )

        fig.add_trace(go.Scatter(
            x=initial[:, 0], y=initial[:, 1],
            mode="markers",
            marker=dict(size=6, color="#70cfff"),
            name="Inicial"
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=final[:, 0], y=final[:, 1],
            mode="markers",
            marker=dict(size=6, color="#d2a5ff"),
            name="Final"
        ), row=1, col=2)

        fig.update_xaxes(title_text="x (unidades arbitrárias)")
        fig.update_yaxes(title_text="y (unidades arbitrárias)")
        fig.update_layout(showlegend=False)

        st.plotly_chart(
            chart_style(fig, 500),
            use_container_width=True
        )

        displacement = np.linalg.norm(final - initial, axis=1)
        a, b, c = st.columns(3)
        a.metric("Partículas simuladas", f"{n_particles}")
        b.metric("Deslocamento médio", f"{displacement.mean():.3f}")
        c.metric("Passos calculados", f"{steps}")

        st.success(
            "Simulação concluída. Compare a concentração e a distribuição "
            "das partículas antes e depois da evolução."
        )

    else:
        st.info(
            "Configure os parâmetros e clique em «Executar simulação» "
            "para calcular uma nova realização."
        )

    st.markdown("### Equações do modelo")

    st.latex(
        r"\frac{d^2\mathbf{x}_i}{dt^2} = "
        r"-G\sum_{j\ne i}m_j"
        r"\frac{\mathbf{x}_i-\mathbf{x}_j}"
        r"(|\mathbf{x}_i-\mathbf{x}_j|^2+\epsilon^2)^{3/2}"
    )

    st.markdown("""
    A expressão representa a aceleração gravitacional de partículas,
    com um termo de suavização para reduzir singularidades em encontros
    próximos. A implementação utiliza unidades adimensionais.
    """)

    st.warning(
        "Esta simulação é um experimento N-corpos didático em duas "
        "dimensões. Não inclui expansão cosmológica, matéria bariônica, "
        "hidrodinâmica, relatividade geral ou condições iniciais "
        "cosmológicas realistas. Não deve ser interpretada como uma "
        "simulação fiel da formação de galáxias."
    )

# ---------------------------- RODAPÉ -----------------------

st.divider()
st.subheader("📚 Interpretação científica")

st.markdown("""
**Newton:** a gravitação newtoniana é uma aproximação útil para estudar
a dinâmica de galáxias e sistemas de partículas em regimes apropriados.

**Einstein:** a relatividade geral descreve a gravidade como geometria
do espaço-tempo. Em cosmologia, a evolução do Universo é tratada por
equações como as de Friedmann, derivadas das equações de Einstein sob
hipóteses cosmológicas específicas.

**Matéria escura:** as curvas de rotação, lentes gravitacionais e
formação de estruturas fornecem evidências complementares para
investigar a distribuição de massa que não é explicada apenas pela
matéria luminosa.
""")

st.caption(
    "Dark Matter Lab · Aplicativo educacional · "
    "Gráficos sintéticos claramente identificados · "
    "Não constitui análise de dados observacionais reais."
)
