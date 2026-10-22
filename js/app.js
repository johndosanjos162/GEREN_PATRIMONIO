/**
 * PMSC 2026 — Academia Militar Imersiva
 * JavaScript: Three.js + WebXR, questões, VR, áudio, treino de tiro
 * Importado por index.html como type="module"
 */
/* ==========================================================================
   JAVASCRIPT — O CÉREBRO E OS MÚSCULOS
   Three.js + WebXR: cena 3D, física de locomoção, painéis VR, banco de
   questões, áudio espacial, vinheta de conforto e treino de tiro.
   O HTML só fornece o espaço; o CSS só estiliza a UI 2D.
   ========================================================================== */


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
    el('p','Toques de corneta militares são reproduzidos ao entrar em VR, ao finalizar um simulado e nas respostas (fora do simulado). Ajuste o volume no menu lateral.',c);
    el('p','Correção tela preta VR + treino de tiro (gatilho). Conforto: vinheta só nas bordas. Iluminação reforçada ao entrar em VR. Áudio espacial nos disparos e feedbacks.',c);
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
// ÁUDIO — CORNETA MILITAR (Web Audio API)
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

    const wet=audioCtx.createGain();
    wet.gain.value=0.28;
    convolver.connect(wet);
    wet.connect(masterGain);

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
  const melody=[
    {f:392.00,t:0.00,d:0.24},
    {f:523.25,t:0.26,d:0.24},
    {f:659.25,t:0.52,d:0.24},
    {f:783.99,t:0.78,d:0.44},
    {f:1046.50,t:1.24,d:0.95}
  ];
  for(const n of melody){
    playNote(n.f,t0+n.t,n.d,0.22);
    playNote(n.f*1.003,t0+n.t+0.01,n.d,0.12);
  }
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
  const notes=[
    {f:392.00,t:0.0,d:0.48},
    {f:392.00,t:0.55,d:0.32},
    {f:523.25,t:0.95,d:0.48},
    {f:392.00,t:1.5,d:0.32},
    {f:329.63,t:1.9,d:0.48},
    {f:261.63,t:2.45,d:0.85}
  ];
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
renderer.toneMappingExposure=1.35;
renderer.shadowMap.enabled=true;
renderer.shadowMap.type=THREE.PCFSoftShadowMap;
renderer.shadowMap.autoUpdate=false;
renderer.shadowMap.needsUpdate=true;
renderer.setPixelRatio(Math.min(devicePixelRatio,2.5));
$('scene').append(renderer.domElement);
renderer.setClearColor(0x8eb4c0, 1);

// Iluminação realista
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
// CONFORTO VR · VINHETA DINÂMICA · ALTURA · ÁUDIO ESPACIAL
// Princípios: UI diegética, locomotion comfort, 6DoF, spatial audio
// =====================================================
// Vinheta de conforto — desligada por padrão; nunca cobre o centro da visão
const vignetteUniforms = {
  uIntensity: { value: 0.0 },
  uRadius: { value: 0.85 },
  uSoftness: { value: 0.4 }
};
const vignetteMat = new THREE.ShaderMaterial({
  transparent: true,
  depthTest: false,
  depthWrite: false,
  blending: THREE.NormalBlending,
  uniforms: vignetteUniforms,
  vertexShader: `
    varying vec2 vUv;
    void main(){
      vUv = uv;
      gl_Position = vec4(position.xy, 0.0, 1.0);
    }
  `,
  fragmentShader: `
    uniform float uIntensity, uRadius, uSoftness;
    varying vec2 vUv;
    void main(){
      if(uIntensity < 0.01){ gl_FragColor = vec4(0.0); return; }
      vec2 c = vUv - 0.5;
      c.x *= 1.1;
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
vignetteMesh.visible = false; // só liga ao locomover
camera.add(vignetteMesh);
vignetteMesh.position.set(0, 0, -0.12);
vignetteMesh.scale.set(1, 1, 1);

let moveVignetteTarget = 0;
let moveVignetteCurrent = 0;
let isLocomoting = false;

function applyPlayerHeight(){
  const h = Number(state.settings.playerHeight) || 1.65;
  // offset vertical do rig: altura dos olhos relativa ao piso
  // em WebXR local-floor o headset já define Y; usamos offset só no preview desktop
  // e como ajuste fino de painéis/conforto sentado
  if(!renderer.xr.isPresenting){
    camera.position.y = h;
  }
  // painéis acompanham altura preferida se ainda não movidos
  if(panels.main && !state.panels?.main){
    state.settings.panelHeight = Math.min(2.4, Math.max(1.0, h));
    if($('panelHeight')) $('panelHeight').value = state.settings.panelHeight;
  }
}

// Áudio espacial: panner 3D ligado ao rig (origem do ouvinte = cabeça)
let listenerNode = null;
function ensureSpatialAudio(){
  initAudio();
  if(!audioCtx || listenerNode) return;
  try {
    listenerNode = audioCtx.listener;
    if(listenerNode.positionX){
      listenerNode.positionX.value = 0;
      listenerNode.positionY.value = 1.6;
      listenerNode.positionZ.value = 0;
    }
  } catch(e){}
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
    if(panner.positionX){
      panner.positionX.value = worldPos.x;
      panner.positionY.value = worldPos.y;
      panner.positionZ.value = worldPos.z;
    } else {
      panner.setPosition(worldPos.x, worldPos.y, worldPos.z);
    }
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
// override fanfare/taps to use spatial positions near flags
const _playFanfare = typeof playFanfare === 'function' ? null : null;


// Sky dome melhorado
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
        // gradiente atmosférico
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
  scene.add(skyMesh); // scene (não rig) — mais estável no WebXR
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
// TEXTURAS PROCEDURAIS DE ALTA QUALIDADE
// =====================================================
const world=new THREE.Group();
scene.add(world);

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
  // veios
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
  // nós
  for(let k=0;k<7;k++){
    const kx=Math.random()*size,ky=Math.random()*size;
    for(let r=22;r>0;r--){
      ctx.strokeStyle=`rgba(28,16,6,${0.04+r*0.012})`;
      ctx.beginPath();ctx.ellipse(kx,ky,r,r*0.65,Math.random()*0.4,0,Math.PI*2);ctx.stroke();
    }
  }
  // grão fino
  const img=ctx.getImageData(0,0,size,size);
  for(let i=0;i<img.data.length;i+=4){
    const n=(Math.random()-0.5)*12;
    img.data[i]+=n;img.data[i+1]+=n;img.data[i+2]+=n;
  }
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
    // grãos por tábua
    for(let g=0;g<90;g++){
      ctx.strokeStyle=`rgba(25,14,6,${0.08+Math.random()*0.22})`;
      ctx.lineWidth=0.4+Math.random()*1.6;
      const y=cy+Math.random()*plankH;
      ctx.beginPath();ctx.moveTo(0,y);
      for(let x=0;x<size;x+=12)ctx.lineTo(x,y+Math.sin(x*0.028+g)*1.5);
      ctx.stroke();
    }
    // bordas
    ctx.strokeStyle='rgba(15,8,3,0.75)';ctx.lineWidth=2.5;
    ctx.strokeRect(0,cy,size,plankH);
  }
  // juntas verticais
  for(let s=0;s<10;s++){
    const x=Math.random()*size,p=Math.floor(Math.random()*8);
    ctx.strokeStyle='rgba(12,6,2,0.65)';ctx.lineWidth=1.8;
    ctx.beginPath();ctx.moveTo(x,p*plankH);ctx.lineTo(x,(p+1)*plankH);ctx.stroke();
  }
  // desgaste
  const img=ctx.getImageData(0,0,size,size);
  for(let i=0;i<img.data.length;i+=4){
    const n=(Math.random()-0.5)*10;
    img.data[i]+=n;img.data[i+1]+=n;img.data[i+2]+=n;
  }
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
  // textura de reboco
  const img=ctx.getImageData(0,0,size,size);
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    const i=(y*size+x)*4;
    const n=fbm(x/size*6,y/size*6,4)*18+(Math.random()-0.5)*8;
    img.data[i]=Math.min(255,Math.max(0,img.data[i]+n));
    img.data[i+1]=Math.min(255,Math.max(0,img.data[i+1]+n*0.95));
    img.data[i+2]=Math.min(255,Math.max(0,img.data[i+2]+n*0.9));
  }
  ctx.putImageData(img,0,0);
  // manchas sutis
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
  // variação de cor em manchas
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
  // rachaduras horizontais
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

// Materiais PBR realistas
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
      color,
      map:surfaceMaps.color,
      roughnessMap:surfaceMaps.roughness,
      normalMap:surfaceMaps.normal,
      aoMap:surfaceMaps.ao,
      aoMapIntensity:0.5,
      roughness:isMetal?0.35:isWood?0.72:isFabric?0.9:0.82,
      metalness:isMetal?0.72:0,
      normalScale:new THREE.Vector2(0.18,0.18),
      envMapIntensity:isMetal?1.1:0.45
    };
    if(isWood){
      params.map=woodTexture;
      params.normalMap=woodNormal;
      params.normalScale=new THREE.Vector2(0.35,0.35);
      params.roughness=0.68;
      params.envMapIntensity=0.3;
    }
    if(isFabric){
      params.roughness=0.92;
      params.normalScale=new THREE.Vector2(0.25,0.25);
    }
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

// BANDEIRA BRASIL realista
function flagTexture(){
  const c=document.createElement('canvas');c.width=1024;c.height=680;
  const a=c.getContext('2d');
  a.fillStyle='#009c3b';a.fillRect(0,0,1024,680);
  a.fillStyle='#ffdf00';
  a.beginPath();a.moveTo(512,48);a.lineTo(960,340);a.lineTo(512,632);a.lineTo(64,340);a.closePath();a.fill();
  a.fillStyle='#002776';a.beginPath();a.arc(512,340,175,0,Math.PI*2);a.fill();
  a.save();a.translate(512,340);a.rotate(-0.18);
  a.fillStyle='#fff';a.fillRect(-185,-16,370,32);
  a.fillStyle='#002776';a.font='bold 22px Arial';a.textAlign='center';a.textBaseline='middle';
  a.fillText('ORDEM E PROGRESSO',0,2);
  a.restore();
  // estrelas
  a.fillStyle='#fff';
  const stars=[[0,-95],[40,-70],[-40,-70],[70,-30],[-70,-30],[85,20],[-85,20],[70,70],[-70,70],[30,100],[-30,100],[0,115],
    [55,-50],[-55,-50],[95,0],[-95,0],[55,55],[-55,55],[0,50],[20,-20],[-20,-20],[0,0]];
  for(const [sx,sy] of stars){
    a.beginPath();a.arc(512+sx,340+sy,3.2,0,Math.PI*2);a.fill();
  }
  // tecido com leve variação
  const img=a.getImageData(0,0,1024,680);
  for(let i=0;i<img.data.length;i+=4){
    const n=(Math.random()-0.5)*6;
    img.data[i]+=n;img.data[i+1]+=n;img.data[i+2]+=n;
  }
  a.putImageData(img,0,0);
  const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;
  t.generateMipmaps=true;t.minFilter=THREE.LinearMipmapLinearFilter;t.magFilter=THREE.LinearFilter;t.anisotropy=8;
  return t;
}
const flagTex=flagTexture();

const staticFlagMaterial=new THREE.MeshStandardMaterial({
  map:flagTex,side:THREE.DoubleSide,roughness:0.65,metalness:0.02,envMapIntensity:0.4
});

const flagMaterial=new THREE.MeshStandardMaterial({
  map:flagTex,side:THREE.DoubleSide,roughness:0.65,metalness:0.02,envMapIntensity:0.4
});
flagMaterial.onBeforeCompile=(shader)=>{
  shader.uniforms.uTime={value:0};shader.uniforms.uWind={value:1.15};
  shader.vertexShader=`
    uniform float uTime;uniform float uWind;
    ${shader.vertexShader}
  `.replace('#include <begin_vertex>',`
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


// =====================================================
// GEOMETRIAS REALISTAS (compostas, multi-parte, proporções corretas)
// =====================================================

function bevelBox(w,h,d,bevel=0.02,seg=1){
  // caixa com leve bisel nas arestas superiores via escala de topo
  const g = new THREE.BoxGeometry(w,h,d,seg,1,seg);
  return g;
}

function flag(x,z){
  // mastro cônico metálico
  const poleGeo = new THREE.CylinderGeometry(0.028,0.042,4.2,20);
  const pole = new THREE.Mesh(withAO(poleGeo), mat('#c9cfc9',{metalness:0.88,roughness:0.22}));
  pole.position.set(x,2.1,z); pole.castShadow=true; world.add(pole);
  // base hexagonal
  const base = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.28,0.34,0.22,8)), mat('#3a3f3a',{metalness:0.45,roughness:0.48}));
  base.position.set(x,0.11,z); base.castShadow=true; base.receiveShadow=true; world.add(base);
  const baseRing = new THREE.Mesh(withAO(new THREE.TorusGeometry(0.3,0.025,10,24)), mat('#2a2e2a',{metalness:0.5,roughness:0.4}));
  baseRing.position.set(x,0.22,z); baseRing.rotation.x=Math.PI/2; world.add(baseRing);
  // ponteira dourada em forma de lança
  const tip = new THREE.Mesh(new THREE.ConeGeometry(0.055,0.18,12), mat('#d4af37',{metalness:0.92,roughness:0.15,clearcoat:0.5}));
  tip.position.set(x,4.28,z); tip.castShadow=true; world.add(tip);
  const tipBall = new THREE.Mesh(new THREE.SphereGeometry(0.04,12,10), mat('#d4af37',{metalness:0.9,roughness:0.18}));
  tipBall.position.set(x,4.12,z); world.add(tipBall);
  // cordas
  for(const yy of [1.32,1.48]){
    const rope = new THREE.Mesh(new THREE.TorusGeometry(0.048,0.008,8,16), mat('#a8895a',{roughness:0.7}));
    rope.position.set(x,yy,z); rope.rotation.x=Math.PI/2; world.add(rope);
  }
  // bandeira com mais subdivisões para vento realista
  const geom = new THREE.PlaneGeometry(1.85,1.18,56,28);
  const mesh = new THREE.Mesh(geom, flagMaterial);
  mesh.position.set(x+0.98,3.32,z); mesh.castShadow=true; world.add(mesh);
  contactShadow(x,z,1.9,1.9);
}

function windowFrame(x,y,z,w,h,rotY=0){
  const g = new THREE.Group(); g.position.set(x,y,z); g.rotation.y=rotY;
  // vidro com profundidade
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(w*0.96,h*0.96), new THREE.MeshPhysicalMaterial({
    color:0x1a3040, metalness:0.04, roughness:0.04, transmission:0.4, transparent:true, opacity:0.78,
    envMapIntensity:1.6, clearcoat:0.7, clearcoatRoughness:0.08, ior:1.52, thickness:0.025
  }));
  glass.position.z=0.02; g.add(glass);
  // moldura externa profunda
  const fw=0.06, depth=0.1, frameMat=mat('#2a1e14',{roughness:0.62});
  const parts = [
    [0, h/2+fw/2, 0, w+fw*2, fw, depth],
    [0,-h/2-fw/2, 0, w+fw*2, fw, depth],
    [-w/2-fw/2, 0, 0, fw, h, depth],
    [w/2+fw/2, 0, 0, fw, h, depth]
  ];
  for(const [px,py,pz,bw,bh,bd] of parts){
    const m = new THREE.Mesh(withAO(new THREE.BoxGeometry(bw,bh,bd)), frameMat);
    m.position.set(px,py,pz); g.add(m);
  }
  // travessas
  const vCross = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.028,h*0.96,0.06)), frameMat);
  vCross.position.z=0.03; g.add(vCross);
  const hCross = new THREE.Mesh(withAO(new THREE.BoxGeometry(w*0.96,0.028,0.06)), frameMat);
  hCross.position.z=0.03; g.add(hCross);
  // peitoril
  const sill = new THREE.Mesh(withAO(new THREE.BoxGeometry(w+fw*2.4,0.04,0.14)), mat('#3a2a1c',{roughness:0.55}));
  sill.position.set(0,-h/2-fw-0.02,0.04); g.add(sill);
  g.traverse(o=>{ if(o.isMesh){ o.castShadow=true; o.receiveShadow=true; }});
  world.add(g); return g;
}

function doorFrame(x,y,z,w,h,rotY=0){
  const g = new THREE.Group(); g.position.set(x,y,z); g.rotation.y=rotY;
  // folha principal
  const panel = new THREE.Mesh(withAO(new THREE.BoxGeometry(w,h,0.075)), mat('#4a3420'));
  panel.position.z=0.038; g.add(panel);
  // 4 painéis rebaixados com moldura interna
  const insets = [
    [-w*0.22, h*0.2, w*0.36, h*0.32],
    [ w*0.22, h*0.2, w*0.36, h*0.32],
    [-w*0.22,-h*0.22,w*0.36, h*0.28],
    [ w*0.22,-h*0.22,w*0.36, h*0.28]
  ];
  for(const [ix,iy,iw,ih] of insets){
    const outer = new THREE.Mesh(withAO(new THREE.BoxGeometry(iw+0.04,ih+0.04,0.02)), mat('#3d2c18'));
    outer.position.set(ix,iy,0.07); g.add(outer);
    const inner = new THREE.Mesh(withAO(new THREE.BoxGeometry(iw,ih,0.015)), mat('#5a4228'));
    inner.position.set(ix,iy,0.08); g.add(inner);
  }
  // batente
  const fw=0.08, frameMat=mat('#2a1e14',{roughness:0.58});
  for(const [px,py,bw,bh] of [[0,h/2+fw/2,w+fw*2,fw],[-w/2-fw/2,0,fw,h],[w/2+fw/2,0,fw,h]]){
    const m = new THREE.Mesh(withAO(new THREE.BoxGeometry(bw,bh,0.12)), frameMat);
    m.position.set(px,py,0); g.add(m);
  }
  // maçaneta e placa
  const plate = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.055,0.14,0.012)), mat('#c9a850',{metalness:0.85,roughness:0.22}));
  plate.position.set(w*0.35,0,0.09); g.add(plate);
  const knob = new THREE.Mesh(new THREE.SphereGeometry(0.038,14,12), mat('#d4af37',{metalness:0.92,roughness:0.14,clearcoat:0.55}));
  knob.position.set(w*0.35,0,0.13); g.add(knob);
  const lever = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.08,0.018,0.018)), mat('#d4af37',{metalness:0.9,roughness:0.16}));
  lever.position.set(w*0.35+0.04,0,0.13); g.add(lever);
  g.traverse(o=>{ if(o.isMesh){ o.castShadow=true; o.receiveShadow=true; }});
  world.add(g); return g;
}

function wallPicture(x,y,z,w,h,rotY=0,color='#3a2a1c'){
  const g = new THREE.Group(); g.position.set(x,y,z); g.rotation.y=rotY;
  // moldura com perfil
  const frame = new THREE.Mesh(withAO(new THREE.BoxGeometry(w,h,0.05)), mat(color,{roughness:0.5}));
  g.add(frame);
  const innerFrame = new THREE.Mesh(withAO(new THREE.BoxGeometry(w*0.94,h*0.94,0.02)), mat('#1a120c',{roughness:0.6}));
  innerFrame.position.z=0.02; g.add(innerFrame);
  const matte = new THREE.Mesh(new THREE.PlaneGeometry(w*0.88,h*0.88), new THREE.MeshStandardMaterial({color:0xf2ede4,roughness:0.92}));
  matte.position.z=0.032; g.add(matte);
  const art = new THREE.Mesh(new THREE.PlaneGeometry(w*0.76,h*0.76), new THREE.MeshStandardMaterial({
    color:new THREE.Color().setHSL(0.08+Math.random()*0.12,0.32,0.4), roughness:0.88, metalness:0
  }));
  art.position.z=0.036; g.add(art);
  g.traverse(o=>{ if(o.isMesh) o.receiveShadow=true; });
  world.add(g); return g;
}

function wallClock(x,y,z){
  const g = new THREE.Group(); g.position.set(x,y,z);
  // corpo
  const face = new THREE.Mesh(new THREE.CircleGeometry(0.32,48), mat('#f5f0e6',{roughness:0.35}));
  g.add(face);
  const rim = new THREE.Mesh(new THREE.TorusGeometry(0.32,0.028,12,48), mat('#2a1e14',{roughness:0.45,metalness:0.15}));
  g.add(rim);
  const glass = new THREE.Mesh(new THREE.CircleGeometry(0.3,48), new THREE.MeshPhysicalMaterial({
    color:0xffffff, transparent:true, opacity:0.12, roughness:0.05, transmission:0.6, metalness:0
  }));
  glass.position.z=0.02; g.add(glass);
  for(let i=0;i<12;i++){
    const len = i%3===0 ? 0.045 : 0.028;
    const tick = new THREE.Mesh(new THREE.BoxGeometry(0.014,len,0.008), mat('#1a1a1a'));
    const a = i/12*Math.PI*2;
    tick.position.set(Math.sin(a)*0.27, Math.cos(a)*0.27, 0.01);
    tick.rotation.z = -a; g.add(tick);
  }
  const hh = new THREE.Mesh(new THREE.BoxGeometry(0.016,0.17,0.008), mat('#1a1a1a'));
  hh.position.set(0,0.085,0.015); hh.rotation.z=-0.5; g.add(hh);
  const mh = new THREE.Mesh(new THREE.BoxGeometry(0.01,0.25,0.006), mat('#1a1a1a'));
  mh.position.set(0,0.125,0.018); mh.rotation.z=1.1; g.add(mh);
  const center = new THREE.Mesh(new THREE.SphereGeometry(0.022,12,10), mat('#c9a850',{metalness:0.85,roughness:0.18}));
  center.position.z=0.02; g.add(center);
  world.add(g); return g;
}

function potPlant(x,y,z){
  // vaso com perfil mais realista (barriga)
  const potPoints = [];
  for(let i=0;i<=12;i++){
    const t=i/12;
    const r = 0.12 + 0.08*Math.sin(t*Math.PI)*0.9 + (t>0.85?0.04:0);
    potPoints.push(new THREE.Vector2(r, t*0.32));
  }
  const pot = new THREE.Mesh(withAO(new THREE.LatheGeometry(potPoints,20)), mat('#7a3a22',{roughness:0.72}));
  pot.position.set(x,y,z); pot.castShadow=true; pot.receiveShadow=true; world.add(pot);
  const rim = new THREE.Mesh(withAO(new THREE.TorusGeometry(0.195,0.018,8,24)), mat('#6a3220',{roughness:0.7}));
  rim.position.set(x,y+0.32,z); rim.rotation.x=Math.PI/2; world.add(rim);
  const soil = new THREE.Mesh(new THREE.CircleGeometry(0.18,20), mat('#2a1a0e',{roughness:0.95}));
  soil.rotation.x=-Math.PI/2; soil.position.set(x,y+0.31,z); world.add(soil);
  // folhas em camadas
  for(let i=0;i<16;i++){
    const leaf = new THREE.Mesh(withAO(new THREE.SphereGeometry(0.09+Math.random()*0.05,10,8)), mat('#2a6a38',{roughness:0.82}));
    const a = i/16*Math.PI*2 + Math.random()*0.3;
    const r = 0.08+Math.random()*0.22;
    leaf.position.set(x+Math.cos(a)*r, y+0.4+Math.random()*0.38, z+Math.sin(a)*r);
    leaf.scale.set(1, 0.4+Math.random()*0.25, 0.7);
    leaf.rotation.set(Math.random()*0.4, Math.random()*Math.PI, Math.random()*0.3);
    leaf.castShadow=true; world.add(leaf);
  }
  contactShadow(x,z,0.75,0.75);
}

function ceilingLamp(x,y,z){
  // cabo
  const cable = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.01,0.01,0.8,8)), mat('#1a1a1a',{metalness:0.6,roughness:0.35}));
  cable.position.set(x,y+0.4,z); world.add(cable);
  // cúpula
  const shadePoints = [new THREE.Vector2(0.05,0), new THREE.Vector2(0.08,0.04), new THREE.Vector2(0.22,0.12), new THREE.Vector2(0.24,0.16)];
  const shade = new THREE.Mesh(withAO(new THREE.LatheGeometry(shadePoints,24)), new THREE.MeshStandardMaterial({
    color:0xf5f0e0, emissive:0xfff0c8, emissiveIntensity:0.5, roughness:0.5, metalness:0.12, side:THREE.DoubleSide
  }));
  shade.position.set(x,y,z); world.add(shade);
  // soquete
  const sock = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.035,0.04,0.06,12)), mat('#2a2a2a',{metalness:0.5,roughness:0.4}));
  sock.position.set(x,y+0.08,z); world.add(sock);
  const light = new THREE.PointLight(0xfff0c0,0.42,5.5,2);
  light.position.set(x,y-0.1,z); world.add(light);
  lightCone(x,y-0.28,z,0.58,2.3);
}

function baseboard(x,y,z,w,d,rotY=0){
  const b = new THREE.Mesh(withAO(new THREE.BoxGeometry(w,0.14,0.05)), mat('#2a1e14',{roughness:0.58}));
  b.position.set(x,y,z); b.rotation.y=rotY; b.receiveShadow=true; world.add(b);
  // filete superior
  const trim = new THREE.Mesh(withAO(new THREE.BoxGeometry(w,0.025,0.055)), mat('#3a2a1c',{roughness:0.55}));
  trim.position.set(x,y+0.08,z); trim.rotation.y=rotY; world.add(trim);
  return b;
}
function crownMolding(x,y,z,w,rotY=0){
  const b = new THREE.Mesh(withAO(new THREE.BoxGeometry(w,0.16,0.09)), mat('#2a1e14',{roughness:0.52}));
  b.position.set(x,y,z); b.rotation.y=rotY; b.receiveShadow=true; world.add(b);
  const trim = new THREE.Mesh(withAO(new THREE.BoxGeometry(w,0.04,0.11)), mat('#3a2a1c',{roughness:0.5}));
  trim.position.set(x,y-0.08,z); trim.rotation.y=rotY; world.add(trim);
  return b;
}

function building(x,z){
  // corpo com textura de concreto
  const body = new THREE.Mesh(withAO(new THREE.BoxGeometry(5.4,4.3,3.4)), new THREE.MeshStandardMaterial({
    map:concreteTexture, color:0x8a948c, roughness:0.86, metalness:0.04,
    normalMap:surfaceMaps.normal, normalScale:new THREE.Vector2(0.14,0.14)
  }));
  body.position.set(x,2.15,z); body.castShadow=true; body.receiveShadow=true; world.add(body);
  // cornija
  box(x,4.4,z,5.9,0.28,3.8,'#4a564e',{roughness:0.72});
  box(x,4.68,z,5.6,0.22,0.5,'#3a4540',{roughness:0.68});
  // platibanda
  box(x,4.9,z,5.7,0.12,3.6,'#3a4540',{roughness:0.7});
  windowFrame(x-1.4,2.35,z+1.72,0.88,1.2);
  windowFrame(x,2.35,z+1.72,0.88,1.2);
  windowFrame(x+1.4,2.35,z+1.72,0.88,1.2);
  doorFrame(x,1.25,z+1.73,1.1,2.1);
  // toldo com estrutura
  box(x,3.2,z+2.0,2.4,0.08,1.3,'#3a3f3a',{metalness:0.35,roughness:0.45});
  for(const dx of [-0.95,0.95]){
    const col = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.04,0.045,2.6,12)), mat('#2e342e',{metalness:0.55,roughness:0.38}));
    col.position.set(x+dx,2.55,z+2.4); col.castShadow=true; world.add(col);
  }
  // degraus com bisel
  box(x,0.1,z+2.3,1.8,0.2,0.5,'#6a7268',{roughness:0.75});
  box(x,0.28,z+2.2,1.6,0.18,0.42,'#7a8278',{roughness:0.75});
  box(x,0.44,z+2.12,1.45,0.14,0.35,'#8a9288',{roughness:0.72});
  contactShadow(x,z+0.5,6.4,4.4);
}

function table(x,z){
  const g = new THREE.Group(); g.position.set(x,0,z);
  // tampo grosso com borda
  const top = new THREE.Mesh(withAO(new THREE.BoxGeometry(1.7,0.06,0.92)), mat('#7a6547'));
  top.position.y=0.84; top.castShadow=true; top.receiveShadow=true; g.add(top);
  const edge = new THREE.Mesh(withAO(new THREE.BoxGeometry(1.72,0.04,0.94)), mat('#5c4528'));
  edge.position.y=0.79; g.add(edge);
  // saia
  const apron = new THREE.Mesh(withAO(new THREE.BoxGeometry(1.55,0.08,0.78)), mat('#6b5334'));
  apron.position.y=0.74; g.add(apron);
  // pernas cônicas com pé
  for(const dx of [-0.68,0.68]) for(const dz of [-0.34,0.34]){
    const leg = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.022,0.035,0.72,14)), mat('#4a5248',{metalness:0.55,roughness:0.32}));
    leg.position.set(dx,0.38,dz); leg.castShadow=true; g.add(leg);
    const foot = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.045,0.05,0.03,12)), mat('#2a2a2a',{metalness:0.5,roughness:0.4}));
    foot.position.set(dx,0.02,dz); g.add(foot);
  }
  // gaveta
  const drawer = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.55,0.14,0.04)), mat('#5c4528'));
  drawer.position.set(-0.4,0.72,0.42); g.add(drawer);
  const knob = new THREE.Mesh(new THREE.SphereGeometry(0.02,10,8), mat('#d4af37',{metalness:0.88,roughness:0.18}));
  knob.position.set(-0.4,0.72,0.46); g.add(knob);
  // objetos sobre a mesa
  const paper = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.28,0.008,0.2)), mat('#f0ebe0',{roughness:0.9}));
  paper.position.set(0.42,0.88,-0.12); g.add(paper);
  const book = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.16,0.03,0.24)), mat('#8a3a35',{roughness:0.75}));
  book.position.set(0.38,0.91,-0.08); g.add(book);
  // caneca
  const cupPoints = [new THREE.Vector2(0.035,0), new THREE.Vector2(0.042,0.02), new THREE.Vector2(0.045,0.08), new THREE.Vector2(0.04,0.1)];
  const cup = new THREE.Mesh(withAO(new THREE.LatheGeometry(cupPoints,16)), mat('#c8c4b8',{roughness:0.3,clearcoat:0.35}));
  cup.position.set(0.55,0.88,0.22); g.add(cup);
  g.traverse(o=>{ if(o.isMesh){ o.castShadow=true; o.receiveShadow=true; }});
  world.add(g);
  contactShadow(x,z,2.4,1.5);
}

function tree(x,z){
  const trunkMat = new THREE.MeshStandardMaterial({map:barkTexture, roughness:0.94, metalness:0, color:0xffffff});
  // tronco levemente cônico e torto
  const trunk = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.1,0.2,2.6,16)), trunkMat);
  trunk.position.set(x,1.3,z); trunk.castShadow=true; trunk.receiveShadow=true;
  trunk.rotation.z = (Math.random()-0.5)*0.08; world.add(trunk);
  // galhos
  for(let i=0;i<6;i++){
    const angle = i*Math.PI*2/6 + Math.random()*0.4;
    const branch = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.015,0.04,1.0,8)), trunkMat);
    branch.position.set(x+Math.cos(angle)*0.4, 2.5+i*0.05, z+Math.sin(angle)*0.4);
    branch.rotation.z = Math.cos(angle)*0.6; branch.rotation.x = Math.sin(angle)*0.6;
    branch.castShadow=true; world.add(branch);
  }
  // copa em camadas orgânicas
  const folColors = [0x2a5034,0x356a40,0x457a4e,0x2e6040,0x3d7048,0x285838,0x3a6844];
  for(let layer=0; layer<3; layer++){
    for(let i=0;i<8;i++){
      const angle = i/8*Math.PI*2 + layer*0.4;
      const radius = 0.25 + layer*0.2 + Math.random()*0.2;
      const size = 0.38 + Math.random()*0.28 - layer*0.05;
      const crown = new THREE.Mesh(withAO(new THREE.SphereGeometry(size,12,10)), new THREE.MeshStandardMaterial({
        color:folColors[(i+layer)%7], roughness:0.88, metalness:0
      }));
      crown.position.set(
        x+Math.cos(angle)*radius,
        3.1 + layer*0.55 + (Math.random()-0.3)*0.3,
        z+Math.sin(angle)*radius
      );
      crown.scale.set(1, 0.75+Math.random()*0.15, 1);
      crown.castShadow=true; crown.receiveShadow=true; world.add(crown);
    }
  }
  contactShadow(x,z,2.2,2.2);
}

function bunk(x,z){
  const g = new THREE.Group(); g.position.set(x,0,z);
  // estrutura metálica
  for(const y of [0.45,1.5]){
    // estrado
    const frame = new THREE.Mesh(withAO(new THREE.BoxGeometry(1.8,0.06,2.25)), mat('#5a6e6a',{metalness:0.35,roughness:0.5}));
    frame.position.y=y; frame.castShadow=true; g.add(frame);
    // travessas
    for(let i=-3;i<=3;i++){
      const slat = new THREE.Mesh(withAO(new THREE.BoxGeometry(1.7,0.025,0.08)), mat('#4a5a56',{metalness:0.3,roughness:0.55}));
      slat.position.set(0,y+0.04,i*0.28); g.add(slat);
    }
    // colchão
    const mattress = new THREE.Mesh(withAO(new THREE.BoxGeometry(1.65,0.12,2.05)), mat('#3d5a4a',{roughness:0.9}));
    mattress.position.y=y+0.12; mattress.castShadow=true; g.add(mattress);
    // lençol
    const sheet = new THREE.Mesh(withAO(new THREE.BoxGeometry(1.6,0.02,1.5)), mat('#e8e4d8',{roughness:0.85}));
    sheet.position.set(0.05,y+0.19,0.15); g.add(sheet);
    // travesseiro com volume
    const pillow = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.5,0.12,0.35)), mat('#f0ebe0',{roughness:0.8}));
    pillow.position.set(-0.4,y+0.22,-0.75); pillow.scale.set(1,0.85,1); g.add(pillow);
    // cobertor dobrado
    const blanket = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.85,0.08,0.9)), mat('#2e4a3a',{roughness:0.88}));
    blanket.position.set(0.25,y+0.2,0.4); g.add(blanket);
  }
  // postes verticais com anéis
  for(const dx of [-0.82,0.82]) for(const dz of [-1.05,1.05]){
    const post = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.028,0.028,2.15,12)), mat('#a0a8a0',{metalness:0.6,roughness:0.32}));
    post.position.set(dx,1.08,dz); post.castShadow=true; g.add(post);
    for(const ry of [0.45,1.5]){
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.035,0.008,8,16), mat('#7a8280',{metalness:0.5,roughness:0.4}));
      ring.position.set(dx,ry,dz); ring.rotation.x=Math.PI/2; g.add(ring);
    }
  }
  // escada lateral
  for(let i=0;i<5;i++){
    const step = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.05,0.03,0.55)), mat('#7a8280',{metalness:0.45,roughness:0.38}));
    step.position.set(0.95,0.28+i*0.32,-0.8); g.add(step);
  }
  const rail = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.015,0.015,1.7,8)), mat('#8a9290',{metalness:0.5,roughness:0.35}));
  rail.position.set(0.95,0.95,-0.55); g.add(rail);
  g.traverse(o=>{ if(o.isMesh){ o.castShadow=true; o.receiveShadow=true; }});
  world.add(g);
  contactShadow(x,z,2.4,2.8);
}

function standingFlag(x,z){
  const base = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.3,0.36,0.08,8)), mat('#2a1e14',{roughness:0.55}));
  base.position.set(x,0.04,z); base.castShadow=true; base.receiveShadow=true; world.add(base);
  const pole = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.018,0.024,2.85,14)), mat('#c9cfc9',{metalness:0.85,roughness:0.22}));
  pole.position.set(x,1.45,z); pole.castShadow=true; world.add(pole);
  const finial = new THREE.Mesh(new THREE.SphereGeometry(0.048,12,10), mat('#d4af37',{metalness:0.92,roughness:0.15}));
  finial.position.set(x,2.9,z); finial.castShadow=true; world.add(finial);
  const miniFlag = new THREE.Mesh(new THREE.PlaneGeometry(0.68,0.44,1,1), staticFlagMaterial);
  miniFlag.position.set(x+0.36,2.4,z); miniFlag.castShadow=true; world.add(miniFlag);
  contactShadow(x,z,1.15,1.15);
}

function militaryPoster(x,y,z,rotY=0){
  const g = new THREE.Group(); g.position.set(x,y,z); g.rotation.y=rotY;
  const poster = new THREE.Mesh(new THREE.PlaneGeometry(0.98,1.4), new THREE.MeshStandardMaterial({color:0x1e3a22,roughness:0.78,metalness:0.04}));
  g.add(poster);
  const frame = new THREE.Mesh(new THREE.BoxGeometry(1.04,1.46,0.03), mat('#1a1a1a',{roughness:0.45}));
  frame.position.z=-0.018; g.add(frame);
  const star = new THREE.Mesh(new THREE.CircleGeometry(0.2,5), mat('#d4af37',{metalness:0.75,roughness:0.22}));
  star.position.z=0.012; g.add(star);
  // faixa inferior
  const bar = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.9,0.12,0.01)), mat('#0a1a0e',{roughness:0.7}));
  bar.position.set(0,-0.55,0.01); g.add(bar);
  world.add(g); return g;
}

function auditoriumChair(x,z,rotY=0){
  const g = new THREE.Group(); g.position.set(x,0,z); g.rotation.y=rotY;
  // assento com leve inclinação
  const seat = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.56,0.06,0.5)), mat('#3d5a4a',{roughness:0.88}));
  seat.position.set(0,0.48,0.02); seat.rotation.x=-0.05; g.add(seat);
  // espuma do assento
  const cushion = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.52,0.04,0.46)), mat('#355448',{roughness:0.9}));
  cushion.position.set(0,0.52,0.02); g.add(cushion);
  // encosto curvado (aproximado por 2 peças)
  const backLower = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.56,0.35,0.06)), mat('#3d5a4a',{roughness:0.88}));
  backLower.position.set(0,0.72,-0.22); backLower.rotation.x=-0.08; g.add(backLower);
  const backUpper = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.54,0.28,0.05)), mat('#3d5a4a',{roughness:0.88}));
  backUpper.position.set(0,1.0,-0.26); backUpper.rotation.x=-0.18; g.add(backUpper);
  // apoio de braço com formato L
  for(const dx of [-0.3,0.3]){
    const armPad = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.07,0.04,0.4)), mat('#2a3a2a',{roughness:0.8}));
    armPad.position.set(dx,0.62,-0.02); g.add(armPad);
    const armSup = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.015,0.015,0.2,8)), mat('#1a1a1a',{metalness:0.55,roughness:0.35}));
    armSup.position.set(dx,0.52,-0.15); g.add(armSup);
  }
  // estrutura metálica em tubo
  for(const dx of [-0.24,0.24]){
    for(const dz of [-0.18,0.2]){
      const leg = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.016,0.018,0.48,10)), mat('#1a1a1a',{metalness:0.55,roughness:0.38}));
      leg.position.set(dx,0.24,dz); g.add(leg);
    }
    // travessa lateral
    const cross = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.012,0.012,0.38,8)), mat('#1a1a1a',{metalness:0.5,roughness:0.4}));
    cross.position.set(dx,0.18,0.01); cross.rotation.x=Math.PI/2; g.add(cross);
  }
  // travessa frontal/traseira
  for(const dz of [-0.18,0.2]){
    const bar = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.012,0.012,0.48,8)), mat('#1a1a1a',{metalness:0.5,roughness:0.4}));
    bar.position.set(0,0.12,dz); bar.rotation.z=Math.PI/2; g.add(bar);
  }
  g.traverse(o=>{ if(o.isMesh){ o.castShadow=true; o.receiveShadow=true; }});
  world.add(g); return g;
}

function makeRoom(){
  const floorMat = new THREE.MeshStandardMaterial({
    map:floorTexture, roughness:0.7, metalness:0.04,
    normalMap:floorNormal, normalScale:new THREE.Vector2(0.3,0.3),
    envMapIntensity:0.38
  });
  const floor = new THREE.Mesh(withAO(new THREE.PlaneGeometry(26,28)), floorMat);
  floor.rotation.x=-Math.PI/2; floor.position.set(0,0,-1); floor.receiveShadow=true; world.add(floor);

  const wallMat = new THREE.MeshStandardMaterial({
    map:wallTexture, color:0xffffff, roughness:0.88, metalness:0.02,
    normalMap:surfaceMaps.normal, normalScale:new THREE.Vector2(0.1,0.1)
  });
  function wall(wx,wy,wz,ww,wh,wd){
    const m = new THREE.Mesh(withAO(new THREE.BoxGeometry(ww,wh,wd)), wallMat);
    m.position.set(wx,wy,wz); m.castShadow=true; m.receiveShadow=true; world.add(m);
  }
  wall(0,2.95,-11.25,24.6,5.9,0.3);
  wall(-12.05,2.95,-1,0.3,5.9,22.6);
  wall(12.05,2.95,-1,0.3,5.9,22.6);

  box(0,5.98,-1,24.6,0.28,22.6,'#6a7a70',{roughness:0.82});
  for(let i=-2;i<=2;i++) box(0,5.8,-1+i*4,23.8,0.12,0.25,'#3a4540',{roughness:0.68});

  baseboard(0,0.07,-11.08,24.2,0.05);
  baseboard(-11.88,0.07,-1,0.05,22.2);
  baseboard(11.88,0.07,-1,0.05,22.2);
  crownMolding(0,5.8,-11.08,24.2);
  crownMolding(-11.88,5.8,-1,22.2,Math.PI/2);
  crownMolding(11.88,5.8,-1,22.2,Math.PI/2);

  wallPicture(-4.3,2.95,-11.08,1.55,1.05,0,'#2a1e14');
  wallPicture(0,2.95,-11.08,2.0,1.25,0,'#3a2a1c');
  wallPicture(4.3,2.95,-11.08,1.55,1.05,0,'#2a1e14');
  wallClock(0,4.75,-11.08);
  militaryPoster(-7.9,3.55,-11.08);
  militaryPoster(7.9,3.55,-11.08);

  potPlant(-10.9,0,-9.3);
  potPlant(10.9,0,-9.3);
  potPlant(-10.9,0,3.3);

  doorFrame(-11.88,1.3,-6.3,1.15,2.35,Math.PI/2);
  doorFrame(11.88,1.3,-6.3,1.15,2.35,-Math.PI/2);
  windowFrame(11.88,2.55,3.3,1.35,1.75,-Math.PI/2);
  windowFrame(11.88,2.55,6.3,1.35,1.75,-Math.PI/2);
  windowFrame(-11.88,2.55,3.3,1.35,1.75,Math.PI/2);

  ceilingLamp(-4.3,5.65,-4.3);
  ceilingLamp(4.3,5.65,-4.3);
  ceilingLamp(0,5.65,-1);

  standingFlag(-9.9,-3.9);
  standingFlag(9.9,-3.9);
}

// =====================================================
// SOLDADO — anatomia e proporções realistas
// =====================================================
let soldiers=[];

function getPatrolRoute(n){
  if(n===3) return [{x:-7,z:-4},{x:7,z:-4},{x:7,z:-8},{x:-7,z:-8}];
  return [{x:-6,z:-3.5},{x:6,z:-3.5},{x:6,z:-5.5},{x:-6,z:-5.5}];
}

function makeSoldier(x,z,route,startIdx){
  const g = new THREE.Group();
  g.position.set(x,0,z);

  const uniform='#3a4a2c';
  const uniformDark='#283620';
  const boot='#121212';
  const skin='#b89470';
  const cap='#283620';
  const belt='#161616';
  const brass='#c9a850';

  const hips = new THREE.Group();
  hips.position.y = 0.98;
  g.add(hips);

  // pelve
  const pelvis = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.38,0.16,0.24)), mat(uniform,{roughness:0.86}));
  pelvis.position.y=0.02; pelvis.castShadow=true; hips.add(pelvis);

  // torso (peito + abdomen)
  const chest = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.46,0.38,0.26)), mat(uniform,{roughness:0.86}));
  chest.position.y=0.32; chest.castShadow=true; hips.add(chest);
  const abdomen = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.4,0.18,0.22)), mat(uniform,{roughness:0.86}));
  abdomen.position.y=0.12; hips.add(abdomen);

  // ombros arredondados
  for(const side of [-1,1]){
    const sh = new THREE.Mesh(withAO(new THREE.SphereGeometry(0.1,12,10)), mat(uniform));
    sh.position.set(side*0.28,0.48,0); hips.add(sh);
  }

  // bolsos no peito
  for(const side of [-1,1]){
    const pk = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.13,0.11,0.02)), mat(uniformDark,{roughness:0.85}));
    pk.position.set(side*0.13,0.38,0.14); hips.add(pk);
    const flap = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.13,0.03,0.025)), mat(uniformDark));
    flap.position.set(side*0.13,0.44,0.15); hips.add(flap);
  }

  // cinto e fivela
  const beltM = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.48,0.05,0.28)), mat(belt,{roughness:0.65}));
  beltM.position.y=0.02; hips.add(beltM);
  const buckle = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.06,0.055,0.03)), mat(brass,{metalness:0.88,roughness:0.18}));
  buckle.position.set(0,0.02,0.155); hips.add(buckle);

  // pescoço
  const neck = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.05,0.06,0.1,12)), mat(skin,{roughness:0.72}));
  neck.position.y=0.58; hips.add(neck);

  // cabeça
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.12,16,14), mat(skin,{roughness:0.72}));
  head.position.y=0.74; head.scale.set(1,1.08,0.95); head.castShadow=true; hips.add(head);

  // boné militar
  const capM = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.13,0.14,0.1,18)), mat(cap,{roughness:0.78}));
  capM.position.y=0.84; capM.castShadow=true; hips.add(capM);
  const brim = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.28,0.02,0.16)), mat(cap,{roughness:0.78}));
  brim.position.set(0,0.79,0.1); hips.add(brim);
  // aba traseira
  const visor = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.135,0.135,0.015,18,1,false,0,Math.PI)), mat(cap));
  visor.position.set(0,0.79,-0.02); visor.rotation.x=0.15; hips.add(visor);

  function makeArm(side){
    const arm = new THREE.Group();
    arm.position.set(side*0.28,0.5,0);
    // braço superior
    const upper = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.055,0.06,0.28,12)), mat(uniform));
    upper.position.y=-0.14; upper.castShadow=true; arm.add(upper);
    // cotovelo
    const elbow = new THREE.Mesh(new THREE.SphereGeometry(0.05,10,8), mat(uniform));
    elbow.position.y=-0.28; arm.add(elbow);
    const lower = new THREE.Group();
    lower.position.y=-0.28; arm.add(lower);
    const fore = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.045,0.052,0.26,12)), mat(uniform));
    fore.position.y=-0.13; fore.castShadow=true; lower.add(fore);
    // mão
    const hand = new THREE.Mesh(new THREE.SphereGeometry(0.048,10,8), mat(skin,{roughness:0.7}));
    hand.position.y=-0.28; hand.scale.set(1,0.85,0.7); lower.add(hand);
    return {group:arm, lower};
  }
  const armL = makeArm(-1);
  const armR = makeArm(1);
  hips.add(armL.group); hips.add(armR.group);

  function makeLeg(side){
    const leg = new THREE.Group();
    leg.position.set(side*0.11,0,0);
    // coxa
    const upper = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.07,0.075,0.4,12)), mat(uniform));
    upper.position.y=-0.2; upper.castShadow=true; leg.add(upper);
    // joelho
    const knee = new THREE.Mesh(new THREE.SphereGeometry(0.065,10,8), mat(uniform));
    knee.position.y=-0.4; leg.add(knee);
    const lower = new THREE.Group();
    lower.position.y=-0.4; leg.add(lower);
    // canela
    const shin = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.055,0.065,0.38,12)), mat(uniform));
    shin.position.y=-0.19; shin.castShadow=true; lower.add(shin);
    // bota com salto
    const bootShaft = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.06,0.065,0.18,12)), mat(boot,{roughness:0.55,metalness:0.08}));
    bootShaft.position.y=-0.42; bootShaft.castShadow=true; lower.add(bootShaft);
    const bootSole = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.14,0.05,0.28)), mat(boot,{roughness:0.6}));
    bootSole.position.set(0,-0.52,0.05); bootSole.castShadow=true; lower.add(bootSole);
    const heel = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.12,0.04,0.08)), mat(boot,{roughness:0.55}));
    heel.position.set(0,-0.54,-0.08); lower.add(heel);
    return {group:leg, lower};
  }
  const legL = makeLeg(-1);
  const legR = makeLeg(1);
  hips.add(legL.group); hips.add(legR.group);

  // fuzil nas costas
  const rifle = new THREE.Group();
  rifle.position.set(0.14,0.35,-0.18);
  rifle.rotation.x=0.15; rifle.rotation.z=0.06;
  const stock = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.04,0.2,0.06)), mat('#3a2a18',{roughness:0.7}));
  stock.position.y=-0.15; rifle.add(stock);
  const body = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.045,0.4,0.045)), mat('#1a1a1a',{metalness:0.45,roughness:0.4}));
  body.position.y=0.1; rifle.add(body);
  const barrel = new THREE.Mesh(withAO(new THREE.CylinderGeometry(0.012,0.014,0.38,10)), mat('#2a2a2a',{metalness:0.65,roughness:0.28}));
  barrel.position.y=0.42; rifle.add(barrel);
  const sight = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.02,0.04,0.02)), mat('#1a1a1a',{metalness:0.5,roughness:0.35}));
  sight.position.y=0.28; rifle.add(sight);
  hips.add(rifle);

  // mochila
  const pack = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.32,0.36,0.18)), mat(uniformDark,{roughness:0.84}));
  pack.position.set(0,0.36,-0.22); pack.castShadow=true; hips.add(pack);
  const packFlap = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.3,0.08,0.04)), mat(uniformDark));
  packFlap.position.set(0,0.52,-0.28); hips.add(packFlap);
  // alças
  for(const side of [-1,1]){
    const strap = new THREE.Mesh(withAO(new THREE.BoxGeometry(0.04,0.35,0.02)), mat(uniformDark,{roughness:0.8}));
    strap.position.set(side*0.14,0.4,-0.1); strap.rotation.x=-0.3; hips.add(strap);
  }

  world.add(g);

  return {
    group:g, hips, armL, armR, legL, legR,
    phase:Math.random()*Math.PI*2,
    walking:false,
    route,
    routeIdx:startIdx%route.length,
    target:route[startIdx%route.length],
    speed:0.52+Math.random()*0.14
  };
}




// =====================================================
// TREINO DE TIRO (mecânica tipo range) — opcional no VR
// Controles: gatilho = disparo; mira pelo raio do controle
// =====================================================
let shootMode = false;
let targets = [];
let scoreShoot = { hits: 0, shots: 0 };
const bulletRays = [];
const muzzleFlashes = [];

function clearTargets(){
  for(const t of targets){
    world.remove(t.mesh);
    if(t.mesh.geometry) t.mesh.geometry.dispose();
  }
  targets = [];
}

function spawnTargets(){
  clearTargets();
  const positions = [
    [0, 1.4, -8.5], [-2.5, 1.5, -7.5], [2.5, 1.5, -7.5],
    [-4, 1.8, -9], [4, 1.8, -9], [0, 2.2, -10],
    [-1.5, 1.2, -6.5], [1.5, 1.2, -6.5]
  ];
  for(const [x,y,z] of positions){
    const g = new THREE.Group();
    // silhueta / alvo circular
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.22, 0.35, 24),
      new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.7, metalness: 0.1, side: THREE.DoubleSide })
    );
    const core = new THREE.Mesh(
      new THREE.CircleGeometry(0.12, 20),
      new THREE.MeshStandardMaterial({ color: 0xcc2233, roughness: 0.6, metalness: 0.05, side: THREE.DoubleSide })
    );
    core.position.z = 0.01;
    const post = new THREE.Mesh(
      new THREE.CylinderGeometry(0.03, 0.04, y, 8),
      mat('#5a5a5a', { metalness: 0.4, roughness: 0.5 })
    );
    post.position.y = -y/2;
    g.add(ring); g.add(core); g.add(post);
    g.position.set(x, y, z);
    g.lookAt(0, 1.4, 0);
    world.add(g);
    targets.push({ mesh: g, alive: true, hp: 1, x, y, z });
  }
  scoreShoot = { hits: 0, shots: 0 };
  note('Treino de tiro: ' + targets.length + ' alvos. Gatilho para disparar.');
}

function toggleShootMode(){
  shootMode = !shootMode;
  if(shootMode){
    spawnTargets();
    note('MODO TREINO DE TIRO ativo — gatilho dispara');
  } else {
    clearTargets();
    note('Modo treino desativado');
  }
  updateVR();
}

function fireFromController(controller){
  if(!shootMode || !renderer.xr.isPresenting) return;
  scoreShoot.shots++;
  const ray = rayFromController(controller);
  if(!ray) return;
  // flash
  const flash = new THREE.PointLight(0xffaa55, 2.5, 3, 2);
  const origin = ray.origin.clone();
  flash.position.copy(origin);
  scene.add(flash);
  setTimeout(()=>{ scene.remove(flash); }, 60);
  // spatial gunshot
  try {
    initAudio(); resumeAudio(); ensureSpatialAudio();
    if(audioCtx){
      const t0 = audioCtx.currentTime;
      playSpatialNote(180, t0, 0.08, 0.25, origin);
      playSpatialNote(90, t0+0.02, 0.12, 0.18, origin);
    }
  } catch(e){}
  // ray visual
  const hitDist = 25;
  let hitTarget = null;
  let hitPoint = ray.origin.clone().addScaledVector(ray.direction, hitDist);
  for(const t of targets){
    if(!t.alive) continue;
    const center = new THREE.Vector3(t.x, t.y, t.z);
    const to = center.clone().sub(ray.origin);
    const proj = to.dot(ray.direction);
    if(proj < 0.3 || proj > hitDist) continue;
    const closest = ray.origin.clone().addScaledVector(ray.direction, proj);
    if(closest.distanceTo(center) < 0.45){
      hitTarget = t;
      hitPoint = closest;
      break;
    }
  }
  const geo = new THREE.BufferGeometry().setFromPoints([ray.origin.clone(), hitPoint]);
  const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: hitTarget ? 0xffee88 : 0xaaddff, transparent: true, opacity: 0.85 }));
  scene.add(line);
  setTimeout(()=>{ scene.remove(line); geo.dispose(); }, 80);
  if(hitTarget){
    hitTarget.alive = false;
    scoreShoot.hits++;
    // feedback visual
    hitTarget.mesh.traverse(o=>{
      if(o.isMesh && o.material){
        o.material = o.material.clone();
        o.material.color = new THREE.Color(0x333333);
        o.material.emissive = new THREE.Color(0x000000);
      }
    });
    hitTarget.mesh.scale.set(0.7, 0.7, 0.7);
    try {
      if(audioCtx){
        const t0 = audioCtx.currentTime;
        playSpatialNote(880, t0, 0.1, 0.2, hitPoint);
        playSpatialNote(1320, t0+0.08, 0.15, 0.15, hitPoint);
      }
    } catch(e){}
    note(`Alvo! ${scoreShoot.hits}/${scoreShoot.shots} · restantes ${targets.filter(t=>t.alive).length}`);
    if(targets.every(t=>!t.alive)){
      note(`Treino concluído: ${scoreShoot.hits} acertos em ${scoreShoot.shots} tiros. Gatilho em área vazia respawna.`);
      setTimeout(()=>{ if(shootMode) spawnTargets(); }, 1500);
    }
  }
}


function spawnSoldiers(n){
  soldiers=[];
  const route=getPatrolRoute(n);
  for(let i=0;i<3;i++){
    const start=route[i%route.length];
    const s=makeSoldier(start.x,start.z,route,i+1);
    soldiers.push(s);
  }
}

function updateSoldiers(dt,time){
  for(const s of soldiers){
    if(!s.target)s.target=s.route[s.routeIdx];
    const dx=s.target.x-s.group.position.x;
    const dz=s.target.z-s.group.position.z;
    const dist=Math.hypot(dx,dz);
    if(dist>0.15){
      const step=Math.min(dist,s.speed*dt);
      const ratio=step/dist;
      s.group.position.x+=dx*ratio;
      s.group.position.z+=dz*ratio;
      s.group.rotation.y=Math.atan2(dx,dz);
      s.walking=true;
    }else{
      s.routeIdx=(s.routeIdx+1)%s.route.length;
      s.target=s.route[s.routeIdx];
      s.walking=false;
    }

    if(s.walking){
      s.phase+=dt*8.2;
      const swing=Math.sin(s.phase)*0.72;
      const swing2=Math.sin(s.phase+Math.PI)*0.72;
      s.legL.group.rotation.x=swing;
      s.legR.group.rotation.x=swing2;
      s.legL.lower.rotation.x=Math.max(0,-Math.sin(s.phase)*0.85);
      s.legR.lower.rotation.x=Math.max(0,-Math.sin(s.phase+Math.PI)*0.85);
      s.armL.group.rotation.x=swing2*0.42;
      s.armR.group.rotation.x=swing*0.42;
      s.armL.lower.rotation.x=-0.28;
      s.armR.lower.rotation.x=-0.28;
      s.hips.position.y=0.95+Math.abs(Math.sin(s.phase))*0.045;
      s.hips.rotation.z=Math.sin(s.phase)*0.025;
    }else{
      s.legL.group.rotation.x*=0.88;
      s.legR.group.rotation.x*=0.88;
      s.armL.group.rotation.x*=0.88;
      s.armR.group.rotation.x*=0.88;
      s.legL.lower.rotation.x*=0.88;
      s.legR.lower.rotation.x*=0.88;
      s.armL.lower.rotation.x*=0.88;
      s.armR.lower.rotation.x*=0.88;
      s.hips.rotation.z*=0.88;
      s.hips.position.y=0.95+Math.sin(time*1.15+s.phase)*0.01;
    }
  }
}

// =====================================================
// AMBIENTES
// =====================================================
function buildWorld(n){
  world.traverse(o=>{if(o.isMesh){if(o.geometry)o.geometry.dispose();}});
  world.clear();

  if(n!==3)makeRoom();
  else{
    const groundMat=new THREE.MeshStandardMaterial({map:grassTexture,roughness:0.94,metalness:0,normalMap:surfaceMaps.normal,normalScale:new THREE.Vector2(0.15,0.15)});
    const ground=new THREE.Mesh(withAO(new THREE.PlaneGeometry(75,75,24,24)),groundMat);
    ground.rotation.x=-Math.PI/2;ground.position.set(0,-0.01,-1);ground.receiveShadow=true;
    const pos=ground.geometry.attributes.position;
    for(let i=0;i<pos.count;i++){const x=pos.getX(i),y=pos.getY(i);pos.setZ(i,Math.sin(x*0.28)*0.09+Math.cos(y*0.26)*0.09);}
    pos.needsUpdate=true;ground.geometry.computeVertexNormals();
    world.add(ground);
    for(let i=0;i<16;i++)tree(-32+Math.random()*64,-16-Math.random()*28);
  }

  flag(-8.2,-9.2);
  flag(8.2,-9.2);

  if(n===0){
    building(0,-8.2);
    for(let x=-6;x<=6;x+=2)box(x,0.025,-2,0.12,0.025,6.5,'#e0dcd0',{roughness:0.85});
    cyl(0,0.32,-6.2,1.05,0.65,'#7a8278',20,{roughness:0.8});
  }
  if(n===1){
    for(let x=-5;x<=5;x+=2.5)for(let z=-6;z<=0;z+=2.2)table(x,z);
    box(0,2.8,-10.9,6.5,2.1,0.1,'#1a3a2a',{roughness:0.7});
    wallPicture(0,3.5,-10.8,2.5,1.3,0,'#1a3a2a');
  }
  if(n===2){
    building(-5.2,-7.2);
    for(let x=-1;x<=7.5;x+=0.8)box(x,1.55,-7.6,0.1,3.1,0.12,'#3a4a42',{metalness:0.2,roughness:0.55});
    box(1,3.95,-8.2,8.5,0.55,1.1,'#4a5a52',{roughness:0.65});
  }
  if(n===3){
    for(let x=-8;x<=8;x+=4){box(x,0.68,-5.2,2.1,1.35,1.25,'#8a6b46');tree(x+1.6,-9.5);}
    for(let z=-1;z<=5;z+=2)box(-5.2,0.28,z,2.9,0.32,0.22,'#7a5a35');
  }
  if(n===4){
    for(let x=-6;x<=6;x+=3.2){bunk(x,-6.2);bunk(x,0.2);}
    box(0,2.8,-10.9,5.2,1.7,0.09,'#1e3a2e',{roughness:0.7});
    wallPicture(0,4.5,-10.8,1.9,1.1,0,'#1e3a2e');
  }
  if(n===5){
    for(let x=-7.2;x<=7.2;x+=2.8){
      box(x,2.05,-8.2,2.2,4.1,0.75,'#6a5238');
      for(let y=0.55;y<4;y+=0.72){
        box(x,y,-7.8,2.05,0.04,0.55,'#5c4528');
        for(let b=0;b<6;b++){
          const bcol=['#a8433d','#3d5a8a','#8a6b3d','#3d6b4a','#5a3d6b'][b%5];
          box(x-0.72+b*0.24,y+0.18,-7.85,0.16,0.28,0.32,bcol,{roughness:0.75});
        }
      }
      contactShadow(x,-8.2,2.5,1.1);
    }
    table(0,-2.2);table(3.2,-3.2);
    ceilingLamp(0,5.6,-5.2);
  }
  if(n===6){
    for(let z=-6.2;z<=1.2;z+=1.45)for(let x=-5.2;x<=5.2;x+=1.45)auditoriumChair(x,z);
    box(0,2.9,-10.9,7.8,2.15,0.08,'#1e3a30',{roughness:0.65});
    box(0,0.18,-9.2,7.2,0.35,2.1,'#3a4540',{roughness:0.7});
  }
  if(n===7){
    table(-4.2,-5.2);table(4.2,-5.2);
    box(0,2.6,-10.9,7.2,2.1,0.1,'#1e3a2e',{roughness:0.7});
    for(let x=-6;x<=6;x+=4)ball(x,1.35,-8.2,0.5,'#4a7a5a',{roughness:0.8});
    wallPicture(-3.2,3.9,-10.8,1.7,1.1,0,'#1e3a2e');
    wallPicture(3.2,3.9,-10.8,1.7,1.1,0,'#1e3a2e');
    ceilingLamp(-3.2,5.6,-3.2);ceilingLamp(3.2,5.6,-3.2);
  }
  if(n===8){
    for(let x=-8;x<=8;x+=4){cyl(x,1.55,-7.2,0.26,3.1,'#8a988c',16,{roughness:0.75});tree(x,-9.5);}
    box(0,0.32,-6.2,5.2,0.65,2.1,'#7a8278',{roughness:0.8});
  }
  if(n===9){
    for(let x=-5.2;x<=5.2;x+=3.2){
      box(x,1.05,-7.2,2.1,0.42,0.95,'#2e4240',{metalness:0.3,roughness:0.5});
      box(x,2.4,-9.2,1.9,1.25,0.12,'#121a22',{roughness:0.6});
      box(x,3.05,-9.25,1.95,0.06,0.14,'#0a1018',{roughness:0.5});
      const screen=new THREE.Mesh(new THREE.PlaneGeometry(1.8,1.15),new THREE.MeshStandardMaterial({
        color:0x1a4060,emissive:0x2a65a0,emissiveIntensity:0.6,roughness:0.25,metalness:0.25
      }));
      screen.position.set(x,2.4,-9.12);world.add(screen);
      contactShadow(x,-7.2,2.3,1.2);
    }
    box(0,4.0,-10.9,7.2,0.18,0.16,'#3ab89a',{emissive:'#2a9a80',emissiveIntensity:0.3,roughness:0.4});
    ceilingLamp(-3.2,5.6,-4.2);ceilingLamp(3.2,5.6,-4.2);
  }

  spawnSoldiers(n);
  if(shootMode) spawnTargets();
  applyLight();
  renderer.shadowMap.needsUpdate=true;
}

function applyLight(){
  const night=state.settings.lighting==='night';
  ambient.intensity=night?0.85:1.5;
  ambient.color.setHex(night?0x5060a0:0xd4e8ff);
  sun.intensity=night?0.6:3.4;
  sun.color.setHex(night?0x8aa0d0:0xfff1d6);
  fill.intensity=night?0.12:0.42;
  rim.intensity=night?0.2:0.55;
  bounce.intensity=night?0.08:0.22;
  scene.environment=night?iblNightTarget.texture:iblDayTarget.texture;
  if(scene.fog){
    scene.fog.color.setHex(night?0x1a2030:0x8aafb2);
    scene.fog.density=night?0.008:0.004;
  }
  renderer.toneMappingExposure=night?1.25:1.4;
  if(skyMesh){
    const u=skyMesh.material.uniforms;
    u.uNight.value=night?1.0:0.0;
    u.uIntensity.value=night?0.6:1.0;
  }
  renderer.shadowMap.needsUpdate=true;
}

// =====================================================
// PAINÉIS VR
// =====================================================
const WIDTH=2048,HEIGHT=1536; // estável no Quest 3S (4096 enegrecia os painéis) // texto nítido Quest 3S (~20 PPD) // alta nitidez de texto no Quest 3S (~20 PPD)
const panels={};
const panelMeshes=[];
const raycaster=new THREE.Raycaster();
const tmpMatrix=new THREE.Matrix4();
let hovered=null;


function refreshPanelTexture(p){
  if(!p||!p.texture)return;
  p.texture.generateMipmaps=false;
  p.texture.minFilter=THREE.LinearFilter;
  p.texture.magFilter=THREE.LinearFilter;
  refreshPanelTexture(p);
}
function makePanel(id,w,h,x,y,z){
  const canvas=document.createElement('canvas');
  canvas.width=WIDTH;
  canvas.height=HEIGHT;
  const ctx=canvas.getContext('2d',{alpha:false,willReadFrequently:false});
  // Preenche já na criação (evita painel preto se o draw falhar)
  ctx.fillStyle='#0c1c17';
  ctx.fillRect(0,0,WIDTH,HEIGHT);
  ctx.fillStyle='#7dffb0';
  ctx.font='bold 64px Arial';
  ctx.fillText('PMSC 2026', 80, 120);
  ctx.fillStyle='#c8e8d4';
  ctx.font='36px Arial';
  ctx.fillText('Carregando painel…', 80, 180);
  const texture=new THREE.CanvasTexture(canvas);
  // NoColorSpace evita textura “apagada” por double-gamma no WebXR do Quest
  texture.colorSpace=THREE.NoColorSpace;
  texture.generateMipmaps=false;
  texture.minFilter=THREE.LinearFilter;
  texture.magFilter=THREE.LinearFilter;
  texture.anisotropy=1;
  texture.needsUpdate=true;
  const group=new THREE.Group();group.position.set(x,y,z);scene.add(group);
  // borda sutil no painel
  const border=new THREE.Mesh(
    new THREE.PlaneGeometry(w+0.04,h+0.04),
    new THREE.MeshBasicMaterial({color:0x0e2a1c,side:THREE.DoubleSide,toneMapped:false})
  );
  border.position.z=-0.008;group.add(border);
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({map:texture,color:0xffffff,side:THREE.DoubleSide,toneMapped:false,transparent:false}));
  group.add(mesh);
  panels[id]={id,canvas,ctx,texture,group,mesh,regions:[],w,h};
  panelMeshes.push(mesh);mesh.userData.id=id;
}
makePanel('main',3.4,2.55,0,1.55,-2.8);
makePanel('left',1.7,2.1,-3.4,1.55,-3.0);
makePanel('right',1.7,2.1,3.4,1.55,-3.0);

function panelPositionReset(){
  panels.main.group.position.set(0,Number(state.settings.panelHeight||1.55),-Number(state.settings.distance||2.8));
  panels.main.group.scale.setScalar(Number(state.settings.panelScale));
  panels.left.group.position.set(-3.4,1.55,-3.0);
  panels.right.group.position.set(3.4,1.55,-3.0);
  for(const p of Object.values(panels))p.group.rotation.set(0,0,0);
}
function resetPanelPositions(){state.panels={};panelPositionReset();safeStore();updateVR();}
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));

function round(ctx,x,y,w,h,r=16){ctx.beginPath();ctx.roundRect(x,y,w,h,r);}
function text(ctx,t,x,y,size=46,color='#f3fff4',weight='700'){
  ctx.font=`${weight} ${size}px system-ui,Arial,sans-serif`;
  ctx.textBaseline='alphabetic';
  ctx.imageSmoothingEnabled=false;
  // sombra leve = contorno legível em VR
  ctx.fillStyle='rgba(0,0,0,0.55)';
  ctx.fillText(String(t),x+2,y+2);
  ctx.fillStyle=color;
  ctx.fillText(String(t),x,y);
}
function wrapped(ctx,content,width,size){
  ctx.font=`700 ${size}px Arial`;const lines=[];
  for(const paragraph of String(content).split('\n')){let line='';for(const word of paragraph.split(/\s+/)){const trial=line?line+' '+word:word;if(ctx.measureText(trial).width>width&&line){lines.push(line);line=word;}else line=trial;}lines.push(line);}
  return lines;
}
function region(p,x,y,w,h,action){p.regions.push({x,y,w,h,action});}


function background(p,title){
  const c=p.ctx; p.regions=[];
  c.imageSmoothingEnabled=true; c.imageSmoothingQuality='high';
  // fundo moderno: gradiente escuro + vinheta
  const bg=c.createLinearGradient(0,0,0,HEIGHT);
  bg.addColorStop(0,'#0a1612'); bg.addColorStop(0.45,'#0c1c17'); bg.addColorStop(1,'#081410');
  c.fillStyle=bg; c.fillRect(0,0,WIDTH,HEIGHT);
  // grade sutil (tech/military modern)
  c.strokeStyle='rgba(80,140,110,0.06)'; c.lineWidth=1;
  for(let x=0;x<WIDTH;x+=64){ c.beginPath(); c.moveTo(x,0); c.lineTo(x,HEIGHT); c.stroke(); }
  for(let y=0;y<HEIGHT;y+=64){ c.beginPath(); c.moveTo(0,y); c.lineTo(WIDTH,y); c.stroke(); }
  // header bar
  const hg=c.createLinearGradient(0,0,WIDTH,0);
  hg.addColorStop(0,'#145a3a'); hg.addColorStop(0.5,'#1a7048'); hg.addColorStop(1,'#145a3a');
  c.fillStyle=hg; round(c,20,18,WIDTH-40,128,20); c.fill();
  // accent line under header
  c.fillStyle='#7dffb0'; round(c,20,140,WIDTH-40,4,2); c.fill();
  // title
  text(c,title,48,78,52,'#f4fff8','700');
  text(c,'☰  ARRASTE PELA BARRA SUPERIOR  ·  GATILHO SELECIONA',48,118,26,'#b8efd0','500');
  // outer frame
  c.strokeStyle='rgba(122,255,176,0.45)'; c.lineWidth=3;
  round(c,12,12,WIDTH-24,HEIGHT-24,24); c.stroke();
  // drag zone
  region(p,0,0,WIDTH,160,'drag');
}

function vrButton(p,label,x,y,w,h,action,color='#1a5c3e',size=40){
  const c=p.ctx;
  const hot=hovered?.panel===p.id && hovered?.action===action;
  // shadow
  c.fillStyle='rgba(0,0,0,0.35)';
  round(c,x+3,y+4,w,h,16); c.fill();
  // body
  const g=c.createLinearGradient(x,y,x,y+h);
  if(hot){ g.addColorStop(0,'#3aa86a'); g.addColorStop(1,'#2a8050'); }
  else {
    // parse hex-ish solid
    c.fillStyle=color;
  }
  if(hot){ c.fillStyle=g; }
  else { c.fillStyle=color; }
  round(c,x,y,w,h,16); c.fill();
  // border
  c.strokeStyle=hot?'#e8fff0':'rgba(100,180,140,0.55)';
  c.lineWidth=hot?4:2.5;
  round(c,x,y,w,h,16); c.stroke();
  // top highlight
  c.fillStyle=hot?'rgba(255,255,255,0.12)':'rgba(255,255,255,0.06)';
  round(c,x+2,y+2,w-4,Math.min(h*0.35,28),12); c.fill();
  const lines=wrapped(c,label,w-40,size);
  lines.slice(0,2).forEach((line,i)=>text(c,line,x+20,y+Math.min(h-14, 42+i*(size+4)),size,'#f5fff8','700'));
  region(p,x,y,w,h,action);
}

function drawOptionCard(p, letter, textContent, x, y, w, h, action, state){
  // state: 'idle' | 'selected' | 'correct' | 'wrong'
  const c=p.ctx;
  const hot=hovered?.panel===p.id && hovered?.action===action;
  let bg='#152a22', border='rgba(90,160,120,0.5)', letterBg='#1e5a3e', letterCol='#c8ffd8';
  if(state==='selected'){ bg='#1a3a55'; border='#5eb0ff'; letterBg='#1e5a8a'; letterCol='#d0eaff'; }
  if(state==='correct'){ bg='#0f3d28'; border='#50ff9d'; letterBg='#147a48'; letterCol='#e0ffe8'; }
  if(state==='wrong'){ bg='#3a1a22'; border='#ff8e91'; letterBg='#8a3040'; letterCol='#ffd0d4'; }
  if(hot && state==='idle'){ bg='#1a3a2e'; border='#9af6bc'; }
  // card shadow
  c.fillStyle='rgba(0,0,0,0.3)';
  round(c,x+2,y+3,w,h,14); c.fill();
  c.fillStyle=bg;
  round(c,x,y,w,h,14); c.fill();
  c.strokeStyle=border; c.lineWidth=hot?3.5:2.5;
  round(c,x,y,w,h,14); c.stroke();
  // letter badge
  const bw=72, bh=Math.min(h-20,72);
  c.fillStyle=letterBg;
  round(c,x+14,y+(h-bh)/2,bw,bh,12); c.fill();
  text(c,letter,x+14+bw/2-16,y+h/2+16,48,letterCol,'800');
  // option text
  const lines=wrapped(c,textContent,w-bw-55,38);
  let ty=y+Math.max(36, (h - lines.length*44)/2 + 32);
  for(const line of lines.slice(0,4)){
    text(c,line,x+bw+30,ty,38,'#f2faf5','600');
    ty+=44;
  }
  region(p,x,y,w,h,action);
}

function drawMain(){
  const p=panels.main, c=p.ctx, s=state.session, q=currentQuestion(), a=currentPool();
  background(p,'PMSC 2026  ·  SALA DE ESTUDO');
  if(!q){
    text(c,'AGUARDANDO QUESTÕES',80,420,56,'#e8fff0','700');
    text(c,'Atualize o banco JSON no menu lateral ou use Demonstração.',80,500,36,'#a8cbb8','500');
    // empty state card
    c.fillStyle='rgba(20,60,45,0.5)';
    round(c,80,560,WIDTH-160,180,18); c.fill();
    text(c,'Toque em “Atualizar JSON” ou “Demonstração” para começar.',100,650,34,'#b8efd0','500');
    refreshPanelTexture(p); return;
  }

  // meta bar
  const pct = Math.round(((s.index+1)/Math.max(1,a.length))*100);
  c.fillStyle='rgba(15,40,30,0.85)';
  round(c,40,168,WIDTH-80,88,14); c.fill();
  text(c,`${s.index+1}  /  ${a.length}`,60,212,36,'#7dffb0','700');
  text(c,q.subject,220,200,32,'#e8fff0','600');
  text(c,q.topic,220,238,26,'#9ab8a8','500');
  // progress bar
  c.fillStyle='#1a3a2a'; round(c,WIDTH-420,198,340,18,9); c.fill();
  c.fillStyle='#4dff9a'; round(c,WIDTH-420,198,Math.max(12,340*pct/100),18,9); c.fill();
  text(c,pct+'%',WIDTH-70,214,24,'#c8ffd8','600');

  const size=Math.round(44*Number(state.settings.fontSize)/120);
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

  const opts=[];
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
      opts.push({i,option,st,oh});
      blocks.push({kind:'option',i,option,st,height:oh+12});
    });
    const chosen=s.answers[q.id];
    if(chosen!==undefined&&(s.mode!=='exam'||s.feedback==='immediate'||s.finished)){
      if(q.explanation) addNote('COMENTÁRIO: '+q.explanation);
      if(q.reference) addNote('REFERÊNCIA: '+q.reference);
    }
  }

  const viewTop=275, viewBottom=1280, viewH=viewBottom-viewTop;
  const total=blocks.reduce((sum,b)=>sum+b.height+10,0);
  s.scroll=clamp(s.scroll,0,Math.max(0,total-viewH));
  c.save();
  c.beginPath(); c.rect(36,viewTop,WIDTH-72,viewH); c.clip();

  let y=viewTop - s.scroll;
  for(const b of blocks){
    if(y+b.height >= viewTop-20 && y <= viewBottom+20){
      if(b.kind==='question'){
        c.fillStyle='rgba(18,48,38,0.9)';
        round(c,48,y,WIDTH-96,b.height-8,16); c.fill();
        c.strokeStyle='rgba(120,220,160,0.25)'; c.lineWidth=2;
        round(c,48,y,WIDTH-96,b.height-8,16); c.stroke();
        // label
        text(c,'ENUNCIADO',64,y+32,22,'#7dffb0','700');
        let ty=y+70;
        for(const line of b.lines){
          text(c,line,64,ty,size,'#ffffff','600');
          ty+=lineH+4;
        }
      } else if(b.kind==='option'){
        const letter=String.fromCharCode(65+b.i);
        drawOptionCard(p, letter, b.option, 48, y, WIDTH-96, b.height-10, 'answer:'+b.i, b.st);
      } else if(b.kind==='note'){
        c.fillStyle='rgba(20,50,40,0.7)';
        round(c,48,y,WIDTH-96,b.height-8,12); c.fill();
        let ty=y+40;
        for(const line of b.lines){
          text(c,line,64,ty,size-4,'#c8e8d4','500');
          ty+=lineH;
        }
      }
    }
    y += b.height+10;
  }
  c.restore();

  // footer toolbar
  c.fillStyle='rgba(8,20,16,0.95)';
  c.fillRect(20,1295,WIDTH-40,220);
  c.fillStyle='#7dffb0'; c.fillRect(20,1295,WIDTH-40,3);

  const bw=300, bh=100, gap=18, baseY=1320;
  let bx=50;
  vrButton(p,'▲ SUBIR',bx,baseY,bw,bh,'scrollUp','#1a4a35',36); bx+=bw+gap;
  vrButton(p,'▼ DESCER',bx,baseY,bw,bh,'scrollDown','#1a4a35',36); bx+=bw+gap;
  vrButton(p,'◀ ANTERIOR',bx,baseY,bw,bh,'prev','#1e3a55',36); bx+=bw+gap;
  vrButton(p,'PRÓXIMA ▶',bx,baseY,bw,bh,'next','#1e5540',36); bx+=bw+gap;
  const lastLabel = s.mode==='flash' ? 'VIRAR' : s.mode==='exam' ? 'FINALIZAR' : '★ FAVORITO';
  const lastAct = s.mode==='flash' ? 'flip' : s.mode==='exam' ? 'finish' : 'favorite';
  vrButton(p,lastLabel,bx,baseY,WIDTH-bx-50,bh,lastAct,s.mode==='exam'?'#5a3020':'#1a5c3e',36);

  const footer = s.mode==='exam'&&s.minutes
    ? `TEMPO: ${Math.max(0,Math.ceil((s.minutes*60000-(Date.now()-s.start))/60000))} min  ·  SIMULADO`
    : s.mode==='flash' ? 'MODO FLASHCARD' : s.mode==='exam' ? 'MODO SIMULADO' : 'MODO ESTUDO';
  text(c,footer,55,1475,28,'#8ecfad','600');
  refreshPanelTexture(p);
}

function drawSide(id){
  const p=panels[id], c=p.ctx;
  background(p, id==='left' ? 'AMBIENTES 3D' : 'DESEMPENHO');
  if(id==='left'){
    let y=185;
    environments.forEach((name,i)=>{
      const active=i===state.settings.env;
      vrButton(p, `${String(i+1).padStart(2,'0')}  ·  ${name}`, 40, y, WIDTH-80, 92, 'env:'+i, active?'#1e7048':'#152a22', 36);
      y+=104;
    });
    vrButton(p,'REPOSICIONAR PAINÉIS',40,HEIGHT-130,WIDTH-80,90,'resetPanels','#1a3a55',36);
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
    let y=185;
    for(let i=0;i<cards.length;i+=2){
      for(let j=0;j<2;j++){
        if(!cards[i+j]) continue;
        const [lab,val]=cards[i+j];
        const x=40+j*((WIDTH-100)/2+20);
        const w=(WIDTH-100)/2;
        c.fillStyle='rgba(18,48,38,0.9)';
        round(c,x,y,w,130,16); c.fill();
        c.strokeStyle='rgba(100,200,150,0.3)'; c.lineWidth=2;
        round(c,x,y,w,130,16); c.stroke();
        text(c,val,x+24,y+70,48,'#7dffb0','800');
        text(c,lab,x+24,y+110,24,'#a8cbb8','500');
      }
      y+=150;
    }
    const modes=[['QUESTÕES','study'],['SIMULADO','exam'],['FLASHCARDS','flash'],['REVISÃO','review']];
    y=HEIGHT-480;
    modes.forEach(([name,mode],i)=>{
      vrButton(p,name,40,y+i*105,WIDTH-80,92,'go:'+mode,'#1a4a35',36);
    });
  }
  refreshPanelTexture(p);
}

function updateVR(){if(!panels.main)return;drawMain();drawSide('left');drawSide('right');}
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

function beginDrag(p,source,kind){
  const start=new THREE.Vector3();source.getWorldPosition(start);
  dragging={p,source,kind,offset:p.group.position.clone().sub(start)};
  note('Movendo painel: solte para fixar.');
}
function endDrag(kind,index){
  if(dragging?.kind===kind&&dragging?.index===index){
    const p=dragging.p;
    state.panels[p.id]=[p.group.position.x,p.group.position.y,p.group.position.z];
    dragging=null;safeStore();
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
  const circle=new THREE.Mesh(
    new THREE.RingGeometry(0.28,0.38,32),
    new THREE.MeshBasicMaterial({color:0x4a9a7a,transparent:true,opacity:0.35,side:THREE.DoubleSide})
  );
  circle.rotation.x=-Math.PI/2;
  circle.position.set(x,0.02,z);
  circle.userData.destination=new THREE.Vector3(x,0,z);
  scene.add(circle);
  teleportMarkers.push(circle);
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
  // Otimizado para Meta Quest 3S: 1832×1920 por olho, ~20 PPD, FOV 96°H/90°V, até 120 Hz
  const q=state.settings.quality;
  // Pixel ratio: no headset o XR gerencia; no desktop limitar
  const pr = q==='low' ? 1 : q==='high' ? Math.min(devicePixelRatio, 2) : Math.min(devicePixelRatio, 1.5);
  renderer.setPixelRatio(pr);
  // Foveated rendering: low foveation = mais nítido nas bordas (Quest 3S Fresnel já perde nas bordas)
  if(typeof renderer.xr.setFoveation==='function'){
    renderer.xr.setFoveation(q==='low' ? 0.7 : q==='high' ? 0.2 : 0.45);
  }
  // Shadow map: 2048 em Alta aproveita a densidade de ~20 PPD
  const res = q==='low' ? 512 : q==='high' ? 2048 : 1024;
  if(sun.shadow.mapSize.x !== res){
    if(sun.shadow.map){ sun.shadow.map.dispose(); sun.shadow.map = null; }
    sun.shadow.mapSize.set(res, res);
    renderer.shadowMap.needsUpdate = true;
  }
  // Framebuffer scale: 1.0 ≈ nativo 1832×1920; >1 supersampling (custa GPU)
  // Alta: 1.15 leve supersampling para compensar lentes Fresnel
  const fb = q==='low' ? 0.9 : q==='high' ? 1.05 : 1.0; // leve super-sample na Alta
  if(typeof renderer.xr.setFramebufferScaleFactor === 'function'){
    renderer.xr.setFramebufferScaleFactor(fb);
  }
  // Prefer 90Hz+ quando disponível (Quest 3S até 120)
  try {
    if(renderer.xr.getSession){ /* session rate set on enter */ }
  } catch(e){}
}
function syncSettings(){
  for(const k of ['lighting','quality','fontSize','distance','panelHeight','panelScale','speed','snap','volume','playerHeight','vignette','comfort']){ if($(k)) $(k).value=state.settings[k]; }
  $('environment').value=state.settings.env;
  configureQuality();applyLight();panelPositionReset();
  for(const [id,v] of Object.entries(state.panels||{})){
    if(panels[id]&&Array.isArray(v)&&v.length===3&&v.every(Number.isFinite))panels[id].group.position.set(...v);
  }
}

let lastSecond=0;
const clock=new THREE.Clock();

renderer.setAnimationLoop(()=>{
  const dt=Math.min(clock.getDelta(),0.05);
  const time=performance.now()*0.001;

  if(flagMaterial.userData.shader)flagMaterial.userData.shader.uniforms.uTime.value=time;

  updateSoldiers(dt,time);

  // Em VR o tamanho vem do headset — NÃO redimensionar pelo #scene (causa tela preta)
  if(!renderer.xr.isPresenting){
    const host = $('scene');
    const w = host ? host.clientWidth : 0;
    const h = host ? host.clientHeight : 0;
    if(w && h){
      const pr = renderer.getPixelRatio();
      if(renderer.domElement.width !== Math.round(w*pr) || renderer.domElement.height !== Math.round(h*pr)){
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
      }
    }
  }

  if(renderer.xr.isPresenting){ try {
    const session=renderer.xr.getSession();
    if(!session) throw Error("no session");
    for(const src of session.inputSources){
      const gp=src.gamepad;if(!gp)continue;
      let ax=0,az=0;
      if(gp.axes.length>=4){ax=gp.axes[2]||0;az=gp.axes[3]||0;}
      else{ax=gp.axes[0]||0;az=gp.axes[1]||0;}
      if(src.handedness==='left'&&(Math.abs(ax)>0.18||Math.abs(az)>0.18)){
        const dir=new THREE.Vector3();
        renderer.xr.getCamera().getWorldDirection(dir);
        dir.y=0;dir.normalize();
        const right=new THREE.Vector3().crossVectors(dir,new THREE.Vector3(0,1,0)).normalize();
        const speed=Number(state.settings.speed);
        rig.position.addScaledVector(dir,-az*dt*speed);
        rig.position.addScaledVector(right,ax*dt*speed);
        rig.position.x=clamp(rig.position.x,-9,9);
        rig.position.z=clamp(rig.position.z,-8,6);
        isLocomoting = true;
        // intensidade proporcional à velocidade do stick (conforto)
        const mag = Math.min(1, Math.hypot(ax, az));
        moveVignetteTarget = (Number(state.settings.comfort) ? mag : 0) * (Number(state.settings.vignette)||100)/100 * 0.55;
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
  } catch(xrErr){ console.warn('XR frame', xrErr); }
  }
  // Vinheta dinâmica: suaviza ao parar de andar (comfort locomotion)
  if(!isLocomoting) moveVignetteTarget *= 0.0;
  isLocomoting = false;
  moveVignetteCurrent += (moveVignetteTarget - moveVignetteCurrent) * Math.min(1, dt * 8);
  if(renderer.xr.isPresenting){
    // segurança: nada de vinheta / fog no imersivo
    if(vignetteMesh) vignetteMesh.visible = false;
    if(vignetteUniforms) vignetteUniforms.uIntensity.value = 0;
    moveVignetteCurrent = 0;
    moveVignetteTarget = 0;
    if(scene.fog) scene.fog = null;
  } else if(vignetteUniforms && vignetteMesh){
    const vi = moveVignetteCurrent;
    vignetteUniforms.uIntensity.value = vi;
    vignetteUniforms.uRadius.value = 0.78 + (1 - vi) * 0.15;
    vignetteMesh.visible = vi > 0.02;
  }
  // Áudio espacial: ouvinte segue a cabeça
  if(audioCtx && listenerNode){
    try {
      const hp = new THREE.Vector3();
      if(renderer.xr.isPresenting) renderer.xr.getCamera().getWorldPosition(hp);
      else camera.getWorldPosition(hp);
      if(listenerNode.positionX){
        listenerNode.positionX.setValueAtTime(hp.x, audioCtx.currentTime);
        listenerNode.positionY.setValueAtTime(hp.y, audioCtx.currentTime);
        listenerNode.positionZ.setValueAtTime(hp.z, audioCtx.currentTime);
      } else if(listenerNode.setPosition){
        listenerNode.setPosition(hp.x, hp.y, hp.z);
      }
      const fwd = new THREE.Vector3();
      if(renderer.xr.isPresenting) renderer.xr.getCamera().getWorldDirection(fwd);
      else camera.getWorldDirection(fwd);
      if(listenerNode.forwardX){
        listenerNode.forwardX.setValueAtTime(fwd.x, audioCtx.currentTime);
        listenerNode.forwardY.setValueAtTime(fwd.y, audioCtx.currentTime);
        listenerNode.forwardZ.setValueAtTime(fwd.z, audioCtx.currentTime);
        listenerNode.upX.setValueAtTime(0, audioCtx.currentTime);
        listenerNode.upY.setValueAtTime(1, audioCtx.currentTime);
        listenerNode.upZ.setValueAtTime(0, audioCtx.currentTime);
      }
    } catch(e){}
  }
  try {
    if(renderer.xr.isPresenting){
      // mantém cena clara a cada frame (evita estado escuro residual)
      if(scene.fog) scene.fog = null;
      if(!scene.background) scene.background = new THREE.Color(0x9ec4d0);
    }
  } catch(err){ console.warn('xr frame prep', err); }

  try {
    renderer.render(scene, camera);
  } catch(err){
    console.error('render error', err);
  }
});



// Marcador de status VR (MeshBasic = visível sem luz)

// ---- Canvas: no Quest o WebXR precisa do canvas em tela cheia (não dentro de #scene) ----
let canvasOriginalParent = null;
function mountCanvasForXR(){
  const canvas = renderer.domElement;
  if(!canvasOriginalParent) canvasOriginalParent = canvas.parentElement;
  document.body.appendChild(canvas);
  canvas.style.cssText = [
    'position:fixed',
    'inset:0',
    'width:100%','height:100%',
    'max-width:none','max-height:none',
    'z-index:2147483646',
    'margin:0','padding:0',
    'border:none','border-radius:0',
    'background:#9ec4d0',
    'display:block'
  ].join(';');
  // tamanho real do framebuffer = tela do headset
  try {
    const w = window.innerWidth || 1832;
    const h = window.innerHeight || 1920;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(1, h);
    camera.updateProjectionMatrix();
  } catch(e){}
}

function restoreCanvasFromXR(){
  const canvas = renderer.domElement;
  canvas.style.cssText = '';
  const host = document.getElementById('scene') || canvasOriginalParent;
  if(host) host.appendChild(canvas);
  try {
    const w = host.clientWidth || 640;
    const h = host.clientHeight || 360;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(1, h);
    camera.updateProjectionMatrix();
  } catch(e){}
}

function forceBrightScene(){
  // Cena legível no Quest sem "estouro" de luz — visual realista
  const night = state.settings.lighting === 'night';
  scene.background = new THREE.Color(night ? 0x0c1420 : 0x87aec0);
  scene.fog = null;
  renderer.setClearColor(night ? 0x0c1420 : 0x87aec0, 1);
  renderer.toneMappingExposure = night ? 1.15 : 1.25;
  if(typeof vrAmbientBoost !== 'undefined') vrAmbientBoost.intensity = night ? 0.35 : 0.45;
  ambient.intensity = night ? 0.75 : 1.35;
  ambient.color.setHex(night ? 0x6080b0 : 0xd8e8f8);
  sun.intensity = night ? 0.45 : 2.8;
  sun.color.setHex(night ? 0x9eb0e0 : 0xfff2d8);
  sun.position.set(8, 14, 6);
  if(sun.target) sun.target.position.set(0, 0, -2);
  fill.intensity = night ? 0.25 : 0.55;
  rim.intensity = night ? 0.3 : 0.55;
  if(typeof bounce !== 'undefined' && bounce) bounce.intensity = night ? 0.12 : 0.28;
  try {
    scene.environment = night ? iblNightTarget.texture : iblDayTarget.texture;
  } catch(e){}
  if(skyMesh){
    skyMesh.visible = true;
    try {
      if(skyMesh.material && skyMesh.material.uniforms){
        skyMesh.material.uniforms.uNight.value = night ? 1.0 : 0.0;
        skyMesh.material.uniforms.uIntensity.value = night ? 0.7 : 1.15;
      }
    } catch(e){}
  }
  world.visible = true;
  renderer.shadowMap.needsUpdate = true;
}



async function enterVR(){
  try{
    if(renderer.xr.isPresenting){
      await renderer.xr.getSession().end();
      return;
    }
    if(!navigator.xr || !(await navigator.xr.isSessionSupported('immersive-vr'))){
      throw Error('WebXR imersivo não disponível neste navegador');
    }

    // CRÍTICO no Quest: canvas em fullscreen no body ANTES da sessão
    mountCanvasForXR();
    forceBrightScene();
    if(world && world.children.length < 5) buildWorld(+state.settings.env || 0);
    
    // Reference space preferindo local-floor
    try {
      if(typeof renderer.xr.setReferenceSpaceType === 'function'){
        renderer.xr.setReferenceSpaceType('local-floor');
      }
    } catch(e){}

    const session = await navigator.xr.requestSession('immersive-vr', {
      optionalFeatures: ['local-floor', 'bounded-floor']
    });

    try {
      if(typeof renderer.xr.setFramebufferScaleFactor === 'function'){
        renderer.xr.setFramebufferScaleFactor(1.0);
      }
    } catch(e){}

    await renderer.xr.setSession(session);

    forceBrightScene();
        rig.position.set(0, 0, 0);
    rig.rotation.set(0, 0, 0);

    try {
      if(typeof vignetteMesh !== 'undefined' && vignetteMesh){
        vignetteMesh.visible = false;
        if(vignetteMesh.parent) vignetteMesh.parent.remove(vignetteMesh);
      }
    } catch(e){}
    if(typeof moveVignetteTarget !== 'undefined'){
      moveVignetteTarget = 0;
      moveVignetteCurrent = 0;
    }

    renderer.shadowMap.enabled = state.settings.quality !== "low";
    renderer.shadowMap.needsUpdate = true;

    try{
      drawMain();
      drawSide('left');
      drawSide('right');
      updateVR();
      // segundo frame: algumas GPUs do Quest só sobem a textura no 2º needsUpdate
      requestAnimationFrame(()=>{ try{ drawMain(); drawSide('left'); drawSide('right'); }catch(e){} });
    }catch(e){ console.warn(e); }
    $('vrButton').textContent = 'SAIR DO VR';
    session.addEventListener('end', () => {
            restoreCanvasFromXR();
      $('vrButton').textContent = 'ENTRAR EM VR';
      dragging = null;
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.needsUpdate = true;
      try {
        if(typeof vignetteMesh !== 'undefined' && vignetteMesh && !vignetteMesh.parent){
          camera.add(vignetteMesh);
        }
      } catch(e){}
      scene.fog = new THREE.FogExp2(0x8aafb2, 0.004);
      applyLight();
      note('Saiu do VR');
    });

    try { playFanfare(); } catch(e){}
    note('VR imersivo • Academia Militar PMSC 2026 • painéis nítidos');
  } catch(e) {
    console.error(e);
    restoreCanvasFromXR();
    note('Não foi possível entrar em VR: ' + e.message);
  }
}


for(const [p,label] of pages){const b=button(label,()=>go(p),$('navigation'));b.dataset.page=p;}
environments.forEach((name,i)=>{$('environment').add(new Option(name,String(i)));});
$('environment').onchange=()=>{setEnvironment(+$('environment').value);};
$('lighting').onchange=()=>{state.settings.lighting=$('lighting').value;applyLight();safeStore();};
$('quality').onchange=()=>{state.settings.quality=$('quality').value;configureQuality();safeStore();};
for(const key of ['fontSize','distance','panelHeight','panelScale','speed','snap']){
  $(key).oninput=()=>{state.settings[key]=+$(key).value;if(['distance','panelHeight','panelScale'].includes(key))panelPositionReset();safeStore();updateVR();};
}
$('volume').oninput=()=>{
  state.settings.volume=+$('volume').value;
  if(masterGain)masterGain.gain.value=state.settings.volume/100;
  safeStore();
};
if($('playerHeight')){
  $('playerHeight').oninput=()=>{
    state.settings.playerHeight=+$('playerHeight').value;
    applyPlayerHeight();
    safeStore();
  };
}
if($('vignette')){
  $('vignette').oninput=()=>{ state.settings.vignette=+$('vignette').value; safeStore(); };
}
if($('comfort')){
  $('comfort').onchange=()=>{ state.settings.comfort=+$('comfort').value; safeStore(); };
}
$('resetPanels').onclick=resetPanelPositions;
$('vrButton').onclick=enterVR;
if($('shootModeBtn')) $('shootModeBtn').onclick=()=>{toggleShootMode(); $('shootModeBtn').textContent = shootMode ? 'SAIR DO TREINO DE TIRO' : 'TREINO DE TIRO (VR)';};
$('reload').onclick=loadBank;
for(const name of ['subject','topic','difficulty'])$(name).onchange=()=>{newSession(page==='exam'?'exam':page==='flash'?'flash':page==='review'?'review':'study');};
$('search').oninput=()=>{newSession('study');};
$('examCount').onchange=()=>{if(page==='exam')newSession('exam');};
$('examTime').onchange=()=>{if(page==='exam')newSession('exam');};
$('examFeedback').onchange=()=>{if(page==='exam')newSession('exam');};

$('demo').onclick=()=>{
  const a=[{id:'demo_1',disciplina:'Direito Constitucional',assunto:'Constituição Federal',enunciado:'Qual é a Constituição Federal atualmente vigente no Brasil?',alternativas:['Constituição de 1967','Constituição de 1988','Constituição de 1946','Constituição de 1937'],gabarito:'B',explicacao:'A Constituição Federal vigente foi promulgada em 1988.'},{id:'demo_2',disciplina:'Direito Penal Comum',assunto:'Patrimônio',enunciado:'Qual artigo do Código Penal trata do furto?',alternativas:['Art. 121','Art. 155','Art. 157','Art. 171'],gabarito:'B',explicacao:'O furto está previsto no artigo 155 do Código Penal.'}];
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
  restoreState();
  db=await openDB();
  if(!state.history.length){const saved=await idbGet('progress');if(saved&&Array.isArray(saved.history))state={...defaultState(),...saved,settings:{...defaultState().settings,...saved.settings}};}
  initSky();
  syncSettings();
  applyPlayerHeight();
  buildWorld(+state.settings.env);
  fillFilters();
  const cache=await idbGet('bank');
  if(Array.isArray(cache)&&cache.length){questions=cache;fillFilters();}
  if(!state.session?.ids?.length)newSession('study');else render();
  await loadBank();
}
start().catch(e=>{console.error(e);note('Erro de inicialização: '+e.message);});

// =============================================
// CORREÇÃO DE MOVIMENTAÇÃO COM AS MÃOS - QUEST 3S
// =============================================
const antigoRayDaMao = rayFromHand;
rayFromHand = function(hand) {
  const index = hands.findIndex(h => h.object === hand);
  const alvo = controllers[index]?.object;
  if (alvo && alvo.visible) return rayFromController(alvo);
  return antigoRayDaMao(hand);
};
handTouchHit = function(hand) {
  const ponta = hand.joints?.['index-finger-tip'];
  if (!ponta) return null;
  const pos = new THREE.Vector3();
  ponta.getWorldPosition(pos);
  for (const p of Object.values(panels)) {
    const local = p.group.worldToLocal(pos.clone());
    const u = local.x / p.w + 0.5, v = 0.5 - local.y / p.h;
    if (Math.abs(local.z) > 0.24 || u < 0 || u > 1 || v < 0 || v > 1) continue;
    const x = u * WIDTH, y = v * HEIGHT;
    const region = [...p.regions].reverse().find(r => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h);
    return { p, region };
  }
  return null;
};
beginDrag = function(p, source, kind) {
  if (dragging) return;
  const index = kind === 'hand' ? hands.findIndex(h => h.object.joints?.['index-finger-tip'] === source) : controllers.findIndex(c => c.object === source);
  const alvo = controllers[index]?.object;
  if (!alvo) return;
  const ray = rayFromController(alvo);
  const hit = intersectFrom(ray.origin, ray.direction);
  let ancora = source;
  if (hit?.p === p && hit.hit) {
    ancora = new THREE.Object3D();
    ancora.position.set(0, 0, -hit.hit.distance);
    ancora.userData.ancoraTemporaria = true;
    alvo.add(ancora);
  }
  const pos = new THREE.Vector3();
  ancora.getWorldPosition(pos);
  dragging = { p, source: ancora, kind, index, offset: p.group.position.clone().sub(pos) };
  note('Movendo painel: mantenha a pinça e mova a mão.');
};
endDrag = function(kind, index) {
  if (!dragging || dragging.kind !== kind || dragging.index !== index) return;
  const p = dragging.p;
  if (dragging.source.userData.ancoraTemporaria) dragging.source.removeFromParent();
  state.panels[p.id] = [p.group.position.x, p.group.position.y, p.group.position.z];
  dragging = null;
  safeStore();
  note('Painel fixado na posição escolhida.');
};
