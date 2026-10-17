import streamlit as st
import ollama
import re

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="Gerador de Questões Verificadas (Local)",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 Gerador de Questões Verificadas — 100% Local")
st.caption(
    "Fluxo: o modelo local **cria o enunciado** no estilo da banca escolhida "
    "e, em seguida, é consultado novamente com um prompt **específico da matéria** "
    "para fundamentar a **resposta correta**. Nenhum dado sai do seu computador."
)

# ============================================================
# PROMPTS
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

PROMPT_BUSCAR_DIREITO = """Você é um especialista em Direito e em legislação brasileira.
Responda à pergunta abaixo com base na legislação vigente (Constituição Federal, códigos, leis específicas, súmulas e jurisprudência consolidada).
Cite o artigo, inciso ou dispositivo legal que fundamenta sua resposta.
Seja objetivo e direto.

Pergunta: {pergunta}

Resposta fundamentada:"""

PROMPT_BUSCAR_PORTUGUES = """Você é um especialista em Língua Portuguesa.
Responda à pergunta abaixo com base na gramática normativa e nas regras oficiais da língua portuguesa.
Cite a regra gramatical aplicável (concordância, regência, pontuação, ortografia, sintaxe, etc.).
Seja objetivo e direto.

Pergunta: {pergunta}

Resposta fundamentada:"""

PROMPT_BUSCAR_MATEMATICA = """Você é um especialista em Matemática.
Resolva o problema abaixo mostrando os cálculos passo a passo e, ao final, apresente a RESPOSTA FINAL de forma clara e destacada.

Pergunta: {pergunta}

Resolução:"""

PROMPT_BUSCAR_GERAL = """Você é um especialista em conhecimentos gerais para concursos públicos.
Responda à pergunta abaixo de forma objetiva e direta, com base em fatos verificáveis e conhecimento consolidado.
Se necessário, indique a fonte (livro, autor, período histórico, conceito).
Seja claro e conciso.

Pergunta: {pergunta}

Resposta fundamentada:"""

# ============================================================
# FUNÇÕES DE COMUNICAÇÃO COM O OLLAMA
# ============================================================
def checar_ollama():
    """Verifica se o servidor Ollama está rodando e retorna a lista de modelos."""
    try:
        resposta = ollama.list()
        modelos = [m["name"] for m in resposta.get("models", [])]
        return True, modelos, None
    except Exception as e:
        return False, [], str(e)


def chamar_modelo(modelo, prompt, temperature=0.7):
    """Chama o modelo local via Ollama e retorna o texto gerado."""
    resposta = ollama.chat(
        model=modelo,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": temperature}
    )
    return resposta["message"]["content"].strip()


def gerar_pergunta(modelo, banca, materia):
    """Etapa 1: gera o enunciado no estilo da banca e matéria."""
    prompt = PROMPT_GERAR.format(banca=banca, materia=materia)
    pergunta = chamar_modelo(modelo, prompt, temperature=0.8)
    return re.sub(r'^["\']|["\']$', "", pergunta).strip()


def buscar_resposta(modelo, materia, pergunta):
    """Etapa 2: roteia para o prompt específico da matéria."""
    if materia == "Direito":
        prompt = PROMPT_BUSCAR_DIREITO.format(pergunta=pergunta)
        temp = 0.3
    elif materia == "Língua Portuguesa":
        prompt = PROMPT_BUSCAR_PORTUGUES.format(pergunta=pergunta)
        temp = 0.3
    elif materia == "Matemática":
        prompt = PROMPT_BUSCAR_MATEMATICA.format(pergunta=pergunta)
        temp = 0.2
    else:  # Geral
        prompt = PROMPT_BUSCAR_GERAL.format(pergunta=pergunta)
        temp = 0.4
    return chamar_modelo(modelo, prompt, temperature=temp)


# ============================================================
# VERIFICAÇÃO INICIAL DO OLLAMA
# ============================================================
ollama_ok, modelos_disponiveis, erro_ollama = checar_ollama()

if not ollama_ok:
    st.error("⚠️ **Ollama não está rodando.**")
    st.markdown(
        "1. Instale em [ollama.com/download](https://ollama.com/download).\n"
        "2. Abra um terminal e execute: `ollama serve`\n"
        "3. Recarregue esta página."
    )
    st.code(f"Detalhe técnico: {erro_ollama}", language="text")
    st.stop()

if not modelos_disponiveis:
    st.warning("⚠️ Nenhum modelo local encontrado.")
    st.markdown(
        "Abra um terminal e baixe um modelo:\n\n"
        "```bash\nollama pull llama3.1:8b\n```\n\n"
        "Depois recarregue esta página."
    )
    st.stop()

# ============================================================
# ESTADO DA SESSÃO
# ============================================================
if "historico" not in st.session_state:
    st.session_state.historico = []

# ============================================================
# BARRA LATERAL
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
    st.subheader("🧠 Modelo Local")

    # Sugere o primeiro modelo disponível como padrão
    modelo = st.selectbox(
        "Modelo Ollama",
        modelos_disponiveis,
        help="Modelos detectados automaticamente no seu Ollama local."
    )

    st.divider()
    st.subheader("📡 Status")
    st.success(f"✅ Ollama conectado ({len(modelos_disponiveis)} modelo(s))")

    st.divider()
    if st.button("🗑️ Limpar histórico", use_container_width=True):
        st.session_state.historico = []
        st.rerun()

# ============================================================
# BOTÃO PRINCIPAL
# ============================================================
col1, _ = st.columns([1, 3])
with col1:
    gerar = st.button("🔍 Gerar Questão", type="primary", use_container_width=True)

# ============================================================
# FLUXO PRINCIPAL
# ============================================================
if gerar:
    try:
        with st.spinner(f"Criando enunciado no estilo da banca {banca} ({materia})..."):
            pergunta = gerar_pergunta(modelo, banca, materia)

        with st.spinner(f"Buscando resposta fundamentada em {materia}..."):
            resposta = buscar_resposta(modelo, materia, pergunta)

        st.session_state.historico.insert(0, {
            "banca": banca,
            "materia": materia,
            "modelo": modelo,
            "pergunta": pergunta,
            "resposta": resposta
        })
    except Exception as e:
        st.error(f"Erro ao executar o modelo local: {e}")

# ============================================================
# HISTÓRICO
# ============================================================
if not st.session_state.historico:
    st.info("Selecione a banca e a matéria na barra lateral e clique em **Gerar Questão**.")
else:
    st.subheader(f"📚 Histórico ({len(st.session_state.historico)} questão(ões))")

    for i, item in enumerate(st.session_state.historico, 1):
        with st.container(border=True):
            st.markdown(
                f"**#{i} — Banca:** `{item['banca']}`  |  "
                f"**Matéria:** `{item['materia']}`  |  "
                f"**Modelo:** `{item['modelo']}`"
            )
            st.markdown("**❓ Pergunta gerada:**")
            st.markdown(f"> {item['pergunta']}")
            st.markdown("**✅ Resposta fundamentada:**")
            st.success(item["resposta"])

st.divider()
st.caption(
    "⚠️ A resposta é gerada pelo modelo de linguagem local com base na sua base de "
    "conhecimento. A precisão depende do tamanho e da qualidade do modelo escolhido. "
    "Sempre confira o material original."
)
