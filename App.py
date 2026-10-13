
import math
import streamlit as st
import numpy as np
import plotly.graph_objects as go

# ============================================================
# LABORATÓRIO DE ENGENHARIA INTERESTELAR
# Arquivo único: app.py
# ============================================================

C = 299_792_458
LY_KM = 9.460730472e12
AU = 149_597_870_700
YEAR = 365.25 * 24 * 3600

st.set_page_config(
    page_title="Interstellar Lab | Laboratório",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------- DESIGN -----------------------------

st.markdown("""
<style>
.stApp {
    background: linear-gradient(145deg, #07111f 0%, #101b30 55%, #091321 100%);
    color: #e8f0ff;
}
[data-testid="stSidebar"] {
    background: #0b1423;
    border-right: 1px solid #243550;
}
.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1450px;
}
h1, h2, h3 { color: #eaf3ff !important; }
p, label, .stMarkdown { color: #c4d2e8; }
[data-testid="stMetric"] {
    background: rgba(22, 39, 64, 0.82);
    border: 1px solid #294568;
    padding: 17px;
    border-radius: 14px;
}
[data-testid="stMetricLabel"] { color: #9db9df; }
[data-testid="stMetricValue"] { color: #66d9ff; }
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    border-bottom: 1px solid #294568;
}
.stTabs [data-baseweb="tab"] {
    background: #13223a;
    border-radius: 9px 9px 0 0;
    padding: 12px 16px;
}
div[data-testid="stAlert"] { border-radius: 12px; }
hr { border-color: #29405e; }
</style>
""", unsafe_allow_html=True)

def fmt(value, digits=3):
    if not math.isfinite(float(value)):
        return "—"
    return f"{value:,.{digits}f}"

def sci(value, unit=""):
    if value == 0:
        return f"0 {unit}".strip()
    return f"{value:.3e} {unit}".strip()

def make_chart(x, y, title, x_title, y_title):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="lines",
        line=dict(color="#50d9ff", width=3),
        fill="tozeroy",
        fillcolor="rgba(80,217,255,0.10)"
    ))
    fig.update_layout(
        title=title,
        xaxis_title=x_title,
        yaxis_title=y_title,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(10,22,40,0.7)",
        margin=dict(l=15, r=15, t=55, b=20),
        height=350
    )
    return fig

def fmt_duration(seconds):
    if seconds < 60:
        return f"{seconds:.2f} segundos"
    if seconds < 3600:
        return f"{seconds / 60:.2f} minutos"
    if seconds < 86400:
        return f"{seconds / 3600:.2f} horas"
    if seconds < YEAR:
        return f"{seconds / 86400:.2f} dias"
    return f"{seconds / YEAR:.3f} anos"

# ----------------------- CABEÇALHO --------------------------

st.title("🚀 INTERSTELLAR LAB")
st.markdown(
    "### Laboratório virtual de propulsão e comunicações interestelares"
)
st.caption(
    "Simulador educacional de missão não tripulada • "
    "Modelos físicos simplificados • Unidades SI"
)

with st.sidebar:
    st.markdown("## 🛰️ Centro de missão")
    st.markdown("**Destino de referência**")
    st.info("Próxima Centauri — aproximadamente 4,24 anos-luz.")
    st.markdown("---")
    st.markdown("**Módulos do laboratório**")
    st.write("01 · Propulsão e velocidade")
    st.write("02 · Vela a laser e materiais")
    st.write("03 · Comunicação em enxame")
    st.write("04 · Enlace com a Terra")
    st.markdown("---")
    st.caption("Protótipo conceitual. Não representa uma nave operacional.")

tab1, tab2, tab3, tab4 = st.tabs([
    "🚀 Propulsão",
    "🔬 Vela e materiais",
    "🛰️ Comunicação em enxame",
    "🌍 Enlace com a Terra"
])

# ============================================================
# ABA 1 — PROPULSÃO E VELOCIDADE
# ============================================================

with tab1:
    st.header("01 · Propulsão e velocidade")
    st.write(
        "Explore como a massa da sonda e a potência incidente "
        "influenciam a aceleração de uma vela refletora."
    )

    col1, col2 = st.columns(2)
    with col1:
        mass_g = st.number_input(
            "Massa total da sonda (gramas)",
            min_value=0.01, max_value=100000.0,
            value=1.0, step=0.1, key="mass_prop"
        )
        power_gw = st.number_input(
            "Potência óptica incidente (GW)",
            min_value=0.001, max_value=10000.0,
            value=100.0, step=1.0, key="power_prop"
        )
    with col2:
        reflectivity = st.slider(
            "Refletividade da vela (%)",
            0.0, 100.0, 99.9, 0.1, key="reflect_prop"
        )
        target_c = st.slider(
            "Velocidade-alvo (% da velocidade da luz)",
            0.1, 20.0, 20.0, 0.1, key="target_prop"
        )

    mass = mass_g / 1000
    power = power_gw * 1e9
    R = reflectivity / 100
    beta = target_c / 100

    # Pressão de radiação para reflexão especular ideal.
    force = (1 + R) * power / C
    acceleration = force / mass

    # Energia cinética relativística.
    gamma = 1 / math.sqrt(1 - beta**2)
    kinetic_energy = (gamma - 1) * mass * C**2

    # Tempo idealizado: força constante e massa constante.
    # Aproximação newtoniana; não é um modelo completo de vela relativística.
    target_v = beta * C
    time_approx = target_v / acceleration
    distance_approx = 0.5 * acceleration * time_approx**2

    m1, m2, m3 = st.columns(3)
    m1.metric("Força ideal na vela", f"{force:.3f} N")
    m2.metric("Aceleração inicial", f"{acceleration:.3g} m/s²")
    m3.metric("Velocidade-alvo", f"{target_c:.1f}% de c")

    m4, m5 = st.columns(2)
    m4.metric("Energia cinética relativística", sci(kinetic_energy, "J"))
    m5.metric(
        "Tempo newtoniano aproximado",
        fmt_duration(time_approx)
    )

    if target_c > 5:
        st.warning(
            "A velocidade escolhida é relativística. O tempo e a distância "
            "acima usam força constante e mecânica newtoniana; não devem ser "
            "interpretados como previsão confiável para uma vela a laser. "
            "A energia cinética usa a fórmula relativística."
        )
    else:
        st.info(
            "Estimativa idealizada: desconsidera perdas ópticas, "
            "difração, variação da força, estabilidade e limitações térmicas."
        )

    st.markdown("#### Comparação de energia cinética por velocidade")
    betas = np.linspace(0.001, 0.20, 100)
    energies = [
        (1 / math.sqrt(1 - b*b) - 1) * mass * C**2
        for b in betas
    ]
    fig = make_chart(
        betas * 100, energies,
        "Energia cinética relativística",
        "Velocidade (% de c)", "Energia (J)"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Referência: Próxima Centauri")
    distance_ly = 4.24
    travel_years = distance_ly / beta
    st.metric(
        "Tempo de viagem idealizado a velocidade constante",
        f"{travel_years:.2f} anos"
    )
    st.caption(
        "Não inclui aceleração, desaceleração, manobras ou tempo de "
        "comunicação. O tempo é medido no referencial aproximado da Terra."
    )

# ============================================================
# ABA 2 — VELA A LASER E MATERIAIS
# ============================================================

with tab2:
    st.header("02 · Vela a laser e materiais")
    st.write(
        "Analise a pressão de radiação, a área da vela e a potência "
        "que seria absorvida pelo material."
    )

    c1, c2 = st.columns(2)
    with c1:
        sail_area = st.number_input(
            "Área iluminada da vela (m²)",
            min_value=0.01, max_value=1e8,
            value=10.0, step=1.0, key="sail_area"
        )
        laser_power = st.number_input(
            "Potência que chega à vela (GW)",
            min_value=0.001, max_value=10000.0,
            value=100.0, step=1.0, key="sail_power"
        )
    with c2:
        absorption = st.number_input(
            "Fração de potência absorvida (%)",
            min_value=0.000001, max_value=100.0,
            value=0.1, step=0.01, format="%.6f",
            key="absorption"
        )
        sail_mass = st.number_input(
            "Massa total da vela e carga (gramas)",
            min_value=0.01, max_value=100000.0,
            value=1.0, step=0.1, key="sail_mass"
        )

    P = laser_power * 1e9
    absorbed_fraction = absorption / 100
    absorbed_power = P * absorbed_fraction
    irradiance = P / sail_area
    pressure = 2 * P / (C * sail_area)
    accel_sail = 2 * P / C / (sail_mass / 1000)

    c1, c2, c3 = st.columns(3)
    c1.metric("Irradiância média", sci(irradiance, "W/m²"))
    c2.metric("Potência absorvida", sci(absorbed_power, "W"))
    c3.metric("Pressão ideal", sci(pressure, "Pa"))

    st.metric("Aceleração ideal por reflexão", f"{accel_sail:.3g} m/s²")

    st.markdown("#### Balanço óptico simplificado")
    st.progress(min(max(absorbed_fraction, 0.0), 1.0))
    st.write(f"Absorção: **{absorption:g}%**")
    st.write(f"Potência não absorvida: **{(1-absorbed_fraction)*100:.6f}%**")

    st.warning(
        "A potência absorvida não determina sozinha a temperatura. "
        "Também são necessários emissividade, espectro do laser, "
        "condutividade térmica, geometria, orientação e propriedades "
        "ópticas do material. Não é possível concluir que a vela sobreviverá "
        "apenas com estes cálculos."
    )

    st.markdown("#### Conceitos de materiais para pesquisa")
    st.markdown("""
    - **Filmes dielétricos multicamadas:** podem oferecer alta refletividade
      em comprimentos de onda específicos.
    - **Cristais fotônicos e metamateriais:** permitem estudar o controle
      espectral e direcional da luz; não garantem resistência térmica.
    - **Membranas ultrafinas:** reduzem a massa, mas aumentam a sensibilidade
      a defeitos, tensões, enrugamento e fabricação.
    - **Estruturas compostas:** podem combinar propriedades ópticas e
      mecânicas, com penalidade potencial de massa.
    """)

    st.caption(
        "As opções acima são linhas de investigação, não materiais "
        "comprovadamente qualificados para uma matriz de laser de 100 GW."
    )

# ============================================================
# ABA 3 — COMUNICAÇÃO EM ENXAME
# ============================================================

with tab3:
    st.header("03 · Arquitetura de comunicação em enxame")
    st.write(
        "Configure uma frota hipotética e examine sua conectividade "
        "e a divisão da largura de banda."
    )

    c1, c2 = st.columns(2)
    with c1:
        probe_count = st.number_input(
            "Número de sondas na frota",
            min_value=1, max_value=10000,
            value=12, step=1, key="probe_count"
        )
        total_bandwidth = st.number_input(
            "Largura de banda total disponível (Mbps)",
            min_value=0.001, max_value=1e9,
            value=100.0, step=1.0, key="total_bandwidth"
        )
    with c2:
        active_fraction = st.slider(
            "Percentual da frota ativa",
            min_value=0, max_value=100,
            value=90, step=5, key="active_fraction"
        )
        bandwidth_use = st.slider(
            "Utilização planejada da banda (%)",
            min_value=0, max_value=100,
            value=65, step=5, key="bandwidth_use"
        )

    active_probes = int(round(probe_count * active_fraction / 100))
    links = active_probes * (active_probes - 1) // 2
    used_bandwidth = total_bandwidth * bandwidth_use / 100
    available_bandwidth = total_bandwidth - used_bandwidth
    per_probe = used_bandwidth / active_probes if active_probes else 0

    st.markdown("#### Estado operacional")
    a, b, c, d = st.columns(4)
    a.metric("Sondas configuradas", f"{probe_count:,}")
    b.metric("Sondas ativas", f"{active_probes:,}")
    c.metric("Conexões em malha completa", f"{links:,}")
    d.metric("Banda por sonda ativa", f"{per_probe:.3f} Mbps")

    st.markdown("#### Utilização da largura de banda")
    st.progress(bandwidth_use / 100)
    x1, x2 = st.columns(2)
    x1.metric("Banda utilizada", f"{used_bandwidth:.3f} Mbps")
    x2.metric("Banda disponível", f"{available_bandwidth:.3f} Mbps")

    fig = go.Figure(go.Bar(
        x=["Utilizada", "Disponível"],
        y=[used_bandwidth, available_bandwidth],
        text=[
            f"{used_bandwidth:.3f} Mbps",
            f"{available_bandwidth:.3f} Mbps"
        ],
        textposition="auto"
    ))
    fig.update_layout(
        title="Distribuição da banda",
        yaxis_title="Mbps",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(10,22,40,0.7)",
        height=320
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Diagnóstico da rede")
    if active_probes == 0:
        st.error("Nenhuma sonda está ativa. Não há comunicação na frota.")
    elif bandwidth_use >= 95:
        st.warning(
            "Rede próxima da saturação. Considere escalonar transmissões "
            "ou reservar banda para telemetria prioritária."
        )
    elif bandwidth_use >= 75:
        st.info(
            "Uso elevado. Monitore filas, retransmissões e prioridades."
        )
    else:
        st.success(
            "Uso dentro da margem configurada. A capacidade disponível "
            "pode acomodar tráfego adicional neste modelo."
        )

    st.caption(
        "A malha completa pressupõe que cada sonda possa conectar-se "
        "diretamente a todas as outras. A banda por sonda é uma média "
        "simplificada; interferência, distâncias, potência, antenas, "
        "visibilidade e protocolos não são simulados."
    )

# ============================================================
# ABA 4 — ENLACE COM A TERRA
# ============================================================

with tab4:
    st.header("04 · Enlace de comunicação com a Terra")
    st.write(
        "Estime o atraso físico da luz e o tempo de transmissão de "
        "um pacote de dados enviado por uma sonda distante."
    )

    c1, c2 = st.columns(2)
    with c1:
        distance_ly_input = st.number_input(
            "Distância até a Terra (anos-luz)",
            min_value=0.0, max_value=1000000.0,
            value=4.24, step=0.1, key="earth_distance"
        )
        data_gb = st.number_input(
            "Volume de dados a transmitir (GB)",
            min_value=0.000001, max_value=1e12,
            value=1.0, step=0.5, key="data_gb"
        )
    with c2:
        data_rate = st.number_input(
            "Taxa efetiva de transmissão (kbps)",
            min_value=0.001, max_value=1e12,
            value=10.0, step=1.0, key="data_rate"
        )
        protocol_efficiency = st.slider(
            "Eficiência útil do enlace (%)",
            min_value=1, max_value=100,
            value=80, step=1, key="protocol_eff"
        )

    distance_m = distance_ly_input * LY_KM * 1000
    light_delay_s = distance_ly_input * YEAR
    effective_rate_bps = data_rate * 1000 * protocol_efficiency / 100
    data_bits = data_gb * 1e9 * 8
    tx_time_s = data_bits / effective_rate_bps
    arrival_s = light_delay_s + tx_time_s

    st.markdown("#### Métricas do enlace")
    a, b, c = st.columns(3)
    a.metric(
        "Atraso de ida da luz",
        f"{distance_ly_input:.3f} anos"
    )
    b.metric(
        "Tempo para transmitir os dados",
        fmt_duration(tx_time_s)
    )
    c.metric(
        "Tempo até a recepção completa",
        fmt_duration(arrival_s)
    )

    st.markdown("#### Detalhes técnicos")
    x1, x2 = st.columns(2)
    x1.metric("Distância calculada", sci(distance_m, "m"))
    x2.metric("Taxa útil", f"{effective_rate_bps / 1000:.3f} kbps")

    if distance_ly_input > 0:
        st.info(
            f"Uma mensagem enviada agora levaria aproximadamente "
            f"{distance_ly_input:.3f} anos para chegar à Terra, "
            "sem contar o tempo necessário para transmitir todos os dados."
        )
    else:
        st.info(
            "Distância zero: o modelo não inclui atraso de propagação."
        )

    st.markdown("#### Comparação entre volume de dados e tempo de envio")
    volumes = np.array([0.1, 1, 10, 100, 1000], dtype=float)
    times = [
        (v * 1e9 * 8) / effective_rate_bps / 3600
        for v in volumes
    ]
    fig = make_chart(
        volumes, times,
        "Tempo de transmissão em função do volume",
        "Volume de dados (GB)", "Tempo de envio (horas)"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.warning(
        "O cálculo assume taxa útil constante e não inclui interrupções, "
        "perdas de pacotes, retransmissões, apontamento óptico, ruído, "
        "limites do receptor ou compressão real. O atraso de ida é imposto "
        "pela velocidade da luz: não pode ser eliminado por IA ou por "
        "uma arquitetura em enxame."
    )

# ----------------------- RODAPÉ -----------------------------

st.markdown("---")
st.markdown("### 🧭 Resumo da missão")
st.write(
    "Este laboratório permite explorar cenários, não certificar um projeto "
    "de voo. Antes de qualquer engenharia real, seriam necessários modelos "
    "ópticos, térmicos, estruturais, orbitais e de comunicação validados."
)
st.caption(
    "Interstellar Lab • Protótipo educacional • "
    "Os valores dependem dos parâmetros escolhidos pelo usuário."
)
