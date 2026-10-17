"""Videoaulas — importa de uploads/ + player local com Range. Arquivo único."""

import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

import streamlit as st

# ============================================================
# CONFIGURAÇÃO E PASTAS
# ============================================================
BASE = Path(__file__).parent.resolve()
UPLOAD_DIR = BASE / "uploads"
DB_PATH = BASE / "videoaulas.db"
UPLOAD_DIR.mkdir(exist_ok=True)

VIDEO_EXTS = {"mp4", "m4v", "webm", "mov", "mkv", "avi",
              "ogv", "flv", "wmv", "mpg", "mpeg", "ts"}
CODEC_OK = {"mp4", "m4v", "webm"}          # tocam direto no navegador
STATUS_OPCOES = ["não iniciada", "em andamento", "concluída"]

_SERVER_INFO = {"port": None}


# ============================================================
# SERVIDOR HTTP COM RANGE (streaming de arquivos grandes)
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
            self.send_error(404, "File not found")
            return None
        try:
            file_len = os.fstat(f.fileno()).st_size
            range_header = self.headers.get("Range")
            m = re.match(r"bytes=(\d+)-(\d*)", range_header) if range_header else None
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
        remaining = getattr(self, "_range_remaining", None)
        if remaining is not None:
            self._range_remaining = None
            while remaining > 0:
                chunk = source.read(min(256 * 1024, remaining))
                if not chunk:
                    break
                outputfile.write(chunk)
                remaining -= len(chunk)
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


def url_video(arquivo_rel: str) -> str:
    return f"http://127.0.0.1:{_SERVER_INFO['port']}/{quote(arquivo_rel)}"


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
        bytes_ = conn.execute(
            "SELECT COALESCE(SUM(tamanho),0) s FROM videos").fetchone()["s"]
    return {"total": total, "concluidas": concluidas, "gb": bytes_ / (1024**3)}


def arquivos_nao_registrados():
    with db() as conn:
        registrados = {r["arquivo"] for r in conn.execute("SELECT arquivo FROM videos")}
    pendentes = []
    for p in UPLOAD_DIR.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower().lstrip(".") not in VIDEO_EXTS:
            continue
        rel = p.relative_to(UPLOAD_DIR).as_posix()
        if rel in registrados:
            continue
        try:
            tam = p.stat().st_size
        except OSError:
            tam = 0
        partes = p.relative_to(UPLOAD_DIR).parts
        disciplina_sug = partes[0] if len(partes) > 1 else ""
        pendentes.append({
            "rel": rel,
            "tamanho": tam,
            "titulo_sug": p.stem.replace("_", " "),
            "disciplina_sug": disciplina_sug,
        })
    return pendentes


# ============================================================
# UI
# ============================================================
st.set_page_config(page_title="Videoaulas", page_icon="🎬", layout="wide")
init_db()
iniciar_servidor()

if "video_atual" not in st.session_state:
    st.session_state.video_atual = None

st.markdown("""
<h1 style="margin-bottom: 4px;">🎬 Minhas Videoaulas</h1>
<p style="color:#8fb8cc;font-size:13px;letter-spacing:1px;margin-top:0;">
    Copie os vídeos direto para <code>uploads/</code> e clique em <b>Importar</b>.
    Player com streaming Range — ideal para arquivos grandes (4–5 GB).
</p>
""", unsafe_allow_html=True)

stt = estatisticas()
c1, c2, c3 = st.columns(3)
c1.metric("Total de aulas", stt["total"])
c2.metric("Concluídas", stt["concluidas"])
c3.metric("Espaço usado", f"{stt['gb']:.1f} GB")

with st.sidebar:
    st.header("📥 Importar do uploads/")
    st.markdown(f"""
    **Pasta monitorada:**  
    `{UPLOAD_DIR}`
    
    1. Copie o vídeo para essa pasta  
    2. Clique em **🔄 Re-escanear**  
    3. Vá na aba **📥 Importar**
    """)

    if st.button("🔄 Re-escanear uploads/", use_container_width=True):
        st.rerun()

    pendentes_count = len(arquivos_nao_registrados())
    if pendentes_count:
        st.info(f"📌 {pendentes_count} arquivo(s) aguardando importação")
    else:
        st.caption("Nenhum arquivo pendente")

    st.divider()
    st.header("🔎 Filtros")
    busca = st.text_input("Buscar", placeholder="Título, tag, anotação...")
    f_disc = st.selectbox("Disciplina", ["Todas"] + disciplinas())
    f_status = st.selectbox("Status", ["Todos"] + STATUS_OPCOES)
    f_fav = st.checkbox("⭐ Apenas favoritos")

# --------- PLAYER (topo) ---------
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
                    f"⚠️ `.{ext}` ({size_gb:.1f} GB) provavelmente **não toca no navegador** "
                    f"(MKV/AVI/HEVC). Copie a URL abaixo no VLC → *Mídia → Abrir Fluxo de Rede* (Ctrl+N):"
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

# --------- ABAS ---------
tab_aulas, tab_importar = st.tabs(["📚 Minhas aulas", "📥 Importar"])

with tab_aulas:
    videos = listar(busca, "" if f_disc == "Todas" else f_disc,
                    "" if f_status == "Todos" else f_status, favorito=f_fav)
    st.caption(f"**{len(videos)}** aula(s) encontrada(s)")

    if not videos:
        st.info("Nenhuma aula cadastrada. Use a aba **📥 Importar** para adicionar.")

    for v in videos:
        path = UPLOAD_DIR / v["arquivo"]
        existe = path.exists()
        emoji = {"não iniciada": "⚪", "em andamento": "🟡", "concluída": "🟢"}[v["status"]]
        favorito = "⭐ " if v["favorito"] else ""
        ghost = "" if existe else "👻 "
        pct = f" • {v['progresso']}%" if v["progresso"] else ""
        gb = v["tamanho"] / (1024**3)

        with st.expander(f"{ghost}{emoji} {favorito}{v['titulo']} — "
                         f"*{v['disciplina'] or 'sem disciplina'}*{pct}"):
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                if existe:
                    st.caption(f"📄 `{v['arquivo']}` • {gb:.2f} GB")
                else:
                    st.error(f"Arquivo ausente em uploads/: `{v['arquivo']}`")
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

with tab_importar:
    st.markdown(f"""
    **Pasta monitorada:** `{UPLOAD_DIR}`
    
    Copie os arquivos para essa pasta (pode criar subpastas por disciplina — o nome
    da subpasta vira a disciplina padrão).
    """)

    pendentes = arquivos_nao_registrados()

    if not pendentes:
        st.success("✅ Nenhum arquivo pendente. Todos os vídeos de `uploads/` já foram cadastrados.")
    else:
        st.info(f"📌 **{len(pendentes)}** arquivo(s) encontrado(s) para importar.")

        if st.button(f"⚡ Importar todos ({len(pendentes)})",
                     use_container_width=True, type="primary",
                     help="Usa nome do arquivo como título e nome da pasta como disciplina"):
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
