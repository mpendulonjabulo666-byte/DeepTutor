from __future__ import annotations

import asyncio
import json
import re
import threading
import urllib.error
import urllib.request

import pytest
from typer.testing import CliRunner

from deeptutor.board import BoardBuilder, BoardStore
from deeptutor.board.bundle import render_bundle, write_bundle
from deeptutor.board.schema import Board
from deeptutor.board.server import make_server

from .test_board_core import GOOD_SVG, builder


def make_board(**over) -> tuple[Board, str]:
    result = asyncio.run(
        builder().build(subject="Civil Engineering", topic="Construction Planning", kb="k")
    )
    for key, value in over.items():
        setattr(result.board, key, value)
    return result.board, result.svg or ""


def test_bundle_is_self_contained_and_offline():
    board, svg = make_board()
    page = render_bundle(board, svg)
    assert "<rect" in page and "Construction Planning" in page
    # no network: no external urls in src/href and no fetch/XHR/service worker
    assert not re.search(r"""(?:src|href)\s*=\s*["']https?://""", page)
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "serviceWorker",
        "innerHTML",
        "eval(",
        "document.write",
    ):
        assert forbidden not in page


def test_bundle_cannot_be_broken_out_of_by_board_text():
    board, svg = make_board()
    board.topic = "</script><script>alert(1)</script> __SVG__ __BOARD_JSON__"
    board.notes.summary = "<img src=x onerror=alert(1)> &   end"
    page = render_bundle(board, svg)
    assert page.lower().count("<script") == 2  # the data block and the app code only
    assert "alert(1)</script>" not in page
    data = re.search(
        r'<script type="application/json" id="board-data">(.*?)</script>', page, re.S
    ).group(1)
    parsed = json.loads(data)
    assert parsed["topic"].startswith("</script>")
    assert parsed["notes"]["summary"].startswith("<img")
    assert "<title>&lt;/script&gt;" in page
    # marker text inside values was not expanded a second time
    assert page.count(GOOD_SVG[:20]) == 1


def test_draft_flag_is_in_the_data_and_approval_flips_it(tmp_path):
    board, svg = make_board()
    store = BoardStore(tmp_path)
    store.save(board, svg)

    def page_data(path):
        text = path.read_text(encoding="utf-8")
        raw = re.search(
            r'<script type="application/json" id="board-data">(.*?)</script>', text, re.S
        ).group(1)
        return json.loads(raw)

    first = write_bundle(store, board.board_id)
    assert first.name == f"{board.board_id}.html"
    assert page_data(first)["review"]["status"] == "draft"
    store.mark_reviewed(board.board_id)
    second = write_bundle(store, board.board_id)
    assert page_data(second)["review"]["status"] == "reviewed"
    assert page_data(second)["review"]["reviewed_at"]


@pytest.fixture()
def running_server(tmp_path):
    board, svg = make_board()
    store = BoardStore(tmp_path)
    store.save(board, svg)
    server = make_server(store, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}", board.board_id
    server.shutdown()
    server.server_close()


def get(url, method="GET"):
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8")


def test_server_serves_boards_with_safe_headers(running_server):
    base, bid = running_server
    status, headers, body = get(base + "/")
    assert status == 200 and bid in body and "(draft)" in body
    status, headers, body = get(f"{base}/b/{bid}.html")
    assert status == 200 and "board-data" in body
    assert "default-src 'none'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Cache-Control"] == "no-store"
    status, _, body = get(f"{base}/b/{bid}.json")
    assert status == 200 and json.loads(body)["board_id"] == bid


@pytest.mark.parametrize(
    "path",
    [
        "/b/nope.html",
        "/b/../x.html",
        "/b/..%2f..%2fetc%2fpasswd.html",
        "/board.json",
        "/api/v1/settings",
        "/b/%2e%2e/%2e%2e/etc/passwd",
        "/.env",
        "/b/UPPER.html",
    ],
)
def test_server_refuses_everything_else(running_server, path):
    base, _ = running_server
    status, _, _ = get(base + path)
    assert status == 404


def test_server_is_read_only(running_server):
    base, bid = running_server
    for method in ("POST", "PUT", "DELETE", "PATCH"):
        req = urllib.request.Request(f"{base}/b/{bid}.html", data=b"x", method=method)
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(req, timeout=5)
        assert err.value.code == 405


def test_server_listens_on_localhost_by_default(tmp_path):
    server = make_server(BoardStore(tmp_path), port=0)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()


# ---- CLI -----------------------------------------------------------------


@pytest.fixture()
def cli(monkeypatch):
    import deeptutor.board as board_pkg
    import deeptutor_cli.board as cli_board
    from deeptutor_cli.main import app

    class FakeBuilder(BoardBuilder):
        def __init__(self):
            super().__init__(
                llm=builder()._llm, picture=builder()._picture, context=builder()._context
            )

    monkeypatch.setattr(board_pkg, "BoardBuilder", FakeBuilder)
    monkeypatch.setattr(cli_board, "maybe_run", lambda coro: asyncio.run(coro))
    return CliRunner(), app


def test_cli_create_list_show_bundle_approve(cli, tmp_path):
    runner, app = cli
    root = ["--root", str(tmp_path)]
    out = runner.invoke(
        app,
        [
            "board",
            "create",
            "-s",
            "Civil Engineering",
            "-t",
            "Construction Planning",
            "--kb",
            "k",
            *root,
        ],
    )
    assert out.exit_code == 0, out.output
    assert "Saved" in out.output and "draft" in out.output.lower()
    bid = "civil-engineering-construction-planning"
    assert (tmp_path / bid / "board.json").is_file()
    assert (tmp_path / bid / "assets" / "picture.svg").is_file()
    assert (tmp_path / bid / f"{bid}.html").is_file()

    again = runner.invoke(
        app, ["board", "create", "-s", "Civil Engineering", "-t", "Construction Planning", *root]
    )
    assert again.exit_code == 1 and "already exists" in again.output
    forced = runner.invoke(
        app,
        [
            "board",
            "create",
            "-s",
            "Civil Engineering",
            "-t",
            "Construction Planning",
            "--force",
            *root,
        ],
    )
    assert forced.exit_code == 0 and "No --kb given" in forced.output

    assert bid in runner.invoke(app, ["board", "list", *root]).output
    shown = runner.invoke(app, ["board", "show", bid, *root])
    assert json.loads(shown.output)["topic"] == "Construction Planning"

    out_file = tmp_path / "copy.html"
    assert (
        runner.invoke(app, ["board", "bundle", bid, "--out", str(out_file), *root]).exit_code == 0
    )
    assert out_file.is_file()

    assert runner.invoke(app, ["board", "approve", bid, *root]).exit_code == 0
    assert (
        json.loads(runner.invoke(app, ["board", "show", bid, *root]).output)["review"]["status"]
        == "reviewed"
    )


def test_cli_missing_board_is_a_clean_error(cli, tmp_path):
    runner, app = cli
    for args in (["show", "ghost"], ["bundle", "ghost"], ["approve", "ghost"]):
        res = runner.invoke(app, ["board", *args, "--root", str(tmp_path)])
        assert res.exit_code == 1 and "No board named" in res.output


def test_pdf_export_has_notes_practice_and_answer_key(tmp_path):
    from pypdf import PdfReader

    from deeptutor.board.export_pdf import write_pdf

    store = BoardStore(tmp_path)
    board, svg = make_board()
    store.save(board, svg)
    path = write_pdf(store, board.board_id)
    assert path.suffix == ".pdf" and path.stat().st_size > 1000
    text = "\n".join(p.extract_text() for p in PdfReader(str(path)).pages)
    assert board.topic in text
    assert "Answer key" in text and "Practice" in text and "DRAFT" in text
    store.mark_reviewed(board.board_id)
    again = write_pdf(store, board.board_id, tmp_path / "x.pdf")
    assert "DRAFT" not in "\n".join(p.extract_text() for p in PdfReader(str(again)).pages)


def test_cli_export_pdf(cli, tmp_path):
    runner, app = cli
    root = ["--root", str(tmp_path)]
    runner.invoke(app, ["board", "create", "-s", "Civil", "-t", "Planning", "--kb", "k", *root])
    out = runner.invoke(app, ["board", "export", "civil-planning", *root])
    assert out.exit_code == 0, out.output
    assert (tmp_path / "civil-planning" / "civil-planning.pdf").is_file()
    bad = runner.invoke(app, ["board", "export", "civil-planning", "-f", "docx", *root])
    assert bad.exit_code == 2


def test_bundle_has_vex_logo_fonts_and_prefixed_picture_ids():
    board, _ = make_board()
    board.level = "NCV Level 2"
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><defs><marker id="title">'
        '<path d="M0 0L1 1"/></marker></defs><line x2="5" marker-end="url(#title)"/></svg>'
    )
    page = render_bundle(board, svg)
    assert 'class="vx-logo"' in page and "VEX <b>CIPHER</b>" in page
    assert page.count("font/woff2;base64,") == 4
    # the picture cannot take over ids the page relies on, such as id="title"
    assert 'id="pic-title"' in page and "url(#pic-title)" in page
    assert page.count('id="title"') == 1
    assert '"level": "NCV Level 2"' in page
