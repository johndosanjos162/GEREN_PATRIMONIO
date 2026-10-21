
import streamlit as st
import json
import random
import time
import pathlib
from collections import defaultdict
from datetime import datetime

st.set_page_config(page_title="PMSC 2026 AOCP - Quest 3S Full VR", page_icon="🎯", layout="wide")

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
def load_banco():
    base = pathlib.Path(__file__).parent
    candidatos = [f for f in base.iterdir() if f.is_file() and f.suffix.lower()==".json"]
    if not candidatos:
        return None, None
    for p in candidatos:
        try:
            with open(p,"r",encoding="utf-8") as f:
                data=json.load(f)
            if isinstance(data, dict):
                total=sum(len(v) for v in data.values() if isinstance(v,list))
                if total>0:
                    return data, f"{p.name} ({total}q)"
            elif isinstance(data,list):
                d=defaultdict(list)
                for q in data:
                    d[q.get("materia","Geral")].append(q)
                return dict(d), f"{p.name} ({len(data)}q)"
        except:
            continue
    return None, None

def montar_simulado(banco):
    sim=[]
    for mat,qtd in DISTRIBUICAO.items():
        pool=banco.get(mat,[])
        if not pool:
            for k,v in banco.items():
                if mat.lower() in k.lower() or k.lower() in mat.lower():
                    pool=v;break
        if pool:
            sim.extend([{**q,"materia":mat} for q in random.sample(pool,min(qtd,len(pool)))])
    random.shuffle(sim)
    return sim

if "simulado" not in st.session_state: st.session_state.simulado=None
if "treino" not in st.session_state: st.session_state.treino=[]
if "hist" not in st.session_state: st.session_state.hist=[]

banco, caminho = load_banco()
st.title("🎯 PMSC 2026 – Simulador AOCP | Quest 3S Full Body")
if not banco:
    st.error("json.json não encontrado. Coloque o json.json na raiz.")
    st.stop()
st.caption(f"✅ {caminho} | {sum(len(v) for v in banco.values())}q | Full VR Interativo")

with st.sidebar:
    st.success(f"📚 {sum(len(v) for v in banco.values())}q")
    for k,v in banco.items(): st.caption(f"{k}: {len(v)}")
    st.divider()
    mat=st.selectbox("Treino", list(banco.keys()))
    qtd=st.slider("Qtd",5,20,10)
    if st.button("▶️ Treino", use_container_width=True):
        pool=banco.get(mat,[])
        st.session_state.treino=[{**q, "materia":mat} for q in random.sample(pool,min(qtd,len(pool)))]
        st.session_state.simulado=None
        st.rerun()
    st.divider()
    if st.button("🚀 Simulado 60q", type="primary", use_container_width=True):
        st.session_state.simulado={"questoes":montar_simulado(banco),"inicio":time.time(),"respostas":{}, "finalizado":False}
        st.session_state.treino=[]
        st.rerun()
    if st.session_state.simulado and not st.session_state.simulado["finalizado"]:
        if st.button("❌ Cancelar"):
            st.session_state.simulado=None
            st.rerun()

def render_full_vr(questoes, modo="ARENA LIVRE", height=900):
    if not questoes:
        return
    key=f"show_full_{modo}"
    if not st.session_state.get(key, False):
        if st.button(f"🥽 ABRIR MODO VR COMPLETO {modo} - Quest 3S ({len(questoes[:20])} blocos interativos)", key=f"btn_{modo}", type="primary", use_container_width=True):
            st.session_state[key]=True
            st.rerun()
        st.markdown("""
        **Como funciona no Quest 3S:**
        - **Grip / Pinch (mão fechada)**: agarrar e mover blocos no espaço 3D
        - **Trigger / Pinch**: clicar nas alternativas A-E (laser)
        - **Thumbstick**: teleporte + andar suave
        - **Dentro do VR** terá painel para SAIR, RECALIBRAR corpo e RESETAR arena
        """)
        return

    amostra = questoes[:20]
    safe=[]
    for q in amostra:
        safe.append({
            "pergunta": q["pergunta"][:220].replace('"',"'").replace("\n"," "),
            "alternativas": [a[:70].replace('"',"'") for a in q["alternativas"][:5]],
            "correta": q["correta"].upper(),
            "materia": q.get("materia","Geral")[:25]
        })
    q_json = json.dumps(safe, ensure_ascii=False).replace("</","<\/")

    html = f"""
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v7.4.0/dist/aframe-extras.min.js"></script>
<script src="https://unpkg.com/super-hands@3.0.5/dist/super-hands.min.js"></script>
<script src="https://unpkg.com/aframe-event-set-component@5.0.0/dist/aframe-event-set-component.min.js"></script>
<style>
html,body{{margin:0;padding:0;width:100%;height:{height}px;overflow:hidden;background:#050a14;font-family:system-ui;}}
#overlay{{position:fixed;top:8px;left:8px;z-index:99999;background:rgba(0,0,0,0.85);color:#00e5ff;border:1px solid #00e5ff;padding:10px 14px;border-radius:10px;font-size:12px;line-height:1.4;max-width:360px;}}
#overlay b{{color:white;}}
#enter{{position:fixed;bottom:14px;left:50%;transform:translateX(-50%);z-index:99999;background:linear-gradient(90deg,#00d1ff,#7000ff);color:white;border:none;padding:14px 30px;border-radius:999px;font-weight:900;font-size:15px;letter-spacing:0.5px;box-shadow:0 0 25px #00d1ff88;cursor:pointer;}}
</style>
</head>
<body>
<div id="overlay">
<div style="font-weight:900;color:white;font-size:14px;margin-bottom:6px;">🥽 QUEST 3S FULL VR - {modo}</div>
<b>✅ Interação Total Ativa</b><br>
👊 <b>GRAB:</b> Grip / Pinch para mover blocos<br>
👉 <b>ANSWER:</b> Trigger / Pinch no laser A-E<br>
🕹️ <b>MOVER:</b> Thumbstick L = andar / Thumbstick R = girar<br>
📍 <b>TELEPORTE:</b> Thumbstick L click<br>
🧍 <b>CALIBRAR:</b> Painel no VR<br>
🚪 <b>SAIR:</b> Botão vermelho SAIR VR dentro do mundo<br>
<div id="hud" style="margin-top:8px;color:#00ff88;font-weight:700;">0/{len(safe)} respondidas</div>
</div>
<button id="enter">🥽 ENTRAR EM VR COMPLETO - QUEST 3S</button>

<a-scene
  background="color: #050a14"
  renderer="antialias:true; colorManagement:true; sortObjects:true; physicallyCorrectLights:true"
  webxr="optionalFeatures: hand-tracking, local-floor, bounded-floor, hit-test, body-tracking"
  vr-mode-ui="enabled:true"
  embedded
  style="width:100%;height:{height}px;"
>

<a-assets>
  <a-mixin id="grab-mix" hoverable grabbable stretchable draggable droppable></a-mixin>
</a-assets>

<a-entity light="type:ambient; intensity:0.8"></a-entity>
<a-entity light="type:directional; intensity:1.2; castShadow:true" position="3 6 4"></a-entity>
<a-entity light="type:point; intensity:0.7; distance:40; color:#00d1ff" position="0 5 0"></a-entity>

<a-plane rotation="-90 0 0" width="80" height="80" color="#0a1430" roughness="0.9"></a-plane>
<a-entity id="grid"></a-entity>

<a-entity position="0 2.8 -6">
  <a-plane width="8" height="2" color="#000000" opacity="0.8"></a-plane>
  <a-text value="PMSC 2026 - EDITAL AOCP - SOLDADO\nMODO VR COMPLETO - MOVA OS BLOCOS COM AS MÃOS" align="center" color="#00e5ff" width="7.5" position="0 0 0.02"></a-text>
</a-entity>

<a-entity id="rig" position="0 0 7" movement-controls="fly:true; speed:0.25">
  <a-entity id="head" camera look-controls="pointerLockEnabled:false" wasd-controls="acceleration:20" position="0 1.65 0">
    <a-entity cursor="rayOrigin: mouse" raycaster="objects: .clickable, .ui" visible="false"></a-entity>
    <a-entity id="hudVR" position="0 -0.6 -1.2">
      <a-plane width="1.1" height="0.35" color="black" opacity="0.75"></a-plane>
      <a-text id="hudVRText" value="0/20 respondidas" color="#00ff88" width="2" align="center" position="0 0 0.01"></a-text>
    </a-entity>
  </a-entity>

  <a-entity id="leftHand"
    hand-controls="hand: left; handModelStyle: lowPoly; color:#00d1ff"
    hand-tracking-controls="hand: left"
    super-hands="colliderEvent: raycaster-intersection; colliderEventProperty: els; colliderEndEvent: raycaster-intersection-cleared; colliderEndEventProperty: clearedEls; grabStartButtons: gripdown, pinchstart, triggerdown; grabEndButtons: gripup, pinchend, triggerup"
    laser-controls="hand: left"
    raycaster="objects: .clickable, .grabbable, .ui; far: 15"
    line="color:#00d1ff; opacity:0.9"
    sphere-collider="objects: .grabbable; radius:0.08"
    teleport-controls="cameraRig: #rig; teleportOrigin: #head; button: thumbstick"
  ></a-entity>

  <a-entity id="rightHand"
    hand-controls="hand: right; handModelStyle: lowPoly; color:#ff8a00"
    hand-tracking-controls="hand: right"
    super-hands="colliderEvent: raycaster-intersection; colliderEventProperty: els; colliderEndEvent: raycaster-intersection-cleared; colliderEndEventProperty: clearedEls; grabStartButtons: gripdown, pinchstart, triggerdown; grabEndButtons: gripup, pinchend, triggerup"
    laser-controls="hand: right"
    raycaster="objects: .clickable, .grabbable, .ui; far: 15"
    line="color:#ff8a00; opacity:0.9"
    sphere-collider="objects: .grabbable; radius:0.08"
    teleport-controls="cameraRig: #rig; teleportOrigin: #head; button: thumbstick"
  ></a-entity>

</a-entity>

<a-entity id="calibrationPanel" position="0 1.6 -1.2">
  <a-plane width="1.8" height="1.4" color="#0a0a0a" opacity="0.9"></a-plane>
  <a-text value="CALIBRAGEM QUEST 3S" color="#00e5ff" width="2.5" align="center" position="0 0.55 0.02"></a-text>
  <a-entity id="btnReset" class="ui clickable" position="-0.45 0.25 0.02" geometry="primitive: plane; width:0.7; height:0.22" material="color:#1a3a6a"><a-text value="RESET POSICAO" color="white" width="1.5" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity id="btnHeightUp" class="ui clickable" position="0.45 0.25 0.02" geometry="primitive: plane; width:0.7; height:0.22" material="color:#1a3a6a"><a-text value="ALTURA +" color="white" width="1.5" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity id="btnResetArena" class="ui clickable" position="-0.45 -0.05 0.02" geometry="primitive: plane; width:0.7; height:0.22" material="color:#1a3a6a"><a-text value="RESET ARENA" color="white" width="1.5" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity id="btnHeightDown" class="ui clickable" position="0.45 -0.05 0.02" geometry="primitive: plane; width:0.7; height:0.22" material="color:#1a3a6a"><a-text value="ALTURA -" color="white" width="1.5" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity id="btnExitVR" class="ui clickable" position="0 -0.45 0.02" geometry="primitive: plane; width:1.5; height:0.28" material="color:#a00000"><a-text value="SAIR DO VR" color="white" width="2" align="center" position="0 0 0.01"></a-text></a-entity>
</a-entity>

<a-entity id="world"></a-entity>
</a-scene>

<script>
const QUESTIONS = {q_json};
let answers = {{}};
let currentHeight = 1.65;
function updateHUD(){{
  const n = Object.keys(answers).length;
  const txt = `${{n}}/${{QUESTIONS.length}} respondidas`;
  const el = document.getElementById('hud');
  if(el) el.textContent = txt;
  const vrHud = document.getElementById('hudVRText');
  if(vrHud) vrHud.setAttribute('value', txt);
}}
function createQuestionBlock(q, i){{
  const cols=5, spacing=2.6;
  const x=(i%cols)*spacing - ((cols-1)*spacing/2);
  const z=Math.floor(i/cols)*-3.0;
  const y=1.4 + Math.random()*0.6;
  const rotY=(Math.random()-0.5)*25;
  const root=document.createElement('a-entity');
  root.setAttribute('id', `block-${{i}}`);
  root.setAttribute('position', `${{x}} ${{y}} ${{z}}`);
  root.setAttribute('rotation', `0 ${{rotY}} 0`);
  root.setAttribute('class','grabbable');
  root.setAttribute('mixin','grab-mix');
  root.setAttribute('hoverable',''); root.setAttribute('grabbable',''); root.setAttribute('stretchable',''); root.setAttribute('draggable',''); root.setAttribute('droppable','');
  const box=document.createElement('a-box');
  box.setAttribute('width','2.2'); box.setAttribute('height','2.0'); box.setAttribute('depth','0.18');
  box.setAttribute('color','#13244a'); box.setAttribute('class','grabbable');
  const title=document.createElement('a-text');
  title.setAttribute('value', `${{i+1}}. ${{q.materia}}`);
  title.setAttribute('color','#00e5ff'); title.setAttribute('width','2.1'); title.setAttribute('align','center');
  title.setAttribute('position','0 0.75 0.11'); title.setAttribute('wrap-count','32');
  const qtext=document.createElement('a-text');
  const shortQ = q.pergunta.length>160 ? q.pergunta.slice(0,157)+'...' : q.pergunta;
  qtext.setAttribute('value', shortQ);
  qtext.setAttribute('color','white'); qtext.setAttribute('width','2.0'); qtext.setAttribute('align','center');
  qtext.setAttribute('position','0 0.38 0.11'); qtext.setAttribute('wrap-count','35');
  root.appendChild(box); root.appendChild(title); root.appendChild(qtext);
  q.alternativas.forEach((alt, idx)=>{{
    const letra = alt.trim().charAt(0).toUpperCase();
    const row=document.createElement('a-entity');
    row.setAttribute('position', `0 ${{ -0.12 - idx*0.24 }} 0.12`);
    row.setAttribute('class','clickable'); row.setAttribute('data-i', i);
    const bg=document.createElement('a-plane');
    bg.setAttribute('width','1.95'); bg.setAttribute('height','0.20');
    bg.setAttribute('color','#0a1933'); bg.setAttribute('class','clickable');
    const txt=document.createElement('a-text');
    const shortAlt = alt.length>60 ? alt.slice(0,57)+'...' : alt;
    txt.setAttribute('value', shortAlt);
    txt.setAttribute('color','#cfe0ff'); txt.setAttribute('width','1.85');
    txt.setAttribute('position','-0.92 0 0.01');
    bg.appendChild(txt); row.appendChild(bg);
    row.addEventListener('click', ()=>{{
      answers[i]=letra;
      document.querySelectorAll(`[data-i="${{i}}"] a-plane`).forEach(p=> p.setAttribute('color','#0a1933'));
      bg.setAttribute('color', letra===q.correta ? '#00c853' : '#d50000');
      if(navigator.vibrate) navigator.vibrate(letra===q.correta ? 50 : 100);
      root.setAttribute('animation','property: scale; from:1 1 1; to:1.08 1.08 1.08; dur:150; dir:alternate; loop:2');
      updateHUD();
    }});
    root.appendChild(row);
  }});
  return root;
}}
function initWorld(){{
  const world=document.getElementById('world');
  world.innerHTML='';
  QUESTIONS.forEach((q,i)=> world.appendChild(createQuestionBlock(q,i)));
  const grid=document.getElementById('grid');
  if(grid){{
    grid.innerHTML='';
    for(let i=-40;i<=40;i+=2){{
      const l1=document.createElement('a-box');
      l1.setAttribute('width','80'); l1.setAttribute('height','0.015'); l1.setAttribute('depth','0.015');
      l1.setAttribute('position',`0 0 ${{i}}`); l1.setAttribute('color','#12204a'); l1.setAttribute('opacity','0.35');
      grid.appendChild(l1);
    }}
  }}
}}
function setupCalibration(){{
  const rig=document.getElementById('rig');
  const head=document.getElementById('head');
  document.getElementById('btnReset').addEventListener('click', ()=>{{ rig.setAttribute('position','0 0 7'); head.setAttribute('position','0 1.65 0'); currentHeight=1.65; }});
  document.getElementById('btnHeightUp').addEventListener('click', ()=>{{ currentHeight+=0.1; head.setAttribute('position',`0 ${{currentHeight}} 0`); }});
  document.getElementById('btnHeightDown').addEventListener('click', ()=>{{ currentHeight=Math.max(0.5, currentHeight-0.1); head.setAttribute('position',`0 ${{currentHeight}} 0`); }});
  document.getElementById('btnResetArena').addEventListener('click', ()=>{{ initWorld(); answers={{}}; updateHUD(); }});
  document.getElementById('btnExitVR').addEventListener('click', ()=>{{ const scene=document.querySelector('a-scene'); if(scene.is('vr-mode')) scene.exitVR(); }});
}}
document.addEventListener('DOMContentLoaded', ()=>{{ initWorld(); setupCalibration(); }});
document.getElementById('enter').addEventListener('click', ()=>{{ document.querySelector('a-scene').enterVR(); }});
</script>
</body>
</html>
    """
    st.components.v1.html(html, height=height, scrolling=False)
    if st.button(f"❌ Fechar VR {modo}", key=f"close_full_{modo}"):
        st.session_state[key]=False
        st.rerun()

tab1, tab2, tab3 = st.tabs(["🥽 ARENA FULL VR", "🏆 SIMULADO FULL VR", "📖 TREINO FULL VR"])
with tab1:
    todas=[]
    for v in banco.values(): todas.extend(v)
    random.shuffle(todas)
    st.subheader("🥽 Arena Full VR - Interação Total Quest 3S")
    render_full_vr(todas, modo="ARENA LIVRE - FULL BODY", height=950)
with tab2:
    if st.session_state.simulado:
        sim=st.session_state.simulado
        qs=sim["questoes"]
        if not sim["finalizado"]:
            rest=max(0,4*3600-int(time.time()-sim["inicio"]))
            h,m,s=rest//3600,(rest%3600)//60,rest%60
            st.warning(f"⏱️ {h:02d}:{m:02d}:{s:02d} | {len(qs)} questões | FULL VR")
            render_full_vr(qs, modo="SIMULADO OFICIAL FULL VR", height=950)
            st.divider()
            with st.form("form_sim"):
                resp={}
                for i,q in enumerate(qs):
                    st.markdown(f"**{i+1}. [{q.get('materia','')}]** {q['pergunta']}")
                    esc=st.radio(f"q_{i}", q["alternativas"], index=None, key=f"sim_{i}", label_visibility="collapsed")
                    if esc: resp[i]=esc[0].upper()
                    st.divider()
                c1,c2=st.columns(2)
                if c1.form_submit_button("💾 Salvar"): 
                    sim["respostas"]=resp
                    st.rerun()
                if c2.form_submit_button("✅ Finalizar", type="primary"):
                    ac=0; dets=[]
                    for i,q in enumerate(qs):
                        r=resp.get(i,""); ok=r==q["correta"].upper()
                        if ok: ac+=1
                        dets.append({"pergunta":q["pergunta"],"materia":q.get("materia",""),"resposta":r,"correta":q["correta"],"acertou":ok})
                    nota=(ac/len(qs))*100
                    st.session_state.hist.append({"data":datetime.now().strftime("%Y-%m-%d %H:%M"),"acertos":ac,"total":len(qs),"nota":round(nota,2),"aprovado":nota>=50,"detalhes":dets,"tempo":time.time()-sim["inicio"]})
                    sim["finalizado"]=True
                    st.rerun()
        else:
            ult=st.session_state.hist[-1] if st.session_state.hist else None
            if ult:
                st.balloons()
                c1,c2,c3=st.columns(3)
                c1.metric("Nota", f"{ult['nota']}%")
                c2.metric("Acertos", f"{ult['acertos']}/{ult['total']}")
                c3.metric("Status", "✅ APROVADO" if ult["aprovado"] else "❌ REPROVADO")
                with st.expander("Gabarito"):
                    for i,d in enumerate(ult["detalhes"]):
                        st.markdown(f"{'✅' if d['acertou'] else '❌'} **{i+1}. [{d['materia']}]** {d['pergunta']}")
                        st.caption(f"Sua: {d['resposta'] or '—'} | Gab: {d['correta']}")
            if st.button("🔄 Novo Simulado", type="primary"):
                st.session_state.simulado=None
                st.rerun()
    else:
        st.info("Inicie o simulado na barra lateral.")
with tab3:
    if st.session_state.treino:
        st.subheader(f"Treino {st.session_state.treino[0].get('materia','')}")
        render_full_vr(st.session_state.treino, modo="TREINO FULL VR", height=950)
        for i,q in enumerate(st.session_state.treino):
            with st.expander(f"{i+1}. {q['pergunta'][:70]}..."):
                for a in q["alternativas"]: st.markdown(f"- {a}")
                st.success(f"Gabarito: {q['correta']}")
        if st.button("Encerrar treino"):
            st.session_state.treino=[]
            st.rerun()
    else:
        st.info("Gere um treino na barra lateral.")
