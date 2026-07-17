# Plate Solving — Progress Tracker

Branch: `feature/plate-solving`. Spec: `docs/SPEC-plate-solving.md` §9 order.
Docker verification runs on remote host **10.3.1.76** (no local Docker).

## Hard rules (do not violate)
- **NEVER push to `main` / GitHub remote.** All work stays on
  `feature/plate-solving`. A PR is opened ONLY after testing on 10.3.1.76.
- No AI authorship in commits/code/docs. Sole author: Vince Geisler.
- No `git commit --no-verify` / `-n`. Never push to any remote.

## Current step
**Step 1 — Schema migration (§4.1)** — IN PROGRESS

## Steps
1. [ ] **Schema migration (§4.1)** — write migration; verify on 10.3.1.76.
2. [ ] **Dockerfile + compose (§4.2, §4.3)** — ASTAP binary, OpenNGC CSV,
       volume + env. Verify `astap_cli` execs on 10.3.1.76.
3. [ ] **`plate_solver.py` + tests (§4.4, §8)**.
4. [ ] **`object_matcher.py` + tests (§4.5, §8)**.
5. [ ] **`solve_pending.py` drain loop (§4.6)** — run `--once` on 10.3.1.76.
6. [ ] **`reindex.py` touch-up (§4.7)** — set `solve_status` on insert/update.
7. [ ] **PHP UI + translations + SFF (§4.8)**.
8. [ ] **README + `.env.example` docs.**
9. [ ] **Full acceptance pass (§7).**

## Verification notes
- Local machine has no Docker daemon. All `docker compose build` / `phinx
  migrate` / runtime checks must be run on 10.3.1.76.
- Python 3.11 available locally; unit tests under `docker/python/tests/` can be
  run locally with `python -m pytest` (after adding pytest to a dev
  requirements file), but they must not be added to the runtime image.
