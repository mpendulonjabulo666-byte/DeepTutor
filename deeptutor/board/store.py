"""Disk storage for boards: one folder per board id.

<root>/<board_id>/board.json
<root>/<board_id>/assets/picture.svg
<root>/<board_id>/<board_id>.html        (offline bundle, written by bundle.py)
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil

from deeptutor.services.file_io import atomic_write_json, atomic_write_text

from .schema import BOARD_ID_PATTERN, Board, utc_now_iso


class BoardNotFound(LookupError):
    pass


class BoardStore:
    def __init__(self, root: Path | str | None = None) -> None:
        if root is None:
            from deeptutor.services.path_service import PathService

            root = PathService.get_instance().get_user_root() / "boards"
        self.root = Path(root)

    def board_dir(self, board_id: str) -> Path:
        if not BOARD_ID_PATTERN.match(board_id or ""):
            raise BoardNotFound(f"Invalid board id: {board_id!r}")
        return self.root / board_id

    def exists(self, board_id: str) -> bool:
        try:
            return (self.board_dir(board_id) / "board.json").is_file()
        except BoardNotFound:
            return False

    def save(self, board: Board, svg: str | None = None) -> Path:
        folder = self.board_dir(board.board_id)
        if svg:
            asset = board.picture.asset or "assets/picture.svg"
            atomic_write_text(folder / asset, svg)
            board.picture.asset = asset
        atomic_write_json(folder / "board.json", board.model_dump(mode="json"))
        return folder

    def load(self, board_id: str) -> Board:
        path = self.board_dir(board_id) / "board.json"
        if not path.is_file():
            raise BoardNotFound(f"No board named {board_id!r}")
        return Board.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def read_asset(self, board: Board) -> str:
        """Return the picture's SVG text, or an empty string when there is none."""
        if not board.picture.asset:
            return ""
        folder = self.board_dir(board.board_id).resolve()
        target = (folder / board.picture.asset).resolve()
        if folder not in target.parents or not target.is_file():
            return ""
        return target.read_text(encoding="utf-8")

    def list(self) -> list[Board]:
        boards: list[Board] = []
        if not self.root.is_dir():
            return boards
        for child in sorted(self.root.iterdir()):
            if (child / "board.json").is_file():
                try:
                    boards.append(self.load(child.name))
                except Exception:
                    continue
        return boards

    def mark_reviewed(self, board_id: str) -> Board:
        board = self.load(board_id)
        board.review.status = "reviewed"
        board.review.reviewed_at = utc_now_iso()
        self.save(board)
        return board

    def delete(self, board_id: str) -> None:
        folder = self.board_dir(board_id)
        if not folder.is_dir():
            raise BoardNotFound(f"No board named {board_id!r}")
        shutil.rmtree(folder)


__all__ = ["BoardNotFound", "BoardStore"]
