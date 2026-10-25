import streamlit as st
import hashlib
import hmac
import os
import logging
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime
from io import BytesIO
from supabase import create_client, Client

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

st.set_page_config(page_title="Invest Control Pro", page_icon="🛡", layout="wide", initial_sidebar_state="expanded", menu_items={"About": "Invest Control Pro · Painel financeiro pessoal"})

logger = logging.getLogger("invest_control_pro")

def validar_acesso(usuario, senha):
    """Credenciais configuráveis em Secrets/ambiente, com compatibilidade de acesso anterior."""
    usuario_config = st.secrets.get("APP_USERNAME", os.getenv("APP_USERNAME", "JOHN"))
    senha_config = st.secrets.get("APP_PASSWORD", os.getenv("APP_PASSWORD", ""))
    senha_hash = st.secrets.get("APP_PASSWORD_SHA256", os.getenv("APP_PASSWORD_SHA256", ""))
    if senha_config:
        valido = hmac.compare_digest(senha, str(senha_config))
    else:
        esperado = str(senha_hash) if senha_hash else "e35fa295cd07fb94e466261ca69816b4267ca07418ee832ce5c295ea329df20d"
        valido = hmac.compare_digest(hashlib.sha256(senha.encode()).hexdigest(), esperado)
    return hmac.compare_digest(usuario, str(usuario_config)) and valido


PALETA = {
    "fundo_principal":"#0A0E14","fundo_sidebar":"#0D1219","fundo_card":"#131A23",
    "fundo_hover":"#1B232E","borda":"#1F2937","borda_acento":"#3B82F6",
    "texto_principal":"#E8EEF5","texto_secundario":"#8A95A5",
    "acento":"#3B82F6","acento_hover":"#2563EB","acento_glow":"rgba(59,130,246,0.25)",
    "verde":"#22C55E","verde_bg":"rgba(34,197,94,0.12)","vermelho":"#EF4444",
    "vermelho_bg":"rgba(239,68,68,0.12)","amarelo":"#F59E0B","amarelo_bg":"rgba(245,158,11,0.12)",
    "roxo":"#8B5CF6","ciano":"#06B6D4",
}

st.markdown(f"""
<style>
.stApp {{ background: radial-gradient(circle at 15% 0%, rgba(59,130,246,0.06), transparent 45%), radial-gradient(circle at 85% 100%, rgba(139,92,246,0.05), transparent 45%), {PALETA["fundo_principal"]}; color: {PALETA["texto_principal"]}; font-family: 'Segoe UI','Inter',sans-serif; }}
html, body, [class*="css"] {{ font-family: 'Segoe UI','Inter',sans-serif; color: {PALETA["texto_principal"]}; }}
h1 {{ color: {PALETA["texto_principal"]} !important; font-weight: 700 !important; letter-spacing: -0.5px !important; font-size: 30px !important; }}
h2, h3 {{ color: {PALETA["texto_principal"]} !important; font-weight: 600 !important; }}
h4, h5 {{ color: {PALETA["texto_secundario"]} !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: 1.2px; font-size: 11px !important; }}
p, span, label {{ color: {PALETA["texto_principal"]}; }}
[data-testid="stCaptionContainer"] {{ color: {PALETA["texto_secundario"]} !important; font-size: 12px !important; }}
section[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {PALETA["fundo_sidebar"]} 0%, {PALETA["fundo_principal"]} 100%); border-right: 1px solid {PALETA["borda"]}; }}
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {{ color: {PALETA["texto_principal"]} !important; border-bottom: 1px solid {PALETA["borda"]}; padding-bottom: 10px; margin-bottom: 12px; }}
section[data-testid="stSidebar"] hr {{ border-color: {PALETA["borda"]} !important; margin: 16px 0 !important; }}
div[data-testid="stMetric"] {{ background: linear-gradient(145deg, {PALETA["fundo_card"]} 0%, {PALETA["fundo_sidebar"]} 100%); border: 1px solid {PALETA["borda"]}; border-radius: 14px; padding: 20px 22px !important; box-shadow: 0 4px 24px -8px rgba(0,0,0,0.5); transition: all 0.25s ease; position: relative; overflow: hidden; }}
div[data-testid="stMetric"]::before {{ content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, {PALETA["acento"]}, transparent); opacity: 0.6; }}
div[data-testid="stMetric"]:hover {{ border-color: {PALETA["borda_acento"]}; box-shadow: 0 0 0 1px {PALETA["acento_glow"]}, 0 8px 32px -8px rgba(59,130,246,0.35); transform: translateY(-2px); }}
div[data-testid="stMetric"] label {{ color: {PALETA["texto_secundario"]} !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{ color: {PALETA["texto_principal"]} !important; font-family: 'Consolas','JetBrains Mono',monospace !important; font-size: 26px !important; font-weight: 700 !important; }}
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{ background: {PALETA["fundo_card"]} !important; color: {PALETA["texto_principal"]} !important; border: 1px solid {PALETA["borda"]} !important; border-radius: 10px !important; padding: 10px 18px !important; font-weight: 600 !important; font-size: 13px !important; transition: all 0.2s ease !important; }}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {{ background: {PALETA["acento"]} !important; border-color: {PALETA["acento"]} !important; color: #FFFFFF !important; box-shadow: 0 0 20px {PALETA["acento_glow"]}; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; background: {PALETA["fundo_card"]}; padding: 6px; border-radius: 12px; border: 1px solid {PALETA["borda"]}; flex-wrap: wrap; }}
.stTabs [data-baseweb="tab"] {{ height: 40px; background: transparent !important; border-radius: 8px !important; color: {PALETA["texto_secundario"]} !important; font-weight: 600; font-size: 13px; padding: 0 16px; }}
.stTabs [aria-selected="true"] {{ background: {PALETA["acento"]} !important; color: #FFFFFF !important; box-shadow: 0 0 16px {PALETA["acento_glow"]}; }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none !important; }}
.stTextInput input, .stNumberInput input, .stDateInput input, div[data-baseweb="select"] > div {{ background: {PALETA["fundo_principal"]} !important; color: {PALETA["texto_principal"]} !important; border: 1px solid {PALETA["borda"]} !important; border-radius: 10px !important; font-size: 13px !important; }}
.stTextInput input:focus, .stNumberInput input:focus, .stDateInput input:focus {{ border-color: {PALETA["acento"]} !important; box-shadow: 0 0 0 3px {PALETA["acento_glow"]} !important; }}
label[data-testid="stWidgetLabel"] p {{ color: {PALETA["texto_secundario"]} !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600; }}
div[data-testid="stExpander"] {{ background: {PALETA["fundo_card"]}; border: 1px solid {PALETA["borda"]} !important; border-radius: 12px !important; }}
div[data-testid="stExpander"] summary {{ font-weight: 600 !important; color: {PALETA["texto_principal"]} !important; padding: 14px 18px !important; }}
div[data-testid="stAlert"] {{ border-radius: 12px !important; border-left-width: 4px !important; font-size: 13px !important; }}
div[data-testid="stAlert"][data-baseweb="notification"] {{ background: {PALETA["fundo_card"]} !important; }}
.stDataFrame, div[data-testid="stTable"] {{ background: {PALETA["fundo_card"]} !important; border-radius: 12px !important; border: 1px solid {PALETA["borda"]} !important; }}
div[data-testid="stTable"] thead tr th {{ background: {PALETA["fundo_sidebar"]} !important; color: {PALETA["texto_secundario"]} !important; text-transform: uppercase; letter-spacing: 1px; font-size: 11px !important; font-weight: 700 !important; border-bottom: 1px solid {PALETA["borda"]} !important; padding: 12px !important; }}
div[data-testid="stTable"] tbody tr:nth-child(even) {{ background: rgba(31,41,55,0.25) !important; }}
.stProgress > div > div > div > div {{ background: linear-gradient(90deg, {PALETA["acento"]}, {PALETA["ciano"]}) !important; border-radius: 999px !important; }}
.stProgress > div > div > div {{ background: {PALETA["fundo_card"]} !important; border-radius: 999px !important; height: 8px !important; }}
.stCheckbox label span, .stRadio label span {{ color: {PALETA["texto_principal"]} !important; font-size: 13px !important; }}
hr {{ border: none !important; height: 1px !important; background: linear-gradient(90deg, transparent, {PALETA["borda"]}, transparent) !important; margin: 20px 0 !important; }}
div[data-testid="stForm"] {{ background: {PALETA["fundo_card"]}; border: 1px solid {PALETA["borda"]}; border-radius: 14px; padding: 20px !important; }}
::-webkit-scrollbar {{ width: 8px; height: 8px; }} ::-webkit-scrollbar-track {{ background: {PALETA["fundo_principal"]}; }}
::-webkit-scrollbar-thumb {{ background: {PALETA["borda"]}; border-radius: 999px; }}
.login-title {{ background: linear-gradient(90deg, {PALETA["acento"]}, {PALETA["ciano"]}); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: 1px; }}

/* ===== Camada visual 2026: acessibilidade, leitura e responsividade ===== */
.block-container {{ max-width: 1680px; padding-top: 1.3rem; padding-bottom: 3rem; }}
section[data-testid="stSidebar"] {{ min-width: 275px; }}
section[data-testid="stSidebar"] .stButton button {{ width: 100%; }}
div[data-testid="stMetric"] {{ min-height: 119px; }}
div[data-testid="stMetricValue"] {{ overflow-wrap: anywhere; }}
.stTabs [data-baseweb="tab-list"] {{
    flex-wrap: nowrap !important; overflow-x: auto; overflow-y: hidden;
    scrollbar-width: thin; scroll-snap-type: x proximity;
    position: sticky; top: 2.75rem; z-index: 20;
    background: #111923 !important; padding: 7px !important;
}}
.stTabs [data-baseweb="tab"] {{ flex: 0 0 auto; scroll-snap-align: start; white-space: nowrap; min-height: 45px; }}
.stTabs [data-baseweb="tab-panel"] {{ padding-top: 1.2rem; }}
[data-testid="stDataFrame"] {{ overflow: hidden; }}
[data-testid="stDataFrame"] [role="grid"] {{ font-size: 13px; }}
[data-testid="stVerticalBlock"] > div {{ min-width: 0; }}
input, textarea {{ font-size: 15px !important; }}
button:focus-visible, input:focus-visible {{ outline: 2px solid #38BDF8 !important; outline-offset: 2px; }}
.stButton > button[kind="primary"] {{ background: #2563EB !important; border-color: #2563EB !important; }}
.invest-eyebrow {{ color: #93A4B8; text-transform: uppercase; font-size: 0.72rem; letter-spacing: 0.13em; font-weight: 750; }}
.invest-heading {{ font-size: clamp(1.6rem, 2.6vw, 2.2rem); font-weight: 760; line-height: 1.2; margin: 5px 0; }}
.invest-subheading {{ color: #AAB8C9; font-size: 0.93rem; margin-bottom: 1.15rem; }}
.invest-status {{ font-size: 0.8rem; color: #9FB0C6; border: 1px solid #263347; padding: 7px 12px; border-radius: 10px; display: inline-block; margin-bottom: 8px; }}
@media (max-width: 900px) {{
 .block-container {{ padding: 0.8rem 1rem 2rem; }}
 div[data-testid="stMetric"] {{ min-height: 105px; padding: 12px !important; }}
 div[data-testid="stMetricValue"] {{ font-size: 20px !important; }}
 .stTabs [data-baseweb="tab-list"] {{ top: 0; }}
}}
@media (prefers-reduced-motion: reduce) {{
 *, *::before, *::after {{ transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; }}
}}

</style>
""", unsafe_allow_html=True)

if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

meses_nomes = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
for i, m in enumerate(meses_nomes):
    if f"reserva_mes_{i+1}" not in st.session_state:
        st.session_state[f"reserva_mes_{i+1}"] = False

# =============================================================================
# LOGIN
# =============================================================================
if not st.session_state['autenticado']:
    col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
    with col_l2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown('<div class="login-title" style="font-size:28px;font-weight:700;text-align:center;margin-bottom:10px;">🛡️ INVEST CONTROL PRO</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:14px;color:#8A95A5;text-align:center;margin-bottom:30px;">Sistema Integrado de Projeção Econômica & Acesso Seguro</div>', unsafe_allow_html=True)
        with st.form("form_login"):
            st.markdown("### Credenciais de Acesso")
            usuario = st.text_input("Usuário / Credencial", placeholder="Digite seu usuário...")
            senha = st.text_input("Senha de Acesso", type="password", placeholder="Digite sua senha...")
            st.markdown("---")
            if st.form_submit_button("Acessar Sistema", use_container_width=True):
                if validar_acesso(usuario, senha):
                    st.session_state['autenticado'] = True
                    st.rerun()
                else:
                    st.error("❌ Credenciais inválidas.")
        st.caption("🔐 Acesso autenticado. Configure APP_USERNAME e APP_PASSWORD nos Secrets para substituir as credenciais antigas.")
        st.stop()

@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    return create_client(url, key) if url and key else None

supabase = init_supabase()
if not supabase and st.session_state.get("autenticado"):
    st.sidebar.warning("Supabase não configurado: consultas podem usar valores demonstrativos e alterações não serão persistidas.")

def _fmt_brl(v):
    try: return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

# CDI
@st.cache_data(ttl=3600)
def obter_taxa_cdi_atual():
    try:
        url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados/ultimos/1?formato=json"
        r = requests.get(url, timeout=10); r.raise_for_status()
        dados = r.json()
        return float(dados[-1]['valor']) if dados else None
    except Exception: return None

@st.cache_data(ttl=3600)
def obter_historico_cdi(dias=30):
    try:
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados/ultimos/{dias}?formato=json"
        r = requests.get(url, timeout=10); r.raise_for_status()
        dados = r.json()
        if dados:
            df = pd.DataFrame(dados)
            df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
            df['valor'] = df['valor'].astype(float)
            return df
        return pd.DataFrame()
    except Exception: return pd.DataFrame()

def calcular_projecao_cdi(aporte_inicial, aporte_mensal, anos, percentual_cdi, cdi_anual):
    if percentual_cdi <= 0 or cdi_anual <= 0: return None
    cdi_mensal = (1 + cdi_anual / 100) ** (1 / 12) - 1
    taxa_efetiva = cdi_mensal * (percentual_cdi / 100)
    meses = anos * 12
    montante = float(aporte_inicial); investido = float(aporte_inicial); dados = []
    for m in range(1, meses + 1):
        montante = montante * (1 + taxa_efetiva) + aporte_mensal
        investido += aporte_mensal
        if m % 12 == 0:
            dados.append({"Ano": m // 12, "Patrimônio Total": round(montante, 2),
                           "Total Investido": round(investido, 2),
                           "Juros Acumulados": round(montante - investido, 2)})
    return {"montante_final": round(montante, 2), "total_investido": round(investido, 2),
            "juros_totais": round(montante - investido, 2),
            "taxa_mensal_efetiva": round(taxa_efetiva * 100, 4),
            "dados_evolucao": pd.DataFrame(dados)}

def gerar_grafico_projecao_cdi(df_evolucao, aporte_inicial, aporte_mensal):
    df = df_evolucao.copy()
    df["Sem Rendimento"] = aporte_inicial + (df["Ano"] * 12 * aporte_mensal)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Ano"], y=df["Patrimônio Total"], mode="lines+markers",
                              name="Com CDI", line=dict(color="#22C55E", width=3),
                              fill="tozeroy", fillcolor="rgba(34,197,94,0.15)"))
    fig.add_trace(go.Scatter(x=df["Ano"], y=df["Sem Rendimento"], mode="lines+markers",
                              name="Sem Rendimento", line=dict(color="#EF4444", width=2, dash="dash")))
    fig.update_layout(paper_bgcolor="#151B23", plot_bgcolor="#151B23", font_color="#E6EDF3",
                       xaxis_title="Anos", yaxis_title="Valor (R$)", legend_title="Cenário",
                       margin=dict(l=20, r=20, t=30, b=20))
    return fig

# DADOS
def carregar_configuracoes():
    if supabase:
        try:
            res = supabase.table("configuracoes").select("*").eq("id", 1).execute()
            if res.data: return res.data[0]
        except: pass
    return {"aluguel_total":1700.0,"salario_a":2700.0,"salario_b":2000.0,"vr_a":700.0,
            "meta_reserva_mensal":800.0,"aluguel_a_custom":850.0,"aluguel_b_custom":850.0,"usa_edicao_manual":False}

def salvar_configuracoes(a, sa, sb, vr, mr, ac, bc, ue):
    if supabase:
        try:
            supabase.table("configuracoes").update({"aluguel_total":a,"salario_a":sa,"salario_b":sb,
                "vr_a":vr,"meta_reserva_mensal":mr,"aluguel_a_custom":ac,"aluguel_b_custom":bc,"usa_edicao_manual":ue}).eq("id",1).execute()
        except: pass

def carregar_gastos_fixos():
    if supabase:
        try:
            res = supabase.table("gastos_fixos").select("*").execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
    return pd.DataFrame([{"id":1,"descricao":"Internet","valor":100.0},{"id":2,"descricao":"Recarga celular","valor":30.0},
                          {"id":3,"descricao":"Corte de cabelo","valor":90.0},{"id":4,"descricao":"Cartão de crédito","valor":49.0}])

def adicionar_gasto_fixo(d, v):
    if supabase:
        try: supabase.table("gastos_fixos").insert({"descricao":d,"valor":v}).execute()
        except: pass

def remover_gasto_fixo(i):
    if supabase:
        try: supabase.table("gastos_fixos").delete().eq("id",i).execute()
        except: pass

def carregar_despesas_variaveis():
    if supabase:
        try:
            res = supabase.table("despesas_variaveis").select("*").order("data", desc=True).execute()
            if res.data:
                df = pd.DataFrame(res.data); df['data'] = pd.to_datetime(df['data']); return df
        except: pass
    return pd.DataFrame(columns=["id","data","descricao","categoria","valor"])

def adicionar_despesa_variavel(data, descricao, categoria, valor):
    if supabase:
        try:
            dfmt = str(data) if hasattr(data, "strftime") else data
            supabase.table("despesas_variaveis").insert({"data":dfmt,"descricao":str(descricao).strip(),
                "categoria":str(categoria).strip(),"valor":float(valor)}).execute()
        except Exception as e: st.error(f"Erro: {e}")

def remover_despesa_variavel(i):
    if supabase:
        try: supabase.table("despesas_variaveis").delete().eq("id",i).execute()
        except: pass

def carregar_orcamento_mes(mes, ano):
    if supabase:
        try:
            res = supabase.table("orcamentos_mensais").select("*").eq("mes",mes).eq("ano",ano).execute()
            if res.data: return res.data[0]
            novo = {"mes":mes,"ano":ano,"orcamento":0.0,"fechado":False}
            r2 = supabase.table("orcamentos_mensais").insert(novo).execute()
            if r2.data: return r2.data[0]
        except: pass
    return {"mes":mes,"ano":ano,"orcamento":0.0,"fechado":False}

def salvar_orcamento_mes(mes, ano, v):
    if supabase:
        try:
            ex = supabase.table("orcamentos_mensais").select("id").eq("mes",mes).eq("ano",ano).execute()
            if ex.data:
                supabase.table("orcamentos_mensais").update({"orcamento":float(v)}).eq("id",ex.data[0]["id"]).execute()
            else:
                supabase.table("orcamentos_mensais").insert({"mes":mes,"ano":ano,"orcamento":float(v),"fechado":False}).execute()
        except: pass

def fechar_mes(mes, ano):
    if supabase:
        try: supabase.table("orcamentos_mensais").update({"fechado":True}).eq("mes",mes).eq("ano",ano).execute()
        except: pass

def carregar_despesas_por_mes(mes, ano):
    if supabase:
        try:
            res = supabase.table("despesas_variaveis").select("*").order("data", desc=True).execute()
            if res.data:
                df = pd.DataFrame(res.data); df['data'] = pd.to_datetime(df['data'])
                return df[(df['data'].dt.month==mes)&(df['data'].dt.year==ano)]
        except: pass
    return pd.DataFrame(columns=["id","data","descricao","categoria","valor"])

def listar_meses_fechados():
    if supabase:
        try:
            res = supabase.table("orcamentos_mensais").select("*").order("ano", desc=True).order("mes", desc=True).execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
    return pd.DataFrame(columns=["id","mes","ano","orcamento","fechado"])

# CORTES
def carregar_metas_corte():
    if supabase:
        try:
            res = supabase.table("metas_corte").select("*").eq("ativo", True).execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
    return pd.DataFrame(columns=["id","categoria","meta_reducao_pct","ativo"])

def salvar_meta_corte(cat, pct):
    if supabase:
        try:
            ex = supabase.table("metas_corte").select("id").eq("categoria",cat).execute()
            if ex.data:
                supabase.table("metas_corte").update({"meta_reducao_pct":float(pct),"ativo":True,
                    "atualizado_em":datetime.now().isoformat()}).eq("categoria",cat).execute()
            else:
                supabase.table("metas_corte").insert({"categoria":cat,"meta_reducao_pct":float(pct),"ativo":True}).execute()
        except: pass

def remover_meta_corte(cat):
    if supabase:
        try: supabase.table("metas_corte").update({"ativo":False}).eq("categoria",cat).execute()
        except: pass

def salvar_analise_corte(mes, ano, sug):
    if supabase and sug:
        try:
            supabase.table("analises_corte").insert([{"mes":int(mes),"ano":int(ano),
                "categoria":s["categoria_limpa"],"valor_atual":float(s["valor_atual"]),
                "valor_sugerido":float(s["corte_sugerido"]),"economia_potencial":float(s["economia_potencial"]),
                "prioridade":int(s["prioridade"])} for s in sug]).execute()
        except: pass

def carregar_historico_analises():
    if supabase:
        try:
            res = supabase.table("analises_corte").select("*").order("criado_em", desc=True).limit(100).execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
    return pd.DataFrame(columns=["id","mes","ano","categoria","valor_atual","valor_sugerido",
                                  "economia_potencial","prioridade","criado_em"])

def marcar_corte_concluido(cat, ve, mes, ano):
    if supabase:
        try:
            supabase.table("cortes_concluidos").insert({"categoria":cat,"valor_economia":float(ve),
                "mes":int(mes),"ano":int(ano),"concluido_em":datetime.now().isoformat()}).execute()
        except: pass

def carregar_cortes_concluidos():
    if supabase:
        try:
            res = supabase.table("cortes_concluidos").select("*").order("concluido_em", desc=True).execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
    return pd.DataFrame(columns=["id","categoria","valor_economia","mes","ano","concluido_em"])

def remover_corte_concluido(i):
    if supabase:
        try: supabase.table("cortes_concluidos").delete().eq("id",i).execute()
        except: pass

def gerar_checklist_semanal(df_sug, df_cc):
    if df_sug.empty: return []
    cc = df_cc['categoria'].tolist() if not df_cc.empty else []
    return [{"categoria":s['categoria_limpa'],"acao":f"Reduzir gastos em {s['categoria_limpa']}",
             "economia":float(s['corte_sugerido'])} for _, s in df_sug.iterrows() if s['categoria_limpa'] not in cc]

def salvar_checklist_semanal(tarefas, semana):
    if supabase and tarefas:
        try:
            supabase.table("checklist_semanal").insert([{"categoria":t["categoria"],"acao":t["acao"],
                "economia_estimada":t["economia"],"semana":semana,"concluida":False} for t in tarefas]).execute()
        except: pass

def carregar_checklist_semana(semana):
    if supabase:
        try:
            res = supabase.table("checklist_semanal").select("*").eq("semana",semana).execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
    return pd.DataFrame(columns=["id","categoria","acao","economia_estimada","concluida","semana"])

def marcar_item_checklist(i, c=True):
    if supabase:
        try: supabase.table("checklist_semanal").update({"concluida":c}).eq("id",i).execute()
        except: pass

# SIMULADOR
def salvar_simulacao_investimento(nome, aporte, anos, taxa, montante, investido, juros,
                                    cdi_taxa=None, aporte_inicial=None):
    if supabase:
        try:
            dados = {"nome":str(nome).strip(),"aporte_mensal":float(aporte),"anos":int(anos),
                     "taxa_anual":float(taxa),"montante_final":float(montante),
                     "total_investido":float(investido),"juros_totais":float(juros)}
            if cdi_taxa is not None: dados["cdi_taxa_utilizada"] = float(cdi_taxa)
            if aporte_inicial is not None:
                try: dados["aporte_inicial"] = float(aporte_inicial)
                except: pass
            supabase.table("simulacoes_investimento").insert(dados).execute()
            return True
        except Exception as e:
            st.error(f"Erro: {e}"); return False
    return False

def carregar_simulacoes_investimento():
    if supabase:
        try:
            res = supabase.table("simulacoes_investimento").select("*").order("criado_em", desc=True).execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
    return pd.DataFrame(columns=["id","nome","aporte_mensal","anos","taxa_anual","montante_final",
                                  "total_investido","juros_totais","criado_em"])

def remover_simulacao_investimento(i):
    if supabase:
        try: supabase.table("simulacoes_investimento").delete().eq("id",i).execute()
        except: pass

# PROSPERIDADE
def carregar_ativos():
    if supabase:
        try:
            res = supabase.table("ativos").select("*").order("valor", desc=True).execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
    return pd.DataFrame(columns=["id","nome","categoria","valor"])

def adicionar_ativo(n, c, v):
    if supabase:
        try: supabase.table("ativos").insert({"nome":str(n).strip(),"categoria":c,"valor":float(v)}).execute()
        except: pass

def remover_ativo(i):
    if supabase:
        try: supabase.table("ativos").delete().eq("id",i).execute()
        except: pass

def carregar_passivos():
    if supabase:
        try:
            res = supabase.table("passivos").select("*").order("valor_total", desc=True).execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
    return pd.DataFrame(columns=["id","nome","tipo","valor_total","parcelas_restantes","juros_mensal"])

def adicionar_passivo(n, t, v, p, j):
    if supabase:
        try: supabase.table("passivos").insert({"nome":str(n).strip(),"tipo":t,"valor_total":float(v),
            "parcelas_restantes":int(p),"juros_mensal":float(j)}).execute()
        except: pass

def remover_passivo(i):
    if supabase:
        try: supabase.table("passivos").delete().eq("id",i).execute()
        except: pass

def carregar_carteira():
    if supabase:
        try:
            res = supabase.table("carteira_invest").select("*").order("valor_atual", desc=True).execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
    return pd.DataFrame(columns=["id","ativo","classe","valor_investido","valor_atual","data_aporte"])

def adicionar_investimento(a, c, vi, va, da):
    if supabase:
        try: supabase.table("carteira_invest").insert({"ativo":str(a).strip(),"classe":c,
            "valor_investido":float(vi),"valor_atual":float(va),"data_aporte":str(da)}).execute()
        except: pass

def remover_investimento(i):
    if supabase:
        try: supabase.table("carteira_invest").delete().eq("id",i).execute()
        except: pass

def carregar_metas_financeiras():
    if supabase:
        try:
            res = supabase.table("metas_financeiras").select("*").order("prazo_anos").execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
    return pd.DataFrame(columns=["id","nome","valor_alvo","valor_atual","prazo_anos","categoria"])

def adicionar_meta_financeira(n, a, at, p, c):
    if supabase:
        try: supabase.table("metas_financeiras").insert({"nome":str(n).strip(),"valor_alvo":float(a),
            "valor_atual":float(at),"prazo_anos":int(p),"categoria":c}).execute()
        except: pass

def remover_meta_financeira(i):
    if supabase:
        try: supabase.table("metas_financeiras").delete().eq("id",i).execute()
        except: pass

def atualizar_valor_meta_financeira(i, nv):
    if supabase:
        try: supabase.table("metas_financeiras").update({"valor_atual":float(nv)}).eq("id",i).execute()
        except: pass

def carregar_rendas():
    if supabase:
        try:
            res = supabase.table("fontes_renda").select("*").order("ano", desc=True).order("mes", desc=True).execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
    return pd.DataFrame(columns=["id","descricao","valor","mes","ano","tipo"])

def adicionar_renda(d, v, m, a, t):
    if supabase:
        try: supabase.table("fontes_renda").insert({"descricao":str(d).strip(),"valor":float(v),
            "mes":int(m),"ano":int(a),"tipo":t}).execute()
        except: pass

def remover_renda(i):
    if supabase:
        try: supabase.table("fontes_renda").delete().eq("id",i).execute()
        except: pass

def carregar_protecoes():
    if supabase:
        try:
            res = supabase.table("protecoes").select("*").order("item").execute()
            if res.data: return pd.DataFrame(res.data)
        except: pass
    return pd.DataFrame(columns=["id","item","contratado","observacao"])

def atualizar_protecao(i, c):
    if supabase:
        try: supabase.table("protecoes").update({"contratado":bool(c),"atualizado_em":datetime.now().isoformat()}).eq("item",i).execute()
        except: pass

def carregar_contas_pagar():
    if supabase:
        try:
            res = supabase.table("contas_pagar").select("*").order("vencimento").execute()
            if res.data:
                df = pd.DataFrame(res.data); df['vencimento'] = pd.to_datetime(df['vencimento']); return df
        except: pass
    return pd.DataFrame(columns=["id","descricao","valor","vencimento","pago","categoria"])

def adicionar_conta_pagar(d, v, ve, c):
    if supabase:
        try: supabase.table("contas_pagar").insert({"descricao":str(d).strip(),"valor":float(v),
            "vencimento":str(ve),"categoria":c,"pago":False}).execute()
        except: pass

def marcar_conta_paga(i, p=True):
    if supabase:
        try: supabase.table("contas_pagar").update({"pago":bool(p)}).eq("id",i).execute()
        except: pass

def remover_conta_pagar(i):
    if supabase:
        try: supabase.table("contas_pagar").delete().eq("id",i).execute()
        except: pass

def calcular_net_worth():
    a = carregar_ativos(); p = carregar_passivos()
    ta = a["valor"].sum() if not a.empty else 0.0
    tp = p["valor_total"].sum() if not p.empty else 0.0
    return {"ativos":round(ta,2),"passivos":round(tp,2),"liquido":round(ta-tp,2)}

def calcular_fire(gasto, pat=0.0, ap=0.0, tr=0.04, tx=0.07):
    """Calcula FIRE. tr = taxa de retirada (padrão 4%), tx = taxa de rendimento (padrão 7%)."""
    if gasto <= 0: return None
    nm = (gasto * 12) / tr
    falta = max(0.0, nm - pat)
    anos = None
    if ap > 0 and falta > 0:
        r = tx / 12; n = 0; saldo = pat
        while saldo < nm and n < 1200:
            saldo = saldo * (1 + r) + ap; n += 1
        anos = n / 12
    return {"numero_magico":round(nm,2),"falta":round(falta,2),
            "anos_para_fire":round(anos,1) if anos else None,
            "retirada_mensal_segura":round(nm*tr/12,2)}

def calcular_diagnostico(receita, tg, tf, reserva, ativos, passivos):
    if receita <= 0: return {"nota":0,"detalhes":{},"taxa_poupanca_pct":0,"meses_reserva":0}
    poup = receita - tg; tp = poup / receita
    pp = min(25, max(0, tp * 100))
    mr = (reserva / tf) if tf > 0 else 0
    pr = min(25, max(0, (mr / 6) * 25))
    pd_ = passivos / (ativos + passivos) if (ativos + passivos) > 0 else 0
    pdv = max(0, 25 * (1 - pd_))
    pi = min(15, max(0, (tp * 100 / 30) * 15))
    pdiv = 10 if ativos > 0 else 0
    nota = round(pp + pr + pdv + pi + pdiv, 1)
    return {"nota":nota,"detalhes":{"poupanca":round(pp,1),"reserva":round(pr,1),
            "divida":round(pdv,1),"investimento":round(pi,1),"diversificacao":round(pdiv,1)},
            "taxa_poupanca_pct":round(tp*100,1),"meses_reserva":round(mr,1)}

def calcular_ordem_quitacao(df):
    if df.empty: return pd.DataFrame()
    df = df.copy()
    df["custo_juros_mensal"] = (df["valor_total"] * df["juros_mensal"] / 100).round(2)
    df = df.sort_values("juros_mensal", ascending=False).reset_index(drop=True)
    df["ordem"] = df.index + 1
    return df

# PDFs
def gerar_relatorio_mensal_pdf(mes, ano, df, orc):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []; styles = getSampleStyleSheet()
    ts = ParagraphStyle('T', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#3B82F6'), spaceAfter=12, alignment=1)
    hs = ParagraphStyle('H', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#1F2937'), spaceBefore=12, spaceAfter=6)
    ns = styles['Normal']
    nome = meses_nomes[mes-1]
    story.append(Paragraph(f"<b>RELATÓRIO MENSAL — {nome.upper()}/{ano}</b>", ts))
    story.append(Paragraph(f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ParagraphStyle('S', parent=ns, alignment=1, textColor=colors.HexColor('#8B949E'))))
    story.append(Spacer(1, 15))
    tg = df["valor"].sum() if not df.empty else 0.0
    saldo = orc - tg; pct = (tg / orc * 100) if orc > 0 else 0
    resumo = [["Indicador","Valor (R$)"],["Orçamento",f"R$ {orc:,.2f}"],["Total Gasto",f"R$ {tg:,.2f}"],
              ["Saldo",f"R$ {saldo:,.2f}"],["% Utilizado",f"{pct:.1f}%"]]
    t = Table(resumo, colWidths=[250,200])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#151B23')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.HexColor('#E6EDF3')),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#232B36'))]))
    story.append(t); story.append(Spacer(1,15))
    if not df.empty:
        data = [["Data","Descrição","Categoria","Valor (R$)"]]
        for _, r in df.iterrows():
            data.append([r['data'].strftime('%d/%m/%Y'),str(r['descricao']),str(r['categoria']),f"R$ {float(r['valor']):,.2f}"])
        tv = Table(data, colWidths=[80,170,110,90])
        tv.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EF4444')),
            ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#232B36'))]))
        story.append(tv)
    doc.build(story); buffer.seek(0); return buffer.getvalue()

def gerar_relatorio_pdf(df_f, df_v, sa, sb, aa, ab):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []; styles = getSampleStyleSheet()
    ts = ParagraphStyle('TS', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#3B82F6'), spaceAfter=12, alignment=1)
    hs = ParagraphStyle('HS', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#1F2937'), spaceBefore=12, spaceAfter=6)
    ns = styles['Normal']
    story.append(Paragraph("<b>INVEST CONTROL PRO - RELATÓRIO FINANCEIRO</b>", ts))
    story.append(Paragraph(f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ParagraphStyle('Sub', parent=ns, alignment=1, textColor=colors.HexColor('#8B949E'))))
    story.append(Spacer(1, 15))
    story.append(Paragraph("<b>1. Rendas</b>", hs))
    rd = [["Descrição","Valor (R$)"],["Salário A",f"R$ {sa:,.2f}"],["Salário B",f"R$ {sb:,.2f}"],
          ["Aluguel A",f"R$ {aa:,.2f}"],["Aluguel B",f"R$ {ab:,.2f}"]]
    t = Table(rd, colWidths=[250,200])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#151B23')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.HexColor('#E6EDF3')),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#232B36'))]))
    story.append(t); story.append(Spacer(1,15))
    story.append(Paragraph("<b>2. Gastos Fixos</b>", hs))
    if not df_f.empty:
        fd = [["Descrição","Valor (R$)"]]
        for _, r in df_f.iterrows(): fd.append([str(r['descricao']),f"R$ {float(r['valor']):,.2f}"])
        tf = Table(fd, colWidths=[250,200])
        tf.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#151B23')),
            ('TEXTCOLOR',(0,0),(-1,0),colors.HexColor('#E6EDF3')),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#232B36'))]))
        story.append(tf)
    else: story.append(Paragraph("Nenhum.", ns))
    story.append(Spacer(1,15))
    story.append(Paragraph("<b>3. Despesas Variáveis</b>", hs))
    if not df_v.empty:
        vd = [["Data","Descrição","Categoria","Valor (R$)"]]
        for _, r in df_v.iterrows():
            ds = r['data'].strftime('%d/%m/%Y') if pd.notnull(r['data']) else ""
            vd.append([ds,str(r['descricao']),str(r['categoria']),f"R$ {float(r['valor']):,.2f}"])
        tv = Table(vd, colWidths=[80,170,110,90])
        tv.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EF4444')),
            ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#232B36'))]))
        story.append(tv)
    else: story.append(Paragraph("Nenhuma.", ns))
    doc.build(story); buffer.seek(0); return buffer.getvalue()

# =============================================================================
# SIDEBAR
# =============================================================================
st.sidebar.title("🛡️ Invest Control Pro")
st.sidebar.caption("Painel de gerenciamento financeiro")
st.sidebar.markdown("**CONFIGURAÇÃO DE CENÁRIOS**")
if st.sidebar.button("🔒 Sair / Bloquear Tela", use_container_width=True):
    st.session_state['autenticado'] = False; st.rerun()
st.sidebar.divider()

config = carregar_configuracoes()
st.sidebar.subheader("🔀 Simulação de Cenário")
cenario = st.sidebar.radio("Cenário:", ["COM Participação de B", "SEM Participação de B (Contingência)"], index=0)
b_participa = (cenario == "COM Participação de B")

st.sidebar.divider()
st.sidebar.subheader("💵 Rendas e custos base")
aluguel_input = st.sidebar.number_input("Valor do Aluguel Total (R$)", value=float(config["aluguel_total"]), step=50.0)
salario_a_input = st.sidebar.number_input("Salário Pessoa A (R$)", value=float(config["salario_a"]), step=100.0)
vr_a_input = st.sidebar.number_input("Vale Refeição (VR) A (R$)", value=float(config["vr_a"]), step=50.0)
if b_participa:
    salario_b_input = st.sidebar.number_input("Salário Pessoa B (R$)", value=float(config["salario_b"]), step=100.0)
else:
    salario_b_input = 0.0
    st.sidebar.warning("⚠️ B não participa.")
meta_reserva_input = st.sidebar.number_input("Meta de Reserva Mensal (R$)", value=float(config["meta_reserva_mensal"]), step=50.0)

st.sidebar.divider()
st.sidebar.subheader("✏ Edição Dinâmica do Aluguel")
edicao_manual = st.sidebar.checkbox("Habilitar edição manual customizada", value=bool(config.get("usa_edicao_manual", False)))
aluguel_a_input = None; aluguel_b_input = None
val_a_db = float(config.get("aluguel_a_custom", aluguel_input * 0.5))
val_b_db = float(config.get("aluguel_b_custom", aluguel_input * 0.5))
if edicao_manual and b_participa:
    quem = st.sidebar.radio("Ajustar:", ["Pessoa A", "Pessoa B"], index=0)
    if quem == "Pessoa A":
        aluguel_a_input = st.sidebar.number_input("A (R$)", 0.0, float(aluguel_input), val_a_db, 25.0)
        aluguel_b_input = max(0.0, aluguel_input - aluguel_a_input)
        st.sidebar.info(f"B: R$ {aluguel_b_input:,.2f}")
    else:
        aluguel_b_input = st.sidebar.number_input("B (R$)", 0.0, float(aluguel_input), val_b_db, 25.0)
        aluguel_a_input = max(0.0, aluguel_input - aluguel_b_input)
        st.sidebar.info(f"A: R$ {aluguel_a_input:,.2f}")
else:
    aluguel_a_input = val_a_db; aluguel_b_input = val_b_db

if st.sidebar.button("💾 Salvar Parâmetros"):
    a_s = aluguel_a_input if edicao_manual else aluguel_input * 0.5
    b_s = aluguel_b_input if edicao_manual else aluguel_input * 0.5
    salvar_configuracoes(aluguel_input, salario_a_input, salario_b_input, vr_a_input, meta_reserva_input, a_s, b_s, edicao_manual)
    st.sidebar.success("Salvo!"); st.rerun()

# ENGINE
if b_participa:
    if edicao_manual and aluguel_a_input is not None:
        aluguel_a, aluguel_b = aluguel_a_input, aluguel_b_input
        prop_a = aluguel_a / aluguel_input if aluguel_input > 0 else 0.5
        prop_b = aluguel_b / aluguel_input if aluguel_input > 0 else 0.5
    else:
        if (salario_a_input + salario_b_input) > 0:
            rt = salario_a_input + salario_b_input
            prop_a = salario_a_input / rt; prop_b = salario_b_input / rt
            aluguel_a = aluguel_input * prop_a; aluguel_b = aluguel_input * prop_b
        else:
            prop_a, prop_b = 1.0, 0.0; aluguel_a, aluguel_b = aluguel_input, 0.0
else:
    prop_a, prop_b = 1.0, 0.0; aluguel_a, aluguel_b = aluguel_input, 0.0

df_gastos_fixos = carregar_gastos_fixos()
total_outros_fixos_a = df_gastos_fixos["valor"].sum() if not df_gastos_fixos.empty else 0.0
total_fixos_a = aluguel_a + total_outros_fixos_a
saldo_livre_bruto = salario_a_input - total_fixos_a
meta_reserva_efetiva = meta_reserva_input if b_participa else min(meta_reserva_input, max(0.0, saldo_livre_bruto - 100))
saldo_para_variaveis = saldo_livre_bruto - meta_reserva_efetiva
df_variaveis = carregar_despesas_variaveis()
total_gastos_variaveis = df_variaveis["valor"].sum() if not df_variaveis.empty else 0.0
saldo_caixa_restante = saldo_para_variaveis - total_gastos_variaveis

# CORPO
st.markdown("""<div class="invest-eyebrow">INVEST CONTROL PRO · CENTRAL FINANCEIRA</div>
<div class="invest-heading">📊 Visão financeira e gerenciamento</div>
<div class="invest-subheading">Planejamento, despesas, investimentos e patrimônio em um único ambiente.</div>""", unsafe_allow_html=True)
st.caption(f"Cenário: **{cenario}** | VR: R$ {vr_a_input:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Salário Líquido (A)", f"+ R$ {salario_a_input:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
c2.metric("Sua Parte no Aluguel", f"- R$ {aluguel_a:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','), delta=f"{prop_a*100:.1f}%" if b_participa else "100%")
c3.metric("Total Gastos Fixos (A)", f"- R$ {total_fixos_a:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
c4.metric("Aporte Reserva Mensal", f"- R$ {meta_reserva_efetiva:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
st.divider()

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "📌 Planejamento", "💳 Gastos variáveis",
    "⚙️ Custos fixos", "📈 Investimentos",
    "📊 DRE", "📑 PDFs",
    "📅 Mensal", "✂️ Cortes", "🚀 Prosperidade"
])

# TAB 1
with tab1:
    st.subheader("🏠 Divisão e Proporcionalidade do Aluguel (A e B)")
    c1, c2, c3 = st.columns(3)
    c1.metric("Salário de A", f"+ R$ {salario_a_input:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
    c2.metric("Salário de B", f"+ R$ {salario_b_input:,.2f}".replace('.', '#').replace(',', '.').replace('#', ',') if b_participa else "R$ 0,00")
    c3.metric("Aluguel Total", f"R$ {aluguel_input:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
    cv1, cv2 = st.columns(2)
    cv1.info(f"👤 **Pessoa A vai pagar:** - R$ **{aluguel_a:,.2f}** ({prop_a*100:.1f}%)".replace('.', '#').replace(',', '.').replace('#', ','))
    if b_participa:
        cv2.success(f"👥 **Pessoa B vai pagar:** - R$ **{aluguel_b:,.2f}** ({prop_b*100:.1f}%)".replace('.', '#').replace(',', '.').replace('#', ','))
    else:
        cv2.warning("⚠️ **Pessoa B:** Sem participação.")
    st.divider()
    cl, cr = st.columns(2)
    with cl:
        st.subheader("💡 Distribuição do Salário de A")
        dc = {"Categoria":["Aluguel Proporcional","Outros Custos Fixos","Meta de Reserva","Orçamento Variável Livre"],
              "Valor":[aluguel_a,total_outros_fixos_a,meta_reserva_efetiva,max(0.0,saldo_para_variaveis)]}
        fig = px.pie(pd.DataFrame(dc), names="Categoria", values="Valor", hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(paper_bgcolor="#151B23", plot_bgcolor="#151B23", font_color="#E6EDF3")
        st.plotly_chart(fig, use_container_width=True)
    with cr:
        st.subheader("🛡 Progresso Anual da Reserva")
        st.write(f"**Aporte Mensal:** R$ {meta_reserva_efetiva:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
        st.write(f"**Meta Anual:** R$ {meta_reserva_efetiva * 12:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
        cols_g = st.columns(4); mc = 0
        for i, nm in enumerate(meses_nomes):
            with cols_g[i % 4]:
                if st.checkbox(f"{i+1}. {nm}", key=f"reserva_mes_{i+1}"):
                    mc += 1
                    st.markdown("<span style='color:#22C55E;font-size:12px;'>● pago</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='color:#F59E0B;font-size:12px;'>⏳ pendente</span>", unsafe_allow_html=True)
        st.markdown("---")
        st.progress(mc / 12.0)
        st.markdown(f"**Progresso:** {mc} de 12 meses (**{mc/12*100:.1f}%**)")

# TAB 2
with tab2:
    st.subheader("🛒 Gerenciamento de Despesas Variáveis do Mês")
    c1, c2, c3 = st.columns(3)
    c1.metric("Orçamento Variável", f"R$ {saldo_para_variaveis:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
    c2.metric("Total Já Gasto", f"- R$ {total_gastos_variaveis:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
    c3.metric("Saldo Restante", f"{'+' if saldo_caixa_restante>=0 else '-'} R$ {abs(saldo_caixa_restante):,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
    st.divider()
    with st.expander("➕ Lançar Nova Despesa Variável", expanded=True):
        with st.form("form_desp", clear_on_submit=True):
            fc1, fc2, fc3, fc4 = st.columns([2, 3, 2, 2])
            data_e = fc1.date_input("Data"); desc_e = fc2.text_input("Descrição")
            cat_e = fc3.selectbox("Categoria", ["Lazer / Passeios","Farmácia / Saúde","Vestuário","Imprevistos","Outros"])
            val_e = fc4.number_input("Valor (R$)", min_value=0.01, step=10.0)
            if st.form_submit_button("Lançar Despesa"):
                if desc_e:
                    adicionar_despesa_variavel(data_e, desc_e, cat_e, val_e); st.success("OK!"); st.rerun()
                else: st.error("Informe descrição.")
    if not df_variaveis.empty:
        st.markdown("#### Histórico de despesas")
        filtro1, filtro2 = st.columns([1, 2])
        opcoes_periodo = ["Todas", "Mês atual", "Últimos 90 dias"]
        filtro_periodo = filtro1.selectbox("Período de visualização", opcoes_periodo, key="filtro_gastos_periodo")
        termo_gastos = filtro2.text_input("Buscar por descrição ou categoria", placeholder="Pesquisar lançamentos...", key="filtro_gastos_texto")
        df_visivel = df_variaveis.copy()
        if filtro_periodo != "Todas":
            data_base = pd.Timestamp.now().normalize()
            inicio = data_base.replace(day=1) if filtro_periodo == "Mês atual" else data_base - pd.Timedelta(days=90)
            df_visivel = df_visivel.loc[df_visivel["data"] >= inicio]
        if termo_gastos.strip():
            termo = termo_gastos.strip().casefold()
            mascara = (df_visivel["descricao"].fillna("").astype(str).str.casefold().str.contains(termo, regex=False)
                | df_visivel["categoria"].fillna("").astype(str).str.casefold().str.contains(termo, regex=False))
            df_visivel = df_visivel.loc[mascara]
        st.caption(f"{len(df_visivel)} lançamento(s) exibido(s) · Total visualizado: {_fmt_brl(df_visivel['valor'].sum())}")
        for _, r in df_visivel.iterrows():
            c1, c2, c3, c4, c5 = st.columns([2, 3, 2, 2, 1])
            c1.write(r["data"].strftime("%d/%m/%Y")); c2.write(r["descricao"]); c3.write(r["categoria"])
            c4.write(f"- R$ {r['valor']:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
            if c5.button("🗑️", key=f"dv_{r['id']}"):
                remover_despesa_variavel(r["id"]); st.rerun()

# TAB 3
with tab3:
    st.subheader("📋 Tabela de Custos Fixos de A")
    c1, c2 = st.columns([2, 1])
    with c1:
        if not df_gastos_fixos.empty:
            for _, r in df_gastos_fixos.iterrows():
                cf1, cf2, cf3 = st.columns([3, 2, 1])
                cf1.write(f"**{r['descricao']}**")
                cf2.write(f"- R$ {r['valor']:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
                if cf3.button("Excluir", key=f"df_{r['id']}"):
                    remover_gasto_fixo(r["id"]); st.rerun()
    with c2:
        st.write("#### Adicionar Novo")
        with st.form("form_fix", clear_on_submit=True):
            df_ = st.text_input("Descrição"); vf = st.number_input("Valor (R$)", min_value=0.01, step=10.0)
            if st.form_submit_button("Cadastrar"):
                if df_: adicionar_gasto_fixo(df_, vf); st.rerun()

# TAB 4 — SIMULADOR
with tab4:
    st.subheader("📈 Simulador de Crescimento Patrimonial (Juros Compostos & CDI)")
    st.markdown("Simule com **taxa fixa** ou **atrelado ao CDI**, com **aporte inicial** e **aportes mensais flexíveis**.")

    cdi_atual = obter_taxa_cdi_atual()
    ci1, ci2 = st.columns([1, 3])
    with ci1:
        st.metric("📊 CDI Atual (a.a.)", f"{cdi_atual:.2f}%" if cdi_atual else "—")
    with ci2:
        if cdi_atual:
            st.success("CDI do Banco Central (SGS 4389). Atualizado a cada 1h.", icon="✅")
        else:
            st.warning("CDI indisponível. Informe manualmente abaixo.", icon="⚠️")
    st.divider()

    modo_taxa = st.radio("Modalidade de rentabilidade:",
        ["🎯 Taxa fixa (% ao ano)", "📊 Atrelado ao CDI (% do CDI)"],
        horizontal=True, key="modo_taxa_sim")

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        aporte_inicial = st.number_input("💰 Aporte Inicial (R$) — o que você já tem para investir agora",
            value=0.0, step=100.0, key="aporte_ini_sim")
        aporte_sim = st.number_input("Aporte Mensal Base (R$)",
            value=float(meta_reserva_efetiva), step=50.0, key="aporte_sim")
        anos_sim = st.slider("Horizonte de Tempo (Anos)", min_value=1, max_value=30, value=5, key="anos_sim")
    with col_s2:
        if modo_taxa.startswith("🎯"):
            taxa_anual_sim = st.slider("Rentabilidade Anual Estimada (%)",
                min_value=1.0, max_value=25.0, value=10.0, step=0.5, key="taxa_sim")
            cdi_ref = None
            nome_sim = st.text_input("Nome da simulação (para salvar)",
                placeholder="Ex: Cenário conservador 5 anos", key="nome_sim_fixa")
        else:
            cdi_manual = st.number_input("CDI considerada (% a.a.) — 0 = usar atual",
                min_value=0.0, max_value=30.0,
                value=float(cdi_atual) if cdi_atual else 13.65, step=0.25, key="cdi_manual")
            percentual_cdi_sim = st.slider("% do CDI contratado", min_value=80, max_value=150,
                value=100, step=5, key="pct_cdi_sim")
            cdi_ref = cdi_manual if cdi_manual > 0 else (cdi_atual if cdi_atual else 13.65)
            taxa_anual_sim = cdi_ref * (percentual_cdi_sim / 100)
            st.info(f"**Taxa efetiva: {taxa_anual_sim:.2f}% a.a.** (CDI {cdi_ref:.2f}% × {percentual_cdi_sim}%)")
            nome_sim = st.text_input("Nome da simulação (para salvar)",
                placeholder="Ex: CDB 110% CDI — 5 anos", key="nome_sim_cdi")

    st.divider()
    usar_aporte_variavel = st.checkbox("🔧 Personalizar aportes mês a mês (flexível)",
        value=False, key="chk_aporte_var",
        help="Marque para editar o valor depositado em cada mês individualmente.")

    meses_total = anos_sim * 12

    if usar_aporte_variavel:
        st.markdown("##### 📝 Edite o valor do aporte para cada mês")
        st.caption("Altere livremente. Ex: R$ 800 no mês 1, R$ 500 no mês 2, R$ 0 no mês 3...")

        chave_df = f"df_aportes_{meses_total}"
        if chave_df not in st.session_state:
            st.session_state[chave_df] = pd.DataFrame({
                "Mês": list(range(1, meses_total + 1)),
                "Aporte (R$)": [float(aporte_sim)] * meses_total,
            })

        cb1, cb2, cb3 = st.columns([1, 1, 2])
        with cb1:
            if st.button("🔄 Resetar para base", key="btn_reset_ap", use_container_width=True):
                st.session_state[chave_df] = pd.DataFrame({
                    "Mês": list(range(1, meses_total + 1)),
                    "Aporte (R$)": [float(aporte_sim)] * meses_total,
                })
                st.rerun()
        with cb2:
            zerar_apos = st.number_input("Zerar após mês", min_value=0, max_value=meses_total,
                value=0, step=1, key="zerar_ap")
            if st.button("Aplicar", key="btn_zerar_ap", use_container_width=True):
                novos = st.session_state[chave_df].copy()
                novos.loc[novos["Mês"] > zerar_apos, "Aporte (R$)"] = 0.0
                st.session_state[chave_df] = novos
                st.rerun()
        with cb3:
            st.markdown("**Atalhos:**")
            cc1, cc2, cc3, cc4 = st.columns(4)
            with cc1:
                if st.button("Tudo R$ 0", key="q_zero"):
                    nv = st.session_state[chave_df].copy(); nv["Aporte (R$)"] = 0.0
                    st.session_state[chave_df] = nv; st.rerun()
            with cc2:
                if st.button("Tudo R$ 500", key="q_500"):
                    nv = st.session_state[chave_df].copy(); nv["Aporte (R$)"] = 500.0
                    st.session_state[chave_df] = nv; st.rerun()
            with cc3:
                if st.button("Tudo R$ 800", key="q_800"):
                    nv = st.session_state[chave_df].copy(); nv["Aporte (R$)"] = 800.0
                    st.session_state[chave_df] = nv; st.rerun()
            with cc4:
                if st.button("Tudo R$ 1000", key="q_1000"):
                    nv = st.session_state[chave_df].copy(); nv["Aporte (R$)"] = 1000.0
                    st.session_state[chave_df] = nv; st.rerun()

        df_edit = st.data_editor(
            st.session_state[chave_df],
            use_container_width=True, hide_index=True, num_rows="fixed",
            key=f"editor_{meses_total}",
            column_config={
                "Mês": st.column_config.NumberColumn("Mês", disabled=True, width="small"),
                "Aporte (R$)": st.column_config.NumberColumn(
                    "Aporte (R$)", min_value=0.0, step=50.0, format="%.2f", required=False),
            },
            height=min(420, 80 + 35 * min(meses_total, 10)),
        )
        st.session_state[chave_df] = df_edit

        lista_aportes = df_edit["Aporte (R$)"].fillna(0).astype(float).tolist()
        soma_mensais = sum(lista_aportes)

        st.markdown(
            f"<div style='background:{PALETA['fundo_card']};border:1px solid {PALETA['borda']};"
            f"border-radius:10px;padding:12px 16px;margin-top:8px;'>"
            f"<b style='color:{PALETA['texto_principal']};'>💼 Total que você vai investir:</b> "
            f"<b style='color:{PALETA['verde']};font-size:15px;'>{_fmt_brl(aporte_inicial + soma_mensais)}</b> "
            f"<span style='color:{PALETA['texto_secundario']};font-size:12px;'>"
            f"(inicial {_fmt_brl(aporte_inicial)} + mensais {_fmt_brl(soma_mensais)} · "
            f"média mensal {_fmt_brl(soma_mensais/meses_total if meses_total > 0 else 0)})</span></div>",
            unsafe_allow_html=True
        )
    else:
        lista_aportes = [float(aporte_sim)] * meses_total

    taxa_mensal = (1 + taxa_anual_sim / 100) ** (1 / 12) - 1
    lista_proj = []; montante_atual = float(aporte_inicial); total_investido = float(aporte_inicial)
    for m, ap in enumerate(lista_aportes, start=1):
        montante_atual = (montante_atual + ap) * (1 + taxa_mensal)
        total_investido += ap
        if m % 12 == 0:
            lista_proj.append({"Ano": m // 12, "Total Investido": total_investido,
                                "Patrimônio Total": montante_atual, "Juros Acumulados": montante_atual - total_investido})

    if lista_proj:
        df_proj = pd.DataFrame(lista_proj)
        juros_totais = montante_atual - total_investido

        cr1, cr2, cr3, cr4 = st.columns(4)
        cr1.metric("💰 Aporte Inicial", _fmt_brl(aporte_inicial))
        cr2.metric("Valor Total Acumulado", f"+ R$ {montante_atual:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
        cr3.metric("Total Investido", f"R$ {total_investido:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
        cr4.metric("Rendimento", f"+ R$ {juros_totais:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))

        st.markdown("")
        cb_1, cb_2 = st.columns([1, 3])
        with cb_1:
            if st.button("💾 Salvar esta simulação", use_container_width=True, key="btn_salvar_sim"):
                if not nome_sim.strip():
                    st.warning("Dê um nome à simulação antes de salvar.")
                else:
                    ap_medio = sum(lista_aportes) / len(lista_aportes) if lista_aportes else aporte_sim
                    ok = salvar_simulacao_investimento(
                        nome_sim, ap_medio, anos_sim, taxa_anual_sim,
                        montante_atual, total_investido, juros_totais,
                        cdi_taxa=cdi_ref, aporte_inicial=aporte_inicial)
                    if ok:
                        st.success(f"Simulação '{nome_sim}' salva!"); st.rerun()

        st.divider()

        if modo_taxa.startswith("📊") and cdi_atual:
            df_graf = df_proj.copy()
            df_graf["Sem Rendimento"] = aporte_inicial + df_graf["Ano"].apply(
                lambda a: sum(lista_aportes[:int(a * 12)]))
            fig_graf = go.Figure()
            fig_graf.add_trace(go.Scatter(x=df_graf["Ano"], y=df_graf["Patrimônio Total"], mode="lines+markers",
                name="Com CDI", line=dict(color="#22C55E", width=3),
                fill="tozeroy", fillcolor="rgba(34,197,94,0.15)"))
            fig_graf.add_trace(go.Scatter(x=df_graf["Ano"], y=df_graf["Sem Rendimento"], mode="lines+markers",
                name="Sem Rendimento", line=dict(color="#EF4444", width=2, dash="dash")))
            fig_graf.update_layout(paper_bgcolor="#151B23", plot_bgcolor="#151B23",
                font_color="#E6EDF3", xaxis_title="Anos", yaxis_title="Valor (R$)",
                legend_title="Cenário", margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_graf, use_container_width=True)
        else:
            fig_invest = px.area(df_proj, x="Ano", y=["Patrimônio Total", "Total Investido"],
                title="Evolução Patrimonial Projetada")
            fig_invest.update_layout(paper_bgcolor="#151B23", plot_bgcolor="#151B23", font_color="#E6EDF3")
            st.plotly_chart(fig_invest, use_container_width=True)

    st.divider()

    if modo_taxa.startswith("📊") and cdi_atual:
        st.markdown("### 🎯 Comparativo de Produtos de Renda Fixa")
        st.caption("Veja quanto renderiam diferentes produtos atrelados ao CDI com os mesmos aportes.")
        produtos = [("Poupança",70,"#8A95A5"),("Tesouro Selic",100,"#3B82F6"),("CDB 100% CDI",100,"#06B6D4"),
                    ("CDB 110% CDI",110,"#22C55E"),("LCI/LCA 90% CDI",90,"#7C3AED"),("CDB 120% CDI",120,"#F59E0B")]
        res = []
        for nome_p, pct, cor in produtos:
            cdi_m = (1 + cdi_ref / 100) ** (1 / 12) - 1
            tx_m = cdi_m * (pct / 100)
            mnt = float(aporte_inicial); inv = float(aporte_inicial)
            for ap in lista_aportes:
                mnt = (mnt + ap) * (1 + tx_m); inv += ap
            res.append({"Produto": nome_p, "Percentual do CDI": f"{pct}%",
                        "Taxa Efetiva (% a.a.)": round(cdi_ref * pct / 100, 2),
                        "Montante Final": round(mnt, 2), "Juros Totais": round(mnt - inv, 2), "_cor": cor})
        if res:
            dfp = pd.DataFrame(res); ds = dfp.drop(columns=["_cor"]).copy()
            ds["Montante Final"] = ds["Montante Final"].apply(_fmt_brl)
            ds["Juros Totais"] = ds["Juros Totais"].apply(_fmt_brl)
            ds["Taxa Efetiva (% a.a.)"] = ds["Taxa Efetiva (% a.a.)"].apply(lambda v: f"{v:.2f}%")
            st.dataframe(ds, use_container_width=True, hide_index=True)
            fc = px.bar(dfp, x="Produto", y="Montante Final", color="Produto",
                color_discrete_sequence=[r["_cor"] for r in res], title=f"Comparativo (CDI {cdi_ref:.2f}% a.a.)")
            fc.update_layout(paper_bgcolor="#151B23", plot_bgcolor="#151B23",
                font_color="#E6EDF3", showlegend=False, xaxis_tickangle=-25)
            st.plotly_chart(fc, use_container_width=True)

    st.divider()

    if cdi_atual:
        with st.expander("📉 Ver histórico recente do CDI (Banco Central)"):
            dch = obter_historico_cdi(30)
            if not dch.empty:
                fc2 = px.line(dch, x="data", y="valor", markers=True, title="Taxa CDI (últimos 30 dias úteis)")
                fc2.update_traces(line_color="#22C55E")
                fc2.update_layout(paper_bgcolor="#151B23", plot_bgcolor="#151B23", font_color="#E6EDF3", height=260)
                st.plotly_chart(fc2, use_container_width=True)
                st.caption(f"Fonte: BCB SGS 4389 · Média: {dch['valor'].mean():.2f}% · Máx: {dch['valor'].max():.2f}% · Mín: {dch['valor'].min():.2f}%")

    st.divider()
    st.markdown("### 📂 Simulações Salvas")
    df_sims = carregar_simulacoes_investimento()
    if df_sims.empty:
        st.info("Nenhuma simulação salva ainda.")
    else:
        melhor = df_sims.loc[df_sims["montante_final"].idxmax()]
        st.markdown(
            f"<div style='background:{PALETA['fundo_card']};border:1px solid {PALETA['borda']};"
            f"border-radius:12px;padding:14px 18px;margin-bottom:12px;'>"
            f"<b style='color:{PALETA['texto_principal']};'>📊 {len(df_sims)} simulações salvas</b> · "
            f"<span style='color:{PALETA['texto_secundario']};'>Melhor: "
            f"<b style='color:{PALETA['verde']};'>{melhor['nome']}</b> com "
            f"R$ {melhor['montante_final']:,.2f}</span></div>", unsafe_allow_html=True)

        cols_d = ["nome", "aporte_mensal", "anos", "taxa_anual", "montante_final",
                   "total_investido", "juros_totais", "criado_em"]
        if "aporte_inicial" in df_sims.columns: cols_d.insert(1, "aporte_inicial")
        if "cdi_taxa_utilizada" in df_sims.columns: cols_d.insert(-1, "cdi_taxa_utilizada")

        ds = df_sims[cols_d].copy()
        ds["aporte_mensal"] = ds["aporte_mensal"].apply(_fmt_brl)
        ds["taxa_anual"] = ds["taxa_anual"].apply(lambda v: f"{v:.2f}%")
        ds["montante_final"] = ds["montante_final"].apply(_fmt_brl)
        ds["total_investido"] = ds["total_investido"].apply(_fmt_brl)
        ds["juros_totais"] = ds["juros_totais"].apply(_fmt_brl)
        ds["anos"] = ds["anos"].apply(lambda v: f"{int(v)} anos")
        ds["criado_em"] = pd.to_datetime(ds["criado_em"]).dt.strftime("%d/%m/%Y %H:%M")
        if "aporte_inicial" in ds.columns:
            ds["aporte_inicial"] = ds["aporte_inicial"].apply(lambda v: _fmt_brl(v) if pd.notnull(v) else "—")
        if "cdi_taxa_utilizada" in ds.columns:
            ds["cdi_taxa_utilizada"] = ds["cdi_taxa_utilizada"].apply(lambda v: f"{v:.2f}%" if pd.notnull(v) else "—")

        ren = {"nome":"Nome","aporte_inicial":"Aporte Inicial","aporte_mensal":"Aporte Mensal Médio",
               "anos":"Prazo","taxa_anual":"Taxa","montante_final":"Montante Final",
               "total_investido":"Investido","juros_totais":"Juros",
               "cdi_taxa_utilizada":"CDI Base","criado_em":"Salvo em"}
        ds = ds.rename(columns=ren)
        st.dataframe(ds, use_container_width=True, hide_index=True)

        fc3 = px.bar(df_sims.sort_values("montante_final"), x="montante_final", y="nome",
            orientation="h", color="montante_final", color_continuous_scale=["#3B82F6", "#22C55E"],
            labels={"montante_final": "Montante Final (R$)", "nome": ""})
        fc3.update_layout(paper_bgcolor="#151B23", plot_bgcolor="#151B23", font_color="#E6EDF3",
            showlegend=False, coloraxis_showscale=False, height=max(200, 60 * len(df_sims)))
        st.plotly_chart(fc3, use_container_width=True)

        st.markdown("#### 🗑️ Excluir")
        cds = st.columns(min(4, len(df_sims)))
        for i, (_, s) in enumerate(df_sims.iterrows()):
            with cds[i % 4]:
                if st.button(f"🗑️ {s['nome'][:20]}", key=f"del_sim_{s['id']}", use_container_width=True):
                    remover_simulacao_investimento(s["id"]); st.rerun()

# TAB 5
with tab5:
    st.subheader("📊 DRE Gerencial & Análise de Lucratividade")
    receita = salario_a_input + vr_a_input
    lucro = receita - total_fixos_a - total_gastos_variaveis
    margem = (lucro / receita * 100) if receita > 0 else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Receita Bruta", f"+ R$ {receita:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
    c2.metric("Lucro Líquido", f"{'+' if lucro>=0 else '-'} R$ {abs(lucro):,.2f}".replace('.', '#').replace(',', '.').replace('#', ','), delta=f"{margem:.1f}%")
    runway = (meta_reserva_efetiva * 6) / total_fixos_a if total_fixos_a > 0 else 0
    c3.metric("Runway", f"{runway:.1f} Meses", delta="Cobertura")
    st.divider()
    dados = [["Conta / Indicador","Valor (R$)","% da Receita"],
        ["(+) Receita Bruta", f"+ R$ {receita:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','),"100.0%"],
        ["(-) Custos Fixos", f"- R$ {total_fixos_a:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','),
         f"{(total_fixos_a/receita)*100:.1f}%" if receita > 0 else "0%"],
        ["(-) Despesas Variáveis", f"- R$ {total_gastos_variaveis:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','),
         f"{(total_gastos_variaveis/receita)*100:.1f}%" if receita > 0 else "0%"],
        ["(=) LUCRO LÍQUIDO", f"{'+' if lucro>=0 else '-'} R$ {abs(lucro):,.2f}".replace('.', '#').replace(',', '.').replace('#', ','), f"{margem:.1f}%"]]
    st.table(pd.DataFrame(dados[1:], columns=dados[0]))
    st.markdown("#### 🔍 Diagnóstico de Ladrões de Lucro")
    if not df_variaveis.empty:
        dca = df_variaveis.groupby("categoria")["valor"].sum().reset_index()
        mg = dca.loc[dca["valor"].idxmax()]
        st.warning(f"⚠️ Maior ralo: **{mg['categoria']}** consumiu **R$ {mg['valor']:,.2f}**.".replace('.', '#').replace(',', '.').replace('#', ','))
    else: st.success("🟢 Nenhuma distorção.")

# TAB 6
with tab6:
    st.subheader("📑 Central de Relatórios em PDF")
    pdf_bytes = gerar_relatorio_pdf(df_gastos_fixos, df_variaveis, salario_a_input, salario_b_input, aluguel_a, aluguel_b)
    st.download_button("📥 Baixar Relatório Completo em PDF", data=pdf_bytes,
        file_name=f"Relatorio_Financeiro_{datetime.now().strftime('%Y%m%d')}.pdf",
        mime="application/pdf", use_container_width=True)

# TAB 7
with tab7:
    st.subheader("📅 Relatório Mensal & Orçamento por Mês")
    hoje = datetime.now()
    cm1, cm2, cm3 = st.columns(3)
    mes_sel = cm1.selectbox("Mês de Referência", list(range(1, 13)), index=hoje.month - 1, format_func=lambda x: meses_nomes[x-1])
    ano_sel = cm2.number_input("Ano", 2020, 2100, hoje.year, 1)
    orc = carregar_orcamento_mes(mes_sel, ano_sel)
    orc_val = float(orc.get("orcamento", 0.0) or 0.0)
    if orc.get("fechado"): cm3.error("🔒 Fechado")
    else: cm3.success("🟢 Aberto")
    st.divider()
    with st.expander("💼 Definir Orçamento", expanded=(orc_val == 0.0)):
        novo = st.number_input("Orçamento (R$)", min_value=0.0, value=orc_val, step=50.0, key=f"orc_{mes_sel}_{ano_sel}")
        c1, c2 = st.columns(2)
        if c1.button("💾 Salvar Orçamento"):
            salvar_orcamento_mes(mes_sel, ano_sel, novo); st.rerun()
        if c2.button("🔒 Fechar Mês e Iniciar Novo Ciclo"):
            fechar_mes(mes_sel, ano_sel)
            pm = 1 if mes_sel == 12 else mes_sel + 1
            pa = ano_sel + 1 if mes_sel == 12 else ano_sel
            carregar_orcamento_mes(pm, pa); st.rerun()
    df_mes = carregar_despesas_por_mes(mes_sel, ano_sel)
    tgm = df_mes["valor"].sum() if not df_mes.empty else 0.0
    sm = orc_val - tgm; pu = (tgm / orc_val * 100) if orc_val > 0 else 0.0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Orçamento", f"R$ {orc_val:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
    c2.metric("Total Gasto", f"- R$ {tgm:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
    c3.metric("Saldo", f"{'+' if sm>=0 else '-'} R$ {abs(sm):,.2f}".replace('.', '#').replace(',', '.').replace('#', ','))
    c4.metric("% Utilizado", f"{pu:.1f}%")
    if orc_val > 0:
        st.progress(min(pu/100, 1.0))
        if pu >= 100: st.error("🚨 Orçamento estourado!")
        elif pu >= 80: st.warning(f"⚠️ {pu:.1f}% utilizado.")
        else: st.success(f"✅ Dentro do orçamento ({pu:.1f}%).")
    st.divider()
    cg1, cg2 = st.columns(2)
    with cg1:
        st.markdown("#### 📊 Gastos por Categoria")
        if not df_mes.empty:
            dcat = df_mes.groupby("categoria")["valor"].sum().reset_index()
            fc = px.bar(dcat, x="categoria", y="valor", color="categoria", color_discrete_sequence=px.colors.qualitative.Set2)
            fc.update_layout(paper_bgcolor="#151B23", plot_bgcolor="#151B23", font_color="#E6EDF3", showlegend=False)
            st.plotly_chart(fc, use_container_width=True)
        else: st.info("Sem despesas.")
    with cg2:
        st.markdown("#### 📋 Detalhamento")
        if not df_mes.empty:
            dm = df_mes.copy(); dm["data"] = dm["data"].dt.strftime("%d/%m/%Y")
            dm = dm[["data","descricao","categoria","valor"]]
            dm.columns = ["Data","Descrição","Categoria","Valor"]
            st.dataframe(dm, use_container_width=True, hide_index=True)
        else: st.info("Nenhuma.")
    st.divider()
    pdf_m = gerar_relatorio_mensal_pdf(mes_sel, ano_sel, df_mes, orc_val)
    st.download_button(f"📥 Relatório {meses_nomes[mes_sel-1]}/{ano_sel}", data=pdf_m,
        file_name=f"Relatorio_{meses_nomes[mes_sel-1]}_{ano_sel}.pdf",
        mime="application/pdf", use_container_width=True)
    st.divider()
    st.markdown("#### 🗂 Histórico")
    dh = listar_meses_fechados()
    if not dh.empty:
        dh["Mês"] = dh["mes"].apply(lambda x: meses_nomes[int(x)-1])
        dh = dh.rename(columns={"ano":"Ano","orcamento":"Orçamento (R$)","fechado":"Fechado"})
        dh["Fechado"] = dh["Fechado"].apply(lambda x: "🔒 Sim" if x else "🟢 Não")
        st.dataframe(dh[["Mês","Ano","Orçamento (R$)","Fechado"]], use_container_width=True, hide_index=True)
    else: st.info("Nenhum mês registrado.")

# TAB 8 — CORTES INTELIGENTES
with tab8:
    st.subheader("✂️ Cortes Inteligentes")
    rc = salario_a_input + vr_a_input

    BENCH = {"Lazer / Passeios":8.0,"Farmácia / Saúde":5.0,"Vestuário":5.0,"Imprevistos":10.0,
             "Outros":5.0,"Internet":3.0,"Recarga celular":2.0,"Corte de cabelo":2.0,
             "Cartão de crédito":10.0,"Alimentação":15.0,"Transporte":10.0,"Moradia":30.0}
    ESFORCO = {"Lazer / Passeios":"Fácil","Vestuário":"Fácil","Outros":"Fácil","Recarga celular":"Fácil",
               "Corte de cabelo":"Médio","Farmácia / Saúde":"Médio","Imprevistos":"Médio",
               "Internet":"Médio","Cartão de crédito":"Médio","Alimentação":"Médio","Transporte":"Médio","Moradia":"Difícil"}

    def _gerar_expl(cat, val, peso, bench, ex, cs, tipo, rb, mr=0.0):
        txt = "despesa variável" if tipo == "Variável" else "custo fixo"
        ep = peso - bench; vi = rb * bench / 100
        if ep >= 10: niv, em = "CRÍTICO", "🚨"; ac = "Revisão imediata necessária."
        elif ep >= 5: niv, em = "ALTO", "⚠️"; ac = "Atenção agora. Reduzir evita problema maior."
        else: niv, em = "MODERADO", "📌"; ac = "Pequenos ajustes já trazem resultado."
        ir = ""
        if mr > 0:
            pct_r = (cs / mr) * 100
            ir = f" Equivale a <b>{pct_r:.0f}%</b> da meta de reserva."
        ird = (cs / rb) * 100 if rb > 0 else 0
        return (f"{em} <b>Nível: {niv}</b><br><br>Gastando <b>R$ {val:,.2f}</b> em <b>{cat}</b> ({txt}), "
                f"<b>{peso:.1f}%</b> da renda. Ideal: máx <b>{bench:.0f}%</b> (R$ {vi:,.2f}). "
                f"Excesso de <b>{ep:.1f} p.p.</b> = <b>R$ {ex:,.2f}/mês</b>.<br><br>"
                f"<b>Por quê?</b> {ac}<br><br><b>Ganho:</b> reduzindo R$ {cs:,.2f}/mês libera "
                f"<b>R$ {cs*12:,.2f}/ano</b>.{ir}<br><br>"
                f"<b>Impacto renda:</b> {ird:.2f}% da receita mensal.")

    def _prog_meta(cat, pct, df):
        if df is None or df.empty: return None
        df = df.copy(); df['data'] = pd.to_datetime(df['data'])
        h = datetime.now()
        da = df[(df['data'].dt.month == h.month) & (df['data'].dt.year == h.year)]
        dp = df[~((df['data'].dt.month == h.month) & (df['data'].dt.year == h.year))]
        if dp.empty: return None
        dp['mes_ano'] = dp['data'].dt.to_period('M')
        mp = dp[dp['categoria'] == cat].groupby('mes_ano')['valor'].sum().mean()
        if pd.isna(mp) or mp <= 0: return None
        at = da[da['categoria'] == cat]['valor'].sum()
        al = mp * (1 - pct / 100)
        pr = 1.0 if at <= al else (0.0 if at >= mp else (mp - at) / (mp - al))
        return {"media":round(mp,2),"atual":round(at,2),"alvo":round(al,2),
                "prog":max(0.0, min(1.0, pr)),"eco":round(max(0, mp-at),2)}

    def _evol_cat(cat, df, meses=6):
        if df is None or df.empty: return pd.DataFrame()
        d = df.copy(); d['data'] = pd.to_datetime(d['data'])
        d = d[d['categoria'] == cat]
        if d.empty: return pd.DataFrame()
        d['mes_ano'] = d['data'].dt.to_period('M').astype(str)
        return d.groupby('mes_ano')['valor'].sum().reset_index().sort_values('mes_ano').tail(meses)

    def _retro(cat, df):
        if df is None or df.empty: return None
        d = df.copy(); d['data'] = pd.to_datetime(d['data'])
        h = datetime.now()
        da = d[(d['data'].dt.month == h.month) & (d['data'].dt.year == h.year)]
        ma = (pd.Timestamp(h) - pd.DateOffset(months=1)).to_period('M')
        dan = d[d['data'].dt.to_period('M') == ma]
        va = da[da['categoria'] == cat]['valor'].sum()
        van = dan[dan['categoria'] == cat]['valor'].sum()
        if van <= 0 or va <= 0: return None
        v = ((va - van) / van) * 100
        return {"var":round(v,1),"atual":round(va,2),"anterior":round(van,2)} if v >= 15 else None

    def _sim_corte(val, pct):
        em = val * (pct / 100)
        return {"mes":round(em,2),"ano":round(em*12,2)}

    def _impacto_res(em, mr, tf):
        if tf <= 0: return None
        return {"meses_ano":round((em*12)/tf,2),"pct_meta":round((em/mr*100) if mr > 0 else 0,1)}

    def _matriz(cat, ea, emax):
        es = ESFORCO.get(cat, "Médio")
        im = "Alto" if emax > 0 and ea >= emax * 0.5 else "Baixo"
        q = f"{es} × {im}"
        if q == "Fácil × Alto": e, c, a = "🟢", "#22C55E", "ATAQUE PRIMEIRO — corte rápido e impactante"
        elif q in ("Fácil × Baixo","Médio × Alto"): e, c, a = "🟡", "#F59E0B", "VALE A PENA — planeje com calma"
        elif q == "Difícil × Alto": e, c, a = "🔴", "#EF4444", "PLANEJAR — mudança estrutural"
        else: e, c, a = "⚪", "#8A95A5", "BAIXA PRIORIDADE"
        return {"esforco":es,"impacto":im,"q":q,"emoji":e,"cor":c,"acao":a}

    def _assin(df, min_oc=3):
        if df is None or df.empty: return pd.DataFrame()
        d = df.copy(); d['data'] = pd.to_datetime(d['data'])
        r = []
        for desc, g in d.groupby('descricao'):
            if len(g) < min_oc: continue
            if g['data'].dt.to_period('M').nunique() < 2: continue
            vm = g['valor'].mean()
            dv = g['valor'].std() / vm if vm > 0 else 1
            if dv < 0.3:
                r.append({"descricao":desc,"valor_medio":round(vm,2),"ocorrencias":len(g),
                          "meses":g['data'].dt.to_period('M').nunique(),
                          "mensal":round(vm,2),"anual":round(vm*12,2)})
        return pd.DataFrame(r).sort_values("anual", ascending=False) if r else pd.DataFrame()

    def _invis(df, lim=60, min_oc=3):
        if df is None or df.empty: return pd.DataFrame()
        d = df.copy(); d['data'] = pd.to_datetime(d['data']); d['mes_ano'] = d['data'].dt.to_period('M')
        r = []
        for desc, g in d.groupby('descricao'):
            if len(g) < min_oc: continue
            vm = g['valor'].mean()
            if vm > lim: continue
            ms = g['mes_ano'].nunique()
            if ms == 0: continue
            fr = len(g) / ms; tm = vm * fr
            r.append({"descricao":desc,"valor_medio":round(vm,2),"freq":round(fr,1),
                      "mensal":round(tm,2),"anual":round(tm*12,2)})
        return pd.DataFrame(r).sort_values("anual", ascending=False) if r else pd.DataFrame()

    def _custo_hora(v, s, hm=176):
        return round(v / (s / hm), 1) if s > 0 else 0.0

    def _proj_lp(vm, ta=0.10):
        tm = (1 + ta) ** (1/12) - 1
        def _s(a):
            s = 0.0
            for _ in range(a * 12): s = (s + vm) * (1 + tm)
            return round(s, 2)
        return {"1":_s(1),"5":_s(5),"10":_s(10),"20":_s(20)}

    def _meta_ideal(rb, tf, tv, mr, tx=0.20):
        if rb <= 0: return None
        mi = rb * tx; pa = max(0.0, mr); fl = max(0.0, mi - pa)
        pap = (pa/rb)*100; mip = tx*100; flp = mip - pap
        pr = min(1.0, pa/mi) if mi > 0 else 0.0
        if pr >= 1.0: sc, se, st_ = "#22C55E", "🟢", "Meta atingida"
        elif pr >= 0.5: sc, se, st_ = "#F59E0B", "🟡", "No caminho"
        else: sc, se, st_ = "#EF4444", "🔴", "Abaixo do ideal"
        return {"mi":round(mi,2),"mip":round(mip,1),"pa":round(pa,2),"pap":round(pap,1),
                "fl":round(fl,2),"flp":round(flp,1),"pr":round(pr,3),"sc":sc,"se":se,"st":st_}

    def _por_cat(df, rb):
        if df.empty: return pd.DataFrame()
        r = []
        for _, s in df.iterrows():
            va = float(s["valor_atual"]); vi = rb * float(s["benchmark_saudavel"]) / 100
            rv = max(0.0, va - vi); rp = (rv/va*100) if va > 0 else 0
            r.append({"Categoria":s["categoria_limpa"],"Tipo":s["tipo"],"Atual (R$)":round(va,2),
                      "Ideal (R$)":round(vi,2),"Reduzir (R$)":round(rv,2),"Reduzir (%)":round(rp,1),
                      "Peso Atual (%)":s["peso_receita"],"Peso Ideal (%)":s["benchmark_saudavel"]})
        return pd.DataFrame(r).sort_values("Reduzir (R$)", ascending=False).reset_index(drop=True)

    sug = []
    if not df_variaveis.empty:
        for cat, val in df_variaveis.groupby("categoria")["valor"].sum().items():
            peso = (val / rc) * 100 if rc > 0 else 0
            b = BENCH.get(cat, 8.0)
            if peso > b:
                ex = val - (rc * b / 100); cs = ex * 0.5
                sug.append({"categoria":f"💳 {cat}","categoria_limpa":cat,"tipo":"Variável","valor_atual":val,
                    "peso_receita":round(peso,2),"benchmark_saudavel":b,"excesso":round(ex,2),
                    "corte_sugerido":round(cs,2),"economia_potencial":round(cs*12,2),
                    "explicacao":_gerar_expl(cat, val, peso, b, ex, cs, "Variável", rc, meta_reserva_efetiva)})
    if not df_gastos_fixos.empty:
        for cat, val in df_gastos_fixos.groupby("descricao")["valor"].sum().items():
            peso = (val / rc) * 100 if rc > 0 else 0
            b = BENCH.get(cat, 5.0)
            if peso > b:
                ex = val - (rc * b / 100); cs = ex * 0.4
                sug.append({"categoria":f"🔧 {cat}","categoria_limpa":cat,"tipo":"Fixo","valor_atual":val,
                    "peso_receita":round(peso,2),"benchmark_saudavel":b,"excesso":round(ex,2),
                    "corte_sugerido":round(cs,2),"economia_potencial":round(cs*12,2),
                    "explicacao":_gerar_expl(cat, val, peso, b, ex, cs, "Fixo", rc, meta_reserva_efetiva)})

    df_sug = pd.DataFrame(sug)
    if not df_sug.empty:
        df_sug = df_sug.sort_values("economia_potencial", ascending=False).reset_index(drop=True)
        df_sug["prioridade"] = df_sug.index + 1

    df_cc = carregar_cortes_concluidos()
    mp = _meta_ideal(rc, total_fixos_a, total_gastos_variaveis, meta_reserva_efetiva)

    if mp:
        st.markdown("### 🎯 Meta Ideal de Poupança")
        st.caption("Padrão: **20% da renda bruta** por mês.")
        m1, m2, m3 = st.columns(3)
        m1.metric("Meta Ideal (R$/mês)", _fmt_brl(mp["mi"]), delta=f"{mp['mip']}% da renda")
        m2.metric("Poupança Atual (R$/mês)", _fmt_brl(mp["pa"]), delta=f"{mp['pap']}% da renda")
        fd = f"-{mp['flp']}% abaixo" if mp["fl"] > 0 else "Atingida"
        m3.metric("Falta Poupar (R$/mês)", _fmt_brl(mp["fl"]), delta=fd,
                   delta_color="inverse" if mp["fl"] > 0 else "normal")
        st.markdown(f"<div style='background:{PALETA['fundo_card']};border:1px solid {PALETA['borda']};"
            f"border-radius:12px;padding:16px 20px;margin:10px 0;'>"
            f"<div style='display:flex;justify-content:space-between;'>"
            f"<b style='color:{PALETA['texto_principal']};'>Progresso</b>"
            f"<span style='color:{mp['sc']};font-weight:700;'>{mp['se']} {mp['st']} — {int(mp['pr']*100)}%</span></div></div>",
            unsafe_allow_html=True)
        st.progress(mp["pr"])
        st.divider()

    if df_sug.empty:
        st.success("🟢 Nenhuma categoria acima do benchmark.")
    else:
        ta = df_sug["economia_potencial"].sum(); tm_ = df_sug["corte_sugerido"].sum()
        top = df_sug.iloc[0]
        ck1, ck2, ck3 = st.columns(3)
        ck1.metric("💸 Economia Mensal", _fmt_brl(tm_))
        ck2.metric("💰 Economia Anual", _fmt_brl(ta))
        ck3.metric("🎯 Prioridade #1", top["categoria"])
        st.divider()

        st.markdown("### 📊 Quanto reduzir por categoria (R$ e %)")
        df_pc = _por_cat(df_sug, rc)
        if not df_pc.empty:
            ds = df_pc.copy()
            for c in ["Atual (R$)","Ideal (R$)","Reduzir (R$)"]:
                ds[c] = ds[c].apply(_fmt_brl)
            ds["Reduzir (%)"] = ds["Reduzir (%)"].apply(lambda v: f"{v:.1f}%")
            ds["Peso Atual (%)"] = ds["Peso Atual (%)"].apply(lambda v: f"{v:.1f}%")
            ds["Peso Ideal (%)"] = ds["Peso Ideal (%)"].apply(lambda v: f"{v:.1f}%")
            st.dataframe(ds, use_container_width=True, hide_index=True)
            tr_ = df_pc["Reduzir (R$)"].sum()
            trp = (tr_/rc*100) if rc > 0 else 0
            st.markdown(f"<div style='background:{PALETA['fundo_card']};border-left:4px solid {PALETA['acento']};"
                f"border-radius:10px;padding:14px 18px;margin-top:10px;'>"
                f"<b style='color:{PALETA['texto_principal']};'>💡 Total a reduzir:</b> "
                f"<b style='color:{PALETA['verde']};font-size:16px;'>{_fmt_brl(tr_)}/mês</b> "
                f"<span style='color:{PALETA['texto_secundario']};'>({trp:.1f}% da renda) · {_fmt_brl(tr_*12)}/ano</span></div>",
                unsafe_allow_html=True)
        st.divider()

        st.markdown("### 🏆 Análise Detalhada por Categoria")
        emax = df_sug["economia_potencial"].max()
        for _, s in df_sug.iterrows():
            cor = "#EF4444" if s["prioridade"] <= 2 else ("#F59E0B" if s["prioridade"] <= 4 else "#3B82F6")
            jc = s["categoria_limpa"] in df_cc['categoria'].tolist() if not df_cc.empty else False
            vi = rc * s['benchmark_saudavel'] / 100
            rv = max(0.0, s['valor_atual'] - vi)
            rp = (rv / s['valor_atual'] * 100) if s['valor_atual'] > 0 else 0
            sb = " ✅ <span style='color:#22C55E;'>já concluído</span>" if jc else ""
            st.markdown(f"""
<div style="background:{PALETA['fundo_card']};border:1px solid {PALETA['borda']};border-left:4px solid {cor};border-radius:10px;padding:14px 18px;margin-bottom:10px;">
<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
<div><span style="color:{cor};font-weight:700;font-size:14px;">#{int(s['prioridade'])} — {s['categoria']}</span>
<span style="color:{PALETA['texto_secundario']};font-size:11px;margin-left:8px;">[{s['tipo']}]{sb}</span></div>
<div style="color:{PALETA['verde']};font-weight:700;font-size:15px;">Reduzir: {_fmt_brl(rv)} ({rp:.1f}%)</div>
</div>
<div style="color:{PALETA['texto_secundario']};font-size:12px;margin-top:6px;">
Atual: <b style="color:{PALETA['texto_principal']};">{_fmt_brl(s['valor_atual'])}</b> → Ideal: <b style="color:{PALETA['texto_principal']};">{_fmt_brl(vi)}</b>
&nbsp;|&nbsp; Peso: <b style="color:{cor};">{s['peso_receita']}%</b> (bench: {s['benchmark_saudavel']}%)
</div></div>""", unsafe_allow_html=True)

            with st.expander(f"📖 Análise completa de {s['categoria_limpa']}", expanded=False):
                st.markdown(f"<div style='background:{PALETA['fundo_sidebar']};border:1px solid {PALETA['borda']};"
                    f"border-radius:10px;padding:16px 20px;color:{PALETA['texto_principal']};"
                    f"font-size:13px;line-height:1.6;margin-bottom:14px;'>{s['explicacao']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='background:{PALETA['fundo_sidebar']};border-left:3px solid {PALETA['verde']};"
                    f"border-radius:8px;padding:12px 16px;margin-bottom:14px;'>"
                    f"<b style='color:{PALETA['verde']};'>💰 Meta direta:</b> "
                    f"<b style='color:{PALETA['texto_principal']};'>{_fmt_brl(rv)}/mês</b> "
                    f"<span style='color:{PALETA['texto_secundario']};'>= <b>{rp:.1f}%</b> · "
                    f"<b>{_fmt_brl(rv*12)}/ano</b></span></div>", unsafe_allow_html=True)
                mz = _matriz(s['categoria_limpa'], s['economia_potencial'], emax)
                st.markdown(f"<div style='background:{PALETA['fundo_sidebar']};border-left:3px solid {mz['cor']};"
                    f"border-radius:8px;padding:12px 16px;margin-bottom:14px;'>"
                    f"<b style='color:{mz['cor']};'>{mz['emoji']} Matriz:</b> "
                    f"<span style='color:{PALETA['texto_principal']};'>{mz['q']}</span><br>"
                    f"<span style='color:{PALETA['texto_secundario']};font-size:12px;'>→ {mz['acao']}</span></div>",
                    unsafe_allow_html=True)
                hrs = _custo_hora(s['valor_atual'], salario_a_input)
                st.markdown(f"<div style='background:{PALETA['fundo_sidebar']};border:1px solid {PALETA['borda']};"
                    f"border-radius:8px;padding:12px 16px;margin-bottom:14px;color:{PALETA['texto_principal']};'>"
                    f"⏱️ <b>Horas de trabalho:</b> {hrs}h em '{s['categoria_limpa']}'.</div>", unsafe_allow_html=True)
                st.markdown("##### 🎛️ Simulador: e se eu cortar X%?")
                cs_ = st.columns([2, 3])
                with cs_[0]:
                    pct_s = st.slider("Percentual", 5, 80, int(rp) if rp >= 5 else 30, 5, key=f"sl_{s['categoria_limpa']}")
                sim = _sim_corte(s['valor_atual'], pct_s)
                with cs_[1]:
                    st.markdown(f"<div style='color:{PALETA['texto_principal']};padding-top:8px;'>"
                        f"💰 Mensal: <b style='color:{PALETA['verde']};'>{_fmt_brl(sim['mes'])}</b><br>"
                        f"📅 Anual: <b style='color:{PALETA['verde']};'>{_fmt_brl(sim['ano'])}</b></div>",
                        unsafe_allow_html=True)
                imp = _impacto_res(sim['mes'], meta_reserva_efetiva, total_fixos_a)
                if imp:
                    st.markdown(f"<div style='background:{PALETA['fundo_sidebar']};border-left:3px solid {PALETA['acento']};"
                        f"border-radius:8px;padding:12px 16px;margin-top:10px;color:{PALETA['texto_principal']};'>"
                        f"🛡️ <b>Impacto reserva:</b> +<b>{imp['meses_ano']}</b> meses/ano · "
                        f"<b>{imp['pct_meta']}%</b> da meta mensal.</div>", unsafe_allow_html=True)
                proj = _proj_lp(sim['mes'], 0.10)
                st.markdown(f"<div style='background:{PALETA['fundo_sidebar']};border-left:3px solid {PALETA['roxo']};"
                    f"border-radius:8px;padding:12px 16px;margin-top:10px;color:{PALETA['texto_principal']};'>"
                    f"📈 <b>10% a.a.:</b> 1a: <b>{_fmt_brl(proj['1'])}</b> · 5a: <b>{_fmt_brl(proj['5'])}</b> · "
                    f"10a: <b>{_fmt_brl(proj['10'])}</b> · 20a: <b style='color:{PALETA['verde']};'>{_fmt_brl(proj['20'])}</b></div>",
                    unsafe_allow_html=True)
                ev = _evol_cat(s['categoria_limpa'], df_variaveis, 6)
                if not ev.empty and len(ev) >= 2:
                    fe = px.line(ev, x="mes_ano", y="valor", markers=True, color_discrete_sequence=[PALETA['acento']])
                    fe.update_layout(paper_bgcolor="#151B23", plot_bgcolor="#151B23", font_color="#E6EDF3",
                        height=220, margin=dict(l=20,r=20,t=20,b=20))
                    st.plotly_chart(fe, use_container_width=True, key=f"ev_{s['categoria_limpa']}")
                rt = _retro(s['categoria_limpa'], df_variaveis)
                if rt:
                    st.warning(f"⚠️ '{s['categoria_limpa']}' subiu {rt['var']}% vs mês ant.")
                st.markdown("---")
                if jc:
                    st.success("✅ Corte já marcado.")
                else:
                    if st.button(f"✅ Marcar '{s['categoria_limpa']}' como concluído",
                                 key=f"bc_{s['categoria_limpa']}", use_container_width=True):
                        h_ = datetime.now()
                        marcar_corte_concluido(s['categoria_limpa'], rv, h_.month, h_.year)
                        st.success("Corte registrado!"); st.rerun()

        st.divider()
        df_mc = carregar_metas_corte()
        if not df_mc.empty:
            st.markdown("### 📈 Progresso das Metas de Corte Ativas")
            for _, m in df_mc.iterrows():
                pr_ = _prog_meta(m['categoria'], float(m['meta_reducao_pct']), df_variaveis)
                if pr_ is None: continue
                p = pr_['prog']
                if p >= 0.75: cp, lb = "#22C55E", "🟢 No caminho"
                elif p >= 0.40: cp, lb = "#F59E0B", "🟡 Atenção"
                else: cp, lb = "#EF4444", "🔴 Não está cortando"
                st.markdown(f"<div style='background:{PALETA['fundo_card']};border:1px solid {PALETA['borda']};"
                    f"border-radius:10px;padding:14px 18px;margin-bottom:8px;'>"
                    f"<div style='display:flex;justify-content:space-between;'>"
                    f"<b style='color:{PALETA['texto_principal']};'>🎯 {m['categoria']} (-{m['meta_reducao_pct']}%)</b>"
                    f"<span style='color:{cp};font-weight:600;'>{lb} — {int(p*100)}%</span></div>"
                    f"<div style='color:{PALETA['texto_secundario']};font-size:12px;margin-top:4px;'>"
                    f"Média: {_fmt_brl(pr_['media'])} · Atual: <b style='color:{PALETA['texto_principal']};'>{_fmt_brl(pr_['atual'])}</b> · "
                    f"Alvo: {_fmt_brl(pr_['alvo'])} · Economia: <b style='color:{PALETA['verde']};'>{_fmt_brl(pr_['eco'])}</b>"
                    f"</div></div>", unsafe_allow_html=True)
                st.progress(p)
            st.divider()

        st.markdown("### 🔎 Assinaturas Recorrentes")
        ass = _assin(df_variaveis)
        if ass.empty: st.info("Nenhuma assinatura detectada.")
        else:
            tt = ass["anual"].sum()
            st.warning(f"💡 **Potencial:** {_fmt_brl(tt)}/ano ({_fmt_brl(tt/12)}/mês).")
            st.dataframe(ass, use_container_width=True, hide_index=True)
        st.divider()

        st.markdown("### 👻 Gastos Invisíveis")
        inv = _invis(df_variaveis, 60)
        if inv.empty: st.info("Nenhum gasto invisível.")
        else:
            ti = inv["anual"].sum()
            st.warning(f"💡 Pequenos gastos: {_fmt_brl(ti)}/ano ({_fmt_brl(ti/12)}/mês).")
            st.dataframe(inv, use_container_width=True, hide_index=True)
        st.divider()

        st.markdown("### 📋 Checklist de Ações da Semana")
        hs_ = datetime.now()
        sem = f"{hs_.year}-W{hs_.isocalendar()[1]:02d}"
        if st.button("🔄 Gerar checklist desta semana", key="btn_chk_f"):
            tf = gerar_checklist_semanal(df_sug, df_cc)
            if tf:
                salvar_checklist_semanal(tf, sem); st.success(f"{len(tf)} tarefas criadas!"); st.rerun()
            else: st.info("Todas concluídas. 🎉")
        dc = carregar_checklist_semana(sem)
        if not dc.empty:
            cc_ = dc[dc['concluida'] == True]
            t_ = len(dc); pc = len(cc_) / t_ if t_ > 0 else 0
            st.progress(pc)
            st.markdown(f"**Progresso:** {len(cc_)}/{t_} ({pc*100:.0f}%)")
            for _, it in dc.iterrows():
                c1, c2, c3 = st.columns([0.5, 4, 1.5])
                with c1: mk = st.checkbox("", value=bool(it['concluida']), key=f"chk_{it['id']}")
                with c2:
                    tx = f"~~{it['acao']}~~" if mk else it['acao']
                    st.markdown(tx)
                with c3:
                    st.markdown(f"<span style='color:{PALETA['verde']};'>💰 {_fmt_brl(it['economia_estimada'])}</span>",
                        unsafe_allow_html=True)
                if mk != bool(it['concluida']):
                    marcar_item_checklist(it['id'], mk); st.rerun()
        st.divider()

        st.markdown("### 📈 Projeção de Economia Acumulada")
        ch1, ch2 = st.columns([1, 1])
        with ch1: hz = st.slider("Horizonte (meses)", 6, 36, 24, 6, key="hz_pj_f")
        with ch2: rd = st.checkbox("Reinvestir a 10% a.a.", value=False, key="rd_pj_f")
        le = list(range(1, hz + 1)); ea_ = []; vt = 0.0
        if rd:
            tmx = (1 + 0.10) ** (1/12) - 1; sl = 0.0
            for _ in le: sl = (sl + tm_) * (1 + tmx); ea_.append(sl)
            vt = sl
        else:
            for m_ in le: ea_.append(tm_ * m_)
            vt = tm_ * hz
        dpe = pd.DataFrame({"Mês": le, "Economia Acumulada": ea_})
        fpe = px.area(dpe, x="Mês", y="Economia Acumulada", title=f"Economia em {hz} meses")
        fpe.update_traces(line_color="#22C55E", fillcolor="rgba(34,197,94,0.20)")
        fpe.update_layout(paper_bgcolor="#151B23", plot_bgcolor="#151B23", font_color="#E6EDF3", showlegend=False)
        st.plotly_chart(fpe, use_container_width=True)
        ck_1, ck_2 = st.columns(2)
        ck_1.metric("💰 Total", _fmt_brl(vt)); ck_2.metric("📅 Média mensal", _fmt_brl(vt / hz))
        st.divider()

        st.markdown("### 📄 Exportar Plano de Corte")
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        sty = getSampleStyleSheet()
        story = [Paragraph("<b>PLANO DE CORTES</b>",
            ParagraphStyle('T', parent=sty['Heading1'], fontSize=18, textColor=colors.HexColor('#3B82F6'), alignment=1)),
            Spacer(1, 15)]
        data = [["#", "Categoria", "Atual", "Corte/mês", "Economia/ano"]]
        for _, s in df_sug.iterrows():
            data.append([str(int(s['prioridade'])), str(s['categoria_limpa']),
                f"R$ {s['valor_atual']:,.2f}", f"R$ {s['corte_sugerido']:,.2f}", f"R$ {s['economia_potencial']:,.2f}"])
        tv_ = Table(data, colWidths=[25, 130, 100, 100, 120])
        tv_.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#151B23')),
            ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#232B36')),
            ('FONTSIZE',(0,0),(-1,-1),9)]))
        story.append(tv_); doc.build(story); buf.seek(0)
        st.download_button("📥 Baixar PDF do Plano", data=buf.getvalue(),
            file_name=f"Plano_Cortes_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf", use_container_width=True, key="dl_pdf_f")
        st.divider()

        st.markdown("### 🎯 Definir Metas de Corte")
        with st.form("form_mc_f", clear_on_submit=True):
            fm1, fm2 = st.columns([3, 2])
            ce = fm1.selectbox("Categoria", options=df_sug["categoria"].tolist(), key="cf_mf")
            mpc = fm2.number_input("Meta redução (%)", 1.0, 100.0, 20.0, 5.0, key="pct_mf")
            if st.form_submit_button("💾 Salvar Meta"):
                cl = ce.split(" ", 1)[-1]
                salvar_meta_corte(cl, mpc); st.success("Meta salva!"); st.rerun()
        if st.button("📥 Salvar Análise no Histórico", use_container_width=True, key="sh_f"):
            ha = datetime.now()
            salvar_analise_corte(ha.month, ha.year, df_sug.to_dict("records"))
            st.success("Análise salva!")

    st.divider()
    st.markdown("### ✅ Cortes Já Realizados")
    df_cc2 = carregar_cortes_concluidos()
    if not df_cc2.empty:
        te = df_cc2['valor_economia'].sum()
        st.success(f"🎉 Já economizou **{_fmt_brl(te)}/mês** (**{_fmt_brl(te*12)}/ano**)!")
        ds_ = df_cc2[["categoria","valor_economia","mes","ano","concluido_em"]].copy()
        ds_["mes"] = ds_["mes"].apply(lambda x: meses_nomes[int(x)-1] if 1 <= int(x) <= 12 else x)
        ds_.columns = ["Categoria","Economia (R$/mês)","Mês","Ano","Data"]
        st.dataframe(ds_, use_container_width=True, hide_index=True)
        cu = st.columns(min(4, len(df_cc2)))
        for i, (_, c) in enumerate(df_cc2.iterrows()):
            with cu[i % 4]:
                if st.button(f"🗑️ {c['categoria']}", key=f"un_{c['id']}"):
                    remover_corte_concluido(c['id']); st.rerun()
    else: st.info("Nenhum corte marcado.")

    st.divider()
    st.markdown("### 📜 Histórico de Análises Salvas")
    dha = carregar_historico_analises()
    if not dha.empty:
        dh2 = dha[["mes","ano","categoria","valor_atual","valor_sugerido","economia_potencial","prioridade","criado_em"]].head(30).copy()
        dh2["mes"] = dh2["mes"].apply(lambda x: meses_nomes[int(x)-1] if 1 <= int(x) <= 12 else x)
        dh2.columns = ["Mês","Ano","Categoria","Valor Atual","Corte","Economia Anual","Prioridade","Data"]
        st.dataframe(dh2, use_container_width=True, hide_index=True)
    else: st.info("Nenhuma análise salva.")

# =============================================================================
# TAB 9 — PROSPERIDADE  (✅ CORRIGIDO)
# =============================================================================
with tab9:
    st.subheader("🚀 Painel de Prosperidade")
    st.caption("Patrimônio · Carteira · Metas · FIRE · Dívidas · Rendas · Diagnóstico · Proteção · Calendário")

    secao = st.selectbox("Selecione a seção:",
        ["💎 Patrimônio (Net Worth)","💼 Carteira de Investimentos","🎯 Metas com Prazo","🔥 Calculadora FIRE",
         "🚨 Dívidas & Quitação","💰 Rendas Extras","🧠 Diagnóstico Financeiro","🛡️ Checklist de Proteção",
         "📅 Calendário Financeiro"], key="sec_pros")
    st.divider()

    # =========================================================
    # 💎 PATRIMÔNIO (NET WORTH)
    # =========================================================
    if secao == "💎 Patrimônio (Net Worth)":
        st.markdown("### 💎 Patrimônio Líquido")
        st.caption("**Net Worth = Ativos − Passivos**.")
        nw = calcular_net_worth()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total de Ativos", _fmt_brl(nw["ativos"]))
        c2.metric("Total de Passivos", _fmt_brl(nw["passivos"]))
        c3.metric("Patrimônio Líquido", _fmt_brl(nw["liquido"]),
            delta="✅ positivo" if nw["liquido"] >= 0 else "⚠️ negativo",
            delta_color="normal" if nw["liquido"] >= 0 else "inverse")
        st.markdown("")
        cp1, cp2 = st.columns(2)
        with cp1:
            st.markdown("#### ➕ Ativo")
            with st.form("f_at", clear_on_submit=True):
                na = st.text_input("Nome"); ca = st.selectbox("Categoria",
                    ["Conta corrente","Poupança","Investimentos","Imóvel","Veículo","Cripto","Outros"])
                va = st.number_input("Valor (R$)", min_value=0.0, step=100.0)
                if st.form_submit_button("Adicionar", use_container_width=True):
                    if na.strip(): adicionar_ativo(na, ca, va); st.rerun()
        with cp2:
            st.markdown("#### ➖ Passivo")
            with st.form("f_ps", clear_on_submit=True):
                np_ = st.text_input("Nome"); tp = st.selectbox("Tipo",
                    ["Cartão de crédito","Empréstimo pessoal","Financiamento","Cheque especial","Consignado","Outros"])
                vp = st.number_input("Valor (R$)", min_value=0.0, step=100.0)
                pp = st.number_input("Parcelas", min_value=1, value=1, step=1)
                jp = st.number_input("Juros mensal (%)", min_value=0.0, step=0.1, format="%.2f")
                if st.form_submit_button("Adicionar", use_container_width=True):
                    if np_.strip() and vp > 0: adicionar_passivo(np_, tp, vp, pp, jp); st.rerun()
        st.divider()
        da = carregar_ativos(); dp = carregar_passivos()
        cl1, cl2 = st.columns(2)
        with cl1:
            st.markdown("#### 📋 Ativos")
            if da.empty: st.info("Nenhum.")
            else:
                for _, a in da.iterrows():
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                    c1.write(f"**{a['nome']}**"); c2.write(a['categoria']); c3.write(_fmt_brl(a['valor']))
                    if c4.button("🗑️", key=f"da_{a['id']}"): remover_ativo(a['id']); st.rerun()
        with cl2:
            st.markdown("#### 📋 Passivos")
            if dp.empty: st.info("Nenhum.")
            else:
                for _, p in dp.iterrows():
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                    c1.write(f"**{p['nome']}**"); c2.write(f"{p['tipo']} ({p['juros_mensal']}%/m)")
                    c3.write(_fmt_brl(p['valor_total']))
                    if c4.button("🗑️", key=f"dp_{p['id']}"): remover_passivo(p['id']); st.rerun()

    # =========================================================
    # 💼 CARTEIRA DE INVESTIMENTOS  ✅ CORRIGIDO
    # =========================================================
    elif secao == "💼 Carteira de Investimentos":
        st.markdown("### 💼 Carteira de Investimentos")
        st.caption("Cadastre cada posição. Veja rentabilidade e alocação.")
        dct = carregar_carteira()
        if not dct.empty:
            ti = dct["valor_investido"].sum(); ta_ = dct["valor_atual"].sum()
            ren = ta_ - ti; rp_ = (ren / ti * 100) if ti > 0 else 0
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Investido", _fmt_brl(ti)); c2.metric("Atual", _fmt_brl(ta_))
            c3.metric("Rendimento", _fmt_brl(ren), delta=f"{rp_:.2f}%",
                delta_color="normal" if ren >= 0 else "inverse")
            c4.metric("Ativos", f"{len(dct)}")
        with st.expander("➕ Nova posição", expanded=dct.empty):
            with st.form("f_inv", clear_on_submit=True):
                at = st.text_input("Ativo"); cls = st.selectbox("Classe",
                    ["Renda Fixa","Ações","FIIs","ETFs","Cripto","Fundos","Previdência","Internacional","Outros"])
                ci1, ci2 = st.columns(2)
                with ci1: vi = st.number_input("Valor investido (R$)", min_value=0.0, step=100.0)
                with ci2: va = st.number_input("Valor atual (R$)", min_value=0.0, step=100.0)
                da_ = st.date_input("Data do aporte", value=datetime.now())
                if st.form_submit_button("Adicionar", use_container_width=True):
                    if at.strip() and vi > 0: adicionar_investimento(at, cls, vi, va, da_); st.rerun()
        if not dct.empty:
            st.divider()
            st.markdown("#### 📊 Alocação por Classe")
            pcl = dct.groupby("classe").agg(va=("valor_atual","sum"), vi=("valor_investido","sum")).reset_index()
            pcl["pct"] = (pcl["va"] / pcl["va"].sum() * 100).round(1)
            pcl["rent"] = ((pcl["va"] - pcl["vi"]) / pcl["vi"].replace(0, 1) * 100).round(2)
            cg1, cg2 = st.columns(2)
            with cg1:
                fp = px.pie(pcl, names="classe", values="va", hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
                fp.update_layout(paper_bgcolor="#151B23", plot_bgcolor="#151B23", font_color="#E6EDF3")
                st.plotly_chart(fp, use_container_width=True)
            with cg2:
                # ✅ CORREÇÃO: selecionar apenas as 4 colunas necessárias
                ds_ = pcl[["classe", "va", "pct", "rent"]].copy()
                ds_["va"] = ds_["va"].apply(_fmt_brl)
                ds_["pct"] = ds_["pct"].apply(lambda v: f"{v}%")
                ds_["rent"] = ds_["rent"].apply(lambda v: f"{v}%")
                ds_.columns = ["Classe", "Valor", "% Carteira", "Rentabilidade"]
                st.dataframe(ds_, use_container_width=True, hide_index=True)
            st.divider()
            st.markdown("#### 🗑️ Posições")
            for _, p in dct.iterrows():
                c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 1])
                c1.write(f"**{p['ativo']}**"); c2.write(p['classe'])
                c3.write(_fmt_brl(p['valor_investido'])); c4.write(_fmt_brl(p['valor_atual']))
                if c5.button("🗑️", key=f"di_{p['id']}"): remover_investimento(p['id']); st.rerun()

    # =========================================================
    # 🎯 METAS COM PRAZO
    # =========================================================
    elif secao == "🎯 Metas com Prazo":
        st.markdown("### 🎯 Metas Financeiras")
        dmf = carregar_metas_financeiras()
        with st.expander("➕ Nova meta", expanded=dmf.empty):
            with st.form("f_mf", clear_on_submit=True):
                nm = st.text_input("Nome"); cm1, cm2 = st.columns(2)
                with cm1:
                    av = st.number_input("Valor alvo (R$)", min_value=0.0, step=1000.0)
                    at = st.number_input("Guardado (R$)", min_value=0.0, step=100.0)
                with cm2:
                    pz = st.number_input("Prazo (anos)", 1, 50, 3)
                    ctg = st.selectbox("Categoria", ["Curto prazo","Médio prazo","Longo prazo","Viagem","Imóvel","Veículo","Educação","Geral"])
                if st.form_submit_button("Adicionar", use_container_width=True):
                    if nm.strip() and av > 0: adicionar_meta_financeira(nm, av, at, pz, ctg); st.rerun()
        if not dmf.empty:
            st.divider()
            for _, m in dmf.iterrows():
                ft = max(0.0, m['valor_alvo'] - m['valor_atual'])
                pct = (m['valor_atual'] / m['valor_alvo'] * 100) if m['valor_alvo'] > 0 else 0
                mr_ = m['prazo_anos'] * 12
                an = ft / mr_ if mr_ > 0 else 0
                cor = "#22C55E" if pct >= 75 else ("#F59E0B" if pct >= 40 else "#EF4444")
                st.markdown(f"<div style='background:{PALETA['fundo_card']};border:1px solid {PALETA['borda']};"
                    f"border-left:4px solid {cor};border-radius:12px;padding:16px 20px;margin-bottom:10px;'>"
                    f"<div style='display:flex;justify-content:space-between;'>"
                    f"<b style='color:{PALETA['texto_principal']};'>🎯 {m['nome']} "
                    f"<span style='color:{PALETA['texto_secundario']};font-size:11px;'>[{m['categoria']}]</span></b>"
                    f"<span style='color:{cor};font-weight:700;'>{pct:.1f}%</span></div>"
                    f"<div style='color:{PALETA['texto_secundario']};font-size:12px;margin-top:6px;'>"
                    f"Guardado: <b style='color:{PALETA['texto_principal']};'>{_fmt_brl(m['valor_atual'])}</b> / "
                    f"Alvo: <b>{_fmt_brl(m['valor_alvo'])}</b> · Prazo: <b>{m['prazo_anos']} anos</b> · "
                    f"Aporte necessário: <b style='color:{PALETA['verde']};'>{_fmt_brl(an)}</b>"
                    f"</div></div>", unsafe_allow_html=True)
                st.progress(min(pct / 100, 1.0))
                c1, c2 = st.columns([3, 1])
                with c1:
                    nv = st.number_input(f"Atualizar '{m['nome']}'", min_value=0.0, value=float(m['valor_atual']),
                        step=100.0, key=f"up_{m['id']}")
                with c2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("💾", key=f"bt_{m['id']}", use_container_width=True):
                        atualizar_valor_meta_financeira(m['id'], nv); st.rerun()
                    if st.button("🗑️", key=f"dmf_{m['id']}", use_container_width=True):
                        remover_meta_financeira(m['id']); st.rerun()

    # =========================================================
    # 🔥 CALCULADORA FIRE  ✅ CORRIGIDO
    # =========================================================
    elif secao == "🔥 Calculadora FIRE":
        st.markdown("### 🔥 Independência Financeira (FIRE)")
        c1, c2 = st.columns(2)
        with c1:
            gm = st.number_input("Gasto mensal (R$)", value=float(total_fixos_a + total_gastos_variaveis), step=100.0, key="fg")
            pa_ = st.number_input("Patrimônio atual (R$)", value=float(calcular_net_worth()["liquido"]), step=1000.0, key="fp")
        with c2:
            am = st.number_input("Aporte mensal (R$)", value=float(meta_reserva_efetiva), step=100.0, key="fa")
            tr_ = st.slider("Taxa retirada (%)", 3.0, 6.0, 4.0, 0.5, key="ft") / 100

        # ✅ CORREÇÃO: usar parâmetro posicional (tr_ = taxa de retirada)
        f = calcular_fire(gm, pa_, am, tr_)

        if f:
            st.markdown("")
            f1, f2, f3 = st.columns(3)
            f1.metric("💎 Número Mágico", _fmt_brl(f["numero_magico"]), delta="quanto precisa ter")
            f2.metric("📉 Falta", _fmt_brl(f["falta"]))
            f3.metric("⏱️ Tempo FIRE", f"{f['anos_para_fire']} anos" if f["anos_para_fire"] else "—",
                       delta=f"com {_fmt_brl(am)}/mês")
            st.markdown(f"<div style='background:{PALETA['fundo_card']};border-left:4px solid {PALETA['roxo']};"
                f"border-radius:12px;padding:18px 22px;margin-top:16px;'>"
                f"<b style='color:{PALETA['texto_principal']};font-size:15px;'>🎉 Com {_fmt_brl(f['numero_magico'])} investidos, "
                f"retira {_fmt_brl(f['retirada_mensal_segura'])}/mês para sempre.</b></div>",
                unsafe_allow_html=True)
            if pa_ < f["numero_magico"]:
                st.divider()
                st.markdown("#### 📈 Evolução")
                amx = min(40, int((f["anos_para_fire"] or 30) + 5))
                dd = []; sl = pa_; rm = 0.07 / 12
                for mm in range(0, amx * 12 + 1):
                    if mm % 12 == 0: dd.append({"Ano": mm//12, "Patrimônio": sl, "Meta": f["numero_magico"]})
                    sl = sl * (1 + rm) + am
                dfF = pd.DataFrame(dd)
                fg = px.area(dfF, x="Ano", y=["Patrimônio","Meta"], color_discrete_sequence=["#22C55E","#7C3AED"])
                fg.update_layout(paper_bgcolor="#151B23", plot_bgcolor="#151B23", font_color="#E6EDF3")
                st.plotly_chart(fg, use_container_width=True)

    # =========================================================
    # 🚨 DÍVIDAS E QUITAÇÃO
    # =========================================================
    elif secao == "🚨 Dívidas & Quitação":
        st.markdown("### 🚨 Análise de Dívidas")
        dp_ = carregar_passivos()
        if dp_.empty: st.success("🟢 Nenhuma dívida cadastrada!")
        else:
            td = dp_["valor_total"].sum()
            jm = (dp_["valor_total"] * dp_["juros_mensal"] / 100).sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Dívidas", _fmt_brl(td))
            c2.metric("Juros/mês", _fmt_brl(jm), delta_color="inverse")
            c3.metric("Juros/ano", _fmt_brl(jm * 12), delta="🔥 queima", delta_color="inverse")
            st.divider()
            st.markdown("#### 🎯 Ordem de quitação (método avalanche)")
            dord = calcular_ordem_quitacao(dp_)
            for _, p in dord.iterrows():
                cor = "#EF4444" if p['ordem'] == 1 else ("#F59E0B" if p['ordem'] <= 3 else "#3B82F6")
                st.markdown(f"<div style='background:{PALETA['fundo_card']};border:1px solid {PALETA['borda']};"
                    f"border-left:4px solid {cor};border-radius:10px;padding:12px 16px;margin-bottom:8px;'>"
                    f"<b style='color:{cor};'>#{int(p['ordem'])}</b> · "
                    f"<b style='color:{PALETA['texto_principal']};'>{p['nome']}</b> "
                    f"<span style='color:{PALETA['texto_secundario']};font-size:12px;'>"
                    f"[{p['tipo']}] · {_fmt_brl(p['valor_total'])} · juros {p['juros_mensal']}%/m · "
                    f"custo {_fmt_brl(p['custo_juros_mensal'])}</span></div>", unsafe_allow_html=True)

    # =========================================================
    # 💰 RENDAS EXTRAS
    # =========================================================
    elif secao == "💰 Rendas Extras":
        st.markdown("### 💰 Rendas")
        dr_ = carregar_rendas()
        hj = datetime.now()
        with st.expander("➕ Adicionar renda", expanded=True):
            with st.form("f_rd", clear_on_submit=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                dr = c1.text_input("Descrição"); vr = c2.number_input("Valor (R$)", min_value=0.0, step=100.0)
                tr = c3.selectbox("Tipo", ["Salário","Freelance","Aluguel","Dividendos","Vendas","Bico","Outros"])
                c4, c5 = st.columns(2)
                mr = c4.selectbox("Mês", list(range(1, 13)), index=hj.month - 1, format_func=lambda x: meses_nomes[x-1])
                ar = c5.number_input("Ano", 2020, 2100, hj.year)
                if st.form_submit_button("Adicionar", use_container_width=True):
                    if dr.strip() and vr > 0: adicionar_renda(dr, vr, mr, ar, tr); st.rerun()
        if not dr_.empty:
            ta_ = dr_[dr_["ano"] == hj.year]["valor"].sum()
            tm_ = dr_[(dr_["ano"] == hj.year) & (dr_["mes"] == hj.month)]["valor"].sum()
            c1, c2 = st.columns(2)
            c1.metric(f"Rendas {meses_nomes[hj.month-1]}", _fmt_brl(tm_))
            c2.metric(f"Rendas {hj.year}", _fmt_brl(ta_))
            st.divider()
            pt = dr_.groupby("tipo")["valor"].sum().reset_index()
            frt = px.bar(pt, x="tipo", y="valor", color="tipo", color_discrete_sequence=px.colors.qualitative.Set2)
            frt.update_layout(paper_bgcolor="#151B23", plot_bgcolor="#151B23", font_color="#E6EDF3", showlegend=False)
            st.plotly_chart(frt, use_container_width=True)
            st.markdown("#### 📋 Lançamentos")
            for _, r in dr_.head(30).iterrows():
                c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 1])
                c1.write(f"**{r['descricao']}**"); c2.write(r['tipo'])
                c3.write(f"{meses_nomes[int(r['mes'])-1]}/{r['ano']}"); c4.write(_fmt_brl(r['valor']))
                if c5.button("🗑️", key=f"dr_{r['id']}"): remover_renda(r['id']); st.rerun()

    # =========================================================
    # 🧠 DIAGNÓSTICO FINANCEIRO
    # =========================================================
    elif secao == "🧠 Diagnóstico Financeiro":
        st.markdown("### 🧠 Diagnóstico Financeiro Pessoal")
        nw = calcular_net_worth()
        dg = calcular_diagnostico(salario_a_input + vr_a_input, total_fixos_a + total_gastos_variaveis,
                                   total_fixos_a, meta_reserva_efetiva * 6, nw["ativos"], nw["passivos"])
        nota = dg["nota"]
        if nota >= 80: cn, sn = "#22C55E", "🟢 EXCELENTE"
        elif nota >= 60: cn, sn = "#F59E0B", "🟡 BOM"
        elif nota >= 40: cn, sn = "#F59E0B", "🟠 REGULAR"
        else: cn, sn = "#EF4444", "🔴 CRÍTICO"
        st.markdown(f"<div style='background:{PALETA['fundo_card']};border:2px solid {cn};"
            f"border-radius:16px;padding:32px;text-align:center;margin:16px 0;'>"
            f"<div style='color:{PALETA['texto_secundario']};font-size:12px;letter-spacing:2px;'>SUA NOTA</div>"
            f"<div style='color:{cn};font-size:64px;font-weight:700;line-height:1.1;'>{nota:.0f}</div>"
            f"<div style='color:{cn};font-size:14px;font-weight:600;letter-spacing:1px;'>{sn}</div></div>",
            unsafe_allow_html=True)
        st.markdown("#### Detalhamento")
        for cr_, pts in dg["detalhes"].items():
            mx = {"poupanca":25,"reserva":25,"divida":25,"investimento":15,"diversificacao":10}.get(cr_, 25)
            pc_ = (pts / mx) if mx > 0 else 0
            cc = "#22C55E" if pc_ >= 0.7 else ("#F59E0B" if pc_ >= 0.4 else "#EF4444")
            lb = {"poupanca":"Taxa de poupança","reserva":"Reserva emergência","divida":"Controle de dívidas",
                  "investimento":"Capacidade investir","diversificacao":"Diversificação"}[cr_]
            st.markdown(f"<div style='background:{PALETA['fundo_card']};border:1px solid {PALETA['borda']};"
                f"border-radius:10px;padding:12px 16px;margin-bottom:8px;'>"
                f"<div style='display:flex;justify-content:space-between;'>"
                f"<span style='color:{PALETA['texto_principal']};'>{lb}</span>"
                f"<span style='color:{cc};font-weight:700;'>{pts:.1f} / {mx} pts</span></div></div>",
                unsafe_allow_html=True)
            st.progress(pc_)
        st.markdown("#### 📊 Extras")
        st.write(f"- Taxa de poupança: **{dg['taxa_poupanca_pct']}%**")
        st.write(f"- Meses de reserva: **{dg['meses_reserva']}** (ideal: 6+)")

    # =========================================================
    # 🛡️ CHECKLIST DE PROTEÇÃO
    # =========================================================
    elif secao == "🛡️ Checklist de Proteção":
        st.markdown("### 🛡️ Checklist de Proteção")
        dpr = carregar_protecoes()
        if dpr.empty: st.info("Rode o SQL de seed.")
        else:
            tt = len(dpr); ft = dpr["contratado"].sum()
            pc_ = (ft / tt * 100) if tt > 0 else 0
            st.markdown(f"<div style='background:{PALETA['fundo_card']};border:1px solid {PALETA['borda']};"
                f"border-radius:12px;padding:16px 20px;margin-bottom:16px;'>"
                f"<b style='color:{PALETA['texto_principal']};'>Progresso: {int(ft)}/{tt} itens ({pc_:.0f}%)</b></div>",
                unsafe_allow_html=True)
            st.progress(pc_ / 100)
            st.markdown("")
            for _, p in dpr.iterrows():
                c1, c2 = st.columns([5, 1])
                with c1:
                    mk = st.checkbox(f"**{p['item']}**", value=bool(p['contratado']), key=f"pr_{p['id']}")
                    if mk != bool(p['contratado']): atualizar_protecao(p['item'], mk); st.rerun()

    # =========================================================
    # 📅 CALENDÁRIO FINANCEIRO
    # =========================================================
    elif secao == "📅 Calendário Financeiro":
        st.markdown("### 📅 Calendário Financeiro")
        dcp = carregar_contas_pagar()
        hdt = datetime.now().date()
        with st.expander("➕ Adicionar conta", expanded=True):
            with st.form("f_ct", clear_on_submit=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                dc = c1.text_input("Descrição"); vc = c2.number_input("Valor (R$)", min_value=0.0, step=10.0)
                cc = c3.selectbox("Categoria", ["Moradia","Alimentação","Transporte","Saúde","Educação","Lazer","Cartão","Outros"])
                vc_ = st.date_input("Vencimento", value=datetime.now())
                if st.form_submit_button("Adicionar", use_container_width=True):
                    if dc.strip() and vc > 0: adicionar_conta_pagar(dc, vc, vc_, cc); st.rerun()
        if not dcp.empty:
            pend = dcp[dcp["pago"] == False]
            tp_ = pend["valor"].sum()
            vh = pend[pend["vencimento"].dt.date == hdt]
            vs = pend[(pend["vencimento"].dt.date >= hdt) & (pend["vencimento"].dt.date <= hdt + pd.Timedelta(days=7))]
            vv = pend[pend["vencimento"].dt.date < hdt]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Pendente", _fmt_brl(tp_))
            c2.metric("Vence hoje", f"{len(vh)}", delta=_fmt_brl(vh['valor'].sum()) if not vh.empty else "—")
            c3.metric("Próx. 7 dias", f"{len(vs)}", delta=_fmt_brl(vs['valor'].sum()) if not vs.empty else "—")
            c4.metric("Vencidas", f"{len(vv)}",
                delta="⚠️" if not vv.empty else "—", delta_color="inverse" if not vv.empty else "normal")
            if not vv.empty: st.error(f"⚠️ {len(vv)} conta(s) vencida(s): {_fmt_brl(vv['valor'].sum())}")
            st.divider()
            st.markdown("#### 📋 Contas")
            for _, ct in dcp.iterrows():
                vd = ct["vencimento"].date() if hasattr(ct["vencimento"], "date") else ct["vencimento"]
                dd = (vd - hdt).days
                if ct["pago"]: cor, stt = "#22C55E", "✅ pago"
                elif dd < 0: cor, stt = "#EF4444", f"⚠️ vencida {abs(dd)}d"
                elif dd == 0: cor, stt = "#F59E0B", "⏰ hoje"
                elif dd <= 7: cor, stt = "#F59E0B", f"⏳ em {dd}d"
                else: cor, stt = "#3B82F6", f"📅 em {dd}d"
                c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 2, 1, 1])
                c1.write(f"**{ct['descricao']}**"); c2.write(ct['categoria'])
                c3.write(vd.strftime("%d/%m/%Y"))
                c4.write(f"<span style='color:{cor};'>{stt}</span>", unsafe_allow_html=True)
                c5.write(_fmt_brl(ct['valor']))
                with c6:
                    if not ct["pago"]:
                        if st.button("✓", key=f"pg_{ct['id']}"): marcar_conta_paga(ct['id'], True); st.rerun()
                    else:
                        if st.button("🗑️", key=f"dc_{ct['id']}"): remover_conta_pagar(ct['id']); st.rerun()

# FIM
