import streamlit as st
import streamlit.components.v1 as components
import json
import random
import time
import pathlib
from datetime import datetime

st.set_page_config(
    page_title="PMSC 2026 – Simulador Imersivo AOCP",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==================================================================
# DISTRIBUIÇÃO OFICIAL EDITAL PMSC 2026 - AOCP (60 questões)
# ==================================================================
DISTRIBUICAO = {
    "Legislação Institucional": 10,
    "Direito Constitucional": 8,
    "Língua Portuguesa": 8,
    "Direito Penal Comum": 6,
    "Direito Processual Penal Comum": 6,
    "Direito Penal Militar": 6,
    "Legislação Especial": 6,
    "Legislação de Trânsito": 5,
    "Informática": 5,
}
TOTAL = 60

# ==================================================================
# CARREGAMENTO DO JSON
# ==================================================================
@st.cache_data
def load_questoes_from_file(path="json_corrigido.json"):
    p = pathlib.Path(path)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Normaliza: pode ser dict de listas ou lista
        if isinstance(data, dict):
            return data
        elif isinstance(data, list):
            # agrupa por materia se tiver campo
            from collections import defaultdict
            d = defaultdict(list)
            for q in data:
                d[q.get("materia", "Geral")].append(q)
            return dict(d)
    return None

def load_questoes():
    # tenta json_corrigido.json, json.json, e upload
    for cand in ["json_corrigido.json", "json.json", "/mnt/data/json_corrigido.json", "/mnt/data/json.json"]:
        data = load_questoes_from_file(cand)
        if data:
            return data
    return None

# ==================================================================
# RENDER 3D - WEBXR PARA META QUEST 3S
# ==================================================================
def render_3d_quest(questoes, modo="simulado"):
    # Limita para performance no Quest - max 60 blocos
    questoes_json = json.dumps(questoes[:60], ensure_ascii=False)
    # HTML imersivo com A-Frame 1.5 + super-hands + grabbable
    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v7.0.0/dist/aframe-extras.min.js"></script>
<script src="https://unpkg.com/super-hands@3.1.0/dist/super-hands.min.js"></script>
<script src="https://unpkg.com/aframe-event-set-component@5.0.0/dist/aframe-event-set-component.min.js"></script>
<style>
  body {{ margin:0; overflow:hidden; font-family: sans-serif; }}
  #hud {{ position: absolute; top:10px; left:10px; color:white; background: rgba(0,0,0,0.6); padding:10px; border-radius:8px; z-index:999; font-size:14px; max-width:320px; }}
  #enter-vr {{ position:absolute; bottom:20px; left:50%; transform:translateX(-50%); z-index:999; padding:14px 28px; background:#00d1ff; border:none; border-radius:12px; font-weight:bold; cursor:pointer; }}
</style>
</head>
<body>
<div id="hud">
<b>🥽 MODO QUEST 3S</b><br>
👊 <b>Pinch/Grab:</b> mover blocos<br>
👉 <b>Laser / Toque:</b> marcar alternativa<br>
🎯 {len(questoes)} blocos | {modo}<br>
<span id="progress">0/{len(questoes)} respondidas</span><br>
<small>Entre em VR pelo botão abaixo</small>
</div>
<button id="enter-vr">ENTRAR EM VR - META QUEST 3S</button>

<a-scene
  background="color: #0a1020"
  renderer="antialias: true; colorManagement: true"
  webxr="optionalFeatures: hand-tracking, hit-test, local-floor, bounded-floor"
  xr-mode-ui="enabled: true"
  >
  <a-assets>
    <a-mixin id="block-mat" material="color: #1a2a4a; metalness: 0.2; roughness: 0.6"></a-mixin>
  </a-assets>

  <!-- Luzes -->
  <a-entity light="type: ambient; intensity: 0.6"></a-entity>
  <a-entity light="type: directional; intensity: 0.8" position="2 4 2"></a-entity>
  <a-entity light="type: point; intensity: 0.5; distance: 20" position="0 3 0" color="#00d1ff"></a-entity>

  <!-- Chão infinito -->
  <a-plane position="0 0 0" rotation="-90 0 0" width="40" height="40" color="#0f1a30" material="roughness: 0.8"></a-plane>
  <a-grid position="0 0.01 0" width="40" height="40" color="#1a3a6a"></a-grid>

  <!-- Rig com mãos e controles -->
  <a-entity id="rig" position="0 0 4">
    <a-entity id="camera" camera look-controls wasd-controls position="0 1.6 0">
      <a-entity cursor="rayOrigin: mouse" raycaster="objects: .clickable"></a-entity>
    </a-entity>
    
    <!-- Controle esquerdo - grab -->
    <a-entity id="left-hand" hand-controls="hand: left; handModelStyle: lowPoly; color: #00d1ff"
              super-hands="grabStartButtons: gripdown, pinchstart; grabEndButtons: gripup, pinchend"
              sphere-collider="objects: .grabbable"
              laser-controls="hand: left" raycaster="objects: .clickable, .grabbable; far: 10"
              line="color: #00d1ff"></a-entity>
    <!-- Controle direito - laser para marcar -->
    <a-entity id="right-hand" hand-controls="hand: right; handModelStyle: lowPoly; color: #ff6a00"
              super-hands="grabStartButtons: gripdown, pinchstart; grabEndButtons: gripup, pinchend"
              sphere-collider="objects: .grabbable"
              laser-controls="hand: right" raycaster="objects: .clickable, .grabbable; far: 10"
              line="color: #ff6a00"></a-entity>
  </a-entity>

  <!-- Container de blocos -->
  <a-entity id="blocos-container"></a-entity>

</a-scene>

<script>
const questoes = {questoes_json};
let respostas = {{}};
let respondidas = 0;

function updateHUD(){{
  document.getElementById('progress').innerText = `${{respondidas}}/${{questoes.length}} respondidas`;
}}

function criarBloco(q, index){{
  const cols = 5;
  const spacing = 2.2;
  const x = (index % cols) * spacing - ((cols-1)*spacing/2);
  const z = Math.floor(index / cols) * -2.5;
  const y = 1.2 + Math.random()*0.6;

  const id = `bloco-${{index}}`;
  const container = document.createElement('a-entity');
  container.setAttribute('id', id);
  container.setAttribute('position', `${{x}} ${{y}} ${{z}}`);
  container.setAttribute('class', 'grabbable');
  container.setAttribute('grabbable', '');
  container.setAttribute('stretchable', '');
  container.setAttribute('draggable', '');
  container.setAttribute('droppable', '');

  // Caixa principal
  const box = document.createElement('a-box');
  box.setAttribute('width', '1.9');
  box.setAttribute('height', '1.4');
  box.setAttribute('depth', '0.15');
  box.setAttribute('color', '#162a50');
  box.setAttribute('material', 'metalness:0.1; roughness:0.7');
  box.setAttribute('class', 'grabbable');
  box.setAttribute('event-set__hover', '_event: mouseenter; material.color: #1e3a6a');
  box.setAttribute('event-set__leave', '_event: mouseleave; material.color: #162a50');

  // Texto pergunta
  const perguntaCurta = q.pergunta.length > 140 ? q.pergunta.substring(0,137)+'...' : q.pergunta;
  const texto = document.createElement('a-text');
  texto.setAttribute('value', `${{index+1}}. [${{q.materia || q.materia || 'Geral'}}]\\n${{perguntaCurta}}`);
  texto.setAttribute('position', '0 0.35 0.08');
  texto.setAttribute('align', 'center');
  texto.setAttribute('width', '1.7');
  texto.setAttribute('color', '#ffffff');
  texto.setAttribute('wrap-count', '30');

  container.appendChild(box);
  container.appendChild(texto);

  // Alternativas como botões 3D
  q.alternativas.forEach((alt, aIdx) => {{
    const letra = alt.charAt(0);
    const btn = document.createElement('a-entity');
    btn.setAttribute('position', `-0.6 ${{0.05 - aIdx*0.18}} 0.1`);
    btn.setAttribute('class', 'clickable');
    btn.setAttribute('data-bloco', index);
    btn.setAttribute('data-letra', letra);

    const plane = document.createElement('a-plane');
    plane.setAttribute('width', '1.6');
    plane.setAttribute('height', '0.15');
    plane.setAttribute('color', '#0f1f3f');
    plane.setAttribute('class', 'clickable');

    const label = document.createElement('a-text');
    label.setAttribute('value', alt.length > 48 ? alt.substring(0,45)+'...' : alt);
    label.setAttribute('align', 'left');
    label.setAttribute('position', '-0.75 0 0.01');
    label.setAttribute('width', '1.5');
    label.setAttribute('color', '#cde0ff');
    label.setAttribute('wrap-count', '28');

    plane.appendChild(label);
    btn.appendChild(plane);

    // Clique
    btn.addEventListener('click', (e) => {{
      const blocoIdx = parseInt(btn.getAttribute('data-bloco'));
      const letra = btn.getAttribute('data-letra');
      respostas[blocoIdx] = letra;
      // Feedback visual
      const allBtns = document.querySelectorAll(`[data-bloco='${{blocoIdx}}'] a-plane`);
      allBtns.forEach(b => b.setAttribute('color', '#0f1f3f'));
      plane.setAttribute('color', '#00ff88');
      
      // Marca respondida
      const isNew = !(blocoIdx in respostas) || true;
      // Conta
      respondidas = Object.keys(respostas).length;
      updateHUD();
      
      // Haptics no Quest
      const rightHand = document.getElementById('right-hand');
      if (rightHand && rightHand.components.haptics) {{
        rightHand.components.haptics.pulse(0.5, 100);
      }}
    }});
    
    container.appendChild(btn);
  }});

  return container;
}}

document.addEventListener('DOMContentLoaded', () => {{
  const container = document.getElementById('blocos-container');
  questoes.forEach((q,i) => {{
    const bloco = criarBloco(q,i);
    container.appendChild(bloco);
  }});
  
  document.getElementById('enter-vr').addEventListener('click', () => {{
    const scene = document.querySelector('a-scene');
    if (scene.is('vr-mode')) {{
      scene.exitVR();
    }} else {{
      scene.enterVR();
    }}
  }});
  
  // Comunicação com Streamlit via localStorage (opcional)
  setInterval(() => {{
    localStorage.setItem('pmsc_respostas_vr', JSON.stringify(respostas));
  }}, 1000);
}});

// Suporte a arrastar blocos no espaço
AFRAME.registerComponent('draggable', {{
  init: function() {{
    this.el.addEventListener('grab-start', (e) => {{
      this.el.setAttribute('material', 'color', '#2a5a9a');
    }});
    this.el.addEventListener('grab-end', (e) => {{
      this.el.setAttribute('material', 'color', '#162a50');
    }});
  }}
}});
</script>
</body>
</html>
"""
    components.html(html, height=780, scrolling=False)

# ==================================================================
# LÓGICA DE SIMULADO
# ==================================================================
def montar_simulado(banco, distribuicao):
    import random
    simulado = []
    for materia, qtd in distribuicao.items():
        # busca case-insensitive
        pool = []
        for k,v in banco.items():
            if k.lower().strip() == materia.lower().strip():
                pool = v
                break
            if materia.lower() in k.lower() or k.lower() in materia.lower():
                if not pool:
                    pool = v
        if not pool:
            continue
        amostra = random.sample(pool, min(qtd, len(pool)))
        for q in amostra:
            q_copy = q.copy()
            q_copy["materia"] = materia
            simulado.append(q_copy)
    random.shuffle(simulado)
    return simulado

# ==================================================================
# INIT STATE
# ==================================================================
if "simulado" not in st.session_state:
    st.session_state.simulado = None
if "historico" not in st.session_state:
    st.session_state.historico = []
if "treino" not in st.session_state:
    st.session_state.treino = []
if "questoes_json" not in st.session_state:
    st.session_state.questoes_json = load_questoes()

# ==================================================================
# SIDEBAR
# ==================================================================
with st.sidebar:
    st.title("🎯 PMSC 2026 - AOCP")
    st.caption("Soldado - Simulador Oficial")
    
    # Upload JSON
    st.subheader("📂 Banco de Questões")
    uploaded = st.file_uploader("Carregue seu json.json", type=["json"])
    if uploaded:
        try:
            data = json.load(uploaded)
            if isinstance(data, list):
                from collections import defaultdict
                d = defaultdict(list)
                for q in data:
                    d[q.get("materia","Geral")].append(q)
                data = dict(d)
            st.session_state.questoes_json = data
            st.success(f"✅ {sum(len(v) for v in data.values())} questões carregadas!")
        except Exception as e:
            st.error(f"Erro no JSON: {e}")
    
    banco = st.session_state.questoes_json
    if banco:
        st.info(f"📚 Banco atual: **{sum(len(v) for v in banco.values())}** questões em **{len(banco)}** matérias")
        with st.expander("Ver matérias"):
            for k,v in banco.items():
                st.caption(f"{k}: {len(v)}")

    st.divider()
    st.subheader("🧠 Modos de Estudo")
    
    # TREINO
    if banco:
        materia_sel = st.selectbox("Treinar matéria", options=list(banco.keys()))
        qtd_treino = st.slider("Qtd questões", 5, 20, 10)
        if st.button("▶️ Gerar Treino 3D", use_container_width=True):
            pool = banco.get(materia_sel, [])
            amostra = random.sample(pool, min(qtd_treino, len(pool)))
            for q in amostra:
                q["materia"] = materia_sel
            st.session_state.treino = amostra
            st.session_state.simulado = None
            st.rerun()
    
    st.divider()
    st.subheader("🏆 Simulado Oficial")
    st.caption(f"{TOTAL} questões | 4h | 50% para aprovação")
    if banco:
        if st.button("🚀 Iniciar Simulado Oficial PMSC 2026", type="primary", use_container_width=True):
            sim_q = montar_simulado(banco, DISTRIBUICAO)
            if len(sim_q) < TOTAL:
                st.warning(f"Só foi possível montar {len(sim_q)} questões. Verifique se o banco tem questões suficientes por matéria.")
            st.session_state.simulado = {
                "questoes": sim_q,
                "inicio": time.time(),
                "respostas": {},
                "finalizado": False,
            }
            st.session_state.treino = []
            st.rerun()
        if st.session_state.simulado and not st.session_state.simulado["finalizado"]:
            if st.button("❌ Cancelar Simulado", use_container_width=True):
                st.session_state.simulado = None
                st.rerun()

    st.divider()
    st.subheader("🥽 Meta Quest 3S")
    st.markdown("""
    **Como usar no Quest 3S:**
    1. Abra este app no **Meta Browser**
    2. Clique em **ENTRAR EM VR**
    3. **Pinch** (juntar dedos) para **mover blocos**
    4. **Laser** do controle para **marcar A-E**
    5. Blocos ficam flutuando em sala 40m²
    6. Suporte a **hand-tracking** nativo
    """)
    st.caption("WebXR + super-hands + grabbable - otimizado para Quest 3S")

# ==================================================================
# MAIN
# ==================================================================
st.title("🎯 PMSC 2026 – Simulador Imersivo AOCP")
st.caption("60 questões | Estilo AOCP | 3D + WebXR | Meta Quest 3S Ready")

banco = st.session_state.questoes_json
if not banco:
    st.warning("⚠️ Nenhum banco carregado. Faça upload do seu `json.json` na barra lateral.")
    st.info("Use o arquivo `json_corrigido.json` que corrigi anteriormente (646 questões).")
    st.stop()

if st.session_state.simulado:
    sim = st.session_state.simulado
    questoes = sim["questoes"]
    if not sim["finalizado"]:
        restante = max(0, 4*3600 - int(time.time() - sim["inicio"]))
        h,m,s = restante//3600, (restante%3600)//60, restante%60
        col1, col2, col3 = st.columns([2,1,1])
        col1.warning(f"⏱️ Tempo restante: {h:02d}:{m:02d}:{s:02d}")
        col2.metric("Questões", len(questoes))
        col3.metric("Respondidas", len(sim["respostas"]))
        
        st.subheader("🌐 Arena 3D Imersiva - Meta Quest 3S")
        st.caption("Mova os blocos no espaço. No Quest 3S, use as mãos para agarrar. No desktop, use mouse.")
        render_3d_quest(questoes, modo="SIMULADO OFICIAL")
        
        st.divider()
        st.subheader("✍️ Marcação Oficial (espelho do VR)")
        with st.form("form_sim"):
            respostas = {}
            for i,q in enumerate(questoes):
                st.markdown(f"**{i+1}. [{q.get('materia','')}]** {q['pergunta']}")
                escolha = st.radio(f"q_{i}", options=q["alternativas"], index=None, key=f"sim_q_{i}", label_visibility="collapsed")
                if escolha:
                    respostas[i] = escolha[0].upper()
                st.divider()
            c1,c2 = st.columns(2)
            salvar = c1.form_submit_button("💾 Salvar Progresso", use_container_width=True)
            finalizar = c2.form_submit_button("✅ Finalizar Prova", type="primary", use_container_width=True)
            if salvar:
                sim["respostas"] = respostas
                st.success("Progresso salvo!")
                st.rerun()
            if finalizar:
                acertos=0
                detalhes=[]
                for i,q in enumerate(questoes):
                    r = respostas.get(i,"")
                    correta = q["correta"].upper()
                    ok = r == correta
                    if ok: acertos+=1
                    detalhes.append({"pergunta": q["pergunta"], "materia": q.get("materia",""), "resposta": r, "correta": correta, "acertou": ok})
                nota = (acertos/len(questoes))*100 if questoes else 0
                st.session_state.historico.append({
                    "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "acertos": acertos, "total": len(questoes),
                    "nota": round(nota,2), "aprovado": nota>=50,
                    "detalhes": detalhes, "tempo": time.time()-sim["inicio"]
                })
                sim["finalizado"]=True
                st.rerun()
    else:
        ultimo = st.session_state.historico[-1] if st.session_state.historico else None
        if ultimo:
            st.balloons()
            st.subheader("📊 Resultado Oficial - Banca AOCP")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Nota", f"{ultimo['nota']}%")
            c2.metric("Acertos", f"{ultimo['acertos']}/{ultimo['total']}")
            c3.metric("Status", "✅ APROVADO" if ultimo["aprovado"] else "❌ REPROVADO")
            c4.metric("Tempo", f"{int(ultimo['tempo']//60)} min")
            
            # Por matéria
            from collections import Counter
            acertos_mat = Counter()
            total_mat = Counter()
            for d in ultimo["detalhes"]:
                total_mat[d["materia"]]+=1
                if d["acertou"]:
                    acertos_mat[d["materia"]]+=1
            st.subheader("📚 Desempenho por Matéria (Edital AOCP)")
            for mat in DISTRIBUICAO.keys():
                if total_mat[mat]>0:
                    st.progress(acertos_mat[mat]/total_mat[mat], text=f"{mat}: {acertos_mat[mat]}/{total_mat[mat]}")
            
            with st.expander("Gabarito detalhado"):
                for i,d in enumerate(ultimo["detalhes"]):
                    icon="✅" if d["acertou"] else "❌"
                    st.markdown(f"{icon} **{i+1}. [{d['materia']}]** {d['pergunta']}")
                    st.caption(f"Sua: {d['resposta'] or '—'} | Gabarito: {d['correta']}")
                    st.divider()
        if st.button("🔄 Novo Simulado", type="primary"):
            st.session_state.simulado=None
            st.rerun()

elif st.session_state.treino:
    st.subheader(f"🌐 Treino 3D - {st.session_state.treino[0].get('materia','')}")
    render_3d_quest(st.session_state.treino, modo="TREINO")
    st.divider()
    for i,q in enumerate(st.session_state.treino):
        with st.expander(f"Questão {i+1} - {q.get('materia','')}"):
            st.markdown(q["pergunta"])
            for alt in q["alternativas"]:
                st.markdown(f"- {alt}")
            st.success(f"Gabarito: **{q['correta']}**")
    if st.button("Encerrar Treino"):
        st.session_state.treino=[]
        st.rerun()

else:
    st.info("👈 Na barra lateral: gere **Treino 3D** ou **Simulado Oficial PMSC 2026**")
    st.markdown(f"""
    ### 📋 Simulador conforme Edital PMSC 2026 - AOCP
    - **Banca:** Instituto AOCP
    - **Prova:** 60 questões objetivas (A-E) + Redação
    - **Duração:** 4 horas
    - **Aprovação:** 50% da prova
    - **Banco:** seu `json.json` com **{sum(len(v) for v in banco.values())} questões**
    - **Imersivo:** WebXR, hand-tracking, blocos arrastáveis no Meta Quest 3S
    - **Compatível:** Quest Browser, Quest 3 / 3S / 2 / Pro

    #### 📊 Distribuição Oficial
    {chr(10).join([f"- **{m}:** {q} questões" for m,q in DISTRIBUICAO.items()])}

    #### 🥽 Como usar no Meta Quest 3S
    1. Conecte o Quest 3S na mesma rede
    2. Abra o link do Streamlit no **Meta Browser**
    3. Clique em **ENTRAR EM VR**
    4. Use **pinch** para mover blocos, **laser** para responder
    5. Ambiente com chão infinito e 40m² de área útil

    #### 🚀 Deploy
    ```bash
    pip install -r requirements.txt
    streamlit run app.py
    ```
    """)

if st.session_state.historico:
    with st.sidebar:
        st.divider()
        st.subheader("📜 Histórico")
        for h in reversed(st.session_state.historico[-5:]):
            st.caption(f"{h['data']} – {h['acertos']}/{h['total']} ({h['nota']}%)")
