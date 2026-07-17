import os
import csv
import math
import logging

logger = logging.getLogger('reindex.object_matcher')

NGC_CSV_PATH = os.getenv("NGC_CSV_PATH", "/opt/scripts/NGC.csv")
SEED_BATCH_SIZE = 500
MAX_MATCHED_LEN = 512
MAX_OBJ_RADIUS_DEG = 3.0  # pre-filter margin for giant objects


def _ra_to_deg(ra_str):
    """Convert ``HH:MM:SS.ss`` to degrees (hours * 15). Returns None if blank."""
    if not ra_str or not ra_str.strip():
        return None
    try:
        h, m, s = (float(p) for p in ra_str.strip().split(":"))
        return (h + m / 60.0 + s / 3600.0) * 15.0
    except (ValueError, TypeError):
        return None


def _dec_to_deg(dec_str):
    """Convert ``±DD:MM:SS.s`` to degrees (sign preserved). None if blank."""
    if not dec_str or not dec_str.strip():
        return None
    s = dec_str.strip()
    sign = -1.0 if s.startswith("-") else 1.0
    if s[0:1] in "+-":
        s = s[1:]
    try:
        d, m, sec = (float(p) for p in s.split(":"))
        val = d + m / 60.0 + sec / 3600.0
        return sign * val
    except (ValueError, TypeError):
        return None


def sexagesimal_to_degrees(ra_str, dec_str):
    """Public helper used by tests. Returns (ra_deg, dec_deg) or (None, None)."""
    return _ra_to_deg(ra_str), _dec_to_deg(dec_str)


def _normalize_messier(m_value):
    """``'031'`` -> ``'M31'``; blank/invalid -> None."""
    if not m_value or not str(m_value).strip():
        return None
    try:
        return "M" + str(int(float(str(m_value).strip())))
    except (ValueError, TypeError):
        return None


def seed_catalog(cursor, csv_path=NGC_CSV_PATH):
    """Load NGC.csv into ``catalog_objects`` if the table is empty.

    Returns the number of rows inserted (0 if already seeded).
    """
    cursor.execute("SELECT COUNT(*) FROM catalog_objects")
    if cursor.fetchone()[0] > 0:
        logger.info("catalog_objects already seeded; skipping.")
        return 0

    if not os.path.isfile(csv_path):
        logger.error(f"OpenNGC CSV not found at {csv_path}; cannot seed catalog.")
        return 0

    rows = []
    with open(csv_path, newline="", encoding="utf-8", errors="ignore") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        for rec in reader:
            name = (rec.get("Name") or "").strip()
            if not name:
                continue
            ra = _ra_to_deg(rec.get("RA"))
            dec = _dec_to_deg(rec.get("Dec"))
            if ra is None or dec is None:
                continue  # skip rows without usable coords (e.g. NonEx placeholders)
            maj_str = (rec.get("MajAx") or "").strip()
            try:
                maj_axis = float(maj_str) if maj_str else None
            except ValueError:
                maj_axis = None
            common = (rec.get("Common names") or "").strip() or None
            if common:
                common = common[:255]
            rows.append((
                name[:32],
                common,
                _normalize_messier(rec.get("M")),
                (rec.get("Type") or "").strip()[:16] or None,
                ra,
                dec,
                maj_axis,
            ))

    insert_sql = (
        "INSERT INTO catalog_objects "
        "(id, common_name, messier, obj_type, ra, `dec`, maj_axis_arcmin) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)"
    )
    for i in range(0, len(rows), SEED_BATCH_SIZE):
        cursor.executemany(insert_sql, rows[i:i + SEED_BATCH_SIZE])

    logger.info(f"Seeded catalog_objects with {len(rows)} objects.")
    return len(rows)


def _angular_separation_arcmin(ra1, dec1, ra2, dec2):
    """Great-circle separation between two points (degrees in, arcmin out)."""
    r1 = math.radians(ra1)
    d1 = math.radians(dec1)
    r2 = math.radians(ra2)
    d2 = math.radians(dec2)
    sdr = math.sin((r2 - r1) / 2.0) ** 2
    sdd = math.sin((d2 - d1) / 2.0) ** 2
    a = sdd + math.cos(d1) * math.cos(d2) * sdr
    sep_rad = 2.0 * math.asin(min(1.0, math.sqrt(a)))
    return math.degrees(sep_rad) * 60.0


def match_objects(cursor, ra_deg, dec_deg, width_px, height_px, pixscale_arcsec):
    """Find catalog objects inside the solved footprint.

    Returns ``(matched_objects_csv, primary_object)``; both ``None`` when no
    object is in frame. ``primary_object`` prefers the Messier id of the
    largest object.
    """
    if ra_deg is None or dec_deg is None or pixscale_arcsec is None:
        return (None, None)

    # Footprint half-diagonal in arcmin.
    diag_px = math.sqrt((width_px or 0) ** 2 + (height_px or 0) ** 2)
    half_diag_arcmin = (diag_px / 2.0) * pixscale_arcsec / 60.0

    band_deg = half_diag_arcmin / 60.0 + MAX_OBJ_RADIUS_DEG

    dec_lo = max(-90.0, dec_deg - band_deg)
    dec_hi = min(90.0, dec_deg + band_deg)

    cos_dec = math.cos(math.radians(max(abs(dec_deg), 0.0)))
    cos_dec = max(cos_dec, 0.01)
    ra_half = band_deg / cos_dec

    ra_lo = ra_deg - ra_half
    ra_hi = ra_deg + ra_half

    where, params = _ra_clause(ra_lo, ra_hi)
    sql = (
        "SELECT id, messier, ra, `dec`, maj_axis_arcmin FROM catalog_objects "
        f"WHERE `dec` BETWEEN %s AND %s AND ({where})"
    )
    cursor.execute(sql, (dec_lo, dec_hi, *params))

    matches = []
    for obj_id, messier, obj_ra, obj_dec, maj_axis in cursor.fetchall():
        sep = _angular_separation_arcmin(ra_deg, dec_deg, obj_ra, obj_dec)
        radius = (maj_axis or 0.0) / 2.0
        if sep <= half_diag_arcmin + radius:
            matches.append({
                "id": obj_id,
                "messier": messier,
                "maj_axis": maj_axis,
            })

    if not matches:
        return (None, None)

    # Largest object first; nulls last.
    matches.sort(key=lambda m: (m["maj_axis"] is None, -(m["maj_axis"] or 0.0)))

    return _format_matches(matches)


def _ra_clause(ra_lo, ra_hi):
    """Build an RA BETWEEN clause that wraps around 0/360. Returns (sql, params)."""
    if ra_lo >= 0 and ra_hi <= 360:
        return ("ra BETWEEN %s AND %s", (ra_lo, ra_hi))
    if ra_lo < 0:
        return ("(ra BETWEEN %s AND 360 OR ra BETWEEN 0 AND %s)",
                (ra_lo + 360, ra_hi))
    # ra_hi > 360
    return ("(ra BETWEEN %s AND 360 OR ra BETWEEN 0 AND %s)",
            (ra_lo, ra_hi - 360))


def _format_matches(matches):
    """Build matched_objects CSV (<=512 chars, no truncated IDs) + primary."""
    ids = [m["id"] for m in matches]
    csv_out = ""
    for obj_id in ids:
        candidate = obj_id if not csv_out else csv_out + "," + obj_id
        if len(candidate) > MAX_MATCHED_LEN:
            break
        csv_out = candidate

    top = matches[0]
    primary = top["messier"] if top["messier"] else top["id"]
    return (csv_out, primary)
