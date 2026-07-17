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
