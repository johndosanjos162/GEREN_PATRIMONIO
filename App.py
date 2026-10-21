import streamlit as st
import streamlit.components.v1 as components
import json
import random
import time
import pathlib
from datetime import datetime
from collections import defaultdict

st.set_page_config(
    page_title="PMSC 2026 – Simulador Imersivo AOCP",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

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

# ========== CARREGAMENTO AUTOMÁTICO DO JSON DA RAIZ (SEM UPLOAD) ==========
@st.cache_data
def load_banco_automatico():
    # Pega a pasta onde o App.py está (raiz do repo no Streamlit Cloud)
    base_dir = pathlib.Path(__file__).parent
    candidatos = [
        base_dir / "json.json",
        base_dir / "json_corrigido.json",
        base_dir / "data.json",
        base_dir / "questoes.json",
        pathlib.Path("json.json"),
        pathlib.Path("json_corrigido.json"),
    ]
    for p in candidatos:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Normaliza
                if isinstance(data, dict):
                    # já está no formato materia: [questoes]
                    return data, str(p)
                elif isinstance(data, list):
                    d = defaultdict(list)
                    for q in data:
                        mat = q.get("materia", q.get("disciplina", "Geral"))
                        d[mat].append(q)
                    return dict(d), str(p)
            except Exception as e:
                st.error(f"Erro ao ler {p}: {e}")
    return None, None

def render_arena_3d(questoes, modo="ARENA LIVRE", height=850):
    if not questoes:
        st.warning("Nenhuma questão para renderizar.")
        return
    amostra = questoes[:40]
    safe_q = []
    for q in amostra:
        safe_q.append({
            "pergunta": q.get("pergunta","")[:280],
            "alternativas": q.get("alternativas", [])[:5],
            "correta": q.get("correta","B").upper(),
            "materia": q.get("materia","Geral")[:30]
        })
    questoes_json = json.dumps(safe_q, ensure_ascii=False).replace("</", "<\\/")

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://aframe.io/releases/1.4.2/aframe.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v6.1.1/dist/aframe-extras.min.js"></script>
<script src="https://unpkg.com/super-hands@3.0.5/dist/super-hands.min.js"></script>
<style>
html,body{{margin:0; padding:0; width:100%; height:100%; overflow:hidden; background:#070d1e; font-family: sans-serif;}}
#hud {{
  position: fixed; top:10px; left:10px; z-index:9999;
  background: rgba(0,0,0,0.85); color:#00e5ff; border:1px solid #00e5ff;
  padding:12px 16px; border-radius:12px; font-size:13px; line-height:1.4; max-width:340px;
}}
#vrBtn {{
  position: fixed; bottom:18px; left:50%; transform:translateX(-50%); z-index:9999;
  background: linear-gradient(90deg,#00d1ff,#0066ff); color:white; border:none;
  padding:16px 36px; border-radius:999px; font-weight:900; font-size:16px; letter-spacing:1px;
  box-shadow:0 0 20px #00d1ff88; cursor:pointer;
}}
</style>
</head>
<body>
<div id="hud">
<div style="font-size:16px; font-weight:900; color:white; margin-bottom:6px;">🥽 META QUEST 3S - {modo}</div>
<div>🎯 <b>{len(safe_q)} blocos 3D</b></div>
<div>👊 <b>AGARRAR:</b> Grip / Pinch</div>
<div>👉 <b>RESPONDER:</b> Trigger / Laser</div>
<div id="status" style="margin-top:8px; color:#00ff88;">0/{len(safe_q)} respondidas</div>
</div>
<button id="vrBtn">🥽 ENTRAR EM VR - QUEST 3S</button>
<a-scene
  background="color: #070d1e"
  renderer="antialias:true; colorManagement:true"
  webxr="optionalFeatures: hand-tracking, local-floor, bounded-floor, hit-test"
  vr-mode-ui="enabled:true"
  embedded
  style="width:100%; height:100%;"
>
  <a-entity light="type:ambient; intensity:0.7"></a-entity>
  <a-entity light="type:directional; intensity:1.0" position="2 6 3"></a-entity>
  <a-entity light="type:point; intensity:0.6; distance:30; color:#00d1ff" position="0 4 0"></a-entity>
  <a-plane rotation="-90 0 0" width="60" height="60" color="#0d1733"></a-plane>
  <a-entity id="grid" position="0 0.02 0"></a-entity>
  <a-entity id="rig" position="0 0 6">
    <a-entity id="cam" camera look-controls wasd-controls="acceleration:25" position="0 1.65 0">
      <a-cursor raycaster="objects: .clickable, .grabbable" color="#00d1ff"></a-cursor>
    </a-entity>
    <a-entity hand-controls="hand:left; handModelStyle: lowPoly; color:#00d1ff"
      super-hands laser-controls="hand:left" raycaster="objects: .clickable, .grabbable; far:15" line="color:#00d1ff"></a-entity>
    <a-entity hand-controls="hand:right; handModelStyle: lowPoly; color:#ff8a00"
      super-hands laser-controls="hand:right" raycaster="objects: .clickable, .grabbable; far:15" line="color:#ff8a00"></a-entity>
  </a-entity>
  <a-entity id="world"></a-entity>
  <a-entity position="0 2.8 -4">
    <a-plane width="5" height="0.9" color="black" opacity="0.75"></a-plane>
    <a-text value="PMSC 2026 - EDITAL AOCP - SOLDADO\\nArena Imersiva Quest 3S" align="center" color="#00d1ff" width="4.8" position="0 0 0.02"></a-text>
  </a-entity>
</a-scene>
<script>
const QUESTIONS = {questoes_json};
let answers = {{}};
function updateStatus(){{
  const n = Object.keys(answers).length;
  document.getElementById('status').textContent = `${{n}}/${{QUESTIONS.length}} respondidas`;
}}
function makeBlock(q, i){{
  const cols = 5; const spacing = 2.4;
  const x = (i % cols)*spacing - ((cols-1)*spacing/2);
  const z = Math.floor(i/cols)* -2.8;
  const y = 1.3 + (Math.random()*0.7);
  const root = document.createElement('a-entity');
  root.setAttribute('position', `${{x}} ${{y}} ${{z}}`);
  root.setAttribute('class','grabbable'); root.setAttribute('grabbable',''); root.setAttribute('draggable','');
  const box = document.createElement('a-box');
  box.setAttribute('width','2.15'); box.setAttribute('height','1.85'); box.setAttribute('depth','0.18');
  box.setAttribute('color','#13244a'); box.setAttribute('class','grabbable');
  const title = document.createElement('a-text');
  title.setAttribute('value', `${{i+1}}. ${{q.materia}}`); title.setAttribute('color','#00e5ff');
  title.setAttribute('width','2'); title.setAttribute('align','center'); title.setAttribute('position','0 0.68 0.11');
  const qtext = document.createElement('a-text');
  const shortQ = q.pergunta.length>150 ? q.pergunta.slice(0,147)+'...' : q.pergunta;
  qtext.setAttribute('value', shortQ); qtext.setAttribute('color','white'); qtext.setAttribute('width','1.95');
  qtext.setAttribute('align','center'); qtext.setAttribute('position','0 0.32 0.11'); qtext.setAttribute('wrap-count','34');
  root.appendChild(box); root.appendChild(title); root.appendChild(qtext);
  q.alternativas.forEach((alt, idx)=>{{
    const letra = alt.trim().charAt(0).toUpperCase();
    const row = document.createElement('a-entity');
    row.setAttribute('position', `-0.05 ${{ -0.08 - idx*0.22 }} 0.12`);
    row.setAttribute('class','clickable'); row.setAttribute('data-i', i); row.setAttribute('data-l', letra);
    const bg = document.createElement('a-plane');
    bg.setAttribute('width','1.9'); bg.setAttribute('height','0.19'); bg.setAttribute('color','#0a1933'); bg.setAttribute('class','clickable');
    const txt = document.createElement('a-text');
    const shortAlt = alt.length>54 ? alt.slice(0,51)+'...' : alt;
    txt.setAttribute('value', shortAlt); txt.setAttribute('color','#cfe0ff'); txt.setAttribute('width','1.8');
    txt.setAttribute('position','-0.9 0 0.01');
    bg.appendChild(txt); row.appendChild(bg);
    row.addEventListener('click', ()=>{{
      answers[i]=letra;
      document.querySelectorAll(`[data-i="${{i}}"] a-plane`).forEach(p=> p.setAttribute('color','#0a1933'));
      bg.setAttribute('color', letra===q.correta ? '#00c853' : '#d50000');
      updateStatus();
    }});
    root.appendChild(row);
  }});
  return root;
}}
document.addEventListener('DOMContentLoaded', ()=>{{
  const world = document.getElementById('world');
  QUESTIONS.forEach((q,i)=> world.appendChild(makeBlock(q,i)));
  const grid = document.getElementById('grid');
  for(let i=-30;i<=30;i+=2){{
    const l1 = document.createElement('a-box');
    l1.setAttribute('width','60'); l1.setAttribute('height','0.02'); l1.setAttribute('depth','0.02');
    l1.setAttribute('position', `0 0 ${{i}}`); l1.setAttribute('color','#12204a'); l1.setAttribute('opacity','0.4');
    grid.appendChild(l1);
  }}
}});
document.getElementById('vrBtn').addEventListener('click', ()=>{{
  document.querySelector('a-scene').enterVR();
}});
</script>
</body>
</html>
"""
    components.html(html, height=height, scrolling=False)

def montar_simulado(banco, distribuicao):
    simulado=[]
    for materia,qtd in distribuicao.items():
        pool=[]
        for k,v in banco.items():
            if k.lower().strip()==materia.lower().strip():
                pool=v
                break
        if not pool:
            for k,v in banco.items():
                if materia.lower() in k.lower() or k.lower() in materia.lower():
                    pool=v
                    break
        if pool:
            amostra = random.sample(pool, min(qtd, len(pool)))
            for q in amostra:
                qc = q.copy()
                qc["materia"]=materia
                simulado.append(qc)
    random.shuffle(simulado)
    return simulado

# ========== STATE ==========
if "simulado" not in st.session_state: st.session_state.simulado=None
if "historico" not in st.session_state: st.session_state.historico=[]
if "treino" not in st.session_state: st.session_state.treino=[]

# Carrega automaticamente da raiz - SEM UPLOAD
banco, caminho = load_banco_automatico()
if banco is None:
    st.error("❌ Não encontrei o `json.json` na raiz do GitHub. Verifique se o arquivo está junto com o App.py no repositório.")
    st.info("Arquivos na pasta atual: " + ", ".join([str(p.name) for p in pathlib.Path(__file__).parent.iterdir()]))
    st.stop()

# ========== SIDEBAR ==========
with st.sidebar:
    st.title("🎯 PMSC 2026 AOCP")
    st.caption(f"📂 Carregado: {caminho}")
    st.success(f"📚 **{sum(len(v) for v in banco.values())}** questões em **{len(banco)}** matérias")
    with st.expander("Ver matérias"):
        for k,v in banco.items():
            st.caption(f"{k}: {len(v)}")
    
    st.divider()
    st.subheader("🧠 Treino Rápido")
    mat = st.selectbox("Matéria", list(banco.keys()))
    qtd = st.slider("Qtd", 5, 20, 10, key="treino_qtd")
    if st.button("▶️ Gerar Treino 3D", use_container_width=True):
        pool=banco.get(mat,[])
        amostra=random.sample(pool, min(qtd,len(pool)))
        for q in amostra: q["materia"]=mat
        st.session_state.treino=amostra
        st.session_state.simulado=None
        st.rerun()
    
    st.divider()
    st.subheader("🏆 Simulado Oficial 60q")
    if st.button("🚀 Iniciar Simulado Oficial", type="primary", use_container_width=True):
        sim = montar_simulado(banco, DISTRIBUICAO)
        st.session_state.simulado={"questoes":sim, "inicio":time.time(), "respostas":{}, "finalizado":False}
        st.session_state.treino=[]
        st.rerun()
    if st.session_state.simulado and not st.session_state.simulado["finalizado"]:
        if st.button("❌ Cancelar Simulado", use_container_width=True):
            st.session_state.simulado=None
            st.rerun()

    st.divider()
    st.markdown("### 🥽 Quest 3S")
    st.markdown("Grip/Pinch = mover\nTrigger = marcar")

# ========== MAIN ==========
st.title("🎯 PMSC 2026 – Simulador Imersivo AOCP")
st.caption(f"Edital AOCP | Banco carregado automaticamente: {caminho} | {sum(len(v) for v in banco.values())} questões | WebXR Quest 3S")

tab1, tab2, tab3 = st.tabs(["🌐 ARENA QUEST 3S (LIVRE)", "🏆 SIMULADO", "📖 TREINO"])

with tab1:
    st.subheader("🌐 Arena Imersiva Livre - Meta Quest 3S")
    st.caption("Blocos 3D carregados automaticamente do json.json da raiz. No Quest 3S clique em ENTRAR EM VR.")
    todas=[]
    for v in banco.values(): todas.extend(v)
    random.shuffle(todas)
    render_arena_3d(todas[:25], modo="ARENA LIVRE", height=900)

with tab2:
    if st.session_state.simulado:
        sim=st.session_state.simulado
        questoes=sim["questoes"]
        if not sim["finalizado"]:
            restante=max(0,4*3600 - int(time.time()-sim["inicio"]))
            h,m,s=restante//3600, (restante%3600)//60, restante%60
            c1,c2,c3=st.columns([2,1,1])
            c1.warning(f"⏱️ {h:02d}:{m:02d}:{s:02d} restantes")
            c2.metric("Questões", len(questoes))
            c3.metric("Respondidas", len(sim["respostas"]))
            st.subheader("🌐 Arena Oficial 60q - Quest 3S")
            render_arena_3d(questoes, modo="SIMULADO OFICIAL 60Q", height=900)
            st.divider()
            st.subheader("✍️ Cartão Resposta")
            with st.form("form_sim"):
                respostas={}
                for i,q in enumerate(questoes):
                    st.markdown(f"**{i+1}. [{q.get('materia','')}]** {q['pergunta']}")
                    esc=st.radio(f"q_{i}", options=q["alternativas"], index=None, key=f"sim_{i}", label_visibility="collapsed")
                    if esc: respostas[i]=esc[0].upper()
                    st.divider()
                c1,c2=st.columns(2)
                salvar=c1.form_submit_button("💾 Salvar", use_container_width=True)
                final=c2.form_submit_button("✅ Finalizar Prova", type="primary", use_container_width=True)
                if salvar:
                    sim["respostas"]=respostas
                    st.success("Salvo!")
                    st.rerun()
                if final:
                    acertos=0; detalhes=[]
                    for i,q in enumerate(questoes):
                        r=respostas.get(i,""); correta=q["correta"].upper(); ok=r==correta
                        if ok: acertos+=1
                        detalhes.append({"pergunta":q["pergunta"],"materia":q.get("materia",""),"resposta":r,"correta":correta,"acertou":ok})
                    nota=(acertos/len(questoes))*100 if questoes else 0
                    st.session_state.historico.append({"data":datetime.now().strftime("%Y-%m-%d %H:%M"),"acertos":acertos,"total":len(questoes),"nota":round(nota,2),"aprovado":nota>=50,"detalhes":detalhes,"tempo":time.time()-sim["inicio"]})
                    sim["finalizado"]=True
                    st.rerun()
        else:
            ultimo=st.session_state.historico[-1] if st.session_state.historico else None
            if ultimo:
                st.balloons()
                c1,c2,c3,c4=st.columns(4)
                c1.metric("Nota", f"{ultimo['nota']}%")
                c2.metric("Acertos", f"{ultimo['acertos']}/{ultimo['total']}")
                c3.metric("Status", "✅ APROVADO" if ultimo["aprovado"] else "❌ REPROVADO")
                c4.metric("Tempo", f"{int(ultimo['tempo']//60)} min")
                from collections import Counter
                ac_mat=Counter(); tot_mat=Counter()
                for d in ultimo["detalhes"]:
                    tot_mat[d["materia"]]+=1
                    if d["acertou"]: ac_mat[d["materia"]]+=1
                for mat in DISTRIBUICAO:
                    if tot_mat[mat]: st.progress(ac_mat[mat]/tot_mat[mat], text=f"{mat}: {ac_mat[mat]}/{tot_mat[mat]}")
                with st.expander("Gabarito"):
                    for i,d in enumerate(ultimo["detalhes"]):
                        icon="✅" if d["acertou"] else "❌"
                        st.markdown(f"{icon} **{i+1}. [{d['materia']}]** {d['pergunta']}")
                        st.caption(f"Sua: {d['resposta'] or '—'} | Gab: {d['correta']}")
            if st.button("🔄 Novo Simulado", type="primary"):
                st.session_state.simulado=None
                st.rerun()
    else:
        st.info("👈 Inicie o Simulado Oficial na barra lateral. A arena 3D com 60 blocos aparecerá aqui.")

with tab3:
    if st.session_state.treino:
        st.subheader(f"📖 Treino - {st.session_state.treino[0].get('materia','')}")
        render_arena_3d(st.session_state.treino, modo=f"TREINO {st.session_state.treino[0].get('materia','')}", height=900)
        for i,q in enumerate(st.session_state.treino):
            with st.expander(f"{i+1}. {q['pergunta'][:80]}..."):
                for alt in q["alternativas"]: st.markdown(f"- {alt}")
                st.success(f"Gabarito: {q['correta']}")
        if st.button("Encerrar Treino"):
            st.session_state.treino=[]
            st.rerun()
    else:
        st.info("Gere um treino na barra lateral.")

if st.session_state.historico:
    with st.sidebar:
        st.divider()
        st.subheader("📜 Histórico")
        for h in reversed(st.session_state.historico[-5:]):
            st.caption(f"{h['data']} – {h['acertos']}/{h['total']} ({h['nota']}%)")
