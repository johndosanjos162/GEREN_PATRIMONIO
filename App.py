import json
import random
import streamlit as st
from datetime import datetime

# Configuração da Página Streamlit
st.set_page_config(
    page_title="PMSC Arena VR",
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

# Distribuição oficial AOCP para o Simulado de 60 questões
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
def load_json_data():
    """Carrega o json.json suportando múltiplos objetos concatenados e deduplica por pergunta."""
    try:
        with open("json.json", "r", encoding="utf-8") as f:
            content = f.read().strip()
        
        decoder = json.JSONDecoder()
        pos = 0
        all_data = []
        while pos < len(content):
            while pos < len(content) and content[pos].isspace():
                pos += 1
            if pos >= len(content):
                break
            obj, idx = decoder.raw_decode(content, pos)
            all_data.append(obj)
            pos = idx
            
        merged = {}
        vistas = set()
        
        for item in all_data:
            if isinstance(item, dict):
                for materia, questoes in item.items():
                    if materia not in merged:
                        merged[materia] = []
                    for q in questoes:
                        texto = q.get("pergunta", "").strip().lower()
                        if texto and texto not in vistas:
                            vistas.add(texto)
                            merged[materia].append(q)
        return merged
    except Exception as e:
        # Fallback se o arquivo não existir ou estiver vazio
        return {
            "Legislação Institucional": [
                {
                    "pergunta": "Exemplo: Qual a missão constitucional da PMSC?",
                    "alternativas": ["A) Policiamento ostensivo", "B) Combate incêndios", "C) Legislação federal", "D) Trânsito rodoviário", "E) Defesa civil exclusiva"],
                    "correta": "A"
                }
            ]
        }

dados_banco = load_json_data()

# Contagem total de questões únicas
total_unicas = sum(len(q_list) for q_list in dados_banco.values())

# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("🛡️ PMSC ARENA VR")
    st.caption("Meta Quest 3/3S • Instituto AOCP")
    
    st.metric("Questões no Banco", total_unicas)
    
    if st.button("🔄 Recarregar json.json"):
        load_json_data.clear()
        st.session_state["vr_loaded"] = False
        st.rerun()
        
    st.divider()
    st.subheader("Configurar Treino")
    materias_disponiveis = list(dados_banco.keys())
    materia_escolhida = st.selectbox("Matéria", materias_disponiveis if materias_disponiveis else ["Geral"])
    qtd_treino = st.slider("Quantidade de Questões", 5, 20, 10)
    
    if st.button("🚀 Iniciar Treino VR", type="primary"):
        pool = dados_banco.get(materia_escolhida, [])
        selected = random.sample(pool, min(qtd_treino, len(pool))) if pool else []
        st.session_state["questoes_treino"] = selected
        st.session_state["simulado_ativo"] = False
        st.session_state["vr_loaded"] = False
        st.success(f"Treino gerado com {len(selected)} questões!")
        st.rerun()
        
    st.divider()
    st.subheader("Simulado Oficial (60q)")
    if not st.session_state["simulado_ativo"]:
        if st.button("🎯 Iniciar Simulado 60q"):
            sim_questoes = []
            for mat, qtd in DISTRIBUICAO_OFICIAL.items():
                pool = dados_banco.get(mat, [])
                if pool:
                    escolhidas = random.sample(pool, min(qtd, len(pool)))
                    for q in escolhidas:
                        q_copy = q.copy()
                        q_copy["materia_origem"] = mat
                        sim_questoes.append(q_copy)
            random.shuffle(sim_questoes)
            st.session_state["questoes_simulado"] = sim_questoes
            st.session_state["simulado_ativo"] = True
            st.session_state["vr_loaded"] = False
            st.rerun()
    else:
        if st.button("❌ Cancelar Simulado Ativo"):
            st.session_state["simulado_ativo"] = False
            st.rerun()
            
    if st.session_state["history"]:
        st.divider()
        st.subheader("Histórico Recente")
        for h in st.session_state["history"][-5:]:
            status_cor = "🟢 Aprovado" if h["aprovado"] else "🔴 Reprovado"
            st.markdown(f"**{h['data']}** | Nota: {h['nota']:.1f}% | {status_cor}")

# ==================== CONTEÚDO PRINCIPAL ====================
tab_vr, tab_simulado = st.tabs(["🥽 Arena VR", "📝 Simulado Clássico"])

# Selecionar lote de questões ativas (Treino ou Simulado)
questoes_ativas = st.session_state["questoes_simulado"] if st.session_state["simulado_ativo"] else st.session_state["questoes_treino"]
if not questoes_ativas:
    primeira_mat = list(dados_banco.keys())[0] if dados_banco else "Geral"
    questoes_ativas = dados_banco.get(primeira_mat, [])[:18]

with tab_simulado:
    st.header("Simulado Oficial PMSC (Instituto AOCP)")
    if not st.session_state["simulado_ativo"]:
        st.info("Inicie um simulado pela barra lateral para realizar a prova clássica de 60 questões com timer e gabarito comentado.")
    else:
        st.write(f"Simulado em andamento com {len(st.session_state['questoes_simulado'])} questões.")
        with st.form("form_simulado"):
            respostas_usuario = {}
            for idx, q in enumerate(st.session_state["questoes_simulado"]):
                st.markdown(f"**Questão {idx+1}** *({q.get('materia_origem', 'Geral')})*: {q['pergunta']}")
                alt = q["alternativas"]
                resp = st.radio(f"Escolha a alternativa Q{idx+1}", alt, key=f"q_{idx}", index=None)
                respostas_usuario[idx] = resp
                st.divider()
            
            submitted = st.form_submit_button("Finalizar Simulado")
            if submitted:
                acertos = 0
                total = len(st.session_state["questoes_simulado"])
                for idx, q in enumerate(st.session_state["questoes_simulado"]):
                    escolha = respostas_usuario.get(idx)
                    if escolha:
                        letra_escolhida = escolha[0].upper()
                        if letra_escolhida == q["correta"].upper():
                            acertos += 1
                nota = (acertos / total) * 100 if total > 0 else 0
                aprovado = nota >= 50.0
                
                reg = {
                    "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "acertos": acertos,
                    "total": total,
                    "nota": nota,
                    "aprovado": aprovado
                }
                st.session_state["history"].append(reg)
                st.session_state["simulado_ativo"] = False
                st.success(f"Simulado finalizado! Acertos: {acertos}/{total} ({nota:.1f}%)")
                st.rerun()

with tab_vr:
    st.header("Arena de Estudos VR (Meta Quest 3 / 3S)")
    st.markdown("Estude em um ambiente imersivo 3D. Mova blocos de questões, responda com o laser ou hand tracking, altere o cenário e teste a Realidade Mista (Passthrough).")
    
    if not st.session_state["vr_loaded"]:
        if st.button("⚡ CARREGAR AMBIENTE VR", type="primary"):
            st.session_state["vr_loaded"] = True
            st.rerun()
    else:
        if st.button("🔄 Descarregar / Recarregar VR"):
            st.session_state["vr_loaded"] = False
            st.rerun()
            
        q_json_str = json.dumps(questoes_ativas[:18], ensure_ascii=False)
        modo_atual = "Simulado" if st.session_state["simulado_ativo"] else "Treino"
        
        # Template string r"""...""" com .replace() para evitar problemas com f-strings e chaves CSS/JS
        html_vr = r"""
        <!DOCTYPE html>
        <html>
          <head>
            <meta charset="utf-8">
            <title>PMSC Arena VR</title>
            <script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
            <script src="https://unpkg.com/aframe-extras@7.4.0/dist/aframe-extras.min.js"></script>
            <style>
              body { margin: 0; background: #000; font-family: sans-serif; }
              #hud-overlay {
                position: absolute; top: 10px; left: 50%; transform: translateX(-50%);
                background: rgba(0,0,0,0.8); color: #00d1ff; padding: 10px 20px;
                border-radius: 8px; font-size: 16px; font-weight: bold; z-index: 999;
                border: 1px solid #00d1ff; pointer-events: none;
              }
            </style>
          </head>
          <body>
            <div id="hud-overlay">🎯 Pressione Grip para mover blocos | Trigger para responder</div>

            <a-scene embedded vr-mode-ui="enabled: true">
              <a-assets>
                <img id="sky-sechelt" src="https://cdn.aframe.io/360-image-gallery-boilerplate/img/sechelt.jpg">
                <img id="sky-city" src="https://cdn.aframe.io/360-image-gallery-boilerplate/img/city.jpg">
                <img id="sky-cubes" src="https://cdn.aframe.io/360-image-gallery-boilerplate/img/cubes.jpg">
              </a-assets>

              <a-sky id="main-sky" color="#050a14"></a-sky>

              <a-entity id="rig" movement-controls="fly: false">
                <a-camera id="camera" position="0 1.6 0">
                  <a-cursor fuse="false" raycaster="objects: .clickable, .grabbable"></a-cursor>
                </a-camera>
                
                <a-entity id="left-hand" hand-controls="hand: left" hand-tracking-controls="hand: left" vr-hand="side: left" raycaster="objects: .clickable, .grabbable; far: 100" line="color: #00d1ff; opacity: 0.85; start: 0 0 0; end: 0 0 -50"></a-entity>
                <a-entity id="right-hand" hand-controls="hand: right" hand-tracking-controls="hand: right" vr-hand="side: right" raycaster="objects: .clickable, .grabbable; far: 100" line="color: #00d1ff; opacity: 0.85; start: 0 0 0; end: 0 0 -50"></a-entity>
              </a-entity>

              <a-light type="ambient" color="#ffffff" intensity="0.8"></a-light>
              <a-light type="directional" position="2 4 2" intensity="0.6"></a-light>

              <a-entity id="control-panel" position="0 2 -2">
                <a-plane width="2.2" height="1.2" color="#111" opacity="0.9">
                  <a-text value="PMSC ARENA VR - PAINEL" position="0 0.45 0.01" align="center" color="#00d1ff" width="2"></a-text>
                  
                  <a-text value="Ambientes:" position="-0.9 0.2 0.01" align="left" color="#fff" width="1.5" scale="0.7 0.7 0.7"></a-text>
                  <a-plane class="clickable" onclick="setSky('escuro')" width="0.35" height="0.2" position="-0.7 0.05 0.02" color="#222"><a-text value="Escuro" align="center" width="1" color="#fff" scale="0.6 0.6 0.6"></a-text></a-plane>
                  <a-plane class="clickable" onclick="setSky('praia')" width="0.35" height="0.2" position="-0.3 0.05 0.02" color="#0066cc"><a-text value="Praia" align="center" width="1" color="#fff" scale="0.6 0.6 0.6"></a-text></a-plane>
                  <a-plane class="clickable" onclick="setSky('escritorio')" width="0.35" height="0.2" position="0.1 0.05 0.02" color="#444"><a-text value="Escrit." align="center" width="1" color="#fff" scale="0.6 0.6 0.6"></a-text></a-plane>
                  <a-plane class="clickable" onclick="setSky('biblioteca')" width="0.35" height="0.2" position="0.5 0.05 0.02" color="#663300"><a-text value="Biblio" align="center" width="1" color="#fff" scale="0.6 0.6 0.6"></a-text></a-plane>
                  <a-plane class="clickable" onclick="setSky('espaco')" width="0.35" height="0.2" position="-0.5 -0.2 0.02" color="#111"><a-text value="Espaço" align="center" width="1" color="#fff" scale="0.6 0.6 0.6"></a-text></a-plane>
                  <a-plane class="clickable" onclick="setSky('passthrough')" width="0.55" height="0.2" position="0.1 -0.2 0.02" color="#00aa55"><a-text value="Passthrough" align="center" width="1" color="#fff" scale="0.5 0.5 0.5"></a-text></a-plane>

                  <a-text value="Layout:" position="-0.9 -0.4 0.01" align="left" color="#fff" width="1.5" scale="0.7 0.7 0.7"></a-text>
                  <a-plane class="clickable" onclick="organizarGrid()" width="0.35" height="0.2" position="-0.5 -0.55 0.02" color="#333"><a-text value="Grid" align="center" width="1" color="#fff" scale="0.6 0.6 0.6"></a-text></a-plane>
                  <a-plane class="clickable" onclick="salvarLayout()" width="0.35" height="0.2" position="-0.1 -0.55 0.02" color="#006633"><a-text value="Salvar" align="center" width="1" color="#fff" scale="0.6 0.6 0.6"></a-text></a-plane>
                  <a-plane class="clickable" onclick="carregarLayout()" width="0.35" height="0.2" position="0.3 -0.55 0.02" color="#663300"><a-text value="Carregar" align="center" width="1" color="#fff" scale="0.6 0.6 0.6"></a-text></a-plane>
                </a-plane>
              </a-entity>

              <a-entity id="calibrator-panel" position="1.8 1.8 -1.5" rotation="0 -25 0">
                <a-plane width="1.2" height="1.4" color="#111" opacity="0.9">
                  <a-text value="CALIBRADOR VR" position="0 0.55 0.01" align="center" color="#ffaa00" width="1.8"></a-text>
                  <a-text id="calib-text" value="Tracking: Ativo" position="-0.5 0.25 0.01" align="left" color="#fff" width="1.5" scale="0.6 0.6 0.6"></a-text>
                  
                  <a-plane class="clickable" onclick="ajustarAltura(0.1)" width="0.45" height="0.18" position="-0.3 -0.1 0.02" color="#333"><a-text value="ALTURA +" align="center" width="1" color="#fff" scale="0.5 0.5 0.5"></a-text></a-plane>
                  <a-plane class="clickable" onclick="ajustarAltura(-0.1)" width="0.45" height="0.18" position="0.3 -0.1 0.02" color="#333"><a-text value="ALTURA -" align="center" width="1" color="#fff" scale="0.5 0.5 0.5"></a-text></a-plane>
                  <a-plane class="clickable" onclick="resetPos()" width="0.95" height="0.18" position="0 -0.35 0.02" color="#aa2222"><a-text value="RESET POSIÇÃO" align="center" width="1" color="#fff" scale="0.5 0.5 0.5"></a-text></a-plane>
                </a-plane>
              </a-entity>

              <a-entity id="questoes-container"></a-entity>
            </a-scene>

            <script>
              const questoesData = __Q_JSON__;
              const modo = "__MODO__";

              AFRAME.registerComponent('vr-hand', {
                schema: { side: { type: 'string', default: 'right' } },
                init: function () {
                  this.el.addEventListener('gripdown', (evt) => { this.startGrab(); });
                  this.el.addEventListener('gripup', (evt) => { this.endGrab(); });
                  this.el.addEventListener('pinchstarted', (evt) => { this.startGrab(); });
                  this.el.addEventListener('pinchended', (evt) => { this.endGrab(); });
                  this.el.addEventListener('triggerdown', (evt) => { this.clickTarget(); });
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
                startGrabsFromCandidate: function() {
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
                startGrab: function() {
                  this.startGrabsFromCandidate();
                },
                endGrab: function() {
                  if (this.isGrabbing && this.grabbedBlock) {
                    this.grabbedBlock.removeAttribute('material');
                    this.isGrabbing = false;
                    this.grabbedBlock = null;
                  }
                },
                clickTarget: function() {
                  if (window.currentClick) {
                    const letra = window.currentClick.getAttribute('data-letra');
                    const correta = window.currentClick.getAttribute('data-correta');
                    if (letra) {
                      if (letra === correta) {
                        window.currentClick.setAttribute('color', '#00ff66');
                        if (navigator.vibrate) navigator.vibrate(200);
                        document.getElementById('hud-overlay').innerText = "✅ Correta!";
                      } else {
                        window.currentClick.setAttribute('color', '#ff0033');
                        if (navigator.vibrate) navigator.vibrate([100, 50, 100]);
                        document.getElementById('hud-overlay').innerText = "❌ Errado! Correta: " + correta;
                      }
                    }
                  }
                }
              });

              function construirBlocos() {
                const container = document.getElementById('questoes-container');
                container.innerHTML = "";
                
                questoesData.forEach((q, index) => {
                  const col = index % 4;
                  const row = Math.floor(index / 4);
                  const x = (col - 1.5) * 1.8;
                  const y = 2.2 - (row * 1.4);
                  const z = -3.5 - (Math.floor(index / 12) * 2.0);

                  const block = document.createElement('a-entity');
                  block.setAttribute('id', 'block-' + index);
                  block.setAttribute('class', 'grabbable');
                  block.setAttribute('position', `${x} ${y} ${z}`);
                  block.setAttribute('geometry', 'primitive: box; width: 1.6; height: 1.2; depth: 0.1');
                  block.setAttribute('material', 'color: #1a1a2e; shader: flat');

                  const titulo = document.createElement('a-text');
                  titulo.setAttribute('value', `Q.${index+1} (${modo})`);
                  titulo.setAttribute('position', '-0.75 0.5 0.06');
                  titulo.setAttribute('scale', '0.5 0.5 0.5');
                  titulo.setAttribute('color', '#00d1ff');
                  block.appendChild(titulo);

                  const pergunta = document.createElement('a-text');
                  let pText = q.pergunta.length > 90 ? q.pergunta.substring(0, 87) + '...' : q.pergunta;
                  pergunta.setAttribute('value', pText);
                  pergunta.setAttribute('position', '-0.75 0.3 0.06');
                  pergunta.setAttribute('width', '1.5');
                  pergunta.setAttribute('scale', '0.35 0.35 0.35');
                  pergunta.setAttribute('color', '#ffffff');
                  block.appendChild(pergunta);

                  q.alternativas.forEach((alt, aIdx) => {
                    const letra = alt[0].toUpperCase();
                    const altY = 0.05 - (aIdx * 0.22);

                    const altPlane = document.createElement('a-plane');
                    altPlane.setAttribute('class', 'clickable');
                    altPlane.setAttribute('position', `0 ${altY} 0.06`);
                    altPlane.setAttribute('width', '1.5');
                    altPlane.setAttribute('height', '0.18');
                    altPlane.setAttribute('color', '#2d3748');
                    altPlane.setAttribute('data-letra', letra);
                    altPlane.setAttribute('data-correta', q.correta.toUpperCase());

                    const altText = document.createElement('a-text');
                    altText.setAttribute('value', alt);
                    altText.setAttribute('position', '-0.7 0 0.01');
                    altText.setAttribute('width', '1.4');
                    altText.setAttribute('scale', '0.35 0.35 0.35');
                    altText.setAttribute('color', '#ffffff');

                    altPlane.appendChild(altText);
                    block.appendChild(altPlane);
                  });

                  container.appendChild(block);
                });
              }

              function setSky(tipo) {
                const sky = document.getElementById('main-sky');
                const sceneEl = document.querySelector('a-scene');
                
                if (tipo === 'escuro') {
                  sky.setAttribute('color', '#050a14');
                  sky.removeAttribute('src');
                } else if (tipo === 'praia') {
                  sky.setAttribute('src', '#sky-sechelt');
                  sky.removeAttribute('color');
                } else if (tipo === 'escritorio') {
                  sky.setAttribute('src', '#sky-city');
                  sky.removeAttribute('color');
                } else if (tipo === 'biblioteca') {
                  sky.setAttribute('src', '#sky-cubes');
                  sky.removeAttribute('color');
                } else if (tipo === 'espaco') {
                  sky.setAttribute('color', '#000005');
                  sky.removeAttribute('src');
                } else if (tipo === 'passthrough') {
                  if (navigator.xr) {
                    navigator.xr.requestSession('immersive-ar', {
                      requiredFeatures: ['local-floor'],
                      optionalFeatures: ['passthrough', 'hand-tracking', 'hit-test', 'bounded-floor']
                    }).then((session) => {
                      sceneEl.renderer.xr.setSession(session);
                    }).catch(err => alert("Passthrough disponível apenas no Meta Quest Browser."));
                  } else {
                    alert("XR não suportado neste navegador.");
                  }
                }
              }

              function organizarGrid() {
                construirBlocos();
              }

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
                alert('Layout salvo com sucesso no navegador!');
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
                  alert('Layout restaurado!');
                } else {
                  alert('Nenhum layout salvo encontrado.');
                }
              }

              function ajustarAltura(val) {
                const cam = document.getElementById('camera');
                const pos = cam.getAttribute('position');
                cam.setAttribute('position', `${pos.x} ${Math.max(0.4, Math.min(2.5, pos.y + val))} ${pos.z}`);
              }

              function resetPos() {
                document.getElementById('rig').setAttribute('position', '0 0 0');
                document.getElementById('camera').setAttribute('position', '0 1.6 0');
              }

              window.addEventListener('DOMContentLoaded', () => {
                construirBlocos();
              });
            </script>
          </body>
        </html>
        """

        html_vr = html_vr.replace("__Q_JSON__", q_json_str)
        html_vr = html_vr.replace("__MODO__", modo_atual)
        
        st.components.v1.html(html_vr, height=650, scrolling=False)
