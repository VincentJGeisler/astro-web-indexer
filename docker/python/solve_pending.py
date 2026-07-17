import os
import sys
import time
import argparse
import logging
import concurrent.futures

import mysql.connector

from indexer_lib.plate_solver import solve, star_db_present
from indexer_lib import object_matcher

# Configure logging (same style as reindex.py)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger('solve_pending')

DRAIN_BATCH = 20
SLEEP_EMPTY_S = 30


def _truthy(val):
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def parse_args():
    parser = argparse.ArgumentParser(description="Drain loop: plate-solve pending LIGHT frames.")
    parser.add_argument("fits_root", help="Root directory containing image files")
    parser.add_argument("--host", default=os.getenv("DB_HOST", "mariadb"), help="MariaDB host")
    parser.add_argument("--user", default=os.getenv("DB_USER", "awi_user"), help="Database username")
    parser.add_argument("--password",
                        default=os.getenv("DB_PASSWORD") or os.getenv("DB_PASS", "awi_password"),
                        help="Database password")
    parser.add_argument("--database", default=os.getenv("DB_NAME", "awi_db"), help="Database name")
    parser.add_argument("--workers", type=int, default=int(os.getenv("AWI_SOLVE_WORKERS", "2")),
                        help="Number of solver threads")
    parser.add_argument("--timeout", type=int, default=int(os.getenv("AWI_SOLVE_TIMEOUT", "60")),
                        help="Per-file ASTAP timeout in seconds")
    parser.add_argument("--once", action="store_true", help="Drain pending rows once and exit")
    parser.add_argument("--force-solve", action="store_true",
                        help="Also re-attempt previously failed rows")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def _sleep_forever():
    while True:
        time.sleep(3600)


def _exit_or_sleep(once):
    if once:
        sys.exit(0)
    _sleep_forever()


def _resolve_star_db(conn, cur, db_dir, present):
    """Keep solve_status consistent with star DB availability."""
    if present:
        n = cur.execute(
            "UPDATE files SET solve_status='pending' "
            "WHERE solve_status='no_star_db' AND imgtype='LIGHT' AND deleted_at IS NULL"
        )
        if cur.rowcount:
            logger.info(f"Star DB now available: requeued {cur.rowcount} no_star_db rows.")
    else:
        logger.warning(
            "ASTAP star database not found at %s. LIGHT frames will be marked "
            "'no_star_db'. To enable solving, populate the astap_db volume with "
            "the D50 database (see README 'Plate Solving')." % db_dir
        )
        cur.execute(
            "UPDATE files SET solve_status='no_star_db' "
            "WHERE solve_status='pending' AND imgtype='LIGHT' AND deleted_at IS NULL"
        )
        if cur.rowcount:
            logger.info("Marked %d pending LIGHT rows as no_star_db." % cur.rowcount)
    conn.commit()


def _pick_batch(cur, force_solve):
    statuses = ["'pending'"]
    if force_solve:
        statuses.append("'failed'")
    status_list = ",".join(statuses)
    cur.execute(
        "SELECT id, path, ra, `dec`, fov_h, width, height FROM files "
        "WHERE solve_status IN (%s) AND imgtype='LIGHT' AND deleted_at IS NULL "
        "ORDER BY id DESC LIMIT %d" % (status_list, DRAIN_BATCH)
    )
    return cur.fetchall()


def drain_once(conn, cur, fits_root, workers, timeout, db_dir, force_solve):
    workers_timeout = (workers, timeout)
    total = 0
    while True:
        rows = _pick_batch(cur, force_solve)
        if not rows:
            break
        # Solving is subprocess-bound; run solves in threads, but do all DB
        # work in the main thread (single shared connection).
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            future_map = {
                ex.submit(solve, os.path.join(fits_root, r[1]),
                          hint_ra_deg=r[2], hint_dec_deg=r[3], fov_h_arcmin=r[4],
                          timeout_s=timeout, db_dir=db_dir): r
                for r in rows
            }
            solved_results = {}
            for future in concurrent.futures.as_completed(future_map):
                r = future_map[future]
                try:
                    solved_results[r[0]] = future.result()
                except Exception as e:
                    logger.error(f"Solve raised for id={r[0]} ({r[1]}): {e}")
                    solved_results[r[0]] = None

        for r in rows:
            try:
                file_id = r[0]
                result = solved_results.get(file_id)
                abs_path = os.path.join(fits_root, r[1])
                width, height = r[5], r[6]
                if not os.path.isfile(abs_path):
                    cur.execute("UPDATE files SET solve_status='failed' WHERE id=%s", (file_id,))
                    continue
                if result is None:
                    cur.execute("UPDATE files SET solve_status='failed' WHERE id=%s", (file_id,))
                    logger.info(f"Failed to solve: {r[1]}")
                    continue
                matched_csv, primary = object_matcher.match_objects(
                    cur, result["ra"], result["dec"], width, height, result["pixscale"]
                )
                cur.execute(
                    "UPDATE files SET solved_ra=%s, solved_dec=%s, solved_rotation=%s, "
                    "solved_pixscale=%s, matched_objects=%s, primary_object=%s, "
                    "solve_status='solved', solved_at=UTC_TIMESTAMP() WHERE id=%s",
                    (result["ra"], result["dec"], result["rotation"], result["pixscale"],
                     matched_csv, primary, file_id)
                )
                logger.info(f"Solved {r[1]} -> {primary or 'no match'} "
                            f"(RA={result['ra']:.4f}, Dec={result['dec']:.4f})")
                total += 1
            except Exception as e:
                logger.error(f"Post-solve handling failed for id={r[0]} ({r[1]}): {e}")
                try:
                    cur.execute("UPDATE files SET solve_status='failed' WHERE id=%s", (r[0],))
                except Exception:
                    pass

        conn.commit()
    return total


def main():
    args = parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    if not _truthy(os.getenv("AWI_PLATE_SOLVE", "1")):
        logger.info("Plate solving disabled (AWI_PLATE_SOLVE=0).")
        _exit_or_sleep(args.once)

    db_dir = os.getenv("ASTAP_DB_DIR", "/opt/astap_db")

    try:
        conn = mysql.connector.connect(host=args.host, user=args.user,
                                       password=args.password, database=args.database)
        cur = conn.cursor()

        present = star_db_present(db_dir)
        _resolve_star_db(conn, cur, db_dir, present)

        if not present:
            logger.info("No star DB; nothing to solve.")
            _exit_or_sleep(args.once)

        seeded = object_matcher.seed_catalog(cur)
        conn.commit()
        logger.info(f"Catalog ready (seeded {seeded} new objects).")

        if args.once:
            total = drain_once(conn, cur, args.fits_root, args.workers,
                               args.timeout, db_dir, args.force_solve)
            logger.info(f"Drain pass complete. Solved {total} file(s).")
            conn.close()
            return

        logger.info(f"Entering drain loop (workers={args.workers}, timeout={args.timeout}s).")
        while True:
            total = drain_once(conn, cur, args.fits_root, args.workers,
                               args.timeout, db_dir, args.force_solve)
            if total == 0:
                time.sleep(SLEEP_EMPTY_S)
    except mysql.connector.Error as err:
        logger.error(f"Database error: {err}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted.")
    finally:
        try:
            if 'conn' in locals() and conn.is_connected():
                conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
