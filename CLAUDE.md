# Project Knowledge: Glucolog

* **Goal:** A modern, user-friendly web app for diabetes management — glucose and insulin
  tracking plus rough meal/macro tracking.
* **Project aims:** learning vehicle, a genuinely deployable app (planned Oracle Always
  Free ARM host), and a portfolio piece. Favor correctness and clear, readable code.
* **Tech stack:** Python, Django 5.2, PostgreSQL, WhiteNoise, Anymail/SendGrid (email),
  gunicorn, Docker. Server-rendered templates — no client-side framework, no `fetch`.
* **Virtualenv:** use `./env/bin/python` (e.g. `./env/bin/python manage.py check`).

## 1. Apps (where things live)
* `users` — custom email-login `User`, `UserPreferences` (mmol vs mg/dL), `HealthProfile`
  (diabetes type), auth, profile editing, password reset. Form logic sits in `services.py`.
* `logs` — the core: `GlucoseLog`, `InsulinLog`, `MealLog`, plus their log/add/edit/delete views.
* `dashboard` — post-login summary screen + glucose chart. Hosts the signup signal.
* `main` — shared `base.html`, the `home()` redirect, and `NoCacheMiddleware`.
* `landing` — public marketing page rendered by `home()`. **Legacy:** superseded by a
  separate Next.js site and slated for removal — don't invest here.
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
./env/bin/python manage.py check         # expect only the anymail/SendGrid W003 warning
./env/bin/python manage.py test          # needs the db above, else "Connection refused"
./env/bin/python manage.py runserver
```

> **`manage.py test` should find 17 tests, all passing.** If the count drops, suspect test
> discovery before assuming tests were deleted — every app needs an `__init__.py`, and
> `logs/` silently lost its own once, which hid the whole core-domain suite from a green run.

## 4. Current state — perishable, dated 2026-08-14
**All of the previously-stranded work is merged to `dev`.** A fresh clone is now deployable:
`deploy/README.md`'s runbook has every file it references, and the production security
settings are in.

Merged: #25 (SECURE_* from env), #26 (validation/ordering fixes + restored test discovery),
#27 (Oracle deploy stack), #28 (NaN/Infinity rejected in glucose and macro input).

* **To discard:** the ~1,400-line `landing/*` redesign sitting in the working tree — that
  app is being removed anyway.
* **Never deployed.** None of this has run on the VM yet.

**Top open risks, in order:** the live unthrottled JWT endpoints at `/users/api/token/`
(nothing consumes them — delete them); no rate limiting on login/register/password-reset;
no database backups; no `LOGGING`/`ADMINS`, so production 500s are invisible; and the
profile page silently discarding edits. Strip PHI from `GlucoseLog.__str__` before wiring
up any error reporter.

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
* Commit/push only when asked. Never commit secrets — `.env`, `sendgrid.env`, and
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
* **JWT endpoints are live and public** at `/users/api/token/` — but nothing consumes them
  (no serializers or viewsets exist, and `rest_framework` isn't in `INSTALLED_APPS`).
  Treat them as an auth surface, not dormant config.
* **Python 3.14 locally vs 3.13 in Docker** — local runs don't exercise the deployed
  interpreter.
* **Media is served only when `DEBUG`** (`core/urls.py:15-16`); Caddy serves it in prod.
* **`NoCacheMiddleware`** (`main/middleware.py`) forces no-store on every authenticated
  page — relevant when debugging anything cache-related.
* Chart.js is loaded from a CDN **unpinned and without SRI** in `dashboard.html`.

## 10. Teaching mode
* Explain the *why* and trade-offs before/with changes; pace work in phases. This project
  doubles as a learning exercise.
