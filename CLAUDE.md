# Project Knowledge: Glucolog

* **Goal:** A modern, user-friendly web app for diabetes management — glucose and insulin
  tracking plus rough meal/macro tracking.
* **Project aims:** learning vehicle, a genuinely deployable app (live on an Oracle Always
  Free VM), and a portfolio piece. Favor correctness and clear, readable code.
* **Tech stack:** Python, Django 5.2, PostgreSQL, WhiteNoise, env-driven SMTP email
  (Gmail in prod, console backend in dev; anymail still installed for a later Resend swap),
  gunicorn, Docker, Caddy. Server-rendered templates — no client-side framework, no `fetch`.
* **Shape — one deployable, decided 2026-08-24.** Everything ships as a single Django
  app on the Oracle VM: the public landing page, the authenticated product, and the admin,
  all behind one Caddy instance at one domain. An earlier plan to split the marketing page
  into a standalone Next.js site on Vercel was **reversed** — don't reintroduce a separate
  frontend, a second host, or `NEXT_PUBLIC_*` wiring.
* **Virtualenv:** use `./env/bin/python` (e.g. `./env/bin/python manage.py check`).

## 1. Apps (where things live)
* `users` — custom email-login `User`, `UserPreferences` (mmol vs mg/dL), `HealthProfile`
  (diabetes type), auth, profile editing, password reset. Form logic sits in `services.py`.
* `logs` — the core: `GlucoseLog`, `InsulinLog`, `MealLog`, plus their log/add/edit/delete views.
* `dashboard` — post-login summary screen + glucose chart. Hosts the signup signal.
* `main` — shared `base.html`, the `home()` redirect, and `NoCacheMiddleware`.
* `landing` — the public marketing page rendered by `home()` for anonymous visitors.
  **Part of the product**, not a stopgap: Glucolog ships as one Django deployment, so the
  landing page lives here and is styled with the same shared theme tokens as the app.
* `core` — settings/urls/wsgi.

## 2. Domain invariants — do not break these
* **Glucose is stored internally in mmol/L.** Convert to/from mg/dL only at the edges,
  driven by the user's `UserPreferences.glucose_unit`. Never persist mg/dL.
* **Soft deletes.** `GlucoseLog`/`InsulinLog`/`MealLog` use `is_deleted` + `deleted_at`.
  Every read query MUST filter `is_deleted=False`. Never hard-delete medical records.
  There is no soft-delete manager — the filter is applied by hand at every call site.
* **Per-user scoping.** Always filter records by `user=request.user`; use
  `get_object_or_404(Model, pk=pk, user=request.user)` so users can't touch others' data.
* **Profiles exist for every user.** The `post_save` signal in `dashboard/signals.py`
  creates `UserPreferences` and `HealthProfile`; service helpers use `get_or_create` as a
  safety net for legacy accounts. Keep both layers consistent.

## 3. Commands
```bash
docker compose up -d db                  # Postgres on 127.0.0.1:5433 — REQUIRED for tests
./env/bin/python manage.py check         # expect zero issues
./env/bin/python manage.py test          # needs the db above, else "Connection refused"
./env/bin/python manage.py runserver
```

> **`manage.py test` should find 73 tests, all passing** (verified 2026-08-31 on `dev`).
> Treat the number as a floor, not a fact — it goes stale. If the count *drops*, suspect
> test discovery before assuming tests were deleted: every app needs an `__init__.py`, and
> `logs/` silently lost its own once, which hid the whole core-domain suite from a green run.

CI runs that same suite under `DEBUG=False` (`.github/workflows/ci.yml`). To reproduce it
locally, run `collectstatic` **first**: with `DEBUG=False` the WhiteNoise manifest storage
raises `Missing staticfiles manifest entry` for every `{% static %}` tag until it has,
erroring most of the suite. Ordinary local runs pass only because `staticfiles/` is
already populated — a clean checkout is not so lucky.

## 4. Current state — perishable, dated 2026-08-31
**Live in production** at `https://glucolog.duckdns.org` — first deploy 2026-08-23 on the
Oracle VM, running `dev`. Caddy holds a valid Let's Encrypt cert, all three containers are
healthy, and the security headers verify on the wire.

**The VM is `VM.Standard.E2.1.Micro` — x86_64, 2 cores, 956 MiB RAM.** *Not* the Ampere A1
arm64 box this file and `deploy/README.md` both claimed until 2026-08-25. It now carries a
2 GB swapfile; before that it had none, with ~630 MiB of its 956 MiB already resident in
the three containers.

**Deploying is automatic — merging to `dev` ships.** Actions runs the tests, builds the
image, pushes it to `ghcr.io/vedranchi/glucolog:dev`; a systemd timer on the VM
(`deploy/redeploy.sh`, every 3 min) pulls and restarts `web` only when the digest changed.
**Never build the image on the VM.** It takes ~7m40s there and is IO-bound, not
network-bound — `mkdir && chown` on two empty dirs costs 32s while PyPI streams at
12 MB/s. The long silence reads as a hang, and an abandoned build leaves the *old
container running*: exactly how #37's design refresh sat merged-but-undeployed for a day.

The security-audit work (#25–#35) is all merged: `SECURE_*` from env, NaN/Infinity
rejected, JWT endpoints removed, env-driven SMTP, auth rate limiting, cross-user isolation
tests, verified backups, PHI stripped from `__str__`, db healthcheck gate and pinned deps.
Since then: the design refresh (#37, one shared token layer in
`main/static/main/css/theme.css` plus a light/dark switch), CI-built images (#39–#40),
offsite B2 backups (#45), and the v1 correctness pass (#49).

**Releases.** `git push --tags` on a `v*` tag builds and publishes `:1.0.0`, `:1.0` and
`:latest` — and deliberately does *not* move `:dev`, so cutting a release cannot change what
production is running. `core.__version__` and `CHANGELOG.md` are bumped in the same commit
as the tag.

* **`main` tracks the last release**; `dev` is the default branch and the integration
  branch, and is what production deploys. Don't work on `main`.

**Deploy gotcha, learned the hard way:** Compose interpolates `$` in `.env`, so a
`SECRET_KEY` containing `$` is silently truncated (you get a `variable is not set` warning
and a different key than the file shows). Escape every literal `$` as `$$`.

**Open items:** HSTS is at 7 days (`SECURE_HSTS_SECONDS`). Raising it to a year is gated on
moving off `duckdns.org` — preload is the only reason to want a full year, and preloading a
subdomain of a registrable domain you don't own pins HTTPS onto borrowed infrastructure,
with removal measured in browser release trains. A year is also unrecoverable from the
server: withdrawing it needs valid HTTPS serving `max-age=0`, which is exactly what a failed
renewal takes away. Revisit on a custom domain.

Also open, and deferred to v1.1: `TIME_ZONE` is hardcoded to `Europe/Skopje` for every user,
so "today" rolls over at the wrong hour elsewhere; log entries are always stamped "now" with
no way to edit the time, so a missed reading can't be back-filled; soft deletes have no
restore UI, though the landing page copy implies one; and changing your email — the login
credential — is unverified.

**Source of truth for longer context:** `deploy/README.md` (the VM runbook), and `HANDOFF.md`
(project state — **local-only, gitignored, never commit it**).

## 5. Coding style
* Follow Django best practices and PEP 8. Match the style of the file you're editing.
* Write clean, single-purpose functions; comment the *why*, not the obvious.
* Prefer DB-level aggregation (`annotate`/`aggregate`/`TruncDate`) over looping in Python.
* **Never compute a total in a template.** Django's `add` filter coerces through `int()`,
  so it silently truncates decimals and returns `""` for a NULL operand — which
  `|default:"0"` then renders as a real zero. That shipped a wrong insulin total to
  production. Aggregate in the view.
* Validate user input (reject negatives/garbage for units, macros, glucose values). The log
  add/edit views hand-parse `request.POST` with no ModelForms — the root cause of the known
  validation bugs, so take extra care adding fields there. Note `max_length` is a *form*
  constraint: `Model.save()` does not truncate, so free-text fields need an explicit length
  check (`logs.views.logs.clean_text`) or Postgres raises `DataError` as a 500.
* On a validation error, **re-render with the submission**, don't `redirect()` — a redirect
  rebuilds the form from the database and throws away what the user typed.

## 6. Git & workflow — strict
* **Verify against `origin` before claiming anything is broken or missing** — but note
  `git fetch` may fail here with `Permission denied (publickey)`. If it does, say so
  plainly; remote-tracking refs are then stale local copies, so don't present them as live.
* `origin/dev` is the true integration branch (currently ~21 commits ahead of `origin/main`;
  `main` is effectively abandoned).
* **Branch per change.** Create a `feature/`, `fix/`, or `chore/` branch off the synced
  `dev` before working. Never commit directly to `dev` or `main`.
* **PRs target `dev`**, not `main`. Use the `gh` CLI (`gh pr create --base dev`).
* **No AI attribution.** Do NOT add `Co-Authored-By` trailers or "Generated with Claude
  Code" to commits or PR bodies.
* Commit/push only when asked. Never commit secrets — `.env`, `email.env`, and
  `.claude/` are gitignored; keep them that way.

## 7. Verify before claiming done
* Run `manage.py check` after changes (expect zero issues), and
  `manage.py makemigrations --check --dry-run` — CI fails on migration drift.
* Where behavior changes, exercise it (run the server / add a test) rather than asserting
  it works. Report failures honestly with output.
* If you couldn't run something, say that — never imply a test passed when it didn't run.

## 8. Config & security
* `DEBUG` comes from the environment only (`env("DEBUG")`); never hard-code it. Set
  `DEBUG=False` for the Oracle deployment.
* `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SECURE_PROXY_SSL_HEADER`, and the `SECURE_*`
  block **already exist and are committed** at `core/settings.py:34-70` — env-driven,
  on-in-prod/off-in-dev. **Do not re-implement them.**
* The site hostname is env-driven end to end (`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`,
  `SITE_DOMAIN` for Caddy), so moving domains is a VM `.env` change, not a code change.
* `SECRET_KEY` and `DATABASE_URL` intentionally fail fast with no fallback. Keep it that way.
* Health data is PHI: keep glucose values and user identity out of logs, `__str__`, and
  anything shipped to a third-party error reporter.

## 9. Known gotchas
* **crispy-forms and Bootstrap are dead weight, not a conflict.** An earlier note here
  warned that `CRISPY_TEMPLATE_PACK = "bootstrap5"` clashed with the Bootstrap **4.6.2** in
  `main/base.html`. It doesn't: crispy renders *nothing* anywhere — one
  `{% load crispy_forms_tags %}` in `profile.html` with no `|crispy` filter or `{% crispy %}`
  tag, and every field hand-rendered. Bootstrap styles nothing either; every
  Bootstrap-looking class in the templates is a custom class in `base.css`. Both are queued
  for removal in v1.1 — that's a deletion, not a migration.
* **The public JWT endpoints are GONE** (removed in #29) — don't reintroduce them. The DRF
  packages are already out of `requirements.txt`; the only remaining reference is the
  docstring of the regression test that asserts the URLs 404.
* **Python 3.14 locally vs 3.13 in Docker** — local runs don't exercise the deployed
  interpreter.
* **Media is served only when `DEBUG`** (`core/urls.py:15-16`); Caddy serves it in prod.
* **`NoCacheMiddleware`** (`main/middleware.py`) forces no-store on every authenticated
  page — relevant when debugging anything cache-related.
* Chart.js and Bootstrap load from a CDN **version-pinned but without SRI** (`dashboard.html`,
  `landing/index.html`, `main/base.html`) — the missing `integrity=` is the real gap.

## 10. Teaching mode
* Explain the *why* and trade-offs before/with changes; pace work in phases. This project
  doubles as a learning exercise.
