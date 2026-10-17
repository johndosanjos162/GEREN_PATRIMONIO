"""Videoaulas — login single-user + upload + importação de pasta."""

import hashlib
import hmac
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
from contextlib import contextmanager
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

import streamlit as st

# ============================================================
# PASTAS E CONFIG
# ============================================================
BASE = Path(__file__).parent.resolve()
UPLOAD_DIR = BASE / "uploads"
DB_PATH = BASE / "videoaulas.db"
AUTH_FILE = BASE / ".auth.json"
UPLOAD_DIR.mkdir(exist_ok=True)

VIDEO_EXTS = {"mp4", "m4v", "webm", "mov", "mkv", "avi",
              "ogv", "flv", "wmv", "mpg", "mpeg", "ts"}
CODEC_OK = {"mp4", "m4v", "webm"}
STATUS_OPCOES = ["não iniciada", "em andamento", "concluída"]

_SERVER_INFO = {"port": None}


# ============================================================
# AUTENTICAÇÃO (single user)
# ============================================================
def _hash_senha(senha: str, salt: str | None = None) -> str:
    salt = salt or os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac(
        "sha256", senha.encode("utf-8"), bytes.fromhex(salt), 200_000
    ).hex()
    return f"{salt}${h}"


def _verificar_senha(senha: str, hash_salvo: str) -> bool:
    try:
        salt, _ = hash_salvo.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(_hash_senha(senha, salt), hash_salvo)


def _carregar_hash():
    if not AUTH_FILE.exists():
        return None
    try:
        return json.loads(AUTH_FILE.read_text()).get("hash")
    except Exception:
        return None


def _salvar_hash(h: str):
    AUTH_FILE.write_text(json.dumps({"hash": h}))
    try:
        AUTH_FILE.chmod(0o600)
    except Exception:
        pass


def tela_autenticacao():
    st.markdown(
        "<h1 style='text-align:center; margin-top:60px;'>🔐 Acesso restrito</h1>",
        unsafe_allow_html=True,
    )
    salvo = _carregar_hash()

    if salvo is None:
        st.info(
            "**Primeira execução** — defina a senha que será usada para acessar o app."
        )
        with st.form("setup_senha"):
            s1 = st.text_input("Nova senha", type="password")
            s2 = st.text_input("Confirmar senha", type="password")
            ok = st.form_submit_button(
                "Definir senha", use_container_width=True, type="primary"
            )
        if ok:
            if not s1:
                st.error("Digite uma senha.")
            elif len(s1) < 4:
                st.error("Use pelo menos 4 caracteres.")
            elif s1 != s2:
                st.error("As senhas não coincidem.")
            else:
                _salvar_hash(_hash_senha(s1))
                st.session_state.authenticated = True
                st.success("Senha definida com sucesso.")
                st.rerun()
        return

    with st.form("login"):
        pwd = st.text_input("Senha", type="password")
        ok = st.form_submit_button(
            "Entrar", use_container_width=True, type="primary"
        )
    if ok:
        if _verificar_senha(pwd, salvo):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Senha incorreta.")


# ============================================================
# SERVIDOR HTTP (Range)
# ============================================================
class RangeHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("directory", str(UPLOAD_DIR))
        super().__init__(*args, **kwargs)

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404)
            return None
        try:
            file_len = os.fstat(f.fileno()).st_size
            rng = self.headers.get("Range")
            m = re.match(r"bytes=(\d+)-(\d*)", rng) if rng else None
            if m:
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else file_len - 1
                end = min(end, file_len - 1)
                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Type", self.guess_type(path))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_len}")
                self.send_header("Content-Length", str(length))
                self.end_headers()
                f.seek(start)
                self._range_remaining = length
                return f
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(file_len))
            self.end_headers()
            return f
        except Exception:
            f.close()
            raise

    def copyfile(self, source, outputfile):
        rem = getattr(self, "_range_remaining", None)
        if rem is not None:
            self._range_remaining = None
            while rem > 0:
                chunk = source.read(min(256 * 1024, rem))
                if not chunk:
                    break
                outputfile.write(chunk)
                rem -= len(chunk)
        else:
            super().copyfile(source, outputfile)

    def log_message(self, *a):
        pass


@st.cache_resource
def iniciar_servidor():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
    _SERVER_INFO["port"] = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def url_video(rel: str) -> str:
    return f"http://127.0.0.1:{_SERVER_INFO['port']}/{quote(rel)}"


# ============================================================
# ABRIR PASTA NO SISTEMA
# ============================================================
def abrir_pasta(path: Path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


# ============================================================
# BANCO
# ============================================================
@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                disciplina TEXT DEFAULT '',
                arquivo TEXT NOT NULL UNIQUE,
                tamanho INTEGER DEFAULT 0,
                status TEXT DEFAULT 'não iniciada',
                progresso INTEGER DEFAULT 0,
                anotacoes TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                favorito INTEGER DEFAULT 0,
                criado_em TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            )
        """)


def _agora():
    return datetime.now().isoformat(timespec="seconds")


def inserir(titulo, disciplina, arquivo, tamanho, tags):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO videos (titulo,disciplina,arquivo,tamanho,tags,"
            "criado_em,atualizado_em) VALUES (?,?,?,?,?,?,?)",
            (titulo, disciplina, arquivo, tamanho, tags, _agora(), _agora()),
        )
        return cur.lastrowid


def atualizar(id_, campos):
    campos["atualizado_em"] = _agora()
    sets = ", ".join(f"{k}=?" for k in campos)
    with db() as conn:
        conn.execute(f"UPDATE videos SET {sets} WHERE id=?",
                     (*campos.values(), id_))


def deletar(id_, apagar_arquivo=True):
    with db() as conn:
        row = conn.execute("SELECT arquivo FROM videos WHERE id=?", (id_,)).fetchone()
        conn.execute("DELETE FROM videos WHERE id=?", (id_,))
    if apagar_arquivo and row:
        try:
            (UPLOAD_DIR / row["arquivo"]).unlink(missing_ok=True)
        except OSError:
            pass


def buscar(id_):
    with db() as conn:
        r = conn.execute("SELECT * FROM videos WHERE id=?", (id_,)).fetchone()
    return dict(r) if r else None


def listar(busca="", disciplina="", status="", favorito=False):
    q, p = "SELECT * FROM videos WHERE 1=1", []
    if busca:
        q += " AND (titulo LIKE ? OR anotacoes LIKE ? OR tags LIKE ?)"
        lk = f"%{busca}%"; p += [lk, lk, lk]
    if disciplina: q += " AND disciplina=?"; p.append(disciplina)
    if status: q += " AND status=?"; p.append(status)
    if favorito: q += " AND favorito=1"
    q += " ORDER BY atualizado_em DESC"
    with db() as conn:
        return [dict(r) for r in conn.execute(q, p).fetchall()]


def disciplinas():
    with db() as conn:
        return [r["disciplina"] for r in conn.execute(
            "SELECT DISTINCT disciplina FROM videos WHERE disciplina<>'' "
            "ORDER BY disciplina")]


def estatisticas():
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM videos").fetchone()["c"]
        concluidas = conn.execute(
            "SELECT COUNT(*) c FROM videos WHERE status='concluída'").fetchone()["c"]
        b = conn.execute("SELECT COALESCE(SUM(tamanho),0) s FROM videos").fetchone()["s"]
    return {"total": total, "concluidas": concluidas, "gb": b / (1024**3)}


def arquivos_nao_registrados():
    with db() as conn:
        reg = {r["arquivo"] for r in conn.execute("SELECT arquivo FROM videos")}
    pend = []
    for p in UPLOAD_DIR.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower().lstrip(".") not in VIDEO_EXTS:
            continue
        rel = p.relative_to(UPLOAD_DIR).as_posix()
        if rel in reg:
            continue
        try:
            tam = p.stat().st_size
        except OSError:
            tam = 0
        partes = p.relative_to(UPLOAD_DIR).parts
        disc_sug = partes[0] if len(partes) > 1 else ""
        pend.append({
            "rel": rel,
            "tamanho": tam,
            "titulo_sug": p.stem.replace("_", " "),
            "disciplina_sug": disc_sug,
        })
    return pend


# ============================================================
# BOOT
# ============================================================
st.set_page_config(page_title="Videoaulas", page_icon="🎬", layout="wide")
init_db()
iniciar_servidor()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    tela_autenticacao()
    st.stop()

# ---------- LOGADO ----------
if "video_atual" not in st.session_state:
    st.session_state.video_atual = None

st.markdown("""
<h1 style="margin-bottom: 4px;">🎬 Minhas Videoaulas</h1>
<p style="color:#8fb8cc;font-size:13px;letter-spacing:1px;margin-top:0;">
    Envie vídeos pelo navegador ou copie arquivos grandes direto para a pasta.
</p>
""", unsafe_allow_html=True)

stt = estatisticas()
c1, c2, c3 = st.columns(3)
c1.metric("Total de aulas", stt["total"])
c2.metric("Concluídas", stt["concluidas"])
c3.metric("Espaço usado", f"{stt['gb']:.1f} GB")

# -------- SIDEBAR --------
with st.sidebar:
    st.header("📂 Pasta de vídeos")
    st.code(str(UPLOAD_DIR), language=None)
    if st.button("📂 Abrir pasta uploads", use_container_width=True):
        abrir_pasta(UPLOAD_DIR)
        st.toast("Pasta aberta no gerenciador de arquivos.")

    if st.button("🔄 Re-escanear pasta", use_container_width=True):
        st.rerun()

    pend_count = len(arquivos_nao_registrados())
    if pend_count:
        st.info(f"📌 {pend_count} arquivo(s) aguardando importação")
    else:
        st.caption("Nenhum arquivo pendente")

    st.divider()
    st.header("🔎 Filtros")
    busca = st.text_input("Buscar", placeholder="Título, tag, anotação...")
    f_disc = st.selectbox("Disciplina", ["Todas"] + disciplinas())
    f_status = st.selectbox("Status", ["Todos"] + STATUS_OPCOES)
    f_fav = st.checkbox("⭐ Apenas favoritos")

    st.divider()
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.video_atual = None
        st.rerun()

# -------- PLAYER --------
if st.session_state.video_atual:
    v = buscar(st.session_state.video_atual)
    if v:
        path = UPLOAD_DIR / v["arquivo"]
        cT, cX = st.columns([8, 1])
        cT.subheader(f"▶️ {v['titulo']}")
        if cX.button("✖️ Fechar", use_container_width=True):
            st.session_state.video_atual = None
            st.rerun()

        if not path.exists():
            st.error(f"Arquivo ausente: `uploads/{v['arquivo']}`")
        else:
            ext = path.suffix.lower().lstrip(".")
            size_gb = v["tamanho"] / (1024**3)
            if ext in CODEC_OK or size_gb < 0.5:
                st.video(url_video(v["arquivo"]))
            else:
                st.warning(
                    f"⚠️ `.{ext}` ({size_gb:.1f} GB) provavelmente não toca no navegador. "
                    f"Copie a URL abaixo no VLC → *Mídia → Abrir Fluxo de Rede* (Ctrl+N):"
                )
                st.code(url_video(v["arquivo"]), language=None)
                if st.button("🎥 Tentar no navegador mesmo assim",
                             use_container_width=True):
                    st.video(url_video(v["arquivo"]))

            with st.form("form_player"):
                c1, c2 = st.columns(2)
                ns = c1.selectbox("Status", STATUS_OPCOES,
                                  index=STATUS_OPCOES.index(v["status"]))
                np_ = c2.slider("Progresso (%)", 0, 100, v["progresso"])
                nota = st.text_area("📝 Anotações", value=v["anotacoes"], height=130)
                tags = st.text_input("🏷️ Tags", value=v["tags"])
                b1, b2 = st.columns(2)
                salvar = b1.form_submit_button("💾 Salvar", use_container_width=True,
                                               type="primary")
                lbl = "💔 Remover favorito" if v["favorito"] else "⭐ Favoritar"
                fav = b2.form_submit_button(lbl, use_container_width=True)
            if salvar:
                atualizar(v["id"], {"status": ns, "progresso": int(np_),
                                    "anotacoes": nota, "tags": tags})
                st.rerun()
            if fav:
                atualizar(v["id"], {"favorito": 0 if v["favorito"] else 1})
                st.rerun()
        st.divider()

# -------- ABAS --------
tab_aulas, tab_upload, tab_pasta = st.tabs(
    ["📚 Minhas aulas", "⬆️ Enviar vídeo", "📥 Importar da pasta"]
)

# =============== MINHAS AULAS ===============
with tab_aulas:
    videos = listar(busca, "" if f_disc == "Todas" else f_disc,
                    "" if f_status == "Todos" else f_status, favorito=f_fav)
    st.caption(f"**{len(videos)}** aula(s) encontrada(s)")

    if not videos:
        st.info(
            "Nenhuma aula cadastrada ainda. "
            "Use **⬆️ Enviar vídeo** (arquivos pequenos) "
            "ou **📥 Importar da pasta** (arquivos grandes)."
        )

    for v in videos:
        path = UPLOAD_DIR / v["arquivo"]
        existe = path.exists()
        emoji = {"não iniciada": "⚪", "em andamento": "🟡", "concluída": "🟢"}[v["status"]]
        fav = "⭐ " if v["favorito"] else ""
        ghost = "" if existe else "👻 "
        pct = f" • {v['progresso']}%" if v["progresso"] else ""
        gb = v["tamanho"] / (1024**3)

        with st.expander(f"{ghost}{emoji} {fav}{v['titulo']} — "
                         f"*{v['disciplina'] or 'sem disciplina'}*{pct}"):
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                if existe:
                    st.caption(f"📄 `{v['arquivo']}` • {gb:.2f} GB")
                else:
                    st.error(f"Arquivo ausente: `uploads/{v['arquivo']}`")
            with c2:
                if existe and st.button("▶️ Assistir", key=f"p_{v['id']}",
                                        use_container_width=True, type="primary"):
                    st.session_state.video_atual = v["id"]
                    st.rerun()
            with c3:
                if st.button("🗑️ Excluir", key=f"d_{v['id']}",
                             use_container_width=True,
                             help="Remove do banco E apaga o arquivo de uploads/."):
                    deletar(v["id"], apagar_arquivo=True)
                    if st.session_state.video_atual == v["id"]:
                        st.session_state.video_atual = None
                    st.rerun()

            if v["anotacoes"]:
                st.markdown("**📝 Anotações:**")
                st.markdown(v["anotacoes"])
            if v["tags"]:
                st.caption("🏷️ " + v["tags"])

# =============== ENVIAR VÍDEO ===============
with tab_upload:
    st.markdown("""
    ### ⬆️ Enviar vídeo pelo navegador
    
    **Bom para arquivos até ~500 MB.** Para arquivos de 4–5 GB, use a aba
    **📥 Importar da pasta** — o navegador não aguenta upload desse tamanho.
    """)

    with st.form("form_upload", clear_on_submit=True):
        arquivo = st.file_uploader(
            "Selecione o arquivo de vídeo",
            type=sorted(VIDEO_EXTS),
            accept_multiple_files=False,
        )
        c1, c2 = st.columns(2)
        titulo = c1.text_input("Título *", placeholder="Ex: Aula 03 — Crase")
        disciplina = c2.text_input("Disciplina", placeholder="Ex: Português")
        tags = st.text_input("Tags (separadas por vírgula)")
        enviar = st.form_submit_button("⬆️ Enviar e cadastrar",
                                       use_container_width=True, type="primary")

    if enviar:
        if not arquivo:
            st.warning("Selecione um arquivo antes de enviar.")
        elif not titulo.strip():
            st.warning("Informe um título.")
        else:
            ext = Path(arquivo.name).suffix.lower().lstrip(".")
            base = Path(arquivo.name).stem.replace(" ", "_")[:60]
            stamp = datetime.now().strftime("%Y%m%d%H%M%S")
            nome = f"{base}_{stamp}.{ext}"
            destino = UPLOAD_DIR / nome
            try:
                with st.spinner(f"Salvando {nome}..."):
                    with open(destino, "wb") as f:
                        shutil.copyfileobj(arquivo, f)
                inserir(titulo.strip(), disciplina.strip(), nome,
                        destino.stat().st_size, tags.strip())
                st.success(f"✅ '{titulo}' enviada e cadastrada!")
                st.rerun()
            except Exception as e:
                st.error(f"Falha ao salvar: {e}")

# =============== IMPORTAR DA PASTA ===============
with tab_pasta:
    st.markdown(f"""
    ### 📥 Importar arquivos que já estão na pasta
    
    **Pasta:** `{UPLOAD_DIR}`
    
    1. Clique em **📂 Abrir pasta uploads** (na barra lateral)
    2. Copie os vídeos (4–5 GB) para dentro dela — instantâneo no mesmo HD
    3. Clique em **🔄 Re-escanear pasta**
    4. Os arquivos aparecem abaixo → clique em **Importar**
    """)

    if st.button("📂 Abrir pasta uploads agora"):
        abrir_pasta(UPLOAD_DIR)
        st.toast("Pasta aberta no gerenciador de arquivos.")

    st.divider()

    pendentes = arquivos_nao_registrados()

    if not pendentes:
        st.success("✅ Nenhum arquivo pendente em `uploads/`. Tudo já foi cadastrado.")
    else:
        st.info(f"📌 **{len(pendentes)}** arquivo(s) encontrado(s) para importar.")

        if st.button(f"⚡ Importar todos ({len(pendentes)})",
                     use_container_width=True, type="primary"):
            for item in pendentes:
                inserir(item["titulo_sug"], item["disciplina_sug"],
                        item["rel"], item["tamanho"], "")
            st.success(f"✅ {len(pendentes)} aula(s) importada(s)!")
            st.rerun()

        st.divider()

        for i, item in enumerate(pendentes):
            gb = item["tamanho"] / (1024**3)
            titulo_disp = item["titulo_sug"][:60]
            disc_disp = f" — *{item['disciplina_sug']}*" if item["disciplina_sug"] else ""
            with st.expander(f"📄 {titulo_disp}  ({gb:.2f} GB){disc_disp}"):
                st.caption(f"Arquivo: `uploads/{item['rel']}`")
                with st.form(key=f"imp_{i}"):
                    c1, c2 = st.columns(2)
                    titulo = c1.text_input("Título *", value=item["titulo_sug"])
                    disc = c2.text_input("Disciplina", value=item["disciplina_sug"])
                    tags = st.text_input("Tags (separadas por vírgula)")
                    if st.form_submit_button("✅ Importar esta aula",
                                             use_container_width=True, type="primary"):
                        if not titulo.strip():
                            st.warning("Informe um título.")
                        else:
                            inserir(titulo.strip(), disc.strip(),
                                    item["rel"], item["tamanho"], tags.strip())
                            st.success(f"✅ '{titulo}' importada!")
                            st.rerun()
