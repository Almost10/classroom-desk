#!/usr/bin/env python3
"""Create a consistent app backup while the worker is paused. Run inside the app container."""
import argparse
import sqlite3
import tarfile
import tempfile
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--data',type=Path,default=Path('/app/data'))
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
# Copying files and DB together requires the app to be stopped; use OCI.md's volume backup method.
with tempfile.TemporaryDirectory() as temp:
    snapshot=Path(temp)/'desk.sqlite3'
    with sqlite3.connect(args.data/'desk.sqlite3') as source,sqlite3.connect(snapshot) as target: source.backup(target)
    with tarfile.open(args.output,'w:gz') as archive:
        archive.add(snapshot,arcname='desk.sqlite3')
        if (args.data/'files').exists(): archive.add(args.data/'files',arcname='files')
print('Backup created. Keep the matching APP_SECRET from .env separately.')
