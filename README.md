# Classroom Desk

> **Disclaimer:** This project is vibe coded with AI assistance. It is experimental; review generated work and verify the app's behavior before relying on it.

A private dashboard that automatically turns newly discovered Google Classroom assignments and attached instructions into reviewable DOCX and PPTX drafts using the Gemini API. Designed for one person.

## What is implemented

- Password-protected, responsive dashboard with search, class/status filters, draft previews and downloads.
- Manually add in-person assignments, include instructions and a due date, and upload handouts or reference files for drafting.
- Read-only Google Classroom + Drive OAuth integration, paginated discovery and selected-class monitoring.
- Automatic persistent queue, one generation at a time, restart recovery and bounded retries with backoff.
- Google Docs/Slides/Sheets export; PDF, DOCX, PPTX, XLSX, TXT and CSV extraction.
- Structured Gemini output, formatted Word/PowerPoint/Excel files, speaker notes, source/review sections, and separate arithmetic evaluation using Decimal. Model-written code is never executed.
- In-app notifications; optional STARTTLS email notifications. Browser notifications while the dashboard is open.
- Encrypted saved Google tokens and Gemini keys, retention, Google token revocation and workspace deletion.
- Multiarchitecture Docker build, persistent data volume, optional Caddy HTTPS, backup script and Oracle deployment instructions.

The app automatically generates drafts; there is no required Generate button. It never submits coursework.

Use **Add assignment** on the dashboard to enter in-person work manually. Choose a connected class, provide instructions or upload source files, and optionally set a due date. Supported uploads are PDF, DOCX, PPTX, XLSX, TXT, CSV and common image formats (20 MB per file, 60 MB combined). Manual assignments enter the same reviewable draft queue. Mark a draft **Completed** after reviewing it to remove it from the Ready for review filter; it remains in All assignments and can be moved back to review. This does not submit work to Classroom.

## First-run behavior

Connect Google, wait for the class list, select classes, add your Gemini key, and save Settings. Upcoming unsubmitted assignments immediately enter the queue. On the initial import, existing overdue/submitted work is listed without automatic generation; initial undated work is limited to the last 30 days by default. New assignments and changed instructions queue automatically thereafter. A retry action can explicitly queue older unsubmitted work.

Paused processing does not start new checks or drafts. An already running request finishes. Deselecting a class prevents its queued assignments from starting. Changes are saved only while the background worker is idle, with a clear message otherwise.

## Quick start with Docker

Install Docker Engine and the Compose plugin. From this directory:

```bash
python3 scripts/setup.py
# Edit .env: Google OAuth client ID/secret. Set BASE_URL to your chosen URL.
docker compose up -d --build
```

Open http://localhost:8000. `scripts/setup.py` asks for a dashboard password; if you leave it blank it creates a private `dashboard-password.txt`. Put it in your password manager and remove that file. Keep `.env` private and keep `APP_SECRET` unchanged: it is required to decrypt saved credentials.

For a cloud VM, start with [the Oracle deployment guide](deploy/ORACLE.md). The app is bound to the VM's loopback address by default; access it through an SSH tunnel or the supplied HTTPS reverse proxy.

## Google setup (required)

1. Create a Google Cloud project; this is separate from the Oracle hosting account. Enable **Google Classroom API** and **Google Drive API**. No Google Cloud VM is required.
2. Configure Google Auth Platform branding and audience as **External** for a personal Google account. In testing mode, add your Google account as a test user.
3. Create an OAuth client of type **Web application**. Add the exact redirect URL shown in the app's Settings, for example `http://localhost:8000/api/google/callback` for local/tunnel use or `https://your-domain/api/google/callback` for public HTTPS.
4. Put the client ID and secret in `.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`, then recreate the container: `docker compose up -d --force-recreate app`.
5. Sign in to the dashboard and click **Connect Google** in Settings. Allow all three read-only permissions.
6. Wait up to one check cycle (about five seconds after connecting), choose monitored classes, and save.

Scopes: `classroom.courses.readonly`, `classroom.coursework.me.readonly`, `drive.readonly`. Drive read-only consent technically grants reading accessible Drive files; this app requests only files referenced by monitored assignments. `drive.file` would not automatically cover existing teacher-owned attachments, which is why it is not used here.

Google external OAuth apps in Testing generally have refresh tokens that expire after seven days for these scopes; reconnect when needed. For unattended use, review Google's publishing/verification requirements for your personal app. Publishing status alone is not a guarantee of permanent authorization. The app reports revoked/expired grants in the dashboard.

References: [Classroom scopes](https://developers.google.com/workspace/classroom/guides/auth), [web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server), [OAuth token expiration](https://developers.google.com/identity/protocols/oauth2/), [Drive export/download](https://developers.google.com/workspace/drive/api/guides/manage-downloads).

## Gemini setup (required)

Create an API key at [Google AI Studio](https://aistudio.google.com/api-keys) for a project with free-tier access, then paste it into authenticated Settings. The saved key is encrypted and is not returned to the browser. The optional `GEMINI_API_KEY` environment variable is an alternative.

The default model is `gemini-3.8-flash`; choose an available model in Settings if its availability changes. The application does not enable billing, choose a fallback model, or purchase quota. It cannot determine or enforce whether Google's project is billed; ensure your chosen project is on the free tier. Check [current pricing](https://ai.google.dev/gemini-api/docs/pricing), [key setup](https://ai.google.dev/gemini-api/docs/api-key), and [account quotas](https://ai.google.dev/gemini-api/docs/rate-limits). Free-tier inputs/outputs may be used to improve Google's products.

For assignments that request name plates and name badges from PDF tables, Classroom Desk reads the printable records and requested measurements, then creates separate sized DOCX files. The files are drafts; check the source data and print at 100% / Actual Size before submitting.

One generation request is made for each queued assignment attempt. No source is silently truncated. Rate limits retry after 1, 2, 4 and 8 hours; temporary network/provider failures use shorter backoff. Five failed attempts move an item to Needs attention. A bad key, unsupported file, or malformed output requires attention and can be retried after fixing the cause. No paid fallback is used.

## Notifications

In-app notifications work without extra services. Browser notifications require permission and an open dashboard; this is not background Web Push.

For email even when the dashboard is closed, configure `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, and `NOTIFY_EMAIL` in `.env`, then recreate the container. Use a mail provider that permits STARTTLS SMTP. Gmail typically needs an app password and account eligibility. Email contains only a generic update and dashboard URL, not assignment contents. Failed delivery stays visible in Settings and retries later.

## Supported work and limits

- Outputs: DOCX, PPTX, and XLSX, chosen from assignment instructions. PPTX includes speaker notes. XLSX workbooks include formatted sheets, source/assumption notes, guarded formulas, and requested charts. Common accounting layouts include budgets, income statements, balance sheets, cash flows, and ratio analysis. Layout and formulas should be reviewed before submission.
- Inputs: Google Docs/Slides/Sheets, PDFs (up to 120 pages), DOCX/PPTX/XLSX, TXT/CSV, and PNG/JPEG/WebP/GIF image attachments. Low-text PDF pages are rendered and sent to Gemini vision; direct image attachments are sent as visual references and added to DOCX/PPTX drafts. Download cap: 20 MB per attachment, 60 MB combined; rendered PDF pages plus direct image inputs are limited to 12 MB combined and text context to 220,000 characters.
- Images embedded inside Office documents or within text-heavy PDF pages are not extracted; attach those separately as supported image files when needed.
- Forms, external links, videos, and unsupported attachment types stop generation with Needs attention rather than pretending their contents were read. No arbitrary URLs are fetched.
- Web research, interactive quizzes, student participation and external activities are not implemented. Missing sources/data or unsupported requested outputs should produce a marked supporting draft with Needs attention.
- Numeric formulas in XLSX files are restricted to a safe function allowlist; macros and network/external workbook formulas are not used. Arithmetic expressions are separately evaluated without executing model code. These checks do not verify financial assumptions, accounting treatment, source accuracy, or the full answer.
- Only published coursework and its attached files are used; separate course stream posts/materials are not automatically incorporated.
- Generated files expire after the configured retention period (90 days by default). Assignment instructions/metadata remain until workspace deletion. Backups must be managed separately.

## Local development without Docker

Python 3.12 and Node.js 24 are recommended. On Ubuntu install `python3-venv` if needed.

```bash
python3 scripts/setup.py
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm install
npm run build
cd ..
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Use one backend worker; the scheduler lives inside that process. Never run multiple containers against the same database. To use Vite development mode, set `BASE_URL=http://localhost:5173`, use that OAuth redirect URL, run the backend as above, and run `npm run dev` in `frontend/`. Vite proxies API requests to port 8000. Restart the backend when changing environment settings.

For a sample dashboard with downloadable demo files, set `DEMO_MODE=true` and use a separate `DATA_DIR` such as `./data-demo`, then restart. Demo mode never calls Google, Gemini or SMTP and cannot save settings. Remove the demo data directory or change DATA_DIR back before switching to live mode; demo and real data should not share a database.

## Validation

The included offline integration checks use fake Google/Gemini services, generate real DOCX/PPTX documents, and cover login/CSRF, queue recovery, duplicate discovery, changed instructions and quota backoff:

```bash
.venv/bin/python -m unittest discover -s tests -v
cd frontend && npm run build
```

These checks require installed dependencies. They do not validate live Google authorization, a Gemini quota, email delivery or your Oracle network configuration.

## Backup and restore

After deploying with Docker, run `sh scripts/backup.sh`. It briefly stops the app, makes a consistent SQLite/document snapshot, saves a matching private `.env` copy under `backups/`, and restarts the app. Copy both matching backup files to private storage off the VM; the environment contains secrets. Do not publish or commit backups.

See [Oracle deployment](deploy/ORACLE.md) for restore commands, updates, firewall configuration and removal.

## Open a no-install laptop preview

If package installation is unavailable, run `python3 scripts/preview.py` from this folder. It opens the sample dashboard directly from `local-preview/index.html`; it does not run a network server, access Google/Gemini, or read your account files. If your browser does not open automatically, open the `local-preview/index.html` file from your file manager. Sample Word and PowerPoint files are in `local-preview/downloads/`. For the connected application, use the Docker/local development instructions above once dependencies are available.

## Start the connected app on Linux Mint/Ubuntu

Open a terminal in this folder and run `bash scripts/run-live.sh`. The script checks Python virtual-environment support and npm registry access before it asks you to set up a private login password. It installs dependencies inside this project, builds the dashboard, and runs the app at http://localhost:8000. Press Ctrl+C to stop it. Keep the terminal open while you use the app.

If Python virtual-environment support is missing, run `sudo apt install python3.12-venv` in your terminal, remove only the incomplete `.venv` folder inside this project, then retry. Never paste Google secrets or API keys into chat; add Google OAuth credentials to `.env` and the Gemini key in the authenticated app Settings.
