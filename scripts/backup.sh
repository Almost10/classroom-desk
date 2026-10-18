#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
umask 077
mkdir -p backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
# Stop the one worker so database and document files are captured together.
docker compose stop app
trap 'docker compose start app >/dev/null' EXIT
# The one-off container uses the same persistent volume and the existing image.
docker compose run --rm --no-deps -T app python scripts/backup.py --output /app/data/workspace-backup.tar.gz
docker compose cp app:/app/data/workspace-backup.tar.gz "backups/workspace-$stamp.tar.gz"
docker compose run --rm --no-deps -T app python -c "from pathlib import Path; Path('/app/data/workspace-backup.tar.gz').unlink()"
cp .env "backups/environment-$stamp.env"
chmod 600 "backups/workspace-$stamp.tar.gz" "backups/environment-$stamp.env"
printf 'Backup saved under backups/. Copy both matching files to private storage away from the VM.\n'
