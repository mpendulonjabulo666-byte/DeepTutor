"""Tutor editing chat: ask the AI to change a draft's notes, with undo.

The chat is private to the tutor. It is kept next to the board but outside
``board.json``, so students never receive it. Every change first saves the
previous notes as a version. Editing an approved board makes it a draft again.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Awaitable, Callable

from pydantic import ValidationError

from .schema import Notes, Practice
from .store import BoardNotFound, BoardStore

ChatLLM = Callable[[str, str], Awaitable[str]]

EDIT_SYSTEM = (
    "You help a tutor edit the study notes of a board before students see it. "
    "You receive the current notes and practice questions as JSON and the tutor's request. Reply with JSON only: "
    '{"reply": "one or two plain sentences saying what you changed, or a question if the request '
    'is unclear", "notes": <the full updated notes object, same keys as given> or null, '
    '"practice": <the full updated practice object, same keys as given> or null}. '
    "Return null for a part that should not change. In practice, every question keeps its id, "
    "type, a correct answer and a marking guide; question ids stay unique. Rules: keep the same JSON shape; change only what the tutor asked for; "
    "write plain, easy wording for someone who does not yet understand; keep sections short; "
    "never invent facts, numbers or standards - if the tutor asks for something you cannot support "
    "from the notes or the tutor's own words, say so in reply and return notes null."
)


class EditError(ValueError):
    pass


class BoardEditor:
    def __init__(self, store: BoardStore, llm: ChatLLM | None = None) -> None:
        self.store = store
        self._llm = llm

    async def _ask(self, prompt: str) -> str:
        if self._llm:
            return await self._llm(prompt, EDIT_SYSTEM)
        from .builder import default_llm

        return await default_llm(prompt, EDIT_SYSTEM)

    def _dir(self, board_id: str) -> Path:
        base = self.store.board_dir(board_id)
        if not (base / "board.json").is_file():
            raise BoardNotFound(board_id)
        d = base / "_tutor"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def history(self, board_id: str) -> list[dict[str, Any]]:
        try:
            return json.loads((self._dir(board_id) / "chat.json").read_text("utf-8"))
        except (OSError, ValueError):
            return []

    def _log(self, board_id: str, role: str, text: str) -> None:
        h = self.history(board_id)[-60:]
        h.append({"role": role, "text": text[:2000], "at": int(time.time())})
        (self._dir(board_id) / "chat.json").write_text(json.dumps(h, indent=1), encoding="utf-8")

    def versions(self, board_id: str) -> list[Path]:
        return sorted(self._dir(board_id).glob("notes-*.json"))

    async def send(self, board_id: str, message: str) -> dict[str, Any]:
        message = " ".join(str(message).split())[:1500]
        if not message:
            raise EditError("Type what you want changed.")
        board = self.store.load(board_id)
        self._log(board_id, "tutor", message)
        prompt = (
            f"Subject: {board.subject}\nTopic: {board.topic}\nLevel: {board.level}\n\n"
            f"CURRENT NOTES JSON:\n{json.dumps(board.notes.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            f"CURRENT PRACTICE JSON:\n{json.dumps(board.practice.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            f"TUTOR REQUEST:\n{message}"
        )
        from deeptutor.utils.json_parser import parse_json_response

        data = parse_json_response(await self._ask(prompt), fallback=None)
        if not isinstance(data, dict):
            reply = "I could not work out that change. Try saying it another way."
            self._log(board_id, "ai", reply)
            return {"reply": reply, "changed": False}
        reply = str(data.get("reply") or "Done.")[:600]
        notes = practice = None
        failed = False
        if isinstance(data.get("notes"), dict):
            try:
                notes = Notes.model_validate(data["notes"])
                if not notes.sections:
                    notes = None
            except ValidationError:
                failed = True
        if isinstance(data.get("practice"), dict):
            try:
                practice = Practice.model_validate(data["practice"])
                if not practice.questions:
                    practice = None
            except ValidationError:
                failed = True
        changed = False
        if failed and notes is None and practice is None:
            reply = "That change did not come out in a usable shape, so nothing was changed. Try again."
        elif notes is not None or practice is not None:
            self._save_version(board_id, board.notes, board.practice)
            if notes is not None:
                board.notes = notes
            if practice is not None:
                board.practice = practice
            board.review.status = "draft"
            board.review.reviewed_at = ""
            self.store.save(board)
            changed = True
        self._log(board_id, "ai", reply)
        return {"reply": reply, "changed": changed}

    def _save_version(self, board_id: str, notes: Notes, practice: Practice) -> None:
        path = self._dir(board_id) / f"notes-{int(time.time() * 1000)}.json"
        snap = {"notes": notes.model_dump(mode="json"), "practice": practice.model_dump(mode="json")}
        path.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")

    def undo(self, board_id: str) -> bool:
        vs = self.versions(board_id)
        if not vs:
            return False
        last = vs[-1]
        board = self.store.load(board_id)
        snap = json.loads(last.read_text("utf-8"))
        if "sections" in snap:  # an older version that held only notes
            snap = {"notes": snap}
        board.notes = Notes.model_validate(snap["notes"])
        if snap.get("practice") is not None:
            board.practice = Practice.model_validate(snap["practice"])
        board.review.status = "draft"
        board.review.reviewed_at = ""
        self.store.save(board)
        last.unlink()
        self._log(board_id, "ai", "Undone: the notes and questions are back to how they were before the last change.")
        return True
