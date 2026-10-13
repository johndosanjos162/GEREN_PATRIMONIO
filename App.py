
import math
import numpy as np
import streamlit as st
import plotly.graph_objects as go

# =========================================================
# INTERSTELLAR LAB — SIMULADOR DE MISSÃO INTERESTELAR
# Aplicação em arquivo único: app.py
# =========================================================

C = 299_792_458.0
YEAR = 365.25 * 24 * 3600
LY_M = 9.460730472e15

st.set_page_config(
    page_title="Interstellar Lab",
    page_icon="🚀",
    layout="wide"
)

# ------------------------- ESTILO -------------------------

st.markdown("""
<style>
.stApp {
    background: linear-gradient(145deg,#06101d,#101d34,#07111f);
    color: #e8f2ff;
}
[data-testid="stSidebar"] {
    background: #0b1525;
    border-right: 1px solid #29415f;
}
.block-container {
    max-width: 1450px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}
h1,h2,h3 {color:#eaf5ff !important;}
[data-testid="stMetric"] {
    background: rgba(20,39,64,.85);
    border: 1px solid #294d70;
    border-radius: 13px;
    padding: 14px;
}
[data-testid="stMetricValue"] {color:#63dcff;}
[data-testid="stMetricLabel"] {color:#b1c9e8;}
.stTabs [data-baseweb="tab"] {
    background:#14233a;
    border-radius:8px 8px 0 0;
}
</style>
""", unsafe_allow_html=True)


def sci(value, unit=""):
    if not math.isfinite(float(value)):
        return "Indefinido"
    return f"{value:.3e} {unit}".strip()


def duration(seconds):
    if seconds < 60:
        return f"{seconds:.2f} s"
    if seconds < 3600:
        return f"{seconds / 60:.2f} min"
    if seconds < 86400:
        return f"{seconds / 3600:.2f} h"
    if seconds < YEAR:
        return f"{seconds / 86400:.2f} dias"
    return f"{seconds / YEAR:.3f} anos"


def chart_layout(fig, height=360):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,19,34,.8)",
        font=dict(color="#dceaff"),
        margin=dict(l=15, r=15, t=55, b=20),
        height=height
    )
    return fig


# ---------------------- ANIMAÇÃO --------------------------

def create_probe_animation():
    """
    Animação conceitual em loop.
    A posição visual é normalizada e NÃO representa
    uma trajetória física calculada em escala real.
    """

    rng = np.random.default_rng(24)
    star_x = rng.uniform(0, 100, 100)
    star_y = rng.uniform(-20, 20, 100)
    star_sizes = rng.uniform(1, 3, 100)

    fig = go.Figure()

    # Estrelas do fundo
    fig.add_trace(go.Scatter(
        x=star_x,
        y=star_y,
        mode="markers",
        marker=dict(
            size=star_sizes,
            color="#b9d7ff",
            opacity=0.65
        ),
        name="Estrelas",
        hoverinfo="skip"
    ))

    # Feixe de laser
    fig.add_trace(go.Scatter(
        x=[0, 15],
        y=[0, 0],
        mode="lines",
        line=dict(color="#ff4d70", width=8),
        name="Feixe laser",
        hoverinfo="skip"
    ))

    # Vela e sonda
    fig.add_trace(go.Scatter(
        x=[15],
        y=[0],
        mode="markers",
        marker=dict(
            size=22,
            symbol="diamond",
            color="#71eaff",
            line=dict(color="white", width=2)
        ),
        name="Vela / sonda",
        hovertemplate="Sonda ilustrativa<extra></extra>"
    ))

    # Reflexo luminoso ilustrativo
    fig.add_trace(go.Scatter(
        x=[15, 13],
        y=[0, 3],
        mode="lines",
        line=dict(color="#71eaff", width=3, dash="dot"),
        name="Luz refletida",
        hoverinfo="skip"
    ))

    frames = []
    positions = np.linspace(15, 92, 60)

    for i, x in enumerate(positions):
        y = 2.2 * math.sin(i / 7)

        frames.append(go.Frame(
            name=str(i),
            data=[
                go.Scatter(),  # Fundo estático
                go.Scatter(x=[0, x], y=[0, y]),
                go.Scatter(x=[x], y=[y]),
                go.Scatter(x=[x, x - 2.5], y=[y, y + 3])
            ],
            traces=[0, 1, 2, 3]
        ))

    fig.frames = frames

    fig.update_layout(
        title="Sonda interestelar — visualização animada",
        xaxis=dict(
            range=[0, 100],
            title="Posição visual normalizada",
            showgrid=False,
            zeroline=False
        ),
        yaxis=dict(
            range=[-20, 20],
            title="Deslocamento visual",
            showgrid=False,
            zeroline=False
        ),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#050d19",
        font=dict(color="#dceaff"),
        height=480,
        margin=dict(l=20, r=20, t=60, b=30),
        legend=dict(orientation="h", y=-0.15),
        updatemenus=[{
            "type": "buttons",
            "showactive": False,
            "x": 0.02,
            "y": 1.12,
            "buttons": [
                {
                    "label": "▶ Iniciar / repetir",
                    "method": "animate",
                    "args": [
                        None,
                        {
                            "frame": {"duration": 80, "redraw": True},
                            "transition": {"duration": 0},
                            "fromcurrent": False,
                            "mode": "immediate"
                        }
                    ]
                },
                {
                    "label": "⏸ Pausar",
                    "method": "animate",
                    "args": [
                        [None],
                        {
                            "frame": {"duration": 0, "redraw": False},
                            "mode": "immediate",
                            "transition": {"duration": 0}
                        }
                    ]
                }
            ]
        }]
    )

    return fig


# ------------------------- CABEÇALHO ----------------------

st.title("🚀 INTERSTELLAR LAB")
st.subheader("Laboratório virtual de engenharia interestelar")
st.caption(
    "Propulsão por laser • Materiais ópticos • Enxame de sondas "
    "• Comunicação interestelar"
)

with st.sidebar:
    st.header("🛰️ Centro de missão")
    st.info("Destino de referência: Próxima Centauri")
    st.write("Distância aproximada: 4,24 anos-luz")
    st.divider()
    st.write("**Módulos científicos**")
    st.write("01 — Propulsão")
    st.write("02 — Vela e animação")
    st.write("03 — Comunicação em enxame")
    st.write("04 — Enlace com a Terra")
    st.divider()
    st.caption("Modelo conceitual e educacional.")

tab1, tab2, tab3, tab4 = st.tabs([
    "🚀 Propulsão",
    "🔬 Vela e animação",
    "🛰️ Comunicação em enxame",
    "🌍 Enlace com a Terra"
])


# =========================================================
# ABA 1 — PROPULSÃO
# =========================================================

with tab1:
    st.header("01 · Propulsão e velocidade")

    col1, col2 = st.columns(2)

    with col1:
        mass_g = st.number_input(
            "Massa total da sonda (g)",
            min_value=0.01, max_value=100000.0,
            value=1.0, step=0.1
        )
        power_gw = st.number_input(
            "Potência óptica incidente (GW)",
            min_value=0.001, max_value=10000.0,
            value=100.0, step=1.0
        )

    with col2:
        reflectivity = st.slider(
            "Refletividade da vela (%)",
            0.0, 100.0, 99.9, 0.1
        )
        beta_percent = st.slider(
            "Velocidade-alvo (% de c)",
            0.1, 20.0, 20.0, 0.1
        )

    mass = mass_g / 1000
    power = power_gw * 1e9
    R = reflectivity / 100
    beta = beta_percent / 100

    # Pressão de radiação para reflexão especular ideal
    force = (1 + R) * power / C
    acceleration = force / mass

    # Energia cinética relativística
    gamma = 1 / math.sqrt(1 - beta**2)
    kinetic_energy = (gamma - 1) * mass * C**2

    # Tempo idealizado de aceleração:
    # estimativa newtoniana, força constante
    target_velocity = beta * C
    t_approx = target_velocity / acceleration
    distance_approx = 0.5 * acceleration * t_approx**2

    m1, m2, m3 = st.columns(3)
    m1.metric("Força ideal", f"{force:.4f} N")
    m2.metric("Aceleração inicial", f"{acceleration:.4g} m/s²")
    m3.metric("Velocidade-alvo", f"{beta_percent:.1f}% de c")

    m1, m2, m3 = st.columns(3)
    m1.metric("Energia cinética", sci(kinetic_energy, "J"))
    m2.metric("Tempo aproximado", duration(t_approx))
    m3.metric("Distância aproximada", sci(distance_approx, "m"))

    st.markdown("### Fórmulas físicas")

    st.latex(r"F = \frac{(1+R)P}{c}")
    st.caption(
        "F = força; R = refletividade idealizada; "
        "P = potência incidente; c = velocidade da luz."
    )

    st.latex(r"a = \frac{F}{m}")
    st.latex(r"E_k = (\gamma - 1)mc^2")
    st.latex(r"\gamma = \frac{1}{\sqrt{1-v^2/c^2}}")

    if beta_percent >= 5:
        st.warning(
            "O tempo e a distância de aceleração usam uma aproximação "
            "newtoniana de força constante. Em velocidades relativísticas, "
            "a previsão exige um modelo relativístico completo."
        )

    st.markdown("### Energia versus velocidade")

    beta_values = np.linspace(0.001, 0.20, 120)
    energy_values = [
        (1 / math.sqrt(1 - b*b) - 1) * mass * C**2
        for b in beta_values
    ]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=beta_values * 100,
        y=energy_values,
        mode="lines",
        line=dict(color="#65ddff", width=3),
        name="Energia cinética"
    ))
    fig.update_layout(
        title="Energia cinética relativística",
        xaxis_title="Velocidade (% de c)",
        yaxis_title="Energia (J)"
    )
    st.plotly_chart(chart_layout(fig), use_container_width=True)


# =========================================================
# ABA 2 — VELA, MATERIAIS E ANIMAÇÃO
# =========================================================

with tab2:
    st.header("02 · Vela a laser e materiais")
    st.write(
        "A animação representa o conceito de uma vela leve acelerada "
        "pela pressão de radiação. Ajuste os parâmetros e observe "
        "os indicadores físicos serem recalculados."
    )

    left, right = st.columns([1.4, 1])

    with left:
        st.plotly_chart(
            create_probe_animation(),
            use_container_width=True,
            key="probe_animation"
        )
        st.caption(
            "A posição e a oscilação da animação são ilustrativas; "
            "não representam uma trajetória orbital em escala."
        )

    with right:
        area = st.number_input(
            "Área iluminada (m²)",
            min_value=0.01, max_value=1e8,
            value=10.0, step=1.0
        )
        sail_power_gw = st.number_input(
            "Potência na vela (GW)",
            min_value=0.001, max_value=10000.0,
            value=100.0, step=1.0
        )
        absorption_percent = st.number_input(
            "Potência absorvida (%)",
            min_value=0.000001, max_value=100.0,
            value=0.1, step=0.01, format="%.6f"
        )
        sail_mass_g = st.number_input(
            "Massa total (g)",
            min_value=0.01, max_value=100000.0,
            value=1.0, step=0.1
        )

        P = sail_power_gw * 1e9
        absorption = absorption_percent / 100
        absorbed_power = P * absorption
        irradiance = P / area
        pressure = 2 * P / (C * area)
        sail_force = 2 * P / C
        sail_accel = sail_force / (sail_mass_g / 1000)

        st.metric("Irradiância média", sci(irradiance, "W/m²"))
        st.metric("Potência absorvida", sci(absorbed_power, "W"))
        st.metric("Pressão de radiação", sci(pressure, "Pa"))
        st.metric("Aceleração ideal", f"{sail_accel:.4g} m/s²")

    st.markdown("### Equações exibidas em tempo real")

    st.latex(r"I = \frac{P}{A}")
    st.latex(r"p_{\mathrm{rad}} = \frac{2P}{Ac}")
    st.latex(r"P_{\mathrm{abs}} = \alpha P")

    st.write(
        f"**Substituição numérica:** "
        f"I = {P:.3e} / {area:.3f} = {irradiance:.3e} W/m²."
    )
    st.write(
        f"**Potência absorvida:** "
        f"{absorption_percent:.6f}% × {P:.3e} W "
        f"= {absorbed_power:.3e} W."
    )

    st.warning(
        "A potência absorvida, isoladamente, não determina a temperatura "
        "da vela. Para prever a temperatura são necessários emissividade, "
        "espectro, propriedades térmicas, geometria e condições de "
        "equilíbrio radiativo."
    )

    st.markdown("### Materiais candidatos para pesquisa")

    st.markdown("""
    - **Filmes dielétricos multicamadas:** alta refletividade em bandas
      espectrais selecionadas.
    - **Cristais fotônicos e metamateriais:** controle de propriedades
      ópticas por meio da estrutura.
    - **Membranas ultrafinas:** menor massa, mas desafios de fabricação,
      rugas, defeitos e estabilidade.
    - **Compósitos:** possível combinação de propriedades ópticas,
      térmicas e mecânicas.
    """)

    st.caption(
        "Nenhuma dessas categorias, por si só, comprova a existência "
        "de uma vela qualificada para operação em um feixe de 100 GW."
    )


# =========================================================
# ABA 3 — COMUNICAÇÃO EM ENXAME
# =========================================================

with tab3:
    st.header("03 · Arquitetura de comunicação em enxame")

    c1, c2 = st.columns(2)

    with c1:
        probe_count = st.number_input(
            "Número total de sondas",
            min_value=1, max_value=10000,
            value=12, step=1
        )
        total_bandwidth = st.number_input(
            "Banda total disponível (Mbps)",
            min_value=0.001, max_value=1e9,
            value=100.0, step=1.0
        )

    with c2:
        active_percent = st.slider(
            "Percentual de sondas ativas",
            0, 100, 90, 5
        )
        use_percent = st.slider(
            "Utilização da banda (%)",
            0, 100, 65, 5
        )

    active = int(round(probe_count * active_percent / 100))
    used = total_bandwidth * use_percent / 100
    available = total_bandwidth - used
    per_probe = used / active if active > 0 else 0
    possible_links = active * (active - 1) // 2

    a, b, c, d = st.columns(4)
    a.metric("Sondas configuradas", f"{probe_count:,}")
    b.metric("Sondas ativas", f"{active:,}")
    c.metric("Links em malha completa", f"{possible_links:,}")
    d.metric("Banda média por sonda", f"{per_probe:.3f} Mbps")

    st.markdown("### Estado da rede")
    st.progress(use_percent / 100)

    a, b = st.columns(2)
    a.metric("Banda utilizada", f"{used:.3f} Mbps")
    b.metric("Banda disponível", f"{available:.3f} Mbps")

    fig = go.Figure(go.Bar(
        x=["Utilizada", "Disponível"],
        y=[used, available],
        text=[f"{used:.2f}", f"{available:.2f}"],
        textposition="auto"
    ))
    fig.update_layout(
        title="Distribuição da largura de banda",
        xaxis_title="Categoria",
        yaxis_title="Mbps"
    )
    st.plotly_chart(chart_layout(fig), use_container_width=True)

    if active == 0:
        st.error("Nenhuma sonda ativa.")
    elif use_percent >= 95:
        st.warning("Rede próxima da saturação.")
    elif use_percent >= 75:
        st.info("Uso elevado: monitore filas e prioridades.")
    else:
        st.success("Uso dentro da margem configurada.")

    st.latex(r"N_{\mathrm{links}} = \frac{n(n-1)}{2}")
    st.latex(r"B_{\mathrm{usada}} = B_{\mathrm{total}}u")

    st.caption(
        "O modelo presume uma rede de malha completa e divide a banda "
        "de forma simplificada. Não simula propagação, interferência, "
        "potência óptica, protocolo ou disponibilidade geométrica."
    )


# =========================================================
# ABA 4 — ENLACE COM A TERRA
# =========================================================

with tab4:
    st.header("04 · Enlace de comunicação com a Terra")

    c1, c2 = st.columns(2)

    with c1:
        distance_ly = st.number_input(
            "Distância até a Terra (anos-luz)",
            min_value=0.0, max_value=1e6,
            value=4.24, step=0.1
        )
        data_gb = st.number_input(
            "Volume de dados (GB)",
            min_value=0.000001, max_value=1e12,
            value=1.0, step=0.5
        )

    with c2:
        rate_kbps = st.number_input(
            "Taxa bruta de transmissão (kbps)",
            min_value=0.001, max_value=1e12,
            value=10.0, step=1.0
        )
        efficiency = st.slider(
            "Eficiência útil (%)",
            1, 100, 80, 1
        )

    distance_m = distance_ly * LY_M
    light_delay = distance_ly * YEAR
    rate_bps = rate_kbps * 1000 * efficiency / 100
    bits = data_gb * 1e9 * 8
    tx_time = bits / rate_bps
    total_time = light_delay + tx_time

    a, b, c = st.columns(3)
    a.metric("Atraso de ida da luz", f"{distance_ly:.3f} anos")
    b.metric("Tempo de transmissão", duration(tx_time))
    c.metric("Recepção completa", duration(total_time))

    a, b = st.columns(2)
    a.metric("Distância em metros", sci(distance_m, "m"))
    b.metric("Taxa útil", f"{rate_bps / 1000:.3f} kbps")

    st.markdown("### Fórmulas de comunicação")

    st.latex(r"t_{\mathrm{luz}} = \frac{d}{c}")
    st.latex(r"t_{\mathrm{transmissão}} = \frac{8D}{R}")
    st.latex(
        r"t_{\mathrm{total}} \approx "
        r"t_{\mathrm{luz}} + t_{\mathrm{transmissão}}"
    )

    st.info(
        f"A uma distância de {distance_ly:.3f} anos-luz, o sinal "
        f"demora aproximadamente {distance_ly:.3f} anos para chegar "
        "à Terra, independentemente da taxa de transmissão."
    )

    volumes = np.array([0.1, 1, 10, 100, 1000])
    hours = [
        (v * 1e9 * 8) / rate_bps / 3600
        for v in volumes
    ]

    fig = go.Figure(go.Scatter(
        x=volumes,
        y=hours,
        mode="lines+markers",
        line=dict(color="#68dcff", width=3)
    ))
    fig.update_layout(
        title="Volume de dados versus tempo de transmissão",
        xaxis_title="Volume (GB)",
        yaxis_title="Tempo de transmissão (horas)"
    )
    st.plotly_chart(chart_layout(fig), use_container_width=True)

    st.warning(
        "O modelo supõe taxa constante. Não inclui perdas, interrupções, "
        "retransmissões, apontamento do laser, ruído do receptor ou "
        "compressão real. O atraso de propagação não pode ser eliminado."
    )


# --------------------------- RODAPÉ ------------------------

st.divider()
st.subheader("🧭 Resumo científico")

st.write(
    "O laboratório combina equações físicas, indicadores calculados "
    "e uma animação conceitual. Os valores são estimativas simplificadas "
    "para estudo, não uma validação de projeto de voo."
)

st.caption(
    "Interstellar Lab · Simulador educacional · "
    "Todos os cálculos são realizados localmente."
)
