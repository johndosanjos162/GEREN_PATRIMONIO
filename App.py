
import streamlit as st
import json
import random
import pathlib
import time
from collections import defaultdict, Counter
from datetime import datetime

st.set_page_config(page_title="PMSC 2026 - Completo MR + Performance", page_icon="🎯", layout="wide")

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
    cands = [f for f in base.iterdir() if f.is_file() and f.suffix.lower()==".json"]
    if not cands:
        try:
            cwd = pathlib.Path.cwd()
            cands = [f for f in cwd.iterdir() if f.is_file() and f.suffix.lower()==".json"]
        except:
            pass
    for p in cands:
        try:
            with open(p,"r",encoding="utf-8") as jf:
                data=json.load(jf)
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
if "erros" not in st.session_state: st.session_state.erros=[]
if "acertos" not in st.session_state: st.session_state.acertos=[]
if "spaced" not in st.session_state: st.session_state.spaced={}

banco, caminho = load_banco()
if not banco:
    st.error("Nenhum .json encontrado na raiz.")
    st.stop()

st.title("PMSC 2026 - Completo: MR + Performance + Tudo Movivel")
st.caption(f"✅ {caminho} | {sum(len(v) for v in banco.values())}q | Quest 3 / 3S - Passthrough")

# Calcula desempenho por materia
def calc_performance():
    if not st.session_state.hist:
        return {}
    # Junta todos os detalhes do historico
    stats = defaultdict(lambda: {"acertos":0, "total":0})
    for h in st.session_state.hist:
        for d in h.get("detalhes",[]):
            mat = d.get("materia","Geral")
            stats[mat]["total"]+=1
            if d.get("acertou"):
                stats[mat]["acertos"]+=1
    perf = {}
    for mat, v in stats.items():
        if v["total"]>0:
            perf[mat] = round((v["acertos"]/v["total"])*100,1)
    return perf

with st.sidebar:
    st.success(f"📚 {sum(len(v) for v in banco.values())}q")
    
    # Radar de desempenho
    perf = calc_performance()
    if perf:
        st.subheader("📊 Radar por Materia")
        for mat in DISTRIBUICAO.keys():
            p = perf.get(mat, 0)
            color = "🟢" if p>=70 else "🟡" if p>=50 else "🔴"
            st.caption(f"{color} {mat[:20]}: {p}%")
        media = sum(perf.values())/len(perf) if perf else 0
        st.metric("Media Geral", f"{media:.1f}%")
        # Previsao AOCP
        # Peso proporcional
        nota_prev = 0
        for mat, qtd in DISTRIBUICAO.items():
            p = perf.get(mat, 50) # se sem dados, assume 50%
            nota_prev += (p/100)*qtd
        st.metric("🎯 Previsao Nota AOCP", f"{nota_prev:.1f}/60 ({nota_prev/60*100:.1f}%)", delta="APROVADO" if nota_prev>=30 else "REPROVADO")
    
    st.divider()
    st.subheader("Treino Inteligente")
    mat=st.selectbox("Materia", list(banco.keys()))
    qtd=st.slider("Qtd",5,20,10)
    col1, col2 = st.columns(2)
    if col1.button("Treino", use_container_width=True):
        pool=banco.get(mat,[])
        st.session_state.treino=[{**q,"materia":mat} for q in random.sample(pool,min(qtd,len(pool)))]
        st.session_state.simulado=None
        st.rerun()
    if col2.button("Erros", use_container_width=True):
        if st.session_state.erros:
            st.session_state.treino = st.session_state.erros[-20:]
            st.session_state.simulado=None
            st.rerun()
        else:
            st.warning("Sem erros ainda")
    
    if st.session_state.erros:
        st.caption(f"🔴 Banco de erros: {len(st.session_state.erros)}q")
        if st.button("Revisao Espacada (10q)", use_container_width=True):
            # Pega erros mais antigos
            rev = st.session_state.erros[-10:]
            random.shuffle(rev)
            st.session_state.treino = rev
            st.session_state.simulado=None
            st.rerun()
    
    st.divider()
    if st.button("Simulado 60q Oficial", type="primary", use_container_width=True):
        st.session_state.simulado={"questoes":montar_simulado(banco),"inicio":time.time(),"respostas":{}, "finalizado":False}
        st.session_state.treino=[]
        st.rerun()
    if st.session_state.simulado and not st.session_state.simulado["finalizado"]:
        if st.button("Cancelar Simulado"):
            st.session_state.simulado=None
            st.rerun()
    
    if st.session_state.hist:
        st.divider()
        st.subheader("Historico")
        for h in reversed(st.session_state.hist[-5:]):
            st.caption(f"{h['data']} - {h['acertos']}/{h['total']} ({h['nota']}%)")

def render_vr_completo(questoes, modo="ARENA", height=980):
    key = f"vr_{modo}"
    if not st.session_state.get(key, False):
        st.info(f"{len(questoes)} questoes prontas. MR: veja sala real. Fundos: praia, escritorio, biblioteca, espaco. Tudo movivel 1 a 1.")
        if st.button(f"CARREGAR VR COMPLETO - {modo} ({len(questoes[:20])} blocos)", key=f"btn_{key}", type="primary", use_container_width=True):
            st.session_state[key]=True
            st.rerun()
        return
    
    amostra = questoes[:20]
    safe=[]
    for q in amostra:
        safe.append({
            "pergunta": q["pergunta"][:190].replace('"',"'").replace("\n"," "),
            "alternativas": [a[:62].replace('"',"'") for a in q["alternativas"][:5]],
            "correta": q["correta"].upper(),
            "materia": q.get("materia","Geral")[:22]
        })
    q_json = json.dumps(safe, ensure_ascii=False).replace("</","<\\/")

    html_template = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v7.4.0/dist/aframe-extras.min.js"></script>
<script src="https://unpkg.com/super-hands@3.0.5/dist/super-hands.min.js"></script>
<script>
AFRAME.registerComponent('tudo-movel', {
  init: function() {
    const el = this.el;
    el.setAttribute('hoverable',''); el.setAttribute('grabbable',''); el.setAttribute('stretchable',''); el.setAttribute('draggable',''); el.setAttribute('droppable','');
    el.addEventListener('grab-start', () => { el.object3D.scale.set(1.05,1.05,1.05); });
    el.addEventListener('grab-end', () => { el.object3D.scale.set(1,1,1); });
  }
});
AFRAME.registerComponent('hand-calibrator-live', {
  schema: { hand: {type:'string', default:'left'} },
  init: function() {
    this.isTracking=false; this.pinch=0; this.grip=false;
    this.el.addEventListener('pinchstarted', ()=>{this.pinch=1;});
    this.el.addEventListener('pinchended', ()=>{this.pinch=0;});
    this.el.addEventListener('gripdown', ()=>{this.grip=true;});
    this.el.addEventListener('gripup', ()=>{this.grip=false;});
  },
  tick: function() {
    const id = this.data.hand==='left' ? 'leftHandData' : 'rightHandData';
    const tEl = document.getElementById(id);
    if(tEl){
      const p=this.el.object3D.position; const s=this.el.getAttribute('scale').x.toFixed(2);
      tEl.setAttribute('value', this.data.hand.toUpperCase()+': '+(this.isTracking?'TRACKING':'CONTROLE')+'\\nPos '+p.x.toFixed(2)+' '+p.y.toFixed(2)+' '+p.z.toFixed(2)+'\\nScale '+s+' | '+(this.pinch?'PINCH':'ABERTA')+' '+(this.grip?'GRIP':''));
    }
  }
});
AFRAME.registerComponent('environment-manager', {
  init: function() {
    this.currentEnv = 'dark';
  },
  setEnvironment: function(env){
    this.currentEnv = env;
    const sky = document.getElementById('sky360');
    const ground = document.getElementById('ground');
    const scene = document.querySelector('a-scene');
    if(env==='passthrough'){
      scene.setAttribute('background','color: transparent');
      scene.setAttribute('renderer','alpha:true; colorManagement:true');
      if(sky) sky.setAttribute('visible','false');
      if(ground) { ground.setAttribute('visible','false'); }
      document.getElementById('envText').setAttribute('value','MODO: PASSTHROUGH - Sala real');
    } else if(env==='dark'){
      scene.setAttribute('background','color: #050a14');
      scene.setAttribute('renderer','alpha:false');
      if(sky) sky.setAttribute('visible','false');
      if(ground) { ground.setAttribute('visible','true'); ground.setAttribute('color','#0a1430'); }
      document.getElementById('envText').setAttribute('value','MODO: ESCURO');
    } else {
      scene.setAttribute('background','color: #87CEEB');
      if(sky){ sky.setAttribute('visible','true'); if(env==='beach') sky.setAttribute('src','#beach360'); if(env==='office') sky.setAttribute('src','#office360'); if(env==='library') sky.setAttribute('src','#library360'); if(env==='space') sky.setAttribute('src','#space360'); }
      if(ground) { ground.setAttribute('visible','true'); }
      document.getElementById('envText').setAttribute('value','MODO: '+env.toUpperCase());
    }
  }
});
AFRAME.registerComponent('calibration-system', {
  init: function() {
    const rig=document.getElementById('rig'); const head=document.getElementById('head');
    const left=document.getElementById('leftHand'); const right=document.getElementById('rightHand');
    const envManager = document.getElementById('envManager').components['environment-manager'];
    let handScale=1; let headH=1.65;
    this.el.querySelectorAll('.calib-btn').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        const a=btn.getAttribute('data-action');
        if(a==='resetPos') rig.setAttribute('position','0 0 8');
        if(a==='resetRot') rig.setAttribute('rotation','0 0 0');
        if(a==='handUp'){ handScale+=0.1; left.setAttribute('scale',handScale+' '+handScale+' '+handScale); right.setAttribute('scale',handScale+' '+handScale+' '+handScale); }
        if(a==='handDown'){ handScale=Math.max(0.2,handScale-0.1); left.setAttribute('scale',handScale+' '+handScale+' '+handScale); right.setAttribute('scale',handScale+' '+handScale+' '+handScale); }
        if(a==='heightUp'){ headH+=0.1; head.setAttribute('position','0 '+headH+' 0'); }
        if(a==='heightDown'){ headH=Math.max(0.4,headH-0.1); head.setAttribute('position','0 '+headH+' 0'); }
        if(a==='resetArena') window.initWorld();
        if(a==='organize') window.organizeBlocks();
        if(a==='scatter') window.scatterBlocks();
        if(a==='organizeByMateria') window.organizeByMateria();
        if(a==='saveLayout') window.saveLayout();
        if(a==='loadLayout') window.loadLayout();
        if(a==='exitVR') document.querySelector('a-scene').exitVR();
        if(a==='envPassthrough') envManager.setEnvironment('passthrough');
        if(a==='envDark') envManager.setEnvironment('dark');
        if(a==='envBeach') envManager.setEnvironment('beach');
        if(a==='envOffice') envManager.setEnvironment('office');
        if(a==='envLibrary') envManager.setEnvironment('library');
        if(a==='envSpace') envManager.setEnvironment('space');
        btn.setAttribute('material','color','#00ff88'); setTimeout(()=>btn.setAttribute('material','color', btn.getAttribute('data-color')||'#1a3a6a'),200);
      });
    });
  }
});
</script>
<style>
html,body{margin:0;padding:0;width:100%;height:__HEIGHT__px;overflow:hidden;background:#050a14;}
#hud{position:fixed;top:8px;left:8px;z-index:99999;background:rgba(0,0,0,0.92);color:#00e5ff;border:1px solid #00e5ff;padding:10px 14px;border-radius:10px;font-size:12px;max-width:420px;}
#enter{position:fixed;bottom:12px;left:50%;transform:translateX(-50%);z-index:99999;background:linear-gradient(90deg,#00d1ff,#7000ff);color:white;border:none;padding:14px 32px;border-radius:999px;font-weight:900;font-size:15px;cursor:pointer;}
</style>
</head>
<body>
<div id="hud">
<div style="font-weight:900;color:white;font-size:14px;">__MODO__ - COMPLETO MR</div>
PASSTHROUGH = ve sala real + blocos | Fundos: praia, escritorio, biblioteca, espaco<br>
Tudo movivel 1 a 1 - Salve layout<br>
<div id="status" style="margin-top:6px;color:#00ff88;font-weight:700;">0/__LEN__ respondidas</div>
</div>
<button id="enter">ENTRAR VR - REALIDADE MISTA COMPLETA</button>

<a-scene
  background="color: #050a14"
  renderer="alpha:false; colorManagement:true; antialias:true"
  webxr="optionalFeatures: hand-tracking, local-floor, bounded-floor, hit-test, passthrough, plane-detection"
  vr-mode-ui="enabled:true"
  embedded
  style="width:100%;height:__HEIGHT__px;"
>
<a-assets>
  <img id="beach360" src="https://cdn.aframe.io/360-image-gallery-boilerplate/img/sechelt.jpg" crossorigin="anonymous">
  <img id="office360" src="https://cdn.aframe.io/360-image-gallery-boilerplate/img/city.jpg" crossorigin="anonymous">
  <img id="library360" src="https://cdn.aframe.io/360-image-gallery-boilerplate/img/flickr.jpg" crossorigin="anonymous">
  <img id="space360" src="https://cdn.aframe.io/a-painter/images/space.jpg" crossorigin="anonymous">
</a-assets>

<a-entity light="type:ambient; intensity:1.0"></a-entity>
<a-entity light="type:directional; intensity:1.0" position="4 7 4"></a-entity>

<a-sky id="sky360" radius="30" visible="false"></a-sky>
<a-plane id="ground" rotation="-90 0 0" width="120" height="120" color="#0a1430"></a-plane>
<a-entity id="envManager" environment-manager></a-entity>

<a-entity id="rig" position="0 0 8" movement-controls="fly:true; speed:0.35">
  <a-entity id="head" camera look-controls wasd-controls="acceleration:22" position="0 1.65 0">
    <a-entity cursor="rayOrigin: mouse" raycaster="objects: .clickable, .ui, .grabbable" visible="false"></a-entity>
    <a-entity position="0 -0.6 -1.1"><a-plane width="1.2" height="0.32" color="black" opacity="0.7"></a-plane><a-text id="hudVRText" value="0/20" color="#00ff88" width="1.9" align="center" position="0 0 0.01"></a-text><a-text id="envText" value="MODO: ESCURO" color="#00e5ff" width="1.8" align="center" position="0 -0.22 0.01"></a-text></a-entity>
  </a-entity>

  <a-entity id="leftHand"
    hand-controls="hand: left; handModelStyle: lowPoly; color:#00d1ff"
    hand-tracking-controls="hand: left"
    hand-calibrator-live="hand: left"
    super-hands="colliderEvent: raycaster-intersection; colliderEventProperty: els; colliderEndEvent: raycaster-intersection-cleared; colliderEndEventProperty: clearedEls; grabStartButtons: gripdown, pinchstart, triggerdown; grabEndButtons: gripup, pinchend, triggerup"
    laser-controls="hand: left"
    raycaster="objects: .clickable, .grabbable, .ui; far: 25"
    line="color:#00d1ff; opacity:0.9"
    sphere-collider="objects: .grabbable; radius:0.16"
    teleport-controls="cameraRig: #rig; teleportOrigin: #head; button: thumbstick"
  ></a-entity>

  <a-entity id="rightHand"
    hand-controls="hand: right; handModelStyle: lowPoly; color:#ff8a00"
    hand-tracking-controls="hand: right"
    hand-calibrator-live="hand: right"
    super-hands="colliderEvent: raycaster-intersection; colliderEventProperty: els; colliderEndEvent: raycaster-intersection-cleared; colliderEndEventProperty: clearedEls; grabStartButtons: gripdown, pinchstart, triggerdown; grabEndButtons: gripup, pinchend, triggerup"
    laser-controls="hand: right"
    raycaster="objects: .clickable, .grabbable, .ui; far: 25"
    line="color:#ff8a00; opacity:0.9"
    sphere-collider="objects: .grabbable; radius:0.16"
    teleport-controls="cameraRig: #rig; teleportOrigin: #head; button: thumbstick"
  ></a-entity>
</a-entity>

<a-entity id="mainPanel" position="0 1.8 -1.5" tudo-movel calibration-system hoverable grabbable draggable stretchable droppable>
  <a-box width="3.2" height="2.8" depth="0.08" color="#0a0a0a" opacity="0.95" class="grabbable"></a-box>
  <a-text value="COMPLETO MR + PERFORMANCE" color="#00e5ff" width="3.8" align="center" position="0 1.22 0.06"></a-text>
  <a-text value="REALIDADE MISTA" color="#00ff88" width="2.5" align="center" position="0 0.95 0.06"></a-text>
  <a-entity class="grabbable ui calib-btn clickable" data-action="envPassthrough" data-color="#00a000" position="-0.9 0.68 0.06" geometry="primitive: plane; width:0.85; height:0.28" material="color:#00a000"><a-text value="PASSTHROUGH" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="envDark" data-color="#1a3a6a" position="0 0.68 0.06" geometry="primitive: plane; width:0.65; height:0.28" material="color:#1a3a6a"><a-text value="ESCURO" color="white" width="1.4" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="envBeach" data-color="#1a3a6a" position="0.9 0.68 0.06" geometry="primitive: plane; width:0.65; height:0.28" material="color:#1a3a6a"><a-text value="PRAIA" color="white" width="1.4" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="envOffice" data-color="#1a3a6a" position="-0.9 0.35 0.06" geometry="primitive: plane; width:0.85; height:0.28" material="color:#1a3a6a"><a-text value="ESCRITORIO" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="envLibrary" data-color="#1a3a6a" position="0 0.35 0.06" geometry="primitive: plane; width:0.85; height:0.28" material="color:#1a3a6a"><a-text value="BIBLIOTECA" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="envSpace" data-color="#1a3a6a" position="0.9 0.35 0.06" geometry="primitive: plane; width:0.85; height:0.28" material="color:#1a3a6a"><a-text value="ESPACO" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-text value="ORGANIZACAO" color="#ffaa00" width="2.8" align="center" position="0 0.02 0.06"></a-text>
  <a-entity class="grabbable ui calib-btn clickable" data-action="organize" data-color="#1a3a6a" position="-0.9 -0.22 0.06" geometry="primitive: plane; width:0.75; height:0.24" material="color:#1a3a6a"><a-text value="GRADE" color="white" width="1.4" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="organizeByMateria" data-color="#1a3a6a" position="0 -0.22 0.06" geometry="primitive: plane; width:0.85; height:0.24" material="color:#1a3a6a"><a-text value="POR MATERIA" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="scatter" data-color="#1a3a6a" position="0.9 -0.22 0.06" geometry="primitive: plane; width:0.75; height:0.24" material="color:#1a3a6a"><a-text value="ESPALHAR" color="white" width="1.4" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="saveLayout" data-color="#2a5a1a" position="-0.9 -0.52 0.06" geometry="primitive: plane; width:0.75; height:0.24" material="color:#2a5a1a"><a-text value="SALVAR" color="white" width="1.4" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="loadLayout" data-color="#2a5a1a" position="0 -0.52 0.06" geometry="primitive: plane; width:0.75; height:0.24" material="color:#2a5a1a"><a-text value="CARREGAR" color="white" width="1.4" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="resetArena" data-color="#1a3a6a" position="0.9 -0.52 0.06" geometry="primitive: plane; width:0.75; height:0.24" material="color:#1a3a6a"><a-text value="RESET" color="white" width="1.4" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="handUp" data-color="#2a5a1a" position="-0.9 -0.82 0.06" geometry="primitive: plane; width:0.5; height:0.22" material="color:#2a5a1a"><a-text value="MAO +" color="white" width="1.2" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="handDown" data-color="#2a5a1a" position="-0.35 -0.82 0.06" geometry="primitive: plane; width:0.5; height:0.22" material="color:#2a5a1a"><a-text value="MAO -" color="white" width="1.2" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="heightUp" data-color="#1a3a6a" position="0.2 -0.82 0.06" geometry="primitive: plane; width:0.5; height:0.22" material="color:#1a3a6a"><a-text value="ALT +" color="white" width="1.2" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="heightDown" data-color="#1a3a6a" position="0.75 -0.82 0.06" geometry="primitive: plane; width:0.5; height:0.22" material="color:#1a3a6a"><a-text value="ALT -" color="white" width="1.2" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="grabbable ui calib-btn clickable" data-action="exitVR" data-color="#a00000" position="1.3 -0.82 0.06" geometry="primitive: plane; width:0.5; height:0.22" material="color:#a00000"><a-text value="SAIR" color="white" width="1.2" align="center" position="0 0 0.01"></a-text></a-entity>
</a-entity>

<a-entity id="handCalibDisplay" position="2.6 1.8 -1.5" tudo-movel hoverable grabbable draggable stretchable droppable>
  <a-box width="1.5" height="1.3" depth="0.06" color="#111111" opacity="0.9" class="grabbable"></a-box>
  <a-text value="CALIBRADOR MAOS" color="#00ff88" width="2.0" align="center" position="0 0.5 0.05"></a-text>
  <a-text id="leftHandData" value="LEFT: aguardando" color="#00d1ff" width="1.7" align="left" position="-0.6 0.18 0.05" wrap-count="30"></a-text>
  <a-text id="rightHandData" value="RIGHT: aguardando" color="#ff8a00" width="1.7" align="left" position="-0.6 -0.22 0.05" wrap-count="30"></a-text>
</a-entity>

<a-entity id="world"></a-entity>
</a-scene>

<script>
const QUESTIONS = __Q_JSON__;
let answers = {}; let blocks = [];
function updateHUD(){
  const n = Object.keys(answers).length;
  const txt = n+'/'+QUESTIONS.length;
  document.getElementById('status').textContent = txt + ' respondidas';
  const vrHud = document.getElementById('hudVRText');
  if(vrHud) vrHud.setAttribute('value', txt);
}
function createBlock(q, i){
  const cols=4, spacing=3.0;
  const x=(i%cols)*spacing - ((cols-1)*spacing/2);
  const z=Math.floor(i/cols)*-3.4 -1.5;
  const y=1.1 + Math.random()*0.8;
  const root=document.createElement('a-entity');
  root.setAttribute('id', 'block-'+i);
  root.setAttribute('position', x+' '+y+' '+z);
  root.setAttribute('class','grabbable');
  root.setAttribute('tudo-movel','');
  root.setAttribute('data-materia', q.materia);
  const box=document.createElement('a-box');
  box.setAttribute('width','2.4'); box.setAttribute('height','2.2'); box.setAttribute('depth','0.22');
  box.setAttribute('color','#13244a'); box.setAttribute('class','grabbable');
  const title=document.createElement('a-text');
  title.setAttribute('value', (i+1)+'. '+q.materia);
  title.setAttribute('color','#00e5ff'); title.setAttribute('width','2.3'); title.setAttribute('align','center');
  title.setAttribute('position','0 0.85 0.13');
  const qtext=document.createElement('a-text');
  const shortQ = q.pergunta.length>150 ? q.pergunta.slice(0,147)+'...' : q.pergunta;
  qtext.setAttribute('value', shortQ);
  qtext.setAttribute('color','white'); qtext.setAttribute('width','2.2'); qtext.setAttribute('align','center');
  qtext.setAttribute('position','0 0.42 0.13'); qtext.setAttribute('wrap-count','36');
  root.appendChild(box); root.appendChild(title); root.appendChild(qtext);
  q.alternativas.forEach((alt, idx)=>{
    const letra = alt.trim().charAt(0).toUpperCase();
    const row=document.createElement('a-entity');
    row.setAttribute('position', '0 ' + (-0.05 - idx*0.28) + ' 0.14');
    row.setAttribute('class','clickable grabbable'); row.setAttribute('data-i', i);
    row.setAttribute('tudo-movel','');
    const bg=document.createElement('a-plane');
    bg.setAttribute('width','2.0'); bg.setAttribute('height','0.22');
    bg.setAttribute('color','#0a1933'); bg.setAttribute('class','clickable grabbable');
    const txt=document.createElement('a-text');
    txt.setAttribute('value', alt.length>60 ? alt.slice(0,57)+'...' : alt);
    txt.setAttribute('color','#cfe0ff'); txt.setAttribute('width','1.9'); txt.setAttribute('position','-0.95 0 0.01');
    bg.appendChild(txt); row.appendChild(bg);
    row.addEventListener('click', (e)=>{
      e.stopPropagation();
      answers[i]=letra;
      document.querySelectorAll('[data-i="'+i+'"] a-plane').forEach(p=> p.setAttribute('color','#0a1933'));
      bg.setAttribute('color', letra===q.correta ? '#00c853' : '#d50000');
      if(navigator.vibrate) navigator.vibrate(letra===q.correta ? 40 : 90);
      root.setAttribute('animation','property: scale; from:1 1 1; to:1.1 1.1 1.1; dur:120; dir:alternate; loop:1');
      updateHUD();
    });
    root.appendChild(row);
  });
  blocks.push(root);
  return root;
}
window.initWorld = function(){
  const world=document.getElementById('world');
  world.innerHTML=''; blocks=[];
  QUESTIONS.forEach((q,i)=> world.appendChild(createBlock(q,i)));
  updateHUD();
}
window.organizeBlocks = function(){
  blocks.forEach((b,i)=>{
    const cols=4, spacing=3.0;
    const x=(i%cols)*spacing - ((cols-1)*spacing/2);
    const z=Math.floor(i/cols)*-3.4 -1.5;
    const y=1.1 + (i%3)*0.2;
    b.setAttribute('animation','property: position; to: '+x+' '+y+' '+z+'; dur: 700');
  });
}
window.organizeByMateria = function(){
  const materias = {};
  blocks.forEach((b,i)=>{
    const mat = b.getAttribute('data-materia') || QUESTIONS[i].materia;
    if(!materias[mat]) materias[mat]=[];
    materias[mat].push(b);
  });
  let clusterX = -6;
  Object.keys(materias).forEach(mat=>{
    const cluster = materias[mat];
    cluster.forEach((b, idx)=>{
      const cols=2, spacing=2.6;
      const x=clusterX + (idx%cols)*spacing;
      const z=Math.floor(idx/cols)*-2.8 -1;
      const y=1.2 + (idx%2)*0.3;
      b.setAttribute('animation','property: position; to: '+x+' '+y+' '+z+'; dur: 800');
    });
    clusterX += 6;
  });
}
window.scatterBlocks = function(){
  blocks.forEach((b,i)=>{
    const x=(Math.random()-0.5)*14; const z=(Math.random()-0.5)*14 -2; const y=0.8 + Math.random()*2.8;
    b.setAttribute('animation','property: position; to: '+x+' '+y+' '+z+'; dur: 700');
  });
}
window.saveLayout = function(){
  const layout = {};
  blocks.forEach(b=>{
    const id = b.getAttribute('id');
    layout[id] = b.getAttribute('position');
  });
  localStorage.setItem('vr_layout', JSON.stringify(layout));
  document.getElementById('envText').setAttribute('value','LAYOUT SALVO!');
}
window.loadLayout = function(){
  const saved = localStorage.getItem('vr_layout');
  if(saved){
    const layout = JSON.parse(saved);
    blocks.forEach(b=>{
      const id = b.getAttribute('id');
      if(layout[id]){
        b.setAttribute('animation','property: position; to: '+layout[id].x+' '+layout[id].y+' '+layout[id].z+'; dur: 800');
      }
    });
    document.getElementById('envText').setAttribute('value','LAYOUT CARREGADO!');
  }
}
document.addEventListener('DOMContentLoaded', ()=>{ window.initWorld(); });
document.getElementById('enter').addEventListener('click', ()=>{ document.querySelector('a-scene').enterVR(); });
</script>
</body>
</html>
    """
    html = html_template.replace("__Q_JSON__", q_json).replace("__MODO__", modo).replace("__LEN__", str(len(safe))).replace("__HEIGHT__", str(height))
    st.components.v1.html(html, height=height, scrolling=False)
    if st.button(f"Fechar VR {modo}", key=f"close_{modo}"):
        st.session_state[key]=False
        st.rerun()

tab1, tab2, tab3, tab4 = st.tabs(["COMPLETO MR + FUNDOS", "SIMULADO", "TREINO + ERROS", "PERFORMANCE"])

with tab1:
    todas=[]
    for v in banco.values(): todas.extend(v)
    random.shuffle(todas)
    st.markdown("### Completo: MR + Fundos + Tudo Movivel + Calibrador")
    render_vr_completo(todas, modo="COMPLETO", height=1000)

with tab2:
    if st.session_state.simulado:
        sim=st.session_state.simulado
        qs=sim["questoes"]
        if not sim["finalizado"]:
            rest=max(0,4*3600-int(time.time()-sim["inicio"]))
            h,m,s=rest//3600,(rest%3600)//60,rest%60
            st.warning(f"{h:02d}:{m:02d}:{s:02d} | {len(qs)}q")
            render_vr_completo(qs, modo="SIMULADO MR", height=1000)
            st.divider()
            with st.form("form_sim"):
                resp={}
                for i,q in enumerate(qs):
                    st.markdown(f"**{i+1}. [{q.get('materia','')}]** {q['pergunta']}")
                    esc=st.radio(f"q_{i}", q["alternativas"], index=None, key=f"sim_{i}", label_visibility="collapsed")
                    if esc: resp[i]=esc[0].upper()
                    st.divider()
                c1,c2=st.columns(2)
                if c1.form_submit_button("Salvar"): 
                    sim["respostas"]=resp
                    st.rerun()
                if c2.form_submit_button("Finalizar", type="primary"):
                    ac=0; dets=[]
                    for i,q in enumerate(qs):
                        r=resp.get(i,""); ok=r==q["correta"].upper()
                        if ok: ac+=1
                        else:
                            # Adiciona no banco de erros
                            st.session_state.erros.append(q)
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
                c3.metric("Status", "APROVADO" if ult["aprovado"] else "REPROVADO")
                with st.expander("Gabarito Detalhado"):
                    for i,d in enumerate(ult["detalhes"]):
                        st.markdown(f"{'✅' if d['acertou'] else '❌'} **{i+1}. [{d['materia']}]** {d['pergunta']}")
                        st.caption(f"Sua: {d['resposta'] or '—'} | Gab: {d['correta']}")
            if st.button("Novo Simulado", type="primary"):
                st.session_state.simulado=None
                st.rerun()
    else:
        st.info("Inicie o simulado na barra lateral - 60q na distribuicao oficial AOCP.")

with tab3:
    if st.session_state.treino:
        st.subheader(f"Treino {st.session_state.treino[0].get('materia','')} - {len(st.session_state.treino)}q")
        render_vr_completo(st.session_state.treino, modo="TREINO", height=1000)
        st.divider()
        st.subheader("Lista + Repeticao Espacada")
        for i,q in enumerate(st.session_state.treino):
            with st.expander(f"{i+1}. [{q.get('materia','')}] {q['pergunta'][:80]}..."):
                for a in q["alternativas"]: st.markdown(f"- {a}")
                st.success(f"Gabarito: {q['correta']}")
                c1,c2=st.columns(2)
                if c1.button(f"Acertei {i}", key=f"ok_{i}"):
                    st.session_state.acertos.append(q)
                    st.success("Movido para acertos")
                if c2.button(f"Errei {i}", key=f"err_{i}"):
                    st.session_state.erros.append(q)
                    st.error("Adicionado ao banco de erros")
        if st.button("Encerrar treino"):
            st.session_state.treino=[]
            st.rerun()
    else:
        st.info("Gere um treino na barra lateral. Use Treino por materia, Erros ou Revisao Espacada.")
        if st.session_state.erros:
            st.subheader(f"Banco de Erros ({len(st.session_state.erros)}q)")
            for i,q in enumerate(st.session_state.erros[-10:]):
                with st.expander(f"Erro {i+1}. {q['pergunta'][:60]}"):
                    st.write(q["pergunta"])
                    st.write(q["alternativas"])
                    st.error(f"Correta: {q['correta']}")

with tab4:
    st.subheader("📊 Performance e Previsao AOCP")
    perf = calc_performance()
    if not perf:
        st.info("Faca simulados para ver seu desempenho por materia")
    else:
        st.markdown("### Radar por Materia")
        for mat, qtd in DISTRIBUICAO.items():
            p = perf.get(mat, 0)
            st.progress(int(p), text=f"{mat}: {p}% ({qtd}q no edital)")
        
        st.divider()
        media = sum(perf.values())/len(perf) if perf else 0
        c1,c2,c3=st.columns(3)
        c1.metric("Media Geral", f"{media:.1f}%")
        nota_prev = sum((perf.get(mat,50)/100)*qtd for mat,qtd in DISTRIBUICAO.items())
        c2.metric("Previsao AOCP", f"{nota_prev:.1f}/60")
        c3.metric("Status", "APROVADO" if nota_prev>=30 else "REPROVADO", delta=f"{nota_prev-30:.1f}" if nota_prev>=30 else f"{nota_prev-30:.1f}")
        
        st.divider()
        st.markdown("### Materias Fracas (focar)")
        fracas = sorted([(mat, perf.get(mat,0)) for mat in DISTRIBUICAO.keys()], key=lambda x: x[1])
        for mat, p in fracas[:3]:
            st.error(f"🔴 {mat}: {p}% - Prioridade maxima")
        
        st.markdown("### Materias Fortes (manter)")
        for mat, p in sorted(perf.items(), key=lambda x: x[1], reverse=True)[:3]:
            st.success(f"🟢 {mat}: {p}%")
