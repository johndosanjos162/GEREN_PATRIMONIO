import streamlit as st
import streamlit.components.v1 as components
import json
import random
import pathlib
import time
import csv
import io
from datetime import datetime
from collections import defaultdict

st.set_page_config(page_title="PMSC 2026 - Cérebro VR v2", page_icon="🧠", layout="wide")

DISTRIBUICAO = {
    "Legislação Institucional": 10, "Direito Constitucional": 8,
    "Língua Portuguesa": 8, "Direito Penal Comum": 6,
    "Direito Processual Penal Comum": 6, "Direito Penal Militar": 6,
    "Legislação Especial": 6, "Legislação de Trânsito": 5, "Informática": 5,
}
PESOS_EDITAL = DISTRIBUICAO  # para previsão de nota

# ================== PARSERS (iguais) ==================
def _parse_concatenado(conteudo):
    decoder, idx, n, resultado = json.JSONDecoder(), 0, len(conteudo), {}
    while idx < n:
        while idx < n and conteudo[idx].isspace(): idx += 1
        if idx >= n: break
        try: obj, idx = decoder.raw_decode(conteudo, idx)
        except json.JSONDecodeError: break
        if isinstance(obj, dict):
            for m, l in obj.items():
                if isinstance(l, list): resultado.setdefault(m, []).extend(l)
        elif isinstance(obj, list):
            for q in obj: resultado.setdefault(q.get("materia", "Geral"), []).append(q)
    return resultado

def _deduplicar(lista):
    vistos, unicas, rem = set(), [], 0
    for q in lista:
        t = q.get("pergunta", "").strip().lower()
        if not t: continue
        if t in vistos: rem += 1; continue
        vistos.add(t); unicas.append(q)
    return unicas, rem

@st.cache_data(ttl=30, show_spinner=False)
def load_banco():
    base = pathlib.Path(__file__).parent
    cands = list(base.glob("*.json")) or list(pathlib.Path.cwd().glob("*.json"))
    resultado, bruto, removidas, ok = defaultdict(list), 0, 0, 0
    for p in cands:
        try:
            with open(p, "r", encoding="utf-8") as jf: conteudo = jf.read()
        except Exception: continue
        parsed = _parse_concatenado(conteudo)
        if not parsed: continue
        for k, v in parsed.items(): resultado[k].extend(v)
        bruto += sum(len(v) for v in parsed.values()); ok += 1
    if not resultado: return None, None
    for k in list(resultado.keys()):
        un, r = _deduplicar(resultado[k]); resultado[k] = un; removidas += r
    return dict(resultado), {"arquivos": ok, "bruto": bruto, "removidas": removidas,
                              "unicas": sum(len(v) for v in resultado.values())}

def montar_simulado(banco):
    sim = []
    for mat, qtd in DISTRIBUICAO.items():
        pool = banco.get(mat, [])
        if not pool:
            for k, v in banco.items():
                if mat.lower() in k.lower() or k.lower() in mat.lower(): pool = v; break
        if pool:
            sel = random.sample(pool, min(qtd, len(pool)))
            sim.extend([{**q, "materia": mat} for q in sel])
    random.shuffle(sim); return sim

# ================== SESSION ==================
for k, d in [("simulado", None), ("treino", []), ("hist", []),
             ("erros", []), ("modo_vr", "ARENA")]:
    if k not in st.session_state: st.session_state[k] = d

banco, info = load_banco()
if not banco:
    st.error("❌ Nenhum .json válido encontrado.")
    try: st.write("Arquivos:", [f.name for f in pathlib.Path(__file__).parent.iterdir()])
    except: pass
    st.stop()

# ================== HEADER ==================
st.title("🧠 PMSC VR — Cérebro de Aprendizagem v2.0")
st.caption(f"✅ {info['unicas']}q únicas · {info['removidas']} duplicatas · Meta Quest 3S")

# ================== SIDEBAR ==================
with st.sidebar:
    st.success(f"📚 {info['unicas']}q únicas")
    if st.button("🔄 Recarregar banco", use_container_width=True):
        load_banco.clear(); st.rerun()
    st.divider()
    mat = st.selectbox("Matéria", list(banco.keys()))
    qtd = st.slider("Qtd", 5, 20, 10)
    if st.button("📚 Treino", use_container_width=True):
        pool = banco.get(mat, [])
        st.session_state.treino = [{**q, "materia": mat}
                                   for q in random.sample(pool, min(qtd, len(pool)))]
        st.session_state.simulado = None; st.rerun()
    st.divider()
    if st.button("📝 Simulado 60q", type="primary", use_container_width=True):
        st.session_state.simulado = {"questoes": montar_simulado(banco),
                                      "inicio": time.time(), "respostas": {}, "finalizado": False}
        st.session_state.treino = []; st.rerun()
    if st.session_state.simulado and not st.session_state.simulado["finalizado"]:
        if st.button("❌ Cancelar", use_container_width=True):
            st.session_state.simulado = None; st.rerun()

    # ========== NOVAS FUNÇÕES SIDEBAR ==========
    st.divider()
    st.subheader("🧠 Cérebro de Aprendizagem")
    with st.expander("⚙️ Configurar repetição espaçada"):
        st.caption("Intervalos: 1h → 1d → 3d → 7d → 15d → 30d")
        st.info("Os blocos errados voltam automaticamente. Funciona dentro do VR via localStorage.")

    with st.expander("📊 Analytics"):
        if st.session_state.hist:
            ult = st.session_state.hist[-1]
            st.metric("Última nota", f"{ult['nota']}%")
            st.metric("Acertos", f"{ult['acertos']}/{ult['total']}")
        else:
            st.caption("Faça um simulado para ver analytics.")
        # Previsão de nota
        if st.session_state.hist:
            media = sum(h["nota"] for h in st.session_state.hist) / len(st.session_state.hist)
            previsao = round(media * 0.9, 1)
            status = "APROVADO ✅" if previsao >= 50 else "REPROVADO ❌"
            st.metric("Previsão próxima prova", f"{previsao}%", status)

    with st.expander("🔴 Banco de Erros"):
        n_erros = len(st.session_state.erros)
        st.metric("Questões erradas", n_erros)
        if n_erros > 0:
            # Export Anki como CSV
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["pergunta", "alternativas", "correta", "materia"])
            for e in st.session_state.erros:
                writer.writerow([e["pergunta"], " | ".join(e["alternativas"]),
                                e["correta"], e.get("materia", "")])
            st.download_button(
                "📥 Exportar para Anki (CSV)",
                data=buf.getvalue(),
                file_name=f"pmsc_erros_{datetime.now():%Y%m%d_%H%M}.csv",
                mime="text/csv",
                use_container_width=True
            )
            st.caption("Importe no Anki: File → Import")

    with st.expander("🎯 Foco / Pomodoro"):
        st.caption("Dentro do VR: 25min foco + 5min passthrough")
        st.info("Botões no painel principal do VR: POMODORO · RESPIRAÇÃO · FOCO")

    with st.expander("🌐 Edital vivo"):
        st.markdown("""
- [Edital PMSC 2026 (PDF)](https://www.pmsc.sc.gov.br)
- [Constituição Federal](https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm)
- [Código Penal](https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm)
- [Código Penal Militar](https://www.planalto.gov.br/ccivil_03/decreto-lei/del1001.htm)
- [CTB](https://www.planalto.gov.br/ccivil_03/leis/l9503compilado.htm)
        """)

# ==================================================================
# RENDER VR — VERSÃO 2.0 (todas as features)
# ==================================================================
def render_vr(questoes, modo="ARENA", height=950):
    key = f"vr_{modo}"
    if not st.session_state.get(key, False):
        st.info(f"{len(questoes)} questões prontas.")
        if st.button(f"🥽 CARREGAR VR — {modo}",
                     key=f"btn_{key}", type="primary", use_container_width=True):
            st.session_state[key] = True; st.rerun()
        return

    amostra = questoes[:18]
    safe = [{"pergunta": q["pergunta"][:190].replace('"', "'").replace("\n", " "),
             "alternativas": [a[:62].replace('"', "'") for a in q["alternativas"][:5]],
             "correta": q["correta"].upper(),
             "materia": q.get("materia", "Geral")[:22],
             "explicacao": q.get("explicacao", "")[:180]} for q in amostra]
    q_json = json.dumps(safe, ensure_ascii=False).replace("</", "<\\/")

    html_template = r"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v7.4.0/dist/aframe-extras.min.js"></script>
<script src="https://unpkg.com/super-hands@3.0.5/dist/super-hands.min.js"></script>
<script>
// ================================================================
// CÉREBRO - Repetição espaçada, histórico, analytics (localStorage)
// ================================================================
window.Brain = {
  KEY: 'pmsc_brain_v2',
  load() {
    try { return JSON.parse(localStorage.getItem(this.KEY) || '{"cards":{},"history":[]}'); }
    catch { return {cards:{}, history:[]}; }
  },
  save(data) {
    try { localStorage.setItem(this.KEY, JSON.stringify(data)); } catch {}
  },
  recordAnswer(blockId, ok, pos) {
    const d = this.load();
    const card = d.cards[blockId] || {reviews:0, correct:0, wrong:0, streak:0, due:0, interval:0};
    card.reviews++;
    if (ok) { card.correct++; card.streak++; }
    else    { card.wrong++;   card.streak = 0; }
    // SM-2 simplificado
    const intervals = [60*60*1000, 24*3600*1000, 3*24*3600*1000,
                      7*24*3600*1000, 15*24*3600*1000, 30*24*3600*1000];
    const idx = Math.min(card.streak, intervals.length - 1);
    card.interval = intervals[idx];
    card.due = Date.now() + card.interval;
    card.lastPos = pos;
    d.cards[blockId] = card;
    d.history.push({t: Date.now(), blockId, ok, pos});
    if (d.history.length > 500) d.history = d.history.slice(-500);
    this.save(d);
  },
  getHeat(blockId) {
    const d = this.load();
    const c = d.cards[blockId];
    if (!c || c.reviews === 0) return 0;      // neutro
    const rate = c.correct / c.reviews;
    if (rate >= 0.8) return 2;                // forte (dourado)
    if (rate >= 0.5) return 1;                // médio (azul)
    return -1;                                 // fraco (vermelho)
  },
  getDueBlocks() {
    const d = this.load(); const now = Date.now();
    return Object.entries(d.cards)
      .filter(([_, c]) => c.due && c.due < now && c.streak < 6)
      .map(([id]) => id);
  },
  getErrorBank() {
    const d = this.load();
    return Object.entries(d.cards).filter(([_, c]) => c.wrong > 0);
  },
  getSpatialHistory() {
    const d = this.load();
    return d.history.slice(-50);
  },
  getScore() {
    const d = this.load();
    const bySubj = {};
    for (const [id, c] of Object.entries(d.cards)) {
      const mat = document.getElementById(id)?.getAttribute('data-materia') || 'Geral';
      if (!bySubj[mat]) bySubj[mat] = {c:0, t:0};
      bySubj[mat].c += c.correct; bySubj[mat].t += c.reviews;
    }
    return bySubj;
  }
};

// ================================================================
// COMPONENTE: BLOCO COMPLETO (grab + flashcard + freeze + heatmap)
// ================================================================
AFRAME.registerComponent('bloco-v2', {
  schema: { index: {type:'int'}, materia:{type:'string'}, correta:{type:'string'} },
  init: function() {
    const el = this.el;
    el.setAttribute('hoverable',''); el.setAttribute('grabbable','');
    el.setAttribute('draggable',''); el.setAttribute('stretchable',''); el.setAttribute('droppable','');
    el.userData = {virado: false, congelado: false, respondida: false, letraEscolhida: null};

    // Aplica heatmap ao criar
    setTimeout(() => this.applyHeat(), 100);

    el.addEventListener('grab-start', () => {
      if (el.userData.congelado) { showToast('🔒 Bloco congelado'); return; }
      el.object3D.scale.set(1.08,1.08,1.08);
      const box = el.querySelector('a-box');
      if (box) box.setAttribute('material','emissive','#ffaa00');
    });
    el.addEventListener('grab-end', () => {
      el.object3D.scale.set(1,1,1);
      const box = el.querySelector('a-box');
      if (box) box.setAttribute('material','emissive','#000000');
      // Flashcard: girar bloco = virar
      const rot = el.object3D.rotation.y;
      if (Math.abs(Math.abs(rot) - Math.PI) < 0.5 && !el.userData.virado) {
        this.virarFlashcard();
      }
      // Salva posição
      setTimeout(() => saveBlockPosition(el.id), 80);
    });
  },
  applyHeat: function() {
    const heat = Brain.getHeat(this.el.id);
    const box = this.el.querySelector('a-box');
    if (!box) return;
    const color = heat === 2 ? '#8a7200' : heat === -1 ? '#8a1f1f' : heat === 1 ? '#1f4a8a' : '#13244a';
    box.setAttribute('material', 'color', color);
  },
  virarFlashcard: function() {
    const el = this.el;
    el.userData.virado = true;
    const box = el.querySelector('a-box');
    // Cria canvas com a resposta + explicação
    const canvas = document.createElement('canvas');
    canvas.width = 512; canvas.height = 512;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#0a2a1a'; ctx.fillRect(0,0,512,512);
    ctx.strokeStyle = '#00cc66'; ctx.lineWidth = 6; ctx.strokeRect(3,3,506,506);
    ctx.fillStyle = '#fff'; ctx.font = 'bold 32px Segoe UI'; ctx.textAlign = 'center';
    ctx.fillText('✅ RESPOSTA', 256, 180);
    ctx.font = 'bold 100px Segoe UI'; ctx.fillStyle = '#00ff88';
    ctx.fillText(this.data.correta, 256, 320);
    ctx.font = '18px Segoe UI'; ctx.fillStyle = '#aaffaa';
    const q = QUESTIONS[this.data.index];
    if (q && q.explicacao) {
      const words = q.explicacao.split(' ');
      let line='', y=400;
      for (const w of words) {
        const test = line + w + ' ';
        if (ctx.measureText(test).width > 460) { ctx.fillText(line, 256, y); line = w+' '; y += 24; }
        else line = test;
      }
      ctx.fillText(line, 256, y);
    }
    ctx.font = '16px Segoe UI'; ctx.fillStyle = '#88aaff';
    ctx.fillText('Gire o bloco para voltar', 256, 480);
    const tex = new THREE.CanvasTexture(canvas);
    box.setAttribute('material', 'src', tex);
    showToast('📖 Flashcard virado');
  }
});

// ================================================================
// COMPONENTE: PRATELEIRAS VIRTUAIS (drop target)
// ================================================================
AFRAME.registerComponent('prateleira', {
  schema: { nome: {type:'string'} },
  init: function() {
    const el = this.el;
    el.setAttribute('droppable', '');
    el.addEventListener('drag-drop', (evt) => {
      const dropped = evt.detail.dropped;
      if (!dropped) return;
      // Reposiciona o bloco em cima da prateleira
      const pos = el.getAttribute('position');
      dropped.setAttribute('animation',
        'property: position; to: ' + pos.x + ' ' + (pos.y + 0.4) + ' ' + (pos.z + 0.3) + '; dur: 400');
      showToast('📚 Movido para ' + this.data.nome);
    });
  }
});

// ================================================================
// COMPONENTE: AI TEACHER RULE-BASED (dica contextual)
// ================================================================
AFRAME.registerComponent('ai-teacher', {
  init: function() {
    const el = this.el;
    window.mostrarDica = (idx) => {
      const q = QUESTIONS[idx];
      if (!q) return;
      const dica = q.explicacao ||
        `Art. relacionado à ${q.materia}. A alternativa correta é ${q.correta}. ` +
        `Analise o contexto da questão e verifique a legislação específica.`;
      const tEl = document.getElementById('aiTeacherText');
      if (tEl) tEl.setAttribute('value', '🤖 ' + dica);
      showToast('🤖 Professor: veja o painel direito');
    };
  }
});

// ================================================================
// CALIBRADOR MÃOS + PINCH STRENGTH + GESTOS + FADIGA
// ================================================================
AFRAME.registerComponent('hand-pro', {
  schema: { hand: {type:'string', default:'left'} },
  init: function() {
    this.pinch = 0; this.pinchStrength = 0; this.grip = false;
    this.lastPositions = [];
    this.jitter = 0;

    this.el.addEventListener('pinchstarted', () => this.pinch = 1);
    this.el.addEventListener('pinchended', () => this.pinch = 0);
    this.el.addEventListener('gripdown', () => this.grip = true);
    this.el.addEventListener('gripup', () => this.grip = false);
  },
  tick: function() {
    const p = this.el.object3D.position;
    // Detecta jitter (tremor/fadiga)
    this.lastPositions.push({x:p.x, y:p.y, z:p.z, t:Date.now()});
    if (this.lastPositions.length > 20) this.lastPositions.shift();
    if (this.lastPositions.length >= 10) {
      let sum = 0;
      for (let i = 1; i < this.lastPositions.length; i++) {
        const a = this.lastPositions[i-1], b = this.lastPositions[i];
        sum += Math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2 + (a.z-b.z)**2);
      }
      this.jitter = sum / this.lastPositions.length;
    }

    const id = this.data.hand === 'left' ? 'leftHandData' : 'rightHandData';
    const tEl = document.getElementById(id);
    if (!tEl) return;
    const tracking = this.el.components['hand-tracking-controls'] ? 'TRACK' : 'CTRL';
    const fadiga = this.jitter > 0.008 ? '⚠️FADIGA' : '';
    tEl.setAttribute('value',
      this.data.hand.toUpperCase() + ': ' + tracking +
      (this.pinch ? ' 🤏' : ' ✋') + (this.grip ? ' 👊' : '') + ' ' + fadiga +
      '\nPos ' + p.x.toFixed(2) + ' ' + p.y.toFixed(2) + ' ' + p.z.toFixed(2)
    );
  }
});

// ================================================================
// POMODORO + RESPIRAÇÃO + FOCO
// ================================================================
AFRAME.registerComponent('pomodoro', {
  init: function() {
    this.state = 'idle'; this.remaining = 25*60; this.cycles = 0;
    const el = this.el;
    window.startPomodoro = () => {
      this.state = 'focus'; this.remaining = 25*60;
      showToast('🍅 Foco 25min iniciado');
    };
    window.startBreathing = () => {
      this.state = 'breathing'; this.remaining = 60;
      showToast('🌬️ Respiração 1min');
      const sphere = document.getElementById('breathSphere');
      if (sphere) {
        sphere.setAttribute('visible', true);
        sphere.setAttribute('animation__scale',
          'property: scale; from: 0.3 0.3 0.3; to: 1 1 1; dur: 4000; dir: alternate; loop: 15; easing: easeInOutSine');
      }
    };
    window.setFocusMode = (on) => {
      document.getElementById('darkOverlay').setAttribute('visible', on);
      showToast(on ? '🌑 Modo foco' : '🌍 Modo normal');
    };
  },
  tick: function(t, dt) {
    if (this.state === 'idle') return;
    this.remaining -= dt/1000;
    if (this.remaining <= 0) {
      if (this.state === 'focus') {
        this.state = 'break'; this.remaining = 5*60; this.cycles++;
        showToast('☕ Pausa 5min — olhe para o passthrough');
      } else if (this.state === 'break') {
        this.state = 'focus'; this.remaining = 25*60;
        showToast('🍅 Foco 25min');
      } else {
        this.state = 'idle';
        const sphere = document.getElementById('breathSphere');
        if (sphere) sphere.setAttribute('visible', false);
      }
    }
    const timerEl = document.getElementById('pomodoroTimer');
    if (timerEl) {
      const m = Math.floor(this.remaining / 60);
      const s = Math.floor(this.remaining % 60);
      timerEl.setAttribute('value', (this.state === 'focus' ? '🍅 ' : this.state === 'break' ? '☕ ' : '') +
        m + ':' + s.toString().padStart(2,'0'));
    }
  }
});

// ================================================================
// FOCUS DETECTOR - olha para fora >10s = aviso
// ================================================================
AFRAME.registerComponent('focus-detector', {
  init: function() {
    this.lookAwayTime = 0;
    this.lastLook = Date.now();
    this.warned = false;
  },
  tick: function(t, dt) {
    const cam = document.getElementById('head');
    if (!cam) return;
    const dir = new THREE.Vector3(0,0,-1).applyQuaternion(cam.object3D.quaternion);
    // Se olhar muito para cima/baixo = distraído
    const dot = dir.y;
    if (Math.abs(dot) > 0.7) {
      this.lookAwayTime += dt/1000;
      if (this.lookAwayTime > 10 && !this.warned) {
        showToast('🎯 Volte aos blocos!', 3000);
        this.warned = true;
        setTimeout(() => { this.warned = false; }, 15000);
      }
    } else {
      this.lookAwayTime = Math.max(0, this.lookAwayTime - dt/1000);
    }
  }
});

// ================================================================
// COMFORT MODE - aproxima blocos se ficar parado
// ================================================================
AFRAME.registerComponent('comfort-mode', {
  init: function() {
    this.lastMove = Date.now();
    this.applied = false;
    document.getElementById('rig')?.addEventListener('thumbstickmoved', () => {
      this.lastMove = Date.now(); this.applied = false;
    });
  },
  tick: function() {
    if (Date.now() - this.lastMove > 60000 && !this.applied) {
      const blocks = document.querySelectorAll('[id^="block-"]');
      blocks.forEach(b => {
        const p = b.getAttribute('position');
        const head = document.getElementById('head');
        const hp = head ? head.getAttribute('position') : {x:0,y:1.65,z:0};
        const newPos = `${(p.x*0.7 + hp.x*0.3).toFixed(2)} ${(p.y*0.7 + hp.y*0.3).toFixed(2)} ${(p.z*0.7 + hp.z*0.3).toFixed(2)}`;
        b.setAttribute('animation','property: position; to: ' + newPos + '; dur: 2000');
      });
      showToast('🛋️ Modo conforto: blocos aproximados');
      this.applied = true;
    }
  }
});

// ================================================================
// CALIBRATION SYSTEM (mantido + novas ações)
// ================================================================
AFRAME.registerComponent('calib-v2', {
  init: function() {
    const rig = document.getElementById('rig');
    const head = document.getElementById('head');
    const left = document.getElementById('leftHand');
    const right = document.getElementById('rightHand');
    let handScale = 1, headH = 1.65;
    this.el.querySelectorAll('.calib-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const a = btn.getAttribute('data-action');
        if (a === 'resetPos') rig.setAttribute('position','0 0 8');
        if (a === 'handUp')   { handScale += 0.1; left.setAttribute('scale',`${handScale} ${handScale} ${handScale}`); right.setAttribute('scale',`${handScale} ${handScale} ${handScale}`); }
        if (a === 'handDown') { handScale = Math.max(0.2, handScale-0.1); left.setAttribute('scale',`${handScale} ${handScale} ${handScale}`); right.setAttribute('scale',`${handScale} ${handScale} ${handScale}`); }
        if (a === 'heightUp') { headH += 0.1; head.setAttribute('position',`0 ${headH} 0`); }
        if (a === 'heightDown') { headH = Math.max(0.4, headH-0.1); head.setAttribute('position',`0 ${headH} 0`); }
        if (a === 'organize') window.organizeBlocks();
        if (a === 'organizeByMat') window.organizeBySubject();
        if (a === 'organizeDue') window.organizeDue();
        if (a === 'scatter') window.scatterBlocks();
        if (a === 'freezeAll') window.freezeAll();
        if (a === 'unfreezeAll') window.unfreezeAll();
        if (a === 'resetArena') window.initWorld();
        if (a === 'saveLayout') window.saveLayout();
        if (a === 'loadLayout') window.loadLayout();
        if (a === 'passthrough') window.setBackground('passthrough');
        if (a === 'dark') window.setBackground('dark');
        if (a === 'focusMode') window.setFocusMode(true);
        if (a === 'normalMode') window.setFocusMode(false);
        if (a === 'pomodoro') window.startPomodoro();
        if (a === 'breathing') window.startBreathing();
        if (a === 'libraryMode') window.setBackground('library');
        if (a === 'spaceMode') window.setBackground('space');
        if (a === 'aiTeacher') window.mostrarDica(0);
        if (a === 'exportAnki') window.exportAnki();
        if (a === 'exitVR') {
          const sess = document.querySelector('a-scene').renderer.xr.getSession();
          if (sess) sess.end();
        }
        const orig = btn.getAttribute('material').color;
        btn.setAttribute('material','color','#00ff88');
        setTimeout(()=>btn.setAttribute('material','color',orig),200);
      });
    });
  }
});
</script>
<style>
html,body{margin:0;padding:0;width:100%;height:__HEIGHT__px;overflow:hidden;background:#050a14;font-family:Segoe UI}
#hud{position:fixed;top:8px;left:8px;z-index:99999;background:rgba(0,0,0,.92);color:#00e5ff;border:1px solid #00e5ff;padding:10px 14px;border-radius:10px;font-size:12px;max-width:400px}
#enter{position:fixed;bottom:12px;left:50%;transform:translateX(-50%);z-index:99999;background:linear-gradient(90deg,#00d1ff,#7000ff);color:white;border:none;padding:14px 32px;border-radius:999px;font-weight:900;font-size:15px;cursor:pointer}
#toast{position:fixed;bottom:80px;left:50%;transform:translateX(-50%);z-index:999999;background:rgba(0,0,0,.95);color:#00ff88;border:2px solid #00ff88;padding:10px 22px;border-radius:10px;font-size:14px;font-weight:700;display:none;pointer-events:none}
</style></head><body>

<div id="hud">
  <div style="font-weight:900;color:white;font-size:14px;">__MODO__ — v2.0 CÉREBRO</div>
  <b>Grip</b>=pegar · <b>Trigger</b>=responder · <b>Girar bloco</b>=flashcard<br>
  <div id="status" style="margin-top:6px;color:#00ff88;font-weight:700;">0/__LEN__ respondidas</div>
</div>
<button id="enter">🥽 ENTRAR VR</button>
<div id="toast"></div>

<a-scene id="scene" background="color:#050a14"
  renderer="antialias:true;colorManagement:true;alpha:true"
  webxr="optionalFeatures:hand-tracking,local-floor,bounded-floor,hit-test,passthrough"
  vr-mode-ui="enabled:true" embedded style="width:100%;height:__HEIGHT__px;">

  <a-sky id="sky" color="#050a14"></a-sky>
  <a-entity id="stars" visible="false"></a-entity>
  <a-entity id="darkOverlay" visible="false">
    <a-sky color="#000000"></a-sky>
  </a-entity>
  <a-entity light="type:ambient;intensity:0.9"></a-entity>
  <a-entity light="type:directional;intensity:1.1" position="4 7 4"></a-entity>
  <a-plane rotation="-90 0 0" width="120" height="120" color="#0a1430" opacity="0.6"></a-plane>

  <!-- ESFERA RESPIRAÇÃO -->
  <a-sphere id="breathSphere" visible="false" position="0 1.6 -2" radius="0.5"
    color="#00e5ff" material="opacity:0.5; transparent:true"></a-sphere>

  <a-entity id="rig" position="0 0 8" movement-controls="fly:true;speed:0.3">
    <a-entity id="head" camera look-controls wasd-controls="acceleration:20" position="0 1.65 0">
      <a-entity cursor="rayOrigin:mouse" raycaster="objects:.clickable,.ui" visible="false"></a-entity>
      <a-entity position="0 -0.6 -1.1">
        <a-plane width="1.6" height="0.34" color="black" opacity="0.75"></a-plane>
        <a-text id="hudVRText" value="0/18" color="#00ff88" width="1.9" align="center" position="-0.4 0 0.01"></a-text>
        <a-text id="pomodoroTimer" value="" color="#ffaa00" width="0.8" align="right" position="0.65 0 0.01"></a-text>
      </a-entity>
      <a-entity pomodoro></a-entity>
      <a-entity focus-detector></a-entity>
    </a-entity>

    <a-entity id="leftHand"
      hand-controls="hand:left;handModelStyle:lowPoly;color:#00d1ff"
      hand-tracking-controls="hand:left"
      hand-pro="hand:left"
      laser-controls="hand:left"
      raycaster="objects:.grabbable,.clickable,.ui;far:30"
      line="color:#00d1ff;opacity:0.9"
      super-hands="colliderEvent:raycaster-intersection;colliderEventProperty:els;colliderEndEvent:raycaster-intersection-cleared;colliderEndEventProperty:clearedEls;grabStartButtons:gripdown,pinchstarted;grabEndButtons:gripup,pinchended"
      sphere-collider="objects:.grabbable;radius:0.30">
    </a-entity>
    <a-entity id="rightHand"
      hand-controls="hand:right;handModelStyle:lowPoly;color:#ff8a00"
      hand-tracking-controls="hand:right"
      hand-pro="hand:right"
      laser-controls="hand:right"
      raycaster="objects:.grabbable,.clickable,.ui;far:30"
      line="color:#ff8a00;opacity:0.9"
      super-hands="colliderEvent:raycaster-intersection;colliderEventProperty:els;colliderEndEvent:raycaster-intersection-cleared;colliderEndEventProperty:clearedEls;grabStartButtons:gripdown,pinchstarted;grabEndButtons:gripup,pinchended"
      sphere-collider="objects:.grabbable;radius:0.30">
    </a-entity>
  </a-entity>

  <!-- ============ PAINEL PRINCIPAL (3 linhas + 2 novas) ============ -->
  <a-entity id="mainPanel" position="0 2.3 -3.5" calibration-plus=""
    hoverable grabbable draggable class="grabbable" calib-v2>
    <a-box width="5.0" height="3.2" depth="0.06" color="#0a0a0a" opacity="0.94" class="grabbable"></a-box>
    <a-text value="CÉREBRO VR v2.0" color="#00e5ff" width="5.5" align="center" position="0 1.45 0.05" class="grabbable"></a-text>

    <!-- LINHA 1: AMBIENTES -->
    <a-entity class="calib-btn clickable" data-action="passthrough" position="-1.9 1.1 0.05" geometry="primitive:plane;width:1.0;height:0.24" material="color:#7a1fa2"><a-text value="PASSTHROUGH" color="white" width="1.1" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="dark" position="-0.75 1.1 0.05" geometry="primitive:plane;width:0.9;height:0.24" material="color:#1a3a6a"><a-text value="ESCURO" color="white" width="1.0" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="libraryMode" position="0.35 1.1 0.05" geometry="primitive:plane;width:0.9;height:0.24" material="color:#5a3a1a"><a-text value="BIBLIOTECA" color="white" width="1.0" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="spaceMode" position="1.45 1.1 0.05" geometry="primitive:plane;width:0.8;height:0.24" material="color:#2a0a5a"><a-text value="ESPAÇO" color="white" width="0.9" align="center"></a-text></a-entity>

    <!-- LINHA 2: FOCO E POMODORO -->
    <a-entity class="calib-btn clickable" data-action="pomodoro" position="-1.9 0.78 0.05" geometry="primitive:plane;width:0.9;height:0.24" material="color:#8a1a1a"><a-text value="🍅 POMODORO" color="white" width="1.0" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="breathing" position="-0.75 0.78 0.05" geometry="primitive:plane;width:0.9;height:0.24" material="color:#1a6a5a"><a-text value="🌬️ RESPIRAR" color="white" width="1.0" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="focusMode" position="0.35 0.78 0.05" geometry="primitive:plane;width:0.9;height:0.24" material="color:#4a1a6a"><a-text value="🌑 FOCO" color="white" width="1.0" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="normalMode" position="1.45 0.78 0.05" geometry="primitive:plane;width:0.8;height:0.24" material="color:#1a3a6a"><a-text value="NORMAL" color="white" width="0.9" align="center"></a-text></a-entity>

    <!-- LINHA 3: ORGANIZAR -->
    <a-entity class="calib-btn clickable" data-action="organize" position="-1.9 0.46 0.05" geometry="primitive:plane;width:0.85;height:0.24" material="color:#1a3a6a"><a-text value="GRADE" color="white" width="0.9" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="organizeByMat" position="-0.85 0.46 0.05" geometry="primitive:plane;width:1.0;height:0.24" material="color:#1a6a3a"><a-text value="POR MATÉRIA" color="white" width="1.1" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="organizeDue" position="0.4 0.46 0.05" geometry="primitive:plane;width:1.0;height:0.24" material="color:#8a5a1a"><a-text value="VENCIDOS" color="white" width="1.1" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="scatter" position="1.5 0.46 0.05" geometry="primitive:plane;width:0.8;height:0.24" material="color:#6a1a1a"><a-text value="ESPALHAR" color="white" width="0.9" align="center"></a-text></a-entity>

    <!-- LINHA 4: SAVE/LOAD/FREEZE -->
    <a-entity class="calib-btn clickable" data-action="saveLayout" position="-1.9 0.14 0.05" geometry="primitive:plane;width:0.9;height:0.24" material="color:#00aa44"><a-text value="SALVAR" color="white" width="1.0" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="loadLayout" position="-0.85 0.14 0.05" geometry="primitive:plane;width:0.9;height:0.24" material="color:#aa8800"><a-text value="CARREGAR" color="white" width="1.0" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="freezeAll" position="0.15 0.14 0.05" geometry="primitive:plane;width:0.85;height:0.24" material="color:#8a1a5a"><a-text value="🔒 TRAVAR" color="white" width="0.9" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="unfreezeAll" position="1.1 0.14 0.05" geometry="primitive:plane;width:0.85;height:0.24" material="color:#5a8a1a"><a-text value="🔓 LIBERAR" color="white" width="0.9" align="center"></a-text></a-entity>

    <!-- LINHA 5: CALIBRAÇÃO -->
    <a-entity class="calib-btn clickable" data-action="handUp" position="-1.9 -0.18 0.05" geometry="primitive:plane;width:0.7;height:0.24" material="color:#2a5a1a"><a-text value="MÃO +" color="white" width="0.8" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="handDown" position="-1.1 -0.18 0.05" geometry="primitive:plane;width:0.7;height:0.24" material="color:#2a5a1a"><a-text value="MÃO -" color="white" width="0.8" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="heightUp" position="-0.3 -0.18 0.05" geometry="primitive:plane;width:0.7;height:0.24" material="color:#1a3a6a"><a-text value="ALT +" color="white" width="0.8" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="heightDown" position="0.5 -0.18 0.05" geometry="primitive:plane;width:0.7;height:0.24" material="color:#1a3a6a"><a-text value="ALT -" color="white" width="0.8" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="resetPos" position="1.3 -0.18 0.05" geometry="primitive:plane;width:0.7;height:0.24" material="color:#1a3a6a"><a-text value="RESET" color="white" width="0.8" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="resetArena" position="2.1 -0.18 0.05" geometry="primitive:plane;width:0.7;height:0.24" material="color:#1a3a6a"><a-text value="RESET ARENA" color="white" width="0.8" align="center"></a-text></a-entity>

    <!-- LINHA 6: AI TEACHER + EXPORT + EXIT -->
    <a-entity class="calib-btn clickable" data-action="aiTeacher" position="-1.9 -0.5 0.05" geometry="primitive:plane;width:1.0;height:0.24" material="color:#0a5a8a"><a-text value="🤖 PROFESSOR" color="white" width="1.1" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="exportAnki" position="-0.75 -0.5 0.05" geometry="primitive:plane;width:1.0;height:0.24" material="color:#8a6a0a"><a-text value="📥 ANKI" color="white" width="1.1" align="center"></a-text></a-entity>
    <a-entity class="calib-btn clickable" data-action="exitVR" position="2.1 -0.5 0.05" geometry="primitive:plane;width:0.7;height:0.24" material="color:#a00000"><a-text value="SAIR VR" color="white" width="0.8" align="center"></a-text></a-entity>

    <a-text value="Grip=pegar · Trigger=responder · Girar bloco=flashcard · Thumbstick=rotacionar"
      color="#ffaa00" width="4.8" align="center" position="0 -1.25 0.05" class="grabbable"></a-text>
  </a-entity>

  <!-- CALIBRADOR MÃOS -->
  <a-entity id="handCalibDisplay" position="3.5 2.3 -3.5" hoverable grabbable draggable>
    <a-box width="1.8" height="1.4" depth="0.06" color="#111111" opacity="0.92" class="grabbable"></a-box>
    <a-text value="MÃOS AO VIVO" color="#00ff88" width="2.4" align="center" position="0 0.55 0.05" class="grabbable"></a-text>
    <a-text id="leftHandData"  value="LEFT: aguardando"  color="#00d1ff" width="1.9" align="left" position="-0.75 0.15 0.05" wrap-count="34" class="grabbable"></a-text>
    <a-text id="rightHandData" value="RIGHT: aguardando" color="#ff8a00" width="1.9" align="left" position="-0.75 -0.35 0.05" wrap-count="34" class="grabbable"></a-text>
  </a-entity>

  <!-- AI TEACHER PANEL -->
  <a-entity id="aiTeacherPanel" position="-3.5 2.3 -3.5" hoverable grabbable draggable>
    <a-box width="1.8" height="1.2" depth="0.06" color="#051a2a" opacity="0.92" class="grabbable"></a-box>
    <a-text value="🤖 PROFESSOR IA" color="#00e5ff" width="2.2" align="center" position="0 0.45 0.05" class="grabbable"></a-text>
    <a-text id="aiTeacherText" value="Aguardando dica..." color="#ffffff" width="1.7" align="left" position="-0.7 -0.05 0.05" wrap-count="30" class="grabbable"></a-text>
  </a-entity>

  <!-- PRATELEIRAS -->
  <a-entity id="shelf1" position="-4 0.5 -6" prateleira="nome: Aprovadas">
    <a-box width="2.5" height="0.15" depth="0.8" color="#00aa44" opacity="0.8"></a-box>
    <a-text value="✅ APROVADAS" color="#00ff88" width="2.2" align="center" position="0 0.3 0"></a-text>
  </a-entity>
  <a-entity id="shelf2" position="0 0.5 -6" prateleira="nome: Revisar Hoje">
    <a-box width="2.5" height="0.15" depth="0.8" color="#aa8800" opacity="0.8"></a-box>
    <a-text value="📚 REVISAR HOJE" color="#ffaa00" width="2.2" align="center" position="0 0.3 0"></a-text>
  </a-entity>
  <a-entity id="shelf3" position="4 0.5 -6" prateleira="nome: Dúvidas">
    <a-box width="2.5" height="0.15" depth="0.8" color="#aa1a1a" opacity="0.8"></a-box>
    <a-text value="❓ DÚVIDAS" color="#ff4444" width="2.2" align="center" position="0 0.3 0"></a-text>
  </a-entity>

  <a-entity id="world"></a-entity>
  <a-entity comfort-mode></a-entity>
</a-scene>

<script>
const QUESTIONS = __Q_JSON__;
let answers = {}; let blocks = [];

function updateHUD() {
  const n = Object.keys(answers).length;
  const txt = n + '/' + QUESTIONS.length;
  document.getElementById('status').textContent = txt + ' respondidas';
  document.getElementById('hudVRText')?.setAttribute('value', txt);
}

function showToast(msg, ms) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.style.display = 'block';
  clearTimeout(window._tt);
  window._tt = setTimeout(() => t.style.display = 'none', ms || 1600);
}

// ===== AMBIENTES =====
window.setBackground = function(mode) {
  const sky = document.getElementById('sky');
  const stars = document.getElementById('stars');
  if (mode === 'passthrough') { window.enablePassthrough(); return; }
  stars.setAttribute('visible', 'false');
  sky.setAttribute('visible', 'true');
  if (mode === 'dark')    { sky.setAttribute('color', '#050a14'); sky.removeAttribute('src'); }
  if (mode === 'library') { sky.setAttribute('color', '#2a1808'); sky.removeAttribute('src'); }
  if (mode === 'space')   {
    sky.setAttribute('color', '#000005'); sky.removeAttribute('src');
    createStars(); stars.setAttribute('visible', 'true');
  }
  showToast('🌍 ' + mode.toUpperCase());
};

window.enablePassthrough = async function() {
  if (!navigator.xr) { showToast('❌ WebXR não suportado'); return; }
  try {
    const ok = await navigator.xr.isSessionSupported('immersive-ar');
    if (!ok) { showToast('❌ Use Meta Quest Browser no headset', 4000); return; }
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
      optionalFeatures: ['passthrough', 'hand-tracking', 'hit-test', 'bounded-floor', 'anchors']
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
  const c = document.getElementById('stars'); c.innerHTML = '';
  for (let i = 0; i < 300; i++) {
    const s = document.createElement('a-sphere');
    const r = 25 + Math.random()*15;
    const t = Math.random()*Math.PI*2, p = Math.acos(2*Math.random()-1);
    s.setAttribute('position', `${r*Math.sin(p)*Math.cos(t)} ${r*Math.sin(p)*Math.sin(t)} ${r*Math.cos(p)}`);
    s.setAttribute('radius', (0.03 + Math.random()*0.08).toString());
    s.setAttribute('color', '#ffffff');
    c.appendChild(s);
  }
}

// ===== CRIAR BLOCO v2 =====
function createBlock(q, i) {
  const cols = 4, spacing = 3.0;
  const x = (i%cols)*spacing - ((cols-1)*spacing/2);
  const z = Math.floor(i/cols)*-3.4 - 1.5;
  const y = 1.2 + Math.random()*0.5;

  const root = document.createElement('a-entity');
  root.setAttribute('id', 'block-' + i);
  root.setAttribute('position', `${x} ${y} ${z}`);
  root.setAttribute('class', 'grabbable');
  root.setAttribute('data-materia', q.materia);
  root.setAttribute('bloco-v2', `index:${i}; materia:${q.materia}; correta:${q.correta}`);

  const box = document.createElement('a-box');
  box.setAttribute('width','2.4'); box.setAttribute('height','2.2'); box.setAttribute('depth','0.24');
  box.setAttribute('color','#13244a'); box.setAttribute('class','grabbable');
  box.setAttribute('material','emissive:#000000; emissiveIntensity:0');

  const title = document.createElement('a-text');
  title.setAttribute('value', (i+1) + '. ' + q.materia);
  title.setAttribute('color','#00e5ff'); title.setAttribute('width','2.3');
  title.setAttribute('align','center'); title.setAttribute('position','0 0.85 0.14');
  title.setAttribute('class','grabbable');

  const qtext = document.createElement('a-text');
  const shortQ = q.pergunta.length > 150 ? q.pergunta.slice(0,147)+'...' : q.pergunta;
  qtext.setAttribute('value', shortQ);
  qtext.setAttribute('color','white'); qtext.setAttribute('width','2.2');
  qtext.setAttribute('align','center'); qtext.setAttribute('position','0 0.45 0.14');
  qtext.setAttribute('wrap-count','36'); qtext.setAttribute('class','grabbable');

  root.appendChild(box); root.appendChild(title); root.appendChild(qtext);

  q.alternativas.forEach((alt, idx) => {
    const letra = alt.trim().charAt(0).toUpperCase();
    const row = document.createElement('a-entity');
    row.setAttribute('position', `0 ${-0.05 - idx*0.28} 0.15`);
    row.setAttribute('class','clickable');
    row.setAttribute('data-i', i);

    const bg = document.createElement('a-plane');
    bg.setAttribute('width','2.0'); bg.setAttribute('height','0.22');
    bg.setAttribute('color','#0a1933'); bg.setAttribute('class','clickable');

    const txt = document.createElement('a-text');
    txt.setAttribute('value', alt.length > 60 ? alt.slice(0,57)+'...' : alt);
    txt.setAttribute('color','#cfe0ff'); txt.setAttribute('width','1.9');
    txt.setAttribute('position','-0.95 0 0.01'); txt.setAttribute('class','clickable');

    bg.appendChild(txt); row.appendChild(bg);

    row.addEventListener('click', (e) => {
      e.stopPropagation();
      if (root.userData.respondida) return;
      answers[i] = letra;
      const ok = letra === q.correta;
      bg.setAttribute('color', ok ? '#00c853' : '#d50000');
      root.userData.respondida = true;
      root.userData.letraEscolhida = letra;
      // Registra no cérebro
      const pos = root.getAttribute('position');
      Brain.recordAnswer(root.id, ok, pos);
      // Heatmap atualiza
      setTimeout(() => {
        const comp = root.components['bloco-v2'];
        if (comp) comp.applyHeat();
      }, 200);
      if (navigator.vibrate) navigator.vibrate(ok ? 40 : 90);
      updateHUD();
      if (!ok) {
        // Adiciona ao banco de erros
        const erros = JSON.parse(localStorage.getItem('pmsc_erros') || '[]');
        erros.push({pergunta: q.pergunta, alternativas: q.alternativas,
                    correta: q.correta, materia: q.materia});
        localStorage.setItem('pmsc_erros', JSON.stringify(erros.slice(-200)));
        // Auto-abre dica do professor
        window.mostrarDica && window.mostrarDica(i);
      }
    });
    root.appendChild(row);
  });

  blocks.push(root);
  return root;
}

// ===== SAVE/LOAD =====
const STORAGE_KEY = 'pmsc_layout_v2';
function saveBlockPosition(id) {
  const el = document.getElementById(id);
  if (!el) return;
  try {
    const L = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    L[id] = {p: el.getAttribute('position'), r: el.getAttribute('rotation') || {x:0,y:0,z:0}};
    localStorage.setItem(STORAGE_KEY, JSON.stringify(L));
  } catch {}
}
window.saveLayout = function() {
  const L = {};
  document.querySelectorAll('[id^="block-"]').forEach(el => {
    L[el.id] = {p: el.getAttribute('position'), r: el.getAttribute('rotation') || {x:0,y:0,z:0}};
  });
  localStorage.setItem(STORAGE_KEY, JSON.stringify(L));
  showToast('💾 ' + Object.keys(L).length + ' blocos salvos');
};
window.loadLayout = function() {
  const L = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  let n = 0;
  Object.entries(L).forEach(([id, d]) => {
    const el = document.getElementById(id);
    if (el) { el.setAttribute('position', d.p); if (d.r) el.setAttribute('rotation', d.r); n++; }
  });
  showToast('📂 ' + n + ' blocos restaurados');
};

// ===== ORGANIZAR =====
window.organizeBlocks = function() {
  blocks.forEach((b, i) => {
    const cols = 4, sp = 3.0;
    const x = (i%cols)*sp - ((cols-1)*sp/2);
    const z = Math.floor(i/cols)*-3.4 - 1.5;
    b.setAttribute('animation', `property:position; to:${x} 1.3 ${z}; dur:800`);
  });
  showToast('📐 GRADE');
};
window.organizeBySubject = function() {
  const by = {};
  blocks.forEach(b => {
    const m = b.getAttribute('data-materia') || 'Geral';
    (by[m] = by[m] || []).push(b);
  });
  const names = Object.keys(by);
  names.forEach((mat, s) => {
    const cluster = by[mat];
    const baseX = (s - (names.length-1)/2) * 8;
    cluster.forEach((b, i) => {
      const col = i%2, row = Math.floor(i/2);
      b.setAttribute('animation',
        `property:position; to:${baseX + (col-0.5)*2.8} 1.5 ${-3 - row*2.8}; dur:900`);
    });
  });
  showToast('🎯 POR MATÉRIA (' + names.length + ')');
};
window.organizeDue = function() {
  const due = Brain.getDueBlocks();
  if (!due.length) { showToast('✅ Nada vencido! Tudo em dia.'); return; }
  due.forEach((id, i) => {
    const b = document.getElementById(id);
    if (!b) return;
    const x = (i - due.length/2) * 2.8;
    b.setAttribute('animation', `property:position; to:${x} 1.5 -2; dur:800`);
  });
  showToast('⏰ ' + due.length + ' vencidos reorganizados');
};
window.scatterBlocks = function() {
  blocks.forEach(b => {
    b.setAttribute('animation',
      `property:position; to:${(Math.random()-0.5)*14} ${0.8+Math.random()*2.5} ${(Math.random()-0.5)*14-2}; dur:800`);
  });
  showToast('🎲 ESPALHADO');
};
window.freezeAll = function() {
  blocks.forEach(b => b.userData.congelado = true);
  showToast('🔒 Todos congelados');
};
window.unfreezeAll = function() {
  blocks.forEach(b => b.userData.congelado = false);
  showToast('🔓 Todos liberados');
};

// ===== EXPORT ANKI (dica visual - download via Streamlit) =====
window.exportAnki = function() {
  const erros = JSON.parse(localStorage.getItem('pmsc_erros') || '[]');
  showToast('📥 ' + erros.length + ' erros prontos. Baixe CSV no sidebar → Banco de Erros');
};

// ===== INIT =====
window.initWorld = function() {
  const w = document.getElementById('world');
  w.innerHTML = ''; blocks = []; answers = {};
  QUESTIONS.forEach((q, i) => w.appendChild(createBlock(q, i)));
  updateHUD();
};

document.addEventListener('DOMContentLoaded', () => window.initWorld());
document.getElementById('enter').addEventListener('click', () => {
  document.querySelector('a-scene').enterVR().catch(e => showToast('❌ ' + e.message));
});
</script>
</body></html>
"""
    html = (html_template
            .replace("__Q_JSON__", q_json)
            .replace("__MODO__", modo)
            .replace("__LEN__", str(len(safe)))
            .replace("__HEIGHT__", str(height)))
    components.html(html, height=height, scrolling=False)
    if st.button(f"❌ Fechar VR — {modo}", key=f"close_{modo}", use_container_width=True):
        st.session_state[key] = False; st.rerun()

# ==================================================================
# TABS
# ==================================================================
tab1, tab2, tab3, tab4 = st.tabs(["🧠 VR CÉREBRO", "📝 SIMULADO", "📚 TREINO", "📊 ANALYTICS"])

with tab1:
    todas = []
    for v in banco.values(): todas.extend(v)
    random.shuffle(todas)
    st.markdown("### Cérebro de Aprendizagem + Ambientes + Prateleiras + AI Teacher")
    render_vr(todas, modo="CEREBRO", height=950)

with tab2:
    if st.session_state.simulado:
        sim = st.session_state.simulado
        qs = sim["questoes"]
        if not sim["finalizado"]:
            rest = max(0, 4*3600 - int(time.time() - sim["inicio"]))
            h, m, s = rest//3600, (rest%3600)//60, rest%60
            st.warning(f"⏱️ {h:02d}:{m:02d}:{s:02d} · {len(qs)}q")
            render_vr(qs, modo="SIMULADO", height=950)
            st.divider()
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
                    ac = 0; dets = []
                    for i, q in enumerate(qs):
                        r = resp.get(i, ""); ok = r == q["correta"].upper()
                        if ok: ac += 1
                        dets.append({"pergunta": q["pergunta"], "materia": q.get("materia",""),
                                     "resposta": r, "correta": q["correta"], "acertou": ok})
                        if not ok:
                            st.session_state.erros.append({
                                "pergunta": q["pergunta"], "alternativas": q["alternativas"],
                                "correta": q["correta"], "materia": q.get("materia","")
                            })
                    nota = (ac/len(qs))*100
                    st.session_state.hist.append({
                        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
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
                with st.expander("Gabarito"):
                    for i, d in enumerate(ult["detalhes"]):
                        ic = "✅" if d["acertou"] else "❌"
                        st.markdown(f"{ic} **{i+1}. [{d['materia']}]** {d['pergunta']}")
                        st.caption(f"Sua: {d['resposta'] or '—'} · Gab: {d['correta']}")
            if st.button("🔄 Novo simulado", type="primary"):
                st.session_state.simulado = None; st.rerun()
    else:
        st.info("👈 Inicie um simulado na barra lateral.")

with tab3:
    if st.session_state.treino:
        mat = st.session_state.treino[0].get("materia","")
        st.subheader(f"📚 Treino — {mat}")
        render_vr(st.session_state.treino, modo="TREINO", height=950)
        for i, q in enumerate(st.session_state.treino):
            with st.expander(f"{i+1}. {q['pergunta'][:70]}..."):
                for a in q["alternativas"]: st.markdown(f"- {a}")
                st.success(f"✅ Gabarito: **{q['correta']}**")
        if st.button("❌ Encerrar treino"):
            st.session_state.treino = []; st.rerun()
    else:
        st.info("👈 Gere um treino na barra lateral.")

with tab4:
    st.subheader("📊 Analytics + Previsão de Nota")
    if st.session_state.hist:
        # Previsão por matéria (baseado em histórico simplificado)
        st.markdown("### 🎯 Previsão de nota próxima prova")
        media = sum(h["nota"] for h in st.session_state.hist) / len(st.session_state.hist)
        cols = st.columns(3)
        cols[0].metric("Média histórica", f"{media:.1f}%")
        cols[1].metric("Previsão (ponderação)", f"{media*0.9:.1f}%")
        cols[2].metric("Status", "APROVADO ✅" if media >= 50 else "REPROVADO ❌")

        st.markdown("### 📈 Histórico de simulados")
        for h in reversed(st.session_state.hist[-10:]):
            st.markdown(f"- {h['data']} — **{h['nota']}%** ({h['acertos']}/{h['total']}) — "
                        f"{'✅' if h['aprovado'] else '❌'}")

        st.markdown("### 🔴 Banco de erros")
        st.metric("Total de erros", len(st.session_state.erros))
        if st.session_state.erros:
            for e in st.session_state.erros[-10:]:
                with st.expander(f"❌ {e['materia']}: {e['pergunta'][:60]}..."):
                    for a in e["alternativas"]: st.markdown(f"- {a}")
                    st.success(f"Correta: **{e['correta']}**")
    else:
        st.info("Faça um simulado para ver analytics.")
