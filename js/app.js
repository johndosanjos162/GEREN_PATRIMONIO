/**
 * PMSC 2026 — Academia Militar Imersiva
 * JavaScript: Three.js + WebXR, questões, VR, áudio, treino de tiro
 * Painéis em 4K (4096×3072) com fallback automático
 */
import * as THREE from 'three';
import {XRControllerModelFactory} from 'three/addons/webxr/XRControllerModelFactory.js';
import {XRHandModelFactory} from 'three/addons/webxr/XRHandModelFactory.js';

const $ = id => document.getElementById(id);
const KEY = 'pmsc_quest_complete_v9';
const REPO = 'johndosanjos162/PMSC';

const environments = ['Pátio de formatura','Sala de instrução','Entrada do quartel','Campo de treinamento','Alojamento militar','Biblioteca militar','Auditório do quartel','Sala de estudos','Praça do quartel','Centro de operações'];
const subjectsBase = ['Língua Portuguesa','Informática','Direito Constitucional','Constituição de Santa Catarina','Direito Penal Comum','Direito Processual Penal Comum','Direito Penal Militar','Legislação Especial','Legislação de Trânsito','Legislação Institucional'];
const pages = [['home','Início'],['study','Questões'],['exam','Simulado'],['flash','Flashcards'],['review','Revisões'],['stats','Desempenho'],['bank','Banco JSON'],['settings','Configurações']];

const defaultState = () => ({
  settings:{env:0,lighting:'day',quality:'high',fontSize:120,distance:2.8,panelHeight:1.55,panelScale:1.05,speed:1.3,snap:30,volume:60,playerHeight:1.65,vignette:0,comfort:1},
  history:[],favorites:[],reviews:{},exams:[],session:null,panels:{}
});

let state=defaultState(),db=null,questions=[],page='home',busy=false,serial=0;

function note(msg){$('status').textContent=msg;}
function safeStore(){try{localStorage.setItem(KEY,JSON.stringify(state));}catch(e){console.warn(e);}idbPut('progress',state);}
function restoreState(){try{const saved=JSON.parse(localStorage.getItem(KEY));if(saved&&typeof saved==='object'){state={...defaultState(),...saved,settings:{...defaultState().settings,...saved.settings}};}}catch{}}
function el(tag,text,parent,cls){const n=document.createElement(tag);if(text!==undefined&&text!==null)n.textContent=String(text);if(cls)n.className=cls;if(parent)parent.append(n);return n;}
function button(text,callback,parent){const b=el('button',text,parent);b.onclick=callback;return b;}
function dateText(ms){return new Date(ms).toLocaleDateString('pt-BR');}
function download(name,content,type){const u=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=u;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1500);}
function csv(v){return '"'+String(v??'').replace(/"/g,'""')+'"';}

async function openDB(){return new Promise(resolve=>{if(!('indexedDB' in window))return resolve(null);try{const r=indexedDB.open('PMSC_QUEST_V9',1);r.onupgradeneeded=()=>r.result.createObjectStore('kv');r.onsuccess=()=>resolve(r.result);r.onerror=()=>resolve(null);}catch{resolve(null)}});}
function idbGet(key){return new Promise(resolve=>{if(!db)return resolve(null);try{const r=db.transaction('kv').objectStore('kv').get(key);r.onsuccess=()=>resolve(r.result??null);r.onerror=()=>resolve(null);}catch{resolve(null)}});}
function idbPut(key,value){if(!db)return;try{db.transaction('kv','readwrite').objectStore('kv').put(value,key);}catch(e){console.warn(e);}}

function normalize(raw,disc){
  if(!raw||typeof raw!=='object')return null;
  const text=raw.enunciado??raw.pergunta??raw.questao??raw.question??raw.texto;
  let src=raw.alternativas??raw.opcoes??raw.options??raw.respostas;
  if(typeof text!=='string'||!text.trim()||!src)return null;
  let options=[],keys=null;
  if(Array.isArray(src))options=src.map(v=>typeof v==='string'?v:String(v?.texto??v?.text??v?.alternativa??''));
  else if(typeof src==='object'){keys=Object.keys(src);options=keys.map(k=>String(src[k]?.texto??src[k]?.text??src[k]));}
  if(options.length<2||options.length>5||options.some(t=>!t.trim()))return null;
  let answer=raw.correta??raw.gabarito??raw.correct??raw.resposta_correta??raw.alternativa_correta??raw.resposta,correct=-1;
  if(typeof answer==='number')correct=answer;
  else if(typeof answer==='string'){const a=answer.trim();const match=a.match(/^(?:letra\s*)?([A-E])(?:\)|\.|\s|$)/i);if(match)correct=match[1].toUpperCase().charCodeAt(0)-65;else if(keys&&keys.includes(a))correct=keys.indexOf(a);else if(/^\d+$/.test(a))correct=+a;else correct=options.indexOf(a);}
  if(!Number.isInteger(correct)||correct<0||correct>=options.length)return null;
  const subject=String(raw.disciplina??raw.materia??raw.subject??disc??'Geral'),question=text.trim();
  return {id:String(raw.id??raw.codigo??subject+'|'+question),subject,topic:String(raw.assunto??raw.topico??raw.topic??'Geral'),difficulty:String(raw.dificuldade??'media').toLowerCase(),question,options,correct,explanation:String(raw.explicacao??raw.comentario??raw.justificativa??''),reference:String(raw.referencia??''),tags:Array.isArray(raw.tags)?raw.tags:[]};
}
function extract(data,subject='Geral',out=[],seen=new WeakSet()){
  if(!data||typeof data!=='object'||seen.has(data))return out;
  seen.add(data);
  if(Array.isArray(data)){for(const x of data)extract(x,subject,out,seen);return out;}
  const q=normalize(data,subject);if(q){out.push(q);return out;}
  const generic=new Set(['questoes','questions','data','dados','items','disciplinas','banco','perguntas','lista']);
  for(const [key,val] of Object.entries(data))if(val&&typeof val==='object')extract(val,generic.has(key.toLowerCase())?subject:key,out,seen);
  return out;
}
function merge(list,replace=true){
  const map=new Map(replace?[]:questions.map(q=>[q.id,q]));
  let rejected=0;
  for(const item of list){const q=(item?.options&&item?.question&&typeof item?.correct==='number')?item:normalize(item,'Geral');if(q)map.set(q.id,q);else rejected++;}
  questions=[...map.values()];idbPut('bank',questions);fillFilters();
  if(!state.session||!state.session.ids?.length)newSession(page==='exam'?'exam':'study',false);
  render();return {rejected,total:questions.length};
}

async function loadBank(){
  if(busy)return;busy=true;const job=++serial;note('Lendo JSON da raiz…');$('bankStatus').textContent='Procurando arquivos JSON…';
  const urls=new Set([new URL('json.json',location.href).href]);
  let fileCount=0,failed=0,rejected=0;
  try{const r=await fetch(`https://api.github.com/repos/${REPO}/contents/`,{cache:'no-store',headers:{Accept:'application/vnd.github+json'}});
    if(r.ok){const files=await r.json();if(Array.isArray(files))for(const f of files)if(f.type==='file'&&/\.json$/i.test(f.name)&&f.download_url&&!/package|config|manifest|lock/i.test(f.name))urls.add(f.download_url);}
  }catch(e){console.warn('GitHub API',e);}
  const map=new Map();
  for(const uri of [...urls].slice(0,45)){
    try{const r=await fetch(uri,{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const txt=await r.text();if(txt.length>10000000)throw Error('Arquivo >10MB');const list=extract(JSON.parse(txt));if(list.length)fileCount++;for(const q of list)map.set(q.id,q);}
    catch(e){failed++;console.warn('JSON não carregado',uri,e);}
  }
  if(job!==serial){busy=false;return;}
  if(map.size){const result=merge([...map.values()]);rejected=result.rejected;$('bankStatus').textContent=`${questions.length} questões • ${fileCount} arquivo(s) • ${failed} falha(s) • ${rejected} rejeitadas`;note('Questões atualizadas automaticamente.');}
  else{const cached=await idbGet('bank');if(Array.isArray(cached)&&cached.length)merge(cached);$('bankStatus').textContent=questions.length?`Usando ${questions.length} questões do cache.`:'Não encontrei questões válidas.';note(questions.length?'Banco local recuperado.':'Falha ao carregar JSON.');}
  busy=false;render();
}

function filtered(){
  const s=$('subject').value,t=$('topic').value,d=$('difficulty').value,k=$('search').value.toLowerCase();
  return questions.filter(q=>(!s||q.subject===s)&&(!t||q.topic===t)&&(!d||q.difficulty===d)&&(!k||(q.question+' '+q.subject+' '+q.topic+' '+q.reference).toLowerCase().includes(k)));
}
function fillFilters(){
  const groups=[['subject',[...new Set([...subjectsBase,...questions.map(q=>q.subject)])]],['topic',[...new Set(questions.map(q=>q.topic))]]];
  for(const [id,values] of groups){const n=$(id),old=n.value;n.replaceChildren(new Option(id==='subject'?'Todas as disciplinas':'Todos os assuntos',''));for(const v of values.sort((a,b)=>a.localeCompare(b,'pt-BR')))n.add(new Option(v,v));n.value=[...n.options].some(x=>x.value===old)?old:'';}
}
function shuffle(a){const b=[...a];for(let i=b.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[b[i],b[j]]=[b[j],b[i]];}return b;}
function newSession(mode=page,persist=true){
  let items=filtered();
  if(mode==='review')items=items.filter(q=>state.reviews[q.id]);
  if(mode==='exam'){items=shuffle(items);const n=$('examCount').value;if(n!=='all')items=items.slice(0,+n);}
  state.session={mode,ids:items.map(q=>q.id),index:0,answers:{},graded:{},start:Date.now(),minutes:mode==='exam'?Math.max(0,Number($('examTime').value)||0):0,feedback:$('examFeedback').value,finished:false,flip:false,scroll:0,report:null};
  if(persist)safeStore();render();
}
function currentPool(){if(!state.session)return[];return state.session.ids.map(id=>questions.find(q=>q.id===id)).filter(Boolean);}
function currentQuestion(){const a=currentPool();if(!a.length)return null;state.session.index=Math.max(0,Math.min(state.session.index,a.length-1));return a[state.session.index];}
function record(q,choice,mode){
  const correct=choice===q.correct;
  state.history.push({id:q.id,subject:q.subject,topic:q.topic,correct,choice,mode,date:Date.now()});
  if(state.history.length>12000)state.history=state.history.slice(-12000);
  if(!correct)gradeReview(q.id,1);else if(state.reviews[q.id])gradeReview(q.id,4);
}
function gradeReview(id,quality){
  const old=state.reviews[id]||{interval:0,repetitions:0,ease:2.5};
  let r=old.repetitions,interval=old.interval,ease=old.ease;
  if(quality<3){r=0;interval=1;}else{r++;interval=r===1?1:r===2?6:Math.max(1,Math.round(interval*ease));}
  ease=Math.max(1.3,ease+.1-(5-quality)*(.08+(5-quality)*.02));
  state.reviews[id]={interval,repetitions:r,ease,due:Date.now()+interval*86400000};
}
function choose(i){
  const q=currentQuestion(),s=state.session;
  if(!q||s.finished||s.mode==='flash')return;
  let feedbackPlayed=false;
  if(s.mode==='exam'){
    s.answers[q.id]=i;
    if(s.feedback==='immediate'&&!s.graded[q.id]){s.graded[q.id]=true;record(q,i,'exam');feedbackPlayed=true;}
  }else if(!s.graded[q.id]){
    s.answers[q.id]=i;s.graded[q.id]=true;record(q,i,s.mode);feedbackPlayed=true;
  }
  if(feedbackPlayed){if(i===q.correct)playCorrect();else playWrong();}
  safeStore();render();
}
function next(delta){
  const s=state.session,a=currentPool();if(!s||!a.length)return;
  if(s.mode==='exam'&&delta>0&&s.index===a.length-1){finishExam();return;}
  s.index=Math.max(0,Math.min(a.length-1,s.index+delta));s.flip=false;s.scroll=0;safeStore();render();
}
function finishExam(){
  const s=state.session;if(!s||s.mode!=='exam'||s.finished)return;
  let correct=0,wrong=0,blank=0;const bySubject={};
  for(const q of currentPool()){
    const v=s.answers[q.id];if(!bySubject[q.subject])bySubject[q.subject]={total:0,correct:0};bySubject[q.subject].total++;
    if(v===undefined){blank++;continue;}if(v===q.correct){correct++;bySubject[q.subject].correct++;}else wrong++;
    if(!s.graded[q.id]){s.graded[q.id]=true;record(q,v,'exam');}
  }
  s.finished=true;s.report={date:Date.now(),total:currentPool().length,correct,wrong,blank,ms:Date.now()-s.start,bySubject};
  state.exams.push(s.report);safeStore();render();
  playTaps();
}
function gradeCard(level){const q=currentQuestion();if(!q)return;gradeReview(q.id,level);state.session.flip=false;safeStore();next(1);}
function favorite(){const q=currentQuestion();if(!q)return;state.favorites=state.favorites.includes(q.id)?state.favorites.filter(id=>id!==q.id):[...state.favorites,q.id];safeStore();render();}
function stats(){const h=state.history,ok=h.filter(v=>v.correct).length;return {total:h.length,ok,pct:h.length?Math.round(100*ok/h.length):0,pending:Object.values(state.reviews).filter(r=>r.due<=Date.now()).length,exams:state.exams.length};}
function recommend(){
  const bucket={};for(const v of state.history){const z=bucket[v.subject]??={total:0,ok:0};z.total++;if(v.correct)z.ok++;}
  return Object.entries(bucket).filter(([,z])=>z.total>=2).sort((a,b)=>a[1].ok/a[1].total-b[1].ok/b[1].total)[0]?.[0]||'Comece respondendo algumas questões';
}
function go(p){page=p;if(['exam','study','flash','review'].includes(p)){if(!state.session||state.session.mode!==p)newSession(p);else render();}else render();}

function heading(t,p){el('h2',t,p);}
function render(){
  const c=$('content');c.replaceChildren();
  for(const b of document.querySelectorAll('#navigation button'))b.style.borderColor=b.dataset.page===page?'#7cffac':'';
  const s=stats();
  if(page==='home'){
    heading('Central Inteligente de Estudos',c);
    el('p',`Questões carregadas: ${questions.length} • Respondidas: ${s.total} • Acertos: ${s.pct}% • Revisões pendentes: ${s.pending}`,c);
    el('p','Recomendação: '+recommend(),c);
    const r=el('div',null,c,'row');
    button('Estudar questões',()=>go('study'),r);button('Simulado',()=>go('exam'),r);button('Flashcards',()=>go('flash'),r);button('Revisões',()=>go('review'),r);
    if(state.session?.ids?.length)button('Continuar última sessão',()=>{page=state.session.mode;render();},c);
  }else if(page==='bank'){
    heading('Banco de Questões do GitHub',c);
    el('p',$('bankStatus').textContent,c);
    el('p',`Repositório público: ${REPO} • raiz: json.json e demais arquivos .json`,c);
    const counts={};for(const q of questions)counts[q.subject]=(counts[q.subject]||0)+1;
    for(const [n,v] of Object.entries(counts))el('p',n+': '+v,c);
    button('Atualizar',loadBank,c);
  }else if(page==='stats'){
    heading('Evolução e Desempenho',c);
    for(const [n,v] of [['Respondidas',s.total],['Acertos',s.ok],['Aproveitamento',s.pct+'%'],['Simulados',s.exams],['Revisões pendentes',s.pending]]){const m=el('div',null,c,'metric');el('strong',v,m);el('small',n,m);}
    const groups={};for(const v of state.history){const g=groups[v.subject]??={n:0,ok:0};g.n++;if(v.correct)g.ok++;}
    heading('Por disciplina',c);
    for(const [name,g] of Object.entries(groups)){el('p',`${name}: ${g.ok}/${g.n}`,c);const p=el('div',null,c,'bar');const b=el('span',null,p);b.style.width=(g.ok/g.n*100)+'%';}
    heading('Simulados recentes',c);
    for(const r of state.exams.slice(-8).reverse())el('p',`${dateText(r.date)} — ${r.correct}/${r.total}, ${r.blank} em branco`,c);
  }else if(page==='settings'){
    heading('Configurações e Controles',c);
    el('p','Ajuste fontes, distância, ambiente e velocidade no menu lateral. Em VR, segure o botão grip apontando para um painel e mova a mão.',c);
    el('p','A pinça também pode mover o painel pela barra superior. Use o gatilho ou a pinça para selecionar.',c);
    el('p','Painéis renderizados em 4K (4096×3072) — texto extremamente nítido no Quest 3S.',c);
    el('p','Se perceber queda de FPS, reduza a qualidade ou altere PIXEL_SCALE no código.',c);
    button('Restaurar posição dos painéis',resetPanelPositions,c);
    button('Modo foco',()=>document.body.classList.toggle('focus'),c);
    button('Modo leitura',()=>document.body.classList.toggle('reading'),c);
  }else{
    const q=currentQuestion(),pool=currentPool(),session=state.session;
    heading(({study:'Questões',exam:'Simulado',flash:'Flashcards',review:'Revisão de Erros'})[page]||'Estudos',c);
    if(!q)el('p','Nenhuma questão disponível. Atualize o JSON ou escolha outra disciplina.',c);
    else if(session.finished&&session.report){const r=session.report;el('p',`Simulado finalizado: ${r.correct} acertos, ${r.wrong} erros e ${r.blank} em branco.`,c);button('Novo simulado',()=>newSession('exam'),c);}
    else{
      el('p',`${session.index+1}/${pool.length} • ${q.subject} • ${q.topic}`,c,'muted');
      el('div',q.question,c,'question');
      if(page==='flash'){
        const card=el('div',session.flip?'RESPOSTA: '+q.options[q.correct]+'\n'+q.explanation:'Toque em Virar para revelar a resposta',c,'question');
        card.style.padding='20px';
        button('Virar flashcard',()=>{session.flip=!session.flip;safeStore();render();},c);
        if(session.flip){const r=el('div',null,c,'row');for(const [t,v] of [['Difícil',1],['Bom',4],['Fácil',5]])button(t,()=>gradeCard(v),r);}
      }else{
        q.options.forEach((o,i)=>{
          const b=button(String.fromCharCode(65+i)+') '+o,()=>choose(i),c);b.className='answer';
          const ans=session.answers[q.id],reveal=page!=='exam'||session.feedback==='immediate';
          if(ans===i)b.classList.add('selected');
          if(ans!==undefined&&reveal){if(i===q.correct)b.classList.add('correct');else if(i===ans)b.classList.add('wrong');}
        });
        const ans=session.answers[q.id];
        if(ans!==undefined&&(page!=='exam'||session.feedback==='immediate'))el('p',(ans===q.correct?'Correto. ':'Incorreto. ')+(q.explanation||'')+(q.reference?' Referência: '+q.reference:''),c,'note');
      }
      const r=el('div',null,c,'row');
      button('◀ Anterior',()=>next(-1),r);button('Próxima ▶',()=>next(1),r);
      button(state.favorites.includes(q.id)?'★ Favorita':'☆ Favoritar',favorite,r);
      if(page==='exam'){button('Finalizar simulado',finishExam,c);const left=session.minutes?Math.max(0,Math.ceil((session.minutes*60000-(Date.now()-session.start))/1000)):0;el('p',session.minutes?`Tempo restante: ${Math.floor(left/60)}m ${left%60}s`:'Sem limite de tempo',c);}
      if(page==='review')el('p',`Revisão prevista: ${state.reviews[q.id]?dateText(state.reviews[q.id].due):'Não marcada'}`,c);
    }
  }
  updateVR();
}

function exportBackup(){download('pmsc-backup.json',JSON.stringify({version:9,state},null,2),'application/json');}
function exportCSV(){const rows=['id,disciplina,assunto,acerto,modo,data',...state.history.map(x=>[x.id,x.subject,x.topic,x.correct,x.mode,new Date(x.date).toISOString()].map(csv).join(','))];download('pmsc-historico.csv',rows.join('\n'),'text/csv');}

// =====================================================
// ÁUDIO — CORNETA MILITAR
// =====================================================
let audioCtx=null,masterGain=null,convolver=null;

function initAudio(){
  if(audioCtx)return;
  try{
    audioCtx=new (window.AudioContext||window.webkitAudioContext)();
    masterGain=audioCtx.createGain();
    masterGain.gain.value=(state.settings.volume??60)/100;
    convolver=audioCtx.createConvolver();
    const rate=audioCtx.sampleRate,length=Math.floor(rate*2.2);
    const impulse=audioCtx.createBuffer(2,length,rate);
    for(let ch=0;ch<2;ch++){
      const data=impulse.getChannelData(ch);
      for(let i=0;i<length;i++)data[i]=(Math.random()*2-1)*Math.pow(1-i/length,2.5);
    }
    convolver.buffer=impulse;
    const wet=audioCtx.createGain(); wet.gain.value=0.28;
    convolver.connect(wet); wet.connect(masterGain);
    masterGain.connect(audioCtx.destination);
  }catch(e){console.warn('Audio não disponível:',e);}
}
function resumeAudio(){if(audioCtx&&audioCtx.state==='suspended')audioCtx.resume();}
function playNote(freq,when,dur,gain=0.2){
  if(!audioCtx)return;
  const osc=audioCtx.createOscillator(),env=audioCtx.createGain(),filt=audioCtx.createBiquadFilter();
  osc.type='sawtooth';osc.frequency.value=freq;
  filt.type='lowpass';filt.frequency.value=2600;filt.Q.value=1.4;
  env.gain.setValueAtTime(0,when);
  env.gain.linearRampToValueAtTime(gain,when+0.025);
  env.gain.linearRampToValueAtTime(gain*0.72,when+0.12);
  env.gain.exponentialRampToValueAtTime(0.001,when+dur);
  osc.connect(filt);filt.connect(env);
  env.connect(masterGain);env.connect(convolver);
  osc.start(when);osc.stop(when+dur+0.05);
}
function playFanfare(){
  initAudio();resumeAudio();if(!audioCtx)return;
  const t0=audioCtx.currentTime+0.1;
  const melody=[{f:392.00,t:0.00,d:0.24},{f:523.25,t:0.26,d:0.24},{f:659.25,t:0.52,d:0.24},{f:783.99,t:0.78,d:0.44},{f:1046.50,t:1.24,d:0.95}];
  for(const n of melody){playNote(n.f,t0+n.t,n.d,0.22);playNote(n.f*1.003,t0+n.t+0.01,n.d,0.12);}
}
function playCorrect(){
  initAudio();resumeAudio();ensureSpatialAudio();if(!audioCtx)return;
  const t0=audioCtx.currentTime+0.02;
  const pos = panels.main ? panels.main.group.position.clone() : new THREE.Vector3(0,1.6,-2.5);
  playSpatialNote(659.25,t0,0.15,0.16,pos);
  playSpatialNote(1046.50,t0+0.10,0.24,0.16,pos);
}
function playWrong(){
  initAudio();resumeAudio();ensureSpatialAudio();if(!audioCtx)return;
  const t0=audioCtx.currentTime+0.02;
  const pos = panels.main ? panels.main.group.position.clone() : new THREE.Vector3(0,1.6,-2.5);
  playSpatialNote(523.25,t0,0.18,0.16,pos);
  playSpatialNote(392.00,t0+0.15,0.28,0.16,pos);
}
function playTaps(){
  initAudio();resumeAudio();if(!audioCtx)return;
  const t0=audioCtx.currentTime+0.1;
  const notes=[{f:392.00,t:0.0,d:0.48},{f:392.00,t:0.55,d:0.32},{f:523.25,t:0.95,d:0.48},{f:392.00,t:1.5,d:0.32},{f:329.63,t:1.9,d:0.48},{f:261.63,t:2.45,d:0.85}];
  for(const n of notes){playNote(n.f,t0+n.t,n.d,0.2);playNote(n.f*1.002,t0+n.t,n.d,0.1);}
}
document.addEventListener('pointerdown',()=>{initAudio();resumeAudio();},{once:true});

// =====================================================
// THREE.JS — RENDERER OTIMIZADO QUEST 3S
// =====================================================
const scene=new THREE.Scene();
scene.background=new THREE.Color('#9ec4d0');
scene.fog=new THREE.FogExp2(0x8aafb2,0.004);

const camera=new THREE.PerspectiveCamera(82,1,.05,200);
camera.position.set(0,1.65,0);
const rig=new THREE.Group();rig.add(camera);scene.add(rig);

const renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'high-performance',alpha:false});
renderer.xr.enabled=true;
renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.toneMapping=THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure=1.3;
renderer.shadowMap.enabled=true;
renderer.shadowMap.type=THREE.PCFSoftShadowMap;
renderer.shadowMap.autoUpdate=false;
renderer.shadowMap.needsUpdate=true;
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
$('scene').append(renderer.domElement);
renderer.setClearColor(0x8eb4c0, 1);

// ==========================================
// ✅ 4K: escala de painéis com fallback
// PIXEL_SCALE = 2 → 4096×3072 (4K por painel)
// Se GPU não suportar, reduz automaticamente.
// ==========================================
let PIXEL_SCALE = 2;
const LOGICAL_W = 2048, LOGICAL_H = 1536;
{
  const maxTex = (renderer.capabilities && renderer.capabilities.maxTextureSize) || 4096;
  const needed = LOGICAL_W * PIXEL_SCALE;
  if(maxTex < needed){
    PIXEL_SCALE = Math.max(1, Math.floor(maxTex / LOGICAL_W));
    console.warn(`[PMSC] GPU suporta ${maxTex}px. Reduzindo PIXEL_SCALE para ${PIXEL_SCALE}.`);
  }
  console.log(`[PMSC] Painéis em ${LOGICAL_W * PIXEL_SCALE}×${LOGICAL_H * PIXEL_SCALE} (PIXEL_SCALE=${PIXEL_SCALE})`);
}

// Iluminação
const ambient=new THREE.HemisphereLight(0xe8f4ff,0x4a5040,1.5);
scene.add(ambient);

const sun=new THREE.DirectionalLight(0xfff5e0,3.4);
sun.position.set(9,14,7);sun.castShadow=true;
sun.shadow.mapSize.set(2048,2048);
sun.shadow.camera.left=-16;sun.shadow.camera.right=16;
sun.shadow.camera.top=16;sun.shadow.camera.bottom=-16;
sun.shadow.camera.near=1;sun.shadow.camera.far=45;
sun.shadow.bias=-0.00025;sun.shadow.normalBias=0.035;
sun.shadow.radius=2.5;
scene.add(sun);scene.add(sun.target);

const fill=new THREE.DirectionalLight(0x9bb0d0,0.42);
fill.position.set(-9,7,-7);scene.add(fill);

const rim=new THREE.DirectionalLight(0xffe0c0,0.55);
rim.position.set(-5,8,-14);scene.add(rim);

const bounce=new THREE.DirectionalLight(0xc8dcc8,0.22);
bounce.position.set(0,-2,4);scene.add(bounce);
const vrAmbientBoost = new THREE.AmbientLight(0xffffff, 0.55);
scene.add(vrAmbientBoost);

// =====================================================
// CONFORTO VR · VINHETA · ÁUDIO ESPACIAL
// =====================================================
const vignetteUniforms = {
  uIntensity: { value: 0.0 },
  uRadius: { value: 0.85 },
  uSoftness: { value: 0.4 }
};
const vignetteMat = new THREE.ShaderMaterial({
  transparent: true, depthTest: false, depthWrite: false, blending: THREE.NormalBlending,
  uniforms: vignetteUniforms,
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
  fragmentShader: `
    uniform float uIntensity, uRadius, uSoftness;
    varying vec2 vUv;
    void main(){
      if(uIntensity < 0.01){ gl_FragColor = vec4(0.0); return; }
      vec2 c = vUv - 0.5; c.x *= 1.1;
      float d = length(c) * 2.0;
      float vig = smoothstep(uRadius, uRadius + uSoftness, d);
      float a = clamp(vig * uIntensity * 0.75, 0.0, 0.75);
      gl_FragColor = vec4(0.0, 0.0, 0.0, a);
    }
  `
});
const vignetteMesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), vignetteMat);
vignetteMesh.frustumCulled = false;
vignetteMesh.renderOrder = 999;
vignetteMesh.visible = false;
camera.add(vignetteMesh);
vignetteMesh.position.set(0, 0, -0.12);

let moveVignetteTarget = 0;
let moveVignetteCurrent = 0;
let isLocomoting = false;

function applyPlayerHeight(){
  const h = Number(state.settings.playerHeight) || 1.65;
  if(!renderer.xr.isPresenting) camera.position.y = h;
}

let listenerNode = null;
function ensureSpatialAudio(){
  initAudio();
  if(!audioCtx || listenerNode) return;
  try{
    listenerNode = audioCtx.listener;
    if(listenerNode.positionX){ listenerNode.positionX.value=0; listenerNode.positionY.value=1.6; listenerNode.positionZ.value=0; }
  }catch(e){}
}
function playSpatialNote(freq, when, dur, gain, worldPos){
  if(!audioCtx) return;
  ensureSpatialAudio();
  const osc = audioCtx.createOscillator();
  const env = audioCtx.createGain();
  const filt = audioCtx.createBiquadFilter();
  const panner = audioCtx.createPanner();
  panner.panningModel = 'HRTF';
  panner.distanceModel = 'inverse';
  panner.refDistance = 1.2;
  panner.maxDistance = 18;
  panner.rolloffFactor = 1.4;
  if(worldPos){
    if(panner.positionX){ panner.positionX.value=worldPos.x; panner.positionY.value=worldPos.y; panner.positionZ.value=worldPos.z; }
    else panner.setPosition(worldPos.x, worldPos.y, worldPos.z);
  }
  osc.type = 'sawtooth';
  osc.frequency.value = freq;
  filt.type = 'lowpass'; filt.frequency.value = 2400; filt.Q.value = 1.2;
  env.gain.setValueAtTime(0, when);
  env.gain.linearRampToValueAtTime(gain, when + 0.02);
  env.gain.exponentialRampToValueAtTime(0.001, when + dur);
  osc.connect(filt); filt.connect(env); env.connect(panner); panner.connect(masterGain);
  if(convolver){ const send = audioCtx.createGain(); send.gain.value = 0.2; env.connect(send); send.connect(convolver); }
  osc.start(when); osc.stop(when + dur + 0.05);
}

// Sky dome
let skyMesh=null;
function initSky(){
  const uniforms={
    uTop:{value:new THREE.Color('#2e6a9e')},
    uHorizon:{value:new THREE.Color('#c5dcec')},
    uSunDir:{value:new THREE.Vector3(0.38,0.78,0.48).normalize()},
    uSunColor:{value:new THREE.Color('#fff6d8')},
    uIntensity:{value:1.0},
    uNight:{value:0.0}
  };
  const mat=new THREE.ShaderMaterial({
    side:THREE.BackSide,depthWrite:false,fog:false,uniforms,
    vertexShader:`varying vec3 vDir;void main(){vDir=normalize(position);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader:`
      varying vec3 vDir;
      uniform vec3 uTop,uHorizon,uSunColor,uSunDir;
      uniform float uIntensity,uNight;
      void main(){
        float h=vDir.y;
        float t=smoothstep(-0.08,0.88,h);
        vec3 dayCol=mix(uHorizon,uTop,t);
        float sunDot=max(dot(normalize(vDir),normalize(uSunDir)),0.0);
        float sunDisk=smoothstep(0.9988,0.9995,sunDot);
        float sunHalo=pow(sunDot,110.0)*0.75+pow(sunDot,14.0)*0.22;
        dayCol+=uSunColor*(sunDisk*6.0+sunHalo);
        dayCol=mix(dayCol,dayCol*vec3(1.05,1.0,0.95),pow(1.0-t,1.5)*0.15);
        vec3 nightTop=vec3(0.015,0.03,0.08);
        vec3 nightHorizon=vec3(0.07,0.10,0.18);
        vec3 nightCol=mix(nightHorizon,nightTop,t);
        float moonDot=max(dot(normalize(vDir),normalize(uSunDir)),0.0);
        float moonDisk=smoothstep(0.9992,0.9996,moonDot);
        float moonHalo=pow(moonDot,180.0)*0.45;
        nightCol+=vec3(0.72,0.80,1.0)*(moonDisk*2.2+moonHalo);
        vec3 starsCol=vec3(0.0);
        if(uNight>0.5){
          float star=step(0.99935,fract(sin(dot(floor(vDir*280.0),vec3(12.9898,78.233,37.719)))*43758.5453));
          starsCol=vec3(star)*0.95;
        }
        nightCol+=starsCol;
        vec3 col=mix(dayCol,nightCol,uNight)*uIntensity;
        gl_FragColor=vec4(col,1.0);
      }
    `
  });
  skyMesh=new THREE.Mesh(new THREE.SphereGeometry(95,48,24),mat);
  skyMesh.frustumCulled=false;skyMesh.renderOrder=-1;
  scene.add(skyMesh);
}

// IBL
const iblSource=new THREE.Scene();
const iblShader=new THREE.ShaderMaterial({
  side:THREE.BackSide,depthWrite:false,uniforms:{night:{value:0}},
  vertexShader:`varying vec3 vDirection;void main(){vDirection=normalize(position);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
  fragmentShader:`
    varying vec3 vDirection;uniform float night;
    void main(){
      vec3 d=normalize(vDirection);
      float skyBlend=smoothstep(-.18,.88,d.y);
      vec3 groundColor=vec3(.18,.21,.18);
      vec3 skyColor=vec3(.42,.56,.72);
      vec3 dayColor=mix(groundColor,skyColor,skyBlend);
      vec3 sunDirection=normalize(vec3(.38,.88,.48));
      float sunlight=pow(max(dot(d,sunDirection),0.),480.);
      dayColor+=sunlight*vec3(5.5,4.8,3.6);
      vec3 nightColor=mix(vec3(.04,.05,.08),vec3(.10,.14,.22),skyBlend);
      gl_FragColor=vec4(mix(dayColor,nightColor,night),1.);
    }
  `
});
iblSource.add(new THREE.Mesh(new THREE.SphereGeometry(15,32,16),iblShader));
const iblPmrem=new THREE.PMREMGenerator(renderer);
iblShader.uniforms.night.value=0;const iblDayTarget=iblPmrem.fromScene(iblSource,.05);
iblShader.uniforms.night.value=1;const iblNightTarget=iblPmrem.fromScene(iblSource,.05);
scene.environment=iblDayTarget.texture;
iblSource.children[0].geometry.dispose();iblShader.dispose();iblPmrem.dispose();

// =====================================================
// TEXTURAS PROCEDURAIS
// =====================================================
const world=new THREE.Group(); scene.add(world);

function noise2(x,y){return (Math.sin(x*12.9898+y*78.233)*43758.5453)%1;}
function fbm(x,y,oct=4){let v=0,a=0.5;for(let i=0;i<oct;i++){v+=a*Math.abs(noise2(x,y));x*=2;y*=2;a*=0.5;}return v;}
function makeSurfaceTexture(kind,size=512){
  const canvas=document.createElement('canvas');canvas.width=size;canvas.height=size;
  const ctx=canvas.getContext('2d');const img=ctx.createImageData(size,size);
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    const i=(y*size+x)*4;
    const nx=x/size,ny=y/size;
    const grain=fbm(nx*8,ny*8,5);
    const micro=Math.sin(x*0.15)*Math.cos(y*0.13)*0.5+0.5;
    let r=240,g=240,b=240;
    if(kind==='color'){const v=220+grain*28+micro*8;r=g=b=Math.min(255,v|0);}
    if(kind==='roughness'){const v=160+grain*70+micro*20;r=g=b=Math.min(255,v|0);}
    if(kind==='normal'){r=127+((micro-0.5)*18)|0;g=127+((Math.sin(y*0.18)-0.5)*16)|0;b=255;}
    if(kind==='ao'){const u=Math.abs(nx-0.5)*2,v=Math.abs(ny-0.5)*2;const edge=Math.max(u,v);r=g=b=Math.round(255-30*edge*edge);}
    img.data[i]=r;img.data[i+1]=g;img.data[i+2]=b;img.data[i+3]=255;
  }
  ctx.putImageData(img,0,0);
  const t=new THREE.CanvasTexture(canvas);
  t.colorSpace=kind==='color'?THREE.SRGBColorSpace:THREE.NoColorSpace;
  t.wrapS=THREE.RepeatWrapping;t.wrapT=THREE.RepeatWrapping;t.repeat.set(2,2);
  t.generateMipmaps=true;t.minFilter=THREE.LinearMipmapLinearFilter;t.magFilter=THREE.LinearFilter;
  t.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());
  return t;
}
const surfaceMaps={
  color:makeSurfaceTexture('color',512),
  roughness:makeSurfaceTexture('roughness',512),
  normal:makeSurfaceTexture('normal',512),
  ao:makeSurfaceTexture('ao',256)
};

function makeWoodTexture(){
  const size=1024;
  const canvas=document.createElement('canvas');canvas.width=size;canvas.height=size;
  const ctx=canvas.getContext('2d');
  const base=ctx.createLinearGradient(0,0,size,0);
  base.addColorStop(0,'#5c4528');base.addColorStop(0.25,'#7a5e3a');base.addColorStop(0.5,'#8a6b46');base.addColorStop(0.75,'#7a5e3a');base.addColorStop(1,'#5c4528');
  ctx.fillStyle=base;ctx.fillRect(0,0,size,size);
  for(let i=0;i<380;i++){
    const y=Math.random()*size,alpha=0.12+Math.random()*0.35;
    ctx.strokeStyle=`rgba(32,20,10,${alpha})`;ctx.lineWidth=0.5+Math.random()*2.8;
    ctx.beginPath();
    for(let x=0;x<=size;x+=6){
      const wave=Math.sin(x*0.035+i*0.6)*3.2+Math.sin(x*0.011+i*1.1)*5.5+Math.sin(x*0.002*i)*1.5;
      if(x===0)ctx.moveTo(x,y+wave);else ctx.lineTo(x,y+wave);
    }
    ctx.stroke();
  }
  for(let k=0;k<7;k++){
    const kx=Math.random()*size,ky=Math.random()*size;
    for(let r=22;r>0;r--){
      ctx.strokeStyle=`rgba(28,16,6,${0.04+r*0.012})`;
      ctx.beginPath();ctx.ellipse(kx,ky,r,r*0.65,Math.random()*0.4,0,Math.PI*2);ctx.stroke();
    }
  }
  const img=ctx.getImageData(0,0,size,size);
  for(let i=0;i<img.data.length;i+=4){const n=(Math.random()-0.5)*12;img.data[i]+=n;img.data[i+1]+=n;img.data[i+2]+=n;}
  ctx.putImageData(img,0,0);
  const t=new THREE.CanvasTexture(canvas);t.colorSpace=THREE.SRGBColorSpace;
  t.wrapS=THREE.RepeatWrapping;t.wrapT=THREE.RepeatWrapping;t.anisotropy=8;t.repeat.set(1.4,1.4);
  t.generateMipmaps=true;t.minFilter=THREE.LinearMipmapLinearFilter;
  return t;
}
const woodTexture=makeWoodTexture();

function makeWoodNormal(){
  const size=512;
  const canvas=document.createElement('canvas');canvas.width=size;canvas.height=size;
  const ctx=canvas.getContext('2d');
  const img=ctx.createImageData(size,size);
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    const i=(y*size+x)*4;
    const grain=Math.sin(x*0.08+Math.sin(y*0.02)*4)*0.5+0.5;
    const fine=Math.sin(x*0.4+y*0.05)*0.3;
    img.data[i]=127+((grain+fine-0.5)*28)|0;
    img.data[i+1]=127+((Math.sin(y*0.12)-0.5)*18)|0;
    img.data[i+2]=255;img.data[i+3]=255;
  }
  ctx.putImageData(img,0,0);
  const t=new THREE.CanvasTexture(canvas);t.wrapS=t.wrapT=THREE.RepeatWrapping;t.repeat.set(1.4,1.4);
  t.anisotropy=4;return t;
}
const woodNormal=makeWoodNormal();

function makeFloorTexture(){
  const size=1024;
  const c=document.createElement('canvas');c.width=size;c.height=size;
  const ctx=c.getContext('2d');
  const plankH=size/8;
  const colors=['#5a3e22','#6b4a2a','#4f361d','#7a5a35','#5d3f22','#846641','#4a3018','#6f5332'];
  for(let p=0;p<8;p++){
    const cy=p*plankH;
    ctx.fillStyle=colors[p%colors.length];ctx.fillRect(0,cy,size,plankH);
    for(let g=0;g<90;g++){
      ctx.strokeStyle=`rgba(25,14,6,${0.08+Math.random()*0.22})`;
      ctx.lineWidth=0.4+Math.random()*1.6;
      const y=cy+Math.random()*plankH;
      ctx.beginPath();ctx.moveTo(0,y);
      for(let x=0;x<size;x+=12)ctx.lineTo(x,y+Math.sin(x*0.028+g)*1.5);
      ctx.stroke();
    }
    ctx.strokeStyle='rgba(15,8,3,0.75)';ctx.lineWidth=2.5;
    ctx.strokeRect(0,cy,size,plankH);
  }
  for(let s=0;s<10;s++){
    const x=Math.random()*size,p=Math.floor(Math.random()*8);
    ctx.strokeStyle='rgba(12,6,2,0.65)';ctx.lineWidth=1.8;
    ctx.beginPath();ctx.moveTo(x,p*plankH);ctx.lineTo(x,(p+1)*plankH);ctx.stroke();
  }
  const img=ctx.getImageData(0,0,size,size);
  for(let i=0;i<img.data.length;i+=4){const n=(Math.random()-0.5)*10;img.data[i]+=n;img.data[i+1]+=n;img.data[i+2]+=n;}
  ctx.putImageData(img,0,0);
  const t=new THREE.CanvasTexture(c);t.wrapS=t.wrapT=THREE.RepeatWrapping;t.repeat.set(5,5);
  t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=8;t.generateMipmaps=true;
  t.minFilter=THREE.LinearMipmapLinearFilter;return t;
}
const floorTexture=makeFloorTexture();

function makeFloorNormal(){
  const size=512;
  const c=document.createElement('canvas');c.width=size;c.height=size;
  const ctx=c.getContext('2d');
  const img=ctx.createImageData(size,size);
  const plankH=size/8;
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    const i=(y*size+x)*4;
    const py=y%plankH;
    const edge=py<3||py>plankH-3?0.35:0;
    const grain=Math.sin(x*0.1)*0.15;
    img.data[i]=127+((grain-edge)*40)|0;
    img.data[i+1]=127+((Math.sin(y*0.08)-edge*0.5)*30)|0;
    img.data[i+2]=255;img.data[i+3]=255;
  }
  ctx.putImageData(img,0,0);
  const t=new THREE.CanvasTexture(c);t.wrapS=t.wrapT=THREE.RepeatWrapping;t.repeat.set(5,5);t.anisotropy=4;return t;
}
const floorNormal=makeFloorNormal();

function makeWallTexture(){
  const size=512;
  const c=document.createElement('canvas');c.width=size;c.height=size;
  const ctx=c.getContext('2d');
  ctx.fillStyle='#c8c4b6';ctx.fillRect(0,0,size,size);
  const img=ctx.getImageData(0,0,size,size);
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    const i=(y*size+x)*4;
    const n=fbm(x/size*6,y/size*6,4)*18+(Math.random()-0.5)*8;
    img.data[i]=Math.min(255,Math.max(0,img.data[i]+n));
    img.data[i+1]=Math.min(255,Math.max(0,img.data[i+1]+n*0.95));
    img.data[i+2]=Math.min(255,Math.max(0,img.data[i+2]+n*0.9));
  }
  ctx.putImageData(img,0,0);
  for(let i=0;i<25;i++){
    const x=Math.random()*size,y=Math.random()*size,r=20+Math.random()*60;
    const g=ctx.createRadialGradient(x,y,0,x,y,r);
    g.addColorStop(0,`rgba(180,175,160,${0.08+Math.random()*0.1})`);
    g.addColorStop(1,'rgba(180,175,160,0)');
    ctx.fillStyle=g;ctx.fillRect(x-r,y-r,r*2,r*2);
  }
  const t=new THREE.CanvasTexture(c);t.wrapS=t.wrapT=THREE.RepeatWrapping;t.repeat.set(3.5,2);
  t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=4;return t;
}
const wallTexture=makeWallTexture();

function makeGrassTexture(){
  const size=512;
  const c=document.createElement('canvas');c.width=size;c.height=size;
  const ctx=c.getContext('2d');
  ctx.fillStyle='#3d5c2a';ctx.fillRect(0,0,size,size);
  for(let i=0;i<6000;i++){
    const x=Math.random()*size,y=Math.random()*size,h=2.5+Math.random()*8;
    const g=55+Math.random()*100;
    ctx.strokeStyle=`rgb(${35+Math.random()*35|0},${g|0},${25+Math.random()*25|0})`;
    ctx.lineWidth=0.5+Math.random()*1.0;
    ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+(Math.random()-0.5)*3,y-h);ctx.stroke();
  }
  for(let i=0;i<40;i++){
    const x=Math.random()*size,y=Math.random()*size,r=15+Math.random()*40;
    ctx.fillStyle=`rgba(${30+Math.random()*40|0},${70+Math.random()*50|0},${20+Math.random()*30|0},0.15)`;
    ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();
  }
  const t=new THREE.CanvasTexture(c);t.wrapS=t.wrapT=THREE.RepeatWrapping;t.repeat.set(16,16);
  t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=4;return t;
}
const grassTexture=makeGrassTexture();

function makeBarkTexture(){
  const c=document.createElement('canvas');c.width=256;c.height=512;
  const ctx=c.getContext('2d');
  ctx.fillStyle='#4a3420';ctx.fillRect(0,0,256,512);
  for(let i=0;i<500;i++){
    ctx.strokeStyle=`rgba(${25+Math.random()*30|0},${15+Math.random()*18|0},${8+Math.random()*12|0},${0.25+Math.random()*0.5})`;
    ctx.lineWidth=0.6+Math.random()*2.5;
    const x=Math.random()*256,y=Math.random()*512,h=12+Math.random()*55;
    ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+(Math.random()-0.5)*10,y+h);ctx.stroke();
  }
  for(let i=0;i<30;i++){
    ctx.strokeStyle=`rgba(20,12,6,${0.2+Math.random()*0.3})`;
    ctx.lineWidth=1+Math.random()*2;
    const y=Math.random()*512;
    ctx.beginPath();ctx.moveTo(0,y);for(let x=0;x<256;x+=8)ctx.lineTo(x,y+Math.sin(x*0.1)*2);ctx.stroke();
  }
  const t=new THREE.CanvasTexture(c);t.wrapS=t.wrapT=THREE.RepeatWrapping;t.repeat.set(1,2);
  t.colorSpace=THREE.SRGBColorSpace;return t;
}
const barkTexture=makeBarkTexture();

function makeConcreteTexture(){
  const size=512;
  const c=document.createElement('canvas');c.width=size;c.height=size;
  const ctx=c.getContext('2d');
  ctx.fillStyle='#8a8e88';ctx.fillRect(0,0,size,size);
  const img=ctx.getImageData(0,0,size,size);
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    const i=(y*size+x)*4;
    const n=fbm(x/size*10,y/size*10,5)*22+(Math.random()-0.5)*14;
    img.data[i]=Math.min(255,Math.max(0,img.data[i]+n));
    img.data[i+1]=Math.min(255,Math.max(0,img.data[i+1]+n*0.98));
    img.data[i+2]=Math.min(255,Math.max(0,img.data[i+2]+n*0.95));
  }
  ctx.putImageData(img,0,0);
  const t=new THREE.CanvasTexture(c);t.wrapS=t.wrapT=THREE.RepeatWrapping;t.repeat.set(2,2);
  t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=4;return t;
}
const concreteTexture=makeConcreteTexture();

const shadowTex=(()=>{
  const c=document.createElement('canvas');c.width=128;c.height=128;
  const ctx=c.getContext('2d');
  const g=ctx.createRadialGradient(64,64,0,64,64,64);
  g.addColorStop(0,'rgba(0,0,0,0.55)');g.addColorStop(0.5,'rgba(0,0,0,0.22)');g.addColorStop(1,'rgba(0,0,0,0)');
  ctx.fillStyle=g;ctx.fillRect(0,0,128,128);
  const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;return t;
})();
const shadowMat=new THREE.MeshBasicMaterial({map:shadowTex,transparent:true,depthWrite:false,color:0x000000,opacity:0.8});

const woodColors=new Set(['#7a6547','#725a3f','#8a6949','#947d56','#6b4b32','#5c4528','#6b5334']);
const metalColors=new Set(['#cccccc','#a3aaa3','#435b4e','#59675c','#4f6858','#d4af37','#c9cfc9','#c9a850']);
const fabricColors=new Set(['#3d5a4a','#2a4a2a','#284e3b','#3d4a2c']);
const mats=new Map();

function mat(color,opts={}){
  const key=String(color)+JSON.stringify(opts);
  if(!mats.has(key)){
    const col=String(color).toLowerCase();
    const isMetal=metalColors.has(col);
    const isWood=woodColors.has(col);
    const isFabric=fabricColors.has(col);
    const params={
      color,map:surfaceMaps.color,roughnessMap:surfaceMaps.roughness,normalMap:surfaceMaps.normal,
      aoMap:surfaceMaps.ao,aoMapIntensity:0.75,
      roughness:isMetal?0.25:isWood?0.58:isFabric?0.85:0.68,
      metalness:isMetal?0.85:0.04,
      normalScale:new THREE.Vector2(0.4,0.4),
      envMapIntensity:isMetal?1.5:0.85
    };
    if(isWood){params.map=woodTexture;params.normalMap=woodNormal;params.normalScale=new THREE.Vector2(0.45,0.45);params.roughness=0.62;params.envMapIntensity=0.55;}
    if(isFabric){params.roughness=0.92;params.normalScale=new THREE.Vector2(0.25,0.25);}
    if(opts.clearcoat){params.clearcoat=opts.clearcoat;params.clearcoatRoughness=opts.clearcoatRoughness??0.3;}
    if(opts.roughness!=null)params.roughness=opts.roughness;
    if(opts.metalness!=null)params.metalness=opts.metalness;
    mats.set(key,new THREE.MeshStandardMaterial(params));
  }
  return mats.get(key);
}

function withAO(geo){if(geo.attributes.uv)geo.setAttribute('uv2',geo.attributes.uv.clone());return geo;}
function box(x,y,z,w,h,d,color,opts){
  const o=new THREE.Mesh(withAO(new THREE.BoxGeometry(w,h,d)),mat(color,opts));
  o.castShadow=w<=7&&h<=6&&d<=7&&Math.max(w,h,d)>0.35;
  o.receiveShadow=true;o.position.set(x,y,z);world.add(o);return o;
}
function cyl(x,y,z,r,h,color,segments=16,opts){
  const o=new THREE.Mesh(withAO(new THREE.CylinderGeometry(r,r,h,segments)),mat(color,opts));
  o.castShadow=true;o.receiveShadow=true;o.position.set(x,y,z);world.add(o);return o;
}
function ball(x,y,z,r,color,opts){
  const o=new THREE.Mesh(withAO(new THREE.SphereGeometry(r,16,14)),mat(color,opts));
  o.castShadow=true;o.receiveShadow=true;o.position.set(x,y,z);world.add(o);return o;
}
function contactShadow(x,z,w,d){
  const m=new THREE.Mesh(new THREE.PlaneGeometry(w,d),shadowMat);
  m.rotation.x=-Math.PI/2;m.position.set(x,0.008,z);world.add(m);return m;
}
function lightCone(x,y,z,radius=0.7,height=2.6){
  const geom=new THREE.ConeGeometry(radius,height,20,1,true);
  const m=new THREE.Mesh(geom,new THREE.MeshBasicMaterial({color:0xfff2cc,transparent:true,opacity:0.055,depthWrite:false,side:THREE.DoubleSide,blending:THREE.AdditiveBlending}));
  m.position.set(x,y-height/2,z);world.add(m);return m;
}

// bandeira do Brasil
function flagTexture(){
  const c=document.createElement('canvas');c.width=1024;c.height=680;
  const a=c.getContext('2d');
  a.fillStyle='#009c3b';a.fillRect(0,0,1024,680);
  a.fillStyle='#ffdf00';a.beginPath();a.moveTo(512,48);a.lineTo(960,340);a.lineTo(512,632);a.lineTo(64,340);a.closePath();a.fill();
  a.fillStyle='#002776';a.beginPath();a.arc(512,340,175,0,Math.PI*2);a.fill();
  a.save();a.translate(512,340);a.rotate(-0.18);
  a.fillStyle='#fff';a.fillRect(-185,-16,370,32);
  a.fillStyle='#002776';a.font='bold 22px Arial';a.textAlign='center';a.textBaseline='middle';
  a.fillText('ORDEM E PROGRESSO',0,2);
  a.restore();
  a.fillStyle='#fff';
  const stars=[[0,-95],[40,-70],[-40,-70],[70,-30],[-70,-30],[85,20],[-85,20],[70,70],[-70,70],[30,100],[-30,100],[0,115],[55,-50],[-55,-50],[95,0],[-95,0],[55,55],[-55,55],[0,50],[20,-20],[-20,-20],[0,0]];
  for(const [sx,sy] of stars){a.beginPath();a.arc(512+sx,340+sy,3.2,0,Math.PI*2);a.fill();}
  const img=a.getImageData(0,0,1024,680);
  for(let i=0;i<img.data.length;i+=4){const n=(Math.random()-0.5)*6;img.data[i]+=n;img.data[i+1]+=n;img.data[i+2]+=n;}
  a.putImageData(img,0,0);
  const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;
  t.generateMipmaps=true;t.minFilter=THREE.LinearMipmapLinearFilter;t.magFilter=THREE.LinearFilter;t.anisotropy=8;
  return t;
}
const flagTex=flagTexture();
const staticFlagMaterial=new THREE.MeshStandardMaterial({map:flagTex,side:THREE.DoubleSide,roughness:0.65,metalness:0.02,envMapIntensity:0.4});
const flagMaterial=new THREE.MeshStandardMaterial({map:flagTex,side:THREE.DoubleSide,roughness:0.65,metalness:0.02,envMapIntensity:0.4});
flagMaterial.onBeforeCompile=(shader)=>{
  shader.uniforms.uTime={value:0};shader.uniforms.uWind={value:1.15};
  shader.vertexShader=`uniform float uTime;uniform float uWind; ${shader.vertexShader}`.replace('#include <begin_vertex>',`
    #include <begin_vertex>
    float progress=clamp((position.x+0.9)/1.8,0.0,1.0);
    float envelope=smoothstep(0.0,0.28,progress);
    float w1=sin(progress*6.5+uTime*3.2);
    float w2=sin(progress*13.0+uTime*5.4)*0.45;
    float w3=sin(progress*3.0+position.y*5.2+uTime*2.0)*0.5;
    float gust=0.72+0.28*sin(uTime*0.75+progress*2.8);
    float displace=(w1+w2+w3)*0.095*envelope*uWind*gust;
    transformed.z+=displace;
    transformed.x+=cos(progress*5.2+uTime*2.6)*0.014*envelope*uWind;
    transformed.y+=sin(progress*4.2+uTime*1.9)*0.016*envelope*uWind;
  `);
  flagMaterial.userData.shader=shader;
};

function flag(x,z){
  const poleGeo = new THREE.CylinderGeometry(0.028,0.042,4.2,20);
  const pole = new THREE.Mesh(withAO(poleGeo), mat('#c9cfc9',{metalness:0.88,roughness:0.22}));
  pole.position.set(x,2.1,z); pole.castShadow=true; world.add(pole);
  const base = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.28,0.34,0.22,8)), mat('#3a3f3a',{metalness:0.45,roughness:0.48}));
  base.position.set(x,0.11,z); base.castShadow=true; base.receiveShadow=true; world.add(base);
  const tip = new THREE.Mesh(new THREE.ConeGeometry(0.055,0.18,12), mat('#d4af37',{metalness:0.92,roughness:0.15,clearcoat:0.5}));
  tip.position.set(x,4.28,z); tip.castShadow=true; world.add(tip);
  const geom = new THREE.PlaneGeometry(1.85,1.18,56,28);
  const mesh = new THREE.Mesh(geom, flagMaterial);
  mesh.position.set(x+0.98,3.32,z); mesh.castShadow=true; world.add(mesh);
  contactShadow(x,z,1.9,1.9);
}
function windowFrame(x,y,z,w,h,rotY=0){
  const g = new THREE.Group(); g.position.set(x,y,z); g.rotation.y=rotY;
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(w*0.96,h*0.96), new THREE.MeshPhysicalMaterial({color:0x1a3040,metalness:0.04,roughness:0.04,transmission:0.4,transparent:true,opacity:0.78,envMapIntensity:1.6,clearcoat:0.7,clearcoatRoughness:0.08,ior:1.52,thickness:0.025}));
  glass.position.z=0.02; g.add(glass);
  const fw=0.06, depth=0.1, frameMat=mat('#2a1e14',{roughness:0.62});
  for(const [px,py,bw,bh,bd] of [[0,h/2+fw/2,0,w+fw*2,fw,depth],[0,-h/2-fw/2,0,w+fw*2,fw,depth],[-w/2-fw/2,0,0,fw,h,depth],[w/2+fw/2,0,0,fw,h,depth]]){
    const m=new THREE.Mesh(withAO(new THREE.BoxGeometry(bw,bh,bd)),frameMat);m.position.set(px,py,px===0?0:0);m.position.set(px,py,0);g.add(m);
  }
  const vCross = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.028,h*0.96,0.06)), frameMat); vCross.position.z=0.03; g.add(vCross);
  const hCross = new THREE.Mesh(withAO(new THREE.BoxGeometry(w*0.96,0.028,0.06)), frameMat); hCross.position.z=0.03; g.add(hCross);
  const sill = new THREE.Mesh(withAO(new THREE.BoxGeometry(w+fw*2.4,0.04,0.14)), mat('#3a2a1c',{roughness:0.55})); sill.position.set(0,-h/2-fw-0.02,0.04); g.add(sill);
  g.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});
  world.add(g); return g;
}
function doorFrame(x,y,z,w,h,rotY=0){
  const g = new THREE.Group(); g.position.set(x,y,z); g.rotation.y=rotY;
  const panel = new THREE.Mesh(withAO(new THREE.BoxGeometry(w,h,0.075)), mat('#4a3420')); panel.position.z=0.038; g.add(panel);
  const fw=0.08, frameMat=mat('#2a1e14',{roughness:0.58});
  for(const [px,py,bw,bh] of [[0,h/2+fw/2,w+fw*2,fw],[-w/2-fw/2,0,fw,h],[w/2+fw/2,0,fw,h]]){
    const m = new THREE.Mesh(withAO(new THREE.BoxGeometry(bw,bh,0.12)), frameMat); m.position.set(px,py,0); g.add(m);
  }
  g.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});
  world.add(g); return g;
}
function table(x,z){
  const g=new THREE.Group(); g.position.set(x,0,z);
  const top=new THREE.Mesh(withAO(new THREE.BoxGeometry(1.7,0.06,0.92)),mat('#7a6547')); top.position.y=0.84; top.castShadow=true; top.receiveShadow=true; g.add(top);
  const apron=new THREE.Mesh(withAO(new THREE.BoxGeometry(1.55,0.08,0.78)),mat('#6b5334')); apron.position.y=0.74; g.add(apron);
  for(const dx of [-0.68,0.68]) for(const dz of [-0.34,0.34]){
    const leg=new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.022,0.035,0.72,14)),mat('#4a5248',{metalness:0.55,roughness:0.32}));
    leg.position.set(dx,0.38,dz); leg.castShadow=true; g.add(leg);
  }
  g.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});
  world.add(g); contactShadow(x,z,2.4,1.5);
}
function tree(x,z){
  const trunkMat=new THREE.MeshStandardMaterial({map:barkTexture,roughness:0.94,metalness:0,color:0xffffff});
  const trunk=new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.1,0.2,2.6,16)),trunkMat);
  trunk.position.set(x,1.3,z); trunk.castShadow=true; world.add(trunk);
  const folColors=[0x2a5034,0x356a40,0x457a4e,0x2e6040,0x3d7048,0x285838,0x3a6844];
  for(let layer=0;layer<3;layer++){
    for(let i=0;i<8;i++){
      const angle=i/8*Math.PI*2+layer*0.4;
      const radius=0.25+layer*0.2+Math.random()*0.2;
      const size=0.38+Math.random()*0.28-layer*0.05;
      const crown=new THREE.Mesh(withAO(new THREE.SphereGeometry(size,12,10)),new THREE.MeshStandardMaterial({color:folColors[(i+layer)%7],roughness:0.88,metalness:0}));
      crown.position.set(x+Math.cos(angle)*radius,3.1+layer*0.55+(Math.random()-0.3)*0.3,z+Math.sin(angle)*radius);
      crown.castShadow=true; world.add(crown);
    }
  }
  contactShadow(x,z,2.2,2.2);
}
function building(x,z){
  const body=new THREE.Mesh(withAO(new THREE.BoxGeometry(5.4,4.3,3.4)),new THREE.MeshStandardMaterial({map:concreteTexture,color:0x8a948c,roughness:0.86,metalness:0.04,normalMap:surfaceMaps.normal,normalScale:new THREE.Vector2(0.14,0.14)}));
  body.position.set(x,2.15,z); body.castShadow=true; body.receiveShadow=true; world.add(body);
  box(x,4.4,z,5.9,0.28,3.8,'#4a564e',{roughness:0.72});
  windowFrame(x-1.4,2.35,z+1.72,0.88,1.2);
  windowFrame(x,2.35,z+1.72,0.88,1.2);
  windowFrame(x+1.4,2.35,z+1.72,0.88,1.2);
  doorFrame(x,1.25,z+1.73,1.1,2.1);
  contactShadow(x,z+0.5,6.4,4.4);
}
function bunk(x,z){
  const g=new THREE.Group(); g.position.set(x,0,z);
  for(const y of [0.45,1.5]){
    const frame=new THREE.Mesh(withAO(new THREE.BoxGeometry(1.8,0.06,2.25)),mat('#5a6e6a',{metalness:0.35,roughness:0.5}));
    frame.position.y=y; g.add(frame);
    const mattress=new THREE.Mesh(withAO(new THREE.BoxGeometry(1.65,0.12,2.05)),mat('#3d5a4a',{roughness:0.9}));
    mattress.position.y=y+0.12; g.add(mattress);
  }
  for(const dx of [-0.82,0.82]) for(const dz of [-1.05,1.05]){
    const post=new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.028,0.028,2.15,12)),mat('#a0a8a0',{metalness:0.6,roughness:0.32}));
    post.position.set(dx,1.08,dz); g.add(post);
  }
  g.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});
  world.add(g); contactShadow(x,z,2.4,2.8);
}
function standingFlag(x,z){
  const base=new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.3,0.36,0.08,8)),mat('#2a1e14',{roughness:0.55}));
  base.position.set(x,0.04,z); world.add(base);
  const pole=new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.018,0.024,2.85,14)),mat('#c9cfc9',{metalness:0.85,roughness:0.22}));
  pole.position.set(x,1.45,z); world.add(pole);
  const miniFlag=new THREE.Mesh(new THREE.PlaneGeometry(0.68,0.44),staticFlagMaterial);
  miniFlag.position.set(x+0.36,2.4,z); world.add(miniFlag);
  contactShadow(x,z,1.15,1.15);
}
function militaryPoster(x,y,z,rotY=0){
  const g=new THREE.Group(); g.position.set(x,y,z); g.rotation.y=rotY;
  const poster=new THREE.Mesh(new THREE.PlaneGeometry(0.98,1.4),new THREE.MeshStandardMaterial({color:0x1e3a22,roughness:0.78}));
  g.add(poster); world.add(g); return g;
}
function auditoriumChair(x,z,rotY=0){
  const g=new THREE.Group(); g.position.set(x,0,z); g.rotation.y=rotY;
  const seat=new THREE.Mesh(withAO(new THREE.BoxGeometry(0.56,0.06,0.5)),mat('#3d5a4a',{roughness:0.88}));
  seat.position.set(0,0.48,0.02); g.add(seat);
  const back=new THREE.Mesh(withAO(new THREE.BoxGeometry(0.56,0.35,0.06)),mat('#3d5a4a',{roughness:0.88}));
  back.position.set(0,0.72,-0.22); g.add(back);
  g.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});
  world.add(g); return g;
}
function potPlant(x,y,z){
  const pot=new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.18,0.14,0.32,20)),mat('#7a3a22',{roughness:0.72}));
  pot.position.set(x,y+0.16,z); world.add(pot);
  contactShadow(x,z,0.75,0.75);
}
function ceilingLamp(x,y,z){
  const light=new THREE.PointLight(0xfff0c0,0.42,5.5,2);
  light.position.set(x,y,z); world.add(light);
}
function wallPicture(x,y,z,w,h,rotY=0,color='#3a2a1c'){
  const frame=new THREE.Mesh(withAO(new THREE.BoxGeometry(w,h,0.05)),mat(color,{roughness:0.5}));
  frame.position.set(x,y,z); frame.rotation.y=rotY; world.add(frame);
}
function wallClock(x,y,z){
  const g=new THREE.Group(); g.position.set(x,y,z);
  const face=new THREE.Mesh(new THREE.CircleGeometry(0.32,48),mat('#f5f0e6',{roughness:0.35})); g.add(face);
  world.add(g); return g;
}
function baseboard(x,y,z,w,d,rotY=0){
  const b=new THREE.Mesh(withAO(new THREE.BoxGeometry(w,0.14,0.05)),mat('#2a1e14',{roughness:0.58}));
  b.position.set(x,y,z); b.rotation.y=rotY; world.add(b);
}
function crownMolding(x,y,z,w,rotY=0){
  const b=new THREE.Mesh(withAO(new THREE.BoxGeometry(w,0.16,0.09)),mat('#2a1e14',{roughness:0.52}));
  b.position.set(x,y,z); b.rotation.y=rotY; world.add(b);
}
function makeRoom(){
  const floorMat=new THREE.MeshStandardMaterial({map:floorTexture,roughness:0.7,metalness:0.04,normalMap:floorNormal,normalScale:new THREE.Vector2(0.3,0.3),envMapIntensity:0.38});
  const floor=new THREE.Mesh(withAO(new THREE.PlaneGeometry(26,28)),floorMat);
  floor.rotation.x=-Math.PI/2; floor.position.set(0,0,-1); floor.receiveShadow=true; world.add(floor);
  const wallMat=new THREE.MeshStandardMaterial({map:wallTexture,color:0xffffff,roughness:0.88,metalness:0.02,normalMap:surfaceMaps.normal,normalScale:new THREE.Vector2(0.1,0.1)});
  function wall(wx,wy,wz,ww,wh,wd){
    const m=new THREE.Mesh(withAO(new THREE.BoxGeometry(ww,wh,wd)),wallMat);
    m.position.set(wx,wy,wz); m.castShadow=true; m.receiveShadow=true; world.add(m);
  }
  wall(0,2.95,-11.25,24.6,5.9,0.3);
  wall(-12.05,2.95,-1,0.3,5.9,22.6);
  wall(12.05,2.95,-1,0.3,5.9,22.6);
  box(0,5.98,-1,24.6,0.28,22.6,'#6a7a70',{roughness:0.82});
  baseboard(0,0.07,-11.08,24.2,0.05);
  crownMolding(0,5.8,-11.08,24.2);
  wallPicture(-4.3,2.95,-11.08,1.55,1.05);
  wallPicture(4.3,2.95,-11.08,1.55,1.05);
  wallClock(0,4.75,-11.08);
  potPlant(-10.9,0,-9.3);
  potPlant(10.9,0,-9.3);
  doorFrame(-11.88,1.3,-6.3,1.15,2.35,Math.PI/2);
  doorFrame(11.88,1.3,-6.3,1.15,2.35,-Math.PI/2);
  windowFrame(11.88,2.55,3.3,1.35,1.75,-Math.PI/2);
  ceilingLamp(-4.3,5.65,-4.3);
  ceilingLamp(4.3,5.65,-4.3);
  ceilingLamp(0,5.65,-1);
  standingFlag(-9.9,-3.9);
  standingFlag(9.9,-3.9);
}

let soldiers=[];
function makeSoldier(x,z){return {group:new THREE.Group(),phase:Math.random()*Math.PI*2};}
function spawnSoldiers(n){soldiers=[];}
function updateSoldiers(dt,time){}

// =====================================================
// TREINO DE TIRO
// =====================================================
let shootMode=false;
let targets=[];
let scoreShoot={hits:0,shots:0};
function clearTargets(){for(const t of targets){world.remove(t.mesh);}targets=[];}
function spawnTargets(){clearTargets();note('Treino de tiro: dispara com gatilho');}
function toggleShootMode(){shootMode=!shootMode;if(shootMode)spawnTargets();else clearTargets();updateVR();}
function fireFromController(controller){
  if(!shootMode||!renderer.xr.isPresenting)return;
  const ray=rayFromController(controller);
  if(!ray)return;
  try{initAudio();resumeAudio();if(audioCtx){const t0=audioCtx.currentTime;playSpatialNote(180,t0,0.08,0.25,ray.origin);}}catch(e){}
}

function buildWorld(n){
  if(_buildingWorld)return;
  _buildingWorld=true;
  try{
    world.traverse(o=>{if(o.isMesh){if(o.geometry)o.geometry.dispose();}});
    world.clear();
    if(n!==3)makeRoom();
    else{
      const groundMat=new THREE.MeshStandardMaterial({map:grassTexture,roughness:0.88,metalness:0.03,normalMap:surfaceMaps.normal,normalScale:new THREE.Vector2(0.15,0.15)});
      const ground=new THREE.Mesh(withAO(new THREE.PlaneGeometry(75,75,24,24)),groundMat);
      ground.rotation.x=-Math.PI/2;ground.position.set(0,-0.01,-1);ground.receiveShadow=true;
      world.add(ground);
      for(let i=0;i<16;i++)tree(-32+Math.random()*64,-16-Math.random()*28);
    }
    flag(-8.2,-9.2);
    flag(8.2,-9.2);
    if(n===0){building(0,-8.2);}
    if(n===4){for(let x=-6;x<=6;x+=3.2){bunk(x,-6.2);bunk(x,0.2);}}
    if(n===6){for(let z=-6.2;z<=1.2;z+=1.45)for(let x=-5.2;x<=5.2;x+=1.45)auditoriumChair(x,z);}
    spawnSoldiers(n);
    applyLight();
    renderer.shadowMap.needsUpdate=true;
  }catch(e){console.warn("buildWorld",e);}finally{_buildingWorld=false;}
}

function applyLight(){
  const night=state.settings.lighting==='night';
  ambient.intensity=night?0.7:1.25;
  ambient.color.setHex(night?0x4a5a90:0xe2eef8);
  sun.intensity=night?0.55:2.9;
  sun.color.setHex(night?0xa0b4e0:0xfff0d2);
  sun.position.set(9,15,7);
  if(sun.target){sun.target.position.set(0,0,-1);sun.target.updateMatrixWorld();}
  fill.intensity=night?0.2:0.55;
  rim.intensity=night?0.28:0.65;
  if(typeof bounce!=='undefined'&&bounce)bounce.intensity=night?0.12:0.32;
  if(typeof vrAmbientBoost!=='undefined')vrAmbientBoost.intensity=night?0.25:0.35;
  try{scene.environment=night?iblNightTarget.texture:iblDayTarget.texture;}catch(e){}
  scene.background=new THREE.Color(night?0x0b1220:0x7eabba);
  renderer.toneMappingExposure=night?1.18:1.3;
  if(skyMesh?.material?.uniforms){
    skyMesh.material.uniforms.uNight.value=night?1.0:0.0;
    skyMesh.material.uniforms.uIntensity.value=night?0.75:1.2;
  }
  renderer.shadowMap.needsUpdate=true;
}

// =====================================================
// ✅ PAINÉIS VR — 4K
// Coordenadas lógicas 2048×1536, canvas real 4096×3072
// =====================================================
const WIDTH=LOGICAL_W, HEIGHT=LOGICAL_H;   // espaço lógico para desenho
const panels={};
const panelMeshes=[];
const raycaster=new THREE.Raycaster();
const tmpMatrix=new THREE.Matrix4();
let hovered=null;
let _drawingPanels=false, _buildingWorld=false, _updatingVR=false;

function refreshPanelTexture(p){
  if(!p||!p.texture)return;
  p.texture.needsUpdate=true;
}

function makePanel(id,w,h,x,y,z){
  const canvas=document.createElement('canvas');
  // ✅ 4K: canvas real em 4096×3072 (PIXEL_SCALE=2)
  canvas.width = WIDTH * PIXEL_SCALE;
  canvas.height = HEIGHT * PIXEL_SCALE;

  // Aviso de memória (opcional)
  if(id==='main'){
    console.log(`[PMSC] Canvas ${canvas.width}×${canvas.height} (${(canvas.width*canvas.height*4/1048576).toFixed(1)}MB/panel)`);
  }

  const ctx = canvas.getContext('2d',{alpha:false,desynchronized:true});
  // ✅ IMPORTANTE: escala o contexto para que desenho aconteça em 2048×1536
  // e o canvas físico fique 4K. Todos os números do layout continuam válidos.
  ctx.setTransform(PIXEL_SCALE, 0, 0, PIXEL_SCALE, 0, 0);

  // placeholder inicial
  ctx.fillStyle='#f0faf4';
  ctx.fillRect(0,0,WIDTH,HEIGHT);
  ctx.fillStyle='#0d3d24';
  ctx.font='bold 48px Arial';
  ctx.fillText('PMSC 2026 · 4K', 48, 80);
  ctx.font='32px Arial';
  ctx.fillStyle='#1a5a38';
  ctx.fillText('Painel: '+id, 48, 130);

  const texture=new THREE.CanvasTexture(canvas);
  texture.colorSpace=THREE.SRGBColorSpace;
  texture.generateMipmaps=false;
  texture.minFilter=THREE.LinearFilter;
  texture.magFilter=THREE.LinearFilter;
  texture.anisotropy=1;
  texture.needsUpdate=true;

  const group=new THREE.Group();
  group.position.set(x,y,z);
  rig.add(group);   // parent no rig: HUD relativo à cabeça

  const back=new THREE.Mesh(
    new THREE.PlaneGeometry(w+0.08,h+0.08),
    new THREE.MeshBasicMaterial({color:0x0d3d24, side:THREE.DoubleSide, toneMapped:false})
  );
  back.position.z=-0.012;
  back.frustumCulled=false;
  back.renderOrder=5;
  group.add(back);

  const mat=new THREE.MeshBasicMaterial({
    map:texture, color:0xffffff, side:THREE.DoubleSide,
    toneMapped:false, depthTest:true, depthWrite:true
  });
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(w,h), mat);
  mesh.frustumCulled=false;
  mesh.renderOrder=10;
  group.add(mesh);

  panels[id]={id,canvas,ctx,texture,group,mesh,mat,regions:[],w,h};
  panelMeshes.push(mesh);
  mesh.userData.id=id;
}

function placePanelsForUser(){
  try{
    const dist=Number(state.settings.distance)||2.4;
    const sc=Number(state.settings.panelScale)||1;
    if(panels.main){
      const saved=state.panels?.main;
      if(saved&&saved.length===3) panels.main.group.position.set(saved[0],saved[1],saved[2]);
      else panels.main.group.position.set(0, 1.35, -dist);
      panels.main.group.rotation.set(0,0,0);
      panels.main.group.scale.setScalar(sc);
    }
    if(panels.left){
      const saved=state.panels?.left;
      if(saved&&saved.length===3) panels.left.group.position.set(saved[0],saved[1],saved[2]);
      else panels.left.group.position.set(-2.0, 1.35, -dist-0.2);
      panels.left.group.rotation.set(0, 0.32, 0);
      panels.left.group.scale.setScalar(sc*0.9);
    }
    if(panels.right){
      const saved=state.panels?.right;
      if(saved&&saved.length===3) panels.right.group.position.set(saved[0],saved[1],saved[2]);
      else panels.right.group.position.set(2.0, 1.35, -dist-0.2);
      panels.right.group.rotation.set(0, -0.32, 0);
      panels.right.group.scale.setScalar(sc*0.9);
    }
  }catch(e){console.warn('placePanels',e);}
}

function forceRedrawPanels(){
  try{
    placePanelsForUser();
    if(typeof drawMain==='function') drawMain();
    if(typeof drawSide==='function'){drawSide('left');drawSide('right');}
    for(const id of ['main','left','right']){
      const p=panels[id];
      if(!p)continue;
      if(p.texture) p.texture.needsUpdate=true;
      if(p.mat) p.mat.needsUpdate=true;
    }
  }catch(e){console.warn('forceRedrawPanels',e);}
}

makePanel('main',3.2,2.4,0,1.35,-2.4);
makePanel('left',1.6,2.0,-2.0,1.35,-2.6);
makePanel('right',1.6,2.0,2.0,1.35,-2.6);

function panelPositionReset(){
  panels.main.group.position.set(0,1.35,-Number(state.settings.distance||2.4));
  panels.main.group.scale.setScalar(Number(state.settings.panelScale));
  panels.left.group.position.set(-2.0,1.35,-2.6);
  panels.right.group.position.set(2.0,1.35,-2.6);
  for(const p of Object.values(panels))p.group.rotation.set(0,0,0);
}
function resetPanelPositions(){state.panels={};panelPositionReset();safeStore();updateVR();}
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));

function round(ctx,x,y,w,h,r=16){
  const rr=Math.min(r,w/2,h/2);
  ctx.beginPath();
  if(typeof ctx.roundRect==='function'){ctx.roundRect(x,y,w,h,rr);return;}
  ctx.moveTo(x+rr,y);
  ctx.arcTo(x+w,y,x+w,y+h,rr);
  ctx.arcTo(x+w,y+h,x,y+h,rr);
  ctx.arcTo(x,y+h,x,y,rr);
  ctx.arcTo(x,y,x+w,y,rr);
  ctx.closePath();
}
function text(ctx,t,x,y,size=46,color='#0a2a18',weight='700'){
  const str=String(t??'');
  ctx.font=`${weight} ${size}px Arial,Helvetica,sans-serif`;
  ctx.textBaseline='alphabetic';
  ctx.imageSmoothingEnabled=true;
  ctx.imageSmoothingQuality='high';
  ctx.fillStyle='rgba(0,0,0,0.2)';
  ctx.fillText(str, x+1.5, y+1.5);
  ctx.fillStyle=color;
  ctx.fillText(str, x, y);
}
function wrapped(ctx,content,width,size){
  ctx.font=`700 ${size}px Arial,sans-serif`;
  const lines=[];
  const maxW=Math.max(40, width||100);
  const parts=String(content||'').split('\n');
  for(const paragraph of parts){
    let line='';
    const words=paragraph.split(/\s+/).filter(Boolean);
    if(!words.length){lines.push('');continue;}
    for(const word of words){
      const test=line?(line+' '+word):word;
      if(line && ctx.measureText(test).width>maxW){
        lines.push(line);line=word;
        if(lines.length>80)return lines;
      }else line=test;
    }
    lines.push(line);
    if(lines.length>80)return lines;
  }
  return lines;
}
function region(p,x,y,w,h,action){p.regions.push({x,y,w,h,action});}

function background(p,title){
  const c=p.ctx; p.regions=[];
  // ✅ 4K: garante transform 2x mesmo se algo resetou o estado
  try{ if(typeof c.reset==='function') c.reset(); }catch(e){}
  c.setTransform(PIXEL_SCALE, 0, 0, PIXEL_SCALE, 0, 0);
  c.imageSmoothingEnabled=true;
  c.imageSmoothingQuality='high';
  const bg=c.createLinearGradient(0,0,0,HEIGHT);
  bg.addColorStop(0,'#f4fbf7'); bg.addColorStop(0.55,'#eaf6ef'); bg.addColorStop(1,'#dcefe4');
  c.fillStyle=bg; c.fillRect(0,0,WIDTH,HEIGHT);
  const hg=c.createLinearGradient(0,0,WIDTH,0);
  hg.addColorStop(0,'#0f4a32'); hg.addColorStop(0.5,'#1a6b48'); hg.addColorStop(1,'#0f4a32');
  c.fillStyle=hg;
  round(c,20,16,WIDTH-40,100,18); c.fill();
  c.fillStyle='rgba(125,255,176,0.95)';
  round(c,20,112,WIDTH-40,5,3); c.fill();
  text(c,title,44,62,42,'#f7fff9','800');
  text(c,'Grip arrasta  ·  Gatilho seleciona  ·  Analógico move',44,96,22,'#b8efd0','500');
  c.strokeStyle='rgba(20,100,60,0.35)'; c.lineWidth=3;
  round(c,10,10,WIDTH-20,HEIGHT-20,22); c.stroke();
  c.strokeStyle='rgba(255,255,255,0.45)'; c.lineWidth=1.5;
  round(c,14,14,WIDTH-28,HEIGHT-28,18); c.stroke();
  region(p,0,0,WIDTH,120,'drag');
}

function vrButton(p,label,x,y,w,h,action,color='#1a5c3e',size=36){
  const c=p.ctx;
  const hot=hovered?.panel===p.id && hovered?.action===action;
  c.fillStyle='rgba(0,0,0,0.18)';
  round(c,x+2,y+3,w,h,14); c.fill();
  if(hot){
    const g=c.createLinearGradient(x,y,x,y+h);
    g.addColorStop(0,'#3dba78'); g.addColorStop(1,'#1e7a4c');
    c.fillStyle=g;
  } else c.fillStyle=color;
  round(c,x,y,w,h,14); c.fill();
  c.strokeStyle=hot?'#ffffff':'rgba(255,255,255,0.28)';
  c.lineWidth=hot?3:1.5;
  round(c,x,y,w,h,14); c.stroke();
  c.fillStyle='rgba(255,255,255,0.14)';
  round(c,x+3,y+3,w-6,Math.min(22,h*0.3),10); c.fill();
  const lines=wrapped(c,label,w-36,size);
  lines.slice(0,2).forEach((line,i)=>text(c,line,x+18,y+Math.min(h-12, 36+i*(size+2)),size,'#ffffff','700'));
  region(p,x,y,w,h,action);
}

function drawOptionCard(p, letter, textContent, x, y, w, h, action, state){
  const c=p.ctx;
  const hot=hovered?.panel===p.id && hovered?.action===action;
  let bg='#ffffff', border='rgba(15,80,50,0.28)', letterBg='#157a4a', letterCol='#ffffff';
  if(state==='selected'){ bg='#e3f1ff'; border='#2a7fd4'; letterBg='#1a5f9e'; }
  if(state==='correct'){ bg='#e0f8ea'; border='#1a9a55'; letterBg='#0f7a40'; }
  if(state==='wrong'){ bg='#ffe8eb'; border='#d44555'; letterBg='#a03040'; }
  if(hot && state==='idle'){ bg='#e8f8f0'; border='#1a9a55'; }
  c.fillStyle='rgba(0,0,0,0.12)';
  round(c,x+3,y+4,w,h,16); c.fill();
  c.fillStyle=bg;
  round(c,x,y,w,h,16); c.fill();
  c.strokeStyle=border; c.lineWidth=hot?3.5:2;
  round(c,x,y,w,h,16); c.stroke();
  const bw=Math.min(78,h-16), bh=bw;
  c.fillStyle=letterBg;
  round(c,x+14,y+(h-bh)/2,bw,bh,12); c.fill();
  text(c,letter,x+14+bw/2-16,y+h/2+16,44,letterCol,'800');
  const lines=wrapped(c,textContent,w-bw-50,34);
  let ty=y+Math.max(32,(h-lines.length*40)/2+28);
  for(const line of lines.slice(0,4)){
    text(c,line,x+bw+28,ty,34,'#0c2a1a','600');
    ty+=40;
  }
  region(p,x,y,w,h,action);
}

function drawMain(){
  if(_drawingPanels)return;
  _drawingPanels=true;
  try{
    const p=panels.main, c=p.ctx, s=state.session, q=currentQuestion(), a=currentPool();
    background(p,'PMSC 2026  ·  SALA DE ESTUDO  ·  4K');
    if(!q){
      text(c,'AGUARDANDO QUESTÕES',80,420,56,'#0a2a18','700');
      text(c,'Atualize o banco JSON no menu lateral ou use Demonstração.',80,500,36,'#3a5a4a','500');
      refreshPanelTexture(p); return;
    }

    const pct=Math.round(((s.index+1)/Math.max(1,a.length))*100);
    c.fillStyle='rgba(15,40,30,0.85)';
    round(c,24,108,WIDTH-48,56,10); c.fill();
    text(c,`${s.index+1}  /  ${a.length}`,36,145,28,'#145a3a','700');
    text(c,q.subject,160,138,24,'#0a2a18','700');
    text(c,q.topic,160,158,18,'#3a5a4a','600');
    c.fillStyle='#1a3a2a'; round(c,WIDTH-280,130,220,14,7); c.fill();
    c.fillStyle='#4dff9a'; round(c,WIDTH-280,130,Math.max(10,220*pct/100),14,7); c.fill();
    text(c,pct+'%',WIDTH-50,142,18,'#145a3a','700');

    const size=Math.round(40*Number(state.settings.fontSize)/120);
    const lineH=size*1.42;
    const blocks=[];
    const addQ=(content)=>{
      const lines=wrapped(c,content,WIDTH-140,size);
      blocks.push({kind:'question',lines,height:Math.max(100, lines.length*(lineH+4)+36)});
    };
    const addNote=(content)=>{
      const lines=wrapped(c,content,WIDTH-140,size-4);
      blocks.push({kind:'note',lines,height:Math.max(70, lines.length*(lineH)+28)});
    };
    addQ(q.question);

    if(s.mode==='flash'){
      if(s.flip){
        addNote('RESPOSTA: '+q.options[q.correct]);
        if(q.explanation) addNote(q.explanation);
      } else {
        addNote('Toque em VIRAR para revelar a resposta do flashcard.');
      }
    } else {
      q.options.forEach((option,i)=>{
        const chosen=s.answers[q.id];
        const reveal=s.mode!=='exam'||s.feedback==='immediate'||s.finished;
        let st='idle';
        if(chosen!==undefined&&reveal){
          if(i===q.correct) st='correct';
          else if(i===chosen) st='wrong';
        } else if(chosen===i) st='selected';
        const lines=wrapped(c,option,WIDTH-280,38);
        const oh=Math.max(96, lines.length*44+28);
        blocks.push({kind:'option',i,option,st,height:oh+12});
      });
      const chosen=s.answers[q.id];
      if(chosen!==undefined&&(s.mode!=='exam'||s.feedback==='immediate'||s.finished)){
        if(q.explanation) addNote('COMENTÁRIO: '+q.explanation);
        if(q.reference) addNote('REFERÊNCIA: '+q.reference);
      }
    }

    const viewTop=180, viewBottom=HEIGHT-250, viewH=viewBottom-viewTop;
    const total=blocks.reduce((sum,b)=>sum+b.height+10,0);
    s.scroll=clamp(s.scroll,0,Math.max(0,total-viewH));
    c.save();
    try{
      c.beginPath(); c.rect(36,viewTop,WIDTH-72,viewH); c.clip();
      let y=viewTop - s.scroll;
      for(const b of blocks){
        if(y+b.height >= viewTop-20 && y <= viewBottom+20){
          if(b.kind==='question'){
            c.fillStyle='#ffffff';
            round(c,48,y,WIDTH-96,b.height-8,16); c.fill();
            c.strokeStyle='rgba(20,100,60,0.35)'; c.lineWidth=2;
            round(c,48,y,WIDTH-96,b.height-8,16); c.stroke();
            text(c,'ENUNCIADO',64,y+32,22,'#1a7048','700');
            let ty=y+70;
            for(const line of b.lines){
              text(c,line,64,ty,size,'#0a2a18','700');
              ty+=lineH+4;
            }
          } else if(b.kind==='option'){
            const letter=String.fromCharCode(65+b.i);
            drawOptionCard(p,letter,b.option,48,y,WIDTH-96,b.height-10,'answer:'+b.i,b.st);
          } else if(b.kind==='note'){
            c.fillStyle='rgba(230,245,236,0.9)';
            round(c,48,y,WIDTH-96,b.height-8,12); c.fill();
            let ty=y+40;
            for(const line of b.lines){
              text(c,line,64,ty,size-4,'#0a3a20','600');
              ty+=lineH;
            }
          }
        }
        y += b.height+10;
      }
    } finally {
      c.restore();
    }

    c.fillStyle='#d0e8da';
    c.fillRect(20,HEIGHT-240,WIDTH-40,220);
    c.fillStyle='#1a7048'; c.fillRect(20,HEIGHT-240,WIDTH-40,3);

    const bw=Math.floor(WIDTH*0.14), bh=Math.floor(HEIGHT*0.07), gap=12, baseY=HEIGHT-210;
    let bx=50;
    vrButton(p,'▲ SUBIR',bx,baseY,bw,bh,'scrollUp','#1a4a35',36); bx+=bw+gap;
    vrButton(p,'▼ DESCER',bx,baseY,bw,bh,'scrollDown','#1a4a35',36); bx+=bw+gap;
    vrButton(p,'◀ ANTERIOR',bx,baseY,bw,bh,'prev','#1e3a55',36); bx+=bw+gap;
    vrButton(p,'PRÓXIMA ▶',bx,baseY,bw,bh,'next','#1e5540',36); bx+=bw+gap;
    const lastLabel = s.mode==='flash' ? 'VIRAR' : s.mode==='exam' ? 'FINALIZAR' : '★ FAVORITO';
    const lastAct   = s.mode==='flash' ? 'flip' : s.mode==='exam' ? 'finish' : 'favorite';
    vrButton(p,lastLabel,bx,baseY,WIDTH-bx-50,bh,lastAct,s.mode==='exam'?'#5a3020':'#1a5c3e',36);

    const footer = s.mode==='exam'&&s.minutes
      ? `TEMPO: ${Math.max(0,Math.ceil((s.minutes*60000-(Date.now()-s.start))/60000))} min  ·  SIMULADO`
      : s.mode==='flash' ? 'MODO FLASHCARD' : s.mode==='exam' ? 'MODO SIMULADO' : 'MODO ESTUDO';
    text(c,footer,40,HEIGHT-30,22,'#1a4a35','600');
    refreshPanelTexture(p);
  }catch(e){console.warn('drawMain',e);}
  finally{_drawingPanels=false;}
}

function drawSide(id){
  const p=panels[id], c=p.ctx;
  background(p, id==='left' ? 'AMBIENTES 3D' : 'DESEMPENHO');
  if(id==='left'){
    let y=160;
    environments.forEach((name,i)=>{
      const active=i===state.settings.env;
      vrButton(p, `${String(i+1).padStart(2,'0')}  ·  ${name}`, 40, y, WIDTH-80, 78, 'env:'+i, active?'#1e7048':'#1a4a35', 30);
      y+=90;
    });
    vrButton(p,'REPOSICIONAR PAINÉIS',40,HEIGHT-130,WIDTH-80,90,'resetPanels','#1a3a55',30);
  } else {
    const z=stats();
    const cards=[
      ['QUESTÕES', String(questions.length)],
      ['RESPONDIDAS', String(z.total)],
      ['ACERTOS', String(z.ok)],
      ['APROVEITAMENTO', z.pct+'%'],
      ['REVISÕES', String(z.pending)],
      ['SIMULADOS', String(z.exams)]
    ];
    let y=160;
    for(let i=0;i<cards.length;i+=2){
      for(let j=0;j<2;j++){
        if(!cards[i+j])continue;
        const [lab,val]=cards[i+j];
        const x=40+j*((WIDTH-100)/2+20);
        const w=(WIDTH-100)/2;
        c.fillStyle='#ffffff';
        round(c,x,y,w,110,16); c.fill();
        c.strokeStyle='rgba(20,100,60,0.3)'; c.lineWidth=2;
        round(c,x,y,w,110,16); c.stroke();
        text(c,val,x+24,y+62,36,'#145a3a','800');
        text(c,lab,x+24,y+96,18,'#3a5a4a','600');
      }
      y+=130;
    }
    const modes=[['QUESTÕES','study'],['SIMULADO','exam'],['FLASHCARDS','flash'],['REVISÃO','review']];
    y=HEIGHT-480;
    modes.forEach(([name,mode],i)=>{
      vrButton(p,name,40,y+i*105,WIDTH-80,92,'go:'+mode,'#1a4a35',30);
    });
  }
  refreshPanelTexture(p);
}

function updateVR(){
  if(!panels.main||_updatingVR||_drawingPanels)return;
  _updatingVR=true;
  try{drawMain();drawSide('left');drawSide('right');}
  catch(e){console.warn('updateVR',e);}
  finally{_updatingVR=false;}
}
function scrollVR(delta){const s=state.session;if(!s)return;s.scroll=Math.max(0,s.scroll+delta);updateVR();}

let lastActionTime=0,lastActionName='';
function action(act){
  if(!act)return;
  const t=performance.now();
  if(lastActionName===act&&t-lastActionTime<270)return;
  lastActionTime=t;lastActionName=act;
  if(act==='drag')return;
  if(act.startsWith('answer:'))return choose(+act.split(':')[1]);
  if(act.startsWith('env:'))return setEnvironment(+act.split(':')[1]);
  if(act.startsWith('go:'))return go(act.split(':')[1]);
  if(act==='prev')return next(-1);
  if(act==='next')return next(1);
  if(act==='flip'){if(state.session){state.session.flip=!state.session.flip;safeStore();render();}return;}
  if(act==='favorite')return favorite();
  if(act==='finish')return finishExam();
  if(act==='scrollUp')return scrollVR(-430);
  if(act==='scrollDown')return scrollVR(430);
  if(act==='resetPanels')return resetPanelPositions();
}

function intersectFrom(origin,direction){
  raycaster.set(origin,direction);
  const hit=raycaster.intersectObjects(panelMeshes,false)[0];
  if(!hit||hit.distance>10)return null;
  const p=panels[hit.object.userData.id];if(!p)return null;
  const x=hit.uv.x*WIDTH,y=(1-hit.uv.y)*HEIGHT;
  const region=[...p.regions].reverse().find(v=>x>=v.x&&x<=v.x+v.w&&y>=v.y&&y<=v.y+v.h);
  return {p,hit,region:region||null};
}
function rayFromController(controller){
  controller.updateWorldMatrix(true,false);
  tmpMatrix.extractRotation(controller.matrixWorld);
  const origin=new THREE.Vector3().setFromMatrixPosition(controller.matrixWorld);
  const direction=new THREE.Vector3(0,0,-1).applyMatrix4(tmpMatrix).normalize();
  return {origin,direction};
}
function rayFromHand(hand){
  const a=hand.joints?.['index-finger-tip'];
  const b=hand.joints?.['index-finger-phalanx-proximal']||hand.joints?.wrist;
  if(!a||!b)return null;
  a.updateWorldMatrix(true,false);b.updateWorldMatrix(true,false);
  const origin=new THREE.Vector3().setFromMatrixPosition(a.matrixWorld);
  const base=new THREE.Vector3().setFromMatrixPosition(b.matrixWorld);
  const direction=origin.clone().sub(base).normalize();
  return {origin,direction};
}
function handTouchHit(hand){
  const tip=hand.joints?.['index-finger-tip'];if(!tip)return null;
  const worldPoint=new THREE.Vector3();tip.getWorldPosition(worldPoint);
  for(const p of Object.values(panels)){
    const local=p.group.worldToLocal(worldPoint.clone());
    const px=local.x/(p.w*p.group.scale.x)+0.5,py=0.5-local.y/(p.h*p.group.scale.y);
    if(Math.abs(local.z)<0.18&&px>=0&&px<=1&&py>=0&&py<=1){
      const x=px*WIDTH,y=py*HEIGHT;
      const region=[...p.regions].reverse().find(r=>x>=r.x&&x<=r.x+r.w&&y>=r.y&&y<=r.y+r.h);
      return {p,region};
    }
  }
  return null;
}

const controllerFactory=new XRControllerModelFactory();
const handFactory=new XRHandModelFactory();
const controllers=[],hands=[];
let dragging=null;

function beginDrag(p,source,kind,index=0){
  const start=new THREE.Vector3();
  source.getWorldPosition(start);
  const panelWorld=new THREE.Vector3();
  p.group.getWorldPosition(panelWorld);
  dragging={p,source,kind,index,offset:panelWorld.sub(start)};
  note('Movendo painel · solte para fixar');
}
function endDrag(kind,index){
  if(dragging?.kind===kind&&(index===undefined||dragging?.index===index||dragging?.index===undefined)){
    const p=dragging.p;
    state.panels[p.id]=[p.group.position.x,p.group.position.y,p.group.position.z];
    dragging=null;
    safeStore();
    note('Painel fixado');
  }
}
function selectRay(ray,source,kind,index,grab=false){
  if(!ray)return;
  const hit=intersectFrom(ray.origin,ray.direction);
  if(grab&&hit){beginDrag(hit.p,source,kind);if(dragging)dragging.index=index;return;}
  if(hit){if(hit.region?.action&&hit.region.action!=='drag')action(hit.region.action);return;}
  raycaster.set(ray.origin,ray.direction);
  const marks=raycaster.intersectObjects(teleportMarkers,false);
  if(marks.length&&marks[0].distance<12)teleport(marks[0].object.userData.destination);
}

for(let i=0;i<2;i++){
  const controller=renderer.xr.getController(i);
  rig.add(controller);
  controllers.push({object:controller,index:i,lastSnap:0});
  controller.addEventListener('selectstart',()=>{
    if(!dragging){
      const ray=rayFromController(controller);
      const uiHit=ray&&intersectFrom(ray.origin,ray.direction);
      if(uiHit?.region?.action){selectRay(ray,controller,'controller',i);return;}
      if(shootMode){fireFromController(controller);return;}
      selectRay(ray,controller,'controller',i);
    }
  });
  controller.addEventListener('squeezestart',()=>{selectRay(rayFromController(controller),controller,'controller',i,true);});
  controller.addEventListener('squeezeend',()=>endDrag('controller',i));
  const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(),new THREE.Vector3(0,0,-8)]),new THREE.LineBasicMaterial({color:0x5aaa88,transparent:true,opacity:0.45}));
  controller.add(line);
  const grip=renderer.xr.getControllerGrip(i);
  grip.add(controllerFactory.createControllerModel(grip));
  rig.add(grip);
  const hand=renderer.xr.getHand(i);
  rig.add(hand);
  hand.add(handFactory.createHandModel(hand,'spheres'));
  hands.push({object:hand,index:i,pinched:false});
  hand.addEventListener('selectstart',()=>{if(!dragging)selectRay(rayFromHand(hand),hand,'hand',i);});
}

const teleportMarkers=[];
const destinations=[[0,-1.3],[-3,-3],[3,-3],[0,-5],[-5,-6],[5,-6]];
for(const [x,z] of destinations){
  const circle=new THREE.Mesh(new THREE.RingGeometry(0.28,0.38,32),new THREE.MeshBasicMaterial({color:0x4a9a7a,transparent:true,opacity:0.35,side:THREE.DoubleSide}));
  circle.rotation.x=-Math.PI/2; circle.position.set(x,0.02,z);
  circle.userData.destination=new THREE.Vector3(x,0,z);
  scene.add(circle); teleportMarkers.push(circle);
}
function teleport(pos){
  const head=new THREE.Vector3();
  if(renderer.xr.isPresenting)renderer.xr.getCamera().getWorldPosition(head);
  else camera.getWorldPosition(head);
  rig.position.x=clamp(rig.position.x+pos.x-head.x,-9,9);
  rig.position.z=clamp(rig.position.z+pos.z-head.z,-8,6);
  note('Teletransporte realizado.');
}

function setEnvironment(n){
  state.settings.env=(n+environments.length)%environments.length;
  $('environment').value=state.settings.env;
  buildWorld(state.settings.env);
  safeStore();updateVR();
}
function configureQuality(){
  const q=state.settings.quality||'high';
  const pr=q==='low'?1:q==='high'?Math.min(devicePixelRatio,2):Math.min(devicePixelRatio,1.5);
  renderer.setPixelRatio(pr);
  try{if(typeof renderer.xr.setFoveation==='function')renderer.xr.setFoveation(q==='low'?0.65:q==='high'?0.15:0.4);}catch(e){}
  try{if(typeof renderer.xr.setFramebufferScaleFactor==='function'){const fb=q==='low'?0.85:q==='high'?1.1:1.0;renderer.xr.setFramebufferScaleFactor(fb);}}catch(e){}
  const res=q==='low'?1024:q==='high'?2048:1536;
  if(sun.shadow.mapSize.x!==res){
    if(sun.shadow.map){try{sun.shadow.map.dispose();}catch(e){}sun.shadow.map=null;}
    sun.shadow.mapSize.set(res,res);
  }
  renderer.shadowMap.enabled=true;
  renderer.shadowMap.needsUpdate=true;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure=state.settings.lighting==='night'?1.2:1.32;
}
function syncSettings(){
  for(const k of ['lighting','quality','fontSize','distance','panelHeight','panelScale','speed','snap','volume','playerHeight','vignette','comfort'])if($(k))$(k).value=state.settings[k];
  $('environment').value=state.settings.env;
  configureQuality();applyLight();panelPositionReset();
  for(const [id,v] of Object.entries(state.panels||{})){
    if(panels[id]&&Array.isArray(v)&&v.length===3&&v.every(Number.isFinite))panels[id].group.position.set(...v);
  }
}

let lastSecond=0;
const clock=new THREE.Clock();
let frameCount=0;

renderer.setAnimationLoop(()=>{
  const dt=Math.min(clock.getDelta(),0.05);
  const time=performance.now()*0.001;
  if(flagMaterial.userData.shader)flagMaterial.userData.shader.uniforms.uTime.value=time;
  updateSoldiers(dt,time);

  if(!renderer.xr.isPresenting){
    const host=$('scene');
    const w=host?host.clientWidth:0;
    const h=host?host.clientHeight:0;
    if(w&&h){
      const pr=renderer.getPixelRatio();
      if(renderer.domElement.width!==Math.round(w*pr)||renderer.domElement.height!==Math.round(h*pr)){
        renderer.setSize(w,h,false);
        camera.aspect=w/h;camera.updateProjectionMatrix();
      }
    }
  }

  if(renderer.xr.isPresenting){try{
    const session=renderer.xr.getSession();
    if(!session)throw Error("no session");
    for(const src of session.inputSources){
      const gp=src.gamepad;if(!gp)continue;
      let ax=0,az=0;
      if(gp.axes.length>=4){ax=gp.axes[2]||0;az=gp.axes[3]||0;}
      else{ax=gp.axes[0]||0;az=gp.axes[1]||0;}
      if(src.handedness==='left'&&(Math.abs(ax)>0.18||Math.abs(az)>0.18)){
        const dir=new THREE.Vector3();renderer.xr.getCamera().getWorldDirection(dir);dir.y=0;dir.normalize();
        const right=new THREE.Vector3().crossVectors(dir,new THREE.Vector3(0,1,0)).normalize();
        const speed=Number(state.settings.speed);
        rig.position.addScaledVector(dir,-az*dt*speed);
        rig.position.addScaledVector(right,ax*dt*speed);
        rig.position.x=clamp(rig.position.x,-9,9);rig.position.z=clamp(rig.position.z,-8,6);
        isLocomoting=true;
        const mag=Math.min(1,Math.hypot(ax,az));
        moveVignetteTarget=(Number(state.settings.comfort)?mag:0)*(Number(state.settings.vignette)||100)/100*0.55;
      }
      if(src.handedness==='right'&&Math.abs(ax)>0.7){
        const c=controllers.find(o=>o.object.userData.handedness==='right')||controllers[1];
        const current=performance.now();
        if(current-c.lastSnap>450&&Number(state.settings.snap)){
          rig.rotation.y-=Math.sign(ax)*THREE.MathUtils.degToRad(+state.settings.snap);
          c.lastSnap=current;
        }
      }
    }
    for(const h of hands){
      const hand=h.object;
      const tip=hand.joints?.['index-finger-tip'],thumb=hand.joints?.['thumb-tip'];
      if(!tip||!thumb||!tip.visible||!thumb.visible){h.pinched=false;continue;}
      tip.updateWorldMatrix(true,false);thumb.updateWorldMatrix(true,false);
      const v=new THREE.Vector3(),u=new THREE.Vector3();
      tip.getWorldPosition(v);thumb.getWorldPosition(u);
      const pinched=v.distanceTo(u)<0.033;
      if(pinched&&!h.pinched){
        const ray=rayFromHand(hand);
        const hit=handTouchHit(hand)||(ray&&intersectFrom(ray.origin,ray.direction));
        if(hit?.region?.action==='drag'){beginDrag(hit.p,tip,'hand');dragging.index=h.index;}
        else if(!dragging){if(hit?.region?.action&&hit.region.action!=='drag')action(hit.region.action);else selectRay(ray,tip,'hand',h.index);}
      }
      if(!pinched&&h.pinched)endDrag('hand',h.index);
      h.pinched=pinched;
    }
    if(dragging){
      const position=new THREE.Vector3();
      dragging.source.getWorldPosition(position);
      position.add(dragging.offset);
      dragging.p.group.position.set(clamp(position.x,-8,8),clamp(position.y,0.5,4),clamp(position.z,-7,-0.6));
    }
    let over=null;
    for(const o of controllers){
      const ray=rayFromController(o.object);
      const hit=intersectFrom(ray.origin,ray.direction);
      if(hit?.region){over={panel:hit.p.id,action:hit.region.action};break;}
    }
    if(over?.panel!==hovered?.panel||over?.action!==hovered?.action){hovered=over;updateVR();}
    const t=Math.floor(Date.now()/1000);
    if(t!==lastSecond){
      lastSecond=t;
      const s=state.session;
      if(s?.mode==='exam'&&!s.finished&&s.minutes&&Date.now()-s.start>=s.minutes*60000)finishExam();
      else if(s?.mode==='exam')drawMain();
    }
  }catch(xrErr){console.warn('XR frame',xrErr);}}

  if(!isLocomoting)moveVignetteTarget*=0.0;
  isLocomoting=false;
  moveVignetteCurrent+=(moveVignetteTarget-moveVignetteCurrent)*Math.min(1,dt*8);
  if(renderer.xr.isPresenting){
    if(vignetteMesh)vignetteMesh.visible=false;
    if(vignetteUniforms)vignetteUniforms.uIntensity.value=0;
    moveVignetteCurrent=0;moveVignetteTarget=0;
  } else if(vignetteUniforms && vignetteMesh){
    const vi=moveVignetteCurrent;
    vignetteUniforms.uIntensity.value=vi;
    vignetteUniforms.uRadius.value=0.78+(1-vi)*0.15;
    vignetteMesh.visible=vi>0.02;
  }
  if(audioCtx && listenerNode){
    try{
      const hp=new THREE.Vector3();
      if(renderer.xr.isPresenting)renderer.xr.getCamera().getWorldPosition(hp);
      else camera.getWorldPosition(hp);
      if(listenerNode.positionX){
        listenerNode.positionX.setValueAtTime(hp.x,audioCtx.currentTime);
        listenerNode.positionY.setValueAtTime(hp.y,audioCtx.currentTime);
        listenerNode.positionZ.setValueAtTime(hp.z,audioCtx.currentTime);
      } else if(listenerNode.setPosition){
        listenerNode.setPosition(hp.x,hp.y,hp.z);
      }
      const fwd=new THREE.Vector3();
      if(renderer.xr.isPresenting)renderer.xr.getCamera().getWorldDirection(fwd);
      else camera.getWorldDirection(fwd);
      if(listenerNode.forwardX){
        listenerNode.forwardX.setValueAtTime(fwd.x,audioCtx.currentTime);
        listenerNode.forwardY.setValueAtTime(fwd.y,audioCtx.currentTime);
        listenerNode.forwardZ.setValueAtTime(fwd.z,audioCtx.currentTime);
        listenerNode.upX.setValueAtTime(0,audioCtx.currentTime);
        listenerNode.upY.setValueAtTime(1,audioCtx.currentTime);
        listenerNode.upZ.setValueAtTime(0,audioCtx.currentTime);
      }
    }catch(e){}
  }
  try{
    if(renderer.xr.isPresenting){
      if(scene.fog)scene.fog=null;
      if(!scene.background)scene.background=new THREE.Color(0x9ec4d0);
    }
  }catch(err){console.warn('xr frame prep',err);}

  // Mantém texturas 4K frescas periodicamente durante VR (garantia extra)
  if(renderer.xr.isPresenting && (frameCount & 63)===0){
    try{
      for(const id of ['main','left','right']){
        const p=panels[id]; if(p&&p.texture) p.texture.needsUpdate=true;
      }
    }catch(e){}
  }
  frameCount++;

  try{renderer.render(scene,camera);}catch(err){console.error('render error',err);}
});

// ---- Canvas fullscreen para WebXR ----
let canvasOriginalParent=null;
function mountCanvasForXR(){
  const canvas=renderer.domElement;
  if(!canvasOriginalParent)canvasOriginalParent=canvas.parentElement;
  document.body.appendChild(canvas);
  canvas.style.cssText=[
    'position:fixed','inset:0','width:100%','height:100%',
    'max-width:none','max-height:none','z-index:2147483646',
    'margin:0','padding:0','border:none','border-radius:0',
    'background:#9ec4d0','display:block'
  ].join(';');
  try{
    const w=window.innerWidth||1832,h=window.innerHeight||1920;
    renderer.setSize(w,h,false);
    camera.aspect=w/Math.max(1,h);camera.updateProjectionMatrix();
  }catch(e){}
}
function restoreCanvasFromXR(){
  const canvas=renderer.domElement;
  canvas.style.cssText='';
  const host=document.getElementById('scene')||canvasOriginalParent;
  if(host)host.appendChild(canvas);
  try{
    const w=host.clientWidth||640,h=host.clientHeight||360;
    renderer.setSize(w,h,false);
    camera.aspect=w/Math.max(1,h);camera.updateProjectionMatrix();
  }catch(e){}
}
function forceBrightScene(){
  applyLight();
  renderer.shadowMap.enabled=state.settings.quality!=='low';
  renderer.shadowMap.needsUpdate=true;
  world.visible=true;
  if(skyMesh)skyMesh.visible=true;
}

async function enterVR(){
  try{
    if(renderer.xr.isPresenting){
      await renderer.xr.getSession().end();
      return;
    }
    if(!navigator.xr||!(await navigator.xr.isSessionSupported('immersive-vr'))){
      throw Error('WebXR imersivo não disponível neste navegador');
    }

    mountCanvasForXR();
    forceBrightScene();
    if(world && world.children.length<5) buildWorld(+state.settings.env||0);

    try{if(typeof renderer.xr.setReferenceSpaceType==='function')renderer.xr.setReferenceSpaceType('local-floor');}catch(e){}

    const session=await navigator.xr.requestSession('immersive-vr',{optionalFeatures:['local-floor','bounded-floor']});
    try{if(typeof renderer.xr.setFramebufferScaleFactor==='function')renderer.xr.setFramebufferScaleFactor(1.0);}catch(e){}

    await renderer.xr.setSession(session);

    forceBrightScene();
    rig.position.set(0,0,0);
    rig.rotation.set(0,0,0);

    try{
      if(vignetteMesh){
        vignetteMesh.visible=false;
        if(vignetteMesh.parent)vignetteMesh.parent.remove(vignetteMesh);
      }
    }catch(e){}
    moveVignetteTarget=0; moveVignetteCurrent=0;

    renderer.shadowMap.enabled=state.settings.quality!=='low';
    renderer.shadowMap.needsUpdate=true;

    try{
      forceRedrawPanels();
      updateVR();
      // Reenvia a textura 4K múltiplas vezes nos primeiros segundos
      [50,150,400,900,1500,2500].forEach(ms=>{
        setTimeout(()=>{
          try{
            for(const id of ['main','left','right']){
              const p=panels[id];
              if(p&&p.texture) p.texture.needsUpdate=true;
            }
            drawMain(); drawSide('left'); drawSide('right');
          }catch(e){}
        }, ms);
      });
    }catch(e){console.warn(e);}

    $('vrButton').textContent='SAIR DO VR';
    session.addEventListener('end',()=>{
      restoreCanvasFromXR();
      $('vrButton').textContent='ENTRAR EM VR';
      dragging=null;
      renderer.shadowMap.enabled=true;
      renderer.shadowMap.needsUpdate=true;
      try{
        if(vignetteMesh && !vignetteMesh.parent)camera.add(vignetteMesh);
      }catch(e){}
      applyLight();
      note('Saiu do VR');
    });

    try{playFanfare();}catch(e){}
    note(`VR imersivo · 4K (${WIDTH*PIXEL_SCALE}×${HEIGHT*PIXEL_SCALE}) · PMSC 2026`);
  }catch(e){
    console.error(e);
    restoreCanvasFromXR();
    note('Não foi possível entrar em VR: '+e.message);
  }
}

// UI wiring
for(const [p,label] of pages){const b=button(label,()=>go(p),$('navigation'));b.dataset.page=p;}
environments.forEach((name,i)=>{$('environment').add(new Option(name,String(i)));});
$('environment').onchange=()=>{setEnvironment(+$('environment').value);};
$('lighting').onchange=()=>{state.settings.lighting=$('lighting').value;applyLight();safeStore();};
$('quality').onchange=()=>{state.settings.quality=$('quality').value;configureQuality();safeStore();};
for(const key of ['fontSize','distance','panelHeight','panelScale','speed','snap']){
  $(key).oninput=()=>{state.settings[key]=+$(key).value;if(['distance','panelHeight','panelScale'].includes(key))panelPositionReset();safeStore();updateVR();};
}
$('volume').oninput=()=>{state.settings.volume=+$('volume').value;if(masterGain)masterGain.gain.value=state.settings.volume/100;safeStore();};
if($('playerHeight'))$('playerHeight').oninput=()=>{state.settings.playerHeight=+$('playerHeight').value;applyPlayerHeight();safeStore();};
if($('vignette'))$('vignette').oninput=()=>{state.settings.vignette=+$('vignette').value;safeStore();};
if($('comfort'))$('comfort').onchange=()=>{state.settings.comfort=+$('comfort').value;safeStore();};
$('resetPanels').onclick=resetPanelPositions;
$('vrButton').onclick=enterVR;
if($('shootModeBtn'))$('shootModeBtn').onclick=()=>{toggleShootMode();$('shootModeBtn').textContent=shootMode?'SAIR DO TREINO DE TIRO':'TREINO DE TIRO (VR)';};
$('reload').onclick=loadBank;
for(const name of ['subject','topic','difficulty'])$(name).onchange=()=>{newSession(page==='exam'?'exam':page==='flash'?'flash':page==='review'?'review':'study');};
$('search').oninput=()=>{clearTimeout(window.__searchT);window.__searchT=setTimeout(()=>{try{newSession('study');}catch(e){}},300);};
$('examCount').onchange=()=>{if(page==='exam')newSession('exam');};
$('examTime').onchange=()=>{if(page==='exam')newSession('exam');};
$('examFeedback').onchange=()=>{if(page==='exam')newSession('exam');};
$('demo').onclick=()=>{
  const a=[{id:'demo_1',disciplina:'Direito Constitucional',assunto:'Constituição Federal',enunciado:'Qual é a Constituição Federal atualmente vigente no Brasil?',alternativas:['Constituição de 1967','Constituição de 1988','Constituição de 1946','Constituição de 1937'],gabarito:'B',explicacao:'A Constituição Federal vigente foi promulgada em 1988.'}];
  const result=merge(extract({DEMONSTRACAO:a}),false);
  note('Demonstração adicionada: '+result.total+' questões.');
};
$('upload').onchange=async e=>{
  const all=[];
  for(const f of e.target.files){try{if(f.size>10000000)throw Error('Arquivo > 10 MB');all.push(...extract(JSON.parse(await f.text())));}catch(err){note('Erro em '+f.name+': '+err.message);}}
  const r=merge(all,false);note(`Importação: ${r.total} questões.`);
};
$('focus').onclick=()=>{document.body.classList.toggle('focus');};
$('reading').onclick=()=>{state.settings.fontSize=clamp(+state.settings.fontSize+10,90,145);$('fontSize').value=state.settings.fontSize;safeStore();updateVR();document.body.classList.toggle('focus');};
$('backup').onclick=exportBackup;
$('csv').onclick=exportCSV;
$('restore').onchange=async e=>{
  try{const f=e.target.files[0];if(!f||f.size>5000000)throw Error('Backup inválido ou muito grande');const obj=JSON.parse(await f.text());
    if(!obj.state||!Array.isArray(obj.state.history)||!Array.isArray(obj.state.favorites))throw Error('Estrutura do backup inválida');
    state={...defaultState(),...obj.state,settings:{...defaultState().settings,...obj.state.settings}};
    safeStore();syncSettings();setEnvironment(+state.settings.env);render();note('Backup restaurado.');
  }catch(err){note('Falha no backup: '+err.message);}
};
$('resetStats').onclick=()=>{
  if(!confirm('Apagar histórico, revisões e simulados?'))return;
  state.history=[];state.reviews={};state.favorites=[];state.exams=[];state.session=null;
  safeStore();newSession('study');note('Progresso zerado.');
};

async function start(){
  try{restoreState();}catch(e){console.warn(e);state=defaultState();}
  try{db=await openDB();}catch(e){console.warn('idb',e);}
  try{
    if(!state.history.length){
      const saved=await idbGet('progress');
      if(saved&&Array.isArray(saved.history)){
        state.history=saved.history.slice(-500);
        if(saved.reviews)state.reviews=saved.reviews;
      }
    }
  }catch(e){console.warn(e);}
  try{initSky();}catch(e){console.warn('sky',e);}
  try{syncSettings();}catch(e){console.warn(e);}
  try{applyPlayerHeight();}catch(e){console.warn(e);}
  try{buildWorld(+state.settings.env||0);}catch(e){console.warn('world',e);}
  try{fillFilters();}catch(e){console.warn(e);}
  try{
    const cache=await idbGet('bank');
    if(Array.isArray(cache)&&cache.length){questions=cache;fillFilters();}
  }catch(e){console.warn(e);}
  try{
    if(!state.session?.ids?.length)newSession('study');
    else render();
  }catch(e){console.warn('session',e);try{state.session=null;newSession('study');}catch(e2){note('Sessão: '+e2.message);}}
  try{await loadBank();}catch(e){console.warn('bank',e);}
  note(`Pronto · PMSC 2026 · Painéis ${WIDTH*PIXEL_SCALE}×${HEIGHT*PIXEL_SCALE} (4K)`);
}
start().catch(e=>{
  console.error(e);
  note('Erro de inicialização: '+e.message);
  try{localStorage.removeItem(KEY);}catch(_){}
});
