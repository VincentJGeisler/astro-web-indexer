import os
import textwrap
import tempfile

from indexer_lib.plate_solver import _parse_solve_ini, star_db_present


def _write_ini(text):
    fd, path = tempfile.mkstemp(suffix=".ini")
    with os.fdopen(fd, "w") as fh:
        fh.write(textwrap.dedent(text))
    return path


def test_parse_success_with_rotation():
    ini = _write_ini("""\
        [astap]
        PLTSOLVD=T
        CRVAL1=10.6847083
        CRVAL2=41.2690667
        CDELT1=-0.000277778
        CDELT2=0.000277778
        CROTA2=123.45
    """)
    try:
        out = _parse_solve_ini(ini)
    finally:
        os.remove(ini)
    assert out is not None
    assert abs(out["ra"] - 10.6847083) < 1e-9
    assert abs(out["dec"] - 41.2690667) < 1e-9
    # CDELT2 is deg/px -> arcsec/px = *3600
    assert abs(out["pixscale"] - 1.0) < 1e-6
    assert abs(out["rotation"] - 123.45) < 1e-6


def test_parse_success_without_rotation():
    ini = _write_ini("""\
        PLTSOLVD=T
        CRVAL1=10.68
        CRVAL2=41.27
        CDELT2=0.000138889
    """)
    try:
        out = _parse_solve_ini(ini)
    finally:
        os.remove(ini)
    assert out is not None
    assert out["rotation"] is None
    assert abs(out["pixscale"] - 0.5) < 1e-6


def test_parse_not_solved():
    ini = _write_ini("""\
        PLTSOLVD=F
        CRVAL1=0
        CRVAL2=0
        CDELT2=0
        ERROR=No solution
    """)
    try:
        assert _parse_solve_ini(ini) is None
    finally:
        os.remove(ini)


def test_parse_missing_file():
    assert _parse_solve_ini("/nonexistent/astap_solve.ini") is None


def test_parse_corrupt_values():
    ini = _write_ini("""\
        PLTSOLVD=T
        CRVAL1=not_a_number
        CRVAL2=41.27
        CDELT2=0.0001
    """)
    try:
        assert _parse_solve_ini(ini) is None
    finally:
        os.remove(ini)


def test_parse_ignores_sections_and_comments():
    ini = _write_ini("""\
        ; a comment
        [header]
        PLTSOLVD = True
        CRVAL1 = 10.0
        CRVAL2 = -5.0
        CDELT2 = 0.0002
    """)
    try:
        out = _parse_solve_ini(ini)
    finally:
        os.remove(ini)
    assert out is not None
    assert abs(out["ra"] - 10.0) < 1e-9
    assert abs(out["dec"] + 5.0) < 1e-9


def test_star_db_present_detects_1476(tmp_path):
    # empty dir -> absent
    assert star_db_present(str(tmp_path)) is False
    # a .1476 file -> present
    (tmp_path / "d50_0101.1476").write_text("dummy")
    assert star_db_present(str(tmp_path)) is True


def test_star_db_present_missing_dir():
    assert star_db_present("/no/such/dir") is False
