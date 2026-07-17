FROM python:3.9-slim

# System dependencies:
#  - build-essential: compile Python wheels (astropy, numpy, pyephem, pillow)
#  - wget, unzip, ca-certificates: fetch ASTAP CLI + OpenNGC catalog at build
#
# NOTE: base switched from python:3.9-alpine to python:3.9-slim (Debian) because
# the ASTAP CLI is a glibc binary (built with FreePascal/Lazarus) and does not
# run reliably under Alpine/musl even with gcompat. Debian runs it natively.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        wget \
        unzip \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/scripts

# Create a virtual environment
RUN python -m venv /opt/venv

# Copy the requirements file
COPY docker/python/requirements.txt .

# Install Python packages into the virtual environment
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Copy and install the local XISF library
COPY external/xisf /opt/scripts/external/xisf
RUN /opt/venv/bin/pip install /opt/scripts/external/xisf

# ASTAP CLI plate solver (license MPL 2.0, GPLv3-compatible).
# Star database is NOT bundled; it lives in the astap_db volume (-d /opt/astap_db).
RUN wget -q "https://sourceforge.net/projects/astap-program/files/linux_installer/astap_command-line_version_Linux_amd64.zip/download" -O /tmp/astap_cli.zip \
    && unzip -o /tmp/astap_cli.zip -d /usr/local/bin \
    && chmod +x /usr/local/bin/astap_cli \
    && rm /tmp/astap_cli.zip \
    && /usr/local/bin/astap_cli 2>&1 | head -1

# OpenNGC deep-sky catalog (license CC-BY-SA-4.0), seeded into catalog_objects
# at drain-loop startup. Pinned to release tag v20260501.
RUN wget -q "https://raw.githubusercontent.com/mattiaverga/OpenNGC/v20260501/database_files/NGC.csv" \
        -O /opt/scripts/NGC.csv

# Copy the application scripts
COPY docker/python/reindex.py .
COPY docker/python/solve_pending.py .
COPY docker/python/watch_fs.py .
COPY docker/python/indexer_lib ./indexer_lib/

# Set the PATH to use the virtual environment's python
ENV PATH="/opt/venv/bin:$PATH"

# Startup command: index once, then run the plate-solve drain loop alongside
# the filesystem watcher (the drain loop polls the DB for pending rows, so
# files newly picked up by reindex/watch_fs are solved automatically).
CMD ["sh", "-c", "python reindex.py /var/fits && (python solve_pending.py /var/fits & python watch_fs.py /var/fits)"]
