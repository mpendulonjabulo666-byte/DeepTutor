# Learning Board

[Handbook](README.md) · [Related guide](AGENT_SETUP.md)

A Learning Board teaches one topic in four sections: **Picture** (a labelled
diagram), **Notes**, **Practice** (questions with marking) and **Progress**
(a mastery path and weak areas). It is private and local-first: the laptop
builds the board, and the phone opens one HTML file that works offline.

## What it reuses

| Section | Built with |
| --- | --- |
| Picture | The visualize pipeline in `deeptutor/agents/visualize`, forced to SVG, then cleaned by `deeptutor/board/svg.py` |
| Notes, Practice, Progress | `deeptutor.services.llm.complete` with strict JSON, checked against `deeptutor/board/schema.py` |
| Source material | An existing knowledge base (`deeptutor kb create`), searched with `RAGService` |

Questions use the same types as the question bank (`single_choice`,
`multi_choice`, `true_false`, `fill_blank`, `short_answer`). Phase 1 does not
write boards into the question bank or the mastery path store; it produces a
self-contained board.

## Studio (no typing of topics or paths)

```powershell
python -m pip install -r requirements/board.txt
deeptutor board studio
```

A page opens in your browser (`http://localhost:8766/`, this computer only).
Choose school, NCV or Nated and your level once, type your subject, upload the
subject guideline and past papers (PDF with real text, Word or text file),
pick a topic and press **Build board**. A build takes a minute or three. The
board is made only from the uploaded files; a PDF that is photos of pages
(a scan) is read with Gemini, ten pages at a time, which sends those pages to
Google and can take a few minutes (limit 120 pages). Each board then has **Open**, **PDF**, **Phone file** and
**Approve**. Your choices and files stay in `data/user/board_studio/`.

## Free Gemini limits

On Google's free tier, `gemini-3.8-flash` allows about 20 requests a day (as
published in October 2026; check your own Google AI Studio usage page). One
board uses roughly 6 to 12 requests and reading a scanned PDF uses one per ten
pages, so that allowance runs out fast. The daily limit resets at midnight
Pacific time, about 10:00 South African time. Flash-Lite models list a much
larger free allowance (about 500 a day). To switch, put that model's name from
AI Studio into `setup.json`, run `deeptutor config apply setup.json`, then
`deeptutor doctor --online`. If a build fails because of the allowance, the
studio says so and saves no empty board.

## Commands

```bash
deeptutor board create --subject "Civil Engineering" --topic "Construction Planning" \
    --kb construction-planning --level "NCV Level 2" --questions 10
deeptutor board list
deeptutor board show <board_id>              # board JSON
deeptutor board bundle <board_id>            # rewrite the phone page
deeptutor board export <board_id>            # printable PDF: notes, practice, answer key
deeptutor board approve <board_id>           # remove the draft banner after you checked it
deeptutor board serve [--port 8765] [--lan]  # read-only server for a phone
```

Boards are stored in `data/user/boards/<board_id>/`: `board.json`,
`assets/picture.svg` and `<board_id>.html`. Every command accepts
`--root <folder>` to use another folder.

A new board is a **draft**. The phone page shows a banner until someone runs
`deeptutor board approve`. Read every note and answer against your guideline
first. If a section fails to generate, the board is still saved with a warning.

The PDF includes the diagram only when `svglib` is installed
(`python -m pip install svglib`); otherwise it points to the phone page.

## Look

The phone page uses the Vex design: one dark page with Picture, Notes,
Practice and Progress cards, and tabs that jump to each card. The animated Vex
"V" logo and the Barlow fonts are embedded from `deeptutor/board/brand.json`
(fonts under the SIL OFL, see `deeptutor/board/FONT_LICENSE.md`), so the page
still makes no network request. Animations pause when the page is hidden, and
stop for people who ask their phone for less motion or switch them off in
Settings. This is branding only; the board is not connected to Vex.

## Board JSON (schema version 1)

Defined in `deeptutor/board/schema.py`. Top level: `schema_version`,
`board_id`, `subject`, `topic`, `generated_at`, `sources`, `picture`, `notes`,
`practice`, `progress`, `explainers`, `review`, `warnings`. Each explainer has
`kp_id`, `title`, `explanation`, `example`, `mistake` and a `check` question. Another client can read this file
without importing DeepTutor.

## Safety

- The phone page makes no network request, loads no library, and writes board
  text with `textContent`. The only markup is the SVG, which is stripped of
  scripts, event handlers, external references, `foreignObject` and animation.
- `board serve` serves only board pages and JSON. It does not expose the
  DeepTutor API, settings or keys. It listens on `127.0.0.1` unless `--lan` is
  given, and `--lan` has no login: anyone on that network can read the boards.
- `deeptutor serve` (the full backend) listens on `0.0.0.0` by default. Do not
  use it on shared Wi-Fi without login enabled.
- Generation sends parts of your guideline to the configured model provider.

## Windows laptop and Android phone

PowerShell, from the repository root. Python 3.11 to 3.14 is required.

```powershell
git checkout feature/deeptutor-board
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements/full.txt
python -m pip install -e . --no-deps
python -m pip install -r requirements/board.txt
```

Set the Gemini key without it appearing in your history:

```powershell
$k = Read-Host "Gemini API key" -AsSecureString
$env:DEEPTUTOR_SETUP_LLM_KEY = [System.Net.NetworkCredential]::new("", $k).Password
$env:DEEPTUTOR_SETUP_EMBEDDING_KEY = $env:DEEPTUTOR_SETUP_LLM_KEY
```

Create `setup.json` (use the model ids your Gemini account offers):

```json
{
  "llm": { "provider": "gemini", "model": "YOUR_GEMINI_MODEL_ID", "api_key_env": "DEEPTUTOR_SETUP_LLM_KEY" },
  "embedding": { "provider": "gemini", "model": "YOUR_GEMINI_EMBEDDING_MODEL_ID", "api_key_env": "DEEPTUTOR_SETUP_EMBEDDING_KEY" }
}
```

```powershell
deeptutor config apply setup.json --check
deeptutor config apply setup.json
deeptutor doctor --online
deeptutor kb create construction-planning --doc "C:\path\guideline.pdf" --doc "C:\path\past-paper.pdf"
deeptutor board create --subject "Civil Engineering" --topic "Construction Planning" `
    --kb construction-planning --level "NCV Level 2"
```

Phone, option 1 (no server): connect the phone by USB in file-transfer mode,
copy `<board_id>.html` to its Downloads folder, open it from the Files app in
Chrome. Turn on airplane mode and reload to prove it works offline.

Phone, option 2 (USB server): turn on USB debugging, install Android platform
tools, then

```powershell
deeptutor board serve
adb reverse tcp:8765 tcp:8765
```

and open `http://localhost:8765/` in Chrome on the phone.

Checks on the phone: all four tabs work in airplane mode; answer five
questions, close the page, reopen it, and confirm the answers are still there.
If a file opened from Downloads does not keep answers, use **Save progress
file** and **Load progress file** on the Progress tab, or use option 2.
