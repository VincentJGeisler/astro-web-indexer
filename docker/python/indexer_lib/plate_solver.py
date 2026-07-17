import os
import subprocess
import tempfile
import shutil
import logging

from astropy.io import fits
import numpy as np

logger = logging.getLogger('reindex.plate_solver')

ASTAP_BIN = os.getenv("ASTAP_BIN", "astap_cli")
DEFAULT_DB_DIR = os.getenv("ASTAP_DB_DIR", "/opt/astap_db")


def star_db_present(db_dir=DEFAULT_DB_DIR):
    """Return True if the ASTAP star database (D50 etc.) is populated.

    ASTAP star DB files have a ``.1476`` extension and simply sit in the -d
    directory. An empty/missing volume means solving is impossible and the
    caller should mark frames ``no_star_db`` instead of attempting solves.
    """
    if not db_dir or not os.path.isdir(db_dir):
        return False
    try:
        for name in os.listdir(db_dir):
            if name.lower().endswith(".1476"):
                return True
    except OSError as e:
        logger.warning(f"Could not inspect star DB dir {db_dir}: {e}")
    return False


def _parse_solve_ini(ini_path):
    """Parse an ASTAP solution .ini file.

    Returns ``{'ra', 'dec', 'rotation', 'pixscale'}`` on a successful solve,
    or ``None`` if the file is missing, not solved, or unparseable. Lines are
    ``KEY=VALUE``; section headers (``[...]``) are ignored. Keys are matched
    case-insensitively. ``rotation`` is None when CROTA2 is absent.
    """
    if not ini_path or not os.path.isfile(ini_path):
        return None

    values = {}
    try:
        with open(ini_path, "r", errors="ignore") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("[") or line.startswith(";"):
                    continue
                if "=" not in line:
                    continue
                key, _, val = line.partition("=")
                values[key.strip().upper()] = val.strip()
    except OSError as e:
        logger.warning(f"Could not read ASTAP ini {ini_path}: {e}")
        return None

    solved = values.get("PLTSOLVD", "").strip().upper()
    if not solved.startswith("T"):
        return None

    try:
        ra = float(values["CRVAL1"])
        dec = float(values["CRVAL2"])
        cdelt2 = float(values["CDELT2"])
    except (KeyError, ValueError):
        logger.warning(f"ASTAP ini {ini_path} marked solved but missing CRVAL/CDELT")
        return None

    pixscale = abs(cdelt2) * 3600.0

    rotation = None
    if "CROTA2" in values and values["CROTA2"] != "":
        try:
            rotation = float(values["CROTA2"])
        except ValueError:
            rotation = None

    return {"ra": ra, "dec": dec, "rotation": rotation, "pixscale": pixscale}


def _xisf_to_fits(xisf_path, out_fits):
    """Convert an XISF image to a minimal 2-D FITS file for ASTAP."""
    from xisf import XISF  # imported lazily so the module loads without xisf
    data = XISF(xisf_path).read_image(0)
    data = np.asarray(data)
    data = np.squeeze(data)
    if data.ndim == 3:
        # colour frame: ASTAP solves on channel 0
        data = data[0]
    if data.ndim != 2:
        raise ValueError(f"Cannot reduce XISF data to 2-D for {xisf_path}: shape {data.shape}")
    hdu = fits.PrimaryHDU(data=data)
    hdu.writeto(out_fits, overwrite=True, output_verify="silentfix")


def _build_command(image_path, db_dir, out_base, fov_h_arcmin, hint_ra_deg, hint_dec_deg):
    """Construct the ASTAP CLI argv. Returns a list."""
    cmd = [
        ASTAP_BIN,
        "-f", str(image_path),
        "-d", str(db_dir),
        "-o", str(out_base),
        "-wcs", "-log",
        "-z", "2",
    ]
    if fov_h_arcmin and fov_h_arcmin > 0:
        cmd += ["-fov", f"{float(fov_h_arcmin) / 60.0:.6f}"]
    if hint_ra_deg is not None and hint_dec_deg is not None:
        # ASTAP takes RA in HOURS and South Pole Distance = dec + 90.
        cmd += [
            "-ra", f"{float(hint_ra_deg) / 15.0:.6f}",
            "-spd", f"{float(hint_dec_deg) + 90.0:.6f}",
            "-r", "10",
        ]
    else:
        # blind solve
        cmd += ["-r", "180"]
    return cmd


def solve(image_path, hint_ra_deg=None, hint_dec_deg=None, fov_h_arcmin=None,
          timeout_s=60, db_dir=DEFAULT_DB_DIR, work_dir="/tmp/astap"):
    """Plate-solve a single FITS/XISF image with ASTAP.

    Returns ``{'ra', 'dec', 'rotation', 'pixscale'}`` on success or ``None``
    on failure/timeout. ALL ASTAP output is written into a temp dir under
    ``work_dir`` (never next to the read-only data file) and removed afterwards.
    """
    if not image_path or not os.path.isfile(image_path):
        logger.warning(f"solve: image not found: {image_path}")
        return None

    os.makedirs(work_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="astap_", dir=work_dir)
    out_base = os.path.join(tmp, "solve")
    solve_target = image_path
    converted_fits = None

    try:
        ext = os.path.splitext(image_path)[1].lower()

        # For XISF, try the file directly first (recent ASTAP reads XISF).
        # The direct attempt is just the normal command below; if it fails we
        # convert to FITS and retry.
        cmd = _build_command(solve_target, db_dir, out_base, fov_h_arcmin,
                             hint_ra_deg, hint_dec_deg)

        logger.debug(f"ASTAP direct: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, timeout=timeout_s, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            logger.warning(f"ASTAP timed out after {timeout_s}s on {image_path}")
            return None

        solved = _parse_solve_ini(out_base + ".ini")

        if solved is None and ext == ".xisf":
            # Fallback: convert XISF -> FITS and solve the converted file.
            converted_fits = os.path.join(tmp, "converted.fits")
            try:
                _xisf_to_fits(image_path, converted_fits)
            except Exception as e:
                logger.warning(f"XISF->FITS conversion failed for {image_path}: {e}")
                return None
            solve_target = converted_fits
            cmd = _build_command(solve_target, db_dir, out_base, fov_h_arcmin,
                                 hint_ra_deg, hint_dec_deg)
            logger.debug(f"ASTAP converted XISF: {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, timeout=timeout_s, capture_output=True, text=True)
            except subprocess.TimeoutExpired:
                logger.warning(f"ASTAP timed out after {timeout_s}s on converted {image_path}")
                return None
            solved = _parse_solve_ini(out_base + ".ini")

        if solved is None:
            stderr_tail = ""
            try:
                stderr_tail = (result.stderr or "").strip().splitlines()[-1:] if result.stderr else []
                stderr_tail = stderr_tail[0] if stderr_tail else ""
            except Exception:
                stderr_tail = ""
            logger.info(f"ASTAP did not solve {image_path} (exit={result.returncode}) {stderr_tail}")
            return None

        logger.debug(f"Solved {image_path}: RA={solved['ra']:.5f} Dec={solved['dec']:.5f} "
                     f"pixscale={solved['pixscale']:.3f}\"/px")
        return solved

    finally:
        shutil.rmtree(tmp, ignore_errors=True)
