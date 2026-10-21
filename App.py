import streamlit as st
import streamlit.components.v1 as components
import json
import random
import pathlib
import time
from datetime import datetime
from collections import defaultdict

st.set_page_config(page_title="PMSC 2026 - Quest 3S Grab Livre",
                   page_icon="🎯", layout="wide")

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


def _parse_concatenado(conteudo: str) -> dict:
    decoder = json.JSONDecoder()
    idx, n = 0, len(conteudo)
    resultado = {}
    while idx < n:
        while idx < n and conteudo[idx].isspace():
            idx += 1
        if idx >= n:
            break
        try:
            obj, idx = decoder.raw_decode(conteudo, idx)
        except json.JSONDecodeError:
            break
        if isinstance(obj, dict):
            for materia, lista in obj.items():
                if isinstance(lista, list):
                    resultado.setdefault(materia, []).extend(lista)
        elif isinstance(obj, list):
            for q in obj:
                resultado.setdefault(q.get("materia", "Geral"), []).append(q)
    return resultado


def _deduplicar(lista):
    vistos, unicas, removidas = set(), [], 0
    for q in lista:
        t = q.get("pergunta", "").strip().lower()
        if not t:
            continue
        if t in vistos:
            removidas += 1
            continue
        vistos.add(t)
        unicas.append(q)
    return unicas, removidas


@st.cache_data(ttl=30, show_spinner=False)
def load_banco():
    base = pathlib.Path(__file__).parent
    cands = list(base.glob("*.json")) or list(pathlib.Path.cwd().glob("*.json"))
    resultado = defaultdict(list)
    total_bruto, removidas, arquivos_ok = 0, 0, 0
    for p in cands:
        try:
            with open(p, "r", encoding="utf-8") as jf:
                conteudo = jf.read()
        except Exception:
            continue
        parsed = _parse_concatenado(conteudo)
        if not parsed:
            continue
        for k, v in parsed.items():
            resultado[k].extend(v)
        total_bruto += sum(len(v) for v in parsed.values())
        arquivos_ok += 1
    if not resultado:
        return None, None
    for k in list(resultado.keys()):
        unicas, rem = _deduplicar(resultado[k])
        resultado[k] = unicas
        removidas += rem
    info = {
        "arquivos": arquivos_ok, "bruto": total_bruto,
        "removidas": removidas, "unicas": sum(len(v) for v in resultado.values()),
    }
    return dict(resultado), info


def montar_simulado(banco):
    sim = []
    for mat, qtd in DISTRIBUICAO.items():
        pool = banco.get(mat, [])
        if not pool:
            for k, v in banco.items():
                if mat.lower() in k.lower() or k.lower() in mat.lower():
                    pool = v
                    break
        if pool:
            selecionadas = random.sample(pool, min(qtd, len(pool)))
            sim.extend([{**q, "materia": mat} for q in selecionadas])
    random.shuffle(sim)
    return sim


for k, default in [("simulado", None), ("treino", []), ("hist", [])]:
    if k not in st.session_state:
        st.session_state[k] = default

banco, info = load_banco()

if not banco:
    st.error("❌ Nenhum .json válido encontrado na raiz.")
    try:
        arquivos = [f.name for f in pathlib.Path(__file__).parent.iterdir()]
        st.write("Arquivos encontrados:", arquivos)
    except Exception:
        pass
    st.stop()

st.title("🎯 PMSC 3D — Grab Livre no VR")
st.caption(
    f"✅ {info['unicas']} questões únicas · Meta Quest 3S · "
    f"Grip = agarrar · Trigger = responder"
)

with st.sidebar:
    st.success(f"📚 {info['unicas']}q únicas · {info['bruto']}q brutas")
    if info["removidas"]:
        st.caption(f"🧹 {info['removidas']} duplicata(s)")
    if st.button("🔄 Recarregar banco", use_container_width=True):
        load_banco.clear()
        st.rerun()
    st.divider()
    mat = st.selectbox("Matéria", list(banco.keys()))
    qtd = st.slider("Qtd", 5, 20, 10)
    if st.button("📚 Treino", use_container_width=True):
        pool = banco.get(mat, [])
        st.session_state.treino = [
            {**q, "materia": mat}
            for q in random.sample(pool, min(qtd, len(pool)))
        ]
        st.session_state.simulado = None
        st.rerun()
    st.divider()
    if st.button("📝 Simulado 60q", type="primary", use_container_width=True):
        st.session_state.simulado = {
            "questoes": montar_simulado(banco),
            "inicio": time.time(),
            "respostas": {},
            "finalizado": False,
        }
        st.session_state.treino = []
        st.rerun()
    if st.session_state.simulado and not st.session_state.simulado["finalizado"]:
        if st.button("❌ Cancelar simulado", use_container_width=True):
            st.session_state.simulado = None
            st.rerun()


# ==================================================================
# RENDERIZADOR VR — GRAB LIVRE MELHORADO
# ==================================================================
def render_vr_tudo_movel(questoes, modo="ARENA", height=950):
    key = f"vr_{modo}"
    if not st.session_state.get(key, False):
        st.info(f"{len(questoes)} questões prontas. Clique para carregar o VR.")
        if st.button(
            f"🥽 CARREGAR VR — {modo} ({min(len(questoes),18)} blocos)",
            key=f"btn_{key}", type="primary", use_container_width=True
        ):
            st.session_state[key] = True
            st.rerun()
        return

    amostra = questoes[:18]
    safe = []
    for q in amostra:
        safe.append({
            "pergunta": q["pergunta"][:190].replace('"', "'").replace("\n", " "),
            "alternativas": [a[:62].replace('"', "'") for a in q["alternativas"][:5]],
            "correta": q["correta"].upper(),
            "materia": q.get("materia", "Geral")[:22],
        })
    q_json = json.dumps(safe, ensure_ascii=False).replace("</", "<\\/")

    html_template = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v7.4.0/dist/aframe-extras.min.js"></script>
<script src="https://unpkg.com/super-hands@3.0.5/dist/super-hands.min.js"></script>
<script>
// ==================================================================
// COMPONENTE: TUDO MOVÍVEL + ROTAÇÃO + FEEDBACK
// ==================================================================
AFRAME.registerComponent('tudo-movel', {
  init: function() {
    const el = this.el;
    el.setAttribute('hoverable', '');
    el.setAttribute('grabbable', '');
    el.setAttribute('draggable', '');
    el.setAttribute('stretchable', '');
    el.setAttribute('droppable', '');

    // Guarda a escala original da box filha para feedback
    let origColor = '#13244a';

    el.addEventListener('grab-start', (evt) => {
      // Feedback: cresce e ilumina
      el.object3D.scale.set(1.08, 1.08, 1.08);
      const box = el.querySelector('a-box');
      if (box) {
        origColor = box.getAttribute('material').color || '#13244a';
        box.setAttribute('material', 'emissive', '#ffaa00');
        box.setAttribute('material', 'emissiveIntensity', 0.8);
      }
      // Guarda a mão que agarrou para rotação
      if (evt.detail && evt.detail.hand) {
        el.sceneEl.emit('block-grabbed', { block: el, hand: evt.detail.hand });
      }
      console.log('[GRAB-START]', el.id);
      showToast('✋ Segurando ' + el.id);
    });

    el.addEventListener('grab-end', () => {
      // Volta ao normal
      el.object3D.scale.set(1, 1, 1);
      const box = el.querySelector('a-box');
      if (box) {
        box.setAttribute('material', 'emissive', '#000000');
        box.setAttribute('material', 'emissiveIntensity', 0);
      }
      el.sceneEl.emit('block-released', { block: el });
      // Salva posição após o frame atualizar
      setTimeout(() => {
        saveBlockPosition(el.id);
        showToast('📍 ' + el.id + ' posicionado');
      }, 80);
      console.log('[GRAB-END]', el.id, el.getAttribute('position'));
    });

    el.addEventListener('stretch-start', () => {
      el.object3D.scale.set(1.15, 1.15, 1.15);
    });
    el.addEventListener('stretch-end', () => {
      el.object3D.scale.set(1, 1, 1);
    });
  }
});

// ==================================================================
// COMPONENTE: ROTAÇÃO COM THUMBSTICK ENQUANTO AGARRA
// ==================================================================
AFRAME.registerComponent('grab-rotator', {
  init: function() {
    const hand = this.el;
    let grabbedBlock = null;

    hand.sceneEl.addEventListener('block-grabbed', (evt) => {
      grabbedBlock = evt.detail.block;
    });
    hand.sceneEl.addEventListener('block-released', () => {
      grabbedBlock = null;
    });

    // Thumbstick nos controles
    hand.addEventListener('thumbstickmoved', (evt) => {
      if (!grabbedBlock) return;
      const x = evt.detail.x;
      const y = evt.detail.y;
      if (Math.abs(x) > 0.15) grabbedBlock.object3D.rotation.y += x * 0.04;
      if (Math.abs(y) > 0.15) grabbedBlock.object3D.rotation.x += y * 0.04;
    });

    // Axismove (fallback para hand tracking)
    hand.addEventListener('axismove', (evt) => {
      if (!grabbedBlock) return;
      const axes = evt.detail.axis;
      if (axes && axes.length >= 2) {
        const x = axes[0], y = axes[1];
        if (Math.abs(x) > 0.15) grabbedBlock.object3D.rotation.y += x * 0.04;
        if (Math.abs(y) > 0.15) grabbedBlock.object3D.rotation.x += y * 0.04;
      }
    });
  }
});

// ==================================================================
// CALIBRADOR DE MÃOS AO VIVO
// ==================================================================
AFRAME.registerComponent('hand-calibrator-live', {
  schema: { hand: {type: 'string', default: 'left'} },
  init: function() {
    this.pinch = 0;
    this.grip = false;
    this.el.addEventListener('pinchstarted', () => this.pinch = 1);
    this.el.addEventListener('pinchended',   () => this.pinch = 0);
    this.el.addEventListener('gripdown',     () => this.grip = true);
    this.el.addEventListener('gripup',       () => this.grip = false);
  },
  tick: function() {
    const id = this.data.hand === 'left' ? 'leftHandData' : 'rightHandData';
    const tEl = document.getElementById(id);
    if (!tEl) return;
    const p = this.el.object3D.position;
    const tracking = this.el.components['hand-tracking-controls'] ? 'TRACK' : 'CTRL';
    tEl.setAttribute('value',
      this.data.hand.toUpperCase() + ': ' + tracking +
      ' | ' + (this.pinch ? '🤏' : '✋') + (this.grip ? ' 👊' : '') +
      '\nPos ' + p.x.toFixed(2) + ' ' + p.y.toFixed(2) + ' ' + p.z.toFixed(2)
    );
  }
});

// ==================================================================
// SISTEMA DE CALIBRAÇÃO + AMBIENTES
// ==================================================================
AFRAME.registerComponent('calibration-system', {
  init: function() {
    const rig = document.getElementById('rig');
    const head = document.getElementById('head');
    const left = document.getElementById('leftHand');
    const right = document.getElementById('rightHand');
    let handScale = 1;
    let headH = 1.65;

    this.el.querySelectorAll('.calib-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const a = btn.getAttribute('data-action');
        if (a === 'resetPos')   rig.setAttribute('position', '0 0 8');
        if (a === 'resetRot')   rig.setAttribute('rotation', '0 0 0');
        if (a === 'handUp') {
          handScale += 0.1;
          const s = handScale + ' ' + handScale + ' ' + handScale;
          left.setAttribute('scale', s);
          right.setAttribute('scale', s);
        }
        if (a === 'handDown') {
          handScale = Math.max(0.2, handScale - 0.1);
          const s = handScale + ' ' + handScale + ' ' + handScale;
          left.setAttribute('scale', s);
          right.setAttribute('scale', s);
        }
        if (a === 'heightUp')  { headH += 0.1; head.setAttribute('position', '0 ' + headH + ' 0'); }
        if (a === 'heightDown'){ headH = Math.max(0.4, headH - 0.1); head.setAttribute('position', '0 ' + headH + ' 0'); }
        if (a === 'resetArena') window.initWorld();
        if (a === 'organize')      window.organizeBlocks();
        if (a === 'organizeByMat') window.organizeBySubject();
        if (a === 'scatter')       window.scatterBlocks();
        if (a === 'saveLayout')    window.saveLayout();
        if (a === 'loadLayout')    window.loadLayout();
        if (a === 'passthrough')   window.setBackground('passthrough');
        if (a === 'dark')          window.setBackground('dark');
        if (a === 'beach')         window.setBackground('beach');
        if (a === 'space')         window.setBackground('space');
        if (a === 'exitVR') {
          const sess = document.querySelector('a-scene').renderer.xr.getSession();
          if (sess) sess.end();
        }
        const orig = btn.getAttribute('material').color;
        btn.setAttribute('material', 'color', '#00ff88');
        setTimeout(() => btn.setAttribute('material', 'color', orig), 200);
      });
    });
  }
});
</script>
<style>
html, body { margin:0; padding:0; width:100%; height:__HEIGHT__px; overflow:hidden; background:#050a14; }
#hud { position:fixed; top:8px; left:8px; z-index:99999;
  background:rgba(0,0,0,0.92); color:#00e5ff; border:1px solid #00e5ff;
  padding:10px 14px; border-radius:10px; font-size:12px; max-width:380px; }
#enter { position:fixed; bottom:12px; left:50%; transform:translateX(-50%); z-index:99999;
  background:linear-gradient(90deg,#00d1ff,#7000ff); color:white; border:none;
  padding:14px 32px; border-radius:999px; font-weight:900; font-size:15px; cursor:pointer; }
#toast { position:fixed; bottom:80px; left:50%; transform:translateX(-50%); z-index:999999;
  background:rgba(0,0,0,0.95); color:#00ff88; border:2px solid #00ff88;
  padding:10px 22px; border-radius:10px; font-size:14px; font-weight:700;
  display:none; pointer-events:none; }
</style>
</head>
<body>
<div id="hud">
  <div style="font-weight:900;color:white;font-size:14px;">__MODO__ — GRAB LIVRE</div>
  <b>Grip</b> = agarrar · <b>Trigger</b> = responder · <b>Thumbstick</b> = rotacionar<br>
  <div id="status" style="margin-top:6px;color:#00ff88;font-weight:700;">0/__LEN__ respondidas</div>
</div>
<button id="enter">🥽 ENTRAR VR</button>
<div id="toast"></div>

<a-scene id="scene"
  background="color: #050a14"
  renderer="antialias:true; colorManagement:true; alpha:true"
  webxr="optionalFeatures: hand-tracking, local-floor, bounded-floor, hit-test, passthrough"
  vr-mode-ui="enabled:true" embedded
  style="width:100%;height:__HEIGHT__px;">

  <a-sky id="sky" color="#050a14"></a-sky>
  <a-entity id="stars" visible="false"></a-entity>
  <a-entity light="type:ambient; intensity:0.9"></a-entity>
  <a-entity light="type:directional; intensity:1.1" position="4 7 4"></a-entity>
  <a-plane rotation="-90 0 0" width="120" height="120" color="#0a1430" opacity="0.6"></a-plane>

  <a-entity id="rig" position="0 0 8" movement-controls="fly:true; speed:0.3">
    <a-entity id="head" camera look-controls wasd-controls="acceleration:20" position="0 1.65 0">
      <a-entity cursor="rayOrigin: mouse" raycaster="objects: .clickable, .ui" visible="false"></a-entity>
      <a-entity position="0 -0.6 -1.1">
        <a-plane width="1.1" height="0.32" color="black" opacity="0.7"></a-plane>
        <a-text id="hudVRText" value="0/18" color="#00ff88" width="1.9" align="center" position="0 0 0.01"></a-text>
      </a-entity>
    </a-entity>

    <!-- MÃO ESQUERDA — GRAB via grip/pinch -->
    <a-entity id="leftHand"
      hand-controls="hand: left; handModelStyle: lowPoly; color:#00d1ff"
      hand-tracking-controls="hand: left"
      hand-calibrator-live="hand: left"
      grab-rotator
      laser-controls="hand: left"
      raycaster="objects: .grabbable, .clickable, .ui; far: 30"
      line="color:#00d1ff; opacity:0.9"
      super-hands="colliderEvent: raycaster-intersection; colliderEventProperty: els; colliderEndEvent: raycaster-intersection-cleared; colliderEndEventProperty: clearedEls; grabStartButtons: gripdown, pinchstarted; grabEndButtons: gripup, pinchended"
      sphere-collider="objects: .grabbable; radius:0.30">
    </a-entity>

    <!-- MÃO DIREITA — GRAB via grip/pinch -->
    <a-entity id="rightHand"
      hand-controls="hand: right; handModelStyle: lowPoly; color:#ff8a00"
      hand-tracking-controls="hand: right"
      hand-calibrator-live="hand: right"
      grab-rotator
      laser-controls="hand: right"
      raycaster="objects: .grabbable, .clickable, .ui; far: 30"
      line="color:#ff8a00; opacity:0.9"
      super-hands="colliderEvent: raycaster-intersection; colliderEventProperty: els; colliderEndEvent: raycaster-intersection-cleared; colliderEndEventProperty: clearedEls; grabStartButtons: gripdown, pinchstarted; grabEndButtons: gripup, pinchended"
      sphere-collider="objects: .grabbable; radius:0.30">
    </a-entity>
  </a-entity>

  <!-- ========== PAINEL PRINCIPAL ========== -->
  <a-entity id="mainPanel" position="0 2.2 -3.0" tudo-movel calibration-system
            hoverable grabbable draggable class="grabbable">
    <a-box width="4.0" height="2.2" depth="0.06" color="#0a0a0a" opacity="0.94" class="grabbable"></a-box>
    <a-text value="GRAB LIVRE + AMBIENTES" color="#00e5ff" width="4.5" align="center" position="0 0.95 0.05" class="grabbable"></a-text>

    <a-text value="AMBIENTE:" color="#00ff88" width="1.2" align="left" position="-1.9 0.65 0.05" class="grabbable"></a-text>
    <a-entity class="calib-btn clickable" data-action="passthrough" position="-0.8 0.65 0.05" geometry="primitive: plane; width:0.85; height:0.22" material="color:#7a1fa2"><a-text value="PASSTHROUGH" color="white" width="0.95" align="center" position="0 0 0.01"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="dark"   position="0.15 0.65 0.05" geometry="primitive: plane; width:0.6; height:0.22" material="color:#1a3a6a"><a-text value="ESCURO" color="white" width="0.7" align="center" position="0 0 0.01"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="beach"  position="0.9 0.65 0.05"  geometry="primitive: plane; width:0.6; height:0.22" material="color:#1a5a6a"><a-text value="PRAIA" color="white" width="0.7" align="center" position="0 0 0.01"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="space"  position="1.65 0.65 0.05" geometry="primitive: plane; width:0.6; height:0.22" material="color:#2a0a5a"><a-text value="ESPAÇO" color="white" width="0.7" align="center" position="0 0 0.01"></a-text></a-entity>

    <a-text value="ORGANIZAR:" color="#00ff88" width="1.2" align="left" position="-1.9 0.35 0.05" class="grabbable"></a-text>
    <a-entity class="calib-btn clickable" data-action="organize"      position="-1.0 0.35 0.05" geometry="primitive: plane; width:0.6; height:0.22" material="color:#1a3a6a"><a-text value="GRADE" color="white" width="0.7" align="center" position="0 0 0.01"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="organizeByMat" position="-0.2 0.35 0.05" geometry="primitive: plane; width:0.85; height:0.22" material="color:#1a6a3a"><a-text value="POR MATÉRIA" color="white" width="0.9" align="center" position="0 0 0.01"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="scatter"       position="0.65 0.35 0.05" geometry="primitive: plane; width:0.7; height:0.22" material="color:#6a1a1a"><a-text value="ESPALHAR" color="white" width="0.8" align="center" position="0 0 0.01"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="saveLayout"    position="1.5 0.35 0.05" geometry="primitive: plane; width:0.6; height:0.22" material="color:#00aa44"><a-text value="SALVAR" color="white" width="0.7" align="center" position="0 0 0.01"></a-text></a-entity>

    <a-text value="LAYOUT:" color="#00ff88" width="1.2" align="left" position="-1.9 0.05 0.05" class="grabbable"></a-text>
    <a-entity class="calib-btn clickable" data-action="loadLayout" position="-1.0 0.05 0.05" geometry="primitive: plane; width:0.6; height:0.22" material="color:#aa8800"><a-text value="CARREGAR" color="white" width="0.7" align="center" position="0 0 0.01"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="resetArena" position="-0.2 0.05 0.05" geometry="primitive: plane; width:0.6; height:0.22" material="color:#1a3a6a"><a-text value="RESET" color="white" width="0.7" align="center" position="0 0 0.01"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="exitVR"     position="0.65 0.05 0.05" geometry="primitive: plane; width:0.6; height:0.22" material="color:#a00000"><a-text value="SAIR VR" color="white" width="0.7" align="center" position="0 0 0.01"></a-text></a-entity>

    <a-text value="CALIBRAR:" color="#00ff88" width="1.2" align="left" position="-1.9 -0.25 0.05" class="grabbable"></a-text>
    <a-entity class="calib-btn clickable" data-action="handUp"     position="-1.1 -0.25 0.05" geometry="primitive: plane; width:0.55; height:0.22" material="color:#2a5a1a"><a-text value="MÃO +" color="white" width="0.6" align="center" position="0 0 0.01"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="handDown"   position="-0.45 -0.25 0.05" geometry="primitive: plane; width:0.55; height:0.22" material="color:#2a5a1a"><a-text value="MÃO -" color="white" width="0.6" align="center" position="0 0 0.01"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="heightUp"   position="0.25 -0.25 0.05" geometry="primitive: plane; width:0.6; height:0.22" material="color:#1a3a6a"><a-text value="ALT +" color="white" width="0.7" align="center" position="0 0 0.01"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="heightDown" position="0.95 -0.25 0.05" geometry="primitive: plane; width:0.6; height:0.22" material="color:#1a3a6a"><a-text value="ALT -" color="white" width="0.7" align="center" position="0 0 0.01"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="resetPos"   position="1.65 -0.25 0.05" geometry="primitive: plane; width:0.6; height:0.22" material="color:#1a3a6a"><a-text value="RESET POS" color="white" width="0.7" align="center" position="0 0 0.01"></a-text></a-entity>

    <a-text value="🖐️ Grip/pinch = pegar · ⚡ Trigger = responder · 🕹️ Thumbstick = rotacionar"
            color="#ffaa00" width="3.9" align="center" position="0 -0.85 0.05" class="grabbable"></a-text>
  </a-entity>

  <!-- PAINEL CALIBRADOR DE MÃOS (movível) -->
  <a-entity id="handCalibDisplay" position="3.2 2.2 -3.0" tudo-movel hoverable grabbable draggable>
    <a-box width="1.8" height="1.4" depth="0.06" color="#111111" opacity="0.92" class="grabbable"></a-box>
    <a-text value="MÃOS AO VIVO" color="#00ff88" width="2.4" align="center" position="0 0.55 0.05" class="grabbable"></a-text>
    <a-text id="leftHandData"  value="LEFT: aguardando"  color="#00d1ff" width="1.9" align="left" position="-0.75 0.15 0.05" wrap-count="34" class="grabbable"></a-text>
    <a-text id="rightHandData" value="RIGHT: aguardando" color="#ff8a00" width="1.9" align="left" position="-0.75 -0.35 0.05" wrap-count="34" class="grabbable"></a-text>
  </a-entity>

  <a-entity id="world"></a-entity>
</a-scene>

<script>
const QUESTIONS = __Q_JSON__;
let answers = {};
let blocks = [];

function updateHUD() {
  const n = Object.keys(answers).length;
  const txt = n + '/' + QUESTIONS.length;
  document.getElementById('status').textContent = txt + ' respondidas';
  const vrHud = document.getElementById('hudVRText');
  if (vrHud) vrHud.setAttribute('value', txt);
}

function showToast(msg, ms) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  clearTimeout(window._toastT);
  window._toastT = setTimeout(() => { t.style.display = 'none'; }, ms || 1600);
}

// ============ AMBIENTES ============
window.setBackground = function(mode) {
  const sky = document.getElementById('sky');
  const stars = document.getElementById('stars');
  if (mode === 'passthrough') { window.enablePassthrough(); return; }
  stars.setAttribute('visible', 'false');
  sky.setAttribute('visible', 'true');
  if (mode === 'dark') {
    sky.setAttribute('color', '#050a14');
    sky.removeAttribute('src');
  } else if (mode === 'beach') {
    sky.setAttribute('src', 'url(https://cdn.aframe.io/360-image-gallery-boilerplate/img/sechelt.jpg)');
    sky.removeAttribute('color');
  } else if (mode === 'space') {
    sky.setAttribute('color', '#000005');
    sky.removeAttribute('src');
    createStars();
    stars.setAttribute('visible', 'true');
  }
  showToast('🌍 ' + mode.toUpperCase());
};

window.enablePassthrough = async function() {
  if (!navigator.xr) { showToast('❌ WebXR não suportado'); return; }
  try {
    const supported = await navigator.xr.isSessionSupported('immersive-ar');
    if (!supported) { showToast('❌ Use o Meta Quest Browser no headset', 4000); return; }
    const sceneEl = document.querySelector('a-scene');
    const renderer = sceneEl.renderer;
    const current = renderer.xr.getSession();
    if (current) { await current.end(); await new Promise(r => setTimeout(r, 400)); }
    document.getElementById('sky').setAttribute('visible', 'false');
    document.getElementById('stars').setAttribute('visible', 'false');
    sceneEl.object3D.background = null;
    renderer.setClearColor(0x000000, 0);
    const session = await navigator.xr.requestSession('immersive-ar', {
      requiredFeatures: ['local-floor'],
      optionalFeatures: ['passthrough', 'hand-tracking', 'hit-test', 'bounded-floor', 'anchors']
    });
    await renderer.xr.setSession(session);
    session.addEventListener('end', () => {
      sceneEl.object3D.background = new THREE.Color(0x050a14);
      renderer.setClearColor(0x050a14, 1);
      document.getElementById('sky').setAttribute('visible', 'true');
      showToast('Saiu do passthrough');
    });
    showToast('👁️ PASSTHROUGH ATIVO');
  } catch (err) {
    showToast('❌ ' + err.message, 4000);
  }
};

function createStars() {
  const c = document.getElementById('stars');
  c.innerHTML = '';
  for (let i = 0; i < 400; i++) {
    const s = document.createElement('a-sphere');
    const r = 25 + Math.random() * 15;
    const t = Math.random() * Math.PI * 2;
    const p = Math.acos(2 * Math.random() - 1);
    s.setAttribute('position', {
      x: r * Math.sin(p) * Math.cos(t),
      y: r * Math.sin(p) * Math.sin(t),
      z: r * Math.cos(p)
    });
    s.setAttribute('radius', 0.03 + Math.random() * 0.08);
    s.setAttribute('color', '#ffffff');
    s.setAttribute('material', 'shader: flat; opacity: 0.9');
    c.appendChild(s);
  }
}

// ============ CRIAR BLOCO (todos os filhos grabbable) ============
function createBlock(q, i) {
  const cols = 4, spacing = 3.0;
  const x = (i % cols) * spacing - ((cols - 1) * spacing / 2);
  const z = Math.floor(i / cols) * -3.4 - 1.5;
  const y = 1.2 + Math.random() * 0.5;

  const root = document.createElement('a-entity');
  root.setAttribute('id', 'block-' + i);
  root.setAttribute('position', x + ' ' + y + ' ' + z);
  root.setAttribute('class', 'grabbable');
  root.setAttribute('data-materia', q.materia || 'Geral');
  root.setAttribute('tudo-movel', '');

  const box = document.createElement('a-box');
  box.setAttribute('width', '2.4');
  box.setAttribute('height', '2.2');
  box.setAttribute('depth', '0.24');
  box.setAttribute('color', '#13244a');
  box.setAttribute('class', 'grabbable');
  box.setAttribute('material', 'emissive: #000000; emissiveIntensity: 0');

  const title = document.createElement('a-text');
  title.setAttribute('value', (i + 1) + '. ' + q.materia);
  title.setAttribute('color', '#00e5ff');
  title.setAttribute('width', '2.3');
  title.setAttribute('align', 'center');
  title.setAttribute('position', '0 0.85 0.14');
  title.setAttribute('class', 'grabbable');

  const qtext = document.createElement('a-text');
  const shortQ = q.pergunta.length > 150 ? q.pergunta.slice(0, 147) + '...' : q.pergunta;
  qtext.setAttribute('value', shortQ);
  qtext.setAttribute('color', 'white');
  qtext.setAttribute('width', '2.2');
  qtext.setAttribute('align', 'center');
  qtext.setAttribute('position', '0 0.45 0.14');
  qtext.setAttribute('wrap-count', '36');
  qtext.setAttribute('class', 'grabbable');

  root.appendChild(box);
  root.appendChild(title);
  root.appendChild(qtext);

  // Alternativas — CLICÁVEIS mas NÃO grabbable (não roubam o grab)
  q.alternativas.forEach((alt, idx) => {
    const letra = alt.trim().charAt(0).toUpperCase();
    const row = document.createElement('a-entity');
    row.setAttribute('position', '0 ' + (-0.05 - idx * 0.28) + ' 0.15');
    row.setAttribute('class', 'clickable');
    row.setAttribute('data-i', i);

    const bg = document.createElement('a-plane');
    bg.setAttribute('width', '2.0');
    bg.setAttribute('height', '0.22');
    bg.setAttribute('color', '#0a1933');
    bg.setAttribute('class', 'clickable');

    const txt = document.createElement('a-text');
    txt.setAttribute('value', alt.length > 60 ? alt.slice(0, 57) + '...' : alt);
    txt.setAttribute('color', '#cfe0ff');
    txt.setAttribute('width', '1.9');
    txt.setAttribute('position', '-0.95 0 0.01');
    txt.setAttribute('class', 'clickable');

    bg.appendChild(txt);
    row.appendChild(bg);

    row.addEventListener('click', (e) => {
      e.stopPropagation();
      answers[i] = letra;
      document.querySelectorAll('[data-i="' + i + '"] a-plane')
        .forEach(p => p.setAttribute('color', '#0a1933'));
      bg.setAttribute('color', letra === q.correta ? '#00c853' : '#d50000');
      if (navigator.vibrate) navigator.vibrate(letra === q.correta ? 40 : 90);
      updateHUD();
    });

    root.appendChild(row);
  });

  blocks.push(root);
  return root;
}

// ============ SAVE/LOAD ============
const STORAGE_KEY = 'pmsc_layout_grab_v3';

function saveBlockPosition(blockId) {
  const el = document.getElementById(blockId);
  if (!el) return;
  try {
    const layouts = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    layouts[blockId] = {
      p: el.getAttribute('position'),
      r: el.getAttribute('rotation') || {x:0,y:0,z:0},
      s: el.getAttribute('scale') || {x:1,y:1,z:1}
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(layouts));
    console.log('[SAVE]', blockId, layouts[blockId].p);
  } catch (err) { console.warn(err); }
}

window.saveLayout = function() {
  try {
    const layout = {};
    document.querySelectorAll('[id^="block-"]').forEach(el => {
      layout[el.id] = {
        p: el.getAttribute('position'),
        r: el.getAttribute('rotation') || {x:0,y:0,z:0},
        s: el.getAttribute('scale') || {x:1,y:1,z:1}
      };
    });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
    showToast('💾 Salvo! ' + Object.keys(layout).length + ' blocos');
  } catch (err) { showToast('❌ ' + err.message); }
};

window.loadLayout = function() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) { showToast('⚠️ Nada salvo ainda'); return; }
    const layout = JSON.parse(saved);
    let count = 0;
    Object.entries(layout).forEach(([id, data]) => {
      const el = document.getElementById(id);
      if (el) {
        el.setAttribute('position', data.p);
        el.setAttribute('rotation', data.r);
        el.setAttribute('scale', data.s);
        count++;
      }
    });
    showToast('📂 ' + count + ' blocos restaurados');
  } catch (err) { showToast('❌ ' + err.message); }
};

// ============ ORGANIZAÇÃO ============
window.organizeBlocks = function() {
  blocks.forEach((b, i) => {
    const cols = 4, spacing = 3.0;
    const x = (i % cols) * spacing - ((cols - 1) * spacing / 2);
    const z = Math.floor(i / cols) * -3.4 - 1.5;
    const y = 1.2 + (i % 3) * 0.2;
    b.setAttribute('animation', 'property: position; to: ' + x + ' ' + y + ' ' + z + '; dur: 800');
  });
  showToast('📐 GRADE');
};

window.organizeBySubject = function() {
  const by = {};
  blocks.forEach(b => {
    const m = b.getAttribute('data-materia') || 'Geral';
    if (!by[m]) by[m] = [];
    by[m].push(b);
  });
  const names = Object.keys(by);
  names.forEach((mat, s) => {
    const cluster = by[mat];
    const baseX = (s - (names.length - 1) / 2) * 8;
    cluster.forEach((b, i) => {
      const col = i % 2;
      const row = Math.floor(i / 2);
      const x = baseX + (col - 0.5) * 2.8;
      const z = -3 - row * 2.8;
      b.setAttribute('animation', 'property: position; to: ' + x + ' 1.5 ' + z + '; dur: 900');
    });
  });
  showToast('🎯 POR MATÉRIA (' + names.length + ')');
};

window.scatterBlocks = function() {
  blocks.forEach(b => {
    const x = (Math.random() - 0.5) * 14;
    const z = (Math.random() - 0.5) * 14 - 2;
    const y = 0.8 + Math.random() * 2.5;
    b.setAttribute('animation', 'property: position; to: ' + x + ' ' + y + ' ' + z + '; dur: 800');
  });
  showToast('🎲 ESPALHADO');
};

window.initWorld = function() {
  const world = document.getElementById('world');
  world.innerHTML = '';
  blocks = [];
  QUESTIONS.forEach((q, i) => world.appendChild(createBlock(q, i)));
  updateHUD();
};

document.addEventListener('DOMContentLoaded', () => window.initWorld());
document.getElementById('enter').addEventListener('click', () => {
  document.querySelector('a-scene').enterVR().catch(e => showToast('❌ ' + e.message));
});
</script>
</body>
</html>
"""

    html = (html_template
            .replace("__Q_JSON__", q_json)
            .replace("__MODO__", modo)
            .replace("__LEN__", str(len(safe)))
            .replace("__HEIGHT__", str(height)))

    components.html(html, height=height, scrolling=False)

    if st.button(f"❌ Fechar VR — {modo}", key=f"close_{modo}", use_container_width=True):
        st.session_state[key] = False
        st.rerun()


# ==================================================================
# TABS
# ==================================================================
tab1, tab2, tab3 = st.tabs(["🥽 GRAB LIVRE", "📝 SIMULADO", "📚 TREINO"])

with tab1:
    todas = []
    for v in banco.values():
        todas.extend(v)
    random.shuffle(todas)
    st.markdown("### Agarre e mova blocos livremente no espaço 3D")
    render_vr_tudo_movel(todas, modo="TUDO MOVIVEL", height=950)

with tab2:
    if st.session_state.simulado:
        sim = st.session_state.simulado
        qs = sim["questoes"]
        if not sim["finalizado"]:
            rest = max(0, 4 * 3600 - int(time.time() - sim["inicio"]))
            h, m, s = rest // 3600, (rest % 3600) // 60, rest % 60
            st.warning(f"⏱️ {h:02d}:{m:02d}:{s:02d} · {len(qs)}q")
            render_vr_tudo_movel(qs, modo="SIMULADO", height=950)
            st.divider()
            with st.form("form_sim"):
                resp = {}
                for i, q in enumerate(qs):
                    st.markdown(f"**{i+1}. [{q.get('materia','')}]** {q['pergunta']}")
                    esc = st.radio(f"q_{i}", q["alternativas"], index=None,
                                   key=f"sim_{i}", label_visibility="collapsed")
                    if esc:
                        resp[i] = esc[0].upper()
                    st.divider()
                c1, c2 = st.columns(2)
                if c1.form_submit_button("💾 Salvar", use_container_width=True):
                    sim["respostas"] = resp
                    st.success("Salvo.")
                    st.rerun()
                if c2.form_submit_button("✅ Finalizar", type="primary", use_container_width=True):
                    ac, dets = 0, []
                    for i, q in enumerate(qs):
                        r = resp.get(i, "")
                        ok = r == q["correta"].upper()
                        if ok: ac += 1
                        dets.append({"pergunta": q["pergunta"], "materia": q.get("materia",""),
                                     "resposta": r, "correta": q["correta"], "acertou": ok})
                    nota = (ac / len(qs)) * 100
                    st.session_state.hist.append({
                        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "acertos": ac, "total": len(qs), "nota": round(nota, 2),
                        "aprovado": nota >= 50, "detalhes": dets,
                        "tempo": time.time() - sim["inicio"],
                    })
                    sim["finalizado"] = True
                    st.rerun()
        else:
            ult = st.session_state.hist[-1] if st.session_state.hist else None
            if ult:
                st.balloons()
                c1, c2, c3 = st.columns(3)
                c1.metric("📊 Nota", f"{ult['nota']}%")
                c2.metric("✅ Acertos", f"{ult['acertos']}/{ult['total']}")
                c3.metric("🏁 Status", "APROVADO ✅" if ult["aprovado"] else "REPROVADO ❌")
                with st.expander("Gabarito"):
                    for i, d in enumerate(ult["detalhes"]):
                        ic = "✅" if d["acertou"] else "❌"
                        st.markdown(f"{ic} **{i+1}. [{d['materia']}]** {d['pergunta']}")
                        st.caption(f"Sua: {d['resposta'] or '—'} · Gab: {d['correta']}")
            if st.button("🔄 Novo simulado", type="primary"):
                st.session_state.simulado = None
                st.rerun()
    else:
        st.info("👈 Inicie um simulado na barra lateral.")

with tab3:
    if st.session_state.treino:
        mat_treino = st.session_state.treino[0].get("materia", "")
        st.subheader(f"📚 Treino — {mat_treino}")
        render_vr_tudo_movel(st.session_state.treino, modo="TREINO", height=950)
        for i, q in enumerate(st.session_state.treino):
            with st.expander(f"{i+1}. {q['pergunta'][:70]}..."):
                for a in q["alternativas"]:
                    st.markdown(f"- {a}")
                st.success(f"✅ Gabarito: **{q['correta']}**")
        if st.button("❌ Encerrar treino"):
            st.session_state.treino = []
            st.rerun()
    else:
        st.info("👈 Gere um treino na barra lateral.")
