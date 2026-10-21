
import streamlit as st
import json
import random
import pathlib
import time
from collections import defaultdict
from datetime import datetime

st.set_page_config(page_title="PMSC ARENA VR - Quest 3/3S", page_icon="🎯", layout="wide")

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

# ===================== CARREGADOR ROBUSTO COM RAW_DECODE =====================
@st.cache_data(ttl=30)
def load_banco():
    base = pathlib.Path(__file__).parent
    # Procura json.json e variações
    candidates = []
    for name in ["json.json", "banco.json", "questoes.json", "questions.json"]:
        p = base / name
        if p.exists():
            candidates.append(p)
    # Também qualquer .json
    for f in base.iterdir():
        if f.is_file() and f.suffix.lower()==".json" and f not in candidates:
            candidates.append(f)
    if not candidates:
        try:
            cwd = pathlib.Path.cwd()
            for f in cwd.iterdir():
                if f.is_file() and f.suffix.lower()==".json":
                    candidates.append(f)
        except:
            pass

    all_questions = defaultdict(list)
    seen = set()  # deduplicacao case-insensitive

    for path in candidates:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            # Suporta múltiplos objetos JSON concatenados
            decoder = json.JSONDecoder()
            idx = 0
            objects = []
            while idx < len(content):
                # Pula espaços e caracteres não JSON
                while idx < len(content) and content[idx] in " \n\r\t":
                    idx+=1
                if idx >= len(content):
                    break
                try:
                    obj, end = decoder.raw_decode(content, idx)
                    objects.append(obj)
                    idx = end
                except json.JSONDecodeError:
                    # Avança 1 char e tenta de novo
                    idx+=1
                    continue

            for obj in objects:
                if isinstance(obj, dict):
                    # Se dict é materia -> lista
                    for k, v in obj.items():
                        if isinstance(v, list):
                            for q in v:
                                if isinstance(q, dict) and "pergunta" in q:
                                    key = q["pergunta"].strip().lower()
                                    if key not in seen:
                                        seen.add(key)
                                        # Normaliza campos
                                        q_norm = {
                                            "pergunta": q.get("pergunta","").strip(),
                                            "alternativas": q.get("alternativas", q.get("opcoes", [])),
                                            "correta": q.get("correta", q.get("gabarito","A")).strip().upper()[:1],
                                            "materia": k
                                        }
                                        all_questions[k].append(q_norm)
                elif isinstance(obj, list):
                    for q in obj:
                        if isinstance(q, dict) and "pergunta" in q:
                            key = q["pergunta"].strip().lower()
                            if key not in seen:
                                seen.add(key)
                                mat = q.get("materia","Geral")
                                q_norm = {
                                    "pergunta": q.get("pergunta","").strip(),
                                    "alternativas": q.get("alternativas", q.get("opcoes", [])),
                                    "correta": q.get("correta", q.get("gabarito","A")).strip().upper()[:1],
                                    "materia": mat
                                }
                                all_questions[mat].append(q_norm)
        except Exception as e:
            continue

    if not all_questions:
        return None, None

    # Converte para dict normal
    banco = dict(all_questions)
    total = sum(len(v) for v in banco.values())
    return banco, f"json.json ({total} únicas)"

def montar_simulado(banco):
    sim=[]
    for mat,qtd in DISTRIBUICAO.items():
        pool=banco.get(mat,[])
        if not pool:
            # Busca fuzzy
            for k,v in banco.items():
                if mat.lower() in k.lower() or k.lower() in mat.lower():
                    pool=v
                    break
        if pool:
            sim.extend([{**q,"materia":mat} for q in random.sample(pool,min(qtd,len(pool)))])
    random.shuffle(sim)
    return sim

if "simulado" not in st.session_state:
    st.session_state.simulado=None
if "treino" not in st.session_state:
    st.session_state.treino=[]
if "hist" not in st.session_state:
    st.session_state.hist=[]

banco, caminho = load_banco()
if not banco:
    st.error("❌ json.json não encontrado na raiz. Coloque seu banco na raiz do repositório.")
    st.stop()

# ===================== SIDEBAR - MODULO 1 =====================
with st.sidebar:
    total_q = sum(len(v) for v in banco.values())
    st.success(f"📚 {total_q} questões únicas")
    st.caption(f"✅ {caminho}")
    if st.button("🔄 Recarregar json.json", use_container_width=True):
        load_banco.clear()
        st.rerun()
    st.divider()
    st.subheader("Treino")
    materias = list(banco.keys())
    mat = st.selectbox("Matéria", materias)
    qtd = st.slider("Quantidade", 5, 20, 10)
    if st.button("▶️ Iniciar Treino", use_container_width=True):
        pool = banco.get(mat,[])
        if pool:
            st.session_state.treino=[{**q,"materia":mat} for q in random.sample(pool,min(qtd,len(pool)))]
            st.session_state.simulado=None
            st.rerun()
    st.divider()
    st.subheader("Simulado Oficial")
    if st.button("🚀 Iniciar Simulado 60q", type="primary", use_container_width=True):
        sim = montar_simulado(banco)
        if len(sim)<60:
            st.warning(f"Banco tem só {len(sim)}q. Gerando com o que tem.")
        st.session_state.simulado={"questoes":sim,"inicio":time.time(),"respostas":{}, "finalizado":False}
        st.session_state.treino=[]
        st.rerun()
    if st.session_state.simulado and not st.session_state.simulado["finalizado"]:
        if st.button("❌ Cancelar simulado", use_container_width=True):
            st.session_state.simulado=None
            st.rerun()
    st.divider()
    if st.session_state.hist:
        st.subheader("📈 Histórico (últimas 5)")
        for h in reversed(st.session_state.hist[-5:]):
            status = "✅" if h["aprovado"] else "❌"
            st.caption(f"{status} {h['data']} - {h['acertos']}/{h['total']} - {h['nota']}%")

st.title("🎯 PMSC ARENA VR - Quest 3 / 3S")
st.caption(f"Edital AOCP | {caminho} | Realidade Mista Passthrough | Tudo movível")

# ===================== FUNÇÃO RENDER VR - SEM F-STRING =====================
def render_vr(questoes, modo="ARENA", height=980):
    key = f"vr_{modo}"
    if not st.session_state.get(key, False):
        st.info(f"🎯 {len(questoes)} questões prontas. Clique para carregar a arena VR. No headset: Grip move bloco à distância, Trigger responde.")
        if st.button(f"🥽 CARREGAR VR - {modo} ({len(questoes[:18])} blocos)", key=f"btn_{key}", type="primary", use_container_width=True):
            st.session_state[key]=True
            st.rerun()
        return

    amostra = questoes[:18]
    safe=[]
    for q in amostra:
        # Garante alternativas no formato A) ...
        alts = q.get("alternativas",[])
        # Normaliza para ter letra
        norm_alts=[]
        for idx, a in enumerate(alts[:5]):
            a_str = str(a).strip()
            # Se não começa com letra, adiciona
            if not (len(a_str)>=2 and a_str[1]==")" or a_str[0] in "ABCDE" and a_str[1]==")"):
                letra = chr(65+idx)
                if not a_str.startswith(letra):
                    a_str = f"{letra}) {a_str}"
            norm_alts.append(a_str[:80].replace('"',"'").replace("\n"," "))
        safe.append({
            "pergunta": q["pergunta"][:200].replace('"',"'").replace("\n"," "),
            "alternativas": norm_alts,
            "correta": q["correta"].upper()[:1],
            "materia": q.get("materia","Geral")[:22]
        })
    q_json = json.dumps(safe, ensure_ascii=False).replace("</","<\\/")

    html_template = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/donmccurdy/aframe-extras@v7.4.0/dist/aframe-extras.min.js"></script>
<style>
html,body{margin:0;padding:0;width:100%;height:__HEIGHT__px;overflow:hidden;background:#050a14;font-family:system-ui;}
#hud{position:fixed;top:8px;left:8px;z-index:99999;background:rgba(0,0,0,0.92);color:#00e5ff;border:1px solid #00e5ff;padding:10px 14px;border-radius:10px;font-size:12px;max-width:440px;line-height:1.35;}
#toast{position:fixed;bottom:90px;left:50%;transform:translateX(-50%);z-index:99999;background:rgba(0,0,0,0.9);color:#00ff88;border:1px solid #00ff88;padding:10px 18px;border-radius:999px;font-size:13px;font-weight:700;opacity:0;transition:opacity 0.2s;}
#enter{position:fixed;bottom:14px;left:50%;transform:translateX(-50%);z-index:99999;background:linear-gradient(90deg,#00d1ff,#7000ff);color:white;border:none;padding:14px 32px;border-radius:999px;font-weight:900;font-size:15px;cursor:pointer;box-shadow:0 0 20px #00d1ff88;}
</style>
<script>
// ===================== COMPONENTE vr-hand CUSTOM - SEM SUPER-HANDS =====================
// Mantém DOIS alvos: currentGrab (bloco) e currentClick (alternativa exata)
AFRAME.registerComponent('vr-hand', {
  schema: {
    hand: {type: 'string', default: 'left'},
    color: {type: 'color', default: '#00d1ff'}
  },
  init: function(){
    this.raycaster = new THREE.Raycaster();
    this.raycaster.far = 100; // alcance longo 100m
    this.currentGrab = null; // bloco inteiro
    this.currentClick = null; // alternativa exata
    this.grabbed = null;
    this.grabOffset = new THREE.Vector3();
    this.grabOffsetLocal = new THREE.Vector3();
    this.initialHandPos = new THREE.Vector3();
    this.pushPull = 0; // thumbstick push/pull
    this.handEl = this.el;
    this.controller = this.el;

    // Estado visual
    this.lineEl = null;

    // Listeners Grip (controle)
    this.el.addEventListener('gripdown', this.onGripDown.bind(this));
    this.el.addEventListener('gripup', this.onGripUp.bind(this));
    this.el.addEventListener('triggerdown', this.onTriggerDown.bind(this));
    // Hand tracking pinch
    this.el.addEventListener('pinchstarted', this.onGripDown.bind(this));
    this.el.addEventListener('pinchended', this.onGripUp.bind(this));
    // Thumbstick
    this.el.addEventListener('thumbstickmoved', this.onThumbstick.bind(this));

    // Para debug HUD
    this.lastHUD = '';
  },
  onThumbstick: function(evt){
    if(!this.grabbed) return;
    const x = evt.detail.x;
    const y = evt.detail.y;
    // y = push/pull, x = rotate
    if(Math.abs(y) > 0.2){
      this.pushPull += y * 0.05; // sensibilidade
      // Limita 8m
      this.pushPull = Math.max(-8, Math.min(8, this.pushPull));
    }
    if(Math.abs(x) > 0.5){
      // Rotação Y
      const rot = this.grabbed.getAttribute('rotation');
      const newY = rot.y + x * 2;
      this.grabbed.setAttribute('rotation', rot.x + ' ' + newY + ' ' + rot.z);
    }
  },
  onGripDown: function(){
    if(!this.currentGrab) return;
    // Guarda bloco
    this.grabbed = this.currentGrab;
    const handPos = new THREE.Vector3();
    this.el.object3D.getWorldPosition(handPos);
    const blockPos = new THREE.Vector3();
    this.grabbed.object3D.getWorldPosition(blockPos);
    // OFFSET EXATO - bloco fica parado onde está
    this.grabOffset.copy(blockPos).sub(handPos);
    this.initialHandPos.copy(handPos);
    this.pushPull = 0;
    // Visual
    this.grabbed.setAttribute('material','emissive','#ffaa00; emissiveIntensity:0.6');
    const box = this.grabbed.querySelector('a-box');
    if(box) box.setAttribute('color','#ffaa00');
    // Toast
    const dist = handPos.distanceTo(blockPos).toFixed(1);
    this.showToast('✋ ' + this.grabbed.id + ' @ ' + dist + 'm');
    if(navigator.vibrate) navigator.vibrate(20);
  },
  onGripUp: function(){
    if(!this.grabbed) return;
    // Salva no localStorage
    const id = this.grabbed.id;
    const pos = this.grabbed.getAttribute('position');
    const rot = this.grabbed.getAttribute('rotation');
    try{
      localStorage.setItem('pmsc_pos_'+id, JSON.stringify({pos: pos, rot: rot}));
    }catch(e){}
    // Restaura cor
    this.grabbed.setAttribute('material','emissive','#000000; emissiveIntensity:0');
    const box = this.grabbed.querySelector('a-box');
    if(box) box.setAttribute('color','#13244a');
    this.grabbed = null;
    this.pushPull = 0;
  },
  onTriggerDown: function(){
    if(!this.currentClick) return;
    // Dispara click na alternativa exata
    this.currentClick.emit('click');
    const letra = this.currentClick.getAttribute('data-letra');
    this.showHUD('🎯 CLICK ['+letra+']');
    if(navigator.vibrate) navigator.vibrate(10);
  },
  showToast: function(msg){
    const t = document.getElementById('toast');
    if(t){ t.textContent = msg; t.style.opacity='1'; setTimeout(()=>{t.style.opacity='0';},1200); }
  },
  showHUD: function(msg){
    if(this.lastHUD === msg) return;
    this.lastHUD = msg;
    const status = document.getElementById('status');
    const vrHud = document.getElementById('hudVRText');
    // Não sobrescreve contador, só HUD secundário
    const target = document.getElementById('grabHUD');
    if(target) target.setAttribute('value', msg);
  },
  tick: function(){
    // 1. Atualiza raycaster a partir da mão
    const origin = new THREE.Vector3();
    const direction = new THREE.Vector3();
    this.el.object3D.getWorldPosition(origin);
    // Direção: -Z local da mão
    this.el.object3D.getWorldDirection(direction);
    // Inverte para frente (A-Frame getWorldDirection pega -Z já)
    // Para mãos, precisamos usar matriz
    const mat = new THREE.Matrix4();
    mat.extractRotation(this.el.object3D.matrixWorld);
    direction.set(0,0,-1).applyMatrix4(mat).normalize();

    this.raycaster.set(origin, direction);

    // 2. Coleta objetos
    const grabbables = [];
    const clickables = [];
    document.querySelectorAll('.grabbable').forEach(el=>{
      if(el.object3D) grabbables.push(el.object3D);
    });
    document.querySelectorAll('.clickable').forEach(el=>{
      if(el.object3D) clickables.push(el.object3D);
    });

    // Interseção grabbable (blocos)
    const intersectsGrab = this.raycaster.intersectObjects(grabbables, true);
    // Interseção clickable (alternativas)
    const intersectsClick = this.raycaster.intersectObjects(clickables, true);

    // Reseta
    this.currentGrab = null;
    this.currentClick = null;

    // Encontra bloco (sobe hierarquia até id block-N)
    if(intersectsGrab.length>0){
      let obj = intersectsGrab[0].object;
      let el = obj.el;
      // Sobe até achar id block-
      while(el && !el.id.startsWith('block-')){
        el = el.parentEl;
      }
      if(el && el.id.startsWith('block-')){
        this.currentGrab = el;
        const dist = intersectsGrab[0].distance.toFixed(1);
        this.showHUD('🎯 ' + el.id + ' ' + dist + 'm');
        // Atualiza HUD fixo
        const grabHUD = document.getElementById('grabHUD');
        if(grabHUD) grabHUD.setAttribute('value','🎯 ' + el.id + ' ' + dist + 'm');
      }
    }

    // Encontra alternativa exata (NÃO pega primeiro do bloco)
    if(intersectsClick.length>0){
      let obj = intersectsClick[0].object;
      let el = obj.el;
      // Sobe até achar data-letra
      while(el && !el.hasAttribute('data-letra')){
        el = el.parentEl;
      }
      if(el && el.hasAttribute('data-letra')){
        this.currentClick = el;
        const letra = el.getAttribute('data-letra');
        const grabHUD = document.getElementById('grabHUD');
        if(grabHUD) grabHUD.setAttribute('value','🎯 CLICK ['+letra+']');
      }
    }

    // 3. Se está agarrando, move bloco mantendo offset + pushPull
    if(this.grabbed){
      const handPos = new THREE.Vector3();
      this.el.object3D.getWorldPosition(handPos);
      // Direção para push/pull
      const dir = new THREE.Vector3();
      this.el.object3D.getWorldDirection(dir);
      // Calcula nova posição: mão + offset + pushPull na direção
      const newPos = new THREE.Vector3();
      newPos.copy(handPos).add(this.grabOffset);
      // Aplica pushPull ao longo da direção da mão
      const pushVec = dir.clone().multiplyScalar(-this.pushPull);
      newPos.add(pushVec);
      // Converte para posição local do parent (world)
      // Como blocos estão em world, seta world position via position
      // Simplifica: seta position direta (assumindo parent = world)
      const world = document.getElementById('world');
      // Transforma world pos para local de world (world é 0,0,0)
      this.grabbed.setAttribute('position', newPos.x + ' ' + newPos.y + ' ' + newPos.z);
    }

    // 4. Atualiza linha laser manual (50m)
    const line = this.el.getAttribute('line');
    if(line){
      const end = direction.clone().multiplyScalar(50);
      this.el.setAttribute('line','start: 0 0 0; end: '+end.x+' '+end.y+' '+end.z+'; color: '+this.data.color+'; opacity: 0.85');
    }
  }
});

// Hand live calibrador
AFRAME.registerComponent('hand-live', {
  schema: {hand: {type:'string', default:'left'}},
  init: function(){
    this.pinch=0; this.grip=false;
    this.el.addEventListener('pinchstarted', ()=>{this.pinch=1;});
    this.el.addEventListener('pinchended', ()=>{this.pinch=0;});
    this.el.addEventListener('gripdown', ()=>{this.grip=true;});
    this.el.addEventListener('gripup', ()=>{this.grip=false;});
  },
  tick: function(){
    const id = this.data.hand==='left' ? 'leftHandData' : 'rightHandData';
    const tEl = document.getElementById(id);
    if(tEl){
      const p=this.el.object3D.position; const s=this.el.getAttribute('scale').x.toFixed(2);
      const tracking = this.el.components['hand-tracking-controls'] ? 'TRACK' : 'CTRL';
      tEl.setAttribute('value', this.data.hand.toUpperCase()+': '+tracking+'\\nPos '+p.x.toFixed(2)+' '+p.y.toFixed(2)+' '+p.z.toFixed(2)+'\\nScale '+s+' Pinch:'+(this.pinch?'ON':'OFF')+' Grip:'+(this.grip?'ON':'OFF'));
    }
  }
});

// Environment manager
AFRAME.registerComponent('environment-manager', {
  init: function(){ this.currentEnv='dark'; },
  setEnvironment: function(env){
    this.currentEnv=env;
    const sky=document.getElementById('sky360');
    const ground=document.getElementById('ground');
    const scene=document.querySelector('a-scene');
    const envText=document.getElementById('envText');
    if(env==='passthrough'){
      // Tenta immersive-ar
      if(navigator.xr){
        navigator.xr.isSessionSupported('immersive-ar').then(supported=>{
          if(supported){
            scene.setAttribute('background','color: transparent');
            scene.renderer.setClearColor(0x000000,0);
            scene.object3D.background=null;
            if(sky) sky.setAttribute('visible','false');
            if(ground) ground.setAttribute('visible','false');
            if(envText) envText.setAttribute('value','PASSTHROUGH - Sala real');
            // Solicita sessão AR se já em VR? Mostra instrução
            document.getElementById('toast').textContent='Para passthrough total, use o botão de passthrough do Quest';
            document.getElementById('toast').style.opacity='1';
            setTimeout(()=>{document.getElementById('toast').style.opacity='0';},2500);
          }else{
            // Fallback transparente
            scene.setAttribute('background','color: transparent');
            if(sky) sky.setAttribute('visible','false');
            if(envText) envText.setAttribute('value','PASSTHROUGH (fallback)');
          }
        });
      }else{
        scene.setAttribute('background','color: transparent');
        if(sky) sky.setAttribute('visible','false');
        if(envText) envText.setAttribute('value','PASSTHROUGH');
      }
    }else if(env==='dark'){
      scene.setAttribute('background','color: #050a14');
      scene.renderer.setClearColor(0x050a14,1);
      if(sky) sky.setAttribute('visible','false');
      if(ground){ ground.setAttribute('visible','true'); ground.setAttribute('color','#0a1430'); }
      if(envText) envText.setAttribute('value','MODO: ESCURO');
    }else if(env==='beach'){
      scene.setAttribute('background','color: #87CEEB');
      if(sky){ sky.setAttribute('visible','true'); sky.setAttribute('src','https://cdn.aframe.io/360-image-gallery-boilerplate/img/sechelt.jpg'); }
      if(envText) envText.setAttribute('value','MODO: PRAIA');
    }else if(env==='office'){
      scene.setAttribute('background','color: #d0d0d0');
      if(sky){ sky.setAttribute('visible','true'); sky.setAttribute('src','https://cdn.aframe.io/360-image-gallery-boilerplate/img/city.jpg'); }
      if(envText) envText.setAttribute('value','MODO: ESCRITORIO');
    }else if(env==='library'){
      scene.setAttribute('background','color: #2c1810');
      if(sky){ sky.setAttribute('visible','true'); sky.setAttribute('src','https://cdn.aframe.io/360-image-gallery-boilerplate/img/cubes.jpg'); }
      if(envText) envText.setAttribute('value','MODO: BIBLIOTECA');
    }else if(env==='space'){
      scene.setAttribute('background','color: #000005');
      if(sky){ sky.setAttribute('visible','true'); sky.setAttribute('src',''); sky.setAttribute('color','#000005'); }
      // Cria estrelas
      const world=document.getElementById('world');
      if(world && !document.getElementById('stars')){
        const stars=document.createElement('a-entity');
        stars.setAttribute('id','stars');
        for(let i=0;i<300;i++){
          const s=document.createElement('a-sphere');
          s.setAttribute('radius','0.05');
          s.setAttribute('color','white');
          s.setAttribute('position', (Math.random()-0.5)*100+' '+(Math.random()-0.5)*100+' '+(Math.random()-0.5)*100);
          stars.appendChild(s);
        }
        world.appendChild(stars);
      }
      if(envText) envText.setAttribute('value','MODO: ESPACO');
    }
  }
});

// Calibration system
AFRAME.registerComponent('calibration-system', {
  init: function(){
    const rig=document.getElementById('rig'); const head=document.getElementById('head');
    const left=document.getElementById('leftHand'); const right=document.getElementById('rightHand');
    const envManager=document.getElementById('envManager').components['environment-manager'];
    let handScale=1; let headH=1.65;
    this.el.querySelectorAll('.calib-btn').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        const a=btn.getAttribute('data-action');
        if(a==='resetPos') rig.setAttribute('position','0 0 8');
        if(a==='resetRot') rig.setAttribute('rotation','0 0 0');
        if(a==='handUp'){ handScale=Math.min(2.0, handScale+0.1); left.setAttribute('scale',handScale+' '+handScale+' '+handScale); right.setAttribute('scale',handScale+' '+handScale+' '+handScale); }
        if(a==='handDown'){ handScale=Math.max(0.2, handScale-0.1); left.setAttribute('scale',handScale+' '+handScale+' '+handScale); right.setAttribute('scale',handScale+' '+handScale+' '+handScale); }
        if(a==='heightUp'){ headH=Math.min(2.5, headH+0.1); head.setAttribute('position','0 '+headH+' 0'); }
        if(a==='heightDown'){ headH=Math.max(0.4, headH-0.1); head.setAttribute('position','0 '+headH+' 0'); }
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
        if(navigator.vibrate) navigator.vibrate(20);
      });
    });
  }
});
</script>
</head>
<body>
<div id="hud">
<div style="font-weight:900;color:white;font-size:14px;">__MODO__ - PMSC ARENA VR</div>
Grip = move bloco (mantem distancia) | Trigger = responde | Thumbstick = push/pull + rotaciona<br>
<div id="status" style="margin-top:6px;color:#00ff88;font-weight:700;">0/__LEN__ respondidas</div>
</div>
<div id="toast"></div>
<button id="enter">🥽 ENTRAR NO VR</button>

<a-scene
  background="color: #050a14"
  renderer="colorManagement:true; antialias:true"
  webxr="optionalFeatures: hand-tracking, local-floor, bounded-floor, hit-test, passthrough, plane-detection; requiredFeatures: local-floor"
  vr-mode-ui="enabled:true"
  embedded
  style="width:100%;height:__HEIGHT__px;"
>
<a-assets>
  <img id="beach360" src="https://cdn.aframe.io/360-image-gallery-boilerplate/img/sechelt.jpg" crossorigin="anonymous">
  <img id="office360" src="https://cdn.aframe.io/360-image-gallery-boilerplate/img/city.jpg" crossorigin="anonymous">
  <img id="library360" src="https://cdn.aframe.io/360-image-gallery-boilerplate/img/cubes.jpg" crossorigin="anonymous">
  <img id="space360" src="https://cdn.aframe.io/a-painter/images/space.jpg" crossorigin="anonymous">
</a-assets>

<a-entity light="type:ambient; intensity:1.0"></a-entity>
<a-entity light="type:directional; intensity:1.0" position="4 7 4"></a-entity>

<a-sky id="sky360" radius="30" visible="false"></a-sky>
<a-plane id="ground" rotation="-90 0 0" width="120" height="120" color="#0a1430"></a-plane>

<a-entity id="envManager" environment-manager></a-entity>

<a-entity id="rig" position="0 0 8" movement-controls="fly:true; speed:0.35">
  <a-entity id="head" camera look-controls wasd-controls="acceleration:22" position="0 1.65 0">
    <a-entity cursor="rayOrigin: mouse" raycaster="objects: .clickable, .grabbable" visible="false"></a-entity>
    <a-entity position="0 -0.65 -1.2">
      <a-plane width="1.4" height="0.6" color="black" opacity="0.7"></a-plane>
      <a-text id="hudVRText" value="0/18" color="#00ff88" width="2.0" align="center" position="0 0.12 0.01"></a-text>
      <a-text id="grabHUD" value="Mire no bloco" color="#00e5ff" width="1.8" align="center" position="0 -0.08 0.01"></a-text>
      <a-text id="envText" value="MODO: ESCURO" color="#ffaa00" width="1.6" align="center" position="0 -0.22 0.01"></a-text>
    </a-entity>
  </a-entity>

  <a-entity id="leftHand"
    hand-controls="hand: left; handModelStyle: lowPoly; color:#00d1ff"
    hand-tracking-controls="hand: left"
    hand-live="hand: left"
    vr-hand="hand: left; color: #00d1ff"
    raycaster="objects: .clickable, .grabbable; far: 100; showLine: false"
    line="color: #00d1ff; opacity: 0.85; start: 0 0 0; end: 0 0 -50"
    teleport-controls="cameraRig: #rig; teleportOrigin: #head; button: thumbstick"
  ></a-entity>

  <a-entity id="rightHand"
    hand-controls="hand: right; handModelStyle: lowPoly; color:#ff8a00"
    hand-tracking-controls="hand: right"
    hand-live="hand: right"
    vr-hand="hand: right; color: #ff8a00"
    raycaster="objects: .clickable, .grabbable; far: 100; showLine: false"
    line="color: #ff8a00; opacity: 0.85; start: 0 0 0; end: 0 0 -50"
    teleport-controls="cameraRig: #rig; teleportOrigin: #head; button: thumbstick"
  ></a-entity>
</a-entity>

<a-entity id="mainPanel" position="0 1.8 -1.5" calibration-system
  hoverable grabbable draggable droppable>
  <a-box width="3.4" height="2.9" depth="0.08" color="#0a0a0a" opacity="0.95" class="grabbable"></a-box>
  <a-text value="PMSC ARENA VR - CONTROLE" color="#00e5ff" width="3.8" align="center" position="0 1.25 0.06"></a-text>
  <a-text value="AMBIENTES" color="#00ff88" width="2.5" align="center" position="0 0.98 0.06"></a-text>
  <a-entity class="ui calib-btn" data-action="envPassthrough" data-color="#00a000" position="-0.95 0.70 0.06" geometry="primitive: plane; width:0.9; height:0.28" material="color:#00a000"><a-text value="PASSTHROUGH" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn" data-action="envDark" data-color="#1a3a6a" position="0 0.70 0.06" geometry="primitive: plane; width:0.65; height:0.28" material="color:#1a3a6a"><a-text value="ESCURO" color="white" width="1.4" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn" data-action="envBeach" data-color="#1a3a6a" position="0.95 0.70 0.06" geometry="primitive: plane; width:0.65; height:0.28" material="color:#1a3a6a"><a-text value="PRAIA" color="white" width="1.4" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn" data-action="envOffice" data-color="#1a3a6a" position="-0.95 0.37 0.06" geometry="primitive: plane; width:0.9; height:0.28" material="color:#1a3a6a"><a-text value="ESCRITORIO" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn" data-action="envLibrary" data-color="#1a3a6a" position="0 0.37 0.06" geometry="primitive: plane; width:0.85; height:0.28" material="color:#1a3a6a"><a-text value="BIBLIOTECA" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn" data-action="envSpace" data-color="#1a3a6a" position="0.95 0.37 0.06" geometry="primitive: plane; width:0.85; height:0.28" material="color:#1a3a6a"><a-text value="ESPACO" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-text value="ORGANIZACAO" color="#ffaa00" width="2.8" align="center" position="0 0.05 0.06"></a-text>
  <a-entity class="ui calib-btn" data-action="organize" data-color="#1a3a6a" position="-0.95 -0.18 0.06" geometry="primitive: plane; width:0.75; height:0.24" material="color:#1a3a6a"><a-text value="GRID" color="white" width="1.4" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn" data-action="organizeByMateria" data-color="#1a3a6a" position="0 -0.18 0.06" geometry="primitive: plane; width:0.9; height:0.24" material="color:#1a3a6a"><a-text value="POR MATERIA" color="white" width="1.6" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn" data-action="scatter" data-color="#1a3a6a" position="0.95 -0.18 0.06" geometry="primitive: plane; width:0.75; height:0.24" material="color:#1a3a6a"><a-text value="ESPALHAR" color="white" width="1.4" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn" data-action="saveLayout" data-color="#2a5a1a" position="-0.95 -0.48 0.06" geometry="primitive: plane; width:0.75; height:0.24" material="color:#2a5a1a"><a-text value="SALVAR" color="white" width="1.4" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn" data-action="loadLayout" data-color="#2a5a1a" position="0 -0.48 0.06" geometry="primitive: plane; width:0.75; height:0.24" material="color:#2a5a1a"><a-text value="CARREGAR" color="white" width="1.4" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn" data-action="resetArena" data-color="#1a3a6a" position="0.95 -0.48 0.06" geometry="primitive: plane; width:0.75; height:0.24" material="color:#1a3a6a"><a-text value="RESET" color="white" width="1.4" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-text value="CALIBRAGEM" color="#ffaa00" width="2.0" align="center" position="0 -0.78 0.06"></a-text>
  <a-entity class="ui calib-btn" data-action="handUp" data-color="#2a5a1a" position="-0.95 -1.0 0.06" geometry="primitive: plane; width:0.5; height:0.22" material="color:#2a5a1a"><a-text value="MAO +" color="white" width="1.2" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn" data-action="handDown" data-color="#2a5a1a" position="-0.4 -1.0 0.06" geometry="primitive: plane; width:0.5; height:0.22" material="color:#2a5a1a"><a-text value="MAO -" color="white" width="1.2" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn" data-action="heightUp" data-color="#1a3a6a" position="0.15 -1.0 0.06" geometry="primitive: plane; width:0.5; height:0.22" material="color:#1a3a6a"><a-text value="ALT +" color="white" width="1.2" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn" data-action="heightDown" data-color="#1a3a6a" position="0.7 -1.0 0.06" geometry="primitive: plane; width:0.5; height:0.22" material="color:#1a3a6a"><a-text value="ALT -" color="white" width="1.2" align="center" position="0 0 0.01"></a-text></a-entity>
  <a-entity class="ui calib-btn" data-action="exitVR" data-color="#a00000" position="1.3 -1.0 0.06" geometry="primitive: plane; width:0.5; height:0.22" material="color:#a00000"><a-text value="SAIR" color="white" width="1.2" align="center" position="0 0 0.01"></a-text></a-entity>
</a-entity>

<a-entity id="handCalibDisplay" position="2.8 1.8 -1.5">
  <a-box width="1.6" height="1.3" depth="0.06" color="#111111" opacity="0.9"></a-box>
  <a-text value="CALIBRADOR MAOS" color="#00ff88" width="2.0" align="center" position="0 0.5 0.05"></a-text>
  <a-text id="leftHandData" value="LEFT: aguardando" color="#00d1ff" width="1.7" align="left" position="-0.65 0.18 0.05" wrap-count="30"></a-text>
  <a-text id="rightHandData" value="RIGHT: aguardando" color="#ff8a00" width="1.7" align="left" position="-0.65 -0.22 0.05" wrap-count="30"></a-text>
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
  const cols=4, spacing=3.2;
  const x=(i%cols)*spacing - ((cols-1)*spacing/2);
  const z=Math.floor(i/cols)*-3.6 -1.5;
  const y=1.1 + Math.random()*0.8;
  const root=document.createElement('a-entity');
  root.setAttribute('id', 'block-'+i);
  root.setAttribute('position', x+' '+y+' '+z);
  root.setAttribute('class','grabbable');
  root.setAttribute('data-materia', q.materia);
  // IMPORTANTE: bloco é grabbable, mas titulo/pergunta NÃO são clickable (só grabbable para mover junto)
  const box=document.createElement('a-box');
  box.setAttribute('width','2.5'); box.setAttribute('height','2.3'); box.setAttribute('depth','0.22');
  box.setAttribute('color','#13244a'); box.setAttribute('class','grabbable');
  const title=document.createElement('a-text');
  title.setAttribute('value', (i+1)+'. '+q.materia);
  title.setAttribute('color','#00e5ff'); title.setAttribute('width','2.3'); title.setAttribute('align','center');
  title.setAttribute('position','0 0.9 0.13');
  title.setAttribute('class','grabbable');
  const qtext=document.createElement('a-text');
  const shortQ = q.pergunta.length>160 ? q.pergunta.slice(0,157)+'...' : q.pergunta;
  qtext.setAttribute('value', shortQ);
  qtext.setAttribute('color','white'); qtext.setAttribute('width','2.2'); qtext.setAttribute('align','center');
  qtext.setAttribute('position','0 0.45 0.13'); qtext.setAttribute('wrap-count','38');
  qtext.setAttribute('class','grabbable');
  root.appendChild(box); root.appendChild(title); root.appendChild(qtext);
  // Alternativas: APENAS alternativas são clickable, NÃO grabbable
  q.alternativas.forEach((alt, idx)=>{
    const letra = alt.trim().charAt(0).toUpperCase();
    const row=document.createElement('a-entity');
    row.setAttribute('position', '0 ' + (-0.05 - idx*0.3) + ' 0.14');
    row.setAttribute('class','clickable');
    row.setAttribute('data-letra', letra);
    const bg=document.createElement('a-plane');
    bg.setAttribute('width','2.1'); bg.setAttribute('height','0.24');
    bg.setAttribute('color','#0a1933'); bg.setAttribute('class','clickable');
    bg.setAttribute('data-letra', letra);
    const txt=document.createElement('a-text');
    txt.setAttribute('value', alt.length>62 ? alt.slice(0,59)+'...' : alt);
    txt.setAttribute('color','#cfe0ff'); txt.setAttribute('width','2.0'); txt.setAttribute('position','-1.0 0 0.01');
    txt.setAttribute('class','clickable');
    txt.setAttribute('data-letra', letra);
    bg.appendChild(txt); row.appendChild(bg);
    row.addEventListener('click', (e)=>{
      e.stopPropagation();
      answers[i]=letra;
      // Reseta cores do mesmo bloco
      document.querySelectorAll('#block-'+i+' a-plane').forEach(p=> p.setAttribute('color','#0a1933'));
      bg.setAttribute('color', letra===q.correta ? '#00c853' : '#d50000');
      const toast=document.getElementById('toast');
      if(toast){
        if(letra===q.correta){
          toast.textContent='✅ Correto!';
          toast.style.borderColor='#00c853'; toast.style.color='#00c853';
        }else{
          toast.textContent='❌ Errado (correta: '+q.correta+')';
          toast.style.borderColor='#d50000'; toast.style.color='#ff6b6b';
        }
        toast.style.opacity='1';
        setTimeout(()=>{toast.style.opacity='0';},1500);
      }
      if(navigator.vibrate) navigator.vibrate(letra===q.correta ? 40 : [30,30,30]);
      root.setAttribute('animation','property: scale; from:1 1 1; to:1.08 1.08 1.08; dur:120; dir:alternate; loop:1');
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
  // Tenta carregar layout salvo
  try{
    const saved=localStorage.getItem('pmsc_layout');
    if(saved){
      const layout=JSON.parse(saved);
      setTimeout(()=>{
        blocks.forEach(b=>{
          const id=b.id;
          if(layout[id]){
            b.setAttribute('position', layout[id].pos.x+' '+layout[id].pos.y+' '+layout[id].pos.z);
            if(layout[id].rot) b.setAttribute('rotation', layout[id].rot.x+' '+layout[id].rot.y+' '+layout[id].rot.z);
          }
        });
      },500);
    }
  }catch(e){}
  updateHUD();
}
window.organizeBlocks = function(){
  blocks.forEach((b,i)=>{
    const cols=4, spacing=3.2;
    const x=(i%cols)*spacing - ((cols-1)*spacing/2);
    const z=Math.floor(i/cols)*-3.6 -1.5;
    const y=1.1 + (i%3)*0.25;
    b.setAttribute('animation','property: position; to: '+x+' '+y+' '+z+'; dur: 700; easing: easeOutQuad');
  });
}
window.organizeByMateria = function(){
  const materias = {};
  blocks.forEach((b,i)=>{
    const mat = b.getAttribute('data-materia') || QUESTIONS[i].materia;
    if(!materias[mat]) materias[mat]=[];
    materias[mat].push(b);
  });
  let clusterX = -7;
  Object.keys(materias).forEach(mat=>{
    const cluster = materias[mat];
    cluster.forEach((b, idx)=>{
      const cols=2, spacing=2.8;
      const x=clusterX + (idx%cols)*spacing;
      const z=Math.floor(idx/cols)*-3.0 -1;
      const y=1.2 + (idx%2)*0.3;
      b.setAttribute('animation','property: position; to: '+x+' '+y+' '+z+'; dur: 800; easing: easeOutQuad');
    });
    clusterX += 6;
  });
}
window.scatterBlocks = function(){
  blocks.forEach((b,i)=>{
    const x=(Math.random()-0.5)*14; const z=(Math.random()-0.5)*14 -2; const y=0.8 + Math.random()*2.8;
    b.setAttribute('animation','property: position; to: '+x+' '+y+' '+z+'; dur: 700; easing: easeOutQuad');
    b.setAttribute('animation__rot','property: rotation; to: 0 '+(Math.random()*60-30)+' 0; dur: 700');
  });
}
window.saveLayout = function(){
  const layout = {};
  blocks.forEach(b=>{
    const id = b.id;
    layout[id] = {pos: b.getAttribute('position'), rot: b.getAttribute('rotation')};
  });
  try{
    localStorage.setItem('pmsc_layout', JSON.stringify(layout));
    document.getElementById('toast').textContent='✅ Layout salvo!';
    document.getElementById('toast').style.opacity='1';
    setTimeout(()=>{document.getElementById('toast').style.opacity='0';},1500);
  }catch(e){
    document.getElementById('toast').textContent='❌ Erro ao salvar';
    document.getElementById('toast').style.opacity='1';
  }
}
window.loadLayout = function(){
  try{
    const saved=localStorage.getItem('pmsc_layout');
    if(saved){
      const layout=JSON.parse(saved);
      blocks.forEach(b=>{
        const id=b.id;
        if(layout[id]){
          b.setAttribute('animation','property: position; to: '+layout[id].pos.x+' '+layout[id].pos.y+' '+layout[id].pos.z+'; dur: 800');
          if(layout[id].rot) b.setAttribute('animation__rot','property: rotation; to: '+layout[id].rot.x+' '+layout[id].rot.y+' '+layout[id].rot.z+'; dur: 800');
        }
      });
      document.getElementById('toast').textContent='✅ Layout carregado!';
      document.getElementById('toast').style.opacity='1';
      setTimeout(()=>{document.getElementById('toast').style.opacity='0';},1500);
    }else{
      document.getElementById('toast').textContent='Nenhum layout salvo';
      document.getElementById('toast').style.opacity='1';
    }
  }catch(e){}
}
document.addEventListener('DOMContentLoaded', ()=>{ window.initWorld(); });
document.getElementById('enter').addEventListener('click', ()=>{ document.querySelector('a-scene').enterVR(); });
</script>
</body>
</html>
    """
    html = html_template.replace("__Q_JSON__", q_json).replace("__MODO__", modo).replace("__LEN__", str(len(safe))).replace("__HEIGHT__", str(height))
    st.components.v1.html(html, height=height, scrolling=False)
    if st.button(f"❌ Fechar VR {modo}", key=f"close_{modo}", use_container_width=True):
        st.session_state[key]=False
        st.rerun()

# ===================== TABS =====================
tab1, tab2 = st.tabs(["🥽 ARENA VR", "📝 Simulado Clássico"])

with tab1:
    todas=[]
    for v in banco.values():
        todas.extend(v)
    random.shuffle(todas)
    st.markdown("### PMSC ARENA VR - Quest 3 / 3S")
    st.markdown("""
    **Controles no controle:**
    - **Grip (lateral)** → agarrar bloco à distância (mantém distância, não puxa para perto)
    - **Trigger (gatilho)** → responder alternativa exata apontada
    - **Thumbstick ↑↓** → empurrar/afastar bloco (máx 8m)
    - **Thumbstick ←→** → rotacionar bloco

    **Hand tracking (sem controle):**
    - **Pinch** → agarrar / responder

    **Dica:** Aponte para o bloco e segure Grip. O bloco NÃO voa para perto, fica onde está e acompanha sua mão.
    """)
    render_vr(todas, modo="ARENA", height=980)

with tab2:
    if st.session_state.simulado:
        sim=st.session_state.simulado
        qs=sim["questoes"]
        if not sim["finalizado"]:
            rest=max(0,4*3600-int(time.time()-sim["inicio"]))
            h,m,s=rest//3600,(rest%3600)//60,rest%60
            st.warning(f"⏱️ Tempo restante: {h:02d}:{m:02d}:{s:02d} | {len(qs)} questões | 60q oficiais AOCP")
            with st.form("form_simulado"):
                resp={}
                for i,q in enumerate(qs):
                    st.markdown(f"**{i+1}. [{q.get('materia','')}]** {q['pergunta']}")
                    esc=st.radio(f"q_{i}", q["alternativas"], index=None, key=f"sim_{i}", label_visibility="collapsed")
                    if esc:
                        # Extrai letra
                        letra = esc.strip()[0].upper() if esc.strip() else ""
                        if letra in "ABCDE":
                            resp[i]=letra
                    st.divider()
                c1,c2=st.columns(2)
                salvar=c1.form_submit_button("💾 Salvar respostas")
                finalizar=c2.form_submit_button("✅ Finalizar simulado", type="primary")
                if salvar:
                    sim["respostas"]=resp
                    st.success("Respostas salvas parcialmente")
                if finalizar:
                    ac=0
                    dets=[]
                    for i,q in enumerate(qs):
                        r=resp.get(i,"")
                        ok=r==q["correta"].upper()
                        if ok:
                            ac+=1
                        dets.append({"pergunta":q["pergunta"],"materia":q.get("materia",""),"resposta":r,"correta":q["correta"],"acertou":ok})
                    nota=round((ac/len(qs))*100,1) if qs else 0
                    aprovado=nota>=50
                    st.session_state.hist.append({
                        "data":datetime.now().strftime("%d/%m %H:%M"),
                        "acertos":ac,
                        "total":len(qs),
                        "nota":nota,
                        "aprovado":aprovado,
                        "detalhes":dets,
                        "tempo":time.time()-sim["inicio"]
                    })
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
                st.divider()
                with st.expander("📋 Gabarito comentado", expanded=True):
                    for i,d in enumerate(ult["detalhes"]):
                        cor = "✅" if d["acertou"] else "❌"
                        st.markdown(f"{cor} **{i+1}. [{d['materia']}]** {d['pergunta']}")
                        st.caption(f"Sua: {d['resposta'] or '—'} | Gabarito: {d['correta']}")
                        st.divider()
            if st.button("🔄 Novo Simulado", type="primary", use_container_width=True):
                st.session_state.simulado=None
                st.rerun()
    else:
        st.info("Inicie um simulado oficial de 60q pela sidebar. Distribuição: 10 Leg Inst, 8 Const, 8 Port, 6 Penal, 6 Proc Penal, 6 Penal Mil, 6 Leg Esp, 5 Trânsito, 5 Info.")
