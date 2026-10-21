"""
PMSC Arena VR — v13 (Painéis Móveis)
Novo: PanelManager com 5 painéis independentes, drag handle, resize, freeze,
      nav bar head-locked, modos de organização, persistência localStorage.
Preservado: gramática, loader JSON, simulado 60q, cartões canvas, FFR, ambientes.
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
TOTAL_OFICIAL = sum(DISTRIBUICAO.values())

# ═══════════════════════════════════════════════════════════════════════
# NORMALIZAÇÃO GRAMATICAL (PRESERVADA)
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
# PARSER TOLERANTE (PRESERVADO)
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
# RENDER VR — COM PANEL MANAGER
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
<title>PMSC Arena VR — Painéis Móveis</title>
<script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v7.4.0/dist/aframe-extras.min.js"></script>
<script>
// ═══════════════════════════════════════════════════════════════════
// FFR programático
// ═══════════════════════════════════════════════════════════════════
function setupFFR() {
  const s = document.querySelector('a-scene');
  if (!s || !s.renderer || !s.renderer.xr) return;
  try { s.renderer.xr.setFoveation(1.0); } catch (e) {}
}
document.addEventListener('DOMContentLoaded', () => {
  const s = document.querySelector('a-scene');
  if (!s) return;
  ['loaded','enter-vr','renderstart'].forEach(e => s.addEventListener(e, setupFFR));
});

// ═══════════════════════════════════════════════════════════════════
// PANEL MANAGER — 5 painéis independentes
// ═══════════════════════════════════════════════════════════════════
const STORAGE_KEY = 'pmsc_panels_v1';
const PANEL_PX_PER_M = 400;

function makeCanvas(panelW, panelH) {
  const c = document.createElement('canvas');
  c.width = Math.round(panelW * PANEL_PX_PER_M);
  c.height = Math.round(panelH * PANEL_PX_PER_M);
  return c;
}

// Desenha um painel base (fundo, borda, título, botões close/freeze/resize)
function drawPanelBase(ctx, W, H, title, opts) {
  // Fundo
  ctx.fillStyle = 'rgba(6,9,19,0.96)';
  ctx.fillRect(0, 0, W, H);

  // Grid sutil
  ctx.strokeStyle = 'rgba(0,209,255,0.05)';
  ctx.lineWidth = 1;
  for (let x = 0; x < W; x += 48) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
  for (let y = 0; y < H; y += 48) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }

  // Borda
  ctx.strokeStyle = '#00d1ff';
  ctx.lineWidth = 6;
  ctx.strokeRect(3, 3, W - 6, H - 6);

  // Título bar (grab handle)
  const titleH = 56;
  ctx.fillStyle = opts.frozen ? 'rgba(255,68,68,0.3)' : 'rgba(0,209,255,0.25)';
  ctx.fillRect(0, 0, W, titleH);
  ctx.strokeStyle = opts.frozen ? '#ff4444' : '#00d1ff';
  ctx.lineWidth = 2;
  ctx.strokeRect(0, 0, W, titleH);

  // Ícone freeze
  ctx.font = 'bold 30px Segoe UI, Arial';
  ctx.textAlign = 'left';
  ctx.fillStyle = opts.frozen ? '#ff4444' : '#ffaa00';
  ctx.fillText(opts.frozen ? '🔒' : '☰', 14, 40);

  // Título
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 26px Segoe UI, Arial';
  ctx.textAlign = 'center';
  ctx.fillText(title, W / 2, 40);

  // Botão fechar (X)
  ctx.fillStyle = '#ff4444';
  ctx.fillRect(W - 44, 8, 36, 40);
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 26px Segoe UI, Arial';
  ctx.textAlign = 'center';
  ctx.fillText('×', W - 26, 38);

  // Botão resize (−)
  ctx.fillStyle = 'rgba(0,209,255,0.4)';
  ctx.fillRect(8, H - 40, 44, 32);
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 22px Segoe UI, Arial';
  ctx.fillText('−', 30, H - 16);

  // Botão resize (+)
  ctx.fillStyle = 'rgba(0,209,255,0.4)';
  ctx.fillRect(60, H - 40, 44, 32);
  ctx.fillStyle = '#fff';
  ctx.fillText('+', 82, H - 16);

  return { titleH };
}

// Cria painel 3D com canvas
function createPanelMesh(id, opts) {
  const { width, height, title, pos, drawContent } = opts;
  const canvas = makeCanvas(width, height);
  const ctx = canvas.getContext('2d', { alpha: false });

  const state = { id, frozen: false, size: 1.0, buttons: [] };

  function redraw() {
    const W = canvas.width, H = canvas.height;
    const { titleH } = drawPanelBase(ctx, W, H, title, state);
    state.buttons = [];
    drawContent(ctx, W, H, titleH, state.buttons);
    texture.needsUpdate = true;
  }

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
  mesh.position.set(pos[0], pos[1], pos[2]);

  mesh.userData = {
    type: 'panel', isClickable: true,
    id, state, canvas, ctx, texture,
    redraw, width, height,
    initialPos: pos.slice(),
  };

  redraw();
  return mesh;
}

// UV → botão do painel
function panelHitFromUV(mesh, uv) {
  const W = mesh.userData.canvas.width;
  const H = mesh.userData.canvas.height;
  const px = uv.x * W;
  const py = (1 - uv.y) * H;
  const titleH = 56;

  // Zone de drag = título (y < titleH)
  if (py < titleH) {
    // Fechar (X): canto superior direito
    if (px > W - 44 && py < 48) return { action: 'close' };
    // Fora da zona dos botões → drag
    return { action: 'drag' };
  }

  // Resize buttons (canto inferior esquerdo)
  if (py > H - 40) {
    if (px < 52) return { action: 'resize-down' };
    if (px >= 60 && px < 104) return { action: 'resize-up' };
  }

  // Botões registrados pelo conteúdo
  for (const b of mesh.userData.state.buttons) {
    if (px >= b.rect[0] && px <= b.rect[2] && py >= b.rect[1] && py <= b.rect[3]) {
      return { action: 'btn', btn: b };
    }
  }
  return null;
}

// ═══════════════════════════════════════════════════════════════════
// CONTEÚDO DOS 5 PAINÉIS
// ═══════════════════════════════════════════════════════════════════
const PanelState = {
  cards: [],          // referência aos cards
  currentCard: 0,
  notes: '',
  mode: 'free',
};

function drawMainContent(ctx, W, H, titleH, buttons) {
  const stats = {
    total: PanelState.cards.length,
    answered: PanelState.cards.filter(c => c.userData.state.respondida).length,
  };
  const pct = stats.total > 0 ? Math.round(stats.answered / stats.total * 100) : 0;

  ctx.fillStyle = '#00d1ff';
  ctx.font = 'bold 28px Segoe UI, Arial';
  ctx.textAlign = 'center';
  ctx.fillText('⬢ PMSC · CENTRO DE COMANDO', W/2, titleH + 45);

  ctx.fillStyle = '#e8f4ff';
  ctx.font = '24px Segoe UI, Arial';
  ctx.fillText('Progresso: ' + stats.answered + '/' + stats.total, W/2, titleH + 90);
  ctx.fillText('Conclusão: ' + pct + '%', W/2, titleH + 125);

  // Barra de progresso
  const barW = W - 100, barH = 20;
  const barX = 50, barY = titleH + 150;
  ctx.fillStyle = 'rgba(0,209,255,0.2)';
  ctx.fillRect(barX, barY, barW, barH);
  ctx.fillStyle = '#00ff88';
  ctx.fillRect(barX, barY, barW * pct / 100, barH);

  // Modes grid
  const modes = [
    { label: 'LIVRE', mode: 'free' },
    { label: 'FOCO', mode: 'focus' },
    { label: 'LEITURA', mode: 'reading' },
    { label: 'EXERCÍCIOS', mode: 'exercises' },
    { label: 'NOTAS', mode: 'notes' },
  ];
  const gridY = barY + 50;
  const cols = 5;
  const cellW = (W - 80) / cols;
  modes.forEach((m, i) => {
    const x1 = 40 + i * cellW + 4;
    const y1 = gridY;
    const x2 = x1 + cellW - 8;
    const y2 = y1 + 60;
    const active = (PanelState.mode === m.mode);
    ctx.fillStyle = active ? 'rgba(0,209,255,0.4)' : 'rgba(10,21,32,0.9)';
    ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
    ctx.strokeStyle = active ? '#00ff88' : '#00d1ff';
    ctx.lineWidth = 2;
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    ctx.fillStyle = active ? '#00ff88' : '#00d1ff';
    ctx.font = 'bold 16px Segoe UI, Arial';
    ctx.textAlign = 'center';
    ctx.fillText(m.label, (x1 + x2) / 2, (y1 + y2) / 2 + 6);
    buttons.push({ rect: [x1, y1, x2, y2], action: 'set-mode', value: m.mode });
  });
}

function drawNotesContent(ctx, W, H, titleH, buttons) {
  ctx.fillStyle = '#ffaa00';
  ctx.font = 'bold 22px Segoe UI, Arial';
  ctx.textAlign = 'left';
  ctx.fillText('📝 ANOTAÇÕES RÁPIDAS', 20, titleH + 35);

  // Área de texto
  const areaX = 20, areaY = titleH + 55;
  const areaW = W - 40, areaH = H - titleH - 130;
  ctx.fillStyle = 'rgba(10,21,32,0.9)';
  ctx.fillRect(areaX, areaY, areaW, areaH);
  ctx.strokeStyle = 'rgba(255,170,0,0.4)';
  ctx.lineWidth = 2;
  ctx.strokeRect(areaX, areaY, areaW, areaH);

  // Texto com wrap
  ctx.fillStyle = '#e8f4ff';
  ctx.font = '20px Segoe UI, Arial';
  ctx.textAlign = 'left';
  const lines = (PanelState.notes || 'Clique em EDITAR para escrever').split('\n');
  let y = areaY + 30;
  lines.forEach(line => {
    // wrap simples
    const words = line.split(' ');
    let cur = '';
    for (const w of words) {
      const test = cur + w + ' ';
      if (ctx.measureText(test).width > areaW - 30) {
        ctx.fillText(cur, areaX + 15, y);
        y += 28;
        cur = w + ' ';
      } else { cur = test; }
    }
    if (cur) { ctx.fillText(cur, areaX + 15, y); y += 28; }
  });

  // Botão editar
  const btnW = 180, btnH = 45;
  const btnX = (W - btnW) / 2, btnY = H - 60;
  ctx.fillStyle = 'rgba(0,209,255,0.6)';
  ctx.fillRect(btnX, btnY, btnW, btnH);
  ctx.strokeStyle = '#00d1ff';
  ctx.lineWidth = 2;
  ctx.strokeRect(btnX, btnY, btnW, btnH);
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 20px Segoe UI, Arial';
  ctx.textAlign = 'center';
  ctx.fillText('✏️ EDITAR', W/2, btnY + 30);
  buttons.push({ rect: [btnX, btnY, btnX + btnW, btnY + btnH], action: 'edit-notes' });
}

function drawExercisesContent(ctx, W, H, titleH, buttons) {
  ctx.fillStyle = '#00ff88';
  ctx.font = 'bold 24px Segoe UI, Arial';
  ctx.textAlign = 'center';
  ctx.fillText('📚 EXERCÍCIOS', W/2, titleH + 40);

  const total = PanelState.cards.length;
  const answered = PanelState.cards.filter(c => c.userData.state.respondida).length;
  ctx.fillStyle = '#e8f4ff';
  ctx.font = '20px Segoe UI, Arial';
  ctx.fillText('Respondidas: ' + answered + '/' + total, W/2, titleH + 75);

  // Navegação
  const navY = titleH + 110;
  const navW = 90, navH = 55;
  const prevX = W/2 - 110, nextX = W/2 + 20;

  ctx.fillStyle = 'rgba(0,209,255,0.3)';
  ctx.fillRect(prevX, navY, navW, navH);
  ctx.strokeStyle = '#00d1ff';
  ctx.strokeRect(prevX, navY, navW, navH);
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 28px Segoe UI, Arial';
  ctx.fillText('◀', prevX + navW/2, navY + 40);
  buttons.push({ rect: [prevX, navY, prevX + navW, navY + navH], action: 'prev' });

  ctx.fillStyle = 'rgba(0,209,255,0.3)';
  ctx.fillRect(nextX, navY, navW, navH);
  ctx.strokeStyle = '#00d1ff';
  ctx.strokeRect(nextX, navY, navW, navH);
  ctx.fillStyle = '#ffffff';
  ctx.fillText('▶', nextX + navW/2, navY + 40);
  buttons.push({ rect: [nextX, navY, nextX + navW, navY + navH], action: 'next' });

  // Botão shuffle
  const shufY = navY + 75;
  const shufW = 200, shufH = 45;
  const shufX = (W - shufW) / 2;
  ctx.fillStyle = 'rgba(255,170,0,0.4)';
  ctx.fillRect(shufX, shufY, shufW, shufH);
  ctx.strokeStyle = '#ffaa00';
  ctx.strokeRect(shufX, shufY, shufW, shufH);
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 18px Segoe UI, Arial';
  ctx.fillText('🎲 ORDEM ALEATÓRIA', W/2, shufY + 28);
  buttons.push({ rect: [shufX, shufY, shufX + shufW, shufY + shufH], action: 'shuffle' });
}

function drawToolsContent(ctx, W, H, titleH, buttons) {
  ctx.fillStyle = '#ffaa00';
  ctx.font = 'bold 22px Segoe UI, Arial';
  ctx.textAlign = 'center';
  ctx.fillText('🔧 FERRAMENTAS', W/2, titleH + 30);

  const actions = [
    { label: 'GRADE', action: 'grade' },
    { label: 'MATÉRIA', action: 'subject' },
    { label: 'ESPALHAR', action: 'scatter' },
    { label: 'RESET', action: 'reset-layout' },
    { label: 'EXPORT', action: 'export-notes' },
    { label: 'LIMPAR', action: 'clear-notes' },
  ];
  const cols = 2;
  const rows = Math.ceil(actions.length / cols);
  const margin = 15;
  const cellW = (W - margin * 2) / cols;
  const cellH = (H - titleH - 50) / rows;

  actions.forEach((a, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    const x1 = margin + col * cellW + 4;
    const y1 = titleH + 50 + row * cellH + 4;
    const x2 = x1 + cellW - 8;
    const y2 = y1 + cellH - 8;
    ctx.fillStyle = 'rgba(10,21,32,0.9)';
    ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
    ctx.strokeStyle = '#00d1ff';
    ctx.lineWidth = 2;
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    ctx.fillStyle = '#00d1ff';
    ctx.font = 'bold 16px Segoe UI, Arial';
    ctx.textAlign = 'center';
    ctx.fillText(a.label, (x1 + x2) / 2, (y1 + y2) / 2 + 6);
    buttons.push({ rect: [x1, y1, x2, y2], action: a.action });
  });
}

function drawSettingsContent(ctx, W, H, titleH, buttons) {
  ctx.fillStyle = '#ff4444';
  ctx.font = 'bold 22px Segoe UI, Arial';
  ctx.textAlign = 'center';
  ctx.fillText('⚙️ CONFIGURAÇÕES', W/2, titleH + 30);

  const actions = [
    { label: '☀+', action: 'bright-up' },
    { label: '☀−', action: 'bright-down' },
    { label: 'HUD', action: 'toggle-hud' },
    { label: 'MÃO+', action: 'hand-up' },
    { label: 'MÃO−', action: 'hand-down' },
    { label: 'SAIR', action: 'exit-vr' },
  ];
  const cols = 2;
  const rows = Math.ceil(actions.length / cols);
  const margin = 15;
  const cellW = (W - margin * 2) / cols;
  const cellH = (H - titleH - 50) / rows;

  actions.forEach((a, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    const x1 = margin + col * cellW + 4;
    const y1 = titleH + 50 + row * cellH + 4;
    const x2 = x1 + cellW - 8;
    const y2 = y1 + cellH - 8;
    ctx.fillStyle = 'rgba(10,21,32,0.9)';
    ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
    ctx.strokeStyle = '#ff4444';
    ctx.lineWidth = 2;
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    ctx.fillStyle = '#ff8888';
    ctx.font = 'bold 16px Segoe UI, Arial';
    ctx.textAlign = 'center';
    ctx.fillText(a.label, (x1 + x2) / 2, (y1 + y2) / 2 + 6);
    buttons.push({ rect: [x1, y1, x2, y2], action: a.action });
  });
}

// ═══════════════════════════════════════════════════════════════════
// CRIAR OS 5 PAINÉIS
// ═══════════════════════════════════════════════════════════════════
const panels = {};

function buildPanels() {
  const scene = document.querySelector('a-scene');
  if (!scene || !scene.object3D) return;
  const root = scene.object3D;

  const configs = [
    { id: 'main',      title: '⬢ PAINEL PRINCIPAL', width: 2.4, height: 1.4, pos: [0, 1.6, -2.2], draw: drawMainContent },
    { id: 'notes',     title: '📝 ANOTAÇÕES',        width: 1.8, height: 1.4, pos: [-2.2, 1.6, -2.2], draw: drawNotesContent },
    { id: 'exercises', title: '📚 EXERCÍCIOS',       width: 1.8, height: 1.4, pos: [2.2, 1.6, -2.2], draw: drawExercisesContent },
    { id: 'tools',     title: '🔧 FERRAMENTAS',      width: 1.4, height: 1.0, pos: [-1.2, 0.4, -2.2], draw: drawToolsContent },
    { id: 'settings',  title: '⚙️ CONFIG',          width: 1.4, height: 1.0, pos: [1.2, 0.4, -2.2], draw: drawSettingsContent },
  ];

  configs.forEach(cfg => {
    const mesh = createPanelMesh(cfg.id, cfg);
    root.add(mesh);
    panels[cfg.id] = mesh;
  });
}

// ═══════════════════════════════════════════════════════════════════
// NAV BAR (head-locked)
// ═══════════════════════════════════════════════════════════════════
function buildNavBar() {
  const head = document.getElementById('head');
  if (!head) return;

  const navW = 2.4, navH = 0.14;
  const canvas = makeCanvas(navW, navH);
  const ctx = canvas.getContext('2d', { alpha: false });

  function draw() {
    const W = canvas.width, H = canvas.height;
    ctx.fillStyle = 'rgba(6,9,19,0.95)';
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = '#00d1ff';
    ctx.lineWidth = 3;
    ctx.strokeRect(1.5, 1.5, W - 3, H - 3);

    const items = [
      { label: '⬢', id: 'main' },
      { label: '📝', id: 'notes' },
      { label: '📚', id: 'exercises' },
      { label: '🔧', id: 'tools' },
      { label: '⚙️', id: 'settings' },
    ];
    const btnW = (W - 20) / items.length;
    items.forEach((it, i) => {
      const x = 10 + i * btnW;
      ctx.fillStyle = 'rgba(0,209,255,0.15)';
      ctx.fillRect(x + 2, 4, btnW - 4, H - 8);
      ctx.fillStyle = '#00d1ff';
      ctx.font = 'bold 32px Segoe UI, Arial';
      ctx.textAlign = 'center';
      ctx.fillText(it.label, x + btnW / 2, H / 2 + 12);
    });
  }
  draw();

  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.minFilter = THREE.LinearFilter;
  tex.magFilter = THREE.LinearFilter;
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: false });
  const geo = new THREE.PlaneGeometry(navW, navH);
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.set(0, -0.35, -0.7);
  mesh.userData = {
    type: 'navbar', isClickable: true,
    canvas, ctx, navW, navH,
  };
  head.object3D.add(mesh);
}

// UV do nav bar
function navHitFromUV(mesh, uv) {
  const W = mesh.userData.canvas.width;
  const px = uv.x * W;
  const items = ['main', 'notes', 'exercises', 'tools', 'settings'];
  const btnW = (W - 20) / items.length;
  for (let i = 0; i < items.length; i++) {
    const x1 = 10 + i * btnW;
    const x2 = x1 + btnW;
    if (px >= x1 && px <= x2) return items[i];
  }
  return null;
}

// ═══════════════════════════════════════════════════════════════════
// VR-HAND — drag handles, buttons, cards
// ═══════════════════════════════════════════════════════════════════
AFRAME.registerComponent('vr-hand', {
  init: function() {
    const hand = this.el;
    const raycaster = new THREE.Raycaster();
    raycaster.far = 20;

    let grabbed = null;
    let grabbedIsPanel = false;
    let grabOffset = new THREE.Vector3();
    let grabDistAdj = 0;
    let currentHit = null;
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
      currentHit = null;
      if (hits.length === 0) return;
      const hit = hits[0], mesh = hit.object;
      if (mesh.userData.type === 'card') {
        currentHit = { mesh, kind: 'card', altIdx: cardHitFromUV(hit.uv) };
      } else if (mesh.userData.type === 'panel') {
        currentHit = { mesh, kind: 'panel', panel: panelHitFromUV(mesh, hit.uv) };
      } else if (mesh.userData.type === 'navbar') {
        currentHit = { mesh, kind: 'navbar', panelId: navHitFromUV(mesh, hit.uv) };
      }
    };

    const doClick = () => {
      if (!currentHit) return;
      if (currentHit.kind === 'card' && currentHit.altIdx >= 0) {
        handleCardClick(currentHit.mesh, currentHit.altIdx);
      } else if (currentHit.kind === 'panel' && currentHit.panel) {
        handlePanelAction(currentHit.mesh, currentHit.panel);
      } else if (currentHit.kind === 'navbar' && currentHit.panelId) {
        togglePanelVisibility(currentHit.panelId);
      }
    };

    const startGrab = () => {
      // Painel: só arrasta se estiver na zona de drag (título)
      if (currentHit && currentHit.kind === 'panel' && currentHit.panel && currentHit.panel.action === 'drag') {
        const p = currentHit.mesh;
        if (p.userData.state.frozen) {
          showToast('🔒 Painel fixado');
          return;
        }
        grabbed = p;
        grabbedIsPanel = true;
        const hp = getPos();
        p.getWorldPosition(_bp);
        grabOffset.copy(_bp).sub(hp);
        grabDistAdj = 0;
        p.material.color.setHex(0x00d1ff);
        showToast('✋ ' + p.userData.id, 600);
        if (navigator.vibrate) navigator.vibrate(30);
        return;
      }
      // Card: grab padrão
      if (currentHit && currentHit.kind === 'card') {
        grabbed = currentHit.mesh;
        grabbedIsPanel = false;
        const hp = getPos();
        grabbed.getWorldPosition(_bp);
        grabOffset.copy(_bp).sub(hp);
        grabDistAdj = 0;
        grabbed.material.color.setHex(0x00d1ff);
        showToast('✋ ' + grabbed.userData.state.index, 600);
        if (navigator.vibrate) navigator.vibrate(30);
      }
    };

    const endGrab = () => {
      if (!grabbed) return;
      grabbed.material.color.setHex(0xffffff);
      if (grabbedIsPanel) {
        savePanelPos(grabbed);
      } else {
        saveCardPos(grabbed);
      }
      showToast('📍 posicionado', 600);
      if (navigator.vibrate) navigator.vibrate(20);
      grabbed = null;
      grabbedIsPanel = false;
      grabDistAdj = 0;
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
      if (currentHit && currentHit.kind === 'panel' && currentHit.panel && currentHit.panel.action === 'drag') {
        startGrab();
      } else if (currentHit) {
        doClick();
      }
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

// ═══════════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════════
function handlePanelAction(mesh, action) {
  const id = mesh.userData.id;
  const state = mesh.userData.state;

  if (action.action === 'close') { togglePanelVisibility(id); return; }
  if (action.action === 'resize-up') {
    state.size = Math.min(2.0, state.size + 0.1);
    mesh.scale.set(state.size, state.size, state.size);
    savePanelPos(mesh);
    return;
  }
  if (action.action === 'resize-down') {
    state.size = Math.max(0.5, state.size - 0.1);
    mesh.scale.set(state.size, state.size, state.size);
    savePanelPos(mesh);
    return;
  }
  if (action.action === 'btn' && action.btn) {
    executeAction(action.btn.action, action.btn.value, mesh);
    return;
  }
}

function executeAction(action, value, mesh) {
  switch (action) {
    case 'set-mode': applyMode(value); break;
    case 'edit-notes': promptNotes(); break;
    case 'prev': cycleCard(-1); break;
    case 'next': cycleCard(1); break;
    case 'shuffle': shuffleCards(); break;
    case 'grade': organizeCards('grade'); break;
    case 'subject': organizeCards('subject'); break;
    case 'scatter': organizeCards('scatter'); break;
    case 'reset-layout': resetLayout(); break;
    case 'export-notes': exportNotes(); break;
    case 'clear-notes': clearNotes(); break;
    case 'bright-up': brightUp(); break;
    case 'bright-down': brightDown(); break;
    case 'toggle-hud': toggleHUD(); break;
    case 'hand-up': handUp(); break;
    case 'hand-down': handDown(); break;
    case 'exit-vr': exitVR(); break;
  }
}

function togglePanelVisibility(id) {
  const p = panels[id];
  if (!p) return;
  p.visible = !p.visible;
  savePanelPos(p);
  showToast(id + ': ' + (p.visible ? 'ON' : 'OFF'));
}

function applyMode(mode) {
  PanelState.mode = mode;
  const modes = {
    free: ['main', 'notes', 'exercises', 'tools', 'settings'],
    focus: ['main', 'exercises'],
    reading: ['notes', 'exercises'],
    exercises: ['exercises'],
    notes: ['notes'],
  };
  const visible = modes[mode] || modes.free;
  Object.keys(panels).forEach(id => {
    panels[id].visible = visible.includes(id);
  });
  Object.keys(panels).forEach(id => {
    panels[id].userData.redraw();
    panels[id].visible = visible.includes(id);
  });
  saveAllPanels();
  showToast('Modo: ' + mode.toUpperCase());
}

function cycleCard(dir) {
  // Move todos os cards para a próxima questão (rotação do array)
  const root = document.querySelector('a-scene').object3D;
  const cards = [];
  root.traverse(o => { if (o.userData && o.userData.type === 'card') cards.push(o); });
  if (cards.length === 0) return;
  const first = cards.shift();
  cards.push(first);
  // Reorganiza posições
  cards.forEach((c, i) => {
    const cols = 4, sp = 2.6;
    c.position.set((i % cols) * sp - ((cols - 1) * sp / 2), 1.6, Math.floor(i / cols) * -sp - 2.5);
  });
  showToast('Cartões rotacionados');
}

function shuffleCards() {
  const root = document.querySelector('a-scene').object3D;
  const cards = [];
  root.traverse(o => { if (o.userData && o.userData.type === 'card') cards.push(o); });
  cards.forEach(c => {
    c.position.set((Math.random() - 0.5) * 10, 0.8 + Math.random() * 1.5, -2 - Math.random() * 6);
  });
  showToast('🎲 Embaralhado');
}

function organizeCards(mode) {
  const root = document.querySelector('a-scene').object3D;
  const cards = [];
  root.traverse(o => { if (o.userData && o.userData.type === 'card') cards.push(o); });
  if (mode === 'grade') {
    cards.forEach((c, i) => {
      const cols = 4, sp = 2.6;
      c.position.set((i % cols) * sp - ((cols - 1) * sp / 2), 1.6, Math.floor(i / cols) * -sp - 2.5);
    });
  } else if (mode === 'subject') {
    const by = {};
    cards.forEach(c => {
      const m = c.userData.state.q.materia || 'Geral';
      (by[m] = by[m] || []).push(c);
    });
    const names = Object.keys(by);
    names.forEach((mat, s) => {
      const baseX = (s - (names.length - 1) / 2) * 5.5;
      by[mat].forEach((c, i) => {
        const col = i % 2, row = Math.floor(i / 2);
        c.position.set(baseX + (col - 0.5) * 2.6, 1.6, -2.5 - row * 2.6);
      });
    });
  } else if (mode === 'scatter') {
    cards.forEach(c => {
      c.position.set((Math.random() - 0.5) * 14, 0.8 + Math.random() * 2.5, -2 - Math.random() * 8);
    });
  }
  showToast('📐 ' + mode.toUpperCase());
}

function resetLayout() {
  Object.values(panels).forEach(p => {
    p.position.set(p.userData.initialPos[0], p.userData.initialPos[1], p.userData.initialPos[2]);
    p.scale.set(1, 1, 1);
    p.visible = true;
    p.userData.state.size = 1.0;
    p.userData.state.frozen = false;
    p.userData.redraw();
  });
  PanelState.mode = 'free';
  saveAllPanels();
  showToast('Layout restaurado');
}

function exportNotes() {
  if (!PanelState.notes) { showToast('Nada para exportar'); return; }
  const blob = new Blob([PanelState.notes], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'pmsc_notas.txt'; a.click();
  URL.revokeObjectURL(url);
  showToast('📥 Exportado');
}

function clearNotes() {
  if (!confirm('Apagar todas as anotações?')) return;
  PanelState.notes = '';
  panels.notes.userData.redraw();
  saveAllPanels();
  showToast('🗑️ Anotações apagadas');
}

function promptNotes() {
  // Meta keyboard: usa input HTML invisível
  const cur = PanelState.notes || '';
  const newText = prompt('Escreva suas anotações:', cur);
  if (newText !== null) {
    PanelState.notes = newText;
    panels.notes.userData.redraw();
    saveAllPanels();
  }
}

function brightUp() {
  const amb = document.getElementById('ambientLight');
  const cur = parseFloat(amb.getAttribute('light').intensity) || 0.8;
  amb.setAttribute('light', 'intensity', Math.min(1.0, cur + 0.1).toFixed(2));
  showToast('☀ ' + Math.round(Math.min(1.0, cur + 0.1) * 100) + '%');
}

function brightDown() {
  const amb = document.getElementById('ambientLight');
  const cur = parseFloat(amb.getAttribute('light').intensity) || 0.8;
  amb.setAttribute('light', 'intensity', Math.max(0.3, cur - 0.1).toFixed(2));
  showToast('☀ ' + Math.round(Math.max(0.3, cur - 0.1) * 100) + '%');
}

function toggleHUD() {
  const hud = document.getElementById('hudPanel');
  if (hud) {
    const y = hud.getAttribute('position').y;
    hud.setAttribute('position', { x: 0, y: y === -0.32 ? 0.4 : -0.32, z: -0.9 });
    showToast('HUD ' + (y === -0.32 ? 'superior' : 'inferior'));
  }
}

function handUp() {
  const l = document.getElementById('leftHand'), r = document.getElementById('rightHand');
  const cur = parseFloat(l.getAttribute('scale').x) || 1;
  const nv = Math.min(2.0, cur + 0.1);
  l.setAttribute('scale', `${nv} ${nv} ${nv}`);
  r.setAttribute('scale', `${nv} ${nv} ${nv}`);
  showToast('Mão ' + nv.toFixed(1));
}

function handDown() {
  const l = document.getElementById('leftHand'), r = document.getElementById('rightHand');
  const cur = parseFloat(l.getAttribute('scale').x) || 1;
  const nv = Math.max(0.2, cur - 0.1);
  l.setAttribute('scale', `${nv} ${nv} ${nv}`);
  r.setAttribute('scale', `${nv} ${nv} ${nv}`);
  showToast('Mão ' + nv.toFixed(1));
}

function exitVR() {
  const s = document.querySelector('a-scene').renderer.xr.getSession();
  if (s) s.end();
}

// ═══════════════════════════════════════════════════════════════════
// SAVE / LOAD (localStorage)
// ═══════════════════════════════════════════════════════════════════
function savePanelPos(mesh) {
  try {
    const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    data[mesh.userData.id] = {
      pos: mesh.position.toArray(),
      scale: mesh.userData.state.size,
      frozen: mesh.userData.state.frozen,
      visible: mesh.visible,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (e) {}
}

function saveAllPanels() {
  Object.values(panels).forEach(p => savePanelPos(p));
}

function loadPanels() {
  try {
    const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    Object.keys(data).forEach(id => {
      const p = panels[id];
      if (!p) return;
      const d = data[id];
      if (d.pos) p.position.set(d.pos[0], d.pos[1], d.pos[2]);
      if (d.scale) {
        p.userData.state.size = d.scale;
        p.scale.set(d.scale, d.scale, d.scale);
      }
      if (typeof d.frozen !== 'undefined') p.userData.state.frozen = d.frozen;
      if (typeof d.visible !== 'undefined') p.visible = d.visible;
      p.userData.redraw();
    });
  } catch (e) {}
}

function saveCardPos(mesh) {
  try {
    const data = JSON.parse(localStorage.getItem('pmsc_cards_v1') || '{}');
    data[mesh.uuid] = { p: mesh.position.toArray(), r: mesh.rotation.toArray() };
    localStorage.setItem('pmsc_cards_v1', JSON.stringify(data));
  } catch (e) {}
}

// ═══════════════════════════════════════════════════════════════════
// CARTÕES (preservado do v12)
// ═══════════════════════════════════════════════════════════════════
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
      if (lineCount >= maxLines - 1) { ctx.fillText(line + '...', x, y); return; }
    } else { line = test; }
  }
  if (line) ctx.fillText(line, x, y);
}

function createCard(q, i) {
  const canvas = document.createElement('canvas');
  canvas.width = CARD_SIZE; canvas.height = CARD_SIZE;
  const ctx = canvas.getContext('2d', { alpha: false });
  const state = { q, index: i, hoverIdx: -1, selectedIdx: -1, respondida: false, isCorreta: null };

  function draw() {
    const grad = ctx.createLinearGradient(0, 0, CARD_SIZE, CARD_SIZE);
    grad.addColorStop(0, '#060913'); grad.addColorStop(1, '#0a1520');
    ctx.fillStyle = grad; ctx.fillRect(0, 0, CARD_SIZE, CARD_SIZE);

    ctx.strokeStyle = 'rgba(0,209,255,0.04)'; ctx.lineWidth = 1;
    for (let gx = 0; gx < CARD_SIZE; gx += 64) { ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, CARD_SIZE); ctx.stroke(); }
    for (let gy = 0; gy < CARD_SIZE; gy += 64) { ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(CARD_SIZE, gy); ctx.stroke(); }

    ctx.strokeStyle = '#00d1ff'; ctx.lineWidth = 8; ctx.strokeRect(4, 4, CARD_SIZE - 8, CARD_SIZE - 8);

    ctx.fillStyle = '#00d1ff'; ctx.font = 'bold 40px Segoe UI, Arial'; ctx.textAlign = 'left';
    ctx.fillText('▸ ' + (i + 1) + '. ' + q.materia.toUpperCase(), 50, 90);

    ctx.strokeStyle = 'rgba(0,209,255,0.4)'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(50, 115); ctx.lineTo(CARD_SIZE - 50, 115); ctx.stroke();

    ctx.fillStyle = '#e8f4ff'; ctx.font = '30px Segoe UI, Arial';
    wrapText(ctx, q.pergunta, 50, 175, CARD_SIZE - 100, 40, 8);

    q.alternativas.forEach((alt, idx) => {
      const yBase = CARD_ALT_START + idx * CARD_ALT_HEIGHT;
      const isHover = (state.hoverIdx === idx && !state.respondida);
      const isSelected = (state.respondida && state.selectedIdx === idx);

      if (isSelected) ctx.fillStyle = state.isCorreta ? '#00aa55' : '#aa2222';
      else if (isHover) ctx.fillStyle = 'rgba(0,209,255,0.20)';
      else ctx.fillStyle = 'rgba(10,21,32,0.7)';
      ctx.fillRect(45, yBase + 6, CARD_SIZE - 90, CARD_ALT_HEIGHT - 12);

      ctx.strokeStyle = isHover ? '#00d1ff' : 'rgba(0,209,255,0.25)';
      ctx.lineWidth = isHover ? 3 : 1;
      ctx.strokeRect(45, yBase + 6, CARD_SIZE - 90, CARD_ALT_HEIGHT - 12);

      ctx.fillStyle = isSelected ? '#ffffff' : '#b8d4e8';
      ctx.font = '26px Segoe UI, Arial'; ctx.textAlign = 'left';
      ctx.fillText(alt.length > 68 ? alt.slice(0, 65) + '...' : alt, 65, yBase + 62);
    });

    if (state.respondida) {
      ctx.fillStyle = state.isCorreta ? '#00ff88' : '#ff4444';
      ctx.font = 'bold 44px Segoe UI, Arial'; ctx.textAlign = 'right';
      ctx.fillText(state.isCorreta ? '✓' : '✗', CARD_SIZE - 50, 90);
    }
  }
  draw();

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = false;

  const material = new THREE.MeshBasicMaterial({ map: texture, transparent: false, side: THREE.FrontSide });
  const geometry = new THREE.PlaneGeometry(2.2, 2.2);
  const mesh = new THREE.Mesh(geometry, material);

  const cols = 4, spacing = 2.6;
  mesh.position.set(
    (i % cols) * spacing - ((cols - 1) * spacing / 2),
    1.6,
    Math.floor(i / cols) * -spacing - 2.5
  );

  mesh.userData = { type: 'card', isClickable: true, state, canvas, ctx, texture, redraw: draw };
  return mesh;
}

function handleCardClick(mesh, altIdx) {
  const state = mesh.userData.state;
  if (state.respondida) return;
  const alt = state.q.alternativas[altIdx];
  const letra = alt.trim().charAt(0).toUpperCase();
  const isCorreta = (letra === state.q.correta);
  state.respondida = true;
  state.selectedIdx = altIdx;
  state.isCorreta = isCorreta;
  mesh.userData.redraw();
  mesh.userData.texture.needsUpdate = true;
  updateHUD();
  showToast(isCorreta ? '✅ Correto! (' + letra + ')' : '❌ Errado. Correta: ' + state.q.correta);
  if (navigator.vibrate) navigator.vibrate(isCorreta ? 40 : 90);
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

function showToast(msg, ms) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.style.display = 'block';
  clearTimeout(window._toastT);
  window._toastT = setTimeout(() => { t.style.display = 'none'; }, ms || 1500);
}

// ═══════════════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════════════
const QUESTIONS = __Q_JSON__;

window.addEventListener('load', () => {
  const scene = document.querySelector('a-scene');
  if (!scene) return;
  if (scene.hasLoaded) initAll();
  else scene.addEventListener('loaded', initAll);

  function initAll() {
    const root = scene.object3D;
    // Cartões
    const cards = QUESTIONS.slice(0, 18).map((q, i) => createCard(q, i));
    cards.forEach(c => root.add(c));
    PanelState.cards = cards;
    // Painéis
    buildPanels();
    buildNavBar();
    loadPanels();
    // HUD inicial
    setTimeout(updateHUD, 500);
  }
});

document.getElementById('enter').addEventListener('click', () => {
  document.querySelector('a-scene').enterVR().catch(e => showToast('❌ ' + e.message));
});
</script>

<style>
html, body { margin: 0; padding: 0; width: 100%; height: 100vh; overflow: hidden;
  background: #060913; font-family: 'Segoe UI', Arial, sans-serif; }
#hud { position: fixed; top: 10px; left: 10px; z-index: 99999;
  background: rgba(6,9,19,0.94); color: #00d1ff;
  border: 1px solid rgba(0,209,255,0.5); padding: 10px 14px;
  border-radius: 6px; font-size: 12px; max-width: 460px; }
#hud .title { font-weight: 900; color: #fff; font-size: 13px; letter-spacing: 2px; }
#hud .counter { margin-top: 5px; color: #00ff88; font-weight: 700; }
#enter { position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%);
  z-index: 99999; background: linear-gradient(90deg, #00d1ff, #0050a8);
  color: #060913; border: 2px solid #00d1ff; padding: 14px 40px;
  border-radius: 6px; font-weight: 900; font-size: 14px; letter-spacing: 2px; cursor: pointer; }
#toast { position: fixed; bottom: 90px; left: 50%; transform: translateX(-50%);
  z-index: 999999; background: rgba(6,9,19,0.96); color: #00d1ff;
  border: 2px solid #00d1ff; padding: 10px 22px; border-radius: 6px;
  font-size: 13px; font-weight: 700; display: none; pointer-events: none; }
</style>
</head>
<body>

<div id="hud">
  <div class="title">⬢ PMSC · PAINÉIS MÓVEIS</div>
  <div class="counter">STATUS: <span id="status">0/__LEN__</span></div>
</div>
<button id="enter">▶ ENTRAR NO VR</button>
<div id="toast"></div>

<a-scene id="scene"
  background="color: #060913"
  renderer="colorManagement: true; antialias: true; precision: high; sortObjects: false; powerPreference: high-performance; foveationLevel: high"
  webxr="referenceSpaceType: local-floor; requiredFeatures: local-floor; optionalFeatures: hand-tracking, bounded-floor, hit-test, passthrough"
  vr-mode-ui="enabled: true" embedded style="width: 100%; height: 100vh;">

  <a-sky id="sky" material="shader: flat; color: #060913"></a-sky>
  <a-entity id="ambientLight" light="type: ambient; intensity: 0.8"></a-entity>
  <a-entity light="type: directional; intensity: 0.4; castShadow: false" position="3 6 4"></a-entity>
  <a-plane rotation="-90 0 0" width="80" height="80" color="#0a0f1a"
    material="shader: flat; opacity: 1; transparent: false"></a-plane>

  <a-entity id="rig" position="0 0 0">
    <a-entity id="head" camera look-controls position="0 1.6 0">
      <a-entity id="hudPanel" position="0 -0.32 -0.9" scale="0.5 0.5 0.5">
        <a-text id="hudVRText" value="0/__LEN__" color="#00d1ff" width="1.0"
          align="center" position="0 0.06 0.004" font="mozillavr" shader="msdf" negate="false"></a-text>
      </a-entity>
    </a-entity>

    <a-entity id="leftHand"
      laser-controls="hand: left"
      hand-tracking-controls="hand: left; modelStyle: dots; color: #00d1ff"
      vr-hand
      raycaster="objects: .clickable; far: 20; interval: 100"
      line="color: #00d1ff; opacity: 0.9">
    </a-entity>

    <a-entity id="rightHand"
      laser-controls="hand: right"
      hand-tracking-controls="hand: right; modelStyle: dots; color: #ff8a00"
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
# UI STREAMLIT (preservada)
# ═══════════════════════════════════════════════════════════════════════
st.title("⬢ PMSC Arena VR — Painéis Móveis")
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
            st.session_state.treino = [{**q, "materia": mat} for q in random.sample(pool, min(qtd, len(pool)))]
            st.session_state.simulado = None
            st.session_state.vr_ready = False
            st.rerun()
    st.divider()
    st.subheader("📝 Simulado")
    st.caption(f"{TOTAL_OFICIAL} questões oficiais do edital")
    if st.button("Iniciar Simulado 60q", type="primary", use_container_width=True):
        st.session_state.simulado = {"questoes": montar_simulado(banco),
                                      "inicio": time.time(), "respostas": {}, "finalizado": False}
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
