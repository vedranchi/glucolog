# Screenshot checklist

Shots for the README. The README links these paths directly, so replacing a file in
place is the only step needed — no README edit required.

**Use seeded/fake data only.** Never capture a real account's glucose, insulin, or meal
values — this is PHI. Use the seed command rather than hand-clicking entries:

```bash
docker compose up -d db
./env/bin/python manage.py seed_demo_data --reset
```

Logs in as `demo@glucolog.app` / `Demo1234!` (override with `--email`/`--password`). Safe
to re-run — `--reset` clears the demo user's previous logs first. Refuses to run unless
`DEBUG=True`, so it can't accidentally touch the production database.

## Shots

- [x] `landing.png` — public marketing page, logged out, light theme.
- [x] `dashboard.png` — post-login dashboard, dark theme. **Worth re-shooting**, see below.
- [x] `insulin.png` — Track Insulin, dark theme, with the 7-day breakdown table.
- [x] `meals.png` — Track Meals, light theme, with the recent-meals table.
- [x] `glucose-form.png` — Add Glucose Reading with the context dropdown open.
- [x] `mobile.jpg` — landing page at phone width, dark theme, nav closed.
- [x] `mobile-nav.jpg` — the full-screen nav drawer open. Paired with `mobile.jpg` as a
      two-up in the README.

Both phone shots are portrait, so the README sets `width="280"` on each via an `<img>`
tag — a plain `![]()` would render them full-column-width and push the page apart. Keep
their aspect ratios close (currently 536×1000 and 543×1000) or the two-up row looks
lopsided.

## Re-shooting the dashboard

The current `dashboard.png` was taken when the seeder didn't produce any of today's data,
so the "Today" cards read 1 / 1 / 0 and Recent Activity had two stale items. That's fixed
(the seeder now covers today up to the current hour), but the shot itself predates the fix.

Because today is seeded only up to *now*, the dashboard fills out as the day goes on.
**Re-seed and shoot in the evening** (~20:00 local or later) for a full set of today's
cards and a complete glucose curve. Shooting at 10:00 gives you one breakfast reading.

## How to capture

```bash
docker compose up -d db
./env/bin/python manage.py runserver
```

Then, in a browser:
- Desktop shots: ~1440px wide window, no dev-tools chrome visible.
- Mobile shot: browser dev-tools device toolbar, iPhone-width preset.
- PNG, not JPG — the UI has flat colors and text that compress better lossless.
- **Crop out the browser chrome** (address bar, tabs, menu bar). Three earlier shots were
  unusable for this reason — one also exposed personal tab titles and an inbox count.
- Committed copies are downscaled to 1600px wide (`sips -Z 1600 <file>`) to keep the repo
  light; capture at full resolution and resize on the way in.
