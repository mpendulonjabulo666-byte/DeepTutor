# Learning Board roadmap

[Handbook](README.md) · [Learning Board](BOARD.md)

This page records where the Learning Board is going. It is a plan, not current
behaviour. What exists today is described in [BOARD.md](BOARD.md).

## Vision

- Cortex Synapse is the company. The Learning Board and Vex are its products.
- A tutoring centre at home, with a materials lab where learners see how
  concrete, steel and bricks behave. Later, a school.
- The owner also wants to become a materials scientist. Maths and science
  boards are part of that path.
- Stages: (1) one person studies with the board; (2) a few learners use it at
  home, free or cheap; (3) the centre opens; (4) much later, the school.
- Check with the municipality early about using a home building for teaching.

## Built

- Four-section board (Picture, Notes, Practice, Progress) as JSON and one
  offline HTML page.
- `deeptutor board studio`: choose route and level once, upload the guideline
  and past papers, pick a topic, press Build.
- PDF export with an answer key.

## Next, in order

1. Explainer mode. A wrong answer opens a plain explanation with a South
   African construction example and a fresh question on the same idea.
2. Pictures that match the notes: a label check against the notes, and a
   picture for each explanation where it helps.
3. Study on PC and phone with saved answers and weak areas shown.
4. Send a finished board to a phone (USB first).
5. Cortex Synapse logo on every board page and the PDF.
6. Extras: a real diagram from a free library (for example Wikimedia Commons)
   shown next to the drawn one, with its source and licence saved. Check
   whether SolidCraft can export pictures for 3D shapes.

## Rules that still hold

- Local only. No public site, no payments, no store distribution.
- No Vex integration until the Vex code has been read. Any later work happens
  on a separate branch and leaves `vex-v0` alone. Proposal wording:
  "Vex may later fetch and cache DeepTutor boards using its existing
  phone-pairing system."
- Board data stays exportable as JSON.
- Every board is a draft until a person has checked it against the guideline.
- The guideline may be old. The NCV Construction Planning Level 2 guideline is
  dated April 2008, so confirm with the lecturer that the exam follows it.
