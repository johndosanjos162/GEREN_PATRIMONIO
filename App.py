import datetime
import json
import re
import streamlit as st
from PIL import Image

# Configuração de Página Inicial de Alta Performance
st.set_page_config(
    page_title="PMSC ARENA VR",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização HUD Futurista / Interface Ciborgue via CSS Customizado
st.markdown("""
<style>
    @import url('https://googleapis.com');
    
    .reportview-container, .main, .block-container {
        background-color: #060913 !important;
        color: #e2e8f0 !important;
        font-family: 'Rajdhani', sans-serif !important;
    }
    h1, h2, h3, .stHeader {
        font-family: 'Orbitron', sans-serif !important;
        color: #00f0ff !important;
        text-shadow: 0 0 10px rgba(0, 240, 255, 0.4);
    }
    .stButton>button {
        background: linear-gradient(135deg, #00f0ff 0%, #7000ff 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 4px !important;
        font-family: 'Orbitron', sans-serif !important;
        font-weight: bold !important;
        box-shadow: 0 0 15px rgba(0, 240, 255, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    .stButton>button:hover {
        transform: scale(1.03) !important;
        box-shadow: 0 0 25px rgba(112, 0, 255, 0.6) !important;
    }
    .sidebar .sidebar-content {
        background-color: #0b1122 !important;
        border-right: 1px solid #00f0ff33 !important;
    }
</style>
""", unsafe_allow_html=True)

# Inicialização Limpa do State
if "historico" not in st.session_state:
    st.session_state.historico = []
if "modo" not in st.session_state:
    st.session_state.modo = "Treino"
if "questoes_ativas" not in st.session_state:
    st.session_state.questoes_ativas = []
if "simulado_iniciado" not in st.session_state:
    st.session_state.simulado_iniciado = False
if "simulado_respostas" not in st.session_state:
    st.session_state.simulado_respostas = {}
if "simulado_start_time" not in st.session_state:
    st.session_state.simulado_start_time = None
if "vr_carregado" not in st.session_state:
    st.session_state.vr_carregado = False

# Carregador Avançado de Fluxo de Objetos JSON Concatenados (Deduplicador Amigável)
@st.cache_data(ttl=30)
def carregar_banco_questoes():
    banco_unificado = {}
    try:
        with open("json.json", "r", encoding="utf-8") as f:
            conteudo = f.read().strip()
        
        decoder = json.JSONDecoder()
        idx = 0
        tamanho = len(conteudo)
        
        while idx < tamanho:
            conteudo_restante = conteudo[idx:].strip()
            if not conteudo_restante:
                break
            try:
                obj, consumido = decoder.raw_decode(conteudo_restante)
                for materia, lista_q in obj.items():
                    if materia not in banco_unificado:
                        banco_unificado[materia] = []
                    banco_unificado[materia].extend(lista_q)
                idx += conteudo.find(conteudo_restante) + consumido
            except json.JSONDecodeError:
                # Se falhar no raw_decode estruturado, tenta varredura fall-back pura
                try:
                    obj_simples = json.loads(conteudo)
                    for materia, lista_q in obj_simples.items():
                        if materia not in banco_unificado:
                            banco_unificado[materia] = []
                        banco_unificado[materia].extend(lista_q)
                except Exception:
                    pass
                break
        
        # Deduplicação rigorosa por string da pergunta (Case-Insensitive)
        for materia in banco_unificado:
            vistas = set()
            filtradas = []
            for q in banco_unificado[materia]:
                txt_limpo = re.sub(r'\s+', '', q.get("pergunta", "")).lower()
                if txt_limpo not in vistas and q.get("pergunta"):
                    vistas.add(txt_limpo)
                    filtradas.append(q)
            banco_unificado[materia] = filtradas
            
    except Exception as e:
        st.sidebar.error(f"Erro Crítico ao ler arquivo de dados: {e}")
    return banco_unificado

banco = carregar_banco_questoes()

# Contagem Global Módulo 1
total_questoes_banco = sum(len(lista) for lista in banco.values())

# SIDEBAR - MÓDULO 1
st.sidebar.title("🛡️ PMSC ARENA VR")
st.sidebar.markdown(f"**Total de Questões Únicas:** `{total_questoes_banco}`")

if st.sidebar.button("⚡ Recarregar json.json"):
    carregar_banco_questoes.clear()
    st.toast("Banco sincronizado e recarregado!", icon="🔄")

st.sidebar.markdown("---")

materias_disponiveis = list(banco.keys()) if banco else ["Nenhuma matéria localizada"]
materia_sel = st.sidebar.selectbox("Matéria de Estudo (Treino)", materias_disponiveis)
qtd_treino = st.sidebar.slider("Quantidade de Questões", 5, 20, 10)

col_b1, col_b2 = st.sidebar.columns(2)
with col_b1:
    if st.button("🎯 Iniciar Treino"):
        if banco and materia_sel in banco:
            lista_original = banco[materia_sel]
            st.session_state.questoes_ativas = lista_original[:qtd_treino]
            st.session_state.modo = "Treino"
            st.session_state.simulado_iniciado = False
            st.session_state.vr_carregado = False
            st.toast("Grade de Treino gerada!", icon="🔥")
with col_b2:
    if st.button("📝 Iniciar Simulado"):
        # Distribuição de Edital Oficial AOCP
        distribuicao = {
            "Legislação Institucional": 10, "Direito Constitucional": 8,
            "Língua Portuguesa": 8, "Direito Penal Comum": 6,
            "Direito Processual Penal Comum": 6, "Direito Penal Militar": 6,
            "Legislação Especial": 6, "Legislação de Trânsito": 5, "Informática": 5
        }
        pool_simulado = []
        for mat, qtd in distribuicao.items():
            lista_q = banco.get(mat, [])
            pool_simulado.extend(lista_q[:qtd])
        
        if len(pool_simulado) > 0:
            st.session_state.questoes_ativas = pool_simulado[:60]
            st.session_state.simulado_respostas = {}
            st.session_state.simulado_start_time = datetime.datetime.now()
            st.session_state.simulado_iniciado = True
            st.session_state.modo = "Simulado"
            st.session_state.vr_carregado = False
            st.toast("Simulado de 60 questões carregado!", icon="⚔️")

if st.session_state.simulado_iniciado:
    if st.sidebar.button("❌ Cancelar Simulado Atual"):
        st.session_state.simulado_iniciado = False
        st.session_state.questoes_ativas = []
        st.session_state.modo = "Treino"
        st.session_state.vr_carregado = False

# Histórico Recente (Persistente na Sessão)
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Histórico de Performance (Últimas 5)")
if st.session_state.historico:
    for h in reversed(st.session_state.historico[-5:]):
        status_txt = "🟢 APROVADO" if h['aprovado'] else "🔴 REPROVADO"
        st.sidebar.markdown(f"**{h['data']}** | {h['modo']}\nAcertos: {h['acertos']} | Nota: {h['nota']:.1f}% \n`{status_txt}`")
else:
    st.sidebar.caption("Nenhum registro localizado nesta sessão.")

# DIVISÃO DE ABAS PRINCIPAIS
tab_vr, tab_classico = st.tabs(["🎮 ARENA IMERSIVA VR", "📋 SIMULADO MODO CLÁSSICO"])

# MÓDULO 2 - FUNÇÃO DE RENDERIZAÇÃO DO FRAME A-FRAME
def render_vr(questoes):
    # Serialização limpa em formato string JSON para o motor JS interno
    lista_limpa = []
    for idx, q in enumerate(questoes):
        lista_limpa.append({
            "id": idx,
            "materia": q.get("materia", "PMSC Concurso"),
            "pergunta": q.get("pergunta", "").replace('"', '&quot;'),
            "alternativas": [alt.replace('"', '&quot;') for alt in q.get("alternativas", [])],
            "correta": q.get("correta", "A")
        })
    q_json_str = json.dumps(lista_limpa)

    # Motor 3D Robusto via Template String Puro (Sem f-strings para evitar quebra de CSS)
    html_template = r"""
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="utf-8">
        <title>PMSC Arena VR Engine</title>
        <script src="https://aframe.io"></script>
        <script src="https://jsdelivr.net"></script>
        <script>
          // Componente customizado de alta fidelidade para tracking e física virtual sem conflito super-hands
          AFRAME.registerComponent('vr-hand', {
            schema: {
              hand: {type: 'string', default: 'right'}
            },
            init: function () {
              this.raycaster = new THREE.Raycaster();
              this.raycaster.far = 100; // Alcance estendido para seleção fluida
              this.currentGrab = null;
              this.currentClick = null;
              this.offset = new THREE.Vector3();
              this.ajusteThumbstick = 0;
              
              this.el.addEventListener('gripdown', this.onGripDown.bind(this));
              this.el.addEventListener('gripup', this.onGripUp.bind(this));
              this.el.addEventListener('triggerdown', this.onTriggerDown.bind(this));
              this.el.addEventListener('thumbstickmoved', this.onThumbstickMoved.bind(this));
              
              // Hand Tracking nativo do Meta Quest (Pinch Eventos)
              this.el.addEventListener('pinchstarted', this.onGripDown.bind(this));
              this.el.addEventListener('pinchended', this.onGripUp.bind(this));
            },
            tick: function () {
              // Executa o raycast manual preciso a cada ciclo de renderização
              var origin = new THREE.Vector3();
              var direction = new THREE.Vector3();
              var matrix = new THREE.Matrix4();
              
              matrix.extractRotation(this.el.object3D.matrixWorld);
