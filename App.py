import streamlit as st
import streamlit.components.v1 as components
import json
import random
import time
import pathlib
from datetime import datetime

st.set_page_config(
    page_title="PMSC 2026 — Arena VR",
    page_icon="🎯",
    layout="wide",
)

DISTRIBUICAO = {
    "Legislação Institucional": 10, "Direito Constitucional": 8,
    "Língua Portuguesa": 8, "Direito Penal Comum": 6,
    "Direito Processual Penal Comum": 6, "Direito Penal Militar": 6,
    "Legislação Especial": 6, "Legislação de Trânsito": 5, "Informática": 5,
}
TOTAL = sum(DISTRIBUICAO.values())


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
    vistos, unicas, rem = set(), [], 0
    for q in lista:
        t = q.get("pergunta", "").strip().lower()
        if not t:
            continue
        if t in vistos:
            rem += 1
            continue
        vistos.add(t)
        unicas.append(q)
    return unicas, rem


@st.cache_data(ttl=30, show_spinner=False)
def load_json():
    candidatos = [
        pathlib.Path(__file__).parent / "json.json",
        pathlib.Path.cwd() / "json.json",
    ]
    for path in candidatos:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    conteudo = f.read()
                parsed = _parse_concatenado(conteudo)
                if not parsed:
                    continue
                total_bruto, removidas = 0, 0
                for mat in list(parsed.keys()):
                    unicas, rem = _deduplicar(parsed[mat])
                    parsed[mat] = unicas
                    total_bruto += len(unicas) + rem
                    removidas += rem
                return parsed, {
                    "arquivo": path.name, "bruto": total_bruto,
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


for k, d in [("simulado", None), ("treino", []), ("hist", []),
             ("vr_ready", False)]:
    if k not in st.session_state:
        st.session_state[k] = d

banco, info = load_json()
if not banco:
    st.error(f"❌ json.json: {info.get('erro', '?')}")
    try:
        st.write("Arquivos:", [f.name for f in pathlib.Path(__file__).parent.iterdir()])
    except Exception:
        pass
    st.stop()

st.title("🎯 PMSC 2026 — Arena VR")
st.caption(
    f"✅ {info['arquivo']} · {info['unicas']}q únicas "
    f"({info['removidas']} duplicatas) · Meta Quest 3S"
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
    qtd = st.slider("Qtd", 5, min(20, maximo) if maximo else 5,
                    min(10, maximo) if maximo else 5)
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
    st.caption(f"{TOTAL} questões oficiais")
    if st.button("Iniciar Simulado 60q", type="primary", use_container_width=True):
        st.session_state.simulado = {
            "questoes": montar_simulado(banco),
            "inicio": time.time(),
            "respostas": {},
            "finalizado": False,
        }
        st.session_state.treino = []
        st.session_state.vr_ready = False
        st.rerun()
    if st.session_state.simulado and not st.session_state.simulado["finalizado"]:
        if st.button("❌ Cancelar", use_container_width=True):
            st.session_state.simulado = None
            st.session_state.vr_ready = False
            st.rerun()
    st.divider()
    st.subheader("📜 Histórico")
    if st.session_state.hist:
        for h in reversed(st.session_state.hist[-5:]):
            st.caption(f"{h['data']} — {h['acertos']}/{h['total']} ({h['nota']}%)")
    else:
        st.caption("Nenhum simulado ainda.")


# ==================================================================
# RENDER VR
# ==================================================================
def render_vr(questoes, modo="ARENA", height=950):
    if not st.session_state.vr_ready:
        st.info(f"{len(questoes)} questões prontas para a arena VR.")
        if st.button(f"🥽 CARREGAR VR — {modo}",
                     type="primary", use_container_width=True):
            st.session_state.vr_ready = True
            st.rerun()
        return

    amostra = questoes[:18]
    safe = [{
        "pergunta": q["pergunta"][:190].replace('"', "'").replace("\n", " "),
        "alternativas": [a[:62].replace('"', "'") for a in q["alternativas"][:5]],
        "correta": q["correta"].upper(),
        "materia": q.get("materia", "Geral")[:22],
    } for q in amostra]
    q_json = json.dumps(safe, ensure_ascii=False).replace("</", "<\\/")

    html = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v7.4.0/dist/aframe-extras.min.js"></script>
<script src="https://unpkg.com/super-hands@3.0.5/dist/super-hands.min.js"></script>
<script>
// ============================================================
// COMPONENTE: vr-hand  (grab/click/rotate customizados)
// Resolve o bug do super-hands: raycast manual que ATRAVESSA
// os textos e encontra o BLOCO INTEIRO mais próximo.
// ============================================================
AFRAME.registerComponent('vr-hand', {
  init: function() {
    const hand = this.el;
    let grabbed = null;
    let grabDist = 0;

    // ---- Helper: acha o elemento mais próximo com a classe ----
    const closestByClass = function(className) {
      const rc = hand.components.raycaster;
      if (!rc || !rc.intersections || rc.intersections.length === 0) return null;
      for (let i = 0; i < rc.intersections.length; i++) {
        const hit = rc.intersections[i];
        let el = hit.object.el;
        while (el) {
          if (el.classList && el.classList.contains(className)) {
            return { el: el, distance: hit.distance };
          }
          el = el.parentEl;
        }
      }
      return null;
    };

    // ---- GRAB ----
    const startGrab = function() {
      if (grabbed) return;
      const found = closestByClass('grabbable');
      if (!found) { showToast('⚠️ Nada grabbable à frente'); return; }
      grabbed = found.el;
      grabDist = found.distance;

      // Feedback
      grabbed.setAttribute('material', 'emissive', '#ffaa00');
      grabbed.setAttribute('material', 'emissiveIntensity', '1');
      const idCurto = (grabbed.id || '').substring(0, 12);
      showToast('✋ Segurando ' + idCurto, 900);
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
      grabDist = 0;
    };

    // ---- CLICK em alternativa ----
    const doClick = function() {
      const found = closestByClass('clickable');
      if (!found) return;
      found.el.emit('click', { target: found.el });
      if (navigator.vibrate) navigator.vibrate(40);
    };

    // ---- Listeners (controle + hand tracking) ----
    hand.addEventListener('gripdown', startGrab);
    hand.addEventListener('gripup', endGrab);
    hand.addEventListener('pinchstarted', startGrab);
    hand.addEventListener('pinchended', endGrab);
    hand.addEventListener('triggerdown', doClick);

    // ---- Thumbstick: rotaciona enquanto segura ----
    hand.addEventListener('thumbstickmoved', function(evt) {
      if (!grabbed) return;
      const x = evt.detail.x;
      const y = evt.detail.y;
      if (Math.abs(x) > 0.15) grabbed.object3D.rotation.y += x * 0.03;
      if (Math.abs(y) > 0.15) grabbed.object3D.rotation.x += y * 0.03;
    });

    // ---- Loop: move o objeto agarrado ----
    this.tick = function() {
      if (!grabbed) return;
      const dir = new THREE.Vector3();
      hand.object3D.getWorldDirection(dir);
      const pos = new THREE.Vector3();
      hand.object3D.getWorldPosition(pos);
      const target = pos.clone().add(dir.clone().multiplyScalar(grabDist));
      const parent = grabbed.object3D.parent;
      if (parent) {
        const local = parent.worldToLocal(target.clone());
        grabbed.object3D.position.copy(local);
      }
    };
  }
});

// ============================================================
// COMPONENTE: hand-live (calibrador em tempo real)
// ============================================================
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
    const isTracking = !!this.el.components['hand-tracking-controls'];
    const tracking = isTracking ? 'TRACKING' : 'CONTROLE';
    tEl.setAttribute('value',
      this.data.hand.toUpperCase() + ': ' + tracking +
      '\nPos ' + p.x.toFixed(2) + ' ' + p.y.toFixed(2) + ' ' + p.z.toFixed(2) +
      '\nEscala ' + s.toFixed(2) +
      ' | ' + (this.pinch ? 'PINCH' : 'ABERTA') +
      (this.grip ? ' GRIP' : '')
    );
  }
});

// ============================================================
// SISTEMA DO PAINEL (fundo, organizar, calibração)
// ============================================================
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
          sky.setAttribute('color', '#050a14');
          sky.removeAttribute('src');
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
          sky.setAttribute('color', '#000005');
          sky.removeAttribute('src');
          createStars();
          stars.setAttribute('visible', 'true');
          showToast('ESPAÇO');
        }

        if (a === 'organizar') window.organizarGrade();
        if (a === 'porMateria') window.organizarPorMateria();
        if (a === 'espalhar') window.espalhar();
        if (a === 'salvar') window.salvarLayout();
        if (a === 'carregar') window.carregarLayout();

        if (a === 'maoMais') {
          handScale += 0.1;
          const v = handScale + ' ' + handScale + ' ' + handScale;
          left.setAttribute('scale', v);
          right.setAttribute('scale', v);
          showToast('Mão + (escala ' + handScale.toFixed(1) + ')');
        }
        if (a === 'maoMenos') {
          handScale = Math.max(0.2, handScale - 0.1);
          const v = handScale + ' ' + handScale + ' ' + handScale;
          left.setAttribute('scale', v);
          right.setAttribute('scale', v);
          showToast('Mão - (escala ' + handScale.toFixed(1) + ')');
        }
        if (a === 'alturaMais') {
          headH += 0.1;
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

// ============================================================
// PASSTHROUGH
// ============================================================
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
  } catch (err) {
    showToast('❌ ' + err.message, 4000);
  }
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

// ============================================================
// CRIA BLOCO DE QUESTÃO  (o PARENT é a caixa grabbable)
// ============================================================
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

  // Título
  const title = document.createElement('a-text');
  title.setAttribute('value', (i + 1) + '. ' + q.materia);
  title.setAttribute('color', '#00e5ff');
  title.setAttribute('width', '2.3');
  title.setAttribute('align', 'center');
  title.setAttribute('position', '0 0.85 0.14');
  root.appendChild(title);

  // Pergunta
  const qtext = document.createElement('a-text');
  const shortQ = q.pergunta.length > 150
    ? q.pergunta.slice(0, 147) + '...' : q.pergunta;
  qtext.setAttribute('value', shortQ);
  qtext.setAttribute('color', 'white');
  qtext.setAttribute('width', '2.2');
  qtext.setAttribute('align', 'center');
  qtext.setAttribute('position', '0 0.45 0.14');
  qtext.setAttribute('wrap-count', '36');
  root.appendChild(qtext);

  // Alternativas
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
      if (root.userData.respondida) return;
      root.userData.respondida = true;
      root.userData.letraEscolhida = letra;
      const ok = letra === q.correta;
      bg.setAttribute('color', ok ? '#00c853' : '#d50000');
      updateHUD();
      showToast(ok ? '✅ Correto!' : '❌ Errado');
    });

    root.appendChild(row);
  });

  return root;
}

// ============================================================
// HUD
// ============================================================
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
  document.getElementById('status').textContent = txt + ' respondidas';
  document.getElementById('hudVRText')?.setAttribute('value', txt);
}

// ============================================================
// ORGANIZAÇÃO
// ============================================================
window.organizarGrade = function() {
  const blocks = document.querySelectorAll('[id^="block-"]');
  blocks.forEach((b, i) => {
    const cols = 4, sp = 3.0;
    const x = (i % cols) * sp - ((cols - 1) * sp / 2);
    const z = Math.floor(i / cols) * -3.4 - 1.5;
    b.setAttribute('animation',
      'property: position; to: ' + x + ' 1.3 ' + z + '; dur: 800');
  });
  showToast('📐 GRADE organizada');
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
        'property: position; to: ' +
        (baseX + (col - 0.5) * 2.8) + ' 1.5 ' +
        (-3 - row * 2.8) + '; dur: 900');
    });
  });
  showToast('🎯 POR MATÉRIA (' + names.length + ' clusters)');
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

// ============================================================
// SAVE / LOAD
// ============================================================
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
  } catch (e) {
    showToast('❌ Erro ao carregar');
  }
};

// ============================================================
// INIT
// ============================================================
const QUESTIONS = __Q_JSON__;

window.addEventListener('load', () => {
  const world = document.getElementById('world');
  if (!world) return;
  QUESTIONS.forEach((q, i) => world.appendChild(createBlock(q, i)));
  setTimeout(updateHUD, 500);
});
</script>

<style>
html, body {
  margin: 0; padding: 0; width: 100%; height: __HEIGHT__px;
  overflow: hidden; background: #050a14;
  font-family: 'Segoe UI', sans-serif;
}
#hud {
  position: fixed; top: 8px; left: 8px; z-index: 99999;
  background: rgba(0,0,0,0.92); color: #00e5ff;
  border: 1px solid #00e5ff; padding: 10px 14px;
  border-radius: 10px; font-size: 12px; max-width: 420px;
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
  <b>Grip</b> = mover bloco · <b>Trigger</b> = responder · <b>Thumbstick</b> = rotacionar<br>
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
  style="width: 100%; height: __HEIGHT__px;">

  <a-sky id="sky" color="#050a14"></a-sky>
  <a-entity id="stars" visible="false"></a-entity>

  <a-entity light="type: ambient; intensity: 0.9"></a-entity>
  <a-entity light="type: directional; intensity: 1.1" position="4 7 4"></a-entity>
  <a-plane rotation="-90 0 0" width="120" height="120" color="#0a1430" opacity="0.6"></a-plane>

  <a-entity id="rig" position="0 0 8" movement-controls="fly: true; speed: 0.3">
    <a-entity id="head" camera look-controls wasd-controls="acceleration: 20" position="0 1.65 0">
      <a-entity position="0 -0.6 -1.1">
        <a-plane width="1.6" height="0.32" color="black" opacity="0.75"></a-plane>
        <a-text id="hudVRText" value="0/__LEN__" color="#00ff88" width="1.9"
          align="center" position="0 0 0.01"></a-text>
      </a-entity>
    </a-entity>

    <!-- MÃO ESQUERDA — vr-hand custom + laser + tracking -->
    <a-entity id="leftHand"
      laser-controls="hand: left"
      hand-tracking-controls="hand: left"
      hand-live="hand: left"
      vr-hand
      raycaster="objects: .grabbable, .clickable; far: 25"
      line="color: #00d1ff; opacity: 0.9">
    </a-entity>

    <!-- MÃO DIREITA -->
    <a-entity id="rightHand"
      laser-controls="hand: right"
      hand-tracking-controls="hand: right"
      hand-live="hand: right"
      vr-hand
      raycaster="objects: .grabbable, .clickable; far: 25"
      line="color: #ff8a00; opacity: 0.9">
    </a-entity>
  </a-entity>

  <!-- ========== PAINEL PRINCIPAL (movível + filhos movíveis) ========== -->
  <a-entity id="mainPanel" position="0 2.6 -4"
    class="grabbable"
    geometry="primitive: box; width: 5.2; height: 3.0; depth: 0.06"
    material="color: #0a0a0a; opacity: 0.94"
    painel-sistema>
    <a-text value="PMSC 2026 — ARENA VR" color="#00e5ff" width="5.5" align="center" position="0 1.35 0.05"></a-text>

    <!-- Fundos -->
    <a-entity class="grabbable clickable calib-btn" data-action="dark"
      position="-2.0 0.9 0.05" geometry="primitive: plane; width: 0.85; height: 0.26"
      material="color: #1a3a6a">
      <a-text value="ESCURO" color="white" width="0.9" align="center"></a-text>
    </a-entity>
    <a-entity class="grabbable clickable calib-btn" data-action="beach"
      position="-1.05 0.9 0.05" geometry="primitive: plane; width: 0.85; height: 0.26"
      material="color: #1a5a6a">
      <a-text value="PRAIA" color="white" width="0.9" align="center"></a-text>
    </a-entity>
    <a-entity class="grabbable clickable calib-btn" data-action="office"
      position="-0.1 0.9 0.05" geometry="primitive: plane; width: 0.85; height: 0.26"
      material="color: #2a4a6a">
      <a-text value="ESCRITÓRIO" color="white" width="0.9" align="center"></a-text>
    </a-entity>
    <a-entity class="grabbable clickable calib-btn" data-action="library"
      position="0.85 0.9 0.05" geometry="primitive: plane; width: 0.85; height: 0.26"
      material="color: #5a3a1a">
      <a-text value="BIBLIOTECA" color="white" width="0.9" align="center"></a-text>
    </a-entity>
    <a-entity class="grabbable clickable calib-btn" data-action="space"
      position="1.8 0.9 0.05" geometry="primitive: plane; width: 0.85; height: 0.26"
      material="color: #2a0a5a">
      <a-text value="ESPAÇO" color="white" width="0.9" align="center"></a-text>
    </a-entity>

    <!-- Passthrough + organizar -->
    <a-entity class="grabbable clickable calib-btn" data-action="passthrough"
      position="-2.0 0.55 0.05" geometry="primitive: plane; width: 1.05; height: 0.26"
      material="color: #7a1fa2">
      <a-text value="PASSTHROUGH" color="white" width="1.1" align="center"></a-text>
    </a-entity>
    <a-entity class="grabbable clickable calib-btn" data-action="organizar"
      position="-0.85 0.55 0.05" geometry="primitive: plane; width: 0.85; height: 0.26"
      material="color: #1a6a3a">
      <a-text value="ORGANIZAR" color="white" width="0.9" align="center"></a-text>
    </a-entity>
    <a-entity class="grabbable clickable calib-btn" data-action="porMateria"
      position="0.1 0.55 0.05" geometry="primitive: plane; width: 1.0; height: 0.26"
      material="color: #1a6a5a">
      <a-text value="POR MATÉRIA" color="white" width="1.05" align="center"></a-text>
    </a-entity>
    <a-entity class="grabbable clickable calib-btn" data-action="espalhar"
      position="1.1 0.55 0.05" geometry="primitive: plane; width: 0.85; height: 0.26"
      material="color: #6a1a1a">
      <a-text value="ESPALHAR" color="white" width="0.9" align="center"></a-text>
    </a-entity>
    <a-entity class="grabbable clickable calib-btn" data-action="salvar"
      position="2.0 0.55 0.05" geometry="primitive: plane; width: 0.7; height: 0.26"
      material="color: #00aa44">
      <a-text value="SALVAR" color="white" width="0.75" align="center"></a-text>
    </a-entity>

    <!-- Carregar + dica -->
    <a-entity class="grabbable clickable calib-btn" data-action="carregar"
      position="-2.0 0.2 0.05" geometry="primitive: plane; width: 0.95; height: 0.26"
      material="color: #aa8800">
      <a-text value="CARREGAR" color="white" width="1.0" align="center"></a-text>
    </a-entity>

    <a-text value="Grip = mover bloco · Trigger = responder · Thumbstick = rotacionar"
      color="#ffaa00" width="4.8" align="center" position="0 -0.95 0.05"></a-text>
  </a-entity>

  <!-- ========== CALIBRADOR ========== -->
  <a-entity id="calibPanel" position="3.6 2.6 -4"
    class="grabbable"
    geometry="primitive: box; width: 2.0; height: 2.4; depth: 0.06"
    material="color: #111111; opacity: 0.92">
    <a-text value="CALIBRADOR" color="#00ff88" width="2.4"
      align="center" position="0 1.05 0.05"></a-text>
    <a-text id="leftData" value="LEFT: aguardando" color="#00d1ff"
      width="1.9" align="left" position="-0.85 0.55 0.05" wrap-count="34"></a-text>
    <a-text id="rightData" value="RIGHT: aguardando" color="#ff8a00"
      width="1.9" align="left" position="-0.85 0.15 0.05" wrap-count="34"></a-text>

    <a-entity class="grabbable clickable calib-btn" data-action="maoMais"
      position="-0.55 -0.2 0.05" geometry="primitive: plane; width: 0.8; height: 0.24"
      material="color: #2a5a1a">
      <a-text value="MÃO +" color="white" width="0.85" align="center"></a-text>
    </a-entity>
    <a-entity class="grabbable clickable calib-btn" data-action="maoMenos"
      position="0.4 -0.2 0.05" geometry="primitive: plane; width: 0.8; height: 0.24"
      material="color: #2a5a1a">
      <a-text value="MÃO -" color="white" width="0.85" align="center"></a-text>
    </a-entity>
    <a-entity class="grabbable clickable calib-btn" data-action="alturaMais"
      position="-0.55 -0.5 0.05" geometry="primitive: plane; width: 0.8; height: 0.24"
      material="color: #1a3a6a">
      <a-text value="ALT +" color="white" width="0.85" align="center"></a-text>
    </a-entity>
    <a-entity class="grabbable clickable calib-btn" data-action="alturaMenos"
      position="0.4 -0.5 0.05" geometry="primitive: plane; width: 0.8; height: 0.24"
      material="color: #1a3a6a">
      <a-text value="ALT -" color="white" width="0.85" align="center"></a-text>
    </a-entity>
    <a-entity class="grabbable clickable calib-btn" data-action="resetPos"
      position="-0.55 -0.8 0.05" geometry="primitive: plane; width: 0.8; height: 0.24"
      material="color: #1a3a6a">
      <a-text value="RESET POS" color="white" width="0.85" align="center"></a-text>
    </a-entity>
    <a-entity class="grabbable clickable calib-btn" data-action="sairVR"
      position="0.4 -0.8 0.05" geometry="primitive: plane; width: 0.8; height: 0.24"
      material="color: #a00000">
      <a-text value="SAIR VR" color="white" width="0.85" align="center"></a-text>
    </a-entity>
  </a-entity>

  <a-entity id="world"></a-entity>
</a-scene>

<script>
document.getElementById('enter').addEventListener('click', () => {
  document.querySelector('a-scene').enterVR().catch(e => showToast('❌ ' + e.message));
});
</script>
</body>
</html>
"""

    html = (html
            .replace("__Q_JSON__", q_json)
            .replace("__MODO__", modo)
            .replace("__LEN__", str(len(safe)))
            .replace("__HEIGHT__", str(height)))

    components.html(html, height=height, scrolling=False)

    if st.button(f"❌ Fechar VR — {modo}", key=f"close_{modo}",
                 use_container_width=True):
        st.session_state.vr_ready = False
        st.rerun()


# ==================================================================
# TABS
# ==================================================================
tab_vr, tab_sim = st.tabs(["🥽 Arena VR", "📝 Simulado"])

with tab_vr:
    if st.session_state.simulado:
        qs = st.session_state.simulado["questoes"]
        st.markdown(f"### Simulado ({len(qs)} questões)")
        render_vr(qs, modo="SIMULADO", height=950)
    elif st.session_state.treino:
        st.markdown(f"### Treino ({len(st.session_state.treino)} questões)")
        render_vr(st.session_state.treino, modo="TREINO", height=950)
    else:
        todas = []
        for v in banco.values():
            todas.extend(v)
        random.shuffle(todas)
        st.markdown("### Arena Livre")
        render_vr(todas, modo="ARENA", height=950)

with tab_sim:
    if st.session_state.simulado:
        sim = st.session_state.simulado
        qs = sim["questoes"]
        if not sim["finalizado"]:
            rest = max(0, 4 * 3600 - int(time.time() - sim["inicio"]))
            h, m, s = rest // 3600, (rest % 3600) // 60, rest % 60
            st.warning(f"⏱️ {h:02d}:{m:02d}:{s:02d} · {len(qs)}q")
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
                        r = resp.get(i, "")
                        ok = r == q["correta"].upper()
                        if ok:
                            ac += 1
                        dets.append({
                            "pergunta": q["pergunta"],
                            "materia": q.get("materia", ""),
                            "resposta": r, "correta": q["correta"], "acertou": ok,
                        })
                    nota = (ac / len(qs)) * 100
                    st.session_state.hist.append({
                        "data": datetime.now().strftime("%d/%m %H:%M"),
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
                c3.metric("🏁 Status",
                          "APROVADO ✅" if ult["aprovado"] else "REPROVADO ❌")
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
