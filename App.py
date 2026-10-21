import streamlit as st
import streamlit.components.v1 as components
import requests
import json
import time
from datetime import datetime

# ==================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==================================================================
st.set_page_config(
    page_title="PMSC 3D – Estudo Imersivo",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==================================================================
# CHAVE DA API DO GROK (via st.secrets)
# ==================================================================
try:
    GROK_API_KEY = st.secrets["GROK_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error(
        "⚠️ **Chave da API do Grok não configurada.**\n\n"
        "Adicione `GROK_API_KEY` nos *Secrets* do Streamlit Cloud ou no arquivo "
        "`.streamlit/secrets.toml` para desenvolvimento local."
    )
    st.stop()

GROK_API_URL = "https://api.x.ai/v1/chat/completions"
GROK_MODEL = "grok-3-latest"

# ==================================================================
# DISTRIBUIÇÃO OFICIAL DAS QUESTÕES (Edital PMSC / AOCP)
# ==================================================================
DISTRIBUICAO_OFICIAL = {
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
TOTAL_QUESTOES = sum(DISTRIBUICAO_OFICIAL.values())

# ==================================================================
# PROMPTS
# ==================================================================
PROMPT_QUESTOES = """
Você é um especialista em concursos públicos e deve gerar questões de múltipla escolha
no estilo da banca **Instituto AOCP**, especificamente para o concurso de Soldado da PMSC.

**Matéria:** {materia}
**Quantidade de questões:** {quantidade}

Cada questão deve ter:
- Enunciado claro e contextualizado, no estilo AOCP (situações-problema, casos práticos).
- 5 alternativas (A, B, C, D, E).
- Apenas uma alternativa correta.
- Indique a resposta correta ao final de cada questão.

Retorne **exclusivamente** um array JSON válido, sem markdown, no seguinte formato:
[
  {{
    "pergunta": "Texto da questão...",
    "alternativas": ["A) ...", "B) ...", "C) ...", "D) ...", "E) ..."],
    "correta": "A"
  }}
]
"""

PROMPT_REDACAO = """
Você é um corretor de redação para concursos públicos, especializado na banca **Instituto AOCP**.
A prova discursiva do concurso PMSC exige uma redação dissertativa de 20 a 30 linhas,
sobre tema ligado à ordem pública, sistema de justiça criminal, políticas públicas
ou a Polícia Militar na Constituição Federal. Valor total: 20 pontos (mínimo 10 para aprovação).

**Tema proposto:** {tema}
**Redação do candidato:** {redacao}

Avalie a redação considerando:
1. Adequação ao tema (0–4 pontos)
2. Estrutura dissertativa (introdução, desenvolvimento, conclusão) (0–4 pontos)
3. Norma culta da língua portuguesa (0–4 pontos)
4. Argumentação e coerência (0–4 pontos)
5. Proposta de intervenção (0–4 pontos)

Retorne **exclusivamente** um JSON válido, sem markdown:
{{
  "nota_total": 0.0,
  "nota_por_criterio": {{
    "adequacao_tema": 0.0,
    "estrutura": 0.0,
    "norma_culta": 0.0,
    "argumentacao": 0.0,
    "proposta_intervencao": 0.0
  }},
  "feedback": "Comentário detalhado sobre a redação."
}}
"""

# ==================================================================
# FUNÇÃO AUXILIAR: CHAMAR O GROK
# ==================================================================
def chamar_grok(prompt, system_msg="Você é um gerador de questões para concursos públicos."):
    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }
    try:
        resp = requests.post(GROK_API_URL, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        texto = resp.json()["choices"][0]["message"]["content"].strip()
        # Limpeza de markdown
        if texto.startswith("```json"):
            texto = texto[7:]
        if texto.startswith("```"):
            texto = texto[3:]
        if texto.endswith("```"):
            texto = texto[:-3]
        texto = texto.strip()
        return json.loads(texto)
    except requests.exceptions.RequestException as e:
        raise Exception(f"Falha na chamada à API do Grok: {str(e)}")
    except json.JSONDecodeError:
        raise Exception("A IA não retornou um JSON válido. Tente novamente.")

def validar_questoes(questoes):
    if not isinstance(questoes, list):
        raise ValueError("A resposta da IA não é uma lista.")
    for q in questoes:
        if not all(k in q for k in ("pergunta", "alternativas", "correta")):
            raise ValueError("Questão com formato inválido.")
        if len(q["alternativas"]) != 5:
            raise ValueError("Cada questão deve ter exatamente 5 alternativas.")
        if q["correta"].upper() not in ["A", "B", "C", "D", "E"]:
            raise ValueError("A alternativa correta deve ser A, B, C, D ou E.")
    return True

# ==================================================================
# COMPONENTE 3D (iframe com Three.js / WebXR)
# ==================================================================
def render_3d(questoes, modo="treino"):
    """Renderiza a cena 3D via iframe usando st.components.v1.html."""
    questoes_json = json.dumps(questoes, ensure_ascii=False)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ margin:0; overflow:hidden; background:#0a0a1a; }}
            canvas {{ display:block; width:100%; height:100%; }}
        </style>
    </head>
    <body>
        <script type="importmap">
        {{
            "imports": {{
                "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
                "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
            }}
        }}
        </script>
        <script type="module">
            import * as THREE from 'three';
            import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';
            import {{ VRButton }} from 'three/addons/webxr/VRButton.js';

            const questoes = {questoes_json};
            const modo = "{modo}";

            // --- Cena ---
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0a0a1a);
            scene.fog = new THREE.Fog(0x0a0a1a, 15, 60);

            const camera = new THREE.PerspectiveCamera(60, window.innerWidth/window.innerHeight, 0.1, 1000);
            camera.position.set(0, 6, 14);

            const renderer = new THREE.WebGLRenderer({{ antialias: true }});
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            renderer.shadowMap.enabled = true;
            renderer.xr.enabled = true;
            document.body.appendChild(renderer.domElement);
            document.body.appendChild(VRButton.createButton(renderer));

            const controls = new OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.target.set(0, 3, 0);
            controls.maxPolarAngle = Math.PI / 2;

            // --- Luzes ---
            scene.add(new THREE.AmbientLight(0x404070, 1.2));
            const dir = new THREE.DirectionalLight(0xffffff, 2);
            dir.position.set(8, 15, 10);
            dir.castShadow = true;
            scene.add(dir);

            // --- Grid ---
            const grid = new THREE.GridHelper(40, 40, 0x0066cc, 0x1a1a3a);
            grid.position.y = -0.5;
            scene.add(grid);

            // --- Cartões ---
            const group = new THREE.Group();
            scene.add(group);

            function criarCartao(q, index) {{
                const canvas = document.createElement('canvas');
                canvas.width = 512; canvas.height = 512;
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = '#12122a';
                ctx.fillRect(0,0,512,512);
                ctx.strokeStyle = modo === 'simulado' ? '#ff6600' : '#0066cc';
                ctx.lineWidth = 6;
                ctx.strokeRect(3,3,506,506);

                ctx.fillStyle = modo === 'simulado' ? '#ff8844' : '#4488ff';
                ctx.font = 'bold 16px "Segoe UI"';
                ctx.fillText(q.materia || (modo === 'treino' ? 'Treino' : 'Simulado'), 25, 35);

                ctx.fillStyle = '#ffffff';
                ctx.font = 'bold 21px "Segoe UI"';
                const palavras = q.pergunta.split(' ');
                let linha = '', y = 75;
                for (const p of palavras) {{
                    const teste = linha + p + ' ';
                    if (ctx.measureText(teste).width > 460) {{
                        ctx.fillText(linha, 25, y); linha = p + ' '; y += 28;
                    }} else {{ linha = teste; }}
                }}
                ctx.fillText(linha, 25, y);

                ctx.font = '17px "Segoe UI"';
                ctx.fillStyle = '#bbbbdd';
                y += 40;
                q.alternativas.forEach(a => {{ ctx.fillText(a, 35, y); y += 28; }});

                const tex = new THREE.CanvasTexture(canvas);
                const mat = new THREE.MeshStandardMaterial({{
                    map: tex, roughness: 0.4, metalness: 0.1,
                    emissive: new THREE.Color(modo === 'simulado' ? 0x331100 : 0x001133),
                    emissiveIntensity: 0.15
                }});
                const card = new THREE.Mesh(new THREE.BoxGeometry(4, 4, 0.15), mat);
                card.castShadow = true; card.receiveShadow = true;

                const cols = 3;
                const x = (index % cols) * 4.8 - (cols - 1) * 2.4;
                const z = Math.floor(index / cols) * 4.8;
                card.position.set(x, 2.2, -z);

                // Clique: revela resposta (apenas no modo treino)
                card.addEventListener('click', () => {{
                    if (modo === 'treino') {{
                        if (!card.userData.virado) {{
                            const c2 = document.createElement('canvas');
                            c2.width = 512; c2.height = 512;
                            const ctx2 = c2.getContext('2d');
                            ctx2.fillStyle = '#0a2a1a'; ctx2.fillRect(0,0,512,512);
                            ctx2.strokeStyle = '#00cc66'; ctx2.lineWidth = 6;
                            ctx2.strokeRect(3,3,506,506);
                            ctx2.fillStyle = '#fff'; ctx2.font = 'bold 34px "Segoe UI"';
                            ctx2.textAlign = 'center';
                            ctx2.fillText('✅ Resposta', 256, 180);
                            ctx2.font = 'bold 80px "Segoe UI"';
                            ctx2.fillStyle = '#00ff88';
                            ctx2.fillText(q.correta, 256, 290);
                            const nt = new THREE.CanvasTexture(c2);
                            card.material.map = nt; card.material.needsUpdate = true;
                            card.userData.virado = true;
                        }} else {{
                            card.material.map = tex; card.material.needsUpdate = true;
                            card.userData.virado = false;
                        }}
                    }}
                }});

                return card;
            }}

            questoes.forEach((q, i) => group.add(criarCartao(q, i)));

            // Ajustar câmera
            const linhas = Math.ceil(questoes.length / 3);
            controls.target.set(0, 2, -((linhas - 1) * 4.8) / 2);
            camera.position.set(0, Math.max(8, linhas * 3.5), linhas * 3.5 + 6);

            // Loop de animação
            renderer.setAnimationLoop(() => {{
                controls.update();
                renderer.render(scene, camera);
            }});

            window.addEventListener('resize', () => {{
                camera.aspect = window.innerWidth / window.innerHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(window.innerWidth, window.innerHeight);
            }});
        </script>
    </body>
    </html>
    """
    components.html(html_content, height=650, scrolling=False)

# ==================================================================
# ESTADO DA SESSÃO (st.session_state)
# ==================================================================
if "questoes_treino" not in st.session_state:
    st.session_state.questoes_treino = []
if "simulado" not in st.session_state:
    st.session_state.simulado = None  # {questoes, inicio, respostas, finalizado}
if "historico" not in st.session_state:
    st.session_state.historico = []
if "redacao_resultado" not in st.session_state:
    st.session_state.redacao_resultado = None

# ==================================================================
# BARRA LATERAL – CONTROLES
# ==================================================================
with st.sidebar:
    st.title("🎯 PMSC 3D")
    st.caption("Banca: Instituto AOCP")
    st.divider()

    # --- Treino por matéria ---
    st.subheader("📚 Treino por Matéria")
    materia = st.selectbox(
        "Matéria",
        list(DISTRIBUICAO_OFICIAL.keys()),
        key="materia_treino",
    )
    quantidade = st.number_input(
        "Quantidade de questões", min_value=1, max_value=20, value=5, key="qtd_treino"
    )
    if st.button("Gerar Questões de Treino", type="primary", use_container_width=True):
        with st.spinner("Gerando questões no estilo AOCP..."):
            try:
                prompt = PROMPT_QUESTOES.format(materia=materia, quantidade=quantidade)
                questoes = chamar_grok(prompt)
                validar_questoes(questoes)
                for q in questoes:
                    q["materia"] = materia
                st.session_state.questoes_treino = questoes
                st.session_state.simulado = None  # limpa simulado anterior
                st.success(f"✅ {len(questoes)} questões geradas para **{materia}**.")
            except Exception as e:
                st.error(f"Erro: {e}")

    st.divider()

    # --- Simulado completo ---
    st.subheader("📝 Simulado Completo")
    st.caption(f"{TOTAL_QUESTOES} questões na proporção oficial do edital.")
    if st.button("Iniciar Simulado (60 questões)", use_container_width=True):
        with st.spinner("Gerando simulado completo... Isso pode levar alguns minutos."):
            try:
                todas = []
                for mat, qtd in DISTRIBUICAO_OFICIAL.items():
                    prompt = PROMPT_QUESTOES.format(materia=mat, quantidade=qtd)
                    qs = chamar_grok(prompt)
                    validar_questoes(qs)
                    for q in qs:
                        q["materia"] = mat
                    todas.extend(qs)
                st.session_state.simulado = {
                    "questoes": todas,
                    "inicio": time.time(),
                    "respostas": {},
                    "finalizado": False,
                }
                st.session_state.questoes_treino = []
                st.success(f"✅ Simulado com {len(todas)} questões iniciado.")
            except Exception as e:
                st.error(f"Erro ao gerar simulado: {e}")

    if st.session_state.simulado and not st.session_state.simulado["finalizado"]:
        if st.button("❌ Cancelar Simulado", use_container_width=True):
            st.session_state.simulado = None
            st.rerun()

    st.divider()

    # --- Redação ---
    st.subheader("✍️ Redação")
    with st.expander("Abrir módulo de redação"):
        tema = st.text_input("Tema da redação", key="red_tema")
        redacao = st.text_area(
            "Sua redação (20 a 30 linhas)", height=300, key="red_texto"
        )
        if st.button("Corrigir Redação", use_container_width=True):
            linhas = len([l for l in redacao.split("\n") if l.strip()])
            if not tema or not redacao:
                st.warning("Preencha tema e redação.")
            elif linhas < 20 or linhas > 30:
                st.warning(f"A redação deve ter 20–30 linhas. Atual: {linhas}.")
            else:
                with st.spinner("Corrigindo com IA..."):
                    try:
                        prompt = PROMPT_REDACAO.format(tema=tema, redacao=redacao)
                        resultado = chamar_grok(
                            prompt, system_msg="Você é um corretor de redação de concursos."
                        )
                        st.session_state.redacao_resultado = resultado
                    except Exception as e:
                        st.error(f"Erro: {e}")

# ==================================================================
# ÁREA PRINCIPAL
# ==================================================================
st.title("🎯 PMSC – Estudo 3D Imersivo")
st.caption("Questões geradas por IA no estilo AOCP | Visualização 3D | Compatível com Meta Quest 3S")

# --- Exibe redação corrigida (se houver) ---
if st.session_state.redacao_resultado:
    res = st.session_state.redacao_resultado
    with st.container(border=True):
        st.subheader("📄 Resultado da Redação")
        st.metric("Nota Total", f"{res.get('nota_total', 0)} / 20")
        cols = st.columns(5)
        crits = [
            ("Adequação ao Tema", "adequacao_tema"),
            ("Estrutura", "estrutura"),
            ("Norma Culta", "norma_culta"),
            ("Argumentação", "argumentacao"),
            ("Proposta de Intervenção", "proposta_intervencao"),
        ]
        for col, (label, key) in zip(cols, crits):
            with col:
                st.metric(label, res.get("nota_por_criterio", {}).get(key, 0))
        st.info(res.get("feedback", ""))
    if st.button("Fechar resultado da redação"):
        st.session_state.redacao_resultado = None
        st.rerun()
    st.divider()

# --- Lógica de exibição principal ---
if st.session_state.simulado:
    sim = st.session_state.simulado
    questoes = sim["questoes"]

    if not sim["finalizado"]:
        # Cronômetro
        decorrido = int(time.time() - sim["inicio"])
        restante = max(0, 4 * 3600 - decorrido)
        h, m, s = restante // 3600, (restante % 3600) // 60, restante % 60
        st.warning(f"⏱️ **Tempo restante:** {h:02d}:{m:02d}:{s:02d}")

        # Cena 3D
        st.subheader("🌐 Visualização 3D das Questões")
        render_3d(questoes, modo="simulado")

        # Formulário de respostas (Streamlit widgets para registro confiável)
        st.subheader("✍️ Responda as Questões")
        with st.form("form_simulado"):
            respostas_form = {}
            for i, q in enumerate(questoes):
                st.markdown(f"**{i+1}. [{q.get('materia','')}]** {q['pergunta']}")
                opcoes = q["alternativas"]
                escolha = st.radio(
                    f"Questão {i+1}",
                    options=opcoes,
                    index=None,
                    key=f"sim_q_{i}",
                    label_visibility="collapsed",
                )
                if escolha:
                    # Extrai a letra (A, B, C...)
                    respostas_form[i] = escolha[0].upper()
                st.divider()

            col1, col2 = st.columns([1, 1])
            with col1:
                submetido = st.form_submit_button(
                    "💾 Salvar Respostas", use_container_width=True
                )
            with col2:
                finalizar = st.form_submit_button(
                    "✅ Finalizar Simulado", type="primary", use_container_width=True
                )

            if submetido:
                sim["respostas"] = respostas_form
                st.success("Respostas salvas! Você pode continuar respondendo.")
                st.rerun()

            if finalizar:
                sim["respostas"] = respostas_form
                sim["finalizado"] = True
                # Calcula resultado
                acertos = 0
                detalhes = []
                for i, q in enumerate(questoes):
                    resp = respostas_form.get(i, "")
                    correta = q["correta"].upper()
                    acertou = resp == correta
                    if acertou:
                        acertos += 1
                    detalhes.append(
                        {
                            "pergunta": q["pergunta"],
                            "materia": q.get("materia", ""),
                            "resposta": resp,
                            "correta": correta,
                            "acertou": acertou,
                        }
                    )
                nota = (acertos / len(questoes)) * 100
                resultado = {
                    "acertos": acertos,
                    "total": len(questoes),
                    "nota_percentual": round(nota, 2),
                    "aprovado": nota >= 50,
                    "detalhes": detalhes,
                    "tempo_gasto": time.time() - sim["inicio"],
                    "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                st.session_state.historico.append(
                    {"tipo": "simulado", "resultado": resultado}
                )
                st.rerun()

    else:
        # Resultado final do simulado
        ultimo = st.session_state.historico[-1]["resultado"] if st.session_state.historico else None
        if ultimo:
            st.subheader("📊 Resultado do Simulado")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Nota", f"{ultimo['nota_percentual']}%")
            with col2:
                st.metric("Acertos", f"{ultimo['acertos']} / {ultimo['total']}")
            with col3:
                status = "✅ APROVADO" if ultimo["aprovado"] else "❌ REPROVADO"
                st.metric("Status", status)
            st.caption(
                f"Tempo gasto: {int(ultimo['tempo_gasto'] // 60)} minutos | "
                f"Data: {ultimo['data']}"
            )
            with st.expander("Ver detalhes por questão"):
                for i, d in enumerate(ultimo["detalhes"]):
                    icon = "✅" if d["acertou"] else "❌"
                    st.markdown(
                        f"{icon} **{i+1}. [{d['materia']}]** {d['pergunta']}"
                    )
                    st.caption(
                        f"Sua resposta: {d['resposta'] or '—'} | Correta: {d['correta']}"
                    )
        if st.button("Novo Simulado"):
            st.session_state.simulado = None
            st.rerun()

elif st.session_state.questoes_treino:
    # Modo Treino
    st.subheader(f"🌐 Visualização 3D – {st.session_state.questoes_treino[0].get('materia','Treino')}")
    render_3d(st.session_state.questoes_treino, modo="treino")

    st.subheader("📖 Questões (texto)")
    for i, q in enumerate(st.session_state.questoes_treino):
        with st.expander(f"Questão {i+1}"):
            st.markdown(q["pergunta"])
            for alt in q["alternativas"]:
                st.markdown(f"- {alt}")
            st.success(f"Resposta correta: **{q['correta']}**")

else:
    # Tela inicial
    st.info(
        "👈 Use a barra lateral para **gerar questões de treino**, "
        "**iniciar um simulado completo** ou **corrigir uma redação**."
    )
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1c/PMSC_logo.svg/200px-PMSC_logo.svg.png",
        width=120,
        caption="Polícia Militar de Santa Catarina",
    )

# --- Histórico ---
if st.session_state.historico:
    with st.sidebar:
        st.divider()
        st.subheader("📜 Histórico")
        for h in reversed(st.session_state.historico[-5:]):
            r = h["resultado"]
            st.caption(
                f"{r['data']} – {r['acertos']}/{r['total']} ({r['nota_percentual']}%)"
            )
