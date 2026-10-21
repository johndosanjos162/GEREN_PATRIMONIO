
import streamlit as st
import json
import random
import pathlib
import time
from collections import defaultdict
from datetime import datetime

st.set_page_config(page_title="PMSC 2026 - Quest 3S TUDO Movível + Calibrador", page_icon="🎯", layout="wide")

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

banco, caminho = load_banco()
if not banco:
    st.error("json.json não encontrado na raiz.")
    st.stop()

st.title("🎯 PMSC 2026 – TUDO Movível no VR + Calibrador de Mãos")
st.caption(f"✅ {caminho} | {sum(len(v) for v in banco.values())}q | Quest 3S - Mova TUDO com as mãos")

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

def render_vr_tudo_movel(questoes, modo="ARENA", height=980):
    amostra = questoes[:20]
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
// ========== COMPONENTE: TUDO AGARRÁVEL ==========
AFRAME.registerComponent('tudo-movel', {{
  init: function() {{
    const el = this.el;
    el.setAttribute('class', (el.getAttribute('class')||'') + ' grabbable');
    el.setAttribute('hoverable','');
    el.setAttribute('grabbable','');
    el.setAttribute('stretchable','');
    el.setAttribute('draggable','');
    el.setAttribute('droppable','');
    
    el.addEventListener('grab-start', () => {{
      el.setAttribute('material','color','#ffaa00');
      if(el.getAttribute('data-type')!=='ui'){
        el.object3D.scale.set(1.05,1.05,1.05);
      }}
    }});
    el.addEventListener('grab-end', () => {{
      const orig = el.getAttribute('data-orig-color') || '#13244a';
      if(el.getAttribute('data-type')!=='ui') el.setAttribute('material','color',orig);
      el.object3D.scale.set(1,1,1);
    }});
    el.addEventListener('hover-start', () => {{
      if(el.getAttribute('data-type')!=='ui'){{
        const box = el.querySelector('a-box');
        if(box) box.setAttribute('color','#1e4a8a');
      }}
    }});
    el.addEventListener('hover-end', () => {{
      if(el.getAttribute('data-type')!=='ui'){{
        const box = el.querySelector('a-box');
        if(box) box.setAttribute('color','#13244a');
      }}
    }});
  }}
}});

// ========== COMPONENTE: CALIBRADOR DE MÃOS EM TEMPO REAL ==========
AFRAME.registerComponent('hand-calibrator-live', {{
  schema: {{
    hand: {{type:'string', default:'left'}}
  }},
  init: function() {{
    this.handEl = this.el;
    this.isTracking = false;
    this.pinchStrength = 0;
    this.grip = false;
    
    // Cria display de texto
    this.display = null;
    
    // Escuta eventos de hand tracking
    this.handEl.addEventListener('pinchstarted', () => {{ this.pinchStrength = 1; }});
    this.handEl.addEventListener('pinchended', () => {{ this.pinchStrength = 0; }});
    this.handEl.addEventListener('gripdown', () => {{ this.grip = true; }});
    this.handEl.addEventListener('gripup', () => {{ this.grip = false; }});
    
    // Hand tracking events
    this.handEl.addEventListener('hand-tracking-started', () => {{ this.isTracking = true; }});
    this.handEl.addEventListener('hand-tracking-lost', () => {{ this.isTracking = false; }});
  }},
  tick: function() {{
    // Atualiza display se existir
    const textId = this.data.hand === 'left' ? 'leftHandData' : 'rightHandData';
    const textEl = document.getElementById(textId);
    if(textEl){{
      const pos = this.el.object3D.position;
      const rot = this.el.object3D.rotation;
      const scale = this.el.getAttribute('scale').x.toFixed(2);
      const tracking = this.isTracking ? '✅ TRACKING' : '⚠️ CONTROLE';
      const pinch = this.pinchStrength > 0 ? '🤏 PINCH' : '✋ ABERTA';
      const gripTxt = this.grip ? '👊 GRIP' : '🖐️';
      
      textEl.setAttribute('value', 
        `${{this.data.hand.toUpperCase()}}: ${{tracking}}\\n`+
        `Pos: ${{pos.x.toFixed(2)}} ${{pos.y.toFixed(2)}} ${{pos.z.toFixed(2)}}\\n`+
        `Rot: ${{(rot.x*57).toFixed(0)}}° ${{(rot.y*57).toFixed(0)}}° ${{(rot.z*57).toFixed(0)}}°\\n`+
        `Scale: ${{scale}} | ${{pinch}} ${{gripTxt}}`
      );
    }}
  }}
}});

// ========== PAINEL DE CALIBRAÇÃO ==========
AFRAME.registerComponent('calibration-system', {{
  init: function() {{
    const panel = this.el;
    const rig = document.getElementById('rig');
    const head = document.getElementById('head');
    const left = document.getElementById('leftHand');
    const right = document.getElementById('rightHand');
    let handScale = 1.0;
    let headHeight = 1.65;

    panel.querySelectorAll('.calib-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        const action = btn.getAttribute('data-action');
        console.log('CALIB ACTION', action);
        
        if(action==='resetPos'){{ rig.setAttribute('position','0 0 8'); rig.setAttribute('rotation','0 0 0'); }}
        if(action==='resetRot'){{ rig.setAttribute('rotation','0 0 0'); head.setAttribute('rotation','0 0 0'); }}
        if(action==='handUp'){{ handScale+=0.1; left.setAttribute('scale',`${{handScale}} ${{handScale}} ${{handScale}}`); right.setAttribute('scale',`${{handScale}} ${{handScale}} ${{handScale}}`); }}
        if(action==='handDown'){{ handScale=Math.max(0.2, handScale-0.1); left.setAttribute('scale',`${{handScale}} ${{handScale}} ${{handScale}}`); right.setAttribute('scale',`${{handScale}} ${{handScale}} ${{handScale}}`); }}
        if(action==='heightUp'){{ headHeight+=0.1; head.setAttribute('position',`0 ${{headHeight}} 0`); }}
        if(action==='heightDown'){{ headHeight=Math.max(0.4, headHeight-0.1); head.setAttribute('position',`0 ${{headHeight}} 0`); }}
        if(action==='resetArena'){{ window.initWorld(); }}
        if(action==='organize'){{ window.organizeBlocks(); }}
        if(action==='scatter'){{ window.scatterBlocks(); }}
        if(action==='exitVR'){{ document.querySelector('a-scene').exitVR(); }}
        if(action==='toggleHands'){{ 
          const style = left.getAttribute('hand-controls').handModelStyle;
          const newStyle = style==='lowPoly' ? 'highPoly' : 'lowPoly';
          left.setAttribute('hand-controls',`hand: left; handModelStyle: ${{newStyle}}`);
          right.setAttribute('hand-controls',`hand: right; handModelStyle: ${{newStyle}}`);
        }}

        // Feedback visual
        btn.setAttribute('material','color','#00ff88');
        setTimeout(()=>btn.setAttribute('material','color', btn.getAttribute('data-color')||'#1a3a6a'),180);
        if(navigator.vibrate) navigator.vibrate(30);
      }});
    }});
  }}
}});
</script>
<style>
html,body{{margin:0;padding:0;width:100%;height:{height}px;overflow:hidden;background:#050a14;font-family:system-ui;}}
#hud{{position:fixed;top:8px;left:8px;z-index:99999;background:rgba(0,0,0,0.92);color:#00e5ff;border:1px solid #00e5ff;padding:10px 14px;border-radius:10px;font-size:12px;max-width:380px;line-height:1.35;}}
#enter{{position:fixed;bottom:12px;left:50%;transform:translateX(-50%);z-index:99999;background:linear-gradient(90deg,#00d1ff,#7000ff);color:white;border:none;padding:14px 32px;border-radius:999px;font-weight:900;font-size:15px;box-shadow:0 0 25px #00d1ff88;cursor:pointer;}}
</style>
</head>
<body>
<div id="hud">
<div style="font-weight:900;color:white;font-size:14px;margin-bottom:4px;">🥽 {modo} - TUDO MOVÍVEL</div>
👊 <b>PEGAR QUALQUER COISA:</b> Grip/Pinch no objeto<br>
📦 Blocos, painel, botões - tudo movível<br>
🖐️ Calibrador lê sua mão em tempo real<br>
<div id="status" style="margin-top:6px;color:#00ff88;font-weight:700;">0/{len(safe)} respondidas</div>
</div>
<button id="enter">🥽 ENTRAR VR - MOVER TUDO</button>

<a-scene
  background="color: #050a14"
  renderer="antialias:true; colorManagement:true; physicallyCorrectLights:true"
  webxr="optionalFeatures: hand-tracking, local-floor, bounded-floor, hit-test, body-tracking, plane-detection"
  vr-mode-ui="enabled:true"
  embedded
  style="width:100%;height:{height}px;"
>

<a-entity light="type:ambient; intensity:0.9"></a-entity>
<a-entity light="type:directional; intensity:1.1; castShadow:true" position="4 7 4"></a-entity>
<a-plane rotation="-90 0 0" width="120" height="120" color="#0a1430"></a-plane>
<a-entity id="grid"></a-entity>
<a-plane id="ground" rotation="-90 0 0" width="120" height="120" visible="false"></a-plane>

<!-- RIG -->
<a-entity id="rig" position="0 0 8" movement-controls="fly:true; speed:0.3">
  <a-entity id="head" camera look-controls wasd-controls="acceleration:20" position="0 1.65 0">
    <a-entity cursor="rayOrigin: mouse" raycaster="objects: .clickable, .ui, .grabbable" visible="false"></a-entity>
    <a-entity position="0 -0.6 -1.1">
      <a-plane width="1.1" height="0.32" color="black" opacity="0.7"></a-plane>
      <a-text id="hudVRText" value="0/20 respondidas" color="#00ff88" width="1.9" align="center" position="0 0 0.01"></a-text>
    </a-entity>
  </a-entity>

  <a-entity id="leftHand"
    hand-controls="hand: left; handModelStyle: lowPoly; color:#00d1ff"
    hand-tracking-controls="hand: left"
    hand-calibrator-live="hand: left"
    super-hands="colliderEvent: raycaster-intersection; colliderEventProperty: els; colliderEndEvent: raycaster-intersection-cleared; colliderEndEventProperty: clearedEls; grabStartButtons: gripdown, pinchstart, triggerdown; grabEndButtons: gripup, pinchend, triggerup"
    laser-controls="hand: left"
    raycaster="objects: .clickable, .grabbable, .ui; far: 25; showLine:true"
    line="color:#00d1ff; opacity:0.9"
    sphere-collider="objects: .grabbable; radius:0.15"
    teleport-controls="cameraRig: #rig; teleportOrigin: #head; button: thumbstick"
  ></a-entity>

  <a-entity id="rightHand"
    hand-controls="hand: right; handModelStyle: lowPoly; color:#ff8a00"
    hand-tracking-controls="hand: right"
    hand-calibrator-live="hand: right"
    super-hands="colliderEvent: raycaster-intersection; colliderEventProperty: els; colliderEndEvent: raycaster-intersection-cleared; colliderEndEventProperty: clearedEls; grabStartButtons: gripdown, pinchstart, triggerdown; grabEndButtons: gripup, pinchend, triggerup"
    laser-controls="hand: right"
    raycaster="objects: .clickable, .grabbable, .ui; far: 25; showLine:true"
    line="color:#ff8a00; opacity:0.9"
    sphere-collider="objects: .grabbable; radius:0.15"
    teleport-controls="cameraRig: #rig; teleportOrigin: #head; button: thumbstick"
  ></a-entity>
</a-entity>

<!-- PAINEL PRINCIPAL - TUDO MOVÍVEL (grabbable) -->
<a-entity id="mainPanel" position="0 1.7 -1.4" tudo-movel calibration-system data-type="ui" data-orig-color="#0a0a0a"
  hoverable grabbable draggable stretchable droppable>
  <a-box width="2.6" height="2.2" depth="0.08" color="#0a0a0a" opacity="0.95" class="grabbable"></a-box>
  <a-text value="TUDO MOVIVEL + CALIBRADOR MAOS" color="#00e5ff" width="3.2" align="center" position="0 0.92 0.06"></a-text>
  <a-text value="Pegue este painel e mova! Tudo e movivel" color="#888" width="2.4" align="center" position="0 0.72 0.06"></a-text>
  
  <!-- Linha 1 -->
  <a-entity class="grabbable ui calib-btn clickable" data-action="resetPos" data-color="#1a3a6a" position="-0.65 0.42 0.06" geometry="primitive: plane; width:0.75; height:0.26" material="color:#1a3a6a"><a-text value="RESET POS" color="white" width="1.5" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="organize" data-color="#1a3a6a" position="0 0.42 0.06" geometry="primitive: plane; width:0.75; height:0.26" material="color:#1a3a6a"><a-text value="ORGANIZAR" color="white" width="1.5" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="scatter" data-color="#1a3a6a" position="0.65 0.42 0.06" geometry="primitive: plane; width:0.75; height:0.26" material="color:#1a3a6a"><a-text value="ESPALHAR" color="white" width="1.5" align="center" position="0 0 0.01"></a-text></a-entity>

  <!-- Linha 2 - Calibrador mãos -->
  <a-entity class="grabbable ui calib-btn clickable" data-action="handUp" data-color="#2a5a1a" position="-0.65 0.10 0.06" geometry="primitive: plane; width:0.75; height:0.26" material="color:#2a5a1a"><a-text value="MAO +" color="white" width="1.5" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="handDown" data-color="#2a5a1a" position="0 0.10 0.06" geometry="primitive: plane; width:0.75; height:0.26" material="color:#2a5a1a"><a-text value="MAO -" color="white" width="1.5" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="toggleHands" data-color="#2a5a1a" position="0.65 0.10 0.06" geometry="primitive: plane; width:0.75; height:0.26" material="color:#2a5a1a"><a-text value="TROCAR MAO" color="white" width="1.5" align="center" position="0 0 0.01"></a-text></a-entity>

  <!-- Linha 3 - Altura -->
  <a-entity class="grabbable ui calib-btn clickable" data-action="heightUp" data-color="#1a3a6a" position="-0.65 -0.22 0.06" geometry="primitive: plane; width:0.75; height:0.26" material="color:#1a3a6a"><a-text value="ALTURA +" color="white" width="1.5" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="heightDown" data-color="#1a3a6a" position="0 -0.22 0.06" geometry="primitive: plane; width:0.75; height:0.26" material="color:#1a3a6a"><a-text value="ALTURA -" color="white" width="1.5" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="resetArena" data-color="#1a3a6a" position="0.65 -0.22 0.06" geometry="primitive: plane; width:0.75; height:0.26" material="color:#1a3a6a"><a-text value="RESET ARENA" color="white" width="1.5" align="center" position="0 0 0.01"></a-text></a-entity>

  <!-- Sair -->
  <a-entity class="grabbable ui calib-btn clickable" data-action="exitVR" data-color="#a00000" position="0 -0.62 0.06" geometry="primitive: plane; width:2.2; height:0.32" material="color:#a00000"><a-text value="🚪 SAIR DO VR" color="white" width="2.4" align="center" position="0 0 0.01"></a-text></a-entity>
</a-entity>

<!-- PAINEL CALIBRADOR DE MÃOS AO VIVO - TAMBÉM MOVÍVEL -->
<a-entity id="handCalibDisplay" position="2.0 1.7 -1.4" tudo-movel data-type="ui" data-orig-color="#111111"
  hoverable grabbable draggable stretchable droppable>
  <a-box width="1.6" height="1.4" depth="0.06" color="#111111" opacity="0.9" class="grabbable"></a-box>
  <a-text value="CALIBRADOR MAOS - TEMPO REAL" color="#00ff88" width="2.2" align="center" position="0 0.55 0.05"></a-text>
  <a-text id="leftHandData" value="LEFT: aguardando..." color="#00d1ff" width="1.9" align="left" position="-0.65 0.2 0.05" wrap-count="32"></a-text>
  <a-text id="rightHandData" value="RIGHT: aguardando..." color="#ff8a00" width="1.9" align="left" position="-0.65 -0.25 0.05" wrap-count="32"></a-text>
</a-entity>

<!-- MUNDO -->
<a-entity id="world"></a-entity>

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
  const cols=4, spacing=3.0;
  const x=(i%cols)*spacing - ((cols-1)*spacing/2);
  const z=Math.floor(i/cols)*-3.4 -1.5;
  const y=1.1 + Math.random()*0.9;
  
  const root=document.createElement('a-entity');
  root.setAttribute('id', `block-${{i}}`);
  root.setAttribute('position', `${{x}} ${{y}} ${{z}}`);
  root.setAttribute('rotation', `0 ${{(Math.random()-0.5)*40}} 0`);
  root.setAttribute('class','grabbable');
  root.setAttribute('tudo-movel','');
  root.setAttribute('data-type','question');
  root.setAttribute('data-orig-color','#13244a');
  
  const box=document.createElement('a-box');
  box.setAttribute('width','2.4'); box.setAttribute('height','2.2'); box.setAttribute('depth','0.22');
  box.setAttribute('color','#13244a'); box.setAttribute('class','grabbable');
  box.setAttribute('roughness','0.5');

  const title=document.createElement('a-text');
  title.setAttribute('value', `${{i+1}}. ${{q.materia}}`);
  title.setAttribute('color','#00e5ff'); title.setAttribute('width','2.3'); title.setAttribute('align','center');
  title.setAttribute('position','0 0.85 0.13');

  const qtext=document.createElement('a-text');
  const shortQ = q.pergunta.length>155 ? q.pergunta.slice(0,152)+'...' : q.pergunta;
  qtext.setAttribute('value', shortQ);
  qtext.setAttribute('color','white'); qtext.setAttribute('width','2.2'); qtext.setAttribute('align','center');
  qtext.setAttribute('position','0 0.45 0.13'); qtext.setAttribute('wrap-count','38');

  root.appendChild(box); root.appendChild(title); root.appendChild(qtext);

  q.alternativas.forEach((alt, idx)=>{{
    const letra = alt.trim().charAt(0).toUpperCase();
    const row=document.createElement('a-entity');
    row.setAttribute('position', `0 ${{ -0.05 - idx*0.28 }} 0.14`);
    row.setAttribute('class','clickable grabbable'); row.setAttribute('data-i', i);
    // Torna a alternativa também movível mas clicável
    row.setAttribute('tudo-movel','');
    row.setAttribute('data-type','answer');
    const bg=document.createElement('a-plane');
    bg.setAttribute('width','2.1'); bg.setAttribute('height','0.22');
    bg.setAttribute('color','#0a1933'); bg.setAttribute('class','clickable grabbable');
    const txt=document.createElement('a-text');
    txt.setAttribute('value', alt.length>62 ? alt.slice(0,59)+'...' : alt);
    txt.setAttribute('color','#cfe0ff'); txt.setAttribute('width','2.0'); txt.setAttribute('position','-1.0 0 0.01');
    bg.appendChild(txt); row.appendChild(bg);
    row.addEventListener('click', (e)=>{{
      e.stopPropagation();
      answers[i]=letra;
      document.querySelectorAll(`[data-i="${{i}}"] a-plane`).forEach(p=> p.setAttribute('color','#0a1933'));
      bg.setAttribute('color', letra===q.correta ? '#00c853' : '#d50000');
      if(navigator.vibrate) navigator.vibrate(letra===q.correta ? 40 : 90);
      root.setAttribute('animation','property: scale; from:1 1 1; to:1.1 1.1 1.1; dur:120; dir:alternate; loop:1');
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
    const cols=4, spacing=3.0;
    const x=(i%cols)*spacing - ((cols-1)*spacing/2);
    const z=Math.floor(i/cols)*-3.4 -1.5;
    const y=1.1 + (i%3)*0.2;
    b.setAttribute('animation',`property: position; to: ${{x}} ${{y}} ${{z}}; dur: 700; easing:easeOutQuad`);
  }});
}}

window.scatterBlocks = function(){{
  blocks.forEach((b,i)=>{{
    const x=(Math.random()-0.5)*12;
    const z=(Math.random()-0.5)*12 -2;
    const y=0.8 + Math.random()*2.5;
    b.setAttribute('animation',`property: position; to: ${{x}} ${{y}} ${{z}}; dur: 700; easing:easeOutQuad`);
    b.setAttribute('animation__rot',`property: rotation; to: 0 ${{(Math.random()-0.5)*180}} 0; dur:700`);
  }});
}}

document.addEventListener('DOMContentLoaded', ()=>{{
  window.initWorld();
  const grid=document.getElementById('grid');
  if(grid){{
    for(let i=-60;i<=60;i+=2){{
      const l=document.createElement('a-box');
      l.setAttribute('width','120'); l.setAttribute('height','0.01'); l.setAttribute('depth','0.01');
      l.setAttribute('position',`0 0 ${{i}}`); l.setAttribute('color','#12204a'); l.setAttribute('opacity','0.25');
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

tab1, tab2, tab3 = st.tabs(["🥽 TUDO MOVÍVEL + CALIBRADOR", "🏆 SIMULADO", "📖 TREINO"])

with tab1:
    todas=[]
    for v in banco.values(): todas.extend(v)
    random.shuffle(todas)
    st.markdown("""
    ### ✅ NOVO: Mova TUDO dentro do VR + Calibrador de mãos em tempo real
    - **Blocos de questões**: pegue 1 a 1, mova, organize
    - **Painel principal**: pegue o painel inteiro e mova no espaço
    - **Calibrador de mãos**: painel ao lado mostra posição, rotação, scale, pinch, grip em tempo real
    - **Tudo grabbable**: até os botões A-E são movíveis
    - Use **ORGANIZAR** / **ESPALHAR** para testar
    """)
    render_vr_tudo_movel(todas, modo="TUDO MOVIVEL + CALIB", height=1000)

with tab2:
    if st.session_state.simulado:
        sim=st.session_state.simulado
        qs=sim["questoes"]
        if not sim["finalizado"]:
            rest=max(0,4*3600-int(time.time()-sim["inicio"]))
            h,m,s=rest//3600,(rest%3600)//60,rest%60
            st.warning(f"⏱️ {h:02d}:{m:02d}:{s:02d} | {len(qs)}q")
            render_vr_tudo_movel(qs, modo="SIMULADO TUDO MOVIVEL", height=1000)
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
        render_vr_tudo_movel(st.session_state.treino, modo="TREINO TUDO MOVIVEL", height=1000)
        for i,q in enumerate(st.session_state.treino):
            with st.expander(f"{i+1}. {q['pergunta'][:70]}..."):
                for a in q["alternativas"]: st.markdown(f"- {a}")
                st.success(f"Gabarito: {q['correta']}")
        if st.button("Encerrar treino"):
            st.session_state.treino=[]
            st.rerun()
    else:
        st.info("Gere um treino na barra lateral.")
