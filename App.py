"""
PMSC Arena VR — Versão Final Otimizada (v12)
Backend: Streamlit + normalização gramatical + loader tolerante
Frontend: A-Frame com FFR 1.0, canvas textures, UV math, flat shader
Target: Meta Quest 3/3S a 72/90 FPS
"""
import streamlit as st
import streamlit.components.v1 as components
import json, random, time, pathlib, re, html as html_module
from datetime import datetime

st.set_page_config(page_title="PMSC Arena VR", page_icon="🎯", layout="wide")

# ═══════════════════════════════════════════════════════════════════════
# DISTRIBUIÇÃO OFICIAL AOCP
# ═══════════════════════════════════════════════════════════════════════
DISTRIBUICAO = {
    "Legislação Institucional": 10, "Direito Constitucional": 8,
    "Língua Portuguesa": 8, "Direito Penal Comum": 6,
    "Direito Processual Penal Comum": 6, "Direito Penal Militar": 6,
    "Legislação Especial": 6, "Legislação de Trânsito": 5, "Informática": 5,
}
TOTAL_OFICIAL = sum(DISTRIBUICAO.values())  # 60


# ═══════════════════════════════════════════════════════════════════════
# NORMALIZAÇÃO GRAMATICAL
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
# PARSER TOLERANTE
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


# ═══════════════════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════════════════
for k, d in [("simulado", None), ("treino", []), ("hist", []), ("vr_ready", False)]:
    if k not in st.session_state: st.session_state[k] = d

banco, info = load_json()
if not banco:
    st.error(f"❌ Erro: {info.get('erro', '?')}")
    try: st.write("Arquivos:", [f.name for f in pathlib.Path(__file__).parent.iterdir()])
    except Exception: pass
    st.stop()


# ═══════════════════════════════════════════════════════════════════════
# EMBED COM PERMISSÕES WEBXR
# ═══════════════════════════════════════════════════════════════════════
def embed_with_webxr_permissions(inner_html, height=950):
    escaped = html_module.escape(inner_html, quote=True)
    wrapper = r'''<!DOCTYPE html><html><head><meta charset="utf-8">
<style>html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:#060913}
iframe{width:100%;height:100%;border:none;display:block}</style></head><body>
<iframe srcdoc="__INNER__"
 allow="xr-spatial-tracking; camera; microphone; accelerometer; gyroscope; fullscreen; autoplay"
 style="width:100%;height:100%;border:none;"></iframe></body></html>'''
    components.html(wrapper.replace("__INNER__", escaped), height=height, scrolling=False)


# ═══════════════════════════════════════════════════════════════════════
# RENDER VR — ENGINE OTIMIZADA
# ═══════════════════════════════════════════════════════════════════════
def render_vr(questoes, modo="ARENA", height=950):
    if not st.session_state.vr_ready:
        st.info(f"{len(questoes)} questões prontas.")
        if st.button(f"🥽 CARREGAR VR — {modo}", type="primary", use_container_width=True):
            st.session_state.vr_ready = True
            st.rerun()
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
<title>PMSC Engine Otimizada</title>
<script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v7.4.0/dist/aframe-extras.min.js"></script>
<script>
// FFR programático
function setupFFR() {
  const scene = document.querySelector('a-scene');
  if (!scene || !scene.renderer || !scene.renderer.xr) return;
  try { scene.renderer.xr.setFoveation(1.0); console.log('[FFR] 1.0'); }
  catch (e) { console.warn('[FFR]', e.message); }
}
document.addEventListener('DOMContentLoaded', () => {
  const scene = document.querySelector('a-scene');
  if (!scene) return;
  ['loaded', 'enter-vr', 'renderstart'].forEach(evt => {
    scene.addEventListener(evt, setupFFR);
  });
});

// vr-hand
AFRAME.registerComponent('vr-hand', {
  init: function() {
    const hand = this.el;
    const raycaster = new THREE.Raycaster();
    raycaster.far = 20;
    let grabbed = null;
    let grabOffset = new THREE.Vector3();
    let grabDistAdj = 0;
    let currentTarget = null;
    let lastRaycast = 0;
    const _pos = new THREE.Vector3(), _dir = new THREE.Vector3();
    const _quat = new THREE.Quaternion(), _target = new THREE.Vector3();
    const _local = new THREE.Vector3(), _bp = new THREE.Vector3();
    const _clickables = [];

    const getPos = () => { hand.object3D.getWorldPosition(_pos); return _pos; };
    const getDir = () => {
      hand.object3D.getWorldQuaternion(_quat);
      return _dir.set(0, 0, -1).applyQuaternion(_quat).normalize();
    };

    this.el.sceneEl.addEventListener('loaded', () => {
      _clickables.length = 0;
      hand.sceneEl.object3D.traverse(o => {
        if (o.userData && o.userData.isClickable) _clickables.push(o);
      });
    });

    const doRaycast = () => {
      if (grabbed) return;
      raycaster.set(getPos(), getDir());
      const hits = raycaster.intersectObjects(_clickables, false);
      currentTarget = null;
      if (hits.length === 0) return;
      const hit = hits[0], mesh = hit.object;
      if (mesh.userData.type === 'card') {
        currentTarget = { mesh, altIdx: cardHitFromUV(hit.uv), isCard: true };
      } else if (mesh.userData.type === 'panel') {
        currentTarget = { mesh, btn: panelHitFromUV(hit.uv, mesh.userData.buttons), isPanel: true };
      }
    };

    const doClick = () => {
      if (!currentTarget) return;
      if (currentTarget.isCard && currentTarget.altIdx >= 0) {
        handleCardClick(currentTarget.mesh, currentTarget.altIdx);
      } else if (currentTarget.isPanel && currentTarget.btn) {
        handlePanelClick(currentTarget.mesh, currentTarget.btn);
      }
    };

    const startGrab = () => {
      if (!currentTarget || !currentTarget.isCard) return;
      grabbed = currentTarget.mesh;
      const hp = getPos();
      grabbed.getWorldPosition(_bp);
      grabOffset.copy(_bp).sub(hp);
      grabDistAdj = 0;
      grabbed.material.color.setHex(0x00d1ff);
      showToast('✋ block-' + grabbed.userData.state.index, 700);
      if (navigator.vibrate) navigator.vibrate(30);
    };

    const endGrab = () => {
      if (!grabbed) return;
      grabbed.material.color.setHex(0xffffff);
      saveCardPos(grabbed);
      showToast('📍 posicionado', 700);
      if (navigator.vibrate) navigator.vibrate(20);
      grabbed = null; grabDistAdj = 0;
    };

    this.tick = (time) => {
      if (time - lastRaycast > 60) { lastRaycast = time; doRaycast(); }
      if (grabbed) {
        const hp = getPos(), dir = getDir();
        _target.copy(hp).add(grabOffset).addScaledVector(dir, grabDistAdj);
        const parent = grabbed.parent;
        if (parent) {
          parent.worldToLocal(_local.copy(_target));
          grabbed.position.copy(_local);
        }
      }
    };

    hand.addEventListener('triggerdown', doClick);
    hand.addEventListener('gripdown', startGrab);
    hand.addEventListener('gripup', endGrab);
    hand.addEventListener('abuttondown', doClick);
    hand.addEventListener('pinchstarted', () => {
      if (currentTarget && (currentTarget.altIdx >= 0 || currentTarget.isPanel)) doClick();
      else startGrab();
    });
    hand.addEventListener('pinchended', endGrab);
    hand.addEventListener('thumbstickmoved', (evt) => {
      if (!grabbed) return;
      const { x, y } = evt.detail;
      if (Math.abs(x) > 0.15) grabbed.rotation.y += x * 0.03;
      if (Math.abs(y) > 0.15) {
        grabDistAdj -= y * 0.05;
        grabDistAdj = Math.max(-8, Math.min(8, grabDistAdj));
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

// CARTÃO VIA CANVAS
const CARD_SIZE = 1024;
const CARD_ALT_START = 500;
const CARD_ALT_HEIGHT = 100;

function cardHitFromUV(uv) {
  const cy = (1 - uv.y) * CARD_SIZE;
  if (cy < CARD_ALT_START || cy > CARD_ALT_START + 5 * CARD_ALT_HEIGHT) return -1;
  const idx = Math.floor((cy - CARD_ALT_START) / CARD_ALT_HEIGHT);
  return (idx >= 0 && idx < 5) ? idx : -1;
}

function wrapText(ctx, text, x, y, maxWidth, lineHeight, maxLines) {
  const words = text.split(' ');
  let line = '', lineCount = 0;
  for (let i = 0; i < words.length; i++) {
    const test = line + words[i] + ' ';
    if (ctx.measureText(test).width > maxWidth && line) {
      ctx.fillText(line, x, y);
      line = words[i] + ' ';
      y += lineHeight;
      lineCount++;
      if (lineCount >= maxLines - 1) {
        ctx.fillText(line + '...', x, y);
        return;
      }
    } else { line = test; }
  }
  if (line) ctx.fillText(line, x, y);
}

function createCard(q, i) {
  const canvas = document.createElement('canvas');
  canvas.width = CARD_SIZE; canvas.height = CARD_SIZE;
  const ctx = canvas.getContext('2d', { alpha: false });

  const state = {
    q, index: i, hoverIdx: -1, selectedIdx: -1,
    respondida: false, isCorreta: null, letraEscolhida: null,
  };

  function draw() {
    const grad = ctx.createLinearGradient(0, 0, CARD_SIZE, CARD_SIZE);
    grad.addColorStop(0, '#060913');
    grad.addColorStop(1, '#0a1520');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, CARD_SIZE, CARD_SIZE);

    ctx.strokeStyle = 'rgba(0,209,255,0.04)';
    ctx.lineWidth = 1;
    for (let gx = 0; gx < CARD_SIZE; gx += 64) {
      ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, CARD_SIZE); ctx.stroke();
    }
    for (let gy = 0; gy < CARD_SIZE; gy += 64) {
      ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(CARD_SIZE, gy); ctx.stroke();
    }

    ctx.strokeStyle = '#00d1ff';
    ctx.lineWidth = 8;
    ctx.strokeRect(4, 4, CARD_SIZE - 8, CARD_SIZE - 8);

    ctx.lineWidth = 14;
    const cs = 50;
    ctx.beginPath(); ctx.moveTo(20, 20 + cs); ctx.lineTo(20, 20); ctx.lineTo(20 + cs, 20); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(CARD_SIZE - 20 - cs, 20); ctx.lineTo(CARD_SIZE - 20, 20); ctx.lineTo(CARD_SIZE - 20, 20 + cs); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(20, CARD_SIZE - 20 - cs); ctx.lineTo(20, CARD_SIZE - 20); ctx.lineTo(20 + cs, CARD_SIZE - 20); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(CARD_SIZE - 20 - cs, CARD_SIZE - 20); ctx.lineTo(CARD_SIZE - 20, CARD_SIZE - 20); ctx.lineTo(CARD_SIZE - 20, CARD_SIZE - 20 - cs); ctx.stroke();

    ctx.fillStyle = '#00d1ff';
    ctx.font = 'bold 40px Segoe UI, Arial, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('▸ ' + (i + 1) + '. ' + q.materia.toUpperCase(), 50, 90);

    ctx.strokeStyle = 'rgba(0,209,255,0.4)';
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(50, 115); ctx.lineTo(CARD_SIZE - 50, 115); ctx.stroke();

    ctx.fillStyle = '#e8f4ff';
    ctx.font = '30px Segoe UI, Arial, sans-serif';
    wrapText(ctx, q.pergunta, 50, 175, CARD_SIZE - 100, 40, 8);

    q.alternativas.forEach((alt, idx) => {
      const yBase = CARD_ALT_START + idx * CARD_ALT_HEIGHT;
      const isHover = (state.hoverIdx === idx && !state.respondida);
      const isSelected = (state.respondida && state.selectedIdx === idx);

      if (isSelected) {
        ctx.fillStyle = state.isCorreta ? '#00aa55' : '#aa2222';
      } else if (isHover) {
        ctx.fillStyle = 'rgba(0,209,255,0.20)';
      } else {
        ctx.fillStyle = 'rgba(10,21,32,0.7)';
      }
      ctx.fillRect(45, yBase + 6, CARD_SIZE - 90, CARD_ALT_HEIGHT - 12);

      ctx.strokeStyle = isHover ? '#00d1ff' : 'rgba(0,209,255,0.25)';
      ctx.lineWidth = isHover ? 3 : 1;
      ctx.strokeRect(45, yBase + 6, CARD_SIZE - 90, CARD_ALT_HEIGHT - 12);

      ctx.fillStyle = isSelected ? '#ffffff' : '#b8d4e8';
      ctx.font = '26px Segoe UI, Arial, sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(alt.length > 68 ? alt.slice(0, 65) + '...' : alt, 65, yBase + 62);
    });

    if (state.respondida) {
      ctx.fillStyle = state.isCorreta ? '#00ff88' : '#ff4444';
      ctx.font = 'bold 44px Segoe UI, Arial';
      ctx.textAlign = 'right';
      ctx.fillText(state.isCorreta ? '✓' : '✗', CARD_SIZE - 50, 90);
    }
  }

  draw();

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = false;
  texture.anisotropy = 1;

  const material = new THREE.MeshBasicMaterial({
    map: texture, transparent: false, side: THREE.FrontSide,
    depthWrite: true, depthTest: true,
  });

  const geometry = new THREE.PlaneGeometry(2.2, 2.2, 1, 1);
  const mesh = new THREE.Mesh(geometry, material);

  const cols = 4, spacing = 2.6;
  mesh.position.set(
    (i % cols) * spacing - ((cols - 1) * spacing / 2),
    1.6,
    Math.floor(i / cols) * -spacing - 2.5
  );

  mesh.userData = {
    type: 'card', isClickable: true, state, canvas, ctx, texture, redraw: draw,
  };

  return mesh;
}

// PAINEL VIA CANVAS
const PANEL_W = 1024, PANEL_H = 768;

function createPanel(width, height, actions, title) {
  const canvas = document.createElement('canvas');
  canvas.width = PANEL_W; canvas.height = PANEL_H;
  const ctx = canvas.getContext('2d', { alpha: false });

  const cols = 4;
  const rows = Math.ceil(actions.length / cols);
  const margin = 30, titleH = 100;
  const cellW = (PANEL_W - margin * 2) / cols;
  const cellH = (PANEL_H - titleH - margin) / rows;

  const buttons = actions.map((action, i) => {
    if (!action) return null;
    const col = i % cols, row = Math.floor(i / cols);
    const x1 = margin + col * cellW + 6;
    const y1 = titleH + row * cellH + 6;
    const x2 = x1 + cellW - 12;
    const y2 = y1 + cellH - 12;
    return { action, label: action.label, rect: [x1, y1, x2, y2] };
  }).filter(Boolean);

  function draw() {
    ctx.fillStyle = 'rgba(6,9,19,0.96)';
    ctx.fillRect(0, 0, PANEL_W, PANEL_H);

    ctx.strokeStyle = 'rgba(0,209,255,0.05)';
    ctx.lineWidth = 1;
    for (let gx = 0; gx < PANEL_W; gx += 64) {
      ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, PANEL_H); ctx.stroke();
    }
    for (let gy = 0; gy < PANEL_H; gy += 64) {
      ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(PANEL_W, gy); ctx.stroke();
    }

    ctx.strokeStyle = '#00d1ff';
    ctx.lineWidth = 6;
    ctx.strokeRect(3, 3, PANEL_W - 6, PANEL_H - 6);

    ctx.fillStyle = '#00d1ff';
    ctx.font = 'bold 44px Segoe UI, Arial';
    ctx.textAlign = 'center';
    ctx.fillText(title, PANEL_W / 2, 60);

    ctx.strokeStyle = 'rgba(0,209,255,0.4)';
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(40, titleH - 10); ctx.lineTo(PANEL_W - 40, titleH - 10); ctx.stroke();

    buttons.forEach(btn => {
      const [x1, y1, x2, y2] = btn.rect;
      const color = btn.action.color || '#0a1520';
      const emissive = btn.action.emissive || '#00d1ff';

      ctx.fillStyle = color;
      ctx.fillRect(x1, y1, x2 - x1, y2 - y1);

      ctx.strokeStyle = emissive;
      ctx.lineWidth = 2;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

      ctx.fillStyle = btn.action.textColor || '#e8f4ff';
      ctx.font = 'bold 28px Segoe UI, Arial';
      ctx.textAlign = 'center';
      ctx.fillText(btn.label, (x1 + x2) / 2, (y1 + y2) / 2 + 10);
    });
  }

  draw();

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = false;

  const material = new THREE.MeshBasicMaterial({
    map: texture, transparent: false, side: THREE.FrontSide,
  });

  const geometry = new THREE.PlaneGeometry(width, height);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.userData = { type: 'panel', isClickable: true, buttons, canvas, ctx, redraw: draw };

  return mesh;
}

function panelHitFromUV(uv, buttons) {
  const cx = uv.x * PANEL_W, cy = (1 - uv.y) * PANEL_H;
  for (const btn of buttons) {
    const [x1, y1, x2, y2] = btn.rect;
    if (cx >= x1 && cx <= x2 && cy >= y1 && cy <= y2) return btn;
  }
  return null;
}

// HANDLERS
function handleCardClick(mesh, altIdx) {
  const state = mesh.userData.state;
  if (state.respondida) return;
  const alt = state.q.alternativas[altIdx];
  const letra = alt.trim().charAt(0).toUpperCase();
  const isCorreta = (letra === state.q.correta);
  state.respondida = true;
  state.selectedIdx = altIdx;
  state.isCorreta = isCorreta;
  state.letraEscolhida = letra;
  mesh.userData.redraw();
  mesh.userData.texture.needsUpdate = true;
  updateHUD();
  showToast(isCorreta ? '✅ Correto! (' + letra + ')' : '❌ Errado. Correta: ' + state.q.correta);
  if (navigator.vibrate) navigator.vibrate(isCorreta ? 40 : 90);
}

function handlePanelClick(mesh, btn) {
  const action = btn.action.name;
  if (window.panelActions && window.panelActions[action]) {
    window.panelActions[action]();
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

function updateHUD() {
  let count = 0, ans = 0;
  document.querySelector('a-scene').object3D.traverse(o => {
    if (o.userData && o.userData.type === 'card') {
      count++;
      if (o.userData.state.respondida) ans++;
    }
  });
  const txt = ans + '/' + count;
  const st = document.getElementById('status');
  if (st) st.textContent = txt + ' respondidas';
  const hd = document.getElementById('hudVRText');
  if (hd) hd.setAttribute('value', txt);
}

// AÇÕES DO PAINEL
window.panelActions = {
  dark: () => {
    document.getElementById('sky').setAttribute('material', 'shader: flat; color: #060913');
    showToast('TÁTICO');
  },
  beach: () => {
    document.getElementById('sky').setAttribute('material',
      'shader: flat; src: url(https://cdn.aframe.io/360-image-gallery-boilerplate/img/sechelt.jpg); color: #fff');
    showToast('PRAIA');
  },
  office: () => {
    document.getElementById('sky').setAttribute('material',
      'shader: flat; src: url(https://cdn.aframe.io/360-image-gallery-boilerplate/img/city.jpg); color: #fff');
    showToast('ESCRITÓRIO');
  },
  library: () => {
    document.getElementById('sky').setAttribute('material',
      'shader: flat; src: url(https://cdn.aframe.io/360-image-gallery-boilerplate/img/cubes.jpg); color: #fff');
    showToast('BIBLIOTECA');
  },
  space: () => {
    document.getElementById('sky').setAttribute('material', 'shader: flat; color: #000008');
    showToast('ESPAÇO');
  },
  passthrough: () => window.enablePassthrough(),
  brightnessDown: () => {
    const amb = document.getElementById('ambientLight');
    const cur = parseFloat(amb.getAttribute('light').intensity) || 0.8;
    const nv = Math.max(0.3, cur - 0.1);
    amb.setAttribute('light', 'intensity', nv.toFixed(2));
    showToast('Brilho ' + Math.round(nv * 100) + '%');
  },
  brightnessUp: () => {
    const amb = document.getElementById('ambientLight');
    const cur = parseFloat(amb.getAttribute('light').intensity) || 0.8;
    const nv = Math.min(1.0, cur + 0.1);
    amb.setAttribute('light', 'intensity', nv.toFixed(2));
    showToast('Brilho ' + Math.round(nv * 100) + '%');
  },
  organizar: () => {
    let i = 0;
    document.querySelector('a-scene').object3D.traverse(o => {
      if (o.userData && o.userData.type === 'card') {
        const cols = 4, sp = 2.6;
        o.position.set((i % cols) * sp - ((cols - 1) * sp / 2), 1.6,
                       Math.floor(i / cols) * -sp - 2.5);
        i++;
      }
    });
    showToast('📐 GRADE');
  },
  porMateria: () => {
    const by = {};
    document.querySelector('a-scene').object3D.traverse(o => {
      if (o.userData && o.userData.type === 'card') {
        const m = o.userData.state.q.materia || 'Geral';
        (by[m] = by[m] || []).push(o);
      }
    });
    const names = Object.keys(by);
    names.forEach((mat, s) => {
      const cluster = by[mat];
      const baseX = (s - (names.length - 1) / 2) * 5.5;
      cluster.forEach((c, i) => {
        const col = i % 2, row = Math.floor(i / 2);
        c.position.set(baseX + (col - 0.5) * 2.6, 1.6, -2.5 - row * 2.6);
      });
    });
    showToast('🎯 POR MATÉRIA');
  },
  espalhar: () => {
    document.querySelector('a-scene').object3D.traverse(o => {
      if (o.userData && o.userData.type === 'card') {
        o.position.set((Math.random() - 0.5) * 10,
                       1.0 + Math.random() * 1.5,
                       -2 - Math.random() * 8);
      }
    });
    showToast('🎲 ESPALHADO');
  },
  salvar: () => {
    const L = {};
    document.querySelector('a-scene').object3D.traverse(o => {
      if (o.userData && o.userData.type === 'card') {
        L[o.uuid] = { p: o.position.toArray(), r: o.rotation.toArray() };
      }
    });
    try { localStorage.setItem('pmsc_layout_v3', JSON.stringify(L)); } catch (e) {}
    showToast('💾 Salvo');
  },
  carregar: () => {
    try {
      const L = JSON.parse(localStorage.getItem('pmsc_layout_v3') || '{}');
      let n = 0;
      document.querySelector('a-scene').object3D.traverse(o => {
        if (o.userData && o.userData.type === 'card' && L[o.uuid]) {
          o.position.fromArray(L[o.uuid].p);
          o.rotation.fromArray(L[o.uuid].r);
          n++;
        }
      });
      showToast('📂 ' + n + ' cartões');
    } catch (e) { showToast('❌ Erro'); }
  },
  toggleHUD: () => {
    const hud = document.getElementById('hudPanel');
    if (hud) {
      const cur = hud.getAttribute('position').y;
      hud.setAttribute('position', { x: 0, y: cur === -0.32 ? 0.4 : -0.32, z: -0.9 });
      showToast(cur === -0.32 ? 'HUD superior' : 'HUD inferior');
    }
  },
  sairVR: () => {
    const s = document.querySelector('a-scene').renderer.xr.getSession();
    if (s) s.end();
  },
  maoMais: () => {
    const l = document.getElementById('leftHand');
    const r = document.getElementById('rightHand');
    const cur = parseFloat(l.getAttribute('scale').x) || 1;
    const nv = Math.min(2.0, cur + 0.1);
    l.setAttribute('scale', `${nv} ${nv} ${nv}`);
    r.setAttribute('scale', `${nv} ${nv} ${nv}`);
    showToast('Mão + (' + nv.toFixed(1) + ')');
  },
  maoMenos: () => {
    const l = document.getElementById('leftHand');
    const r = document.getElementById('rightHand');
    const cur = parseFloat(l.getAttribute('scale').x) || 1;
    const nv = Math.max(0.2, cur - 0.1);
    l.setAttribute('scale', `${nv} ${nv} ${nv}`);
    r.setAttribute('scale', `${nv} ${nv} ${nv}`);
    showToast('Mão - (' + nv.toFixed(1) + ')');
  },
  alturaMais: () => {
    const cam = document.getElementById('head');
    const cur = parseFloat(cam.getAttribute('position').y) || 1.6;
    const nv = Math.min(2.5, cur + 0.1);
    cam.setAttribute('position', { x: 0, y: nv, z: 0 });
    showToast('Altura ' + nv.toFixed(1) + 'm');
  },
  alturaMenos: () => {
    const cam = document.getElementById('head');
    const cur = parseFloat(cam.getAttribute('position').y) || 1.6;
    const nv = Math.max(0.4, cur - 0.1);
    cam.setAttribute('position', { x: 0, y: nv, z: 0 });
    showToast('Altura ' + nv.toFixed(1) + 'm');
  },
};

function saveCardPos(mesh) {
  try {
    const L = JSON.parse(localStorage.getItem('pmsc_layout_v3') || '{}');
    L[mesh.uuid] = { p: mesh.position.toArray(), r: mesh.rotation.toArray() };
    localStorage.setItem('pmsc_layout_v3', JSON.stringify(L));
  } catch (e) {}
}

// PASSTHROUGH
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
    sceneEl.object3D.background = null;
    renderer.setClearColor(0x000000, 0);
    const sess = await navigator.xr.requestSession('immersive-ar', {
      requiredFeatures: ['local-floor'],
      optionalFeatures: ['passthrough', 'hand-tracking', 'hit-test'],
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

// TIMER
let timerStart = Date.now();
setInterval(() => {
  const el = document.getElementById('timerText');
  if (!el) return;
  const s = Math.floor((Date.now() - timerStart) / 1000);
  const m = Math.floor(s / 60), r = s % 60;
  el.setAttribute('value', (m < 10 ? '0' : '') + m + ':' + (r < 10 ? '0' : '') + r);
}, 1000);

// INIT
const QUESTIONS = __Q_JSON__;

window.addEventListener('load', () => {
  const scene = document.querySelector('a-scene');
  if (!scene) return;
  if (scene.hasLoaded) initCards();
  else scene.addEventListener('loaded', initCards);

  function initCards() {
    const root = scene.object3D;
    QUESTIONS.slice(0, 18).forEach((q, i) => root.add(createCard(q, i)));

    const panelActions = [
      { name: 'dark', label: 'TÁTICO', color: '#0a1520', emissive: '#00d1ff' },
      { name: 'beach', label: 'PRAIA', color: '#0a1520', emissive: '#00d1ff' },
      { name: 'office', label: 'ESCRITÓRIO', color: '#0a1520', emissive: '#00d1ff' },
      { name: 'library', label: 'BIBLIOTECA', color: '#0a1520', emissive: '#00d1ff' },
      { name: 'space', label: 'ESPAÇO', color: '#0a1520', emissive: '#00d1ff' },
      { name: 'passthrough', label: 'PASSTHROUGH', color: '#0a1520', emissive: '#ffaa00' },
      { name: 'brightnessDown', label: '◐-', color: '#0a1520', emissive: '#00d1ff' },
      { name: 'brightnessUp', label: '◐+', color: '#0a1520', emissive: '#00d1ff' },
      { name: 'organizar', label: 'GRADE', color: '#0a1520', emissive: '#00d1ff' },
      { name: 'porMateria', label: 'POR MATÉRIA', color: '#0a1520', emissive: '#00d1ff' },
      { name: 'espalhar', label: 'ESPALHAR', color: '#0a1520', emissive: '#ffaa00' },
      { name: 'salvar', label: 'SALVAR', color: '#0a1520', emissive: '#00ff88' },
      { name: 'carregar', label: 'CARREGAR', color: '#0a1520', emissive: '#ffaa00' },
      { name: 'toggleHUD', label: 'HUD', color: '#0a1520', emissive: '#00ff88' },
      { name: 'sairVR', label: 'SAIR VR', color: '#0a1520', emissive: '#ff2222', textColor: '#ff2222' },
    ];
    const mainPanel = createPanel(3.4, 2.4, panelActions, '⬢ COMANDO TÁTICO');
    mainPanel.position.set(0, 1.6, -2.2);
    root.add(mainPanel);

    const calibActions = [
      { name: 'maoMais', label: 'MÃO +', color: '#0a1520', emissive: '#00d1ff' },
      { name: 'maoMenos', label: 'MÃO -', color: '#0a1520', emissive: '#00d1ff' },
      { name: 'alturaMais', label: 'ALT +', color: '#0a1520', emissive: '#00d1ff' },
      { name: 'alturaMenos', label: 'ALT -', color: '#0a1520', emissive: '#00d1ff' },
    ];
    const calibPanel = createPanel(1.6, 1.4, calibActions, '◉ SENSORES');
    calibPanel.position.set(2.2, 1.6, -2.2);
    calibPanel.rotation.y = -0.3;
    root.add(calibPanel);

    setTimeout(updateHUD, 500);
    console.log('[ENGINE] ' + QUESTIONS.slice(0, 18).length + ' cartões + 2 painéis');
  }
});

document.getElementById('enter').addEventListener('click', () => {
  document.querySelector('a-scene').enterVR().catch(e => showToast('❌ ' + e.message));
});
</script>

<style>
html, body {
  margin: 0; padding: 0; width: 100%; height: 100vh;
  overflow: hidden; background: #060913;
  font-family: 'Segoe UI', Arial, sans-serif;
}
#hud {
  position: fixed; top: 10px; left: 10px; z-index: 99999;
  background: rgba(6,9,19,0.94); color: #00d1ff;
  border: 1px solid rgba(0,209,255,0.5);
  padding: 10px 14px; border-radius: 6px;
  font-size: 12px; max-width: 460px;
  box-shadow: 0 0 20px rgba(0,209,255,0.15);
}
#hud .title { font-weight: 900; color: #fff; font-size: 13px; letter-spacing: 2px; }
#hud .sub { color: #00d1ff; font-size: 11px; margin-top: 3px; }
#hud .counter { margin-top: 5px; color: #00ff88; font-weight: 700; }
#enter {
  position: fixed; bottom: 16px; left: 50%;
  transform: translateX(-50%); z-index: 99999;
  background: linear-gradient(90deg, #00d1ff, #0050a8);
  color: #060913; border: 2px solid #00d1ff;
  padding: 14px 40px; border-radius: 6px;
  font-weight: 900; font-size: 14px; letter-spacing: 2px;
  cursor: pointer; box-shadow: 0 0 24px rgba(0,209,255,0.5);
}
#toast {
  position: fixed; bottom: 90px; left: 50%;
  transform: translateX(-50%); z-index: 999999;
  background: rgba(6,9,19,0.96); color: #00d1ff;
  border: 2px solid #00d1ff; padding: 10px 22px;
  border-radius: 6px; font-size: 13px; font-weight: 700;
  display: none; pointer-events: none;
  box-shadow: 0 0 20px rgba(0,209,255,0.5);
}
</style>
</head>
<body>

<div id="hud">
  <div class="title">⬢ PMSC · ENGINE OTIMIZADA</div>
  <div class="sub">__MODO__ · FFR 1.0 · DRAW CALLS ~26</div>
  <div class="counter">STATUS: <span id="status">0/__LEN__</span></div>
</div>
<button id="enter">▶ ENTRAR NO VR</button>
<div id="toast"></div>

<a-scene id="scene"
  background="color: #060913"
  renderer="colorManagement: true; antialias: true; precision: high; sortObjects: false; powerPreference: high-performance; foveationLevel: high"
  webxr="referenceSpaceType: local-floor; requiredFeatures: local-floor; optionalFeatures: hand-tracking, bounded-floor, hit-test, passthrough"
  vr-mode-ui="enabled: true"
  embedded
  style="width: 100%; height: 100vh;">

  <a-sky id="sky" material="shader: flat; color: #060913"></a-sky>

  <a-entity id="ambientLight" light="type: ambient; intensity: 0.8"></a-entity>
  <a-entity light="type: directional; intensity: 0.4; castShadow: false" position="3 6 4"></a-entity>

  <a-plane rotation="-90 0 0" width="80" height="80" color="#0a0f1a"
    material="shader: flat; opacity: 1; transparent: false"></a-plane>

  <a-entity id="rig" position="0 0 0">
    <a-entity id="head" camera look-controls position="0 1.6 0">
      <a-entity id="hudPanel" position="0 -0.32 -0.9" scale="0.5 0.5 0.5">
        <a-text id="hudVRText" value="0/__LEN__" color="#00d1ff" width="1.0"
          align="center" position="0 0.06 0.004"
          font="mozillavr" shader="msdf" negate="false"></a-text>
        <a-text id="timerText" value="00:00" color="#00ff88" width="0.45"
          align="right" position="0.35 -0.07 0.004"
          font="mozillavr" shader="msdf" negate="false"></a-text>
      </a-entity>
    </a-entity>

    <a-entity id="leftHand"
      laser-controls="hand: left"
      hand-tracking-controls="hand: left; modelStyle: dots; color: #00d1ff"
      hand-live="hand: left"
      vr-hand
      raycaster="objects: .clickable; far: 20; interval: 100"
      line="color: #00d1ff; opacity: 0.9">
    </a-entity>

    <a-entity id="rightHand"
      laser-controls="hand: right"
      hand-tracking-controls="hand: right; modelStyle: dots; color: #ff8a00"
      hand-live="hand: right"
      vr-hand
      raycaster="objects: .clickable; far: 20; interval: 100"
      line="color: #ff8a00; opacity: 0.9">
    </a-entity>
  </a-entity>
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
# UI STREAMLIT
# ═══════════════════════════════════════════════════════════════════════
st.title("⬢ PMSC Arena VR — Engine Otimizada")
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


# ═══════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════
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
