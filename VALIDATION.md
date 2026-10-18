# Implementation handoff

The source includes the application, Docker deployment, Oracle instructions, a sample data mode, and offline integration checks.

## Checks completed in the authoring environment

- Python source compilation for backend, scripts and integration checks.
- Node syntax check for Vite configuration.
- Shell syntax check for the backup script.
- Actual SQLite initialization/settings persistence, encrypted-secret round trip, notification insertion and processing-job recovery, with an isolated configuration and temporary directory.
- Decimal arithmetic examples and rejection of code execution, names, attribute access, invalid division and excessive powers, using the isolated calculation function.

## Checks still required on a machine with package access

The authoring environment has no Docker, no usable pip/venv bootstrap and cannot resolve package registries. npm installation and the frontend build were attempted but could not complete. Consequently these have NOT been run:

- Full frontend TypeScript/Vite build and browser review.
- Included Python integration suite with its actual web/document dependencies.
- Docker image build on ARM64 or AMD64.
- Live Google OAuth, Classroom/Drive retrieval, Gemini generation, SMTP delivery or Oracle deployment.

On the Oracle VM (or a development machine with internet), build first and run the offline checks using the commands in README.md / deploy/ORACLE.md. Then connect Google, select one class and confirm one real assignment all the way through document download. Browser notification permission and layout should also be checked on the intended devices.

Google OAuth client credentials, a Gemini key, and an Oracle VM/SSH setup have not been supplied. No cloud resources were created, no assignments were accessed and no notifications were sent.

The no-install preview's JavaScript syntax and generated Office-package XML/ZIP structure were checked. Full rendering in Firefox/LibreOffice could not be confirmed inside this sandbox: the browser is launched through the desktop controller, but direct Firefox/LibreOffice access cannot run normally here. Open `local-preview/index.html` on your desktop to review it and download the samples.
