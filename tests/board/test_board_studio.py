from __future__ import annotations

import io
import json
import threading
import time
import urllib.error
from urllib.parse import quote
import urllib.request

import pytest

from deeptutor.board import BoardBuilder, BoardStore
from deeptutor.board.studio import (
    Studio,
    StudioError,
    clean_profile,
    detect_topics,
    level_text,
    make_studio_server,
    pick_passages,
)

from .test_board_core import fake_llm, good_picture

GUIDE = (
    "CONSTRUCTION PLANNING - LEVEL 2\n\n"
    "1.   Terminology and components of the construction industry        5%\n"
    "2.   Measuring, setting out and levelling                          25%\n\n"
    "Topic 1: Terminology and components of the construction industry\n\n"
    "Topic 2: Measuring, setting out and levelling\n\n"
    "7.2 Measuring, setting out and levelling. Describe and use measuring instruments such as "
    "tapes, levels and theodolites. Set out strip footing foundations for a residential house. "
    "Use a dumpy level to transfer heights. "
    * 3
    + "\n\nUnrelated paragraph about assessment weights and portfolios of evidence. " * 2
)
PROFILE = {
    "curriculum": "ncv",
    "level": "Level 2",
    "programme": "Civil Engineering",
    "subject": "Construction Planning",
}


def test_profile_validation_and_level_text():
    p = clean_profile(PROFILE)
    assert "NCV Level 2" in level_text(p) and "Civil Engineering" in level_text(p)
    assert "simple English" in level_text(p)
    with pytest.raises(StudioError):
        clean_profile({**PROFILE, "level": "N5"})
    with pytest.raises(StudioError):
        clean_profile({**PROFILE, "curriculum": "uni"})
    with pytest.raises(StudioError):
        clean_profile({**PROFILE, "subject": "  "})
    school = clean_profile({"curriculum": "school", "level": "Grade 11", "subject": "Maths"})
    assert "Grade 11" in level_text(school)


def test_topics_and_passages():
    topics = detect_topics(GUIDE)
    assert [t["number"] for t in topics] == [1, 2]
    assert topics[1]["weight"] == 25 and topics[0]["weight"] == 5
    got = pick_passages([GUIDE], "Construction Planning Measuring setting out levelling")
    assert "theodolites" in got
    assert pick_passages([GUIDE], "zzzz qqqq") == ""


def make_studio(tmp_path):
    store = BoardStore(tmp_path / "boards")
    seen = {}

    def factory(context):
        seen["context"] = context
        return BoardBuilder(llm=fake_llm(), picture=good_picture, context=context)

    return Studio(store, tmp_path / "studio", factory), seen


def wait_done(studio, job, secs=10):
    end = time.time() + secs
    while time.time() < end:
        if job.status != "running":
            return
        time.sleep(0.05)
    raise AssertionError("build did not finish")


def test_full_flow_builds_a_board_from_uploaded_files(tmp_path):
    studio, seen = make_studio(tmp_path)
    with pytest.raises(StudioError, match="level"):
        studio.start_build("Foundations", 5, True)
    studio.save_profile(PROFILE)
    with pytest.raises(StudioError, match="Upload"):
        studio.start_build("Foundations", 5, True)
    with pytest.raises(StudioError):
        studio.add_doc("notes.exe", b"x" * 500)
    with pytest.raises(StudioError, match="No readable text"):
        studio.add_doc("scan.txt", b"short")
    doc = studio.add_doc("guideline.txt", GUIDE.encode())
    assert studio.state()["topics"][1]["name"].startswith("Measuring")
    job = studio.start_build("Measuring, setting out and levelling", 5, True)
    wait_done(studio, job)
    assert job.status == "done", job.error
    board = studio.store.load(job.board_id)
    assert board.review.status == "draft"
    assert (tmp_path / "boards" / job.board_id / f"{job.board_id}.html").is_file()
    import asyncio

    ctx = asyncio.run(seen["context"]("x", "theodolites setting out"))
    assert "theodolites" in ctx
    studio.delete_doc(doc["id"])
    assert studio.docs() == []


def test_a_failed_build_is_reported_not_raised(tmp_path):
    store = BoardStore(tmp_path / "b")

    def factory(context):
        raise RuntimeError("no key set")

    studio = Studio(store, tmp_path / "s", factory)
    studio.save_profile(PROFILE)
    studio.add_doc("g.txt", GUIDE.encode())
    job = studio.start_build("Foundations", 5, False)
    wait_done(studio, job)
    assert job.status == "failed" and "no key set" in job.error


def call(port, path, method="GET", data=None, headers=None, host=None):
    h = {"Host": host or f"127.0.0.1:{port}", **(headers or {})}
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=data, method=method, headers=h
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_http_flow_and_safety(tmp_path):
    studio, _ = make_studio(tmp_path)
    import socket

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    srv = make_studio_server(studio, port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        code, headers, body = call(port, "/")
        assert code == 200 and b"Vboard" in body
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        # wrong Host header (DNS rebinding) is refused
        assert call(port, "/api/state", host="evil.example")[0] == 403
        # POST without the custom header is refused
        assert call(port, "/api/profile", "POST", b"{}")[0] == 403
        xs = {"X-Studio": "1", "Content-Type": "application/json"}
        bad = call(port, "/api/profile", "POST", json.dumps({"curriculum": "x"}).encode(), xs)
        assert bad[0] == 400 and b"Choose" in bad[2]
        ok = call(port, "/api/profile", "POST", json.dumps(PROFILE).encode(), xs)
        assert ok[0] == 200
        up = call(
            port,
            "/api/docs",
            "POST",
            GUIDE.encode(),
            {"X-Studio": "1", "X-Filename": quote("My guideline.txt")},
        )
        assert up[0] == 200
        state = json.loads(call(port, "/api/state")[2])
        assert (
            state["profile"]["level"] == "Level 2"
            and state["docs"][0]["name"] == "My guideline.txt"
        )
        assert "api_key" not in json.dumps(state).lower()
        started = json.loads(
            call(
                port,
                "/api/build",
                "POST",
                json.dumps({"topic": "Foundations", "questions": 4}).encode(),
                xs,
            )[2]
        )["job"]
        end = time.time() + 10
        while time.time() < end:
            job = json.loads(call(port, f"/api/jobs/{started['id']}")[2])
            if job["status"] != "running":
                break
            time.sleep(0.05)
        assert job["status"] == "done", job
        bid = job["board_id"]
        html = call(port, f"/b/{bid}.html")
        assert (
            html[0] == 200
            and b"Practice" in html[2]
            and "connect-src" not in html[1]["Content-Security-Policy"]
        )
        assert call(port, f"/b/{bid}.json")[0] == 200
        pdf = call(port, f"/b/{bid}.pdf")
        assert pdf[0] == 200 and pdf[2][:4] == b"%PDF"
        assert call(port, f"/api/boards/{bid}/approve", "POST", b"{}", xs)[0] == 200
        assert studio.store.load(bid).review.status == "reviewed"
        assert call(port, "/b/../etc/passwd")[0] == 404
        assert call(port, "/nope")[0] == 404
    finally:
        srv.shutdown()
        srv.server_close()


def test_pdf_upload_is_read(tmp_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in GUIDE.splitlines():
        if line.strip():
            c.drawString(40, y, line[:110])
            y -= 14
    c.save()
    studio, _ = make_studio(tmp_path)
    studio.add_doc("guide.pdf", buf.getvalue())
    assert any(t["number"] == 2 for t in studio.topics())


def test_weights_with_single_spacing():
    text = "1. Foundations 10% \n2. Behaviour of structures 25% \nTopic 1: Foundations\nTopic 2: Behaviour of structures\n"
    assert [t["weight"] for t in detect_topics(text)] == [10, 25]


def test_scanned_pdf_is_read_with_the_ocr_fallback(tmp_path):
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.rect(50, 50, 100, 100)  # a page with a drawing and no text: stands in for a scan
    c.save()
    store = BoardStore(tmp_path / "b")
    seen = {}

    def fake_ocr(data: bytes) -> str:
        seen["bytes"] = len(data)
        return GUIDE

    studio = Studio(store, tmp_path / "s", ocr=fake_ocr)
    studio.add_doc("scan.pdf", buf.getvalue())
    assert seen["bytes"] > 0 and studio.topics()[1]["number"] == 2

    from deeptutor.board.ocr import OcrUnavailable

    def no_gemini(data: bytes) -> str:
        raise OcrUnavailable("Reading scanned PDFs needs Gemini to be your configured model.")

    plain = Studio(store, tmp_path / "s2", ocr=no_gemini)
    with pytest.raises(StudioError, match="photos of pages"):
        plain.add_doc("scan.pdf", buf.getvalue())


def test_gemini_ocr_splits_pages_and_retries(tmp_path, monkeypatch):
    from reportlab.pdfgen import canvas

    from deeptutor.board import ocr

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for _ in range(12):
        c.rect(10, 10, 20, 20)
        c.showPage()
    c.save()
    monkeypatch.setattr(ocr, "_gemini_settings", lambda: ("gemini-test", "KEY"))
    monkeypatch.setattr(ocr.time, "sleep", lambda s: None)
    calls = []

    class Resp:
        def __init__(self, code, text=""):
            self.status_code = code
            self._t = text

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": self._t}]}}]}

    def post(url, headers, json, timeout):
        calls.append((url, headers["x-goog-api-key"]))
        return Resp(503) if len(calls) == 1 else Resp(200, f"text{len(calls)}")

    out = ocr.ocr_pdf_with_gemini(buf.getvalue(), post=post)
    assert len(calls) == 3  # first part retried once, second part once: 12 pages = 2 parts
    assert "text2" in out and "text3" in out and "gemini-test" in calls[0][0]


def test_a_build_with_no_notes_and_no_questions_fails_clearly(tmp_path):
    from .test_board_core import fake_llm

    class Quota(Exception):
        pass

    async def broke(prompt, system_prompt, **kw):
        raise Quota("HTTP 429 Error: You exceeded your current quota")

    def factory(context):
        return BoardBuilder(llm=broke, picture=good_picture, context=context)

    studio = Studio(BoardStore(tmp_path / "b"), tmp_path / "s", factory)
    studio.save_profile(PROFILE)
    studio.add_doc("g.txt", GUIDE.encode())
    job = studio.start_build("Foundations", 5, False)
    wait_done(studio, job)
    assert job.status == "failed" and "allowance" in job.error
    assert studio.store.list() == []


SECTIONED = (
    "Topic 1: Terminology and components\n\nTopic 2: Measuring, setting out and levelling\n\n"
    "7.1 Topic 1: Terminology and components\nDefine the terms used on site.\n\n"
    "7.2 Topic 2: Measuring, setting out and levelling\n7.2.1 Subject Outcome 1: Describe and use "
    "measuring instruments. Steel tape, ranging rods, dumpy level.\n\n"
    "7.3 Topic 3: Foundations\nPrinciples of founding structures.\n\n8 RESOURCE NEEDS\nPhysical resources.\n"
)


def test_topic_section_returns_only_that_topic():
    from deeptutor.board.studio import topic_section

    got = topic_section([SECTIONED], "Measuring, setting out and levelling")
    assert "dumpy level" in got and "Foundations" not in got and "Physical resources" not in got
    last = topic_section([SECTIONED], "Foundations")
    assert "Principles of founding" in last and "Physical resources" not in last
    assert topic_section([SECTIONED], "Nothing like it") == ""


def test_phone_mode_needs_the_secret_link(tmp_path):
    import http.client
    import threading

    from deeptutor.board.store import BoardStore
    from deeptutor.board.studio import Studio, make_studio_server

    studio = Studio(BoardStore(tmp_path), tmp_path / "s")
    server = make_studio_server(studio, 0, phone_token="secrettoken123")
    port = server.server_address[1]
    # the port is only known after binding, so rebuild with it
    server.server_close()
    server = make_studio_server(studio, port, phone_token="secrettoken123")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        def get(path, headers=None):
            c = http.client.HTTPConnection("127.0.0.1", port)
            c.request("GET", path, headers={"Host": f"192.168.1.5:{port}", **(headers or {})})
            r = c.getresponse()
            return r.status, r.getheader("Set-Cookie"), r.read()

        assert get("/")[0] == 403
        assert get("/?k=wrong")[0] == 403
        code, cookie, _ = get("/?k=secrettoken123")
        assert code == 302 and "vb=secrettoken123" in cookie and "HttpOnly" in cookie
        code, _, body = get("/", {"Cookie": "vb=secrettoken123"})
        assert code == 200 and b"Vboard" in body
        assert get("/api/state", {"Cookie": "vb=nope"})[0] == 403
    finally:
        server.shutdown()


def test_focus_reaches_every_prompt_and_trash_restores(tmp_path):
    import asyncio

    from deeptutor.board.builder import BoardBuilder
    from deeptutor.board.store import BoardStore
    from deeptutor.board.studio import Studio

    seen: list[str] = []

    async def llm(prompt: str, system_prompt: str = "") -> str:
        seen.append(prompt)
        return "{}"

    async def pic(*a):
        return "<svg xmlns='http://www.w3.org/2000/svg'/>"

    async def ctx(kb, q):
        return "source text"

    asyncio.run(
        BoardBuilder(llm=llm, picture=pic, context=ctx).build(
            subject="S", topic="T", kb="k", with_picture=False, focus="go deep on levelling"
        )
    )
    assert seen and all("go deep on levelling" in p for p in seen[:1])

    store = BoardStore(tmp_path / "boards")
    d = store.board_dir("demo-board")
    d.mkdir(parents=True)
    (d / "board.json").write_text("{}")
    studio = Studio(store, tmp_path / "studio")
    studio.trash_board("demo-board")
    assert not d.exists() and studio.trashed()[0]["id"] == "demo-board"
    assert studio.restore_board(studio.trashed()[0]["key"]) == "demo-board"
    assert (d / "board.json").exists() and studio.trashed() == []


def test_pictures_and_editing_chat(tmp_path):
    import asyncio
    import json
    import struct
    import zlib

    from deeptutor.board.pictures import PictureError
    from deeptutor.board.schema import Board, NoteSection, Notes
    from deeptutor.board.store import BoardStore
    from deeptutor.board.studio import Studio

    def png():
        raw = b"\x00\xff\x00\x00"
        def chunk(t, d):
            c = struct.pack(">I", len(d)) + t + d
            return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

    async def llm(prompt, system):
        notes = {"summary": "s", "sections": [{"heading": "Simple", "points": ["Easy words."]}],
                 "formulas": [], "key_terms": []}
        return json.dumps({"reply": "Made it simpler.", "notes": notes})

    store = BoardStore(tmp_path / "b")
    board = Board(board_id="demo-board", subject="S", topic="T",
                  notes=Notes(sections=[NoteSection(heading="Hard", points=["Complex."])]))
    store.save(board)
    store.mark_reviewed("demo-board")
    st = Studio(store, tmp_path / "s", chat_llm=llm)

    pic = st.library.add("Level.PNG", png(), "Dumpy level")
    svg, meta = st.library.svg_for(pic["id"])
    assert "data:image/png;base64," in svg and meta["caption"] == "Dumpy level"
    for bad in (b"not a picture", b"<html><script>x</script></html>"):
        try:
            st.library.add("x.png", bad)
            raise AssertionError("accepted")
        except PictureError:
            pass

    out = asyncio.run(st.editor.send("demo-board", "make it simpler"))
    assert out["changed"] and store.load("demo-board").notes.sections[0].heading == "Simple"
    assert store.load("demo-board").review.status == "draft"  # edits need a new approval
    assert st.editor.undo("demo-board")
    assert store.load("demo-board").notes.sections[0].heading == "Hard"
    assert "_tutor" not in json.dumps(store.load("demo-board").model_dump())  # students never get the chat


def test_chat_edits_practice_and_undo_restores_both(tmp_path):
    import asyncio
    import json

    from deeptutor.board.schema import Board, NoteSection, Notes, Practice, Question
    from deeptutor.board.store import BoardStore
    from deeptutor.board.studio import Studio

    def q(text):
        return Question(id="q1", type="short_answer", question=text, answer="Because.", marks=2)

    async def llm(prompt, system):
        assert "CURRENT PRACTICE JSON" in prompt
        new = Practice(questions=[q("Easier question?")]).model_dump(mode="json")
        return json.dumps({"reply": "Made question 1 easier.", "notes": None, "practice": new})

    store = BoardStore(tmp_path / "b")
    store.save(Board(board_id="demo-board", subject="S", topic="T",
                     notes=Notes(sections=[NoteSection(heading="H", points=["p"])]),
                     practice=Practice(questions=[q("Hard question?")])))
    st = Studio(store, tmp_path / "s", chat_llm=llm)
    out = asyncio.run(st.editor.send("demo-board", "make question 1 easier"))
    b = store.load("demo-board")
    assert out["changed"] and b.practice.questions[0].question == "Easier question?"
    assert b.notes.sections[0].heading == "H"  # untouched part stays
    assert st.editor.undo("demo-board")
    assert store.load("demo-board").practice.questions[0].question == "Hard question?"


def test_picture_description_guides_the_build(tmp_path):
    from deeptutor.board.store import BoardStore
    from deeptutor.board.studio import Job, Studio

    seen = {}
    st = Studio(BoardStore(tmp_path / "b"), tmp_path / "s", describe=lambda raw, mime: seen.setdefault("mime", mime) and "Staff: 1.5 m reading")
    svg = b"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'><text x='1' y='2'>Backsight</text><text x='1' y='5'>Foresight</text></svg>"
    pic = st.library.add("a.svg", svg, "Levelling")
    job = Job(id="j", topic="T")
    assert st._picture_parts(pic["id"], job) == "Backsight; Foresight"  # SVG read locally, no network
    off = st.library.add("p.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 40, "Photo")
    assert st._picture_parts(off["id"], job) == "" and "mime" not in seen  # not sent unless ticked
    on = st.library.add("q.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 40, "Photo", ai_read=True)
    assert st._picture_parts(on["id"], job) == "Staff: 1.5 m reading" and seen["mime"] == "image/png"


def test_picture_url_refuses_private_and_bad_addresses():
    import pytest

    from deeptutor.board.pictures import PictureError, fetch_picture

    for bad in ("http://127.0.0.1/a.png", "http://localhost/a.png", "file:///etc/passwd", "ftp://x.org/a.png", ""):
        with pytest.raises(PictureError):
            fetch_picture(bad)


def test_picture_from_web_keeps_source_and_licence(tmp_path):
    from deeptutor.board.pictures import PictureLibrary

    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="5" height="5"/></svg>'
    lib = PictureLibrary(tmp_path)
    a = lib.add("a.svg", svg, "Level", False, "https://example.org/a.svg", "")
    b = lib.add("b.svg", svg, "Plain")
    assert a["source_url"] == "https://example.org/a.svg" and a["license"] == "not checked"
    assert "source_url" not in b


def test_scan_inbox_imports_once_and_reports_problems(tmp_path):
    from deeptutor.board.store import BoardStore
    from deeptutor.board.studio import Studio

    st = Studio(BoardStore(tmp_path / "boards"), tmp_path / "studio")
    (st.inbox / "sub").mkdir()
    (st.inbox / "notes.txt").write_text("Levelling uses a dumpy level. " * 20, "utf-8")
    (st.inbox / "sub" / "p.svg").write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="5" height="5"/></svg>'
    )
    (st.inbox / "short.txt").write_text("too short", "utf-8")
    r = st.scan_inbox()
    assert sorted(r["added"]) == ["notes.txt", "p.svg"] and len(r["problems"]) == 1
    assert len(st.docs()) == 1 and len(st.library.list()) == 1
    r2 = st.scan_inbox()
    assert r2["added"] == [] and r2["problems"] == []
