import streamlit as st
import json
import random
import time
import pathlib
import tempfile
import os
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

@st.cache_data
def load_banco_automatico():
    base_dir = pathlib.Path(__file__).parent
    candidatos = [
        base_dir / "json.json",
        base_dir / "json_corrigido.json",
        base_dir / "data.json",
        pathlib.Path("json.json"),
        pathlib.Path("json_corrigido.json"),
        pathlib.Path("/mount/src/nasa-5.0/json.json"),
    ]
    for p in candidatos:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
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
            "pergunta": q.get("pergunta","")[:280].replace('"',"'"),
            "alternativas": [a[:80].replace('"',"'") for a in q.get("alternativas", [])[:5]],
            "correta": q.get("correta","B").upper(),
            "materia": q.get("materia","Geral")[:30].replace('"',"'")
        })
    questoes_json = json.dumps(safe_q, ensure_ascii=False).replace("</", "<\\/")

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://aframe.io/releases/1.4.2/aframe.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v6.1.1/dist/aframe-extras.min.js"></script>
<script src="https://unpkg.com/super-hands@3.0.5/dist/super-hands.min.js"></script>
<style>
html,body{{margin:0;padding:0;width:100%;height:{height}px;overflow:hidden;background:#070d1e;font-family:sans-serif;}}
#hud{{position:fixed;top:10px;left:10px;z-index:9999;background:rgba(0,0,0,0.85);color:#00e5ff;border:1px solid #00e5ff;padding:12px 16px;border-radius:12px;font-size:13px;max-width:340px;}}
#vrBtn{{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);z-index:9999;background:linear-gradient(90deg,#00d1ff,#0066ff);color:white;border:none;padding:16px 36px;border-radius:999px;font-weight:900;font-size:16px;box-shadow:0 0 20px #00d1ff88;cursor:pointer;}}
</style>
</head>
<body>
<div id="hud">
<div style="font-size:15px;font-weight:900;color:white;margin-bottom:6px;">🥽 {modo}</div>
<div>🎯 <b>{len(safe_q)} blocos 3D</b></div>
<div>👊 Grip/Pinch = mover | Trigger = marcar</div>
<div id="status" style="margin-top:8px;color:#00ff88;">0/{len(safe_q)} respondidas</div>
</div>
<button id="vrBtn">🥽 ENTRAR EM VR - QUEST 3S</button>
<a-scene background="color: #070d1e" renderer="antialias:true" webxr="optionalFeatures: hand-tracking, local-floor, bounded-floor" vr-mode-ui="enabled:true" embedded style="width:100%;height:{height}px;">
  <a-entity light="type:ambient; intensity:0.7"></a-entity>
  <a-entity light="type:directional; intensity:1.0" position="2 6 3"></a-entity>
  <a-plane rotation="-90 0 0" width="60" height="60" color="#0d1733"></a-plane>
  <a-entity id="rig" position="0 0 6">
    <a-entity camera look-controls wasd-controls="acceleration:25" position="0 1.65 0"><a-cursor raycaster="objects: .clickable, .grabbable" color="#00d1ff"></a-cursor></a-entity>
    <a-entity hand-controls="hand:left; handModelStyle: lowPoly; color:#00d1ff" super-hands laser-controls="hand:left" raycaster="objects: .clickable, .grabbable; far:15"></a-entity>
    <a-entity hand-controls="hand:right; handModelStyle: lowPoly; color:#ff8a00" super-hands laser-controls="hand:right" raycaster="objects: .clickable, .grabbable; far:15"></a-entity>
  </a-entity>
  <a-entity id="world"></a-entity>
</a-scene>
<script>
const QUESTIONS = {questoes_json};
let answers = {{}};
function updateStatus(){{document.getElementById('status').textContent = Object.keys(answers).length + '/{len(safe_q)} respondidas';}}
function makeBlock(q,i){{
  const cols=5,spacing=2.4,x=(i%cols)*spacing-((cols-1)*spacing/2),z=Math.floor(i/cols)*-2.8,y=1.3+Math.random()*0.7;
  const root=document.createElement('a-entity');root.setAttribute('position',`${{x}} ${{y}} ${{z}}`);root.setAttribute('class','grabbable');root.setAttribute('grabbable','');
  const box=document.createElement('a-box');box.setAttribute('width','2.15');box.setAttribute('height','1.85');box.setAttribute('depth','0.18');box.setAttribute('color','#13244a');box.setAttribute('class','grabbable');
  const title=document.createElement('a-text');title.setAttribute('value',`${{i+1}}. ${{q.materia}}`);title.setAttribute('color','#00e5ff');title.setAttribute('width','2');title.setAttribute('align','center');title.setAttribute('position','0 0.68 0.11');
  const qtext=document.createElement('a-text');qtext.setAttribute('value',q.pergunta.length>150?q.pergunta.slice(0,147)+'...':q.pergunta);qtext.setAttribute('color','white');qtext.setAttribute('width','1.95');qtext.setAttribute('align','center');qtext.setAttribute('position','0 0.32 0.11');qtext.setAttribute('wrap-count','34');
  root.appendChild(box);root.appendChild(title);root.appendChild(qtext);
  q.alternativas.forEach((alt,idx)=>{{
    const letra=alt.trim().charAt(0).toUpperCase();
    const row=document.createElement('a-entity');row.setAttribute('position',`-0.05 ${{ -0.08 - idx*0.22 }} 0.12`);row.setAttribute('class','clickable');row.setAttribute('data-i',i);
    const bg=document.createElement('a-plane');bg.setAttribute('width','1.9');bg.setAttribute('height','0.19');bg.setAttribute('color','#0a1933');bg.setAttribute('class','clickable');
    const txt=document.createElement('a-text');txt.setAttribute('value',alt.length>54?alt.slice(0,51)+'...':alt);txt.setAttribute('color','#cfe0ff');txt.setAttribute('width','1.8');txt.setAttribute('position','-0.9 0 0.01');
    bg.appendChild(txt);row.appendChild(bg);
    row.addEventListener('click',()=>{{answers[i]=letra;document.querySelectorAll(`[data-i="${{i}}"] a-plane`).forEach(p=>p.setAttribute('color','#0a1933'));bg.setAttribute('color',letra===q.correta?'#00c853':'#d50000');updateStatus();}});
    root.appendChild(row);
  }});
  return root;
}}
document.addEventListener('DOMContentLoaded',()=>{{const world=document.getElementById('world');QUESTIONS.forEach((q,i)=>world.appendChild(makeBlock(q,i)));}});
document.getElementById('vrBtn').addEventListener('click',()=>{{document.querySelector('a-scene').enterVR();}});
</script>
</body>
</html>
"""
    # Usa st.components.v1.html ainda é o mais compatível, mas com nova API iframe se disponível
    try:
        # Streamlit 1.66+ tem st.html mas para HTML inline com JS, components ainda funciona
        import streamlit.components.v1 as components
        components.html(html_content, height=height, scrolling=False)
    except Exception:
        st.html(html_content)

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

if "simulado" not in st.session_state: st.session_state.simulado=None
if "historico" not in st.session_state: st.session_state.historico=[]
if "treino" not in st.session_state: st.session_state.treino=[]

banco, caminho = load_banco_automatico()

st.title("🎯 PMSC 2026 – Simulador Imersivo AOCP")
if banco:
    st.caption(f"✅ Banco automático: {caminho} | {sum(len(v) for v in banco.values())} questões | AOCP 60q | Quest 3S")
else:
    st.error("❌ Não encontrei json.json na raiz. Coloque o arquivo json.json junto com App.py no GitHub.")
    st.stop()

with st.sidebar:
    st.title("🎯 PMSC 2026 AOCP")
    st.success(f"📚 {sum(len(v) for v in banco.values())} questões")
    with st.expander("Matérias"):
        for k,v in banco.items():
            st.caption(f"{k}: {len(v)}")
    st.divider()
    st.subheader("🧠 Treino")
    mat = st.selectbox("Matéria", list(banco.keys()))
    qtd = st.slider("Qtd", 5, 20, 10)
    if st.button("▶️ Gerar Treino 3D", use_container_width=True):
        pool=banco.get(mat,[])
        amostra=random.sample(pool, min(qtd,len(pool)))
        for q in amostra: q["materia"]=mat
        st.session_state.treino=amostra
        st.session_state.simulado=None
        st.rerun()
    st.divider()
    st.subheader("🏆 Simulado 60q")
    if st.button("🚀 Iniciar Simulado Oficial", type="primary", use_container_width=True):
        sim = montar_simulado(banco, DISTRIBUICAO)
        st.session_state.simulado={"questoes":sim, "inicio":time.time(), "respostas":{}, "finalizado":False}
        st.session_state.treino=[]
        st.rerun()
    if st.session_state.simulado and not st.session_state.simulado["finalizado"]:
        if st.button("❌ Cancelar", use_container_width=True):
            st.session_state.simulado=None
            st.rerun()

tab1, tab2, tab3 = st.tabs(["🌐 ARENA QUEST 3S", "🏆 SIMULADO", "📖 TREINO"])

with tab1:
    st.subheader("🌐 Arena Imersiva - Quest 3S - Carregamento Automático")
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
            c1,c2=st.columns(2)
            c1.warning(f"⏱️ {h:02d}:{m:02d}:{s:02d}")
            c2.metric("Questões", len(questoes))
            render_arena_3d(questoes, modo="SIMULADO OFICIAL 60Q", height=900)
            st.divider()
            with st.form("form_sim"):
                respostas={}
                for i,q in enumerate(questoes):
                    st.markdown(f"**{i+1}. [{q.get('materia','')}]** {q['pergunta']}")
                    esc=st.radio(f"q_{i}", options=q["alternativas"], index=None, key=f"sim_{i}", label_visibility="collapsed")
                    if esc: respostas[i]=esc[0].upper()
                    st.divider()
                c1,c2=st.columns(2)
                salvar=c1.form_submit_button("💾 Salvar", use_container_width=True)
                final=c2.form_submit_button("✅ Finalizar", type="primary", use_container_width=True)
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
                c1,c2,c3=st.columns(3)
                c1.metric("Nota", f"{ultimo['nota']}%")
                c2.metric("Acertos", f"{ultimo['acertos']}/{ultimo['total']}")
                c3.metric("Status", "✅ APROVADO" if ultimo["aprovado"] else "❌ REPROVADO")
                with st.expander("Gabarito"):
                    for i,d in enumerate(ultimo["detalhes"]):
                        icon="✅" if d["acertou"] else "❌"
                        st.markdown(f"{icon} **{i+1}. [{d['materia']}]** {d['pergunta']}")
                        st.caption(f"Sua: {d['resposta'] or '—'} | Gab: {d['correta']}")
            if st.button("🔄 Novo Simulado", type="primary"):
                st.session_state.simulado=None
                st.rerun()
    else:
        st.info("Inicie o simulado na barra lateral.")

with tab3:
    if st.session_state.treino:
        st.subheader(f"Treino - {st.session_state.treino[0].get('materia','')}")
        render_arena_3d(st.session_state.treino, modo="TREINO", height=900)
        if st.button("Encerrar"):
            st.session_state.treino=[]
            st.rerun()
    else:
        st.info("Gere um treino na barra lateral.")
