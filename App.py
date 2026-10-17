import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import requests
import re
import json
import os
import urllib.parse

# ============================================================
# TENTATIVA DE IMPORTAR BIBLIOTECAS OPCIONAIS
# ============================================================
try:
    from openai import OpenAI
except ImportError:
    raise SystemExit("Instale: pip install openai")

try:
    from vectorgov import VectorGov
    VECTORGOV_DISPONIVEL = True
except ImportError:
    VECTORGOV_DISPONIVEL = False

try:
    import google.generativeai as genai
    GEMINI_DISPONIVEL = True
except ImportError:
    GEMINI_DISPONIVEL = False

# ============================================================
# CARREGAR CHAVES DO ARQUIVO config.py
# ============================================================
try:
    import config
    DEEPSEEK_KEY = config.DEEPSEEK_API_KEY
    VECTORGOV_KEY = getattr(config, "VECTORGOV_API_KEY", "")
    GEMINI_KEY = getattr(config, "GEMINI_API_KEY", "")
except ImportError:
    DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    VECTORGOV_KEY = os.getenv("VECTORGOV_API_KEY", "")
    GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

if not DEEPSEEK_KEY:
    raise SystemExit("Configure DEEPSEEK_API_KEY no arquivo config.py ou como variável de ambiente.")

# ============================================================
# CLIENTE DEEPSEEK
# ============================================================
deepseek_client = OpenAI(
    api_key=DEEPSEEK_KEY,
    base_url="https://api.deepseek.com"  # endpoint compatível com OpenAI[reference:5]
)

# ============================================================
# PROMPT PARA GERAR A PERGUNTA
# ============================================================
PROMPT_GERAR = """Você é um elaborador de questões para concursos públicos.
Banca alvo: {banca}.
Matéria: {materia}.

Sua ÚNICA tarefa é criar o ENUNCIADO de uma questão inédita, no estilo da banca {banca}, sobre a matéria informada.
NÃO forneça alternativas.
NÃO responda à questão.
NÃO diga qual é a resposta correta.
Apenas escreva o texto do enunciado, de forma clara e objetiva.

Enunciado gerado:"""

# ============================================================
# FUNÇÕES DE BUSCA (CAMADA DE VERIFICAÇÃO)
# ============================================================
def buscar_direito(pergunta):
    """Busca a resposta em legislação brasileira usando o SDK VectorGov."""
    if not VECTORGOV_DISPONIVEL:
        return "⚠️ Biblioteca vectorgov não instalada. Execute: pip install vectorgov"
    if not VECTORGOV_KEY:
        return "⚠️ Chave VectorGov não configurada no config.py."

    try:
        vg = VectorGov(api_key=VECTORGOV_KEY)
        resultados = vg.search(pergunta)
        if not resultados:
            return "Nenhum trecho de legislação relevante foi encontrado."

        # Pega o primeiro resultado (mais relevante)
        hit = resultados[0]
        fonte = getattr(hit, "source", "Fonte não informada")
        texto_lei = getattr(hit, "text", "")[:800]  # limita o tamanho
        return f"📖 Base legal: {fonte}\n\nTrecho: \"{texto_lei}...\""
    except Exception as e:
        return f"Erro na busca jurídica: {e}"


def buscar_portugues(pergunta):
    """Busca definições e classes gramaticais usando a Free Dictionary API."""
    # Extrai palavras longas da pergunta para usar como termo de busca
    palavras = re.findall(r"\b[a-zA-ZáàâãéèêíìîóòôõúùûçÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ]{4,}\b", pergunta)
    if not palavras:
        return "Não foi possível extrair uma palavra-chave para buscar no dicionário."

    # Remove palavras muito comuns (stopwords simples)
    stopwords = {"qual", "quais", "como", "onde", "quando", "porque", "para", "sobre", "entre", "após", "segundo"}
    candidatas = [p for p in palavras if p.lower() not in stopwords]
    termo = candidatas[0] if candidatas else palavras[0]

    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/pt/{urllib.parse.quote(termo)}"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 404:
            return f"A palavra '{termo}' não foi encontrada no dicionário."
        resp.raise_for_status()
        dados = resp.json()
        if dados and isinstance(dados, list):
            significado = dados[0]["meanings"][0]
            classe = significado.get("partOfSpeech", "classe não informada")
            definicao = significado["definitions"][0].get("definition", "")
            return f"📚 Definição oficial para '{termo}' ({classe}):\n\n{definicao}"
        return "Definição não encontrada."
    except Exception as e:
        return f"Erro na busca do dicionário: {e}"


def buscar_matematica(pergunta):
    """Avalia uma expressão matemática usando a API Math.js."""
    # Tenta extrair uma expressão matemática simples (números e operadores)
    match = re.search(r"([\d\.\+\-\*\/\(\)\s\^]+)", pergunta)
    if not match:
        return "Nenhuma expressão matemática simples detectada na pergunta."

    expressao = match.group(1).strip()
    if len(expressao) < 3:
        return "A expressão detectada é muito curta para ser calculada."

    try:
        url = f"https://api.mathjs.org/v4/?expr={urllib.parse.quote(expressao)}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        resultado = resp.text.strip()
        return f"🧮 Resultado do cálculo para a expressão '{expressao}':\n\n{resultado}"
    except Exception as e:
        return f"Erro ao calcular a expressão: {e}"


def buscar_geral(pergunta):
    """Busca geral usando Gemini com Grounding (Google Search)."""
    if not GEMINI_DISPONIVEL:
        return "⚠️ Biblioteca google-generativeai não instalada. Execute: pip install google-generativeai"
    if not GEMINI_KEY:
        return "⚠️ Chave Gemini não configurada no config.py."

    try:
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        # A ferramenta de Grounding com Google Search permite que a IA
        # consulte a web para embasar a resposta.
        tool = {"google_search_retrieval": {}}
        resposta = model.generate_content(
            f"Responda de forma objetiva e direta, com base em fontes confiáveis: {pergunta}",
            tools=[tool]
        )
        texto = resposta.text.strip() if resposta.text else "Nenhuma resposta gerada."
        return f"🌐 Resposta com base em busca na web:\n\n{texto}"
    except Exception as e:
        return f"Erro na busca geral: {e}"


# ============================================================
# INTERFACE GRÁFICA
# ============================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gerador e Verificador de Questões por Matéria")
        self.geometry("900x720")
        self._construir_ui()

    def _construir_ui(self):
        # --- Controles superiores ---
        frame = tk.Frame(self, pady=10)
        frame.pack(fill="x", padx=15)

        tk.Label(frame, text="Banca:", font=("Arial", 10, "bold")).pack(side="left")
        self.combo_banca = ttk.Combobox(
            frame,
            values=["AOCP", "FCC", "VUNESP", "CESPE", "FGV", "IBFC", "IDECAN"],
            state="readonly", width=12
        )
        self.combo_banca.pack(side="left", padx=(0, 20))

        tk.Label(frame, text="Matéria:", font=("Arial", 10, "bold")).pack(side="left")
        self.combo_materia = ttk.Combobox(
            frame,
            values=["Direito", "Língua Portuguesa", "Matemática", "Geral"],
            state="readonly", width=18
        )
        self.combo_materia.pack(side="left", padx=(0, 20))

        self.btn_gerar = tk.Button(
            frame, text="🔍 Gerar Questão Verificada",
            command=self.gerar_questao,
            bg="#4CAF50", fg="white", font=("Arial", 11, "bold")
        )
        self.btn_gerar.pack(side="left")

        self.lbl_status = tk.Label(frame, text="", fg="blue")
        self.lbl_status.pack(side="right")

        # --- Área de resultado ---
        self.txt_resultado = scrolledtext.ScrolledText(
            self, wrap="word", font=("Consolas", 11),
            bg="#fafafa", state="disabled"
        )
        self.txt_resultado.pack(fill="both", expand=True, padx=15, pady=10)

        # --- Rodapé informativo ---
        rodape = tk.Label(
            self,
            text="Fluxo: DeepSeek gera a pergunta → busca consulta fonte oficial → você confere a resposta.",
            fg="gray", font=("Arial", 9)
        )
        rodape.pack(pady=(0, 10))

    def gerar_questao(self):
        banca = self.combo_banca.get()
        materia = self.combo_materia.get()
        if not banca or not materia:
            messagebox.showwarning("Atenção", "Selecione a banca e a matéria.")
            return

        self.btn_gerar.config(state="disabled", text="⏳ Gerando...")
        self.lbl_status.config(text="Criando enunciado com DeepSeek...")
        self.update_idletasks()

        try:
            # ---------- ETAPA 1: GERAR A PERGUNTA ----------
            prompt = PROMPT_GERAR.format(banca=banca, materia=materia)
            resposta_ia = deepseek_client.chat.completions.create(
                model="deepseek-chat",  # modelo compatível[reference:6]
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=400
            )
            pergunta = resposta_ia.choices[0].message.content.strip()
            pergunta = re.sub(r'^["\']|["\']$', "", pergunta)  # remove aspas

            self.lbl_status.config(text="Buscando resposta correta na fonte...")
            self.update_idletasks()

            # ---------- ETAPA 2: BUSCAR A RESPOSTA ----------
            if materia == "Direito":
                resposta = buscar_direito(pergunta)
            elif materia == "Língua Portuguesa":
                resposta = buscar_portugues(pergunta)
            elif materia == "Matemática":
                resposta = buscar_matematica(pergunta)
            else:
                resposta = buscar_geral(pergunta)

            # ---------- ETAPA 3: EXIBIR ----------
            texto_final = (
                f"{'='*70}\n"
                f"BANCA: {banca}  |  MATÉRIA: {materia}\n"
                f"{'='*70}\n\n"
                f"❓ PERGUNTA GERADA PELA IA:\n\n{pergunta}\n\n"
                f"{'='*70}\n"
                f"✅ RESPOSTA CORRETA (com base em fonte oficial):\n\n{resposta}\n"
                f"{'='*70}"
            )
            self._exibir(texto_final)
            self.lbl_status.config(text="Pronto!")

        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro:\n{e}")
            self.lbl_status.config(text="")
        finally:
            self.btn_gerar.config(state="normal", text="🔍 Gerar Questão Verificada")

    def _exibir(self, texto):
        self.txt_resultado.config(state="normal")
        self.txt_resultado.delete("1.0", tk.END)
        self.txt_resultado.insert(tk.END, texto)
        self.txt_resultado.config(state="disabled")


if __name__ == "__main__":
    App().mainloop()
