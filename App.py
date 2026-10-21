import streamlit as st
import json
import random
import time
import pathlib
from collections import defaultdict
from datetime import datetime

st.set_page_config(page_title="PMSC 2026 AOCP", page_icon="🎯", layout="wide")

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
    try:
        arquivos = [f.name for f in base.iterdir() if f.is_file()]
    except:
        arquivos = ["erro ao listar"]
    
    # Procura todos .json na raiz
    candidatos = []
    try:
        for f in base.iterdir():
            if f.is_file() and f.suffix.lower() == ".json":
                candidatos.append(f)
    except:
        pass
    
    # Tenta cwd também
    try:
        cwd = pathlib.Path.cwd()
        for f in cwd.iterdir():
            if f.is_file() and f.suffix.lower() == ".json" and f not in candidatos:
                candidatos.append(f)
    except:
        pass

    if not candidatos:
        st.error(f"❌ Nenhum .json encontrado. Arquivos na pasta {base}: {arquivos}")
        return None, None

    for p in candidatos:
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                total = sum(len(v) for v in data.values() if isinstance(v, list))
                if total > 0:
                    return data, f"{p.name} ({total} questões)"
            elif isinstance(data, list):
                d = defaultdict(list)
                for q in data:
                    d[q.get("materia","Geral")].append(q)
                return dict(d), f"{p.name} ({len(data)} questões)"
        except Exception as e:
            st.warning(f"⚠️ Erro ao ler {p.name}: {e} - tentando correção automática...")
            try:
                import re
                text = p.read_text(encoding="utf-8")
                pat = re.compile(r'\{\s*"pergunta"\s*:\s*"((?:\\"|[^"])*)"\s*,\s*"alternativas"\s*:\s*\[(.*?)\]\s*,\s*"correta"\s*:\s*"([A-E])"\s*\}', re.DOTALL)
                materias = []
                for m in re.finditer(r'"(Legislação Institucional|Direito Constitucional|Língua Portuguesa|Legislação Especial|Legislação de Trânsito|Direito Penal Comum|Direito Processual Penal Comum|Direito Penal Militar|Informática)"\s*:\s*\[', text):
                    materias.append((m.start(), m.group(1)))
                materias.sort()
                questions = []
                for mm in pat.finditer(text):
                    alt_text = mm.group(2)
                    alts = re.findall(r'"((?:\\"|[^"])*)"', alt_text)
                    questions.append((mm.start(), {"pergunta": mm.group(1).replace('\\"', '"'), "alternativas": [a.replace('\\"', '"') for a in alts], "correta": mm.group(3)}))
                final = defaultdict(list)
                questions.sort()
                idx=0
                for qpos,qobj in questions:
                    while idx+1 < len(materias) and materias[idx+1][0] < qpos:
                        idx+=1
                    if idx < len(materias):
                        final[materias[idx][1]].append(qobj)
                if final:
                    return dict(final), f"{p.name} (corrigido - {sum(len(v) for v in final.values())} q)"
            except Exception as e2:
                st.error(f"Falha correção {p.name}: {e2}")
                continue
    st.error(f"❌ Nenhum JSON válido. Encontrados: {[c.name for c in candidatos]} | Arquivos na pasta: {arquivos}")
    return None, None

def montar_simulado(banco):
    sim=[]
    for mat,qtd in DISTRIBUICAO.items():
        pool=banco.get(mat,[])
        if not pool:
            for k,v in banco.items():
                if mat.lower() in k.lower() or k.lower() in mat.lower():
                    pool=v
                    break
        if pool:
            sim.extend([{**q, "materia": mat} for q in random.sample(pool, min(qtd, len(pool)))])
    random.shuffle(sim)
    return sim

if "simulado" not in st.session_state: st.session_state.simulado=None
if "treino" not in st.session_state: st.session_state.treino=[]
if "hist" not in st.session_state: st.session_state.hist=[]

banco, caminho = load_banco()

st.title("🎯 PMSC 2026 – Simulador AOCP")
if not banco:
    st.error("❌ json.json não encontrado na raiz. Coloque o json_corrigido.json como json.json no GitHub.")
    # Mostra arquivos para debug
    base = pathlib.Path(__file__).parent
    try:
        st.write("Arquivos na pasta:", [f.name for f in base.iterdir()])
    except Exception as e:
        st.write(f"Erro listar: {e}")
    st.stop()
st.caption(f"✅ {caminho} | {sum(len(v) for v in banco.values())} questões | Edital AOCP 60q")

with st.sidebar:
    st.success(f"📚 {sum(len(v) for v in banco.values())} questões")
    for k,v in banco.items():
        st.caption(f"{k}: {len(v)}")
    st.divider()
    mat = st.selectbox("Matéria treino", list(banco.keys()))
    qtd = st.slider("Qtd", 5, 20, 10)
    if st.button("▶️ Gerar Treino", use_container_width=True):
        pool=banco.get(mat,[])
        st.session_state.treino=[{**q, "materia": mat} for q in random.sample(pool, min(qtd, len(pool)))]
        st.session_state.simulado=None
        st.rerun()
    st.divider()
    if st.button("🚀 Simulado Oficial 60q", type="primary", use_container_width=True):
        st.session_state.simulado={"questoes": montar_simulado(banco), "inicio": time.time(), "respostas":{}, "finalizado": False}
        st.session_state.treino=[]
        st.rerun()
    if st.session_state.simulado and not st.session_state.simulado["finalizado"]:
        if st.button("❌ Cancelar"):
            st.session_state.simulado=None
            st.rerun()

def render_3d_leve(questoes, modo="ARENA"):
    if not questoes:
        return
    key = f"show3d_{modo}"
    if not st.session_state.get(key, False):
        if st.button(f"🥽 CARREGAR ARENA 3D {modo} - Quest 3S ({len(questoes[:15])} blocos)", key=f"btn3d_{modo}", type="primary"):
            st.session_state[key] = True
            st.rerun()
        st.info("Clique acima para carregar a arena imersiva. Isso evita travamento inicial.")
        return
    amostra = questoes[:15]
    safe = [{"pergunta": q["pergunta"][:150].replace(chr(34),"'"), "alternativas": [a[:50].replace(chr(34),"'") for a in q["alternativas"][:5]], "correta": q["correta"], "materia": q.get("materia","Geral")[:20]} for q in amostra]
    q_json = json.dumps(safe, ensure_ascii=False).replace("</", "<\\/")

    html = f'''
    <html><head><script src="https://aframe.io/releases/1.4.2/aframe.min.js"></script><script src="https://unpkg.com/super-hands@3.0.5/dist/super-hands.min.js"></script>
    <style>body{{margin:0;background:#070d1e;}}#hud{{position:fixed;top:10px;left:10px;z-index:9999;background:rgba(0,0,0,0.8);color:#00e5ff;padding:10px;border-radius:8px;font-size:12px;}}#vr{{position:fixed;bottom:15px;left:50%;transform:translateX(-50%);z-index:9999;background:#00d1ff;color:white;border:none;padding:12px 28px;border-radius:99px;font-weight:900;cursor:pointer;}}</style>
    </head><body><div id="hud">🥽 {modo} - {len(safe)} blocos<br>👊 Grip/Pinch = mover<br>👉 Trigger = responder</div><button id="vr">🥽 ENTRAR VR</button>
    <a-scene background="color:#070d1e" webxr="optionalFeatures: hand-tracking, local-floor" embedded style="height:650px;width:100%;"><a-entity light="type:ambient;intensity:0.8"></a-entity><a-plane rotation="-90 0 0" width="40" height="40" color="#0d1733"></a-plane>
    <a-entity id="rig" position="0 0 5"><a-entity camera look-controls wasd-controls position="0 1.6 0"><a-cursor raycaster="objects:.clickable,.grabbable" color="#00d1ff"></a-cursor></a-entity><a-entity hand-controls="hand:left" super-hands laser-controls="hand:left" raycaster="objects:.clickable,.grabbable;far:12"></a-entity><a-entity hand-controls="hand:right" super-hands laser-controls="hand:right" raycaster="objects:.clickable,.grabbable;far:12"></a-entity></a-entity><a-entity id="world"></a-entity></a-scene>
    <script>const QS={q_json};function mk(q,i){{const c=5,s=2.3,x=(i%c)*s-((c-1)*s/2),z=Math.floor(i/c)*-2.5,y=1.2+Math.random()*0.5;const r=document.createElement('a-entity');r.setAttribute('position',`${{x}} ${{y}} ${{z}}`);r.setAttribute('class','grabbable');r.setAttribute('grabbable','');const b=document.createElement('a-box');b.setAttribute('width','2');b.setAttribute('height','1.5');b.setAttribute('depth','0.15');b.setAttribute('color','#13244a');b.setAttribute('class','grabbable');const t=document.createElement('a-text');t.setAttribute('value',`${{i+1}}. ${{q.materia}}\\n${{q.pergunta.slice(0,80)}}`);t.setAttribute('color','white');t.setAttribute('width','1.8');t.setAttribute('align','center');t.setAttribute('position','0 0.35 0.1');t.setAttribute('wrap-count','28');r.appendChild(b);r.appendChild(t);q.alternativas.forEach((a,idx)=>{{const row=document.createElement('a-entity');row.setAttribute('position',`0 ${{-0.1-idx*0.18}} 0.1`);row.setAttribute('class','clickable');row.setAttribute('data-i',i);const bg=document.createElement('a-plane');bg.setAttribute('width','1.7');bg.setAttribute('height','0.14');bg.setAttribute('color','#0a1933');bg.setAttribute('class','clickable');const tx=document.createElement('a-text');tx.setAttribute('value',a);tx.setAttribute('color','#cfe0ff');tx.setAttribute('width','1.6');tx.setAttribute('position','-0.8 0 0.01');bg.appendChild(tx);row.appendChild(bg);row.addEventListener('click',()=>{{document.querySelectorAll(`[data-i="${{i}}"] a-plane`).forEach(p=>p.setAttribute('color','#0a1933'));bg.setAttribute('color',a.trim()[0].toUpperCase()===q.correta?'#00c853':'#d50000');}});r.appendChild(row);}});return r;}}document.addEventListener('DOMContentLoaded',()=>{{const w=document.getElementById('world');QS.forEach((q,i)=>w.appendChild(mk(q,i)));}});document.getElementById('vr').onclick=()=>document.querySelector('a-scene').enterVR();</script></body></html>
    '''
    st.components.v1.html(html, height=700, scrolling=False)
    if st.button("❌ Fechar 3D", key=f"close3d_{modo}"):
        st.session_state[key]=False
        st.rerun()

tab1, tab2, tab3 = st.tabs(["🌐 ARENA", "🏆 SIMULADO", "📖 TREINO"])
with tab1:
    todas=[]
    for v in banco.values(): todas.extend(v)
    random.shuffle(todas)
    st.subheader("🌐 Arena Quest 3S - Leve")
    render_3d_leve(todas, modo="LIVRE")
with tab2:
    if st.session_state.simulado:
        sim=st.session_state.simulado
        qs=sim["questoes"]
        if not sim["finalizado"]:
            rest=max(0,4*3600-int(time.time()-sim["inicio"]))
            h,m,s=rest//3600,(rest%3600)//60,rest%60
            st.warning(f"⏱️ {h:02d}:{m:02d}:{s:02d} | {len(qs)} questões")
            render_3d_leve(qs, modo="SIMULADO")
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
                    st.success("Salvo!")
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
        render_3d_leve(st.session_state.treino, modo="TREINO")
        for i,q in enumerate(st.session_state.treino):
            with st.expander(f"{i+1}. {q['pergunta'][:70]}..."):
                for a in q["alternativas"]: st.markdown(f"- {a}")
                st.success(f"Gabarito: {q['correta']}")
        if st.button("Encerrar treino"):
            st.session_state.treino=[]
            st.rerun()
    else:
        st.info("Gere um treino na barra lateral.")
