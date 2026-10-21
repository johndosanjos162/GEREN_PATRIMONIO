import streamlit as st
import json
import random
import time
from datetime import datetime, timedelta
import pandas as pd

st.set_page_config(
    page_title="Simulador PMSC 2026 – AOCP",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====================== CONFIGURAÇÃO DO EDITAL ======================
EDITAL = {
    "Legislação Institucional": 10,
    "Direito Constitucional": 8,
    "Língua Portuguesa": 8,
    "Direito Penal Comum": 6,
    "Direito Processual Penal Comum": 6,
    "Direito Penal Militar": 6,
    "Legislação Especial": 6,
    "Legislação de Trânsito": 5,
    "Informática": 5
}

TOTAL_QUESTOES = 60
TEMPO_PROVA_MINUTOS = 300  # 5 horas
NOTA_MINIMA = 30
# ====================================================================

def carregar_json(uploaded_file):
    try:
        data = json.load(uploaded_file)
        return data
    except Exception as e:
        st.error(f"Erro ao ler o JSON: {e}")
        return None

def gerar_prova_completa(banco: dict):
    """Gera uma prova com a distribuição exata do edital AOCP"""
    prova = []
    for materia, qtd in EDITAL.items():
        questoes = banco.get(materia, [])
        if len(questoes) < qtd:
            st.warning(f"Poucas questões em {materia}: {len(questoes)} disponíveis (necessário {qtd})")
            selecionadas = questoes.copy()
        else:
            selecionadas = random.sample(questoes, qtd)
        
        for q in selecionadas:
            q_copy = q.copy()
            q_copy["materia"] = materia
            prova.append(q_copy)
    
    random.shuffle(prova)
    return prova

def inicializar_estado():
    if "prova" not in st.session_state:
        st.session_state.prova = []
    if "respostas" not in st.session_state:
        st.session_state.respostas = {}
    if "indice" not in st.session_state:
        st.session_state.indice = 0
    if "inicio" not in st.session_state:
        st.session_state.inicio = None
    if "finalizada" not in st.session_state:
        st.session_state.finalizada = False
    if "modo" not in st.session_state:
        st.session_state.modo = "home"

def calcular_resultado(prova, respostas):
    acertos = 0
    por_materia = {m: {"acertos": 0, "total": 0} for m in EDITAL}
    
    for i, q in enumerate(prova):
        materia = q["materia"]
        por_materia[materia]["total"] += 1
        resp = respostas.get(i)
        if resp and resp == q["correta"]:
            acertos += 1
            por_materia[materia]["acertos"] += 1
    
    zerou = any(v["acertos"] == 0 and v["total"] > 0 for v in por_materia.values())
    aprovado = acertos >= NOTA_MINIMA and not zerou
    
    return {
        "acertos": acertos,
        "total": len(prova),
        "por_materia": por_materia,
        "zerou": zerou,
        "aprovado": aprovado
    }

# ====================== INTERFACE ======================
inicializar_estado()

st.title("🛡️ Simulador de Prova – PMSC 2026 (AOCP)")
st.caption("Edital nº 002/CCP/2026 – CFP | Banca Instituto AOCP | 60 questões + Redação")

# Sidebar
with st.sidebar:
    st.header("Configurações")
    uploaded = st.file_uploader("Carregar banco de questões (JSON)", type=["json"])
    
    if uploaded:
        banco = carregar_json(uploaded)
        if banco:
            st.success(f"Banco carregado com {sum(len(v) for v in banco.values())} questões")
            st.session_state.banco = banco
    
    st.divider()
    st.subheader("Modo de Prova")
    modo = st.radio(
        "Escolha o modo:",
        ["Prova Completa (60 questões – Edital)", "Treino por Matéria", "Revisão Livre"],
        key="modo_radio"
    )
    
    if st.button("Iniciar Simulado", type="primary", use_container_width=True):
        if "banco" not in st.session_state:
            st.error("Carregue o JSON primeiro!")
        else:
            if modo.startswith("Prova Completa"):
                st.session_state.prova = gerar_prova_completa(st.session_state.banco)
            else:
                # Treino: usa todas as questões disponíveis
                todas = []
                for mat, qs in st.session_state.banco.items():
                    for q in qs:
                        q2 = q.copy()
                        q2["materia"] = mat
                        todas.append(q2)
                st.session_state.prova = todas
            
            st.session_state.respostas = {}
            st.session_state.indice = 0
            st.session_state.inicio = datetime.now()
            st.session_state.finalizada = False
            st.session_state.modo = "prova"
            st.rerun()

    if st.session_state.modo == "prova" and st.session_state.inicio:
        elapsed = datetime.now() - st.session_state.inicio
        remaining = timedelta(minutes=TEMPO_PROVA_MINUTOS) - elapsed
        if remaining.total_seconds() <= 0:
            st.session_state.finalizada = True
            st.error("⏰ Tempo esgotado!")
        else:
            mins = int(remaining.total_seconds() // 60)
            secs = int(remaining.total_seconds() % 60)
            st.metric("Tempo restante", f"{mins:02d}:{secs:02d}")

# ====================== TELA PRINCIPAL ======================
if st.session_state.modo == "home":
    st.info("""
    ### Como usar
    1. Faça upload do arquivo JSON com as questões (formato já usado anteriormente).
    2. Escolha o modo de prova.
    3. Clique em **Iniciar Simulado**.
    
    **Regras do Edital AOCP (PMSC 2026):**
    - 60 questões objetivas
    - Nota mínima: 30 pontos (50%)
    - Não pode zerar nenhuma disciplina
    - Tempo total: 5 horas (prova objetiva + redação)
    """)
    
    st.markdown("### Distribuição oficial das questões")
    df = pd.DataFrame(list(EDITAL.items()), columns=["Disciplina", "Questões"])
    st.dataframe(df, use_container_width=True, hide_index=True)

elif st.session_state.modo == "prova" and not st.session_state.finalizada:
    prova = st.session_state.prova
    if not prova:
        st.warning("Nenhuma questão carregada.")
        st.stop()
    
    idx = st.session_state.indice
    q = prova[idx]
    
    # Cabeçalho da questão
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.subheader(f"Questão {idx + 1} de {len(prova)}")
    with col2:
        st.caption(f"**{q['materia']}**")
    with col3:
        if idx in st.session_state.respostas:
            st.success("Respondida")
        else:
            st.warning("Em branco")
    
    st.markdown("---")
    st.markdown(f"**{q['pergunta']}**")
    st.write("")
    
    # Alternativas
    opcoes = q["alternativas"]
    letras = [alt[0] for alt in opcoes]  # A, B, C, D, E
    
    resposta_atual = st.session_state.respostas.get(idx)
    
    escolha = st.radio(
        "Escolha a alternativa:",
        options=letras,
        format_func=lambda x: next(a for a in opcoes if a.startswith(x)),
        index=letras.index(resposta_atual) if resposta_atual in letras else None,
        key=f"radio_{idx}"
    )
    
    if escolha:
        st.session_state.respostas[idx] = escolha
    
    st.markdown("---")
    
    # Navegação
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        if st.button("⏮ Anterior", disabled=idx == 0, use_container_width=True):
            st.session_state.indice = max(0, idx - 1)
            st.rerun()
    with c2:
        if st.button("Próxima ⏭", disabled=idx == len(prova) - 1, use_container_width=True):
            st.session_state.indice = min(len(prova) - 1, idx + 1)
            st.rerun()
    with c3:
        if st.button("📋 Revisar", use_container_width=True):
            st.session_state.modo = "revisao"
            st.rerun()
    with c4:
        if st.button("✅ Finalizar Prova", type="primary", use_container_width=True):
            st.session_state.finalizada = True
            st.session_state.modo = "resultado"
            st.rerun()
    with c5:
        st.write("")  # espaçador

elif st.session_state.modo == "revisao":
    st.subheader("Revisão de Respostas")
    prova = st.session_state.prova
    for i, q in enumerate(prova):
        resp = st.session_state.respostas.get(i, "—")
        cor = "🟢" if resp != "—" else "⚪"
        if st.button(f"{cor} Q{i+1} | {q['materia'][:20]}... | Resp: {resp}", key=f"rev_{i}"):
            st.session_state.indice = i
            st.session_state.modo = "prova"
            st.rerun()
    
    if st.button("Voltar para a prova"):
        st.session_state.modo = "prova"
        st.rerun()

elif st.session_state.modo == "resultado" or st.session_state.finalizada:
    st.header("📊 Resultado do Simulado")
    resultado = calcular_resultado(st.session_state.prova, st.session_state.respostas)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Acertos", f"{resultado['acertos']} / {resultado['total']}")
    col2.metric("Aproveitamento", f"{resultado['acertos']/resultado['total']*100:.1f}%")
    col3.metric("Situação", "✅ APROVADO" if resultado["aprovado"] else "❌ REPROVADO")
    
    if resultado["zerou"]:
        st.error("Você zerou pelo menos uma disciplina → eliminado conforme edital.")
    
    st.subheader("Desempenho por Disciplina")
    dados = []
    for mat, v in resultado["por_materia"].items():
        dados.append({
            "Disciplina": mat,
            "Acertos": v["acertos"],
            "Total": v["total"],
            "%": round(v["acertos"]/v["total"]*100, 1) if v["total"] > 0 else 0
        })
    st.dataframe(pd.DataFrame(dados), use_container_width=True, hide_index=True)
    
    with st.expander("Ver gabarito completo"):
        for i, q in enumerate(st.session_state.prova):
            resp = st.session_state.respostas.get(i, "—")
            correta = q["correta"]
            status = "✅" if resp == correta else "❌"
            st.markdown(f"**Q{i+1}** {status} | Sua: **{resp}** | Gabarito: **{correta}** | {q['materia']}")
            st.caption(q["pergunta"][:120] + "...")
            st.divider()
    
    if st.button("Fazer novo simulado"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
