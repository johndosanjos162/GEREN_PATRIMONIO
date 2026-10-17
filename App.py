import streamlit as st
import requests
import re
import urllib.parse
import os

# ============================================================
# IMPORTAÇÕES OPCIONAIS
# ============================================================
try:
    from openai import OpenAI
except ImportError:
    st.error("Instale: pip install openai")
    st.stop()

try:
    from vectorgov import VectorGov
    VECTORGOV_DISPONIVEL = True
except ImportError:
    VECTORGOV_DISPONIVEL = False

try:
    import google.generativeai as genai
    GEMINI_DISPONIVEL = True
except ImportError:
    GEMINI_DISPONIVEL = False

# ============================================================
# CARREGAMENTO DE SEGREDOS (secrets.toml ou variáveis de ambiente)
# ============================================================
def get_secret(nome, padrao=""):
    try:
        return st.secrets[nome]
    except (KeyError, FileNotFoundError):
        return os.getenv(nome, padrao)

DEEPSEEK_KEY = get_secret("DEEPSEEK_API_KEY")
VECTORGOV_KEY = get_secret("VECTORGOV_API_KEY")
GEMINI_KEY = get_secret("GEMINI_API_KEY")

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="Gerador de Questões Verificadas",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 Gerador de Questões Verificadas")
st.caption(
    "A **DeepSeek** cria o enunciado no estilo da banca escolhida. "
    "A resposta é buscada em **fontes oficiais** (legislação, dicionário, cálculo, web)."
)

if not DEEPSEEK_KEY:
    st.error("⚠️ Configure `DEEPSEEK_API_KEY` em `.streamlit/secrets.toml` para começar.")
    st.stop()

# ============================================================
# CLIENTE DEEPSEEK
# ============================================================
deepseek_client = OpenAI(
    api_key=DEEPSEEK_KEY,
    base_url="https://api.deepseek.com"
)

# ============================================================
# PROMPT DE GERAÇÃO
# ============================================================
PROMPT_GERAR = """Você é um elaborador de questões para concursos públicos.
Banca alvo: {banca}.
Matéria: {materia}.

Sua ÚNICA tarefa é criar o ENUNCIADO de uma questão inédita, no estilo da banca {banca}, sobre a matéria informada.
NÃO forneça alternativas.
NÃO responda à questão.
NÃO diga qual é a resposta correta.
Apenas escreva o texto do enunciado, de forma clara e objetiva.

Enunciado gerado:"""

# ============================================================
# FUNÇÕES DE BUSCA
# ============================================================
@st.cache_data(show_spinner=False)
def buscar_direito(pergunta):
    if not VECTORGOV_DISPONIVEL:
        return "⚠️ Biblioteca `vectorgov` não instalada."
    if not VECTORGOV_KEY:
        return "⚠️ Chave VectorGov não configurada."
    try:
        vg = VectorGov(api_key=VECTORGOV_KEY)
        resultados = vg.search(pergunta)
        if not resultados:
            return "Nenhum trecho de legislação relevante encontrado."
        hit = resultados[0]
        fonte = getattr(hit, "source", "Fonte não informada")
        texto = getattr(hit, "text", "")[:800]
        return f"📖 **Base legal:** {fonte}\n\n> {texto}..."
    except Exception as e:
        return f"Erro na busca jurídica: {e}"


@st.cache_data(show_spinner=False)
def buscar_portugues(pergunta):
    palavras = re.findall(
        r"\b[a-zA-ZáàâãéèêíìîóòôõúùûçÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ]{4,}\b",
        pergunta
    )
    if not palavras:
        return "Não foi possível extrair palavra-chave para o dicionário."
    stopwords = {"qual", "quais", "como", "onde", "quando", "porque",
                 "para", "sobre", "entre", "após", "segundo", "assinale"}
    candidatas = [p for p in palavras if p.lower() not in stopwords]
    termo = candidatas[0] if candidatas else palavras[0]
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/pt/{urllib.parse.quote(termo)}"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 404:
            return f"A palavra **'{termo}'** não foi encontrada no dicionário."
        resp.raise_for_status()
        dados = resp.json()
        if dados and isinstance(dados, list):
            m = dados[0]["meanings"][0]
            classe = m.get("partOfSpeech", "classe não informada")
            definicao = m["definitions"][0].get("definition", "")
            return f"📚 **Definição oficial de '{termo}'** ({classe}):\n\n> {definicao}"
        return "Definição não encontrada."
    except Exception as e:
        return f"Erro na busca do dicionário: {e}"


@st.cache_data(show_spinner=False)
def buscar_matematica(pergunta):
    match = re.search(r"([\d\.\+\-\*\/\(\)\s\^]+)", pergunta)
    if not match:
        return "Nenhuma expressão matemática simples detectada."
    expressao = match.group(1).strip()
    if len(expressao) < 3:
        return "Expressão muito curta para calcular."
    try:
        url = f"https://api.mathjs.org/v4/?expr={urllib.parse.quote(expressao)}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return f"🧮 **Resultado do cálculo:**\n\n`{expressao} = {resp.text.strip()}`"
    except Exception as e:
        return f"Erro ao calcular: {e}"


@st.cache_data(show_spinner=False)
def buscar_geral(pergunta):
    if not GEMINI_DISPONIVEL:
        return "⚠️ Biblioteca `google-generativeai` não instalada."
    if not GEMINI_KEY:
        return "⚠️ Chave Gemini não configurada."
    try:
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        tool = {"google_search_retrieval": {}}
        resposta = model.generate_content(
            f"Responda de forma objetiva e direta, com base em fontes confiáveis: {pergunta}",
            tools=[tool]
        )
        texto = resposta.text.strip() if resposta.text else "Nenhuma resposta gerada."
        return f"🌐 **Resposta com base em busca na web:**\n\n{texto}"
    except Exception as e:
        return f"Erro na busca geral: {e}"


def gerar_pergunta(banca, materia):
    """Chama a DeepSeek para gerar o enunciado."""
    prompt = PROMPT_GERAR.format(banca=banca, materia=materia)
    resposta = deepseek_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=400
    )
    pergunta = resposta.choices[0].message.content.strip()
    return re.sub(r'^["\']|["\']$', "", pergunta)


def buscar_resposta(materia, pergunta):
    """Roteia a busca para a API correta conforme a matéria."""
    if materia == "Direito":
        return buscar_direito(pergunta)
    if materia == "Língua Portuguesa":
        return buscar_portugues(pergunta)
    if materia == "Matemática":
        return buscar_matematica(pergunta)
    return buscar_geral(pergunta)


# ============================================================
# ESTADO DA SESSÃO (histórico)
# ============================================================
if "historico" not in st.session_state:
    st.session_state.historico = []

# ============================================================
# CONTROLES NA BARRA LATERAL
# ============================================================
with st.sidebar:
    st.header("⚙️ Configuração")
    banca = st.selectbox(
        "Banca",
        ["AOCP", "FCC", "VUNESP", "CESPE", "FGV", "IBFC", "IDECAN"]
    )
    materia = st.selectbox(
        "Matéria",
        ["Direito", "Língua Portuguesa", "Matemática", "Geral"]
    )

    st.divider()
    st.subheader("🔌 Status das APIs")
    st.write(f"{'✅' if DEEPSEEK_KEY else '❌'} DeepSeek")
    st.write(f"{'✅' if VECTORGOV_KEY and VECTORGOV_DISPONIVEL else '⚪'} VectorGov (Direito)")
    st.write(f"{'✅' if GEMINI_KEY and GEMINI_DISPONIVEL else '⚪'} Gemini (Geral)")

    st.divider()
    if st.button("🗑️ Limpar histórico", use_container_width=True):
        st.session_state.historico = []
        st.rerun()

# ============================================================
# BOTÃO PRINCIPAL
# ============================================================
col1, col2 = st.columns([1, 3])
with col1:
    gerar = st.button("🔍 Gerar Questão", type="primary", use_container_width=True)

# ============================================================
# FLUXO PRINCIPAL
# ============================================================
if gerar:
    with st.spinner("Criando enunciado com a DeepSeek..."):
        try:
            pergunta = gerar_pergunta(banca, materia)
        except Exception as e:
            st.error(f"Erro ao gerar a pergunta: {e}")
            st.stop()

    with st.spinner(f"Buscando resposta na fonte oficial ({materia})..."):
        try:
            resposta = buscar_resposta(materia, pergunta)
        except Exception as e:
            resposta = f"Erro na busca: {e}"

    # Guarda no histórico
    st.session_state.historico.insert(0, {
        "banca": banca,
        "materia": materia,
        "pergunta": pergunta,
        "resposta": resposta
    })

# ============================================================
# EXIBIÇÃO DO HISTÓRICO
# ============================================================
if not st.session_state.historico:
    st.info("Selecione a banca e a matéria, depois clique em **Gerar Questão**.")
else:
    st.subheader(f"📚 Histórico ({len(st.session_state.historico)} questão(ões))")
    for i, item in enumerate(st.session_state.historico, 1):
        with st.container(border=True):
            st.markdown(
                f"**#{i} — Banca:** `{item['banca']}`  |  "
                f"**Matéria:** `{item['materia']}`"
            )
            st.markdown("**❓ Pergunta gerada pela IA:**")
            st.markdown(f"> {item['pergunta']}")
            st.markdown("**✅ Resposta correta (fonte oficial):**")
            st.markdown(item["resposta"])

st.divider()
st.caption(
    "⚠️ A IA **não** gera a resposta. Ela vem da camada de busca em fontes "
    "oficiais (legislação, dicionário, cálculo ou web). Sempre confira o material original."
)
