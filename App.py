
import streamlit as st
import json
import random
import pathlib
import time
from collections import defaultdict
from datetime import datetime

st.set_page_config(page_title="PMSC 2026 AOCP - Quest 3S Grab Individual", page_icon="🎯", layout="wide")

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
    for f in base.iterdir():
        if f.is_file() and f.suffix.lower()==".json":
            try:
                with open(f,"r",encoding="utf-8") as jf:
                    data=json.load(jf)
                if isinstance(data, dict):
                    total=sum(len(v) for v in data.values() if isinstance(v,list))
                    if total>0:
                        return data, f"{f.name} ({total}q)"
                elif isinstance(data,list):
                    d=defaultdict(list)
                    for q in data:
                        d[q.get("materia","Geral")].append(q)
                    return dict(d), f"{f.name} ({len(data)}q)"
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
if "vr_full" not in st.session_state: st.session_state.vr_full=False

banco, caminho = load_banco()
if not banco:
    st.error("json.json não encontrado na raiz.")
    st.stop()

st.title("🎯 PMSC 2026 – Quest 3S - Blocos Individuais + Calibragem")
st.caption(f"✅ {caminho} | {sum(len(v) for v in banco.values())}q | Mover bloco a bloco + Calibrador de mãos dentro do VR")

with st.sidebar:
    st.success(f"📚 {sum(len(v) for v in banco.values())}q")
    mat=st.selectbox("Matéria", list(banco.keys()))
    qtd=st.slider("Qtd",5,20,10)
    if st.button("▶️ Treino", use_container_width=True):
        pool=banco.get(mat,[])
        st.session_state.treino=[{**q,"materia":mat} for q in random.sample(pool,min(qtd,len(pool)))]
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

def render_vr_individual(questoes, modo="ARENA", height=950):
    amostra = questoes[:18]
    safe=[]
    for q in amostra:
        safe.append({
            "pergunta": q["pergunta"][:200].replace('"',"'").replace("\n"," "),
            "alternativas": [a[:65].replace('"',"'") for a in q["alternativas"][:5]],
            "correta": q["correta"].upper(),
            "materia": q.get("materia","Geral")[:22]
        })
    q_json = json.dumps(safe, ensure_ascii=False).replace("</","<\\/")

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v7.4.0/dist/aframe-extras.min.js"></script>
<script src="https://unpkg.com/super-hands@3.0.5/dist/super-hands.min.js"></script>
<script>
// Componente para mover bloco individualmente
AFRAME.registerComponent('individual-grab', {{
  init: function() {{
    this.grabbed = false;
    this.offset = new THREE.Vector3();
    this.el.addEventListener('grab-start', (e) => {{
      this.grabbed = true;
      this.el.setAttribute('material','color','#ffaa00');
      // Traz para frente
      this.el.object3D.position.y += 0.05;
      console.log('GRAB START bloco', this.el.id);
    }});
    this.el.addEventListener('grab-end', (e) => {{
      this.grabbed = false;
      this.el.setAttribute('material','color','#13244a');
      console.log('GRAB END bloco', this.el.id);
    }});
    this.el.addEventListener('hover-start', () => {{
      if(!this.grabbed) this.el.setAttribute('material','color','#1e3a6a');
    }});
    this.el.addEventListener('hover-end', () => {{
      if(!this.grabbed) this.el.setAttribute('material','color','#13244a');
    }});
  }}
}});

AFRAME.registerComponent('hand-calibrator', {{
  schema: {{
    handSize: {{type:'number', default:1}},
    offsetX: {{type:'number', default:0}},
    offsetY: {{type:'number', default:0}},
    offsetZ: {{type:'number', default:0}}
  }},
  init: function() {{
    this.updateHand();
  }},
  updateHand: function() {{
    const hand = this.el;
    hand.setAttribute('scale', `${{this.data.handSize}} ${{this.data.handSize}} ${{this.data.handSize}}`);
  }}
}});

AFRAME.registerComponent('calibration-panel', {{
  init: function() {{
    const panel = this.el;
    // Botões
    panel.querySelectorAll('.calib-btn').forEach(btn => {{
      btn.addEventListener('click', (e) => {{
        const action = btn.getAttribute('data-action');
        const rig = document.getElementById('rig');
        const left = document.getElementById('leftHand');
        const right = document.getElementById('rightHand');
        const head = document.getElementById('head');
        
        if(action==='resetPos'){{ rig.setAttribute('position','0 0 6'); }}
        if(action==='resetRot'){{ rig.setAttribute('rotation','0 0 0'); }}
        if(action==='handSizeUp'){{ 
          let s = left.getAttribute('scale').x + 0.1;
          left.setAttribute('scale',`${{s}} ${{s}} ${{s}}`);
          right.setAttribute('scale',`${{s}} ${{s}} ${{s}}`);
        }}
        if(action==='handSizeDown'){{ 
          let s = Math.max(0.3, left.getAttribute('scale').x - 0.1);
          left.setAttribute('scale',`${{s}} ${{s}} ${{s}}`);
          right.setAttribute('scale',`${{s}} ${{s}} ${{s}}`);
        }}
        if(action==='resetArena'){{
          window.initWorld();
        }}
        if(action==='exitVR'){{
          document.querySelector('a-scene').exitVR();
        }}
        if(action==='organize'){{
          window.organizeBlocks();
        }}
        // feedback
        btn.setAttribute('material','color','#00ff88');
        setTimeout(()=>btn.setAttribute('material','color','#1a3a6a'),200);
      }});
    }});
  }}
}});
</script>
<style>
html,body{{margin:0;padding:0;width:100%;height:{height}px;overflow:hidden;background:#050a14;font-family:system-ui;}}
#hud{{position:fixed;top:8px;left:8px;z-index:99999;background:rgba(0,0,0,0.9);color:#00e5ff;border:1px solid #00e5ff;padding:10px 14px;border-radius:10px;font-size:12px;max-width:360px;}}
#enter{{position:fixed;bottom:12px;left:50%;transform:translateX(-50%);z-index:99999;background:linear-gradient(90deg,#00d1ff,#7000ff);color:white;border:none;padding:14px 32px;border-radius:999px;font-weight:900;font-size:15px;box-shadow:0 0 25px #00d1ff88;cursor:pointer;}}
</style>
</head>
<body>
<div id="hud">
<div style="font-weight:900;color:white;font-size:14px;margin-bottom:6px;">🥽 {modo} - BLOCO INDIVIDUAL</div>
👊 <b>PEGAR 1 BLOCO:</b> Aponte mão, Grip/Pinch no bloco<br>
🖐️ <b>MOVER:</b> Segure e arraste no espaço<br>
👉 <b>SOLTAR:</b> Solte Grip - bloco fica onde parou<br>
📦 <b>ORGANIZAR:</b> Painel VR > ORGANIZAR<br>
<div id="status" style="margin-top:6px;color:#00ff88;font-weight:700;">0/{len(safe)} respondidas</div>
</div>
<button id="enter">🥽 ENTRAR VR - MOVER BLOCOS 1 A 1</button>

<a-scene
  background="color: #050a14"
  renderer="antialias:true; colorManagement:true"
  webxr="optionalFeatures: hand-tracking, local-floor, bounded-floor, hit-test"
  vr-mode-ui="enabled:true"
  embedded
  style="width:100%;height:{height}px;"
>

<a-entity light="type:ambient; intensity:0.9"></a-entity>
<a-entity light="type:directional; intensity:1.0; castShadow:true" position="3 6 4"></a-entity>
<a-plane rotation="-90 0 0" width="100" height="100" color="#0a1430"></a-plane>
<a-entity id="grid"></a-entity>

<a-entity id="rig" position="0 0 8" movement-controls="fly:true; speed:0.25">
  <a-entity id="head" camera look-controls wasd-controls="acceleration:18" position="0 1.65 0">
    <a-entity cursor="rayOrigin: mouse" raycaster="objects: .clickable, .ui, .grabbable" visible="false"></a-entity>
    <a-entity position="0 -0.55 -1.1">
      <a-plane width="1.0" height="0.3" color="black" opacity="0.7"></a-plane>
      <a-text id="hudVRText" value="0/18 respondidas" color="#00ff88" width="1.8" align="center" position="0 0 0.01"></a-text>
    </a-entity>
  </a-entity>

  <!-- MÃO ESQUERDA - CONFIGURADA PARA GRAB INDIVIDUAL -->
  <a-entity id="leftHand"
    hand-controls="hand: left; handModelStyle: lowPoly; color:#00d1ff"
    hand-tracking-controls="hand: left"
    super-hands="colliderEvent: raycaster-intersection; colliderEventProperty: els; colliderEndEvent: raycaster-intersection-cleared; colliderEndEventProperty: clearedEls; grabStartButtons: gripdown, pinchstart, triggerdown; grabEndButtons: gripup, pinchend, triggerup; stretchStartButtons: gripdown, pinchstart; stretchEndButtons: gripup, pinchend"
    laser-controls="hand: left"
    raycaster="objects: .clickable, .grabbable, .ui; far: 20; showLine:true"
    line="color:#00d1ff; opacity:0.9"
    sphere-collider="objects: .grabbable; radius:0.12"
    teleport-controls="cameraRig: #rig; teleportOrigin: #head; button: thumbstick; collisionEntities: #ground"
    hand-calibrator="handSize: 1"
  ></a-entity>

  <!-- MÃO DIREITA -->
  <a-entity id="rightHand"
    hand-controls="hand: right; handModelStyle: lowPoly; color:#ff8a00"
    hand-tracking-controls="hand: right"
    super-hands="colliderEvent: raycaster-intersection; colliderEventProperty: els; colliderEndEvent: raycaster-intersection-cleared; colliderEndEventProperty: clearedEls; grabStartButtons: gripdown, pinchstart, triggerdown; grabEndButtons: gripup, pinchend, triggerup; stretchStartButtons: gripdown, pinchstart; stretchEndButtons: gripup, pinchend"
    laser-controls="hand: right"
    raycaster="objects: .clickable, .grabbable, .ui; far: 20; showLine:true"
    line="color:#ff8a00; opacity:0.9"
    sphere-collider="objects: .grabbable; radius:0.12"
    teleport-controls="cameraRig: #rig; teleportOrigin: #head; button: thumbstick"
    hand-calibrator="handSize: 1"
  ></a-entity>
</a-entity>

<!-- PAINEL DE CALIBRAGEM DE MÃOS DENTRO DO VR -->
<a-entity id="calibPanel" position="0 1.7 -1.3" calibration-panel>
  <a-plane width="2.2" height="1.8" color="#0a0a0a" opacity="0.92"></a-plane>
  <a-text value="CALIBRAGEM MAOS + BLOCOS" color="#00e5ff" width="2.8" align="center" position="0 0.72 0.02"></a-text>
  
  <a-entity class="ui calib-btn clickable" data-action="resetPos" position="-0.55 0.45 0.02" geometry="primitive: plane; width:0.8; height:0.24" material="color:#1a3a6a"><a-text value="RESET POS" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn clickable" data-action="organize" position="0.55 0.45 0.02" geometry="primitive: plane; width:0.8; height:0.24" material="color:#1a3a6a"><a-text value="ORGANIZAR" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>

  <a-entity class="ui calib-btn clickable" data-action="handSizeUp" position="-0.55 0.15 0.02" geometry="primitive: plane; width:0.8; height:0.24" material="color:#1a3a6a"><a-text value="MAO +" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn clickable" data-action="handSizeDown" position="0.55 0.15 0.02" geometry="primitive: plane; width:0.8; height:0.24" material="color:#1a3a6a"><a-text value="MAO -" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>

  <a-entity class="ui calib-btn clickable" data-action="resetArena" position="-0.55 -0.15 0.02" geometry="primitive: plane; width:0.8; height:0.24" material="color:#1a3a6a"><a-text value="RESET ARENA" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn clickable" data-action="resetRot" position="0.55 -0.15 0.02" geometry="primitive: plane; width:0.8; height:0.24" material="color:#1a3a6a"><a-text value="RESET ROT" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>

  <a-entity class="ui calib-btn clickable" data-action="exitVR" position="0 -0.55 0.02" geometry="primitive: plane; width:1.8; height:0.32" material="color:#a00000"><a-text value="🚪 SAIR DO VR" color="white" width="2.2" align="center" position="0 0 0.01"></a-text></a-entity>
</a-entity>

<a-entity id="world"></a-entity>
<a-plane id="ground" rotation="-90 0 0" width="100" height="100" visible="false"></a-plane>

</a-scene>

<script>
const QUESTIONS = {q_json};
let answers = {{}};
let blocks = [];

function updateHUD(){{
  const n = Object.keys(answers).length;
  const txt = `${{n}}/${{QUESTIONS.length}} respondidas`;
  document.getElementById('status').textContent = txt;
  const vrHud = document.getElementById('hudVRText');
  if(vrHud) vrHud.setAttribute('value', txt);
}}

function createBlock(q, i){{
  const cols=4, spacing=2.8;
  const x=(i%cols)*spacing - ((cols-1)*spacing/2);
  const z=Math.floor(i/cols)*-3.2 -1;
  const y=1.2 + Math.random()*0.8;
  
  const root=document.createElement('a-entity');
  root.setAttribute('id', `block-${{i}}`);
  root.setAttribute('position', `${{x}} ${{y}} ${{z}}`);
  root.setAttribute('rotation', `0 ${{(Math.random()-0.5)*30}} 0`);
  root.setAttribute('class','grabbable');
  root.setAttribute('hoverable','');
  root.setAttribute('grabbable','');
  root.setAttribute('stretchable','');
  root.setAttribute('draggable','');
  root.setAttribute('droppable','');
  root.setAttribute('individual-grab','');
  root.setAttribute('dynamic-body','mass:0.8; shape:box; linearDamping:0.9; angularDamping:0.9');

  const box=document.createElement('a-box');
  box.setAttribute('width','2.3'); box.setAttribute('height','2.1'); box.setAttribute('depth','0.2');
  box.setAttribute('color','#13244a'); box.setAttribute('roughness','0.6'); box.setAttribute('metalness','0.15');
  box.setAttribute('class','grabbable');
  box.setAttribute('shadow','cast:true');

  const title=document.createElement('a-text');
  title.setAttribute('value', `${{i+1}}. ${{q.materia}}`);
  title.setAttribute('color','#00e5ff'); title.setAttribute('width','2.2'); title.setAttribute('align','center');
  title.setAttribute('position','0 0.8 0.12'); title.setAttribute('wrap-count','34');

  const qtext=document.createElement('a-text');
  const shortQ = q.pergunta.length>150 ? q.pergunta.slice(0,147)+'...' : q.pergunta;
  qtext.setAttribute('value', shortQ);
  qtext.setAttribute('color','white'); qtext.setAttribute('width','2.1'); qtext.setAttribute('align','center');
  qtext.setAttribute('position','0 0.42 0.12'); qtext.setAttribute('wrap-count','36');

  root.appendChild(box); root.appendChild(title); root.appendChild(qtext);

  q.alternativas.forEach((alt, idx)=>{{
    const letra = alt.trim().charAt(0).toUpperCase();
    const row=document.createElement('a-entity');
    row.setAttribute('position', `0 ${{ -0.08 - idx*0.26 }} 0.13`);
    row.setAttribute('class','clickable'); row.setAttribute('data-i', i);
    const bg=document.createElement('a-plane');
    bg.setAttribute('width','2.0'); bg.setAttribute('height','0.21');
    bg.setAttribute('color','#0a1933'); bg.setAttribute('class','clickable');
    const txt=document.createElement('a-text');
    txt.setAttribute('value', alt.length>58 ? alt.slice(0,55)+'...' : alt);
    txt.setAttribute('color','#cfe0ff'); txt.setAttribute('width','1.9'); txt.setAttribute('position','-0.95 0 0.01');
    bg.appendChild(txt); row.appendChild(bg);
    row.addEventListener('click', ()=>{{
      answers[i]=letra;
      document.querySelectorAll(`[data-i="${{i}}"] a-plane`).forEach(p=> p.setAttribute('color','#0a1933'));
      bg.setAttribute('color', letra===q.correta ? '#00c853' : '#d50000');
      if(navigator.vibrate) navigator.vibrate(letra===q.correta ? 40 : 90);
      root.setAttribute('animation','property: scale; from:1 1 1; to:1.12 1.12 1.12; dur:120; dir:alternate; loop:1');
      updateHUD();
    }});
    root.appendChild(row);
  }});
  blocks.push(root);
  return root;
}}

window.initWorld = function(){{
  const world=document.getElementById('world');
  world.innerHTML='';
  blocks=[];
  QUESTIONS.forEach((q,i)=> world.appendChild(createBlock(q,i)));
  updateHUD();
}}

window.organizeBlocks = function(){{
  blocks.forEach((b,i)=>{{
    const cols=4, spacing=2.8;
    const x=(i%cols)*spacing - ((cols-1)*spacing/2);
    const z=Math.floor(i/cols)*-3.2 -1;
    const y=1.2 + (i%3)*0.15;
    b.setAttribute('animation',`property: position; to: ${{x}} ${{y}} ${{z}}; dur: 800; easing:easeOutQuad`);
    b.setAttribute('animation__rot',`property: rotation; to: 0 ${{(Math.random()-0.5)*10}} 0; dur:800`);
  }});
}}

document.addEventListener('DOMContentLoaded', ()=>{{
  window.initWorld();
  const grid=document.getElementById('grid');
  if(grid){{
    for(let i=-50;i<=50;i+=2){{
      const l=document.createElement('a-box');
      l.setAttribute('width','100'); l.setAttribute('height','0.01'); l.setAttribute('depth','0.01');
      l.setAttribute('position',`0 0 ${{i}}`); l.setAttribute('color','#12204a'); l.setAttribute('opacity','0.3');
      grid.appendChild(l);
    }}
  }}
}});

document.getElementById('enter').addEventListener('click', ()=>{{
  document.querySelector('a-scene').enterVR();
}});
</script>
</body>
</html>
    """
    st.components.v1.html(html, height=height, scrolling=False)
    if st.button(f"❌ Fechar VR {modo}", key=f"close_{modo}"):
        st.session_state[f"show_full_{modo}"]=False
        st.rerun()

tab1, tab2, tab3 = st.tabs(["🥽 MOVER 1 A 1 + CALIB", "🏆 SIMULADO", "📖 TREINO"])

with tab1:
    todas=[]
    for v in banco.values(): todas.extend(v)
    random.shuffle(todas)
    st.markdown("""
    ### 🥽 NOVO: Mover blocos individualmente + Calibrador de mãos DENTRO do VR
    - **Aponte a mão para UM bloco** e aperte **Grip** - só aquele bloco gruda na mão
    - Solte para deixar onde quiser - organize a sala como quiser
    - Painel **CALIBRAGEM MAOS** dentro do VR: aumentar/diminuir mão, reset posição, organizar blocos, sair
    """)
    render_vr_individual(todas, modo="BLOCOS INDIVIDUAIS", height=950)

with tab2:
    if st.session_state.simulado:
        sim=st.session_state.simulado
        qs=sim["questoes"]
        if not sim["finalizado"]:
            rest=max(0,4*3600-int(time.time()-sim["inicio"]))
            h,m,s=rest//3600,(rest%3600)//60,rest%60
            st.warning(f"⏱️ {h:02d}:{m:02d}:{s:02d} | {len(qs)}q")
            render_vr_individual(qs, modo="SIMULADO INDIVIDUAL", height=950)
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
        render_vr_individual(st.session_state.treino, modo="TREINO INDIVIDUAL", height=950)
        for i,q in enumerate(st.session_state.treino):
            with st.expander(f"{i+1}. {q['pergunta'][:70]}..."):
                for a in q["alternativas"]: st.markdown(f"- {a}")
                st.success(f"Gabarito: {q['correta']}")
        if st.button("Encerrar treino"):
            st.session_state.treino=[]
            st.rerun()
    else:
        st.info("Gere um treino na barra lateral.")
