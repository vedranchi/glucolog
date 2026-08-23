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
#   → set ADMINS, or unhandled 500s are logged and nobody is told.
#   → DJANGO_LOGLEVEL=INFO is a sane start; DEBUG must stay False.
nano .env

cp deploy/email.env.example email.env
nano email.env               # SMTP host/user + Gmail App Password

# 8. Build & launch. `web` waits for Postgres to pass its healthcheck before
#    starting, so the boot-time migrate cannot race the database. First build on
#    a 1-OCPU Ampere is slow — several minutes is normal.
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

- `curl -I https://<domain>/` → `200` and a valid cert (no TLS warning). `/` renders the
  landing page for anonymous visitors; `home()` only redirects once you are logged in.
  `curl -I https://<domain>/dashboard/` is the one that should `302` to `/users/login/`.
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

## Logs and error alerts

Everything logs to stdout, so `docker logs` is the collection point:

```bash
dcp logs -f web            # app + gunicorn access log
dcp logs --tail=200 web    # recent
```

gunicorn runs with `--access-logfile -` and `--error-logfile -`, so requests and
worker errors both appear there. `--timeout 60` replaces the 30s default, which
silently killed slow requests.

`DJANGO_LOGLEVEL` in `.env` sets the level (default `INFO`). `django.db.backends`
is pinned at `INFO` regardless — at `DEBUG` it echoes query parameters, which for
this app means glucose readings in the logs.

**Set `ADMINS` in `.env`** or unhandled 500s are logged and nothing else:

```
ADMINS=Vedran <you@example.com>
```

Mail goes out over the same SMTP as password reset, so it only works once
`email.env` is configured.

> Docker's json log driver is unbounded. Cap it before the free-tier disk fills:
> add `--log-opt max-size=10m --log-opt max-file=3` to the daemon config, or a
> `logging:` block per service in the compose file.

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
- **`web` restarting in a loop** → `dcp ps` shows `db` health. `web` only starts once
  Postgres reports healthy, so a stuck `db` means the database never came up: check
  `dcp logs db` and that `DB_*` in `.env` match `DATABASE_URL`.
- **Static 404 / unstyled admin** → check `web` logs for the collectstatic step and that
  the `static_data` volume mounted. Confirm with
  `curl -I https://<domain>/static/admin/css/base.css` (expect `200`). Note the *stock
  Django admin theme is not your Bootstrap theme* — a plain-looking admin that loads its
  own dark header and sidebar is working correctly, not unstyled.
- **Password reset email never arrives** → don't guess, ask the mail backend directly:
  ```bash
  dcp exec web python manage.py shell -c "
  from django.conf import settings
  from django.core.mail import send_mail
  print(settings.EMAIL_BACKEND, settings.EMAIL_HOST, settings.EMAIL_HOST_USER)
  print('password set:', bool(settings.EMAIL_HOST_PASSWORD))
  send_mail('test', 'body', None, ['you@example.com'])"
  ```
  - `SMTPAuthenticationError (535 ... BadCredentials)` → Gmail is rejecting the password.
    It must be an **App Password** (16 chars, no spaces, unquoted) from
    `myaccount.google.com/apppasswords`, which requires 2FA on the account. Gmail has
    refused plain account passwords for SMTP since 2022, and always fails with this exact
    error. `password set: True` only means non-empty, not valid.
  - Sends fine from the shell but the reset form still mails nothing → Django's
    `PasswordResetForm` shows the same confirmation whether or not the address matches a
    real account (deliberate, prevents account enumeration). Check the address is exactly
    the one on the account.
  - **After editing `email.env`, recreate the container** — `env_file` is read at container
    creation, so `dcp restart web` will *not* pick up the change:
    `dcp up -d --force-recreate web`.
- **`WARN[0000] The "..." variable is not set` on every compose command** → a value in
  `.env` contains a literal `$`, which Compose reads as interpolation and replaces with an
  empty string. The app then runs with a *different* value than the file shows — silently.
  Escape each literal `$` as `$$`. Most likely to bite a generated `SECRET_KEY`.
