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
