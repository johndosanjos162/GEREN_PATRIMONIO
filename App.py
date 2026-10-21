"""
PMSC Arena VR — Centro de Comando Tático (v11)
Design: militar azul fosco #060913 + ciano neon #00d1ff
Correções: z-fighting, scale, hover tátil, cockpit a 2.2m
Lógica intacta: JSON, gramática, correção, ambientes, localStorage
"""
import streamlit as st
import streamlit.components.v1 as components
import json, random, time, pathlib, re, html as html_module
from datetime import datetime

st.set_page_config(page_title="PMSC Arena VR", page_icon="🎯", layout="wide")

DISTRIBUICAO = {
    "Legislação Institucional": 10, "Direito Constitucional": 8,
    "Língua Portuguesa": 8, "Direito Penal Comum": 6,
    "Direito Processual Penal Comum": 6, "Direito Penal Militar": 6,
    "Legislação Especial": 6, "Legislação de Trânsito": 5, "Informática": 5,
}
TOTAL_OFICIAL = sum(DISTRIBUICAO.values())

# ═══════════════════════════════════════════════════════════════════════
# NORMALIZAÇÃO GRAMATICAL (mantida)
# ═══════════════════════════════════════════════════════════════════════
def _limpar_espacos(t): return re.sub(r"\s+", " ", t or "").strip()
def _capitalizar(t): return t[0].upper() + t[1:] if t else t

def normalizar_enunciado(t):
    if not isinstance(t, str): return ""
    t = _capitalizar(_limpar_espacos(t))
    if t and t[-1] not in ".?!:;": t += "."
    return t

def normalizar_alternativa(t):
    if not isinstance(t, str): return ""
    t = _limpar_espacos(t)
    t = re.sub(r"^[A-Ea-e]\s*[\)\.\-\:]\s*", "", t)
    return _capitalizar(t)

def extrair_letra(c):
    if not isinstance(c, str): return ""
    c = c.strip().upper()
    m = re.match(r"^([A-E])(?:[\)\.\-\:\s]|$)", c)
    if m: return m.group(1)
    m = re.search(r"\b([A-E])\b", c)
    return m.group(1) if m else ""

def normalizar_questao(q):
    if not isinstance(q, dict): return None
    letra = extrair_letra(q.get("correta", ""))
    if not letra: return None
    pergunta = normalizar_enunciado(q.get("pergunta", ""))
    if not pergunta: return None
    alts = q.get("alternativas", [])
    if not isinstance(alts, list) or len(alts) < 5: return None
    limpas = [normalizar_alternativa(a) for a in alts[:5]]
    if any(not a for a in limpas): return None
    return {
        "pergunta": pergunta,
        "alternativas": [f"{chr(65+i)}) {a}" for i, a in enumerate(limpas)],
        "correta": letra, "materia": q.get("materia", ""),
    }

def normalizar_banco(banco):
    r = {}
    for mat, lista in banco.items():
        novas = [nq for q in lista if (nq := normalizar_questao(q))]
        if novas: r[mat] = novas
    return r

# ═══════════════════════════════════════════════════════════════════════
# CARREGADOR (mantido)
# ═══════════════════════════════════════════════════════════════════════
def _parse_concatenado(conteudo):
    decoder, idx, n, res = json.JSONDecoder(), 0, len(conteudo), {}
    while idx < n:
        while idx < n and conteudo[idx].isspace(): idx += 1
        if idx >= n: break
        try: obj, idx = decoder.raw_decode(conteudo, idx)
        except json.JSONDecodeError: break
        if isinstance(obj, dict):
            for m, l in obj.items():
                if isinstance(l, list): res.setdefault(m, []).extend(l)
        elif isinstance(obj, list):
            for q in obj: res.setdefault(q.get("materia", "Geral"), []).append(q)
    return res

def _dedup(lista):
    vistos, unicas, rem = set(), [], 0
    for q in lista:
        t = q.get("pergunta", "").strip().lower()
        if not t: continue
        if t in vistos: rem += 1; continue
        vistos.add(t); unicas.append(q)
    return unicas, rem

@st.cache_data(ttl=30, show_spinner=False)
def load_json():
    for path in [pathlib.Path(__file__).parent / "json.json",
                 pathlib.Path.cwd() / "json.json"]:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    parsed = _parse_concatenado(f.read())
                if not parsed: continue
                parsed = normalizar_banco(parsed)
                if not parsed: continue
                bruto, remov = 0, 0
                for mat in list(parsed.keys()):
                    un, r = _dedup(parsed[mat]); parsed[mat] = un
                    bruto += len(un) + r; remov += r
                return parsed, {"arquivo": path.name, "bruto": bruto,
                                "removidas": remov,
                                "unicas": sum(len(v) for v in parsed.values())}
            except Exception as e:
                return None, {"erro": str(e)}
    return None, {"erro": "json.json não encontrado"}

def montar_simulado(banco):
    sim = []
    for mat, qtd in DISTRIBUICAO.items():
        pool = banco.get(mat, [])
        if not pool:
            for k, v in banco.items():
                if mat.lower() in k.lower() or k.lower() in mat.lower():
                    pool = v; break
        if pool:
            sel = random.sample(pool, min(qtd, len(pool)))
            sim.extend([{**q, "materia": mat} for q in sel])
    random.shuffle(sim); return sim

for k, d in [("simulado", None), ("treino", []), ("hist", []), ("vr_ready", False)]:
    if k not in st.session_state: st.session_state[k] = d

banco, info = load_json()
if not banco:
    st.error(f"❌ Erro: {info.get('erro', '?')}"); st.stop()

def embed_with_webxr_permissions(inner_html, height=950):
    escaped = html_module.escape(inner_html, quote=True)
    wrapper = r'''<!DOCTYPE html><html><head><meta charset="utf-8">
<style>html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:#060913}
iframe{width:100%;height:100%;border:none;display:block}</style></head><body>
<iframe srcdoc="__INNER__"
 allow="xr-spatial-tracking; camera; microphone; accelerometer; gyroscope; fullscreen; autoplay"
 style="width:100%;height:100%;border:none;"></iframe></body></html>'''
    components.html(wrapper.replace("__INNER__", escaped), height=height, scrolling=False)

def render_vr(questoes, modo="ARENA", height=950):
    if not st.session_state.vr_ready:
        st.info(f"{len(questoes)} questões prontas.")
        if st.button(f"🥽 CARREGAR VR — {modo}", type="primary", use_container_width=True):
            st.session_state.vr_ready = True; st.rerun()
        return

    safe = [{
        "pergunta": q["pergunta"][:190].replace('"', "'").replace("\n", " "),
        "alternativas": [a[:62].replace('"', "'") for a in q["alternativas"][:5]],
        "correta": q["correta"].upper(),
        "materia": q.get("materia", "Geral")[:22],
    } for q in questoes[:18]]
    q_json = json.dumps(safe, ensure_ascii=False).replace("</", "<\\/")

    html_template = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>PMSC Tático VR</title>
<script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v7.4.0/dist/aframe-extras.min.js"></script>
<script>
// ═══════════════════════════════════════════════════════════════════
// vr-hand v11 — click isolado, feedback tátil
// ═══════════════════════════════════════════════════════════════════
AFRAME.registerComponent('vr-hand', {
  init: function() {
    const hand = this.el;
    let grabbed = null;
    let offset = new THREE.Vector3();
    let distAdjust = 0;
    const _p = new THREE.Vector3(), _d = new THREE.Vector3();
    const _q = new THREE.Quaternion(), _t = new THREE.Vector3();
    const _l = new THREE.Vector3(), _b = new THREE.Vector3();

    if (!hand.components.raycaster) {
      hand.setAttribute('raycaster', 'objects: .clickable, .ui-btn, .grabbable; far: 20; interval: 50');
    }

    const getPos = () => { hand.object3D.getWorldPosition(_p); return _p; };
    const getDir = () => {
      hand.object3D.getWorldQuaternion(_q);
      return _d.set(0, 0, -1).applyQuaternion(_q).normalize();
    };

    const findIn = (predicate) => {
      const rc = hand.components.raycaster;
      let list = (rc && rc.intersections && rc.intersections.length) ? rc.intersections : [];
      if (list.length === 0) {
        const objs = [];
        hand.sceneEl.object3D.traverse((o) => {
          if (o.el && o.el.classList && (o.el.classList.contains('clickable') ||
              o.el.classList.contains('ui-btn') ||
              o.el.classList.contains('grabbable'))) objs.push(o);
        });
        const ray = new THREE.Raycaster(getPos(), getDir(), 0, 20);
        list = ray.intersectObjects(objs, true);
      }
      for (const hit of list) {
        let cur = hit.object ? hit.object.el : null;
        while (cur) {
          if (predicate(cur)) return { el: cur, distance: hit.distance };
          cur = cur.parentEl;
        }
      }
      return null;
    };

    const findClickable = () => findIn(el => el.classList &&
      (el.classList.contains('clickable') || el.classList.contains('ui-btn')));
    const findBlock = () => findIn(el => el.id && el.id.indexOf('block-') === 0);

    const startGrab = () => {
      if (grabbed) return;
      const b = findBlock(); if (!b) return;
      grabbed = b.el;
      const hp = getPos();
      grabbed.object3D.getWorldPosition(_b);
      offset.copy(_b).sub(hp);
      distAdjust = 0;
      grabbed.setAttribute('material', 'emissive', '#ffaa00');
      grabbed.setAttribute('material', 'emissiveIntensity', '1');
      showToast('✋ ' + grabbed.id + ' @ ' + offset.length().toFixed(1) + 'm', 900);
      if (navigator.vibrate) navigator.vibrate(30);
    };

    const endGrab = () => {
      if (!grabbed) return;
      grabbed.setAttribute('material', 'emissive', '#00d1ff');
      grabbed.setAttribute('material', 'emissiveIntensity', '0.18');
      savePos(grabbed.id);
      showToast('📍 ' + grabbed.id + ' posicionado', 900);
      if (navigator.vibrate) navigator.vibrate(20);
      grabbed = null; distAdjust = 0;
    };

    const doClick = () => {
      const c = findClickable();
      if (!c) { showToast('⚠️ Aponte para uma alternativa A–E', 800); return; }
      c.el.emit('click', { target: c.el }, true);
      if (navigator.vibrate) navigator.vibrate(60);
    };

    this.tick = () => {
      if (grabbed) {
        const hp = getPos(); const dir = getDir();
        _t.copy(hp).add(offset).addScaledVector(dir, distAdjust);
        const parent = grabbed.object3D.parent;
        if (parent) {
          parent.worldToLocal(_l.copy(_t));
          grabbed.object3D.position.copy(_l);
        }
      }
    };

    hand.addEventListener('triggerdown', doClick);
    hand.addEventListener('gripdown', startGrab);
    hand.addEventListener('gripup', endGrab);
    hand.addEventListener('abuttondown', doClick);
    hand.addEventListener('pinchstarted', () => {
      const c = findClickable();
      if (c) doClick(); else startGrab();
    });
    hand.addEventListener('pinchended', endGrab);
    hand.addEventListener('thumbstickmoved', (evt) => {
      if (!grabbed) return;
      const { x, y } = evt.detail;
      if (Math.abs(x) > 0.15) grabbed.object3D.rotation.y += x * 0.03;
      if (Math.abs(y) > 0.15) {
        distAdjust -= y * 0.05;
        distAdjust = Math.max(-8, Math.min(8, distAdjust));
      }
    });
  }
});

AFRAME.registerComponent('hand-live', {
  schema: { hand: { type: 'string', default: 'left' } },
  init: function() {
    this.pinch = false; this.grip = false;
    this.el.addEventListener('pinchstarted', () => this.pinch = true);
    this.el.addEventListener('pinchended', () => this.pinch = false);
    this.el.addEventListener('gripdown', () => this.grip = true);
    this.el.addEventListener('gripup', () => this.grip = false);
  },
  tick: function() {
    const tEl = document.getElementById(this.data.hand + 'Data');
    if (!tEl) return;
    const p = this.el.object3D.position;
    const hasT = !!this.el.components['hand-tracking-controls'];
    const hasC = !!this.el.components['oculus-touch-controls'];
    const mode = hasT && hasC ? 'BOTH' : hasT ? 'HAND' : 'CTRL';
    tEl.setAttribute('value',
      this.data.hand.toUpperCase() + ': ' + mode +
      ' | ' + (this.pinch ? 'PINCH' : '✋') + (this.grip ? ' GRIP' : '') +
      '\nPos ' + p.x.toFixed(2) + ' ' + p.y.toFixed(2) + ' ' + p.z.toFixed(2));
  }
});

AFRAME.registerComponent('painel-sistema', {
  init: function() {
    const rig = document.getElementById('rig');
    const head = document.getElementById('head');
    const left = document.getElementById('leftHand');
    const right = document.getElementById('rightHand');
    const sky = document.getElementById('sky');
    const stars = document.getElementById('stars');
    const ambient = document.getElementById('ambientLight');
    let handScale = 1, headH = 1.65, brightness = 1.0;

    const applyBrightness = (b) => {
      if (ambient) ambient.setAttribute('light', 'intensity', (0.8 * b).toFixed(2));
    };

    this.el.querySelectorAll('.calib-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const a = btn.getAttribute('data-action');
        if (a === 'passthrough') { window.enablePassthrough(); return; }
        if (a === 'dark') {
          sky.setAttribute('visible', 'true');
          sky.setAttribute('material', 'shader: flat; color: #060913');
          stars.setAttribute('visible', 'false'); showToast('TÁTICO');
        }
        if (a === 'beach') {
          sky.setAttribute('visible', 'true');
          sky.setAttribute('material', 'shader: flat; src: url(https://cdn.aframe.io/360-image-gallery-boilerplate/img/sechelt.jpg); color: #fff');
          stars.setAttribute('visible', 'false'); showToast('PRAIA');
        }
        if (a === 'office') {
          sky.setAttribute('visible', 'true');
          sky.setAttribute('material', 'shader: flat; src: url(https://cdn.aframe.io/360-image-gallery-boilerplate/img/city.jpg); color: #fff');
          stars.setAttribute('visible', 'false'); showToast('ESCRITÓRIO');
        }
        if (a === 'library') {
          sky.setAttribute('visible', 'true');
          sky.setAttribute('material', 'shader: flat; src: url(https://cdn.aframe.io/360-image-gallery-boilerplate/img/cubes.jpg); color: #fff');
          stars.setAttribute('visible', 'false'); showToast('BIBLIOTECA');
        }
        if (a === 'space') {
          sky.setAttribute('visible', 'true');
          sky.setAttribute('material', 'shader: flat; color: #000008');
          createStarsPoints(); stars.setAttribute('visible', 'true'); showToast('ESPAÇO');
        }
        if (a === 'brightnessUp') {
          brightness = Math.min(1.0, brightness + 0.1);
          applyBrightness(brightness);
          showToast('Brilho ' + Math.round(brightness * 100) + '%');
        }
        if (a === 'brightnessDown') {
          brightness = Math.max(0.3, brightness - 0.1);
          applyBrightness(brightness);
          showToast('Brilho ' + Math.round(brightness * 100) + '%');
        }
        if (a === 'organizar') window.organizarGrade();
        if (a === 'porMateria') window.organizarPorMateria();
        if (a === 'espalhar') window.espalhar();
        if (a === 'salvar') window.salvarLayout();
        if (a === 'carregar') window.carregarLayout();
        if (a === 'maoMais') {
          handScale = Math.min(2.0, handScale + 0.1);
          const v = handScale + ' ' + handScale + ' ' + handScale;
          left.setAttribute('scale', v); right.setAttribute('scale', v);
          showToast('Mão + (' + handScale.toFixed(1) + ')');
        }
        if (a === 'maoMenos') {
          handScale = Math.max(0.2, handScale - 0.1);
          const v = handScale + ' ' + handScale + ' ' + handScale;
          left.setAttribute('scale', v); right.setAttribute('scale', v);
          showToast('Mão - (' + handScale.toFixed(1) + ')');
        }
        if (a === 'alturaMais') {
          headH = Math.min(2.5, headH + 0.1);
          head.setAttribute('position', '0 ' + headH + ' 0');
          showToast('Altura ' + headH.toFixed(1) + 'm');
        }
        if (a === 'alturaMenos') {
          headH = Math.max(0.4, headH - 0.1);
          head.setAttribute('position', '0 ' + headH + ' 0');
          showToast('Altura ' + headH.toFixed(1) + 'm');
        }
        if (a === 'resetPos') {
          rig.setAttribute('position', '0 0 3');
          rig.setAttribute('rotation', '0 0 0');
          showToast('Posição resetada');
        }
        if (a === 'sairVR') {
          const s = document.querySelector('a-scene').renderer.xr.getSession();
          if (s) s.end();
        }
        if (a === 'toggleHUD') window.toggleHUDMode();
        if (a === 'resetWorld') { window.location.reload(); }

        const orig = btn.getAttribute('material').color;
        btn.setAttribute('material', 'color', '#00ff88');
        setTimeout(() => btn.setAttribute('material', 'color', orig), 200);
      });
    });
  }
});

let hudMode = 'head';
window.toggleHUDMode = function() {
  const hud = document.getElementById('hudPanel');
  const head = document.getElementById('head');
  const leftHand = document.getElementById('leftHand');
  if (!hud || !head || !leftHand) return;
  if (hudMode === 'head') {
    hudMode = 'hand';
    hud.parentEl.removeChild(hud);
    leftHand.appendChild(hud);
    hud.setAttribute('position', '0 0.08 -0.08');
    hud.setAttribute('rotation', '0 0 0');
    hud.setAttribute('scale', '0.18 0.18 0.18');
    showToast('HUD no pulso');
  } else {
    hudMode = 'head';
    hud.parentEl.removeChild(hud);
    head.appendChild(hud);
    hud.setAttribute('position', '0 -0.32 -0.9');
    hud.setAttribute('rotation', '0 0 0');
    hud.setAttribute('scale', '0.5 0.5 0.5');
    showToast('HUD na cabeça');
  }
};

window.enablePassthrough = async function() {
  if (!navigator.xr) { showToast('❌ WebXR não suportado'); return; }
  try {
    const ok = await navigator.xr.isSessionSupported('immersive-ar');
    if (!ok) { showToast('❌ Use Meta Quest Browser', 4000); return; }
    const sceneEl = document.querySelector('a-scene');
    const renderer = sceneEl.renderer;
    const cur = renderer.xr.getSession();
    if (cur) { await cur.end(); await new Promise(r => setTimeout(r, 400)); }
    document.getElementById('sky').setAttribute('visible', 'false');
    document.getElementById('stars').setAttribute('visible', 'false');
    sceneEl.object3D.background = null;
    renderer.setClearColor(0x000000, 0);
    const sess = await navigator.xr.requestSession('immersive-ar', {
      requiredFeatures: ['local-floor'],
      optionalFeatures: ['passthrough', 'hand-tracking', 'hit-test', 'bounded-floor'],
    });
    try { await sess.updateRenderState({ passthroughEnabled: true }); } catch (e) {}
    await renderer.xr.setSession(sess);
    sess.addEventListener('end', () => {
      sceneEl.object3D.background = new THREE.Color(0x060913);
      renderer.setClearColor(0x060913, 1);
      document.getElementById('sky').setAttribute('visible', 'true');
    });
    showToast('👁️ PASSTHROUGH ATIVO');
  } catch (err) { showToast('❌ ' + err.message, 4000); }
};

let starsPoints = null;
function createStarsPoints() {
  const c = document.getElementById('stars'); if (!c) return;
  if (starsPoints) { c.object3D.remove(starsPoints);
    starsPoints.geometry.dispose(); starsPoints.material.dispose(); }
  const geo = new THREE.BufferGeometry();
  const N = 800; const pos = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    const r = 25 + Math.random() * 20;
    const t = Math.random() * Math.PI * 2;
    const p = Math.acos(2 * Math.random() - 1);
    pos[i*3] = r*Math.sin(p)*Math.cos(t);
    pos[i*3+1] = r*Math.sin(p)*Math.sin(t);
    pos[i*3+2] = r*Math.cos(p);
  }
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.PointsMaterial({
    color: 0xaaffff, size: 0.06, sizeAttenuation: true,
    transparent: true, opacity: 0.85, depthWrite: false });
  starsPoints = new THREE.Points(geo, mat);
  c.object3D.add(starsPoints);
}

function showToast(msg, ms) {
  const t = document.getElementById('toast'); if (!t) return;
  t.textContent = msg; t.style.display = 'block';
  clearTimeout(window._toastT);
  window._toastT = setTimeout(() => { t.style.display = 'none'; }, ms || 1600);
}

// ═══════════════════════════════════════════════════════════════════
// Textura neon tática (canvas)
// ═══════════════════════════════════════════════════════════════════
function makeCardTexture() {
  const cv = document.createElement('canvas');
  cv.width = 512; cv.height = 512;
  const ctx = cv.getContext('2d');
  const g = ctx.createLinearGradient(0, 0, 512, 512);
  g.addColorStop(0, '#060913');
  g.addColorStop(0.5, '#0a1520');
  g.addColorStop(1, '#0d1b2a');
  ctx.fillStyle = g; ctx.fillRect(0, 0, 512, 512);
  // Grid tático sutil
  ctx.strokeStyle = 'rgba(0, 209, 255, 0.06)';
  ctx.lineWidth = 1;
  for (let i = 0; i < 512; i += 32) {
    ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, 512); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(512, i); ctx.stroke();
  }
  // Borda ciano
  ctx.strokeStyle = '#00d1ff'; ctx.lineWidth = 6;
  ctx.strokeRect(3, 3, 506, 506);
  // Cantos táticos (L-shapes)
  ctx.strokeStyle = '#00d1ff'; ctx.lineWidth = 8;
  const cs = 40;
  ctx.beginPath(); ctx.moveTo(15, 15+cs); ctx.lineTo(15, 15); ctx.lineTo(15+cs, 15); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(512-15-cs, 15); ctx.lineTo(512-15, 15); ctx.lineTo(512-15, 15+cs); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(15, 512-15-cs); ctx.lineTo(15, 512-15); ctx.lineTo(15+cs, 512-15); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(512-15-cs, 512-15); ctx.lineTo(512-15, 512-15); ctx.lineTo(512-15, 512-15-cs); ctx.stroke();
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}
const CARD_TEX = makeCardTexture();

// ═══════════════════════════════════════════════════════════════════
// CRIA BLOCO — offsets z-fighting corrigidos + hover tátil
// ═══════════════════════════════════════════════════════════════════
function createBlock(q, i) {
  const cols = 4, spacing = 2.6;
  const x = (i % cols) * spacing - ((cols - 1) * spacing / 2);
  const z = Math.floor(i / cols) * -2.8 - 3.0;
  const y = 1.5;

  const root = document.createElement('a-entity');
  root.setAttribute('id', 'block-' + i);
  root.setAttribute('position', `${x} ${y} ${z}`);
  root.setAttribute('class', 'grabbable');
  root.setAttribute('data-materia', q.materia || 'Geral');
  root.setAttribute('geometry', 'primitive: box; width: 2.2; height: 2.0; depth: 0.06');
  root.setAttribute('material', 'shader: flat; color: #060913; emissive: #00d1ff; emissiveIntensity: 0.18; metalness: 0.3; roughness: 0.6');
  root.userData = { respondida: false, letraEscolhida: null };

  // Face frontal do cartão (textura neon)
  const face = document.createElement('a-plane');
  face.setAttribute('geometry', 'primitive: plane; width: 2.16; height: 1.96');
  face.setAttribute('material', 'shader: flat; transparent: true; opacity: 0.95; src: #cardTex');
  face.setAttribute('position', '0 0 0.032');
  face.setAttribute('class', 'grabbable');
  root.appendChild(face);

  // Título — z = 0.04 (evita z-fighting)
  const title = document.createElement('a-text');
  title.setAttribute('value', '▸ ' + (i + 1) + '. ' + q.materia.toUpperCase());
  title.setAttribute('color', '#00d1ff');
  title.setAttribute('width', '2.2');
  title.setAttribute('align', 'center');
  title.setAttribute('position', '0 0.85 0.04');
  title.setAttribute('class', 'grabbable');
  title.setAttribute('font', 'mozillavr');
  title.setAttribute('shader', 'msdf');
  title.setAttribute('negate', 'false');
  root.appendChild(title);

  // Pergunta — z = 0.04
  const qtext = document.createElement('a-text');
  const shortQ = q.pergunta.length > 150 ? q.pergunta.slice(0, 147) + '...' : q.pergunta;
  qtext.setAttribute('value', shortQ);
  qtext.setAttribute('color', '#e8f4ff');
  qtext.setAttribute('width', '2.0');
  qtext.setAttribute('align', 'center');
  qtext.setAttribute('position', '0 0.5 0.04');
  qtext.setAttribute('wrap-count', '38');
  qtext.setAttribute('class', 'grabbable');
  qtext.setAttribute('font', 'mozillavr');
  qtext.setAttribute('shader', 'msdf');
  qtext.setAttribute('negate', 'false');
  root.appendChild(qtext);

  // Alternativas — hover tátil + z escalonado
  q.alternativas.forEach((alt, idx) => {
    const letra = alt.trim().charAt(0).toUpperCase();
    const isCorreta = (letra === q.correta);
    const rowY = -0.05 - idx * 0.28;

    const row = document.createElement('a-entity');
    row.setAttribute('position', `0 ${rowY} 0.05`);

    const bg = document.createElement('a-plane');
    bg.setAttribute('id', `alt-${i}-${idx}`);
    bg.setAttribute('geometry', 'primitive: plane; width: 2.0; height: 0.24');
    bg.setAttribute('material', 'shader: flat; color: #0a1520; emissive: #000000; emissiveIntensity: 0; side: double; opacity: 0.95; transparent: true');
    bg.setAttribute('class', 'clickable ui-btn');
    bg.setAttribute('data-i', i);
    bg.setAttribute('data-letra', letra);
    bg.setAttribute('data-correta', isCorreta ? 'true' : 'false');
    // Hover tátil: escala + brilho
    bg.setAttribute('animation__hover',
      'property: scale; to: 1.05 1.05 1.05; dur: 120; startEvents: raycaster-intersection');
    bg.setAttribute('animation__hoverout',
      'property: scale; to: 1 1 1; dur: 120; startEvents: raycaster-intersection-cleared');
    bg.setAttribute('animation__glow',
      'property: material.emissiveIntensity; from: 0; to: 0.5; dur: 120; startEvents: raycaster-intersection');

    // Texto — z = 0.006 (dentro do row, que já está a 0.05)
    const txt = document.createElement('a-text');
    txt.setAttribute('value', alt.length > 58 ? alt.slice(0, 55) + '...' : alt);
    txt.setAttribute('color', '#b8d4e8');
    txt.setAttribute('width', '1.85');
    txt.setAttribute('position', '-0.92 0 0.006');
    txt.setAttribute('font', 'mozillavr');
    txt.setAttribute('shader', 'msdf');
    txt.setAttribute('negate', 'false');

    bg.appendChild(txt);
    row.appendChild(bg);

    // Click isolado
    bg.addEventListener('click', function(e) {
      e.stopPropagation();
      if (root.userData.respondida) return;
      root.userData.respondida = true;
      root.userData.letraEscolhida = letra;

      // Limpa SÓ neste bloco
      root.querySelectorAll('[data-correta]').forEach(el => {
        el.setAttribute('material', 'emissive', '#000000');
        el.setAttribute('material', 'emissiveIntensity', '0');
        delete el.dataset.hl;
      });

      // Aplica cor apenas no bg clicado
      const cor = isCorreta ? '#00aa55' : '#aa2222';
      bg.setAttribute('material', 'color', cor);
      bg.setAttribute('material', 'emissive', cor);
      bg.setAttribute('material', 'emissiveIntensity', '0.8');
      bg.dataset.respondida = 'true';

      // Animação de clique (flash)
      bg.setAttribute('animation__click',
        'property: scale; from: 1.05 1.05 1.05; to: 1.15 1.15 1.15; dur: 100; dir: alternate; loop: 2');

      updateHUD();
      showToast(isCorreta ? '✅ Correto! (' + letra + ')' : '❌ Errado. Correta: ' + q.correta);
    });

    root.appendChild(row);
  });

  return root;
}

function updateHUD() {
  let total = 0, respondidas = 0;
  document.querySelectorAll('[data-correta]').forEach(el => {
    total++;
    if (el.dataset.respondida === 'true') respondidas++;
  });
  const txt = respondidas + '/' + total;
  const st = document.getElementById('status');
  if (st) st.textContent = txt + ' respondidas';
  const hd = document.getElementById('hudVRText');
  if (hd) hd.setAttribute('value', txt);
}

let timerStart = Date.now();
setInterval(() => {
  const el = document.getElementById('timerText'); if (!el) return;
  const elapsed = Math.floor((Date.now() - timerStart) / 1000);
  const m = Math.floor(elapsed / 60), s = elapsed % 60;
  el.setAttribute('value', (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s);
}, 1000);

window.organizarGrade = function() {
  document.querySelectorAll('[id^="block-"]').forEach((b, i) => {
    const cols = 4, sp = 2.6;
    const x = (i % cols) * sp - ((cols - 1) * sp / 2);
    const z = Math.floor(i / cols) * -2.8 - 3.0;
    b.setAttribute('animation', `property: position; to: ${x} 1.5 ${z}; dur: 800`);
  });
  showToast('📐 GRADE TÁTICA');
};

window.organizarPorMateria = function() {
  const by = {};
  document.querySelectorAll('[id^="block-"]').forEach(b => {
    const m = b.getAttribute('data-materia') || 'Geral';
    (by[m] = by[m] || []).push(b);
  });
  const names = Object.keys(by);
  names.forEach((mat, s) => {
    const cluster = by[mat];
    const baseX = (s - (names.length - 1) / 2) * 5.5;
    cluster.forEach((b, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      b.setAttribute('animation',
        `property: position; to: ${baseX + (col - 0.5) * 2.6} 1.5 ${-3 - row * 2.8}; dur: 900`);
    });
  });
  showToast('🎯 POR MATÉRIA (' + names.length + ')');
};

window.espalhar = function() {
  document.querySelectorAll('[id^="block-"]').forEach(b => {
    const x = (Math.random() - 0.5) * 14;
    const z = (Math.random() - 0.5) * 14 - 3;
    const y = 0.8 + Math.random() * 2.5;
    b.setAttribute('animation', `property: position; to: ${x} ${y} ${z}; dur: 800`);
  });
  showToast('🎲 ESPALHADO');
};

const STORAGE_KEY = 'pmsc_arena_layout_v2';
function savePos(id) {
  if (!id) return;
  const el = document.getElementById(id); if (!el) return;
  try {
    const L = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    L[id] = {
      p: el.getAttribute('position'),
      r: el.getAttribute('rotation') || { x: 0, y: 0, z: 0 },
      s: el.getAttribute('scale') || { x: 1, y: 1, z: 1 },
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(L));
  } catch (e) {}
}

window.salvarLayout = function() {
  const L = {};
  document.querySelectorAll('.grabbable').forEach(el => {
    if (!el.id) return;
    L[el.id] = {
      p: el.getAttribute('position'),
      r: el.getAttribute('rotation') || { x: 0, y: 0, z: 0 },
      s: el.getAttribute('scale') || { x: 1, y: 1, z: 1 },
    };
  });
  localStorage.setItem(STORAGE_KEY, JSON.stringify(L));
  showToast('💾 ' + Object.keys(L).length + ' objetos salvos');
};

window.carregarLayout = function() {
  try {
    const L = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    let n = 0;
    Object.keys(L).forEach(id => {
      const el = document.getElementById(id); if (!el) return;
      el.setAttribute('position', L[id].p);
      if (L[id].r) el.setAttribute('rotation', L[id].r);
      if (L[id].s) el.setAttribute('scale', L[id].s);
      n++;
    });
    showToast('📂 ' + n + ' objetos restaurados');
  } catch (e) { showToast('❌ Erro'); }
};

const QUESTIONS = __Q_JSON__;
window.addEventListener('load', () => {
  const world = document.getElementById('world'); if (!world) return;
  QUESTIONS.forEach((q, i) => world.appendChild(createBlock(q, i)));
  setTimeout(updateHUD, 500);
});
document.getElementById('enter').addEventListener('click', () => {
  document.querySelector('a-scene').enterVR().catch(e => showToast('❌ ' + e.message));
});
</script>

<style>
html, body {
  margin: 0; padding: 0; width: 100%; height: 100vh;
  overflow: hidden; background: #060913;
  font-family: 'Segoe UI', 'Inter', sans-serif;
}
#hud {
  position: fixed; top: 12px; left: 12px; z-index: 99999;
  background: rgba(6, 9, 19, 0.94); color: #00d1ff;
  border: 1px solid rgba(0, 209, 255, 0.5);
  padding: 12px 16px; border-radius: 8px;
  font-size: 12px; max-width: 480px;
  box-shadow: 0 0 20px rgba(0, 209, 255, 0.15);
  backdrop-filter: blur(6px);
}
#hud .title { font-weight: 900; color: #fff; font-size: 13px; letter-spacing: 2px; }
#hud .sub { font-weight: 600; color: #00d1ff; font-size: 11px; margin-top: 4px; }
#hud .counter { margin-top: 6px; color: #00ff88; font-weight: 700; }
#enter {
  position: fixed; bottom: 16px; left: 50%;
  transform: translateX(-50%); z-index: 99999;
  background: linear-gradient(90deg, #00d1ff, #0050a8);
  color: #060913; border: 2px solid #00d1ff;
  padding: 14px 40px; border-radius: 6px;
  font-weight: 900; font-size: 14px; letter-spacing: 2px;
  cursor: pointer; box-shadow: 0 0 24px rgba(0, 209, 255, 0.5);
}
#enter:hover { background: linear-gradient(90deg, #00e5ff, #0070d8); }
#toast {
  position: fixed; bottom: 90px; left: 50%;
  transform: translateX(-50%); z-index: 999999;
  background: rgba(6, 9, 19, 0.96); color: #00d1ff;
  border: 2px solid #00d1ff; padding: 12px 24px;
  border-radius: 8px; font-size: 13px; font-weight: 700;
  display: none; pointer-events: none;
  box-shadow: 0 0 24px rgba(0, 209, 255, 0.6);
  letter-spacing: 1px;
}
</style>
</head>
<body>

<div id="hud">
  <div class="title">⬢ PMSC · CENTRO DE COMANDO</div>
  <div class="sub">__MODO__ · GRIP=MOVER · TRIGGER=RESPONDER</div>
  <div class="counter">STATUS: <span id="status">0/__LEN__</span></div>
</div>
<button id="enter">▶ ENTRAR NO VR</button>
<div id="toast"></div>

<a-scene id="scene"
  background="color: #060913"
  renderer="colorManagement: true; antialias: true; highRefreshRate: true; foveationLevel: 2; powerPreference: high-performance; alpha: true"
  webxr="optionalFeatures: hand-tracking, local-floor, bounded-floor, hit-test, passthrough"
  vr-mode-ui="enabled: true"
  embedded
  style="width: 100%; height: 100vh;">

  <a-sky id="sky" material="shader: flat; color: #060913"></a-sky>
  <a-entity id="stars" visible="false"></a-entity>

  <a-entity id="ambientLight" light="type: ambient; intensity: 0.8"></a-entity>
  <a-entity light="type: directional; intensity: 0.4" position="3 6 4"></a-entity>
  <a-entity light="type: point; color: #00d1ff; intensity: 0.6; distance: 8" position="0 3 -2"></a-entity>
  <a-plane rotation="-90 0 0" width="80" height="80" color="#0a0f1a" material="shader: flat; opacity: 0.9"></a-plane>

  <a-entity id="rig" position="0 0 3" movement-controls="fly: true; speed: 0.3">
    <a-entity id="head" camera look-controls wasd-controls="acceleration: 20" position="0 1.65 0">
      <a-entity id="hudPanel" position="0 -0.32 -0.9" scale="0.5 0.5 0.5">
        <a-plane width="1.1" height="0.3" color="#060913" opacity="0.9" material="shader: flat"></a-plane>
        <a-text id="hudVRText" value="0/__LEN__" color="#00d1ff" width="1.0"
          align="center" position="0 0.06 0.004" font="mozillavr" shader="msdf" negate="false"></a-text>
        <a-text id="timerText" value="00:00" color="#00ff88" width="0.45"
          align="right" position="0.35 -0.07 0.004" font="mozillavr" shader="msdf" negate="false"></a-text>
        <a-text value="◉ LIVE" color="#ffaa00" width="0.4"
          align="left" position="-0.35 -0.07 0.004" font="mozillavr" shader="msdf" negate="false"></a-text>
      </a-entity>
    </a-entity>

    <a-entity id="leftHand"
      laser-controls="hand: left"
      hand-tracking-controls="hand: left; modelStyle: dots; color: #00d1ff"
      hand-live="hand: left"
      vr-hand
      raycaster="objects: .clickable, .ui-btn, .grabbable; far: 20; interval: 50"
      line="color: #00d1ff; opacity: 0.9">
    </a-entity>

    <a-entity id="rightHand"
      laser-controls="hand: right"
      hand-tracking-controls="hand: right; modelStyle: dots; color: #ff8a00"
      hand-live="hand: right"
      vr-hand
      raycaster="objects: .clickable, .ui-btn, .grabbable; far: 20; interval: 50"
      line="color: #ff8a00; opacity: 0.9">
    </a-entity>
  </a-entity>

  <!-- ═══════════ PAINEL PRINCIPAL (cockpit 2.2m, curvado) ═══════════ -->
  <a-entity id="mainPanel" position="0 2.3 -2.2"
    rotation="0 0 0"
    class="grabbable"
    geometry="primitive: box; width: 3.4; height: 2.2; depth: 0.05"
    material="shader: flat; color: #060913; emissive: #00d1ff; emissiveIntensity: 0.08; metalness: 0.4; roughness: 0.5; opacity: 0.96; transparent: true"
    painel-sistema>

    <!-- Borda neon decorativa -->
    <a-plane geometry="primitive: plane; width: 3.36; height: 2.16"
      material="shader: flat; color: #00d1ff; opacity: 0.15; transparent: true"
      position="0 0 0.026"></a-plane>

    <!-- Título -->
    <a-text value="⬢ PMSC · PAINEL TÁTICO"
      color="#00d1ff" width="3.2" align="center" position="0 0.92 0.03"
      font="mozillavr" shader="msdf" negate="false"></a-text>
    <a-text value="SISTEMA DE COMANDO DE ESTUDO" color="#5a7a9a" width="2.4"
      align="center" position="0 0.82 0.03"
      font="mozillavr" shader="msdf" negate="false"></a-text>

    <!-- Linha 1: Ambientes -->
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="dark"
      position="-1.2 0.6 0.03" geometry="primitive: plane; width: 0.65; height: 0.22"
      material="shader: flat; color: #0a1520; emissive: #00d1ff; emissiveIntensity: 0.15; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.15; to: 0.6; dur: 100; startEvents: raycaster-intersection">
      <a-text value="TÁTICO" color="#00d1ff" width="0.55" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="beach"
      position="-0.5 0.6 0.03" geometry="primitive: plane; width: 0.65; height: 0.22"
      material="shader: flat; color: #0a1520; emissive: #00d1ff; emissiveIntensity: 0.15; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.15; to: 0.6; dur: 100; startEvents: raycaster-intersection">
      <a-text value="PRAIA" color="#00d1ff" width="0.55" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="office"
      position="0.2 0.6 0.03" geometry="primitive: plane; width: 0.65; height: 0.22"
      material="shader: flat; color: #0a1520; emissive: #00d1ff; emissiveIntensity: 0.15; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.15; to: 0.6; dur: 100; startEvents: raycaster-intersection">
      <a-text value="ESCRITÓRIO" color="#00d1ff" width="0.55" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="library"
      position="0.9 0.6 0.03" geometry="primitive: plane; width: 0.65; height: 0.22"
      material="shader: flat; color: #0a1520; emissive: #00d1ff; emissiveIntensity: 0.15; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.15; to: 0.6; dur: 100; startEvents: raycaster-intersection">
      <a-text value="BIBLIOTECA" color="#00d1ff" width="0.55" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <!-- Linha 2: Espaço + Passthrough + Brilho -->
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="space"
      position="-1.2 0.3 0.03" geometry="primitive: plane; width: 0.65; height: 0.22"
      material="shader: flat; color: #0a1520; emissive: #00d1ff; emissiveIntensity: 0.15; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.15; to: 0.6; dur: 100; startEvents: raycaster-intersection">
      <a-text value="ESPAÇO" color="#00d1ff" width="0.55" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="passthrough"
      position="-0.5 0.3 0.03" geometry="primitive: plane; width: 0.65; height: 0.22"
      material="shader: flat; color: #0a1520; emissive: #ffaa00; emissiveIntensity: 0.2; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.2; to: 0.7; dur: 100; startEvents: raycaster-intersection">
      <a-text value="PASSTHROUGH" color="#ffaa00" width="0.55" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="brightnessDown"
      position="0.2 0.3 0.03" geometry="primitive: plane; width: 0.4; height: 0.22"
      material="shader: flat; color: #0a1520; emissive: #00d1ff; emissiveIntensity: 0.15; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.15; to: 0.6; dur: 100; startEvents: raycaster-intersection">
      <a-text value="◐-" color="#00d1ff" width="0.4" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="brightnessUp"
      position="0.65 0.3 0.03" geometry="primitive: plane; width: 0.4; height: 0.22"
      material="shader: flat; color: #0a1520; emissive: #00d1ff; emissiveIntensity: 0.15; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.15; to: 0.6; dur: 100; startEvents: raycaster-intersection">
      <a-text value="◐+" color="#00d1ff" width="0.4" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="toggleHUD"
      position="1.2 0.3 0.03" geometry="primitive: plane; width: 0.55; height: 0.22"
      material="shader: flat; color: #0a1520; emissive: #00ff88; emissiveIntensity: 0.2; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.2; to: 0.7; dur: 100; startEvents: raycaster-intersection">
      <a-text value="HUD" color="#00ff88" width="0.5" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <!-- Linha 3: Organização -->
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="organizar"
      position="-1.2 0.0 0.03" geometry="primitive: plane; width: 0.65; height: 0.22"
      material="shader: flat; color: #0a1520; emissive: #00d1ff; emissiveIntensity: 0.15; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.15; to: 0.6; dur: 100; startEvents: raycaster-intersection">
      <a-text value="GRADE" color="#00d1ff" width="0.55" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="porMateria"
      position="-0.5 0.0 0.03" geometry="primitive: plane; width: 0.65; height: 0.22"
      material="shader: flat; color: #0a1520; emissive: #00d1ff; emissiveIntensity: 0.15; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.15; to: 0.6; dur: 100; startEvents: raycaster-intersection">
      <a-text value="POR MATÉRIA" color="#00d1ff" width="0.55" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="espalhar"
      position="0.2 0.0 0.03" geometry="primitive: plane; width: 0.65; height: 0.22"
      material="shader: flat; color: #0a1520; emissive: #ffaa00; emissiveIntensity: 0.15; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.15; to: 0.6; dur: 100; startEvents: raycaster-intersection">
      <a-text value="ESPALHAR" color="#ffaa00" width="0.55" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="salvar"
      position="0.9 0.0 0.03" geometry="primitive: plane; width: 0.6; height: 0.22"
      material="shader: flat; color: #0a1520; emissive: #00ff88; emissiveIntensity: 0.2; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.2; to: 0.7; dur: 100; startEvents: raycaster-intersection">
      <a-text value="SALVAR" color="#00ff88" width="0.5" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <!-- Linha 4: Carregar + Sair -->
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="carregar"
      position="-1.2 -0.3 0.03" geometry="primitive: plane; width: 0.6; height: 0.22"
      material="shader: flat; color: #0a1520; emissive: #ffaa00; emissiveIntensity: 0.2; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.2; to: 0.7; dur: 100; startEvents: raycaster-intersection">
      <a-text value="CARREGAR" color="#ffaa00" width="0.5" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="sairVR"
      position="1.2 -0.3 0.03" geometry="primitive: plane; width: 0.6; height: 0.22"
      material="shader: flat; color: #0a1520; emissive: #ff2222; emissiveIntensity: 0.25; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.25; to: 0.8; dur: 100; startEvents: raycaster-intersection">
      <a-text value="SAIR VR" color="#ff2222" width="0.5" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <!-- Rodapé -->
    <a-text value="▸ GRIP=MOVER · TRIGGER=RESPONDER · STICK=AJUSTAR"
      color="#5a7a9a" width="3.0" align="center" position="0 -0.85 0.03"
      font="mozillavr" shader="msdf" negate="false"></a-text>
  </a-entity>

  <!-- ═══════════ PAINEL CALIBRADOR (cockpit, curvado à direita) ═══════════ -->
  <a-entity id="calibPanel" position="2.5 2.3 -2.0"
    rotation="0 -18 0"
    class="grabbable"
    geometry="primitive: box; width: 1.4; height: 1.8; depth: 0.05"
    material="shader: flat; color: #060913; emissive: #00d1ff; emissiveIntensity: 0.08; metalness: 0.4; opacity: 0.95; transparent: true">
    <a-plane geometry="primitive: plane; width: 1.36; height: 1.76"
      material="shader: flat; color: #00d1ff; opacity: 0.12; transparent: true"
      position="0 0 0.026"></a-plane>
    <a-text value="◉ SENSORES" color="#00d1ff" width="1.3" align="center" position="0 0.75 0.03"
      font="mozillavr" shader="msdf" negate="false"></a-text>
    <a-text id="leftData" value="LEFT: aguardando" color="#00d1ff" width="1.25"
      align="left" position="-0.6 0.4 0.03" wrap-count="30"
      font="mozillavr" shader="msdf" negate="false"></a-text>
    <a-text id="rightData" value="RIGHT: aguardando" color="#ff8a00" width="1.25"
      align="left" position="-0.6 0.05 0.03" wrap-count="30"
      font="mozillavr" shader="msdf" negate="false"></a-text>

    <!-- Botões calibrador -->
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="maoMais"
      position="-0.35 -0.25 0.03" geometry="primitive: plane; width: 0.55; height: 0.2"
      material="shader: flat; color: #0a1520; emissive: #00d1ff; emissiveIntensity: 0.15; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.15; to: 0.6; dur: 100; startEvents: raycaster-intersection">
      <a-text value="MÃO +" color="#00d1ff" width="0.5" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="maoMenos"
      position="0.35 -0.25 0.03" geometry="primitive: plane; width: 0.55; height: 0.2"
      material="shader: flat; color: #0a1520; emissive: #00d1ff; emissiveIntensity: 0.15; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.15; to: 0.6; dur: 100; startEvents: raycaster-intersection">
      <a-text value="MÃO -" color="#00d1ff" width="0.5" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="alturaMais"
      position="-0.35 -0.55 0.03" geometry="primitive: plane; width: 0.55; height: 0.2"
      material="shader: flat; color: #0a1520; emissive: #00d1ff; emissiveIntensity: 0.15; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.15; to: 0.6; dur: 100; startEvents: raycaster-intersection">
      <a-text value="ALT +" color="#00d1ff" width="0.5" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="alturaMenos"
      position="0.35 -0.55 0.03" geometry="primitive: plane; width: 0.55; height: 0.2"
      material="shader: flat; color: #0a1520; emissive: #00d1ff; emissiveIntensity: 0.15; opacity: 0.95; transparent: true"
      animation__hover="property: scale; to: 1.06 1.06 1; dur: 100; startEvents: raycaster-intersection"
      animation__hoverout="property: scale; to: 1 1 1; dur: 100; startEvents: raycaster-intersection-cleared"
      animation__glow="property: material.emissiveIntensity; from: 0.15; to: 0.6; dur: 100; startEvents: raycaster-intersection">
      <a-text value="ALT -" color="#00d1ff" width="0.5" align="center" position="0 0 0.004" font="mozillavr" shader="msdf" negate="false"></a-text></a-entity>
  </a-entity>

  <a-entity id="world"></a-entity>
</a-scene>

</body>
</html>"""

    html = (html_template
            .replace("__Q_JSON__", q_json)
            .replace("__MODO__", modo)
            .replace("__LEN__", str(len(safe))))

    embed_with_webxr_permissions(html, height=height)

    if st.button(f"❌ Fechar VR — {modo}", key=f"close_{modo}", use_container_width=True):
        st.session_state.vr_ready = False
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════
# UI STREAMLIT (mantida)
# ═══════════════════════════════════════════════════════════════════════
st.title("⬢ PMSC Arena VR — Centro de Comando Tático")
st.caption(f"✅ {info['arquivo']} · {info['unicas']} questões únicas "
           f"({info['removidas']} duplicatas) · Meta Quest 3/3S")

with st.sidebar:
    st.success(f"📚 {info['unicas']} questões únicas")
    if st.button("🔄 Recarregar json.json", use_container_width=True):
        load_json.clear(); st.rerun()
    st.divider()
    st.subheader("📚 Treino")
    mat = st.selectbox("Matéria", list(banco.keys()))
    maximo = len(banco.get(mat, []))
    if maximo > 0:
        qtd = st.slider("Quantidade", 5, min(20, maximo), min(10, maximo))
        if st.button("Iniciar Treino", use_container_width=True):
            pool = banco.get(mat, [])
            st.session_state.treino = [
                {**q, "materia": mat} for q in random.sample(pool, min(qtd, len(pool)))
            ]
            st.session_state.simulado = None
            st.session_state.vr_ready = False
            st.rerun()
    st.divider()
    st.subheader("📝 Simulado")
    st.caption(f"{TOTAL_OFICIAL} questões oficiais do edital")
    if st.button("Iniciar Simulado 60q", type="primary", use_container_width=True):
        st.session_state.simulado = {
            "questoes": montar_simulado(banco),
            "inicio": time.time(), "respostas": {}, "finalizado": False,
        }
        st.session_state.treino = []
        st.session_state.vr_ready = False
        st.rerun()
    if st.session_state.simulado and not st.session_state.simulado["finalizado"]:
        if st.button("❌ Cancelar simulado", use_container_width=True):
            st.session_state.simulado = None
            st.session_state.vr_ready = False
            st.rerun()
    st.divider()
    st.subheader("📜 Histórico")
    if st.session_state.hist:
        for h in reversed(st.session_state.hist[-5:]):
            st.caption(f"{h['data']} — {h['acertos']}/{h['total']} ({h['nota']}%)")
    else:
        st.caption("Nenhum simulado finalizado ainda.")

tab_vr, tab_sim = st.tabs(["🥽 Arena VR", "📝 Simulado"])

with tab_vr:
    if st.session_state.simulado:
        render_vr(st.session_state.simulado["questoes"], modo="SIMULADO", height=950)
    elif st.session_state.treino:
        render_vr(st.session_state.treino, modo="TREINO", height=950)
    else:
        todas = []
        for v in banco.values(): todas.extend(v)
        random.shuffle(todas)
        render_vr(todas, modo="ARENA", height=950)

with tab_sim:
    if st.session_state.simulado:
        sim = st.session_state.simulado; qs = sim["questoes"]
        if not sim["finalizado"]:
            rest = max(0, 4*3600 - int(time.time() - sim["inicio"]))
            h, m, s = rest//3600, (rest%3600)//60, rest%60
            st.warning(f"⏱️ **Tempo:** {h:02d}:{m:02d}:{s:02d} · {len(qs)}q")
            with st.form("form_sim"):
                resp = {}
                for i, q in enumerate(qs):
                    st.markdown(f"**{i+1}. [{q.get('materia','')}]** {q['pergunta']}")
                    esc = st.radio(f"q_{i}", q["alternativas"], index=None,
                                   key=f"sim_{i}", label_visibility="collapsed")
                    if esc: resp[i] = esc[0].upper()
                    st.divider()
                c1, c2 = st.columns(2)
                if c1.form_submit_button("💾 Salvar", use_container_width=True):
                    sim["respostas"] = resp; st.success("Salvo."); st.rerun()
                if c2.form_submit_button("✅ Finalizar", type="primary", use_container_width=True):
                    ac, dets = 0, []
                    for i, q in enumerate(qs):
                        r = resp.get(i, ""); ok = r == q["correta"].upper()
                        if ok: ac += 1
                        dets.append({"pergunta": q["pergunta"], "materia": q.get("materia",""),
                                     "resposta": r, "correta": q["correta"], "acertou": ok})
                    nota = (ac/len(qs))*100
                    st.session_state.hist.append({
                        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "acertos": ac, "total": len(qs), "nota": round(nota,2),
                        "aprovado": nota >= 50, "detalhes": dets,
                        "tempo": time.time() - sim["inicio"],
                    })
                    sim["finalizado"] = True; st.rerun()
        else:
            ult = st.session_state.hist[-1] if st.session_state.hist else None
            if ult:
                st.balloons()
                c1, c2, c3 = st.columns(3)
                c1.metric("📊 Nota", f"{ult['nota']}%")
                c2.metric("✅ Acertos", f"{ult['acertos']}/{ult['total']}")
                c3.metric("🏁 Status", "APROVADO ✅" if ult["aprovado"] else "REPROVADO ❌")
                with st.expander("Ver gabarito"):
                    for i, d in enumerate(ult["detalhes"]):
                        ic = "✅" if d["acertou"] else "❌"
                        st.markdown(f"{ic} **{i+1}. [{d['materia']}]** {d['pergunta']}")
                        st.caption(f"Sua: {d['resposta'] or '—'} · Correta: {d['correta']}")
            if st.button("🔄 Novo simulado", type="primary"):
                st.session_state.simulado = None
                st.session_state.vr_ready = False
                st.rerun()
    else:
        st.info("👈 Inicie um simulado pela barra lateral.")
