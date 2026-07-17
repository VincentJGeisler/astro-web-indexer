<?php

declare(strict_types=1);

use Phinx\Migration\AbstractMigration;

final class AddPlateSolving extends AbstractMigration
{
    /**
     * Adds plate-solving columns to the `files` table and creates the
     * `catalog_objects` table used for cone-search object matching.
     *
     * Fully additive and idempotent (uses IF NOT EXISTS) so it cannot
     * destroy existing data. Solved identity is stored ONLY in the new
     * columns; the header `object` column is never overwritten.
     */
    public function change(): void
    {
        // Guard: nothing to do if the base table isn't present (fresh installs
        // are handled by the initial schema migration).
        if (!$this->hasTable('files')) {
            return;
        }

        $alter = <<<'SQL'
ALTER TABLE `files`
    ADD COLUMN IF NOT EXISTS `solved_ra` DOUBLE NULL COMMENT 'Plate-solved center RA (deg, J2000)',
    ADD COLUMN IF NOT EXISTS `solved_dec` DOUBLE NULL COMMENT 'Plate-solved center Dec (deg, J2000)',
    ADD COLUMN IF NOT EXISTS `solved_rotation` FLOAT NULL COMMENT 'Plate-solved position angle (deg)',
    ADD COLUMN IF NOT EXISTS `solved_pixscale` FLOAT NULL COMMENT 'Plate-solved pixel scale (arcsec/px)',
    ADD COLUMN IF NOT EXISTS `solve_status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending|solved|failed|skipped|no_star_db',
    ADD COLUMN IF NOT EXISTS `solved_at` DATETIME NULL,
    ADD COLUMN IF NOT EXISTS `matched_objects` VARCHAR(512) NULL COMMENT 'Comma-separated catalog IDs in frame',
    ADD COLUMN IF NOT EXISTS `primary_object` VARCHAR(64) NULL COMMENT 'Best catalog match, used for filtering',
    ADD INDEX IF NOT EXISTS `idx_primary_object` (`primary_object`),
    ADD INDEX IF NOT EXISTS `idx_solve_status` (`solve_status`);
SQL;
        $this->execute($alter);

        $createCatalog = <<<'SQL'
CREATE TABLE IF NOT EXISTS `catalog_objects` (
    `id` VARCHAR(32) PRIMARY KEY COMMENT 'Canonical ID, e.g. NGC0224, IC0434',
    `common_name` VARCHAR(255) NULL,
    `messier` VARCHAR(8) NULL COMMENT 'e.g. M31 if the object has a Messier number',
    `obj_type` VARCHAR(16) NULL COMMENT 'OpenNGC Type column (G, OCl, PN, ...)',
    `ra` DOUBLE NOT NULL COMMENT 'deg J2000',
    `dec` DOUBLE NOT NULL COMMENT 'deg J2000',
    `maj_axis_arcmin` FLOAT NULL,
    INDEX `idx_radec` (`ra`, `dec`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
SQL;
        $this->execute($createCatalog);

        // Backfill: non-LIGHT frames never get plate-solved. Existing LIGHT
        // rows keep the default 'pending' so the drain loop picks them up.
        $this->execute(
            "UPDATE `files` SET `solve_status`='skipped' " .
            "WHERE `solve_status`='pending' AND (`imgtype` IS NULL OR `imgtype` <> 'LIGHT');"
        );
    }
}
