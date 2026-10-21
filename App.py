"""
PMSC Arena VR — Versão com correções de orientação e click
- Mãos: laser-controls + hand-tracking-controls (auto-detect)
- Click: raycaster via atributo + duplo listener + walk-up + feedback
"""
import streamlit as st
import streamlit.components.v1 as components
import json
import random
import time
import pathlib
import html as html_module
from datetime import datetime

st.set_page_config(page_title="PMSC Arena VR", page_icon="🎯", layout="wide")

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
TOTAL_OFICIAL = sum(DISTRIBUICAO.values())


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
def load_json():
    for path in [
        pathlib.Path(__file__).parent / "json.json",
        pathlib.Path.cwd() / "json.json",
    ]:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    parsed = _parse_concatenado(f.read())
                if not parsed:
                    continue
                bruto, removidas = 0, 0
                for mat in list(parsed.keys()):
                    un, r = _deduplicar(parsed[mat])
                    parsed[mat] = un
                    bruto += len(un) + r
                    removidas += r
                return parsed, {
                    "arquivo": path.name, "bruto": bruto,
                    "removidas": removidas,
                    "unicas": sum(len(v) for v in parsed.values()),
                }
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
                    pool = v
                    break
        if pool:
            sel = random.sample(pool, min(qtd, len(pool)))
            sim.extend([{**q, "materia": mat} for q in sel])
    random.shuffle(sim)
    return sim


for key, default in [
    ("simulado", None), ("treino", []), ("hist", []), ("vr_ready", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

banco, info = load_json()
if not banco:
    st.error(f"❌ Erro ao carregar json.json: {info.get('erro', '?')}")
    st.stop()


def embed_with_webxr_permissions(inner_html: str, height: int = 950):
    """Duplo iframe: interno com allow='xr-spatial-tracking; ...'."""
    escaped = html_module.escape(inner_html, quote=True)
    wrapper = r'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:#050a14}
iframe{width:100%;height:100%;border:none;display:block}</style>
</head><body>
<iframe srcdoc="__INNER__"
 allow="xr-spatial-tracking; camera; microphone; accelerometer; gyroscope; fullscreen; autoplay"
 style="width:100%;height:100%;border:none;"></iframe>
</body></html>'''
    wrapper = wrapper.replace("__INNER__", escaped)
    components.html(wrapper, height=height, scrolling=False)


def render_vr(questoes, modo="ARENA", height=950):
    if not st.session_state.vr_ready:
        st.info(f"{len(questoes)} questões prontas para a arena VR.")
        if st.button(f"🥽 CARREGAR VR — {modo}", type="primary", use_container_width=True):
            st.session_state.vr_ready = True
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

    html_template = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>PMSC Arena VR</title>
<script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v7.4.0/dist/aframe-extras.min.js"></script>
<script>
// ═══════════════════════════════════════════════════════════════════
// vr-hand v8 — leitura do raycaster A-Frame + duplo evento + feedback
// ═══════════════════════════════════════════════════════════════════
AFRAME.registerComponent('vr-hand', {
  init: function() {
    const hand = this.el;
    let grabbed = null;
    let offset = new THREE.Vector3();
    let distAdjust = 0;
    const FALLBACK_FAR = 20;

    // Garante que o raycaster exista (laser-controls já monta, mas reforçamos)
    if (!hand.components.raycaster) {
      hand.setAttribute('raycaster', 'objects: .clickable, .ui-btn, .grabbable; far: 20; interval: 100');
    }

    const getPos = function() {
      const p = new THREE.Vector3();
      hand.object3D.getWorldPosition(p);
      return p;
    };
    const getDir = function() {
      const q = new THREE.Quaternion();
      hand.object3D.getWorldQuaternion(q);
      return new THREE.Vector3(0, 0, -1).applyQuaternion(q).normalize();
    };

    // Percorre as interseções atuais e sobe até o alvo desejado
    const findInIntersections = function(predicate) {
      const rc = hand.components.raycaster;
      let list = [];
      if (rc && rc.intersections && rc.intersections.length > 0) {
        list = rc.intersections;
      } else {
        // Fallback: raycast manual
        const objs = [];
        hand.sceneEl.object3D.traverse(function(o) {
          if (o.el && o.el.classList) {
            if (o.el.classList.contains('clickable') ||
                o.el.classList.contains('ui-btn') ||
                o.el.classList.contains('grabbable')) {
              objs.push(o);
            }
          }
        });
        const ray = new THREE.Raycaster(getPos(), getDir(), 0, FALLBACK_FAR);
        list = ray.intersectObjects(objs, true);
      }
      for (const hit of list) {
        let el = hit.object ? hit.object.el : null;
        let cur = el;
        while (cur) {
          if (predicate(cur)) {
            return { el: cur, distance: hit.distance, hit: hit };
          }
          cur = cur.parentEl;
        }
      }
      return null;
    };

    const findClickable = function() {
      return findInIntersections(function(el) {
        return el.classList && (el.classList.contains('clickable') ||
                                el.classList.contains('ui-btn'));
      });
    };
    const findBlock = function() {
      return findInIntersections(function(el) {
        return el.id && el.id.indexOf('block-') === 0;
      });
    };

    const atualizarHUD = function() {
      const dbg = document.getElementById('debugAlvo');
      if (!dbg) return;
      const c = findClickable();
      const b = findBlock();
      if (c) {
        const letra = c.el.getAttribute('data-letra') || '?';
        dbg.setAttribute('value', '🎯 CLICK [' + letra + '] ' + c.distance.toFixed(1) + 'm');
      } else if (b) {
        dbg.setAttribute('value', '🎯 ' + b.el.id + ' ' + b.distance.toFixed(1) + 'm');
      } else {
        dbg.setAttribute('value', '🎯 (nada)');
      }
    };

    const startGrab = function() {
      if (grabbed) return;
      const b = findBlock();
      if (!b) return;
      grabbed = b.el;
      const hp = getPos();
      const bp = new THREE.Vector3();
      grabbed.object3D.getWorldPosition(bp);
      offset.copy(bp).sub(hp);
      distAdjust = 0;
      grabbed.setAttribute('material', 'emissive', '#ffaa00');
      grabbed.setAttribute('material', 'emissiveIntensity', '1');
      const dist = offset.length();
      showToast('✋ ' + grabbed.id + ' @ ' + dist.toFixed(1) + 'm', 900);
      if (navigator.vibrate) navigator.vibrate(30);
    };

    const endGrab = function() {
      if (!grabbed) return;
      grabbed.setAttribute('material', 'emissive', '#000000');
      grabbed.setAttribute('material', 'emissiveIntensity', '0');
      savePos(grabbed.id);
      showToast('📍 ' + grabbed.id + ' posicionado', 900);
      if (navigator.vibrate) navigator.vibrate(20);
      grabbed = null;
      distAdjust = 0;
    };

    const doClick = function() {
      const c = findClickable();
      if (!c) {
        showToast('⚠️ Aponte para uma alternativa A–E', 800);
        return;
      }
      c.el.emit('click', { target: c.el, cursorEl: hand });
      if (navigator.vibrate) navigator.vibrate(60);
    };

    this.tick = function() {
      atualizarHUD();
      if (grabbed) {
        const hp = getPos();
        const dir = getDir();
        const target = hp.clone()
          .add(offset)
          .add(dir.clone().multiplyScalar(distAdjust));
        const parent = grabbed.object3D.parent;
        if (parent) {
          const local = parent.worldToLocal(target.clone());
          grabbed.object3D.position.copy(local);
        }
      }
    };

    // ═══════════════ EVENTOS DUPLOS ═══════════════
    // Controle físico
    hand.addEventListener('triggerdown', doClick);
    hand.addEventListener('gripdown', startGrab);
    hand.addEventListener('gripup', endGrab);
    hand.addEventListener('abuttondown', doClick);   // Botão A/X extra
    // Hand tracking
    hand.addEventListener('pinchstarted', function() {
      // Se há clickable no foco → click. Senão → grab.
      const c = findClickable();
      if (c) {
        doClick();
      } else {
        startGrab();
      }
    });
    hand.addEventListener('pinchended', endGrab);

    // Thumbstick (ajuste distância + rotação)
    hand.addEventListener('thumbstickmoved', function(evt) {
      if (!grabbed) return;
      const x = evt.detail.x, y = evt.detail.y;
      if (Math.abs(x) > 0.15) grabbed.object3D.rotation.y += x * 0.03;
      if (Math.abs(y) > 0.15) {
        distAdjust -= y * 0.05;
        distAdjust = Math.max(-8, Math.min(8, distAdjust));
      }
    });

    // ═══════════════ FEEDBACK VISUAL NO LASER ═══════════════
    hand.addEventListener('raycaster-intersection', function(evt) {
      const els = evt.detail.els || [];
      for (const el of els) {
        if (el.classList && (el.classList.contains('clickable') ||
                             el.classList.contains('ui-btn'))) {
          if (!el.dataset.hl) {
            el.dataset.hl = 'true';
            el.setAttribute('material', 'emissive', '#00ff88');
            el.setAttribute('material', 'emissiveIntensity', '0.6');
          }
        }
      }
    });
    hand.addEventListener('raycaster-intersection-cleared', function(evt) {
      const els = evt.detail.clearedEls || [];
      for (const el of els) {
        if (el.dataset && el.dataset.hl) {
          el.setAttribute('material', 'emissive', '#000000');
          el.setAttribute('material', 'emissiveIntensity', '0');
          delete el.dataset.hl;
        }
      }
    });
  }
});

// ═══════════════════════════════════════════════════════════════════
// hand-live: calibrador
// ═══════════════════════════════════════════════════════════════════
AFRAME.registerComponent('hand-live', {
  schema: { hand: { type: 'string', default: 'left' } },
  init: function() {
    this.pinch = false;
    this.grip = false;
    this.el.addEventListener('pinchstarted', () => this.pinch = true);
    this.el.addEventListener('pinchended', () => this.pinch = false);
    this.el.addEventListener('gripdown', () => this.grip = true);
    this.el.addEventListener('gripup', () => this.grip = false);
  },
  tick: function() {
    const tEl = document.getElementById(this.data.hand + 'Data');
    if (!tEl) return;
    const p = this.el.object3D.position;
    const s = this.el.object3D.scale.x;
    const hasTracking = !!this.el.components['hand-tracking-controls'];
    const hasController = !!this.el.components['oculus-touch-controls'];
    let mode = 'CTRL';
    if (hasTracking && !hasController) mode = 'HAND';
    else if (hasTracking && hasController) mode = 'BOTH';
    tEl.setAttribute('value',
      this.data.hand.toUpperCase() + ': ' + mode +
      '\nPos ' + p.x.toFixed(2) + ' ' + p.y.toFixed(2) + ' ' + p.z.toFixed(2) +
      '\nEscala ' + s.toFixed(2) +
      ' | ' + (this.pinch ? 'PINCH' : 'ABERTA') +
      (this.grip ? ' GRIP' : ''));
  }
});

// ═══════════════════════════════════════════════════════════════════
// painel-sistema
// ═══════════════════════════════════════════════════════════════════
AFRAME.registerComponent('painel-sistema', {
  init: function() {
    const rig = document.getElementById('rig');
    const head = document.getElementById('head');
    const left = document.getElementById('leftHand');
    const right = document.getElementById('rightHand');
    const sky = document.getElementById('sky');
    const stars = document.getElementById('stars');
    let handScale = 1, headH = 1.65;

    this.el.querySelectorAll('.calib-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const a = btn.getAttribute('data-action');

        if (a === 'passthrough') { window.enablePassthrough(); return; }
        if (a === 'dark') {
          sky.setAttribute('visible', 'true');
          sky.setAttribute('color', '#050a14'); sky.removeAttribute('src');
          stars.setAttribute('visible', 'false');
          showToast('ESCURO');
        }
        if (a === 'beach') {
          sky.setAttribute('visible', 'true');
          sky.setAttribute('src', 'url(https://cdn.aframe.io/360-image-gallery-boilerplate/img/sechelt.jpg)');
          sky.removeAttribute('color');
          stars.setAttribute('visible', 'false');
          showToast('PRAIA');
        }
        if (a === 'office') {
          sky.setAttribute('visible', 'true');
          sky.setAttribute('src', 'url(https://cdn.aframe.io/360-image-gallery-boilerplate/img/city.jpg)');
          sky.removeAttribute('color');
          stars.setAttribute('visible', 'false');
          showToast('ESCRITÓRIO');
        }
        if (a === 'library') {
          sky.setAttribute('visible', 'true');
          sky.setAttribute('src', 'url(https://cdn.aframe.io/360-image-gallery-boilerplate/img/cubes.jpg)');
          sky.removeAttribute('color');
          stars.setAttribute('visible', 'false');
          showToast('BIBLIOTECA');
        }
        if (a === 'space') {
          sky.setAttribute('visible', 'true');
          sky.setAttribute('color', '#000005'); sky.removeAttribute('src');
          createStars(); stars.setAttribute('visible', 'true');
          showToast('ESPAÇO');
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
          rig.setAttribute('position', '0 0 8');
          rig.setAttribute('rotation', '0 0 0');
          showToast('Posição resetada');
        }
        if (a === 'sairVR') {
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

// ═══════════════════════════════════════════════════════════════════
// Passthrough / Stars / Toast
// ═══════════════════════════════════════════════════════════════════
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
    await renderer.xr.setSession(sess);
    sess.addEventListener('end', () => {
      sceneEl.object3D.background = new THREE.Color(0x050a14);
      renderer.setClearColor(0x050a14, 1);
      document.getElementById('sky').setAttribute('visible', 'true');
    });
    showToast('👁️ PASSTHROUGH ATIVO');
  } catch (err) { showToast('❌ ' + err.message, 4000); }
};

function createStars() {
  const c = document.getElementById('stars');
  c.innerHTML = '';
  for (let i = 0; i < 300; i++) {
    const s = document.createElement('a-sphere');
    const r = 25 + Math.random() * 15;
    const t = Math.random() * Math.PI * 2;
    const p = Math.acos(2 * Math.random() - 1);
    s.setAttribute('position',
      (r * Math.sin(p) * Math.cos(t)) + ' ' +
      (r * Math.sin(p) * Math.sin(t)) + ' ' +
      (r * Math.cos(p)));
    s.setAttribute('radius', (0.03 + Math.random() * 0.08).toString());
    s.setAttribute('color', '#ffffff');
    c.appendChild(s);
  }
}

function showToast(msg, ms) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.style.display = 'block';
  clearTimeout(window._toastT);
  window._toastT = setTimeout(() => { t.style.display = 'none'; }, ms || 1600);
}

// ═══════════════════════════════════════════════════════════════════
// CRIA BLOCO — alternativas com .clickable .ui-btn + geometria explícita
// ═══════════════════════════════════════════════════════════════════
function createBlock(q, i) {
  const cols = 4, spacing = 3.0;
  const x = (i % cols) * spacing - ((cols - 1) * spacing / 2);
  const z = Math.floor(i / cols) * -3.4 - 1.5;
  const y = 1.2 + Math.random() * 0.4;

  const root = document.createElement('a-entity');
  root.setAttribute('id', 'block-' + i);
  root.setAttribute('position', x + ' ' + y + ' ' + z);
  root.setAttribute('class', 'grabbable');
  root.setAttribute('data-materia', q.materia || 'Geral');
  root.setAttribute('geometry', 'primitive: box; width: 2.4; height: 2.2; depth: 0.24');
  root.setAttribute('material', 'color: #13244a; emissive: #000000; emissiveIntensity: 0');

  const title = document.createElement('a-text');
  title.setAttribute('value', (i + 1) + '. ' + q.materia);
  title.setAttribute('color', '#00e5ff');
  title.setAttribute('width', '2.3');
  title.setAttribute('align', 'center');
  title.setAttribute('position', '0 0.85 0.14');
  title.setAttribute('class', 'grabbable');
  root.appendChild(title);

  const qtext = document.createElement('a-text');
  const shortQ = q.pergunta.length > 150 ? q.pergunta.slice(0, 147) + '...' : q.pergunta;
  qtext.setAttribute('value', shortQ);
  qtext.setAttribute('color', 'white');
  qtext.setAttribute('width', '2.2');
  qtext.setAttribute('align', 'center');
  qtext.setAttribute('position', '0 0.45 0.14');
  qtext.setAttribute('wrap-count', '36');
  qtext.setAttribute('class', 'grabbable');
  root.appendChild(qtext);

  q.alternativas.forEach((alt, idx) => {
    const letra = alt.trim().charAt(0).toUpperCase();
    const row = document.createElement('a-entity');
    row.setAttribute('position', '0 ' + (-0.05 - idx * 0.28) + ' 0.15');
    row.setAttribute('class', 'clickable ui-btn');
    row.setAttribute('data-i', i);
    row.setAttribute('data-letra', letra);

    // PLACA com geometria explícita + .clickable .ui-btn
    const bg = document.createElement('a-plane');
    bg.setAttribute('geometry', 'primitive: plane; width: 2.0; height: 0.22');
    bg.setAttribute('material', 'color: #0a1933; emissive: #000000; emissiveIntensity: 0; side: double');
    bg.setAttribute('class', 'clickable ui-btn');

    const txt = document.createElement('a-text');
    txt.setAttribute('value', alt.length > 60 ? alt.slice(0, 57) + '...' : alt);
    txt.setAttribute('color', '#cfe0ff');
    txt.setAttribute('width', '1.9');
    txt.setAttribute('position', '-0.95 0 0.02');
    txt.setAttribute('class', 'clickable ui-btn');

    bg.appendChild(txt);
    row.appendChild(bg);

    // ═══════════════ EVENTO DE CLICK (recebe o .emit('click') do vr-hand) ═══════════════
    row.addEventListener('click', (e) => {
      e.stopPropagation();
      if (root.userData.respondida) return;
      root.userData.respondida = true;
      root.userData.letraEscolhida = letra;
      const ok = letra === q.correta;
      bg.setAttribute('material', 'color', ok ? '#00c853' : '#d50000');
      bg.setAttribute('material', 'emissive', ok ? '#00ff88' : '#ff2222');
      bg.setAttribute('material', 'emissiveIntensity', '0.7');
      updateHUD();
      showToast(ok ? '✅ Correto!' : '❌ Errado (correta: ' + q.correta + ')');
    });

    root.appendChild(row);
  });

  return root;
}

function updateHUD() {
  let total = 0, respondidas = 0;
  document.querySelectorAll('[data-i]').forEach(row => {
    const bg = row.querySelector('a-plane');
    if (!bg) return;
    total++;
    const c = bg.getAttribute('material').color;
    if (c === '#00c853' || c === '#d50000') respondidas++;
  });
  const txt = respondidas + '/' + total;
  const st = document.getElementById('status');
  if (st) st.textContent = txt + ' respondidas';
  const hd = document.getElementById('hudVRText');
  if (hd) hd.setAttribute('value', txt);
}

window.organizarGrade = function() {
  document.querySelectorAll('[id^="block-"]').forEach((b, i) => {
    const cols = 4, sp = 3.0;
    const x = (i % cols) * sp - ((cols - 1) * sp / 2);
    const z = Math.floor(i / cols) * -3.4 - 1.5;
    b.setAttribute('animation',
      'property: position; to: ' + x + ' 1.3 ' + z + '; dur: 800');
  });
  showToast('📐 GRADE');
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
    const baseX = (s - (names.length - 1) / 2) * 6;
    cluster.forEach((b, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      b.setAttribute('animation',
        'property: position; to: ' + (baseX + (col - 0.5) * 2.8) +
        ' 1.5 ' + (-3 - row * 2.8) + '; dur: 900');
    });
  });
  showToast('🎯 POR MATÉRIA (' + names.length + ')');
};

window.espalhar = function() {
  document.querySelectorAll('[id^="block-"]').forEach(b => {
    const x = (Math.random() - 0.5) * 14;
    const z = (Math.random() - 0.5) * 14 - 2;
    const y = 0.8 + Math.random() * 2.5;
    b.setAttribute('animation',
      'property: position; to: ' + x + ' ' + y + ' ' + z + '; dur: 800');
  });
  showToast('🎲 ESPALHADO');
};

const STORAGE_KEY = 'pmsc_arena_layout';
function savePos(id) {
  if (!id) return;
  const el = document.getElementById(id);
  if (!el) return;
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
      const el = document.getElementById(id);
      if (!el) return;
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
  const world = document.getElementById('world');
  if (!world) return;
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
  overflow: hidden; background: #050a14;
  font-family: 'Segoe UI', sans-serif;
}
#hud {
  position: fixed; top: 8px; left: 8px; z-index: 99999;
  background: rgba(0,0,0,0.92); color: #00e5ff;
  border: 1px solid #00e5ff; padding: 10px 14px;
  border-radius: 10px; font-size: 12px; max-width: 480px;
}
#enter {
  position: fixed; bottom: 12px; left: 50%;
  transform: translateX(-50%); z-index: 99999;
  background: linear-gradient(90deg, #00d1ff, #7000ff);
  color: white; border: none; padding: 14px 32px;
  border-radius: 999px; font-weight: 900; font-size: 15px;
  cursor: pointer;
}
#toast {
  position: fixed; bottom: 80px; left: 50%;
  transform: translateX(-50%); z-index: 999999;
  background: rgba(0,0,0,0.95); color: #00ff88;
  border: 2px solid #00ff88; padding: 10px 22px;
  border-radius: 10px; font-size: 14px; font-weight: 700;
  display: none; pointer-events: none;
}
</style>
</head>
<body>

<div id="hud">
  <div style="font-weight:900;color:white;font-size:14px;">__MODO__ — Arena VR</div>
  <b>Grip</b> = pegar à distância · <b>Trigger</b> = responder<br>
  <b>Thumbstick ↑↓</b> = empurrar/afastar · <b>←→</b> = rotacionar<br>
  <div id="status" style="margin-top:6px;color:#00ff88;font-weight:700;">0/__LEN__ respondidas</div>
</div>
<button id="enter">🥽 ENTRAR NO VR</button>
<div id="toast"></div>

<a-scene id="scene"
  background="color: #050a14"
  renderer="antialias: true; colorManagement: true; alpha: true"
  webxr="optionalFeatures: hand-tracking, local-floor, bounded-floor, hit-test, passthrough"
  vr-mode-ui="enabled: true"
  embedded
  style="width: 100%; height: 100vh;">

  <a-sky id="sky" color="#050a14"></a-sky>
  <a-entity id="stars" visible="false"></a-entity>

  <a-entity light="type: ambient; intensity: 0.9"></a-entity>
  <a-entity light="type: directional; intensity: 1.1" position="4 7 4"></a-entity>
  <a-plane rotation="-90 0 0" width="120" height="120" color="#0a1430" opacity="0.6"></a-plane>

  <a-entity id="rig" position="0 0 8" movement-controls="fly: true; speed: 0.3">
    <a-entity id="head" camera look-controls wasd-controls="acceleration: 20" position="0 1.65 0">
      <a-entity position="0 -0.8 -1.1">
        <a-plane width="2.6" height="0.62" color="black" opacity="0.75"></a-plane>
        <a-text id="hudVRText" value="0/__LEN__" color="#00ff88" width="1.9"
          align="center" position="0 0.22 0.01"></a-text>
        <a-text id="debugAlvo" value="🎯 (aguardando)" color="#ffaa00" width="1.9"
          align="center" position="0 0.02 0.01"></a-text>
        <a-text value="Grip=pegar · Trigger=responder · Stick=ajustar" color="#aaccff"
          width="1.9" align="center" position="0 -0.18 0.01"></a-text>
      </a-entity>
    </a-entity>

    <!-- MÃO ESQUERDA: laser-controls (posiciona o controle) + hand-tracking-controls (posiciona a mão) -->
    <a-entity id="leftHand"
      laser-controls="hand: left"
      hand-tracking-controls="hand: left; modelStyle: dots; color: #00d1ff"
      hand-live="hand: left"
      vr-hand
      raycaster="objects: .clickable, .ui-btn, .grabbable; far: 20; interval: 100"
      line="color: #00d1ff; opacity: 0.85">
    </a-entity>

    <!-- MÃO DIREITA -->
    <a-entity id="rightHand"
      laser-controls="hand: right"
      hand-tracking-controls="hand: right; modelStyle: dots; color: #ff8a00"
      hand-live="hand: right"
      vr-hand
      raycaster="objects: .clickable, .ui-btn, .grabbable; far: 20; interval: 100"
      line="color: #ff8a00; opacity: 0.85">
    </a-entity>
  </a-entity>

  <a-entity id="mainPanel" position="0 2.6 -4"
    class="grabbable"
    geometry="primitive: box; width: 5.2; height: 3.0; depth: 0.06"
    material="color: #0a0a0a; opacity: 0.94"
    painel-sistema>
    <a-text value="PMSC 2026 — ARENA VR" color="#00e5ff" width="5.5" align="center" position="0 1.35 0.05"></a-text>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="dark"
      position="-2.0 0.9 0.05" geometry="primitive: plane; width: 0.85; height: 0.26"
      material="color: #1a3a6a"><a-text value="ESCURO" color="white" width="0.9" align="center"></a-text></a-entity>
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="beach"
      position="-1.05 0.9 0.05" geometry="primitive: plane; width: 0.85; height: 0.26"
      material="color: #1a5a6a"><a-text value="PRAIA" color="white" width="0.9" align="center"></a-text></a-entity>
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="office"
      position="-0.1 0.9 0.05" geometry="primitive: plane; width: 0.85; height: 0.26"
      material="color: #2a4a6a"><a-text value="ESCRITÓRIO" color="white" width="0.9" align="center"></a-text></a-entity>
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="library"
      position="0.85 0.9 0.05" geometry="primitive: plane; width: 0.85; height: 0.26"
      material="color: #5a3a1a"><a-text value="BIBLIOTECA" color="white" width="0.9" align="center"></a-text></a-entity>
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="space"
      position="1.8 0.9 0.05" geometry="primitive: plane; width: 0.85; height: 0.26"
      material="color: #2a0a5a"><a-text value="ESPAÇO" color="white" width="0.9" align="center"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="passthrough"
      position="-2.0 0.55 0.05" geometry="primitive: plane; width: 1.05; height: 0.26"
      material="color: #7a1fa2"><a-text value="PASSTHROUGH" color="white" width="1.1" align="center"></a-text></a-entity>
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="organizar"
      position="-0.85 0.55 0.05" geometry="primitive: plane; width: 0.85; height: 0.26"
      material="color: #1a6a3a"><a-text value="ORGANIZAR" color="white" width="0.9" align="center"></a-text></a-entity>
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="porMateria"
      position="0.1 0.55 0.05" geometry="primitive: plane; width: 1.0; height: 0.26"
      material="color: #1a6a5a"><a-text value="POR MATÉRIA" color="white" width="1.05" align="center"></a-text></a-entity>
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="espalhar"
      position="1.1 0.55 0.05" geometry="primitive: plane; width: 0.85; height: 0.26"
      material="color: #6a1a1a"><a-text value="ESPALHAR" color="white" width="0.9" align="center"></a-text></a-entity>
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="salvar"
      position="2.0 0.55 0.05" geometry="primitive: plane; width: 0.7; height: 0.26"
      material="color: #00aa44"><a-text value="SALVAR" color="white" width="0.75" align="center"></a-text></a-entity>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="carregar"
      position="-2.0 0.2 0.05" geometry="primitive: plane; width: 0.95; height: 0.26"
      material="color: #aa8800"><a-text value="CARREGAR" color="white" width="1.0" align="center"></a-text></a-entity>

    <a-text value="Grip=pegar · Trigger=responder · Stick=ajustar"
      color="#ffaa00" width="4.8" align="center" position="0 -0.95 0.05"></a-text>
  </a-entity>

  <a-entity id="calibPanel" position="3.6 2.6 -4"
    class="grabbable"
    geometry="primitive: box; width: 2.0; height: 2.4; depth: 0.06"
    material="color: #111111; opacity: 0.92">
    <a-text value="CALIBRADOR" color="#00ff88" width="2.4" align="center" position="0 1.05 0.05"></a-text>
    <a-text id="leftData" value="LEFT: aguardando" color="#00d1ff" width="1.9"
      align="left" position="-0.85 0.55 0.05" wrap-count="34"></a-text>
    <a-text id="rightData" value="RIGHT: aguardando" color="#ff8a00" width="1.9"
      align="left" position="-0.85 0.15 0.05" wrap-count="34"></a-text>

    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="maoMais"
      position="-0.55 -0.2 0.05" geometry="primitive: plane; width: 0.8; height: 0.24"
      material="color: #2a5a1a"><a-text value="MÃO +" color="white" width="0.85" align="center"></a-text></a-entity>
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="maoMenos"
      position="0.4 -0.2 0.05" geometry="primitive: plane; width: 0.8; height: 0.24"
      material="color: #2a5a1a"><a-text value="MÃO -" color="white" width="0.85" align="center"></a-text></a-entity>
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="alturaMais"
      position="-0.55 -0.5 0.05" geometry="primitive: plane; width: 0.8; height: 0.24"
      material="color: #1a3a6a"><a-text value="ALT +" color="white" width="0.85" align="center"></a-text></a-entity>
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="alturaMenos"
      position="0.4 -0.5 0.05" geometry="primitive: plane; width: 0.8; height: 0.24"
      material="color: #1a3a6a"><a-text value="ALT -" color="white" width="0.85" align="center"></a-text></a-entity>
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="resetPos"
      position="-0.55 -0.8 0.05" geometry="primitive: plane; width: 0.8; height: 0.24"
      material="color: #1a3a6a"><a-text value="RESET POS" color="white" width="0.85" align="center"></a-text></a-entity>
    <a-entity class="grabbable clickable ui-btn calib-btn" data-action="sairVR"
      position="0.4 -0.8 0.05" geometry="primitive: plane; width: 0.8; height: 0.24"
      material="color: #a00000"><a-text value="SAIR VR" color="white" width="0.85" align="center"></a-text></a-entity>
  </a-entity>

  <a-entity id="world"></a-entity>
</a-scene>

</body>
</html>"""

    html = (
        html_template
        .replace("__Q_JSON__", q_json)
        .replace("__MODO__", modo)
        .replace("__LEN__", str(len(safe)))
    )

    embed_with_webxr_permissions(html, height=height)

    if st.button(f"❌ Fechar VR — {modo}", key=f"close_{modo}",
                 use_container_width=True):
        st.session_state.vr_ready = False
        st.rerun()


st.title("🎯 PMSC Arena VR")
st.caption(
    f"✅ {info['arquivo']} · {info['unicas']} questões únicas "
    f"({info['removidas']} duplicatas) · Meta Quest 3/3S"
)

with st.sidebar:
    st.success(f"📚 {info['unicas']} questões únicas")
    if st.button("🔄 Recarregar json.json", use_container_width=True):
        load_json.clear()
        st.rerun()
    st.divider()
    st.subheader("📚 Treino")
    mat = st.selectbox("Matéria", list(banco.keys()))
    maximo = len(banco.get(mat, []))
    if maximo > 0:
        qtd = st.slider("Quantidade", 5, min(20, maximo), min(10, maximo))
        if st.button("Iniciar Treino", use_container_width=True):
            pool = banco.get(mat, [])
            st.session_state.treino = [
                {**q, "materia": mat}
                for q in random.sample(pool, min(qtd, len(pool)))
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
        qs = st.session_state.simulado["questoes"]
        render_vr(qs, modo="SIMULADO", height=950)
    elif st.session_state.treino:
        render_vr(st.session_state.treino, modo="TREINO", height=950)
    else:
        todas = []
        for v in banco.values():
            todas.extend(v)
        random.shuffle(todas)
        render_vr(todas, modo="ARENA", height=950)

with tab_sim:
    if st.session_state.simulado:
        sim = st.session_state.simulado
        qs = sim["questoes"]
        if not sim["finalizado"]:
            rest = max(0, 4 * 3600 - int(time.time() - sim["inicio"]))
            h, m, s = rest // 3600, (rest % 3600) // 60, rest % 60
            st.warning(f"⏱️ **Tempo:** {h:02d}:{m:02d}:{s:02d} · {len(qs)}q")
            with st.form("form_sim"):
                resp = {}
                for i, q in enumerate(qs):
                    st.markdown(f"**{i+1}. [{q.get('materia', '')}]** {q['pergunta']}")
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
                if c2.form_submit_button("✅ Finalizar", type="primary",
                                          use_container_width=True):
                    ac, dets = 0, []
                    for i, q in enumerate(qs):
                        r = resp.get(i, ""); ok = r == q["correta"].upper()
                        if ok: ac += 1
                        dets.append({"pergunta": q["pergunta"], "materia": q.get("materia", ""),
                                     "resposta": r, "correta": q["correta"], "acertou": ok})
                    nota = (ac / len(qs)) * 100
                    st.session_state.hist.append({
                        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
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
