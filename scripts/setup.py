#!/usr/bin/env python3
"""Generate local secrets without printing or accepting them in command arguments."""
import getpass
import os
import secrets
from pathlib import Path
root=Path(__file__).resolve().parents[1]
path=root/'.env'
if path.exists():
    raise SystemExit('.env already exists; edit it locally to change configuration. It was not overwritten.')
password=getpass.getpass('Choose a dashboard password (12+ characters; leave blank to generate): ')
if not password:
    password=secrets.token_urlsafe(20)
    password_file=root/'dashboard-password.txt'
    fd=os.open(password_file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f: f.write(password+'\n')
    print('Generated password saved to dashboard-password.txt (private file). Move it to your password manager.')
if len(password)<12 or '\n' in password or "'" in password or '${' in password:
    raise SystemExit('Use 12+ characters without single quotes, newlines or ${ variable syntax.')
text=(root/'.env.example').read_text().replace('APP_SECRET=replace-with-generated-secret',f'APP_SECRET={secrets.token_urlsafe(48)}').replace('APP_PASSWORD=replace-with-a-long-password',f"APP_PASSWORD='{password}'")
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f: f.write(text)
print('Created .env with private permissions. Configure Google credentials there; add your Gemini key through the dashboard.')
