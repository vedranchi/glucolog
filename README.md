# Glucolog

A web app for people managing diabetes day-to-day — glucose readings, insulin doses, and
rough meal/macro tracking in one place, with a dashboard that turns raw logs into a picture
of the day.

**Live:** [glucolog.duckdns.org](https://glucolog.duckdns.org)
&nbsp;·&nbsp;
[![CI](https://github.com/vedranchi/glucolog/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/vedranchi/glucolog/actions/workflows/ci.yml)

![Glucolog landing page](docs/screenshots/landing.png)

---

## The app

The dashboard is the first thing you see after logging in: today's totals, recent activity,
and a glucose trend you can page through day by day.

![Dashboard](docs/screenshots/dashboard.png)

Every screen ships in both themes, driven by one shared token layer rather than two
hand-maintained stylesheets.

| Insulin — dark | Meals — light |
|---|---|
| ![Insulin tracking](docs/screenshots/insulin.png) | ![Meal tracking](docs/screenshots/meals.png) |

Logging is deliberately boring: short forms, explicit units, no hidden defaults.

![Add a glucose reading](docs/screenshots/glucose-form.png)

The same templates collapse to a phone without a separate mobile codebase — the layout
stacks to a single column and the nav folds into a full-screen drawer.

| Phone layout | Nav drawer open |
|---|---|
| <img src="docs/screenshots/mobile.jpg" alt="Glucolog on a phone" width="280"> | <img src="docs/screenshots/mobile-nav.jpg" alt="Mobile nav drawer" width="280"> |

## Why this exists

Most CRUD portfolio projects stop at "users can create/read/update/delete a record."
Glucolog is built around the constraints that make a *health* app different from a todo
app: values have a canonical unit that must never drift, records can never be truly
deleted, every query has to be scoped to the right person, and nothing that touches a
diagnosis belongs in a log line. Those rules are documented and enforced consistently
across the codebase rather than bolted on per-view — see [Engineering notes](#engineering-notes)
below.

It's also a real deployment, not a `localhost` demo: it runs in production on an Oracle
Cloud free-tier VM behind Caddy with a Let's Encrypt certificate, deploys automatically
on merge, and backs up its own database off-site.

## Features

- **Email-based auth** — signup, login, password reset, no username field.
- **Glucose, insulin, and meal logging** — add/edit/delete with per-user history.
- **Dashboard** — daily/weekly summaries and a glucose trend chart.
- **Unit preference** — mmol/L or mg/dL display, per user, without touching stored data.
- **Soft deletes** — logs are archived, never destroyed, so history is always recoverable.
- **Responsive UI** — shared light/dark theme, full-screen mobile nav.

## Engineering notes

A few decisions worth pointing out to anyone skimming the code:

- **Canonical units.** Glucose is always stored in mmol/L. Conversion to/from mg/dL
  happens only at the display/input edge, driven by a per-user preference — so unit
  choice can never corrupt stored data.
- **Soft deletes, enforced by hand.** `GlucoseLog`, `InsulinLog`, and `MealLog` use an
  `is_deleted` flag instead of hard deletes, and every read path filters it explicitly.
  Medical history doesn't get destroyed by a misclick.
- **Per-user isolation, tested.** Every query is scoped with `user=request.user` /
  `get_object_or_404(..., user=request.user)`, backed by a dedicated cross-user
  isolation test suite so one account can never read or edit another's data.
- **PHI hygiene.** Glucose values and user identity are kept out of logs, model
  `__str__` output, and anything that would reach a third-party error reporter.
- **Hardened auth endpoints.** Rate limiting on login/signup/password-reset via
  `django-ratelimit`, `SECURE_*` settings driven entirely by environment variables
  (nothing hard-coded per environment).
- **Real backup/restore, not just a cron job.** Verified Postgres backups run on the VM
  and are pushed off-site to Backblaze B2 automatically — with a documented restore
  drill, not just "the job ran and nobody checked."
- **CI parity with production.** GitHub Actions runs the full test suite with
  `DEBUG=False` against a real Postgres service container — the same failure mode
  (WhiteNoise's manifest storage) that a lazy `DEBUG=True` test run would hide.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python, Django 5.2 |
| Database | PostgreSQL 17 |
| Frontend | Server-rendered Django templates, Bootstrap, crispy-forms — no client-side framework |
| Static files | WhiteNoise |
| Email | Env-driven SMTP (Gmail in prod, console backend in dev) |
| Deployment | Docker, gunicorn, Caddy (reverse proxy + automatic TLS) |
| Hosting | Oracle Cloud Always Free VM |
| CI/CD | GitHub Actions → GHCR image → systemd timer pulls on the VM |
| Backups | Nightly Postgres dumps, verified and synced off-site to Backblaze B2 |

## Architecture

| App | Responsibility |
|---|---|
| `users` | Custom email-login `User`, `UserPreferences` (unit system), `HealthProfile`, auth, profile editing |
| `logs` | Core domain: `GlucoseLog`, `InsulinLog`, `MealLog` and their CRUD views |
| `dashboard` | Post-login summary screen and glucose chart |
| `main` | Shared base template, home routing, no-cache middleware |
| `landing` | Public marketing page for anonymous visitors |
| `core` | Settings, URLs, WSGI |

## Running locally

Requires Python 3.13+ and Docker.

```bash
# 1. Config — SECRET_KEY and DATABASE_URL fail fast with no fallback,
#    so this step is not optional.
cp .env.example .env
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
# paste the result into SECRET_KEY

# 2. Dependencies
python -m venv env
./env/bin/pip install -r requirements.txt

# 3. Postgres (required — the dev server and the tests both need it)
docker compose up -d db

# 4. Django
./env/bin/python manage.py migrate
./env/bin/python manage.py runserver
```

### Demo data

Clicking in a fortnight of readings by hand is no way to see the dashboard work, so
there's a seeder that backdates two weeks of plausible glucose/insulin/meal history —
including a partial day for today, so the "Today" cards aren't empty:

```bash
./env/bin/python manage.py seed_demo_data --reset
```

Logs in as `demo@glucolog.app` / `Demo1234!`. It refuses to run unless `DEBUG=True`, so it
can't be pointed at production by accident.

## Testing

```bash
docker compose up -d db
./env/bin/python manage.py test
```

CI runs the same suite with `DEBUG=False` on every push and pull request against `dev`.
To reproduce that locally, run `collectstatic` first — with `DEBUG=False` WhiteNoise's
manifest storage raises `Missing staticfiles manifest entry` for every `{% static %}` tag
until it has.

## Deployment

Merging to `dev` ships automatically: GitHub Actions tests the change, builds the image,
and pushes it to GHCR; a systemd timer on the VM pulls and restarts only when the image
digest has changed. See [`deploy/README.md`](deploy/README.md) for the full VM runbook.

## Status / known limitations

This is an active learning project as well as a working app, so a few things are
open by design rather than overlooked:

- HSTS is currently set to 7 days while HTTPS stability is proven out; it will move to
  a 1-year max-age once that's confirmed.
- Backups are pulled off-site, but full disaster-recovery drills are ongoing.
- Some legacy Bootstrap 4/5 class mismatches remain from an earlier theme pass.

## License

[MIT](LICENSE) © Vedran Chichov

Glucolog is a personal project for tracking your own readings. It is not a medical device,
it gives no clinical advice, and nothing it displays should be used to make treatment
decisions — talk to your care team instead.
