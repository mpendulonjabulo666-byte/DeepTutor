"""Learning Board studio: a local page to pick your level, upload your
guideline, choose a topic and press Build.

It is for one person on one computer. It listens on 127.0.0.1 only, has no
accounts, and never returns an API key. Uploaded files and your choices stay in
a folder on this computer.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable
from urllib.parse import unquote, urlsplit
import uuid

from .bundle import render_bundle, write_bundle
from .store import BoardNotFound, BoardStore

DEFAULT_PORT = 8766
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_DOCS = 20
ALLOWED_EXT = {".pdf", ".txt", ".md", ".docx"}

# South African study routes. NCV runs Level 2 to 4; Nated N4 to N6; school Grade 10 to 12.
CURRICULA: dict[str, dict[str, Any]] = {
    "school": {"label": "School (Grade 10 to 12)", "levels": ["Grade 10", "Grade 11", "Grade 12"]},
    "ncv": {"label": "College: NCV", "levels": ["Level 2", "Level 3", "Level 4"]},
    "nated": {"label": "College: Nated", "levels": ["N4", "N5", "N6"]},
}
_TOPIC_LINE = re.compile(
    r"^\s*Topic\s+(\d+)\s*[:.\-]\s*(.{3,120}?)\s*$", re.IGNORECASE | re.MULTILINE
)
_WEIGHT_LINE = re.compile(r"^\s*\d+\.\s+(.{3,120}?)\s+(\d{1,3})\s*%\s*$", re.MULTILINE)


def friendly_error(text: str) -> str:
    """Turn a provider error into something a student can act on."""
    low = text.lower()
    if "429" in low or "quota" in low or "resource_exhausted" in low:
        return (
            "Your free Gemini allowance for this model is used up. It comes back at about "
            "10:00 South African time. Or switch to a model with a bigger free allowance."
        )
    if "503" in low or "unavailable" in low or "high demand" in low:
        return "Google is busy right now. Wait a minute and press Build again."
    return text


class StudioError(ValueError):
    """A problem the person can fix (shown on the page)."""


# ---------------------------------------------------------------- profile


def clean_profile(raw: dict[str, Any]) -> dict[str, str]:
    curriculum = str(raw.get("curriculum", "")).strip()
    if curriculum not in CURRICULA:
        raise StudioError("Choose school, NCV or Nated.")
    level = str(raw.get("level", "")).strip()
    if level not in CURRICULA[curriculum]["levels"]:
        raise StudioError("Choose a level that matches your route.")
    programme = " ".join(str(raw.get("programme", "")).split())[:120]
    subject = " ".join(str(raw.get("subject", "")).split())[:120]
    if not subject:
        raise StudioError("Type your subject, for example Construction Planning.")
    return {
        "curriculum": curriculum,
        "level": level,
        "programme": programme,
        "subject": subject,
    }


def level_text(profile: dict[str, str]) -> str:
    route = {"school": "South African school (CAPS)", "ncv": "NCV", "nated": "Nated"}[
        profile["curriculum"]
    ]
    sep = ", " if profile["curriculum"] == "school" else " "
    bits = [f"{route}{sep}{profile['level']}"]
    if profile.get("programme"):
        bits.append(profile["programme"])
    bits.append(
        "South Africa. Explain in simple English with South African examples. "
        "Follow the uploaded guideline and past papers."
    )
    return ", ".join(bits)


def short_level(profile: dict[str, str]) -> str:
    """A short label for the board header, for example 'NCV Level 2' or 'Grade 11'."""
    if profile["curriculum"] == "school":
        return profile["level"]
    route = {"ncv": "NCV", "nated": "Nated"}[profile["curriculum"]]
    return f"{route} {profile['level']}"


# ---------------------------------------------------------------- documents


def extract_text(name: str, data: bytes) -> str:
    ext = Path(name).suffix.lower()
    if ext in {".txt", ".md"}:
        return data.decode("utf-8", errors="replace")
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - depends on install
            raise StudioError(
                "Reading PDFs needs a package. Run: python -m pip install -r requirements/board.txt"
            ) from exc
        import io

        try:
            reader = PdfReader(io.BytesIO(data))
            return "\n\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:
            raise StudioError(f"That PDF could not be read: {exc}") from exc
    if ext == ".docx":
        try:
            import io

            from docx import Document
        except ImportError as exc:  # pragma: no cover
            raise StudioError("Reading Word files needs python-docx.") from exc
        try:
            return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
        except Exception as exc:
            raise StudioError(f"That Word file could not be read: {exc}") from exc
    raise StudioError("Upload a PDF, Word (.docx) or text file.")


def detect_topics(text: str) -> list[dict[str, Any]]:
    """Find 'Topic N: name' lines (NCV subject guidelines) and their weights."""
    weights = {m.group(1).strip().lower(): int(m.group(2)) for m in _WEIGHT_LINE.finditer(text)}
    seen: dict[int, str] = {}
    for m in _TOPIC_LINE.finditer(text):
        number = int(m.group(1))
        seen.setdefault(number, m.group(2).strip().rstrip("."))
    topics = []
    for number in sorted(seen):
        name = seen[number]
        topics.append({"number": number, "name": name, "weight": weights.get(name.lower())})
    return topics


def _chunks(text: str, size: int = 1200) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out: list[str] = []
    cur = ""
    for para in paras:
        if cur and len(cur) + len(para) > size:
            out.append(cur)
            cur = ""
        cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        out.append(cur)
    return out


_TOPIC_HEAD = re.compile(r"Topic\s+(\d+)\s*[:.\-]\s*(.{3,120}?)\s*$", re.IGNORECASE | re.MULTILINE)
_SECTION_END = re.compile(r"\n\s*(?:8\s+)?RESOURCE NEEDS", re.IGNORECASE)


def topic_section(texts: list[str], topic: str, limit: int = 11_000) -> str:
    """The guideline's own section for one topic (from its heading to the next topic)."""
    want = " ".join(topic.lower().split())
    best = ""
    for text in texts:
        heads = list(_TOPIC_HEAD.finditer(text))
        for i, m in enumerate(heads):
            name = " ".join(m.group(2).lower().split()).rstrip(".")
            if name != want and want not in name and name not in want:
                continue
            end = len(text)
            for nxt in heads[i + 1 :]:
                if nxt.group(1) != m.group(1):
                    end = nxt.start()
                    break
            tail = _SECTION_END.search(text, m.start())
            if tail and tail.start() < end:
                end = tail.start()
            chunk = text[m.start() : end].strip()
            if len(chunk) > len(best):
                best = chunk
    return best[:limit]


def pick_passages(texts: list[str], query: str, limit: int = 11_000) -> str:
    """Choose the passages that mention the query words most; keep document order."""
    words = {w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 3}
    scored: list[tuple[int, int, str]] = []
    pos = 0
    for text in texts:
        for chunk in _chunks(text):
            low = chunk.lower()
            score = sum(low.count(w) for w in words)
            scored.append((score, pos, chunk))
            pos += 1
    chosen: list[tuple[int, str]] = []
    used = 0
    for score, p, chunk in sorted(scored, key=lambda t: (-t[0], t[1])):
        if score <= 0 or used + len(chunk) > limit:
            continue
        chosen.append((p, chunk))
        used += len(chunk)
    return "\n\n---\n\n".join(c for _, c in sorted(chosen))


# ---------------------------------------------------------------- state


@dataclass
class Job:
    id: str
    topic: str
    status: str = "running"  # running | done | failed
    board_id: str = ""
    error: str = ""
    warnings: list[str] = field(default_factory=list)
    started: float = field(default_factory=time.time)
    finished: float = 0.0

    def public(self) -> dict[str, Any]:
        end = self.finished or time.time()
        return {
            "id": self.id,
            "topic": self.topic,
            "status": self.status,
            "board_id": self.board_id,
            "error": self.error,
            "warnings": self.warnings,
            "seconds": int(end - self.started),
        }


BuilderFactory = Callable[[Callable[[str, str], Any]], Any]


class Studio:
    def __init__(
        self,
        store: BoardStore,
        folder: Path | str,
        builder_factory: BuilderFactory | None = None,
        ocr: Callable[[bytes], str] | None = None,
    ) -> None:
        self.store = store
        self.folder = Path(folder)
        self.docs_dir = self.folder / "docs"
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._builder_factory = builder_factory or self._default_builder
        self._ocr = ocr

    @staticmethod
    def _default_builder(context):
        from .builder import BoardBuilder

        return BoardBuilder(context=context)

    # profile
    @property
    def _profile_path(self) -> Path:
        return self.folder / "profile.json"

    def profile(self) -> dict[str, str] | None:
        try:
            return clean_profile(json.loads(self._profile_path.read_text("utf-8")))
        except (OSError, ValueError, StudioError):
            return None

    def save_profile(self, raw: dict[str, Any]) -> dict[str, str]:
        profile = clean_profile(raw)
        self._profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        return profile

    # documents
    @property
    def _index_path(self) -> Path:
        return self.docs_dir / "index.json"

    def docs(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self._index_path.read_text("utf-8"))
        except (OSError, ValueError):
            return []
        return [
            d for d in data if isinstance(d, dict) and (self.docs_dir / f"{d['id']}.txt").is_file()
        ]

    def _write_index(self, docs: list[dict[str, Any]]) -> None:
        self._index_path.write_text(json.dumps(docs, indent=2), encoding="utf-8")

    def add_doc(self, filename: str, data: bytes) -> dict[str, Any]:
        name = Path(filename.replace("\\", "/")).name[:120] or "upload"
        if Path(name).suffix.lower() not in ALLOWED_EXT:
            raise StudioError("Upload a PDF, Word (.docx) or text file.")
        if not data or len(data) > MAX_UPLOAD_BYTES:
            raise StudioError("That file is empty or bigger than 25 MB.")
        current = self.docs()
        if len(current) >= MAX_DOCS:
            raise StudioError("Remove a file first. The limit is 20.")
        text = extract_text(name, data).strip()
        if len(text) < 200 and name.lower().endswith(".pdf"):
            text = self._read_scanned(data) or text
        if len(text) < 200:
            raise StudioError(
                "No readable text found. A scanned PDF (photos of pages) cannot be read yet; "
                "upload a PDF with real text, or a Word or text file."
            )
        doc_id = uuid.uuid4().hex[:12]
        (self.docs_dir / f"{doc_id}.txt").write_text(text, encoding="utf-8")
        meta = {"id": doc_id, "name": name, "chars": len(text)}
        self._write_index([*current, meta])
        return meta

    def _read_scanned(self, data: bytes) -> str:
        """A PDF with no text layer is photos of pages: read it with Gemini."""
        from .ocr import OcrUnavailable, ocr_pdf_with_gemini

        try:
            return (self._ocr or ocr_pdf_with_gemini)(data).strip()
        except OcrUnavailable as exc:
            raise StudioError(f"This PDF is photos of pages. {exc}") from exc
        except Exception as exc:
            raise StudioError(f"This PDF is photos of pages and could not be read: {exc}") from exc

    def delete_doc(self, doc_id: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{12}", doc_id):
            raise StudioError("Unknown file.")
        (self.docs_dir / f"{doc_id}.txt").unlink(missing_ok=True)
        self._write_index([d for d in self.docs() if d["id"] != doc_id])

    def texts(self) -> list[str]:
        return [(self.docs_dir / f"{d['id']}.txt").read_text("utf-8") for d in self.docs()]

    def topics(self) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for text in self.texts():
            for t in detect_topics(text):
                merged.setdefault(t["name"].lower(), t)
        return list(merged.values())

    # build
    def start_build(self, topic: str, questions: int, with_picture: bool) -> Job:
        profile = self.profile()
        if not profile:
            raise StudioError("Choose your level and subject first.")
        topic = " ".join(str(topic).split())[:200]
        if not topic:
            raise StudioError("Choose or type a topic.")
        if not self.docs():
            raise StudioError("Upload your guideline or a past paper first.")
        questions = max(3, min(int(questions), 30))
        with self._lock:
            if any(j.status == "running" for j in self._jobs.values()):
                raise StudioError("A board is already being built. Wait for it to finish.")
            job = Job(id=uuid.uuid4().hex[:10], topic=topic)
            self._jobs[job.id] = job
        threading.Thread(
            target=self._run, args=(job, profile, questions, with_picture), daemon=True
        ).start()
        return job

    def _run(self, job: Job, profile: dict[str, str], questions: int, with_picture: bool) -> None:
        texts = self.texts()

        section = topic_section(texts, job.topic)

        async def context(_kb: str, query: str) -> str:
            if section and "exam questions" not in query:
                # the guideline's own section first; add best matches only if it is short
                extra = ""
                if len(section) < 3000:
                    extra = "\n\n---\n\n" + pick_passages(texts, query, 11_000 - len(section))
                return section + extra
            return pick_passages(texts, query)

        try:
            builder = self._builder_factory(context)
            result = asyncio.run(
                builder.build(
                    subject=profile["subject"],
                    topic=job.topic,
                    kb="your uploaded files",
                    level=level_text(profile),
                    questions=questions,
                    with_picture=with_picture,
                )
            )
            board = result.board
            board.level = short_level(profile)
            board.programme = profile.get("programme", "")
            if not board.notes.sections and not board.practice.questions:
                reasons = " ".join(board.warnings)
                raise RuntimeError(friendly_error(reasons) or "Nothing could be generated.")
            self.store.save(result.board, result.svg)
            write_bundle(self.store, result.board.board_id)
            job.board_id = result.board.board_id
            job.warnings = [friendly_error(w) if len(w) > 120 else w for w in result.board.warnings]
            job.status = "done"
        except Exception as exc:  # shown to the person; details stay short
            job.error = friendly_error(str(exc))[:400] or exc.__class__.__name__
            job.status = "failed"
        finally:
            job.finished = time.time()

    def job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def latest_job(self) -> Job | None:
        return max(self._jobs.values(), key=lambda j: j.started, default=None)

    def state(self) -> dict[str, Any]:
        latest = self.latest_job()
        return {
            "profile": self.profile(),
            "curricula": CURRICULA,
            "docs": self.docs(),
            "topics": self.topics(),
            "boards": [
                {
                    "id": b.board_id,
                    "topic": b.topic,
                    "subject": b.subject,
                    "status": b.review.status,
                    "generated_at": b.generated_at,
                }
                for b in self.store.list()
            ],
            "job": latest.public() if latest else None,
        }


# ---------------------------------------------------------------- http

_BOARD_ROUTE = re.compile(r"^/b/([a-z0-9][a-z0-9-]{0,79})\.(html|json|pdf)$")
_CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "connect-src 'self'; img-src data:; base-uri 'none'; form-action 'none'; "
    "frame-ancestors 'none'"
)


def make_studio_server(
    studio: Studio, port: int = DEFAULT_PORT, *, phone_token: str | None = None
) -> ThreadingHTTPServer:
    """``phone_token`` opens the studio to other devices on your Wi-Fi.

    Every request must then carry the secret token (first in the link, then in a
    cookie). Without it the server answers only 127.0.0.1 and localhost.
    """
    import hmac

    from .studio_page import PAGE

    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _cookie_token(header: str) -> str:
        for part in header.split(";"):
            name, _, value = part.strip().partition("=")
            if name == "vb":
                return value
        return ""

    class Handler(BaseHTTPRequestHandler):
        server_version = "BoardStudio"

        def log_message(self, *args: Any) -> None:  # keep the console quiet
            return

        # -- helpers
        def _send(self, code: int, body: bytes, ctype: str, extra: dict[str, str] | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if "Content-Security-Policy" not in (extra or {}):
                self.send_header("Content-Security-Policy", _CSP)
            self.send_header("Referrer-Policy", "no-referrer")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, code: int, data: Any) -> None:
            self._send(code, json.dumps(data).encode("utf-8"), "application/json")

        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").lower()
            if phone_token is None:
                return host in allowed_hosts
            if host in allowed_hosts:
                return True  # the laptop itself
            if not host.endswith(f":{port}"):
                return False
            given = _cookie_token(self.headers.get("Cookie") or "")
            return hmac.compare_digest(given, phone_token)

        def _phone_login(self) -> bool:
            """Handle the one-time link: set the cookie and go to the page."""
            if phone_token is None:
                return False
            parts = urlsplit(self.path)
            m = re.search(r"(?:^|&)k=([0-9A-Za-z_-]+)", parts.query)
            if parts.path != "/" or not m:
                return False
            if not hmac.compare_digest(m.group(1), phone_token):
                self._json(403, {"error": "That link is not valid. Open the new link from the laptop."})
                return True
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header(
                "Set-Cookie", f"vb={phone_token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800"
            )
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return True

        def _post_ok(self) -> bool:
            # A custom header cannot be sent by another website without our consent.
            return self.headers.get("X-Studio") == "1"

        def _body(self) -> bytes:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length < 0 or length > MAX_UPLOAD_BYTES:
                raise StudioError("That file is empty or bigger than 25 MB.")
            return self.rfile.read(length)

        def _json_body(self) -> dict[str, Any]:
            try:
                data = json.loads(self._body() or b"{}")
            except ValueError as exc:
                raise StudioError("That request was not understood.") from exc
            if not isinstance(data, dict):
                raise StudioError("That request was not understood.")
            return data

        # -- verbs
        def do_GET(self) -> None:  # noqa: N802
            self._get()

        do_HEAD = do_GET  # noqa: N815

        def _get(self) -> None:
            if self._phone_login():
                return
            if not self._host_ok():
                return self._json(403, {"error": "Wrong host."})
            path = urlsplit(self.path).path
            if path == "/":
                return self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            if path == "/api/state":
                return self._json(200, studio.state())
            m = re.fullmatch(r"/api/jobs/([0-9a-f]{10})", path)
            if m:
                job = studio.job(m.group(1))
                return (
                    self._json(200, job.public())
                    if job
                    else self._json(404, {"error": "No such job."})
                )
            m = _BOARD_ROUTE.match(unquote(path))
            if m:
                return self._board(m.group(1), m.group(2))
            self._json(404, {"error": "Not found."})

        def _board(self, board_id: str, kind: str) -> None:
            try:
                board = studio.store.load(board_id)
                svg = studio.store.read_asset(board)
                if kind == "html":
                    return self._send(
                        200,
                        render_bundle(board, svg).encode("utf-8"),
                        "text/html; charset=utf-8",
                        {"Content-Security-Policy": _board_csp()},
                    )
                if kind == "json":
                    return self._send(
                        200,
                        json.dumps(
                            board.model_dump(mode="json"), ensure_ascii=False, indent=2
                        ).encode(),
                        "application/json",
                    )
                from .export_pdf import write_pdf

                pdf = write_pdf(studio.store, board_id)
                return self._send(
                    200,
                    pdf.read_bytes(),
                    "application/pdf",
                    {"Content-Disposition": f'attachment; filename="{board_id}.pdf"'},
                )
            except BoardNotFound:
                self._json(404, {"error": "No such board."})
            except ImportError:
                self._json(
                    500,
                    {
                        "error": "PDF needs a package. Run: python -m pip install -r requirements/board.txt"
                    },
                )

        def do_POST(self) -> None:  # noqa: N802
            if not self._host_ok():
                return self._json(403, {"error": "Wrong host."})
            if not self._post_ok():
                return self._json(403, {"error": "Blocked."})
            path = urlsplit(self.path).path
            try:
                if path == "/api/profile":
                    return self._json(200, {"profile": studio.save_profile(self._json_body())})
                if path == "/api/docs":
                    name = unquote(self.headers.get("X-Filename") or "upload")
                    return self._json(200, {"doc": studio.add_doc(name, self._body())})
                m = re.fullmatch(r"/api/docs/([0-9a-f]{12})/delete", path)
                if m:
                    studio.delete_doc(m.group(1))
                    return self._json(200, {"ok": True})
                if path == "/api/build":
                    body = self._json_body()
                    job = studio.start_build(
                        str(body.get("topic", "")),
                        int(body.get("questions", 10) or 10),
                        bool(body.get("with_picture", True)),
                    )
                    return self._json(200, {"job": job.public()})
                m = re.fullmatch(r"/api/boards/([a-z0-9][a-z0-9-]{0,79})/approve", path)
                if m:
                    studio.store.mark_reviewed(m.group(1))
                    write_bundle(studio.store, m.group(1))
                    return self._json(200, {"ok": True})
            except StudioError as exc:
                return self._json(400, {"error": str(exc)})
            except BoardNotFound:
                return self._json(404, {"error": "No such board."})
            except (TypeError, ValueError):
                return self._json(400, {"error": "That request was not understood."})
            self._json(404, {"error": "Not found."})

    bind = "0.0.0.0" if phone_token else "127.0.0.1"  # noqa: S104 - token required
    return ThreadingHTTPServer((bind, port), Handler)


def _board_csp() -> str:
    return (
        "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "img-src data:; font-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )
