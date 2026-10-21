import streamlit as st
import json
import datetime
import math
import random
from datetime import datetime

# ============================================================================
# CONFIGURAÇÃO DE INTERFACE E ESTILO FUTURISTA (STREAMLIT CENTRAL)
# ============================================================================
st.set_page_config(
    page_title="PMSC Arena VR",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS Injetada para customização do tema Neon Cyberpunk
st.markdown("""
<style>
    .reportview-container, .main { background-color: #050a14 !important; color: #00ffff !important; }
    h1, h2, h3, h4, h5, h6, label, p, span { color: #00ffff !important; font-family: 'Courier New', monospace !important; text-shadow: 0 0 8px rgba(0, 255, 255, 0.6); }
    .stButton>button {
        background-color: #0d1b2a !important; color: #00ffff !important; border: 2px solid #00ffff !important;
        box-shadow: 0 0 10px rgba(0, 255, 255, 0.4) !important; font-family: 'Courier New', monospace !important; 
        font-weight: bold !important; width: 100%; transition: all 0.3s ease-in-out;
    }
    .stButton>button:hover { background-color: #00ffff !important; color: #050a14 !important; box-shadow: 0 0 20px #00ffff !important; }
    .stTabs [data-baseweb="tab-list"] { background-color: #0d1b2a; border-radius: 4px; padding: 5px; }
    .stTabs [data-baseweb="tab"] { color: #ffffff !important; font-family: 'Courier New', monospace; }
    .stTabs [aria-selected="true"] { color: #00ffff !important; border-bottom: 2px solid #00ffff !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# CARREGADOR DE QUESTÕES COM SUPORTE A MÚLTIPLOS OBJETOS CONCATENADOS (STREAM)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=30)
def load_questions_db():
    questions = {}
    try:
        with open("json.json", "r", encoding="utf-8") as f:
            content = f.read().strip()
            
        decoder = json.JSONDecoder()
        idx = 0
        while idx < len(content):
            content = content[idx:].strip()
            if not content:
                break
            try:
                obj, consumed = decoder.raw_decode(content)
                idx += consumed
                for materia, lista in obj.items():
                    if materia not in questions:
                        questions[materia] = []
                    for q in lista:
                        # Deduplicação case-insensitive baseada no enunciado da pergunta
                        if not any(x['pergunta'].lower() == q['pergunta'].lower() for x in questions[materia]):
                            questions[materia].append(q)
            except json.JSONDecodeError:
                break
    except FileNotFoundError:
        pass
    return questions

questions_db = load_questions_db()

# ---------------------------------------------------------------------------
# GERENCIAMENTO DE ESTADO DA SESSÃO (SESSION STATE)
# ---------------------------------------------------------------------------
if "historico" not in st.session_state:
    st.session_state.historico = []
if "simulado_ativo" not in st.session_state:
    st.session_state.simulado_ativo = False
if "simulado_questoes" not in st.session_state:
    st.session_state.simulado_questoes = []
if "simulado_inicio" not in st.session_state:
    st.session_state.simulado_inicio = None
if "respostas_simulado" not in st.session_state:
    st.session_state.respostas_simulado = {}
if "treino_questoes" not in st.session_state:
    st.session_state.treino_questoes = []
if "vr_carregado" not in st.session_state:
    st.session_state.vr_carregado = False

# Contagem total de questões no banco
total_questoes_unicas = sum(len(lista) for lista in questions_db.values())

# ---------------------------------------------------------------------------
# MÓDULO 1: SIDEBAR CENTRAL DE CONTROLE
# ---------------------------------------------------------------------------
st.sidebar.title("🛡️ PMSC ARENA VR")
st.sidebar.markdown(f"**Banco de Dados:** `{total_questoes_unicas}` questões únicas.")

if st.sidebar.button("🔄 Recarregar Banco (json.json)"):
    load_questions_db.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🎯 Modo Treinamento")
materias_disponiveis = list(questions_db.keys()) if questions_db else ["Nenhuma cadastrada"]
materia_sel = st.sidebar.selectbox("Escolha a Matéria:", materias_disponiveis)
qtd_treino = st.sidebar.slider("Quantidade de questões:", 5, 20, 10)

if st.sidebar.button("⚔️ Iniciar Treino VR"):
    st.session_state.simulado_ativo = False
    if materia_sel in questions_db and questions_db[materia_sel]:
        pool = questions_db[materia_sel]
        st.session_state.treino_questoes = random.sample(pool, min(len(pool), qtd_treino))
        st.session_state.vr_carregado = False
    else:
        st.sidebar.error("Sem questões disponíveis para esta matéria.")

st.sidebar.markdown("---")
st.sidebar.header("📝 Simulado Oficial")
DISTRIBUICAO_EDITAL = {
    "Legislação Institucional": 10, "Direito Constitucional": 8, "Língua Portuguesa": 8,
    "Direito Penal Comum": 6, "Direito Processual Penal Comum": 6, "Direito Penal Militar": 6,
    "Legislação Especial": 6, "Legislação de Trânsito": 5, "Informática": 5
}

if st.sidebar.button("🚀 Iniciar Simulado 60q (AOCP)"):
    sim_pool = []
    for mat, qtd in DISTRIBUICAO_EDITAL.items():
        disponiveis = questions_db.get(mat, [])
        if len(disponiveis) < qtd:
            sim_pool.extend(disponiveis)
            outras = [q for m, l in questions_db.items() for q in l if q not in sim_pool]
            if outras:
                sim_pool.extend(random.sample(outras, min(len(outras), qtd - len(disponiveis))))
        else:
            sim_pool.extend(random.sample(disponiveis, qtd))
    
    if len(sim_pool) > 0:
        st.session_state.simulado_questoes = sim_pool[:60]
        st.session_state.simulado_ativo = True
        st.session_state.simulado_inicio = datetime.now()
        st.session_state.respostas_simulado = {}
        st.session_state.vr_carregado = False
    else:
        st.sidebar.error("Banco de dados insuficiente para gerar simulados.")

if st.session_state.simulado_ativo:
    if st.sidebar.button("🔴 Cancelar Simulado Atual"):
        st.session_state.simulado_ativo = False
        st.session_state.simulado_questoes = []
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("📊 Últimas Provas")
if st.session_state.historico:
    for h in st.session_state.historico[-5:]:
        status = "🟢 APROVADO" if h['aprovado'] else "🔴 REPROVADO"
        st.sidebar.markdown(f"**{h['data']}**<br>Nota: `{h['nota']:.1f}` ({h['acertos']}/60) -> {status}", unsafe_allow_html=True)
else:
    st.sidebar.info("Nenhum registro encontrado na sessão atual.")

# ---------------------------------------------------------------------------
# INTERFACE PRINCIPAL - DISTRIBUIÇÃO EM TABS
# ---------------------------------------------------------------------------
tab1, tab2 = st.tabs(["🌐 MÓDULO 2 & 3: Arena VR Imersiva", "📋 MÓDULO 7: Simulado Tradicional"])

with tab1:
    st.title("⚡ PMSC COGNITIVE ARENA 3D")
    st.write("Ambiente holográfico imersivo projetado para o Meta Quest Browser e navegadores Desktop convencionais.")

    safe_questions = st.session_state.simulado_questoes if st.session_state.simulado_ativo else st.session_state.treino_questoes

    if not safe_questions:
        st.info("Utilize as ferramentas do painel esquerdo (Sidebar) para injetar carga de questões na Arena.")
    else:
        if not st.session_state.vr_carregado:
            if st.button("🔌 INICIALIZAR RENDERIZADOR E CARREGAR ARENA 3D"):
                st.session_state.vr_carregado = True
                st.rerun()
        else:
            # Serialização segura das questões para injeção no JS do A-Frame
            q_json = json.dumps(safe_questions, ensure_ascii=False)
            modo_str = "SIMULADO" if st.session_state.simulado_ativo else "TREINAMENTO"
            
            # Matriz pura de texto (raw string literal) mitigando erros de interpolação por chaves do JS/CSS
            html_content = r"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>PMSC Arena VR</title>
    <script src="https://aframe.io"></script>
    <script src="https://jsdelivr.net"></script>
    <style>
        .vr-hud-overlay {
            position: absolute; top: 12px; left: 12px; background: rgba(5,10,20,0.9);
            color: #00ffff; padding: 15px; font-family: 'Courier New', monospace; border: 2px solid #00ffff;
            border-radius: 4px; mountaineering: none; z-index: 9999; pointer-events: none; box-shadow: 0 0 10px #00ffff;
        }
    </style>
</head>
<body>
    <div class="vr-hud-overlay">
        <div>📡 NETCORE: SYSTEM PMSC ARENA VR</div>
        <div id="hud-modo">MODO: __MODO__</div>
        <div id="hud-stats">PROGRESSO: 0 / __LEN__</div>
        <div id="hud-last-action">🎯 TELEMETRIA PRONTA. AGUARDANDO COMANDO...</div>
    </div>

    <script>
        // Carga ativa de dados injetada via template replace
        const questoesData = __Q_JSON__;
        let respondidasCount = 0;

        // MÓDULO 3.1 & 3.3 & 7.1: Sistema Avançado de Tracking e Interação Remota Customizada
        AFRAME.registerComponent('vr-hand', {
            schema: {
                hand: {type: 'string', default: 'right'}
            },
            init: function() {
                this.raycaster = new THREE.Raycaster();
                this.raycaster.far = 100; 
                this.currentGrab = null;
                this.currentClick = null;
                this.grabOffset = new THREE.Vector3();
                this.grabDistance = 0;

