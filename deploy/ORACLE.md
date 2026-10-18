# Deploy on Oracle Cloud Always Free

These steps deploy into your existing Oracle account. They do not provision resources automatically or assume any current credits. Check eligibility and your tenancy's available quota in the OCI Console before creating anything.

## 1. VM

Use an Always Free eligible Ubuntu 24.04 image in your tenancy's home region. Prefer `VM.Standard.A1.Flex` with **1 OCPU and 6 GB RAM**, and the default boot volume (typically around 50 GB). This is ample for a single user; AI inference is remote. Docker images support ARM64 and AMD64. The 1 GB micro shape is considerably more constrained, especially during frontend builds.

Oracle currently documents an A1 free allowance equivalent to 2 OCPUs/12 GB across instances and 200 GB combined boot/block storage. Do not rely on older advice claiming 4 OCPUs/24 GB. Check current account limits and the creation screen; other existing resources consume the same allowances. Leave paid extras, paid images, extra block volumes and load balancers off. Default boot volumes have a provider minimum, so they cannot be reduced to the 20 GB app estimate discussed earlier.

Always Free compute can be reclaimed if Oracle considers it idle. Keep backups off the VM; do not create artificial load. Capacity may be unavailable in your region. [Oracle Always Free resource documentation](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).

## 2. Network

Use a public subnet with a public IP, internet gateway and the usual outbound HTTPS access. Allow inbound TCP 22 **from your own public IP** for SSH. For the optional public HTTPS dashboard, also allow TCP 80 and 443 from the internet in an OCI network security group/security list. Do not open 8000 or any database port.

There are two firewalls: OCI network rules and the VM's own firewall. Preserve SSH access when adjusting either. If Ubuntu's UFW is already your active firewall, add SSH from your IP before enabling/changing it, then add 80/443 for public mode. Some Oracle images have preconfigured iptables rules; inspect and adjust only the necessary ingress rules using that firewall's tooling. Do not flush the firewall or blindly switch managers. Docker publishes the app only on 127.0.0.1; the optional Caddy service publishes 80/443.

## 3. Install Docker and upload the app

SSH into the Ubuntu VM with your private key:

```bash
ssh -i /path/to/key ubuntu@YOUR_VM_IP
```

Install Docker Engine and the Compose plugin using [Docker's official Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/). Ubuntu ARM64 is supported. Use `sudo docker ...` until your login has appropriate Docker access. Only add trusted users to the Docker group; it grants host-level privileges.

Copy this project to `~/classroom-desk` on the VM. Transfer source files, not your local node_modules, .venv, .git, or generated files. A prepared source archive can be extracted there. Do not transfer secrets through chat.

```bash
cd ~/classroom-desk
python3 scripts/setup.py
nano .env
```

Set Google client credentials as described in README.md. Do not change APP_SECRET after saving Google/Gemini tokens; it encrypts them.

## 4A. Start privately, without needing a domain

Keep `BASE_URL=http://localhost:8000` and `DEMO_MODE=false` in .env.

On the VM:

```bash
docker compose up -d --build
docker compose ps
```

On your own computer, keep this SSH tunnel open:

```bash
ssh -i /path/to/key -N -L 8000:127.0.0.1:8000 ubuntu@YOUR_VM_IP
```

Open **http://localhost:8000** on that computer. Configure the Google Web OAuth client's redirect as `http://localhost:8000/api/google/callback`. Your browser follows the redirect through the tunnel. The worker continues checking/drafting on the VM when your computer or tunnel is closed. The dashboard is accessible only while you connect through a tunnel. Browser notifications need an open page; configured email works without it. Dashboard links in email open the local URL and therefore require the tunnel.

Do not expose this plain HTTP local configuration directly to the internet.

## 4B. Optional public HTTPS dashboard

Use a hostname you control. Create an A record pointing to the VM's public IPv4. Remove stale AAAA records unless IPv6 is correctly configured. Public access requires 80/443 in both OCI and host firewalls.

Edit .env:

```dotenv
BASE_URL=https://desk.your-domain.example
DOMAIN=desk.your-domain.example
ACME_EMAIL=your-email@example.com
DEMO_MODE=false
```

Set the exact Google OAuth redirect to `https://desk.your-domain.example/api/google/callback`.

```bash
docker compose -f compose.yaml -f deploy/compose.public.yaml up -d --build
docker compose -f compose.yaml -f deploy/compose.public.yaml ps
```

Caddy obtains and renews the HTTPS certificate. Keep its named volumes. The dashboard requires the password set during setup. Do not enable access logs containing Google authorization query parameters. You can keep the SSH tunnel available for administration, but sign in through the BASE_URL configured in .env for normal use.

No paid domain, certificate, mail plan or DNS service is created automatically by this application. Use your existing/free hostname or private tunnel as appropriate.

## 5. Connect and start automation

1. Sign in to the dashboard.
2. Open Settings and connect Google.
3. Wait for classes to appear, then select monitored classes.
4. Enter your free-tier Gemini API key and save.
5. The next worker cycle imports eligible assignments and queues drafts automatically. Processing is sequential.
6. Check a ready draft and its source/review notes. The app never submits it.

Configure optional SMTP in .env and recreate the app container if you want email while the site is closed. No email is sent until configured.

## 6. Operate and back up

```bash
# Status and sanitized operational logs
docker compose ps
docker compose logs --tail 100 app
# Consistent data + matching environment backup
sh scripts/backup.sh
# Check disk usage
df -h
```

Copy backups elsewhere securely, including the matching environment file containing APP_SECRET. Oracle can reclaim free VMs. A backup on the VM alone does not protect against that.

To update after copying reviewed new source, use the same compose command you used to start (include both files for public HTTPS):

```bash
docker compose up -d --build
```

Do not use `--workers` greater than 1 or scale replicas. SQLite and the scheduler are intended for this single-instance application.

To run the included offline checks on the VM using the built image:

```bash
docker compose run --rm --no-deps -T -v "$PWD/tests:/app/tests:ro" app python -m unittest discover -s tests -v
```

The checks use a temporary database and fake providers; they do not access your real Google account or make Gemini/email requests.

## 7. Restore

Use the same application source version as the backup initially. Restore the matching private .env before starting the app; without the matching APP_SECRET its saved credentials cannot be decrypted.

From the project directory, after selecting the backup files:

```bash
docker compose stop app
# Replace .env with the private environment backup locally, then adjust BASE_URL/DOMAIN if needed.
chmod 600 .env
docker compose run --rm --no-deps -T app python -c "from pathlib import Path; import shutil; p=Path('/app/data'); [shutil.rmtree(x) if x.is_dir() else x.unlink() for x in p.iterdir()]"
docker compose run --rm --no-deps -T app python -c "import sys,tarfile; tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz').extractall('/app/data',filter='data')" < backups/YOUR_WORKSPACE_BACKUP.tar.gz
docker compose up -d
```

The clearing command deletes the current workspace data. Restore only your own trusted archive; Python's extraction filter rejects unsafe archive paths. Use the public compose override when recreating a public deployment. Reconnect Google if the restored token has expired or been revoked.

## 8. Stop or remove

`docker compose stop app` pauses the app and worker while preserving files. `docker compose down` removes containers but keeps named data volumes. For public mode, include both compose files to stop Caddy as well.

Before permanently deleting the VM, disconnect Google in the dashboard to revoke its grant, back up anything needed, and remove the app's Google Account access if necessary. Deleting the boot volume/volumes removes stored data. Confirm OCI boot-volume, IP, and other resource usage in the console after termination; only destroy resources belonging to this app.

Set an OCI budget alert if available. Alerts are notifications, not hard spending caps. This project uses no automatic cloud provisioning and creates no paid cloud resources by itself.
