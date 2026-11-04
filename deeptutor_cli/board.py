"""CLI commands for Learning Boards: one topic taught as Picture, Notes, Practice and Progress."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .common import console, maybe_run


def _store(root: Path | None):
    from deeptutor.board import BoardStore

    return BoardStore(root)


def register(app: typer.Typer) -> None:
    @app.command("create")
    def create(
        subject: str = typer.Option(..., "--subject", "-s", help="For example: Civil Engineering."),
        topic: str = typer.Option(..., "--topic", "-t", help="For example: Construction Planning."),
        kb: str | None = typer.Option(
            None,
            "--kb",
            help="Knowledge base with your guideline and past papers. Strongly recommended.",
        ),
        level: str = typer.Option("", "--level", help="For example: NCV Level 2."),
        questions: int = typer.Option(
            10, "--questions", "-q", min=1, max=50, help="Practice questions."
        ),
        picture: bool = typer.Option(True, "--picture/--no-picture", help="Draw a diagram (SVG)."),
        board_id: str | None = typer.Option(
            None, "--id", help="Board id. Default: built from subject and topic."
        ),
        force: bool = typer.Option(
            False, "--force", help="Replace an existing board with the same id."
        ),
        root: Path | None = typer.Option(
            None, "--root", help="Boards folder. Default: DeepTutor user data."
        ),
    ) -> None:
        """Build a topic board from one request."""
        from deeptutor.board import BoardBuilder
        from deeptutor.board.bundle import write_bundle
        from deeptutor.board.schema import slugify

        store = _store(root)
        bid = board_id or slugify(subject, topic)
        if store.exists(bid) and not force:
            console.print(
                f"[red]Board '{bid}' already exists.[/] Use --force to replace it, or pick another --id."
            )
            raise typer.Exit(code=1)

        if not kb:
            console.print(
                "[yellow]No --kb given.[/] The board will use general knowledge only. "
                "Build a knowledge base from your guideline first: deeptutor kb create <name> --doc file.pdf"
            )
        console.print(
            f"Building board '{bid}'. This makes 3 to 4 model calls and may take a minute."
        )

        result = maybe_run(
            BoardBuilder().build(
                subject=subject,
                topic=topic,
                kb=kb,
                level=level,
                questions=questions,
                with_picture=picture,
                board_id=bid,
            )
        )
        if result is None:
            raise typer.Exit(code=130)
        store.save(result.board, result.svg)
        page = write_bundle(store, bid)
        board = result.board
        console.print(f"[green]Saved[/] {store.board_dir(bid)}")
        console.print(
            f"  notes: {len(board.notes.sections)} sections, {len(board.notes.key_terms)} key terms"
            f" | questions: {len(board.practice.questions)}"
            f" | mastery path: {len(board.progress.mastery_path)}"
            f" | picture: {'yes' if board.picture.asset else 'no'}"
        )
        for warning in board.warnings:
            console.print(f"[yellow]Warning:[/] {warning}")
        console.print(f"Phone file: {page}")
        console.print(
            "[dim]This is a draft. Read it, then run: deeptutor board approve " + bid + "[/]"
        )

    @app.command("list")
    def list_boards(root: Path | None = typer.Option(None, "--root")) -> None:
        """List boards."""
        boards = _store(root).list()
        if not boards:
            console.print(
                "No boards yet. Create one with: deeptutor board create --subject ... --topic ..."
            )
            return
        for b in boards:
            console.print(
                f"[cyan]{b.board_id}[/]  {b.topic} ({b.subject})  "
                f"{len(b.practice.questions)} questions  [{b.review.status}]"
            )

    @app.command("show")
    def show(
        board_id: str = typer.Argument(...),
        root: Path | None = typer.Option(None, "--root"),
    ) -> None:
        """Print a board as JSON."""
        from deeptutor.board import BoardNotFound

        try:
            board = _store(root).load(board_id)
        except BoardNotFound as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(code=1)
        typer.echo(json.dumps(board.model_dump(mode="json"), ensure_ascii=False, indent=2))

    @app.command("bundle")
    def bundle(
        board_id: str = typer.Argument(...),
        out: Path | None = typer.Option(None, "--out", help="Where to write the HTML file."),
        root: Path | None = typer.Option(None, "--root"),
    ) -> None:
        """Write the single-file offline page to copy to a phone."""
        from deeptutor.board import BoardNotFound
        from deeptutor.board.bundle import write_bundle

        try:
            path = write_bundle(_store(root), board_id, out)
        except BoardNotFound as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(code=1)
        console.print(f"[green]Wrote[/] {path}")

    @app.command("export")
    def export(
        board_id: str = typer.Argument(...),
        fmt: str = typer.Option("pdf", "--format", "-f", help="pdf"),
        out: Path | None = typer.Option(None, "--out", help="Where to write the file."),
        root: Path | None = typer.Option(None, "--root"),
    ) -> None:
        """Write a printable PDF (notes, practice, answer key) for phones that cannot open the page."""
        from deeptutor.board import BoardNotFound
        from deeptutor.board.export_pdf import write_pdf

        if fmt != "pdf":
            console.print("[red]Only --format pdf is supported.[/]")
            raise typer.Exit(code=2)
        try:
            path = write_pdf(_store(root), board_id, out)
        except BoardNotFound as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(code=1)
        console.print(f"[green]Wrote[/] {path}")

    @app.command("studio")
    def studio(
        port: int = typer.Option(8766, "--port"),
        root: Path | None = typer.Option(None, "--root", help="Where boards are stored."),
        open_browser: bool = typer.Option(True, "--open-browser/--no-browser"),
    ) -> None:
        """Open the Learning Board Studio in your browser: level, upload, topic, Build."""
        import webbrowser

        from deeptutor.board.studio import Studio, make_studio_server

        try:  # the picture step needs the default settings files; saved settings are kept
            from deeptutor.services.config import get_runtime_settings_service

            get_runtime_settings_service().ensure_defaults()
        except Exception as exc:
            console.print(f"[yellow]Could not create default settings: {exc}[/]")
        store = _store(root)
        folder = store.root.parent / "board_studio" if root is None else Path(root) / "_studio"
        server = make_studio_server(Studio(store, folder), port)
        url = f"http://localhost:{port}/"
        console.print(
            f"Studio is open at [bold]{url}[/]. Only this computer can reach it. Press Ctrl+C to stop."
        )
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            console.print("Stopped.")
        finally:
            server.server_close()

    @app.command("approve")
    def approve(
        board_id: str = typer.Argument(...),
        root: Path | None = typer.Option(None, "--root"),
    ) -> None:
        """Mark a board as checked by a person. Removes the draft banner from the phone page."""
        from deeptutor.board import BoardNotFound
        from deeptutor.board.bundle import write_bundle

        store = _store(root)
        try:
            store.mark_reviewed(board_id)
            write_bundle(store, board_id)
        except BoardNotFound as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(code=1)
        console.print(f"[green]Marked reviewed:[/] {board_id}")

    @app.command("serve")
    def serve(
        port: int = typer.Option(8765, "--port"),
        lan: bool = typer.Option(
            False,
            "--lan",
            help="Listen on the local network so a phone on the same Wi-Fi can open it. No login. Default is this computer only.",
        ),
        root: Path | None = typer.Option(None, "--root"),
    ) -> None:
        """Serve boards to a phone. Read-only. Boards only: no DeepTutor API, no settings, no keys."""
        from deeptutor.board.server import lan_address, make_server

        host = "0.0.0.0" if lan else "127.0.0.1"
        try:
            server = make_server(_store(root), host, port)
        except OSError as exc:
            console.print(f"[red]Could not start on port {port}:[/] {exc}")
            raise typer.Exit(code=1)
        if lan:
            ip = lan_address() or "<this-computer-ip>"
            console.print(
                f"[yellow]Network mode.[/] Anyone on this Wi-Fi can read your boards at http://{ip}:{port}/"
            )
            console.print("[yellow]Do not use this on shared or public Wi-Fi.[/]")
        else:
            console.print(f"Serving on http://127.0.0.1:{port}/ (this computer only)")
            console.print(
                f"Phone over USB: adb reverse tcp:{port} tcp:{port}  then open http://localhost:{port}/ on the phone"
            )
        console.print("Press Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            console.print("\nStopped.")
        finally:
            server.server_close()


__all__ = ["register"]
