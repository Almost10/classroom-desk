#!/usr/bin/env python3
"""Open the offline Classroom Desk sample. No packages or internet required."""
from pathlib import Path
import subprocess
import webbrowser

root=Path(__file__).resolve().parents[1]/'local-preview'
url=(root/'index.html').as_uri()
print('Opening the Classroom Desk sample in your browser.',flush=True)
print('Demo only: it uses sample content and does not connect to Google or Gemini.',flush=True)
if webbrowser.open(url,new=2):
    raise SystemExit(0)
try:
    subprocess.Popen(['firefox','--new-tab',url],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
except OSError:
    print('Open this local file in your browser: '+str(root/'index.html'),flush=True)
