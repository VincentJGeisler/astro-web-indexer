# Plate Solving — Progress Tracker

Branch: `feature/plate-solving`. Spec: `docs/SPEC-plate-solving.md` §9 order.
Docker verification runs on remote host **10.3.1.76** (no local Docker).

## Hard rules (do not violate)
- **NEVER push to `main` / GitHub remote.** All work stays on
  `feature/plate-solving`. A PR is opened ONLY after testing on 10.3.1.76.
- No AI authorship in commits/code/docs. Sole author: Vince Geisler.
- No `git commit --no-verify` / `-n`. Never push to any remote.

## Current step
**Step 2 — Dockerfile + compose (§4.2, §4.3)** — IN PROGRESS

## Test stack on 10.3.1.76 (isolated from live :8100 deployment)
- Project: `awi-ps`. Clone: `~/awi-ps-test` (branch `feature/plate-solving`).
- `~/awi-ps-test/.env`: `NGINX_PORT=8101`, `FITS_DATA_PATH=/mnt/astronomy`
  (read-only, shared with live), `AWI_PLATE_SOLVE=0`, `AWI_VERSION=ps-test`.
- `~/awi-ps-test/docker-compose.override.yml` (UNTRACKED, test-only) renames
  containers to `*-awi-ps` (compose hardcodes `*-awi`, which the live stack
  already occupies).
- **Gotcha (do not repeat):** `docker compose build` tags images `:latest` by
  default (via `${AWI_VERSION:-latest}`) — same tag the live containers use.
  ALWAYS keep `AWI_VERSION=ps-test` in the test `.env` so test images never
  clobber the live `:latest` tags. (Caught & restored once already.)

## Steps
1. [x] **Schema migration (§4.1)** — verified on 10.3.1.76 (Phinx OK).
2. [ ] **Dockerfile + compose (§4.2, §4.3)** — ASTAP binary, OpenNGC CSV,
       volume + env. Verify `astap_cli` execs on 10.3.1.76. IN PROGRESS.
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
