# Plate Solving — Change Log

Implementation of `docs/SPEC-plate-solving.md` on branch `feature/plate-solving`.
All verification that requires Docker (build, migrations, runtime) is performed
on the remote Docker host at **10.3.1.76** — Docker is not available on the
local dev machine.

The format is loosely based on Keep a Changelog. Each spec step (§9) is one
entry.

## [Unreleased]

### Step 1 — Schema migration (spec §4.1)
- Added Phinx migration `src/db/migrations/<ts>_add_plate_solving.php`
  (`AddPlateSolving`): ALTER TABLE `files` adding `solved_ra`, `solved_dec`,
  `solved_rotation`, `solved_pixscale`, `solve_status` (default 'pending'),
  `solved_at`, `matched_objects`, `primary_object`, plus indexes
  `idx_primary_object` and `idx_solve_status`.
- Creates `catalog_objects` table (id, common_name, messier, obj_type, ra, dec,
  maj_axis_arcmin, idx_radec).
- Backfills non-LIGHT rows to `solve_status='skipped'`.
- [ ] Verify on 10.3.1.76: restart php container (runs `phinx migrate`), then
  `SHOW COLUMNS FROM files LIKE 'solve%';` and confirm `catalog_objects` exists.
