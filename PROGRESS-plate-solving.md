# Plate Solving — Progress Tracker

Branch: `feature/plate-solving`. Spec: `docs/SPEC-plate-solving.md` §9 order.

## Hard rules (do not violate)
- **NEVER push to `main` / GitHub remote.** All work stays on
  `feature/plate-solving`. A PR is opened ONLY after testing on 10.3.1.76.
- No AI authorship in commits/code/docs. Sole author: Vince Geisler.
- No `git commit --no-verify` / `-n`. Never push to any remote.

## Current step
**COMPLETE — deployed to live stack at 10.3.1.76:8100**

## Steps
1. [x] **Schema migration (§4.1)** — verified on 10.3.1.76 (Phinx OK).
2. [x] **Dockerfile + compose (§4.2, §4.3)** — astap_cli execs in-container;
       NGC.csv present (13969 rows). Base switched to python:3.9-slim.
3. [x] **`plate_solver.py` + tests (§4.4, §8)** — 8 unit tests pass; real solve
       on NGC 185 frame correct.
4. [x] **`object_matcher.py` + tests (§4.5, §8)** — 23 tests pass; 13,962
       objects seeded; NGC 185 -> primary=NGC0185.
5. [x] **`solve_pending.py` drain loop (§4.6)** — all paths verified.
6. [x] **`reindex.py` touch-up + Dockerfile CMD (§4.7)** — solve_status set
       on insert; unchanged files keep solved status (acceptance #6).
7. [x] **PHP UI + translations + SFF (§4.8)** — lint clean, HTTP 200, all 5
       language files have 15 new keys.
8. [x] **README + `.env.example` docs** — Plate Solving section added.
9. [x] **Full acceptance pass (§7)** — all 10 criteria pass.

## Live deployment (10.3.1.76:8100) — DONE
- Feature branch pulled into `~/src/astro-web-indexer`, images rebuilt.
- Migration applied: `files` table has all new solve columns;
  15,414 non-LIGHT rows = `skipped`; 907 LIGHT rows = `pending`.
- `astap_db` volume created (empty — D50 not yet installed; see README).
- Python container reindexing 2780 new/changed files; drain loop starts
  automatically after reindex completes.
- **To enable solving:** populate the `astap_db` volume with D50 per README.

## Next
1. Install D50 star database into `astro-web-indexer_astap_db` volume (README).
2. Watch `docker logs python-awi` — drain loop will log solve progress.
3. When ready, open PR: `feature/plate-solving` -> `main` (or `dev`).
