import json
import random
import glob
import os
import urllib.parse
import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="PMSC 2026 Arena VR - AOCP",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicialização do Session State
if "history" not in st.session_state:
    st.session_state["history"] = []
if "simulado_ativo" not in st.session_state:
    st.session_state["simulado_ativo"] = False
if "questoes_treino" not in st.session_state:
    st.session_state["questoes_treino"] = []
if "questoes_simulado" not in st.session_state:
    st.session_state["questoes_simulado"] = []
if "vr_loaded" not in st.session_state:
    st.session_state["vr_loaded"] = False
if "modo_atual" not in st.session_state:
    st.session_state["modo_atual"] = "Arena Livre"

# Distribuição oficial AOCP para o Simulado de 60 questões (Edital PMSC)
DISTRIBUICAO_OFICIAL = {
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

@st.cache_data(ttl=30)
def carregar_banco_questoes():
    """Procura automaticamente por arquivos .json na raiz e carrega as questões."""
    arquivos_json = glob.glob("*.json")
    if not arquivos_json:
        return None
    
    banco_geral = {}
    vistas = set()
    
    for arq in arquivos_json:
        try:
            with open(arq, "r", encoding="utf-8") as f:
                conteudo = f.read().strip()
                if not conteudo:
                    continue
                decoder = json.JSONDecoder()
                pos = 0
                while pos < len(conteudo):
                    while pos < len(conteudo) and conteudo[pos].isspace():
                        pos += 1
                    if pos >= len(conteudo):
                        break
                    obj, idx = decoder.raw_decode(conteudo, pos)
                    pos = idx
                    
                    if isinstance(obj, dict):
                        for mat, questoes in obj.items():
                            if mat not in banco_geral:
                                banco_geral[mat] = []
                            for q in questoes:
                                p_texto = q.get("pergunta", "").strip().lower()
                                if p_texto and p_texto not in vistas:
                                    vistas.add(p_texto)
                                    banco_geral[mat].append(q)
                    elif isinstance(obj, list):
                        for q in obj:
                            mat = q.get("materia", "Geral")
                            if mat not in banco_geral:
                                banco_geral[mat] = []
                            p_texto = q.get("pergunta", "").strip().lower()
                            if p_texto and p_texto not in vistas:
                                vistas.add(p_texto)
                                banco_geral[mat].append(q)
        except Exception as e:
            continue
            
    return banco_geral

banco_dados = carregar_banco_questoes()

if not banco_dados:
    st.error("❌ ERRO CRÍTICO: Nenhum arquivo `json.json` válido encontrado na raiz do aplicativo.")
    st.stop()

total_questoes_unicas = sum(len(q_list) for q_list in banco_dados.values())

# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("🛡️ PMSC 2026 VR")
    st.caption("Banca Instituto AOCP • Meta Quest 3/3S")
    
    st.metric("Total de Questões Únicas", total_questoes_unicas)
    
    if st.button("🔄 Recarregar Banco JSON"):
        carregar_banco_questoes.clear()
        st.session_state["vr_loaded"] = False
        st.rerun()
        
    st.divider()
    st.subheader("⚙️ Configurar Treino")
    materias_disponiveis = list(banco_dados.keys())
    materia_selecionada = st.selectbox("Matéria", materias_disponiveis if materias_disponiveis else ["Geral"])
    qtd_treino = st.slider("Quantidade de Questões", 5, 25, 10)
    
    if st.button("🚀 Iniciar Treino VR", type="primary"):
        pool = banco_dados.get(materia_selecionada, [])
        selected = random.sample(pool, min(qtd_treino, len(pool))) if pool else []
        for q in selected:
            q["materia_origem"] = materia_selecionada
        st.session_state["questoes_treino"] = selected
        st.session_state["simulado_ativo"] = False
        st.session_state["modo_atual"] = f"Treino: {materia_selecionada}"
        st.session_state["vr_loaded"] = False
        st.success(f"Treino gerado com {len(selected)} questões!")
        st.rerun()
        
    st.divider()
    st.subheader("🎯 Simulado Oficial (60q)")
    if not st.session_state["simulado_ativo"]:
        if st.button("📝 Iniciar Simulado 60q (AOCP)", type="primary"):
            sim_questoes = []
            for mat, qtd in DISTRIBUICAO_OFICIAL.items():
                pool = banco_dados.get(mat, [])
                if pool:
                    escolhidas = random.sample(pool, min(qtd, len(pool)))
                    for q in escolhidas:
                        q_copy = q.copy()
                        q_copy["materia_origem"] = mat
                        sim_questoes.append(q_copy)
                else:
                    all_pool = [item for sublist in banco_dados.values() for item in sublist]
                    if all_pool:
                        escolhidas = random.sample(all_pool, min(qtd, len(all_pool)))
                        for q in escolhidas:
                            q_copy = q.copy()
                            q_copy["materia_origem"] = mat
                            sim_questoes.append(q_copy)
            random.shuffle(sim_questoes)
            st.session_state["questoes_simulado"] = sim_questoes
            st.session_state["simulado_ativo"] = True
            st.session_state["modo_atual"] = "Simulado Oficial 60q"
            st.session_state["vr_loaded"] = False
            st.rerun()
    else:
        if st.button("❌ Cancelar Simulado Ativo"):
            st.session_state["simulado_ativo"] = False
            st.session_state["modo_atual"] = "Arena Livre"
            st.rerun()
            
    if st.session_state["history"]:
        st.divider()
        st.subheader("📊 Histórico de Simulados")
        for h in st.session_state["history"][-5:]:
            status = "🟢 Aprovado" if h["aprovado"] else "🔴 Reprovado"
            st.markdown(f"**{h['data']}** | Nota: {h['nota']:.1f}% | {status}")

# ==================== ABAS PRINCIPAIS ====================
aba_livre, aba_simulado, aba_treino = st.tabs(["🥽 Arena Livre VR", "📝 Simulado Clássico", "📚 Treino & Lista"])

if st.session_state["simulado_ativo"]:
    questoes_ativas = st.session_state["questoes_simulado"]
elif st.session_state["questoes_treino"]:
    questoes_ativas = st.session_state["questoes_treino"]
else:
    all_q = []
    for mat, q_list in banco_dados.items():
        for q in q_list:
            q_copy = q.copy()
            q_copy["materia_origem"] = mat
            all_q.append(q_copy)
    random.shuffle(all_q)
    questoes_ativas = all_q[:20]

with aba_simulado:
    st.header("Simulado Oficial PMSC - Instituto AOCP (60 Questões)")
    if not st.session_state["simulado_ativo"]:
        st.info("Clique em **'Iniciar Simulado 60q (AOCP)'** na barra lateral para iniciar a prova oficial.")
    else:
        st.success(f"Simulado ativo com {len(questoes_ativas)} questões.")
        with st.form("form_simulado_oficial"):
            respostas_usuario = {}
            for idx, q in enumerate(questoes_ativas):
                st.markdown(f"**Q.{idx+1} [{q.get('materia_origem', 'Geral')}]**: {q['pergunta']}")
                resp = st.radio(f"Alternativas Q.{idx+1}", q["alternativas"], key=f"quest_sim_{idx}", index=None)
                respostas_usuario[idx] = resp
                st.divider()
            
            enviar_simulado = st.form_submit_button("Finalizar e Corrigir Simulado")
            if enviar_simulado:
                acertos = 0
                total = len(questoes_ativas)
                for idx, q in enumerate(questoes_ativas):
                    escolha = respostas_usuario.get(idx)
                    if escolha and escolha[0].upper() == q["correta"].upper():
                        acertos += 1
                nota = (acertos / total) * 100 if total > 0 else 0
                aprovado = nota >= 50.0
                
                registro = {
                    "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "acertos": acertos,
                    "total": total,
                    "nota": nota,
                    "aprovado": aprovado
                }
                st.session_state["history"].append(registro)
                st.session_state["simulado_ativo"] = False
                st.success(f"Prova finalizada! Você acertou {acertos}/{total} ({nota:.1f}%).")
                st.rerun()

with aba_treino:
    st.header("Banco de Questões e Treino em Lista")
    mat_escolha = st.selectbox("Filtrar Matéria para Lista", list(banco_dados.keys()))
    for i, q in enumerate(banco_dados.get(mat_escolha, [])):
        with st.expander(f"Q.{i+1}: {q['pergunta'][:80]}..."):
            st.write(f"**Pergunta:** {q['pergunta']}")
            for alt in q["alternativas"]:
                st.write(alt)
            st.markdown(f"**Correta:** `{q['correta']}`")

with aba_livre:
    st.header(f"Arena de Estudos VR — Modo: {st.session_state['modo_atual']}")
    st.markdown("Ambiente imersivo completo para **Meta Quest 3 / 3S**. Calibração automática de altura e mãos ativada. Pegue painéis e blocos com o Grip ou Pinch e selecione alternativas com o Trigger.")
    
    num_blocos = len(questoes_ativas)
    
    if not st.session_state["vr_loaded"]:
        if st.button(f"⚡ CARREGAR VR — MODO ({num_blocos} blocos)", type="primary"):
            st.session_state["vr_loaded"] = True
            st.rerun()
    else:
        if st.button("🔄 Ocultar / Recarregar Ambiente VR"):
            st.session_state["vr_loaded"] = False
            st.rerun()
            
        q_json_str = json.dumps(questoes_ativas, ensure_ascii=False)
        
        html_template = r"""
        <!DOCTYPE html>
        <html>
          <head>
            <meta charset="utf-8">
            <title>PMSC 2026 Arena VR</title>
            <script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
            <script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v7.4.0/dist/aframe-extras.min.js"></script>
            <script src="https://unpkg.com/super-hands@3.0.5/dist/super-hands.min.js"></script>
            <style>
              html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; background: #000; font-family: sans-serif; }
              a-scene { width: 100%; height: 100%; }
              #vr-overlay-ui {
                position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%);
                z-index: 1000; display: flex; gap: 15px;
              }
              .vr-btn {
                background: #00d1ff; color: #000; border: none; padding: 14px 28px;
                font-size: 18px; font-weight: bold; border-radius: 8px; cursor: pointer;
                box-shadow: 0 4px 15px rgba(0,209,255,0.5); transition: 0.2s;
              }
              .vr-btn:hover { background: #00ff88; }
              #hud-overlay {
                position: absolute; top: 15px; left: 50%; transform: translateX(-50%);
                background: rgba(0, 20, 40, 0.9); color: #00d1ff; padding: 12px 24px;
                border-radius: 10px; font-size: 16px; font-weight: bold; z-index: 999;
                border: 2px solid #00d1ff; pointer-events: none; text-align: center;
                box-shadow: 0 0 15px rgba(0,209,255,0.4);
              }
            </style>
          </head>
          <body>
            <div id="hud-overlay">🎯 PMSC Arena VR | Calibrado e Pronto | Use Grip/Pinch para mover painéis e blocos</div>
            
            <div id="vr-overlay-ui">
              <button class="vr-btn" onclick="entrarModoVR()">🥽 ENTRAR EM REALIDADE VIRTUAL (QUEST 3)</button>
            </div>

            <a-scene embedded vr-mode-ui="enabled: true"
                     webxr="optionalFeatures: hand-tracking, local-floor, bounded-floor, hit-test, passthrough, plane-detection"
                     renderer="colorManagement: true; alpha: false;">
              
              <a-assets>
                <img id="beach360" src="https://cdn.aframe.io/360-image-gallery-boilerplate/img/sechelt.jpg">
                <img id="office360" src="https://cdn.aframe.io/360-image-gallery-boilerplate/img/city.jpg">
                <img id="library360" src="https://cdn.aframe.io/360-image-gallery-boilerplate/img/cubes.jpg">
                <img id="space360" src="https://cdn.aframe.io/360-image-gallery-boilerplate/img/bg.jpg">
              </a-assets>

              <a-sky id="main-sky" color="#050a14"></a-sky>

              <!-- Rig com Calibração Automática de Chão e Altura (local-floor) -->
              <a-entity id="rig" movement-controls="fly: false; speed: 0.2">
                <a-entity id="camera" camera look-controls position="0 1.6 0" universal-controls>
                  <a-cursor fuse="false" raycaster="objects: .clickable, .grabbable, .ui-btn"></a-cursor>
                </a-entity>
                
                <!-- Mão Esquerda (Controle + Hand Tracking + Super-Hands) -->
                <a-entity id="left-hand"
                          hand-controls="hand: left; handModelStyle: lowPoly"
                          hand-tracking-controls="hand: left"
                          laser-controls="hand: left"
                          raycaster="objects: .clickable, .grabbable, .ui-btn; far: 25"
                          super-hands="colliderEvent: raycaster-intersection; colliderEventProperty: els; colliderEndEvent: raycaster-intersection-cleared; colliderEndEventProperty: clearedEls; grabStartButtons: gripdown, pinchstart, triggerdown; grabEndButtons: gripup, pinchend, triggerup">
                </a-entity>
                
                <!-- Mão Direita (Controle + Hand Tracking + Super-Hands) -->
                <a-entity id="right-hand"
                          hand-controls="hand: right; handModelStyle: lowPoly"
                          hand-tracking-controls="hand: right"
                          laser-controls="hand: right"
                          raycaster="objects: .clickable, .grabbable, .ui-btn; far: 25"
                          super-hands="colliderEvent: raycaster-intersection; colliderEventProperty: els; colliderEndEvent: raycaster-intersection-cleared; colliderEndEventProperty: clearedEls; grabStartButtons: gripdown, pinchstart, triggerdown; grabEndButtons: gripup, pinchend, triggerup">
                </a-entity>
              </a-entity>

              <a-light type="ambient" color="#ffffff" intensity="0.9"></a-light>
              <a-light type="directional" position="2 4 2" intensity="0.6"></a-light>

              <!-- PAINEL DE CONTROLE PRINCIPAL (MOVÍVEL E INTERATIVO) -->
              <a-entity id="control-panel" class="grabbable" position="0 2 -2.2" hoverable grabbable stretchable draggable droppable>
                <a-plane width="2.4" height="1.4" color="#0b132b" opacity="0.95" material="shader: flat">
                  <a-text value="PMSC 2026 - PAINEL DE CONTROLE VR" position="0 0.55 0.01" align="center" color="#00d1ff" width="2.2" scale="0.7 0.7 0.7"></a-text>
                  
                  <a-text value="Ambientes & MR:" position="-1.05 0.28 0.01" align="left" color="#ffffff" width="2" scale="0.5 0.5 0.5"></a-text>
                  <a-plane class="ui-btn clickable" data-action="env-passthrough" width="0.7" height="0.18" position="-0.7 0.12 0.02" color="#00aa55"><a-text value="Passthrough" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="ui-btn clickable" data-action="env-dark" width="0.5" height="0.18" position="0.0 0.12 0.02" color="#111"><a-text value="Escuro" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="ui-btn clickable" data-action="env-beach" width="0.5" height="0.18" position="0.55 0.12 0.02" color="#0066cc"><a-text value="Praia" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="ui-btn clickable" data-action="env-office" width="0.5" height="0.18" position="-0.7 -0.08 0.02" color="#444"><a-text value="Escritorio" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="ui-btn clickable" data-action="env-library" width="0.5" height="0.18" position="-0.15 -0.08 0.02" color="#663300"><a-text value="Biblioteca" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="ui-btn clickable" data-action="env-space" width="0.5" height="0.18" position="0.4 -0.08 0.02" color="#220033"><a-text value="Espaço" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>

                  <a-text value="Organização & Layout:" position="-1.05 -0.26 0.01" align="left" color="#ffffff" width="2" scale="0.5 0.5 0.5"></a-text>
                  <a-plane class="ui-btn clickable" data-action="layout-grid" width="0.5" height="0.18" position="-0.7 -0.42 0.02" color="#2b2d42"><a-text value="GRADE" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="ui-btn clickable" data-action="layout-materia" width="0.5" height="0.18" position="-0.15 -0.42 0.02" color="#2b2d42"><a-text value="MATERIA" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="ui-btn clickable" data-action="layout-esparso" width="0.5" height="0.18" position="0.4 -0.42 0.02" color="#2b2d42"><a-text value="ESPALHAR" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="ui-btn clickable" data-action="save-layout" width="0.32" height="0.15" position="-0.8 -0.62 0.02" color="#006633"><a-text value="Salvar" align="center" width="1.2" color="#fff" scale="0.4 0.4 0.4"></a-text></a-plane>
                  <a-plane class="ui-btn clickable" data-action="load-layout" width="0.32" height="0.15" position="-0.4 -0.62 0.02" color="#663300"><a-text value="Carregar" align="center" width="1.2" color="#fff" scale="0.4 0.4 0.4"></a-text></a-plane>
                  <a-plane class="ui-btn clickable" data-action="reset-layout" width="0.32" height="0.15" position="0.0 -0.62 0.02" color="#aa2222"><a-text value="Reset" align="center" width="1.2" color="#fff" scale="0.4 0.4 0.4"></a-text></a-plane>
                </a-plane>
              </a-entity>

              <!-- PAINEL CALIBRADOR DE MÃOS E ALTURA (MOVÍVEL E INTERATIVO) -->
              <a-entity id="calibrator-panel" class="grabbable" position="1.8 1.8 -1.8" rotation="0 -25 0" hoverable grabbable stretchable draggable droppable>
                <a-plane width="1.3" height="1.4" color="#111122" opacity="0.95" material="shader: flat">
                  <a-text value="CALIBRADOR VR" position="0 0.56 0.01" align="center" color="#ffaa00" width="1.8" scale="0.6 0.6 0.6"></a-text>
                  <a-text id="leftHandData" value="Mão Esq: Tracking OK" position="-0.55 0.3 0.01" align="left" color="#00d1ff" width="1.5" scale="0.4 0.4 0.4"></a-text>
                  <a-text id="rightHandData" value="Mão Dir: Tracking OK" position="-0.55 0.1 0.01" align="left" color="#00d1ff" width="1.5" scale="0.4 0.4 0.4"></a-text>
                  
                  <a-plane class="ui-btn clickable" data-action="height-up" width="0.5" height="0.16" position="-0.3 -0.12 0.02" color="#333"><a-text value="ALTURA +" align="center" width="1.2" color="#fff" scale="0.4 0.4 0.4"></a-text></a-plane>
                  <a-plane class="ui-btn clickable" data-action="height-down" width="0.5" height="0.16" position="0.3 -0.12 0.02" color="#333"><a-text value="ALTURA -" align="center" width="1.2" color="#fff" scale="0.4 0.4 0.4"></a-text></a-plane>
                  <a-plane class="ui-btn clickable" data-action="reset-cam" width="1.1" height="0.16" position="0 -0.32 0.02" color="#aa2222"><a-text value="RESET CÂMERA" align="center" width="1.5" color="#fff" scale="0.4 0.4 0.4"></a-text></a-plane>
                  <a-plane class="ui-btn clickable" data-action="exit-vr" width="1.1" height="0.16" position="0 -0.52 0.02" color="#444444"><a-text value="SAIR VR" align="center" width="1.5" color="#fff" scale="0.4 0.4 0.4"></a-text></a-plane>
                </a-plane>
              </a-entity>

              <!-- CONTAINER DOS BLOCOS DE QUESTÕES -->
              <a-entity id="questoes-container"></a-entity>
            </a-scene>

            <script>
              const questoesData = __Q_JSON__;

              function entrarModoVR() {
                const sceneEl = document.querySelector('a-scene');
                if (sceneEl) {
                  sceneEl.enterVR();
                }
              }

              // CONSTRUÇÃO E REORGANIZAÇÃO DOS BLOCOS 3D COM SUPER-HANDS
              function construirBlocos(modoLayout = 'grid') {
                const container = document.getElementById('questoes-container');
                if (!container) return;
                container.innerHTML = "";
                
                questoesData.forEach((q, index) => {
                  let x = 0, y = 0, z = 0;
                  
                  if (modoLayout === 'grid') {
                    const col = index % 4;
                    const row = Math.floor(index / 4);
                    x = (col - 1.5) * 1.8;
                    y = 2.2 - (row * 1.35);
                    z = -3.2 - (Math.floor(index / 16) * 1.8);
                  } else if (modoLayout === 'esparso') {
                    const angulo = (index / questoesData.length) * Math.PI * 2;
                    const raio = 3.5;
                    x = Math.cos(angulo) * raio;
                    y = 1.6 + (Math.random() * 1.2 - 0.6);
                    z = Math.sin(angulo) * raio;
                  } else if (modoLayout === 'materia') {
                    const materiasUnicas = [...new Set(questoesData.map(item => item.materia_origem || 'Geral'))];
                    const matIndex = materiasUnicas.indexOf(q.materia_origem || 'Geral');
                    x = (matIndex - (materiasUnicas.length / 2)) * 2.2;
                    y = 2.0 - ((index % 4) * 1.3);
                    z = -3.0 - (Math.floor(index / 4) * 0.8);
                  }

                  const block = document.createElement('a-entity');
                  block.setAttribute('id', 'block-' + index);
                  block.setAttribute('class', 'grabbable');
                  block.setAttribute('position', `${x} ${y} ${z}`);
                  block.setAttribute('geometry', 'primitive: box; width: 1.6; height: 1.15; depth: 0.08');
                  block.setAttribute('material', 'color: #16213e; shader: flat');
                  block.setAttribute('hoverable', '');
                  block.setAttribute('grabbable', '');
                  block.setAttribute('stretchable', '');
                  block.setAttribute('draggable', '');
                  block.setAttribute('droppable', '');
                  block.setAttribute('data-materia', q.materia_origem || 'Geral');

                  block.addEventListener('grab-end', () => {
                    salvarLayoutAutomatico();
                  });

                  const titulo = document.createElement('a-text');
                  titulo.setAttribute('value', `Q.${index+1} [${q.materia_origem || 'Geral'}]`);
                  titulo.setAttribute('position', '-0.74 0.48 0.05');
                  titulo.setAttribute('scale', '0.45 0.45 0.45');
                  titulo.setAttribute('color', '#00d1ff');
                  block.appendChild(titulo);

                  const pergunta = document.createElement('a-text');
                  let pText = q.pergunta.length > 85 ? q.pergunta.substring(0, 82) + '...' : q.pergunta;
                  pergunta.setAttribute('value', pText);
                  pergunta.setAttribute('position', '-0.74 0.28 0.05');
                  pergunta.setAttribute('width', '1.48');
                  pergunta.setAttribute('scale', '0.32 0.32 0.32');
                  pergunta.setAttribute('color', '#ffffff');
                  block.appendChild(pergunta);

                  q.alternativas.forEach((alt, aIdx) => {
                    const letra = alt[0].toUpperCase();
                    const altY = 0.04 - (aIdx * 0.2);

                    const altPlane = document.createElement('a-plane');
                    altPlane.setAttribute('class', 'clickable ui-btn');
                    altPlane.setAttribute('position', `0 ${altY} 0.05`);
                    altPlane.setAttribute('width', '1.45');
                    altPlane.setAttribute('height', '0.17');
                    altPlane.setAttribute('color', '#1f4068');
                    altPlane.setAttribute('data-letra', letra);
                    altPlane.setAttribute('data-correta', q.correta.toUpperCase());

                    altPlane.addEventListener('click', function () {
                      const correta = this.getAttribute('data-correta');
                      if (letra === correta) {
                        this.setAttribute('color', '#00aa55');
                        document.getElementById('hud-overlay').innerText = "✅ Resposta Correta!";
                        if (navigator.vibrate) navigator.vibrate(200);
                      } else {
                        this.setAttribute('color', '#aa2222');
                        document.getElementById('hud-overlay').innerText = `❌ Incorreto! Correta: ${correta}`;
                        if (navigator.vibrate) navigator.vibrate([100, 50, 100]);
                      }
                    });

                    const altText = document.createElement('a-text');
                    altText.setAttribute('value', alt);
                    altText.setAttribute('position', '-0.68 0 0.01');
                    altText.setAttribute('width', '1.38');
                    altText.setAttribute('scale', '0.32 0.32 0.32');
                    altText.setAttribute('color', '#ffffff');

                    altPlane.appendChild(altText);
                    block.appendChild(altPlane);
                  });

                  container.appendChild(block);
                });
              }

              // GERENCIAMENTO GLOBAL DE CLIQUES NOS BOTÕES 3D (PAINÉIS)
              document.addEventListener('click', (e) => {
                const target = e.target.closest('.ui-btn');
                if (!target) return;
                
                const action = target.getAttribute('data-action');
                if (!action) return;

                const sky = document.getElementById('main-sky');
                const sceneEl = document.querySelector('a-scene');

                if (action === 'env-passthrough') {
                  if (navigator.xr) {
                    navigator.xr.requestSession('immersive-ar', {
                      requiredFeatures: ['local-floor'],
                      optionalFeatures: ['passthrough', 'hand-tracking', 'hit-test', 'bounded-floor']
                    }).then((session) => {
                      sceneEl.renderer.xr.setSession(session);
                      sky.setAttribute('color', 'transparent');
                      sky.removeAttribute('src');
                    }).catch(err => alert("Passthrough ativo ou indisponível."));
                  }
                } else if (action === 'env-dark') {
                  sky.setAttribute('color', '#050a14');
                  sky.removeAttribute('src');
                } else if (action === 'env-beach') {
                  sky.setAttribute('src', '#beach360');
                  sky.removeAttribute('color');
                } else if (action === 'env-office') {
                  sky.setAttribute('src', '#office360');
                  sky.removeAttribute('color');
                } else if (action === 'env-library') {
                  sky.setAttribute('src', '#library360');
                  sky.removeAttribute('color');
                } else if (action === 'env-space') {
                  sky.setAttribute('src', '#space360');
                  sky.removeAttribute('color');
                } else if (action === 'layout-grid') {
                  construirBlocos('grid');
                } else if (action === 'layout-materia') {
                  construirBlocos('materia');
                } else if (action === 'layout-esparso') {
                  construirBlocos('esparso');
                } else if (action === 'save-layout') {
                  salvarLayout();
                } else if (action === 'load-layout') {
                  carregarLayout();
                } else if (action === 'reset-layout') {
                  localStorage.removeItem('pmsc_vr_layout');
                  construirBlocos('grid');
                  document.getElementById('hud-overlay').innerText = "🔄 Arena reiniciada!";
                } else if (action === 'height-up') {
                  const cam = document.getElementById('camera');
                  const pos = cam.getAttribute('position');
                  cam.setAttribute('position', `${pos.x} ${Math.min(2.5, pos.y + 0.1)} ${pos.z}`);
                } else if (action === 'height-down') {
                  const cam = document.getElementById('camera');
                  const pos = cam.getAttribute('position');
                  cam.setAttribute('position', `${pos.x} ${Math.max(0.5, pos.y - 0.1)} ${pos.z}`);
                } else if (action === 'reset-cam') {
                  document.getElementById('rig').setAttribute('position', '0 0 0');
                  document.getElementById('camera').setAttribute('position', '0 1.6 0');
                } else if (action === 'exit-vr') {
                  if (sceneEl && sceneEl.exitVR) sceneEl.exitVR();
                }
              });

              function salvarLayout() {
                const layout = {};
                questoesData.forEach((_, index) => {
                  const b = document.getElementById('block-' + index);
                  if (b) {
                    layout[index] = {
                      pos: b.getAttribute('position'),
                      rot: b.getAttribute('rotation')
                    };
                  }
                });
                localStorage.setItem('pmsc_vr_layout', JSON.stringify(layout));
                document.getElementById('hud-overlay').innerText = "💾 Layout salvo com sucesso!";
              }

              function salvarLayoutAutomatico() {
                const layout = {};
                questoesData.forEach((_, index) => {
                  const b = document.getElementById('block-' + index);
                  if (b) {
                    layout[index] = {
                      pos: b.getAttribute('position'),
                      rot: b.getAttribute('rotation')
                    };
                  }
                });
                localStorage.setItem('pmsc_vr_layout', JSON.stringify(layout));
              }

              function carregarLayout() {
                const saved = localStorage.getItem('pmsc_vr_layout');
                if (saved) {
                  const layout = JSON.parse(saved);
                  for (let idx in layout) {
                    const b = document.getElementById('block-' + idx);
                    if (b) {
                      b.setAttribute('position', layout[idx].pos);
                      b.setAttribute('rotation', layout[idx].rot);
                    }
                  }
                  document.getElementById('hud-overlay').innerText = "📂 Layout restaurado!";
                } else {
                  document.getElementById('hud-overlay').innerText = "⚠️ Nenhum layout salvo encontrado.";
                }
              }

              // MONITORAMENTO DE POSIÇÃO E CALIBRAÇÃO AUTOMÁTICA DAS MÃOS
              setInterval(() => {
                const leftHand = document.getElementById('left-hand');
                const rightHand = document.getElementById('right-hand');
                if (leftHand && leftHand.object3D) {
                  const p = leftHand.object3D.position;
                  const el = document.getElementById('leftHandData');
                  if (el) el.setAttribute('value', `Esq: X=${p.x.toFixed(1)} Y=${p.y.toFixed(1)} Z=${p.z.toFixed(1)}`);
                }
                if (rightHand && rightHand.object3D) {
                  const p = rightHand.object3D.position;
                  const el = document.getElementById('rightHandData');
                  if (el) el.setAttribute('value', `Dir: X=${p.x.toFixed(1)} Y=${p.y.toFixed(1)} Z=${p.z.toFixed(1)}`);
                }
              }, 500);

              // INICIALIZAÇÃO DA CENA VR
              if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => construirBlocos('grid'));
              } else {
                construirBlocos('grid');
              }

              window.addEventListener('load', () => {
                const saved = localStorage.getItem('pmsc_vr_layout');
                if (saved) carregarLayout();
              });
            </script>
          </body>
        </html>
        """

        html_vr = html_template.replace("__Q_JSON__", q_json_str)
        
        encoded_html = urllib.parse.quote(html_vr)
        st.iframe(f"data:text/html;charset=utf-8,{encoded_html}", height=750)

# ==================== RODAPÉ ====================
st.markdown("---")
st.caption("🛡️ PMSC 2026 Arena VR • Desenvolvido para o Meta Quest 3 e 3S • Instituto AOCP")
