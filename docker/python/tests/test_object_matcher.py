import os
import math
import types

import pytest

from indexer_lib.object_matcher import (
    sexagesimal_to_degrees,
    _normalize_messier,
    _angular_separation_arcmin,
    _ra_clause,
    _format_matches,
    match_objects,
    seed_catalog,
    NGC_CSV_PATH,
)


def _approx(a, b, tol=1e-3):
    return abs(a - b) < tol


# ---------------------------------------------------------------------------
# Sexagesimal conversion
# ---------------------------------------------------------------------------

def test_m31_sexagesimal():
    # M31: RA 00:42:44.35, Dec +41:16:08.6 -> ~10.6848, 41.2691
    ra, dec = sexagesimal_to_degrees("00:42:44.35", "+41:16:08.6")
    assert _approx(ra, 10.6848)
    assert _approx(dec, 41.2691)


def test_ngc185_sexagesimal():
    ra, dec = sexagesimal_to_degrees("00:38:57.97", "+48:20:14.6")
    assert _approx(ra, 9.74166)
    assert _approx(dec, 48.33739)


def test_negative_dec_and_high_ra():
    ra, dec = sexagesimal_to_degrees("23:59:60", "-45:30:00")
    # 23:59:60 == 24h -> 360 deg
    assert _approx(ra, 360.0)
    assert _approx(dec, -45.5)


def test_blank_sexagesimal():
    assert sexagesimal_to_degrees("", "") == (None, None)


# ---------------------------------------------------------------------------
# Messier normalization
# ---------------------------------------------------------------------------

def test_messier_strips_zeros():
    assert _normalize_messier("031") == "M31"
    assert _normalize_messier("110") == "M110"
    assert _normalize_messier("") is None
    assert _normalize_messier(None) is None


# ---------------------------------------------------------------------------
# Angular separation
# ---------------------------------------------------------------------------

def test_separation_zero_and_known():
    assert _approx(_angular_separation_arcmin(10.0, 41.0, 10.0, 41.0), 0.0)
    # 1 degree separation at dec=0 -> 60 arcmin
    sep = _angular_separation_arcmin(0.0, 0.0, 1.0, 0.0)
    assert _approx(sep, 60.0)


# ---------------------------------------------------------------------------
# RA wrap clause
# ---------------------------------------------------------------------------

def test_ra_clause_normal():
    sql, params = _ra_clause(5.0, 15.0)
    assert sql == "ra BETWEEN %s AND %s"
    assert params == (5.0, 15.0)


def test_ra_clause_wrap_below_zero():
    sql, params = _ra_clause(-5.0, 10.0)
    assert "OR" in sql
    assert params == (355.0, 10.0)


def test_ra_clause_wrap_above_360():
    sql, params = _ra_clause(355.0, 370.0)
    assert "OR" in sql
    assert params == (355.0, 10.0)


# ---------------------------------------------------------------------------
# match formatting (512 truncation + primary selection)
# ---------------------------------------------------------------------------

def test_format_primary_prefers_messier():
    matches = [
        {"id": "NGC0224", "messier": "M31", "maj_axis": 177.83},
        {"id": "NGC0221", "messier": "M32", "maj_axis": 7.74},
    ]
    csv_out, primary = _format_matches(matches)
    assert primary == "M31"
    assert csv_out == "NGC0224,NGC0221"


def test_format_truncates_without_cutting_id():
    matches = [{"id": f"NGC{i:04d}", "messier": None, "maj_axis": None} for i in range(200)]
    csv_out, primary = _format_matches(matches)
    assert len(csv_out) <= 512
    # no partial id at the end
    assert not csv_out.endswith(",")


# ---------------------------------------------------------------------------
# match_objects math with a fake cursor
# ---------------------------------------------------------------------------

class _FakeCursor:
    """Returns a canned row set regardless of the SQL/params."""
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        self._last_sql = sql
        self._last_params = params

    def fetchall(self):
        return self._rows


def test_match_m31_field():
    # M31, M32, M110 around (10.68, 41.27); 2-degree diagonal footprint
    rows = [
        # id, messier, ra, dec, maj_axis
        ("NGC0224", "M31", 10.6847, 41.2691, 177.83),
        ("NGC0221", "M32", 10.6743, 40.8651, 7.74),
        ("NGC0205", "M110", 10.0922, 41.6852, 16.22),
    ]
    cur = _FakeCursor(rows)
    csv_out, primary = match_objects(cur, 10.68, 41.27, 4000, 3000, 1.0)
    # primary is M31 (largest); all three present
    assert primary == "M31"
    for nid in ("NGC0224", "NGC0221", "NGC0205"):
        assert nid in csv_out


def test_match_no_hits_returns_none():
    cur = _FakeCursor([])
    assert match_objects(cur, 10.68, 41.27, 4000, 3000, 1.0) == (None, None)


def test_match_pole_adjacent_does_not_crash():
    # dec near +89; ensure dec clamp / cos handling doesn't raise
    rows = []
    cur = _FakeCursor(rows)
    out = match_objects(cur, 0.0, 89.5, 1000, 1000, 1.0)
    assert out == (None, None)


# ---------------------------------------------------------------------------
# seed_catalog against the real bundled NGC.csv (in-container only)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.isfile(NGC_CSV_PATH),
                    reason="NGC.csv not available outside the container")
class TestSeedReal:
    def _connect(self):
        import mysql.connector
        host = os.getenv("DB_HOST", "mariadb")
        return mysql.connector.connect(
            host=host,
            user=os.getenv("DB_USER", "awi_user"),
            password=os.getenv("DB_PASS", os.getenv("DB_PASSWORD", "awi_password")),
            database=os.getenv("DB_NAME", "awi_db"),
        )

    def test_seed_and_m31(self):
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM catalog_objects")
            conn.commit()
            n = seed_catalog(cur, NGC_CSV_PATH)
            conn.commit()
            assert 13000 <= n <= 15000
            # M31 present with messier M31
            cur.execute("SELECT messier FROM catalog_objects WHERE id='NGC0224'")
            assert cur.fetchone()[0] == "M31"
            # re-seed should be a no-op
            assert seed_catalog(cur, NGC_CSV_PATH) == 0
        finally:
            conn.close()
