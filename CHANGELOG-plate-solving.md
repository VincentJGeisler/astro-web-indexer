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
