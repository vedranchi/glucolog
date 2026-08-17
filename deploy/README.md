# Deploying Glucolog to the Oracle VM

Production runs as three containers via Docker Compose — **Caddy** (public, TLS) →
**web** (gunicorn) → **db** (Postgres) — reachable over HTTPS at a DuckDNS domain.
Caddy provisions the Let's Encrypt certificate automatically.

```
Internet ──443──▶ caddy ──proxy──▶ web:8000 (gunicorn/Django) ──▶ db:5432 (postgres)
                    │  serves /static/* and /media/* from shared volumes
```

## Files

| File | Role |
| --- | --- |
| `docker-compose.yml` | base: `db` service |
| `docker-compose.override.yml` | **dev only** (auto-loaded): publishes DB on localhost |
| `docker-compose.prod.yml` | **prod**: adds `web` + `caddy`, hardens `db` |
| `deploy/Caddyfile` | reverse proxy + auto-HTTPS + static/media |
| `deploy/env.example` | template for repo-root `.env` |
| `deploy/email.env.example` | template for repo-root `email.env` |
| `deploy/backup.sh` | verified `pg_dump` + rotation (cron) |
| `deploy/restore.sh` | restore a dump; `--into` for a non-destructive drill |
| `deploy/duckdns.sh` | optional dynamic-DNS updater |

> **Prerequisite:** the prod-security settings in `core/settings.py` must be committed
> and present on the branch you deploy. The VM pulls from git.

---

## One-time VM setup

1. **Instance** — Oracle Ampere A1 (arm64), Ubuntu 22.04/24.04. Note the public IP and
   **reserve it** (Networking → Reserved public IPs) so it survives stop/start.

2. **Open the ports (VCN ingress)** — Networking → your VCN → Security List → add
   ingress rules: TCP **80** and TCP **443** from `0.0.0.0/0` (22 already exists).

3. **Install Docker**
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker "$USER"      # then log out/in
   ```

4. **Fix the instance firewall (the Oracle gotcha)** — Ubuntu images ship a default
   `INPUT ... REJECT` rule that blocks 80/443 even after the ingress rule. Insert ACCEPTs
   above it and persist:
   ```bash
   sudo iptables -I INPUT 6 -p tcp --dport 80  -j ACCEPT
   sudo iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT
   sudo netfilter-persistent save
   ```
   (Check `sudo iptables -L INPUT --line-numbers` — the ACCEPTs must sit above the REJECT.)

5. **DuckDNS** — create the subdomain at duckdns.org and set its IP to the VM's public IP.
   If the IP isn't reserved, install `deploy/duckdns.sh` on a 5-min cron (see the script).

---

## Deploy

```bash
# 6. Get the code
git clone git@github.com:vedranchi/glucolog.git /opt/glucolog
cd /opt/glucolog
git checkout <deploy-branch>

# 7. Secrets (never committed)
cp deploy/env.example .env
python3 -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
#   → paste into SECRET_KEY; set ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS / SITE_DOMAIN to
#     your DuckDNS domain; set matching DB_PASSWORD + DATABASE_URL password.
nano .env

cp deploy/email.env.example email.env
nano email.env               # SMTP host/user + Gmail App Password

# 8. Build & launch (web auto-runs migrate + collectstatic; Caddy fetches the cert)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f caddy   # watch cert issuance

# 9. Create an admin user
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web \
  python manage.py createsuperuser
```

Define a shell alias to save typing:
```bash
alias dcp='docker compose -f docker-compose.yml -f docker-compose.prod.yml'
```

---

## Verify (end-to-end)

- `curl -I https://<domain>/` → `302` to `/users/login/`, valid cert (no TLS warning).
- Open `https://<domain>/users/register/` → styled page (CSS from `/static/`).
- Register → log in → dashboard → log a glucose reading.
- Upload a profile picture → shows from `/media/…`, and survives `dcp restart web`.
- `https://<domain>/admin/` loads and is styled; superuser logs in.
- Trigger a password reset → email arrives (confirms `email.env`).
- Set `NEXT_PUBLIC_APP_URL=https://<domain>` in Vercel + redeploy → landing CTAs reach the app.
- `dcp down && dcp up -d` → DB rows and uploaded media persist (named volumes).
- Run `./deploy/backup.sh`, then restore it with `--into glucolog_drill` and confirm the row
  counts match. An untested backup is not a backup.

## Backups

Health records live on one volume, on one VM. `docker compose down -v` destroys
them irreversibly, and so does losing the instance. Take backups before there is
data worth losing.

```bash
./deploy/backup.sh          # writes backups/glucolog-<UTC stamp>.sql.gz
```

`pg_dump` runs *inside* the db container and reads the `POSTGRES_*` variables
already present there, so no credentials are passed from the host.

The dump is verified before anything is rotated — valid gzip, a completion
marker, and the expected tables present. A dump that fails any check is deleted
and **older backups are kept**, because rotating on the strength of a broken
backup is how backup histories quietly disappear. Retention defaults to 14 days
(`RETENTION_DAYS`).

Schedule it (03:30 daily):

```bash
crontab -e
30 3 * * * cd /opt/glucolog && ./deploy/backup.sh >> /var/log/glucolog-backup.log 2>&1
```

### Restore

**Drill — non-destructive.** Restores into a scratch database and prints row
counts. This is how you find out whether a backup is real:

```bash
./deploy/restore.sh backups/glucolog-<stamp>.sql.gz --into glucolog_drill
```

**Real restore — destructive.** Drops and replaces the live database, and
requires typing the database name to confirm:

```bash
./deploy/restore.sh backups/glucolog-<stamp>.sql.gz
```

> A backup that has never been restored is not a backup. Run the drill after the
> first deploy, and again whenever Postgres is upgraded.

### Gaps to close

- **Backups sit on the same VM as the database.** They protect against a bad
  migration, an accidental `DROP`, or corruption — **not** against losing the
  instance. Copy them off (`scp`, `rclone`) for that.
- Dumps contain health data. `backups/` is gitignored and excluded from the
  image; keep it that way, and treat any copy as PHI.
- Nothing alerts on a failed backup. Until something does, check the log.

## Update / redeploy

```bash
cd /opt/glucolog && git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Troubleshooting

- **Cert won't issue** → 80/443 not reachable: re-check VCN ingress **and** the instance
  iptables (step 4); confirm DuckDNS resolves to the VM IP (`dig +short <domain>`).
- **`DisallowedHost` / CSRF 403** → `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` in `.env`
  must include the exact domain (CSRF with `https://` scheme).
- **Static 404 / unstyled admin** → check `web` logs for the collectstatic step and that
  the `static_data` volume mounted.
- **Password reset email never arrives** → check `email.env`. Email settings now have safe
  defaults, so a missing value degrades to "mail does not send" rather than blocking boot.
  For Gmail, `EMAIL_HOST_PASSWORD` must be an App Password, not the account password.
