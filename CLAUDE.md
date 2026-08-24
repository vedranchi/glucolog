# Project Knowledge: Glucolog

* **Goal:** A modern, user-friendly web app for diabetes management — glucose and insulin
  tracking plus rough meal/macro tracking.
* **Project aims:** learning vehicle, a genuinely deployable app (live on an Oracle Always
  Free ARM host), and a portfolio piece. Favor correctness and clear, readable code.
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
./env/bin/python manage.py check         # expect zero issues (the old anymail W003 went away with #30)
./env/bin/python manage.py test          # needs the db above, else "Connection refused"
./env/bin/python manage.py runserver
```

> **`manage.py test` should find 44 tests, all passing** (verified 2026-08-23 on `dev`).
> If the count drops, suspect test discovery before assuming tests were deleted — every app
> needs an `__init__.py`, and `logs/` silently lost its own once, which hid the whole
> core-domain suite from a green run.

## 4. Current state — perishable, dated 2026-08-23
**Live in production** at `https://glucolog.duckdns.org` — first deploy 2026-08-23 on the
Oracle Ampere VM, running `dev`. Caddy holds a valid Let's Encrypt cert, all three
containers are healthy, and the security headers verify on the wire.

Merged to `dev`: #25 (SECURE_* from env), #26 (validation/ordering + test discovery),
#27 (Oracle deploy stack), #28 (NaN/Infinity rejected), #29 (JWT endpoints removed),
#30 (SendGrid → env-driven SMTP), #31 (rate limiting on auth endpoints), #32 (cross-user
isolation tests), #33 (verified backups + restore drill), #34 (PHI stripped from `__str__`,
`LOGGING`/`ADMINS`), #35 (db healthcheck gate, capped logs, pinned deps).

* **Design refresh (PR #37, open against `dev`):** one shared token layer
  (`main/static/main/css/theme.css`) plus a light/dark switch, with the landing, auth,
  dashboard and log screens rebuilt on top of it.
* **`main` is stale** — 46 commits behind `dev` as of this date. Deploy `dev`.

**Deploy gotcha, learned the hard way:** Compose interpolates `$` in `.env`, so a
`SECRET_KEY` containing `$` is silently truncated (you get a `variable is not set` warning
and a different key than the file shows). Escape every literal `$` as `$$`.

**Open items:** the profile page silently discarding edits; HSTS is deliberately at 7 days
(`SECURE_HSTS_SECONDS`) — raise to 31536000 once HTTPS is proven stable, at which point the
already-on `SECURE_HSTS_PRELOAD` becomes meaningful; backups live on the same VM as the
database, so copy them off for real disaster recovery.

**Source of truth for longer context:** `deploy/README.md` (the VM runbook), and `HANDOFF.md`
(project state — **local-only, gitignored, never commit it**).

## 5. Coding style
* Follow Django best practices and PEP 8. Match the style of the file you're editing.
* Write clean, single-purpose functions; comment the *why*, not the obvious.
* Prefer DB-level aggregation (`annotate`/`aggregate`/`TruncDate`) over looping in Python.
  (`dashboard/views.py` still sums in Python — follow the rule, not that example.)
* Validate user input (reject negatives/garbage for units, macros, glucose values). The log
  add/edit views hand-parse `request.POST` with no ModelForms — the root cause of the known
  validation bugs, so take extra care adding fields there.

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
* Run `manage.py check` after changes (the anymail W003 warning is expected and unrelated).
* Where behavior changes, exercise it (run the server / add a test) rather than asserting
  it works. Report failures honestly with output.
* If you couldn't run something, say that — never imply a test passed when it didn't run.

## 8. Config & security
* `DEBUG` comes from the environment only (`env("DEBUG")`); never hard-code it. Set
  `DEBUG=False` for the Oracle deployment.
* `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SECURE_PROXY_SSL_HEADER`, and the `SECURE_*`
  block **already exist** at `core/settings.py:34-68` — env-driven, on-in-prod/off-in-dev.
  **Do not re-implement them.** They are uncommitted (see §4); the remaining work is to
  commit them.
* `SECRET_KEY` and `DATABASE_URL` intentionally fail fast with no fallback. Keep it that way.
* Health data is PHI: keep glucose values and user identity out of logs, `__str__`, and
  anything shipped to a third-party error reporter.

## 9. Known gotchas
* **Bootstrap mismatch:** `CRISPY_TEMPLATE_PACK = "bootstrap5"` but `main/base.html` loads
  Bootstrap **4.6.2**. Crispy emits BS5 classes against BS4 CSS. Don't "fix" one side alone.
* **The public JWT endpoints are GONE** (removed in #29) — don't reintroduce them. The DRF
  packages are still in `requirements.txt` but nothing imports them; drop them in a
  dependency pass.
* **Python 3.14 locally vs 3.13 in Docker** — local runs don't exercise the deployed
  interpreter.
* **Media is served only when `DEBUG`** (`core/urls.py:15-16`); Caddy serves it in prod.
* **`NoCacheMiddleware`** (`main/middleware.py`) forces no-store on every authenticated
  page — relevant when debugging anything cache-related.
* Chart.js is loaded from a CDN **unpinned and without SRI** in `dashboard.html`.

## 10. Teaching mode
* Explain the *why* and trade-offs before/with changes; pace work in phases. This project
  doubles as a learning exercise.
