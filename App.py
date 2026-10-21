import json
import random
import glob
import os
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
    st.error("❌ ERRO CRÍTICO: Nenhum arquivo `json.json` válido encontrado na raiz do aplicativo. Certifique-se de enviar o arquivo JSON com as questões.")
    st.stop()

total_questoes_unicas = sum(len(q_list) for q_list in banco_dados.values())

# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("🛡️ PMSC 2026 VR")
    st.caption("Banca Instituto AOCP • Quest 3/3S")
    
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

# Definir pool de questões ativas dependendo do modo
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
    st.markdown("Ambiente imersivo com suporte a controles e **Hand Tracking** no Meta Quest 3/3S. Use o Grip/Pinch para mover blocos na distância exata e o Trigger para responder.")
    
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
        
        # Template HTML/JS com componente robusto vr-hand (sem super-hands, evitando tela preta)
        html_template = r"""
        <!DOCTYPE html>
        <html>
          <head>
            <meta charset="utf-8">
            <title>PMSC 2026 Arena VR</title>
            <script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
            <script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v7.4.0/dist/aframe-extras.min.js"></script>
            <style>
              body { margin: 0; background: #000; font-family: sans-serif; }
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
            <div id="hud-overlay">🎯 PMSC Arena VR | Grip/Pinch para mover blocos | Trigger para responder</div>

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

              <!-- Rig e Controles Quest 3 / 3S -->
              <a-entity id="rig" movement-controls="fly: false">
                <a-entity id="camera" camera look-controls position="0 1.6 0">
                  <a-cursor fuse="false" raycaster="objects: .clickable, .grabbable"></a-cursor>
                </a-entity>
                
                <a-entity id="left-hand" hand-controls="hand: left" hand-tracking-controls="hand: left" vr-hand="side: left" raycaster="objects: .clickable, .grabbable; far: 100" line="color: #00d1ff; opacity: 0.85; start: 0 0 0; end: 0 0 -50"></a-entity>
                <a-entity id="right-hand" hand-controls="hand: right" hand-tracking-controls="hand: right" vr-hand="side: right" raycaster="objects: .clickable, .grabbable; far: 100" line="color: #00d1ff; opacity: 0.85; start: 0 0 0; end: 0 0 -50"></a-entity>
              </a-entity>

              <a-light type="ambient" color="#ffffff" intensity="0.85"></a-light>
              <a-light type="directional" position="2 4 2" intensity="0.6"></a-light>

              <!-- Painel de Controle Principal -->
              <a-entity id="control-panel" position="0 2 -2.2">
                <a-plane width="2.4" height="1.4" color="#0b132b" opacity="0.95" material="shader: flat">
                  <a-text value="PMSC 2026 - PAINEL DE CONTROLE" position="0 0.55 0.01" align="center" color="#00d1ff" width="2.2" scale="0.7 0.7 0.7"></a-text>
                  
                  <a-text value="Ambientes & MR:" position="-1.05 0.28 0.01" align="left" color="#ffffff" width="2" scale="0.5 0.5 0.5"></a-text>
                  <a-plane class="clickable" onclick="setEnvironment('passthrough')" width="0.7" height="0.18" position="-0.7 0.12 0.02" color="#00aa55"><a-text value="Passthrough" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="clickable" onclick="setEnvironment('dark')" width="0.5" height="0.18" position="0.0 0.12 0.02" color="#111"><a-text value="Escuro" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="clickable" onclick="setEnvironment('beach')" width="0.5" height="0.18" position="0.55 0.12 0.02" color="#0066cc"><a-text value="Praia" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="clickable" onclick="setEnvironment('office')" width="0.5" height="0.18" position="-0.7 -0.08 0.02" color="#444"><a-text value="Escritorio" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="clickable" onclick="setEnvironment('library')" width="0.5" height="0.18" position="-0.15 -0.08 0.02" color="#663300"><a-text value="Biblioteca" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="clickable" onclick="setEnvironment('space')" width="0.5" height="0.18" position="0.4 -0.08 0.02" color="#220033"><a-text value="Espaço" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>

                  <a-text value="Organização & Layout:" position="-1.05 -0.26 0.01" align="left" color="#ffffff" width="2" scale="0.5 0.5 0.5"></a-text>
                  <a-plane class="clickable" onclick="organizarGrid()" width="0.5" height="0.18" position="-0.7 -0.42 0.02" color="#2b2d42"><a-text value="GRADE" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="clickable" onclick="organizarPorMateria()" width="0.5" height="0.18" position="-0.15 -0.42 0.02" color="#2b2d42"><a-text value="MATERIA" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="clickable" onclick="espalharBlocos()" width="0.5" height="0.18" position="0.4 -0.42 0.02" color="#2b2d42"><a-text value="ESPALHAR" align="center" width="1.5" color="#fff" scale="0.45 0.45 0.45"></a-text></a-plane>
                  <a-plane class="clickable" onclick="salvarLayout()" width="0.32" height="0.15" position="-0.8 -0.62 0.02" color="#006633"><a-text value="Salvar" align="center" width="1.2" color="#fff" scale="0.4 0.4 0.4"></a-text></a-plane>
                  <a-plane class="clickable" onclick="carregarLayout()" width="0.32" height="0.15" position="-0.4 -0.62 0.02" color="#663300"><a-text value="Carregar" align="center" width="1.2" color="#fff" scale="0.4 0.4 0.4"></a-text></a-plane>
                  <a-plane class="clickable" onclick="resetArena()" width="0.32" height="0.15" position="0.0 -0.62 0.02" color="#aa2222"><a-text value="Reset" align="center" width="1.2" color="#fff" scale="0.4 0.4 0.4"></a-text></a-plane>
                </a-plane>
              </a-entity>

              <!-- Painel Calibrador de Mãos -->
              <a-entity id="calibrator-panel" position="1.8 1.8 -1.8" rotation="0 -25 0">
                <a-plane width="1.3" height="1.4" color="#111122" opacity="0.95" material="shader: flat">
                  <a-text value="CALIBRADOR VR" position="0 0.56 0.01" align="center" color="#ffaa00" width="1.8" scale="0.6 0.6 0.6"></a-text>
                  <a-text id="leftHandData" value="Mão Esq: Tracking OK" position="-0.55 0.3 0.01" align="left" color="#00d1ff" width="1.5" scale="0.4 0.4 0.4"></a-text>
                  <a-text id="rightHandData" value="Mão Dir: Tracking OK" position="-0.55 0.1 0.01" align="left" color="#00d1ff" width="1.5" scale="0.4 0.4 0.4"></a-text>
                  
                  <a-plane class="clickable" onclick="ajustarAltura(0.1)" width="0.5" height="0.16" position="-0.3 -0.12 0.02" color="#333"><a-text value="ALTURA +" align="center" width="1.2" color="#fff" scale="0.4 0.4 0.4"></a-text></a-plane>
                  <a-plane class="clickable" onclick="ajustarAltura(-0.1)" width="0.5" height="0.16" position="0.3 -0.12 0.02" color="#333"><a-text value="ALTURA -" align="center" width="1.2" color="#fff" scale="0.4 0.4 0.4"></a-text></a-plane>
                  <a-plane class="clickable" onclick="resetPos()" width="1.1" height="0.16" position="0 -0.32 0.02" color="#aa2222"><a-text value="RESET CÂMERA" align="center" width="1.5" color="#fff" scale="0.4 0.4 0.4"></a-text></a-plane>
                  <a-plane class="clickable" onclick="sairVR()" width="1.1" height="0.16" position="0 -0.52 0.02" color="#444444"><a-text value="SAIR VR" align="center" width="1.5" color="#fff" scale="0.4 0.4 0.4"></a-text></a-plane>
                </a-plane>
              </a-entity>

              <!-- Container de Questões -->
              <a-entity id="questoes-container"></a-entity>
            </a-scene>

            <script>
              const questoesData = __Q_JSON__;
              const modoStr = "__MODO__";

              // Componente customizado 'vr-hand' para grab à distância e clique sem conflitos
              AFRAME.registerComponent('vr-hand', {
                schema: { side: { type: 'string', default: 'right' } },
                init: function () {
                  this.el.addEventListener('gripdown', () => { this.startGrab(); });
                  this.el.addEventListener('gripup', () => { this.endGrab(); });
                  this.el.addEventListener('pinchstarted', () => { this.startGrab(); });
                  this.el.addEventListener('pinchended', () => { this.endGrab(); });
                  this.el.addEventListener('triggerdown', () => { this.clickTarget(); });
                  this.el.addEventListener('thumbstickmoved', (evt) => {
                    this.thumbX = evt.detail.x;
                    this.thumbY = evt.detail.y;
                  });
                  this.isGrabbing = false;
                  this.grabbedBlock = null;
                  this.grabDistance = 0;
                  this.thumbX = 0;
                  this.thumbY = 0;
                  this.raycaster = new THREE.Raycaster();
                  this.raycaster.far = 100;
                },
                tick: function () {
                  const handObj = this.el.object3D;
                  const worldPos = new THREE.Vector3();
                  const worldDir = new THREE.Vector3(0, 0, -1);
                  handObj.getWorldPosition(worldPos);
                  handObj.getWorldDirection(worldDir);
                  worldDir.negate();

                  const intersectables = [];
                  document.querySelectorAll('.clickable, .grabbable').forEach(el => {
                    if (el.object3D) intersectables.push(el.object3D);
                  });

                  this.raycaster.set(worldPos, worldDir);
                  const intersects = this.raycaster.intersectObjects(intersectables, true);

                  window.currentClick = null;
                  window.currentGrabCandidate = null;

                  if (intersects.length > 0) {
                    let hit = intersects[0].object;
                    let curr = hit;
                    while (curr) {
                      if (curr.el) {
                        if (curr.el.classList.contains('clickable')) {
                          window.currentClick = curr.el;
                        }
                        if (curr.el.classList.contains('grabbable')) {
                          window.currentGrabCandidate = curr.el;
                          break;
                        }
                      }
                      curr = curr.parent;
                    }
                  }

                  let hudText = "🎯 Apontando...";
                  if (window.currentClick) hudText = "🎯 CLICK [Alternativa]";
                  if (window.currentGrabCandidate) hudText = "✋ " + window.currentGrabCandidate.id;
                  document.getElementById('hud-overlay').innerText = hudText;

                  if (this.isGrabbing && this.grabbedBlock) {
                    if (Math.abs(this.thumbY) > 0.1) {
                      this.grabDistance += this.thumbY * 0.05;
                      this.grabDistance = Math.max(1.0, Math.min(8.0, this.grabDistance));
                    }
                    if (Math.abs(this.thumbX) > 0.1) {
                      this.grabbedBlock.object3D.rotation.y += this.thumbX * 0.03;
                    }

                    const newPos = worldPos.clone().add(worldDir.clone().multiplyScalar(this.grabDistance));
                    this.grabbedBlock.object3D.position.copy(newPos);
                  }
                },
                startGrab: function() {
                  if (window.currentGrabCandidate) {
                    this.isGrabbing = true;
                    this.grabbedBlock = window.currentGrabCandidate;
                    const handPos = new THREE.Vector3();
                    this.el.object3D.getWorldPosition(handPos);
                    const blockPos = new THREE.Vector3();
                    this.grabbedBlock.object3D.getWorldPosition(blockPos);
                    this.grabDistance = handPos.distanceTo(blockPos);
                    
                    this.grabbedBlock.setAttribute('material', 'emissive', '#ffaa00');
                    document.getElementById('hud-overlay').innerText = "✋ Agarrado " + this.grabbedBlock.id;
                  }
                },
                endGrab: function() {
                  if (this.isGrabbing && this.grabbedBlock) {
                    this.grabbedBlock.removeAttribute('material');
                    this.isGrabbing = false;
                    this.grabbedBlock = null;
                    salvarLayoutAutomatico();
                  }
                },
                clickTarget: function() {
                  if (window.currentClick) {
                    const letra = window.currentClick.getAttribute('data-letra');
                    const correta = window.currentClick.getAttribute('data-correta');
                    if (letra) {
                      if (letra === correta) {
                        window.currentClick.setAttribute('color', '#00aa55');
                        if (navigator.vibrate) navigator.vibrate(200);
                        document.getElementById('hud-overlay').innerText = "✅ Resposta Correta!";
                      } else {
                        window.currentClick.setAttribute('color', '#aa2222');
                        if (navigator.vibrate) navigator.vibrate([100, 50, 100]);
                        document.getElementById('hud-overlay').innerText = "❌ Incorreto! Correta: " + correta;
                      }
                    }
                  }
                }
              });

              function construirBlocos(modoLayout = 'grid') {
                const container = document.getElementById('questoes-container');
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
                  block.setAttribute('data-materia', q.materia_origem || 'Geral');

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
                    altPlane.setAttribute('class', 'clickable');
                    altPlane.setAttribute('position', `0 ${altY} 0.05`);
                    altPlane.setAttribute('width', '1.45');
                    altPlane.setAttribute('height', '0.17');
                    altPlane.setAttribute('color', '#1f4068');
                    altPlane.setAttribute('data-letra', letra);
                    altPlane.setAttribute('data-correta', q.correta.toUpperCase());

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

              function setEnvironment(tipo) {
                const sky = document.getElementById('main-sky');
                const sceneEl = document.querySelector('a-scene');
                
                if (tipo === 'dark') {
                  sky.setAttribute('color', '#050a14');
                  sky.removeAttribute('src');
                } else if (tipo === 'beach') {
                  sky.setAttribute('src', '#beach360');
                  sky.removeAttribute('color');
                } else if (tipo === 'office') {
                  sky.setAttribute('src', '#office360');
                  sky.removeAttribute('color');
                } else if (tipo === 'library') {
                  sky.setAttribute('src', '#library360');
                  sky.removeAttribute('color');
                } else if (tipo === 'space') {
                  sky.setAttribute('src', '#space360');
                  sky.removeAttribute('color');
                } else if (tipo === 'passthrough') {
                  if (navigator.xr) {
                    navigator.xr.requestSession('immersive-ar', {
                      requiredFeatures: ['local-floor'],
                      optionalFeatures: ['passthrough', 'hand-tracking', 'hit-test', 'bounded-floor']
                    }).then((session) => {
                      sceneEl.renderer.xr.setSession(session);
                      sky.setAttribute('color', 'transparent');
                      sky.removeAttribute('src');
                    }).catch(err => alert("Passthrough ativado ou não suportado neste dispositivo."));
                  } else {
                    alert("WebXR não suportado.");
                  }
                }
              }

              function organizarGrid() { construirBlocos('grid'); }
              function organizarPorMateria() { construirBlocos('materia'); }
              function espalharBlocos() { construirBlocos('esparso'); }

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
                document.getElementById('hud-overlay').innerText = "💾 Layout salvo!";
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
                  document.getElementById('hud-overlay').innerText = "⚠️ Nenhum layout salvo.";
                }
              }

              function resetArena() {
                localStorage.removeItem('pmsc_vr_layout');
                construirBlocos('grid');
                document.getElementById('hud-overlay').innerText = "🔄 Arena reiniciada!";
              }

              function ajustarAltura(val) {
                const cam = document.getElementById('camera');
                const pos = cam.getAttribute('position');
                cam.setAttribute('position', `${pos.x} ${Math.max(0.5, Math.min(2.5, pos.y + val))} ${pos.z}`);
              }

              function resetPos() {
                document.getElementById('rig').setAttribute('position', '0 0 0');
                document.getElementById('camera').setAttribute('position', '0 1.6 0');
              }

              function sairVR() {
                const scene = document.querySelector('a-scene');
                if (scene && scene.exitVR) {
                  scene.exitVR();
                }
              }

              setInterval(() => {
                const leftHand = document.getElementById('left-hand');
                const rightHand = document.getElementById('right-hand');
                if (leftHand && leftHand.object3D) {
                  const p = leftHand.object3D.position;
                  document.getElementById('leftHandData').setAttribute('value', `Esq: X=${p.x.toFixed(1)} Y=${p.y.toFixed(1)} Z=${p.z.toFixed(1)}`);
                }
                if (rightHand && rightHand.object3D) {
                  const p = rightHand.object3D.position;
                  document.getElementById('rightHandData').setAttribute('value', `Dir: X=${p.x.toFixed(1)} Y=${p.y.toFixed(1)} Z=${p.z.toFixed(1)}`);
                }
              }, 500);

              window.addEventListener('DOMContentLoaded', () => {
                construirBlocos('grid');
                const saved = localStorage.getItem('pmsc_vr_layout');
                if (saved) {
                  carregarLayout();
                }
              });
            </script>
          </body>
        </html>
        """

        html_vr = html_template.replace("__Q_JSON__", q_json_str)
        html_vr = html_vr.replace("__MODO__", st.session_state["modo_atual"])
        
        st.components.v1.html(html_vr, height=720, scrolling=False)

# ==================== RODAPÉ ====================
st.markdown("---")
st.caption("🛡️ PMSC 2026 Arena VR • Desenvolvido para o Meta Quest 3 e 3S • Instituto AOCP")
