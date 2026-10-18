#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

if ! python3 -c 'import ensurepip' >/dev/null 2>&1; then
    printf 'Python virtual environment support is missing. On Linux Mint/Ubuntu run: sudo apt install python3.12-venv\n' >&2
    exit 1
fi
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
    printf 'pip is missing in .venv. Remove this project’s incomplete .venv folder, install python3.12-venv (sudo apt install python3.12-venv), and retry.\n' >&2
    exit 1
fi
if ! npm ping --fetch-timeout=10000 --fetch-retries=0 >/dev/null 2>&1; then
    printf 'npm cannot reach its package registry. Enable internet/package-registry access and retry. No app credentials were changed.\n' >&2
    exit 1
fi
if [ ! -f .env ]; then
    python3 scripts/setup.py
fi
.venv/bin/python -m pip install -r backend/requirements.txt
(cd frontend && npm install --no-audit --no-fund && npm run build)
printf '\nStarting Classroom Desk at http://localhost:8000 (Ctrl+C stops it).\n'
exec .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
