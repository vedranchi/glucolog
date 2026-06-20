# Project Knowledge: Glucolog

* **Tech Stack:** Python, Django 5.2, PostgreSQL, WhiteNoise, Anymail/SendGrid (email),
  Docker. Crispy Forms + Bootstrap 5 for forms. DRF + SimpleJWT are wired but not yet used.
* **Goal:** A modern, user-friendly web app for diabetes management — glucose and insulin
  tracking plus rough meal/macro tracking.
* **Project aims:** learning vehicle, a genuinely deployable app (planned Oracle Always
  Free ARM host), and a portfolio piece. Favor correctness and clear, readable code.
* **Virtualenv:** use `./env/bin/python` (e.g. `./env/bin/python manage.py check`).

## 1. Apps (where things live)
* `users` — custom email-login `User`, `UserPreferences` (mmol vs mg/dL), `HealthProfile`
  (diabetes type), auth, profile editing, password reset. Form logic sits in `services.py`.
* `logs` — the core: `GlucoseLog`, `InsulinLog`, `MealLog`, plus their log/add/edit/delete views.
* `dashboard` — post-login summary screen + glucose chart. Hosts the signup signal.
* `main` — public landing page.
* `core` — settings/urls/wsgi.

## 2. Domain invariants — do not break these
* **Glucose is stored internally in mmol/L.** Convert to/from mg/dL only at the edges,
  driven by the user's `UserPreferences.glucose_unit`. Never persist mg/dL.
* **Soft deletes.** `GlucoseLog`/`InsulinLog`/`MealLog` use `is_deleted` + `deleted_at`.
  Every read query MUST filter `is_deleted=False`. Never hard-delete medical records.
* **Per-user scoping.** Always filter records by `user=request.user`; use
  `get_object_or_404(Model, pk=pk, user=request.user)` so users can't touch others' data.
* **Profiles exist for every user.** The `post_save` signal in `dashboard/signals.py`
  creates `UserPreferences` and `HealthProfile`; service helpers use `get_or_create` as a
  safety net for legacy accounts. Keep both layers consistent.

## 3. Coding style
* Follow Django best practices and PEP 8. Match the style of the file you're editing.
* Write clean, single-purpose functions; comment the *why*, not the obvious.
* Prefer DB-level aggregation (`annotate`/`aggregate`/`TruncDate`) over looping in Python.
* Validate user input (reject negatives/garbage for units, macros, glucose values).

## 4. Git & workflow — strict
* **ALWAYS `git fetch --all` first.** This local clone drifts far behind `origin`.
  Before claiming anything is broken/missing, diff local against `origin/*`
  (`git log --oneline LOCAL..origin/LOCAL`). `origin/dev` is the true, most up-to-date
  integration branch (ahead of `origin/main`).
* **Branch per change.** Create a `feature/`, `fix/`, or `chore/` branch off the synced
  `dev` before working. Never commit directly to `dev` or `main`.
* **PRs target `dev`**, not `main`. Use the `gh` CLI (`gh pr create --base dev`).
* **No AI attribution.** Do NOT add `Co-Authored-By` trailers or "Generated with Claude
  Code" to commits or PR bodies.
* Commit/push only when asked. Never commit secrets — `.env`, `sendgrid.env`, and
  `.claude/` are gitignored; keep them that way.

## 5. Verify before claiming done
* Run `./env/bin/python manage.py check` after changes (a pre-existing anymail/SendGrid
  deprecation warning is expected and unrelated).
* Where behavior changes, exercise it (run the server / add a test) rather than asserting
  it works. Report failures honestly with output.

## 6. Config & security
* `DEBUG` comes from the environment only (`env("DEBUG")`); never hard-code it. Set
  `DEBUG=False` for the Oracle deployment.
* Production still needs `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `SECURE_*` headers —
  open work, not yet done.

## 7. Teaching mode
* Explain the *why* and trade-offs before/with changes; pace work in phases. This project
  doubles as a learning exercise.
