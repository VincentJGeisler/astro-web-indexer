# Plate Solving — Change Log

Implementation of `docs/SPEC-plate-solving.md` on branch `feature/plate-solving`.
All verification that requires Docker (build, migrations, runtime) is performed
on the remote Docker host at **10.3.1.76** — Docker is not available on the
local dev machine.

The format is loosely based on Keep a Changelog. Each spec step (§9) is one
entry.

## [Unreleased]

### Step 1 — Schema migration (spec §4.1) — VERIFIED on 10.3.1.76
- Added Phinx migration `src/db/migrations/20260716203022_add_plate_solving.php`
  (`AddPlateSolving`): ALTER TABLE `files` adding `solved_ra`, `solved_dec`,
  `solved_rotation`, `solved_pixscale`, `solve_status` (default 'pending'),
  `solved_at`, `matched_objects`, `primary_object`, plus indexes
  `idx_primary_object` and `idx_solve_status`.
- Creates `catalog_objects` table (id, common_name, messier, obj_type, ra, dec,
  maj_axis_arcmin, idx_radec).
- Backfills non-LIGHT rows to `solve_status='skipped'`. Migration uses
  `IF NOT EXISTS` so it is idempotent and cannot destroy data.
- Verified in isolated test stack `awi-ps` (project `awi-ps`, containers
  `*-awi-ps`, port 8101, image tag `:ps-test`, separate DB volume; live
  `*-awi` deployment at :8100 untouched): Phinx applied it, all columns /
  indexes / `catalog_objects` present; backfill confirmed LIGHT stays
  `pending`, DARK + NULL imgtype -> `skipped` via throwaway rows.

### Step 2 — Dockerfile + compose (spec §4.2, §4.3) — VERIFIED on 10.3.1.76
- `docker/python/Dockerfile`: base switched to `python:3.9-slim` (Debian) so
  the glibc ASTAP CLI runs natively (alpine+gcompat is unreliable for the
  FreePascal binary; this is the spec-approved fallback). Downloads ASTAP CLI
  v2026.07.16 (MPL 2.0) and OpenNGC `NGC.csv` pinned to release `v20260501`.
- `docker-compose.yml` + `docker-compose.release.yml`: `astap_db` named volume
  mounted at `/opt/astap_db`; new env `AWI_PLATE_SOLVE`, `AWI_SOLVE_WORKERS`,
  `AWI_SOLVE_TIMEOUT`. Documented in `.env.example`.
- Verified: `astap_cli` execs in-container (banner + usage, exit 0) —
  acceptance #1. `NGC.csv` present (13,969 objects). D50 installed into the
  volume (910 MB, 1476 `d50_*.1476` files). Test image isolated as `:ps-test`;
  live `:latest` tags untouched.

### Step 3 — `plate_solver.py` + tests (spec §4.4, §8) — VERIFIED on 10.3.1.76
- `indexer_lib/plate_solver.py`: `star_db_present()`, `solve()`, defensive
  `.ini` parser (PLTSOLVD/CRVAL1/CRVAL2/CDELT2/optional CROTA2), XISF->FITS
  fallback. All ASTAP output goes to a per-call temp dir under `/tmp/astap`,
  cleaned in `finally`.
- `tests/test_plate_solver.py`: 8 unit tests, all pass (run in-container).
- Real end-to-end solve on an NGC 185 light frame: returned RA=9.74°,
  Dec=48.34° (matches NGC 185), pixscale=0.3465″/px (matches header geometry),
  5.1s hinted. Failure path returns `None` (bad hint, 2.7s) and missing-file
  returns `None`. `/tmp/astap` stays clean.
- Note: the real-solve test frame has no `IMAGETYP` header, so it would be
  `skipped` by the drain loop; `solve()` itself works regardless.

### Step 4 — `object_matcher.py` + tests (spec §4.5, §8) — VERIFIED on 10.3.1.76
- `indexer_lib/object_matcher.py`: `seed_catalog()` (idempotent OpenNGC load,
  batches of 500, skips blank RA/Dec) and `match_objects()` (dec/RA band
  pre-filter via `idx_radec`, exact haversine check, largest-object-first
  ordering, `matched_objects` <=512 chars with no truncated IDs, Messier
  preferred for `primary_object`, RA 0/360 wrap + pole-safe).
- `tests/test_object_matcher.py`: 23 tests pass (run in-container with DB).
- Real-data checks: seeded 13,962 objects; M31 -> `messier='M31'`;
  `match_objects` on the solved NGC 185 frame returns `primary=NGC0185`.

### Step 5 — `solve_pending.py` drain loop (spec §4.6) — VERIFIED on 10.3.1.76
- `docker/python/solve_pending.py`: standalone drain loop mirroring reindex.py
  conventions. Honors `AWI_PLATE_SOLVE`; reconciles `no_star_db`<->`pending`
  against D50 availability; solves pending LIGHT rows in a ThreadPoolExecutor
  (all DB writes on the main thread), matches objects, commits per batch of 20.
  `--once` / `--force-solve` / `--debug`; per-file errors never kill the loop.
- Verified with synthetic rows over real frames: LIGHT -> `solved`
  (`primary_object=NGC0185`); unsolvable LIGHT -> `failed` (loop continues);
  DARK -> `skipped` (untouched); missing file -> `failed`. Disabled path exits
  0; empty star DB marks pending LIGHT -> `no_star_db` with one warning + exit
  (no busy-loop) — acceptance #2, #4, #5.

### Step 7 — PHP UI + translations + SFF (spec §4.8) — VERIFIED on 10.3.1.76
- `src/includes/db_functions.php`: `buildQueryParts` / `countFiles` /
  `getFiles` / `sumExposureTime` now take `$solvedObject` param; new
  `getDistinctSolvedObjects()` for the filter facet.
- `src/includes/init.php`: reads `$filterSolvedObject = $_GET['solved_object']`.
- `src/includes/filters.php`: "Identified object" select, wired exactly like
  the existing object filter; pagination preserves `solved_object` via `$_GET`.
- `src/includes/template_functions.php`: `formatRaDegToHms`, `formatDecDegToDms`,
  `solveStatusLabel`, `getIdentifiedObjectMarkup` (status dot, solve tooltip,
  header-mismatch badge).
- `src/includes/table.php`: always-visible `primary_object` column (list + thumb
  views); 6 new advanced-view columns (solve_status, solved_ra/dec/pixscale/
  rotation, matched_objects).
- `src/api/find_calibration_files.php`: SFF RA/Dec matching prefers
  `COALESCE(solved_ra, ra)` / `COALESCE(solved_dec, dec)`.
- All 5 language files: 15 new keys. PHP lint clean. HTTP 200 on index +
  solved_object filter. Acceptance #9 (5 hits) passes.

### Step 8 — README + .env.example docs (spec §4.3, §8) — done
- README.md: "Plate Solving" section — how it works, D50 volume setup command,
  environment variable table. Also updated `technologies` list with ASTAP/OpenNGC.
- `.env.example`: AWI_PLATE_SOLVE, AWI_SOLVE_WORKERS, AWI_SOLVE_TIMEOUT with
  comments. (Committed as part of step 2.)

### Step 9 — Full acceptance pass (spec §7) — ALL PASS
| # | Result |
|---|--------|
| 1 | astap_cli prints usage inside python container (CLI-2026.07.16, MPL 2.0). |
| 2 | Empty astap_db → LIGHT rows → no_star_db, one clear warning, no crash/loop. |
| 3 | NGC0185 LIGHT frame solves to primary_object=NGC0185 (matches reality). |
| 4 | UNKNOWN/DARK/FLAT rows → solve_status=skipped, ASTAP never invoked. |
| 5 | Unsolvable frame → failed; drain loop continues (tested step 5). |
| 6 | Reindex unchanged files: processed=0, skipped=12; solved row unchanged. |
| 7 | catalog_objects: 13,962 rows; re-seed returns 0 (idempotent). |
| 8 | /tmp/astap is empty after solve; /var/fits mount is read-only. |
| 9 | grep identified_object src/languages/*.php → 5 hits. |
| 10 | HTTP 200, 12 thumbnails generated, SFF/moon phase/duplicates functional. |
- `reindex.py`: computes `solve_status` (`pending` for LIGHT, else `skipped`)
  in the worker, adds it to the INSERT, and resets the solve columns in the ON
  DUPLICATE KEY UPDATE. The full update only fires for content-changed files,
  so unchanged solved rows are preserved.
- `Dockerfile` CMD: `reindex && (solve_pending & watch_fs)`.
- Verified with synthetic FITS: LIGHT->`pending`, DARK->`skipped`; re-run on
  unchanged files keeps a solved row `solved` (acceptance #6); rewriting a
  file resets its solve columns to `pending`. Container CMD smoke test: all
  three phases start correctly.
