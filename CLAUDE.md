# Hockey Sale Tracker — Project Instructions

## What This Project Is

A personal tracker for annual hockey equipment sales in the Detroit/Windsor metro area. Nic uses this to monitor when local NHL, AHL, and ECHL teams hold their end-of-season gear sales so he can plan to attend.

## Files in This Project

- **`teams_data.json`** — The source of truth. Contains team info, historical sale dates, predicted windows, watch URLs, and search queries for each team.
- **`index.html`** — The live dashboard served by GitHub Pages at nicmuffins.github.io/hockey-sale-tracker/. THIS is the file to edit for any dashboard changes — not `dashboard.html`.
- **`monitor.py`** — The GitHub Actions monitor script that runs daily searches and updates `teams_data.json`.
- **`monitor_state.json`** — Tracks team search windows and run state for the monitor.

## Working Rules

- **Data accuracy is the top priority.** Before updating any team's sale dates, predicted windows, or notes in `teams_data.json`, verify the information is correct. If something is uncertain, flag it rather than guessing.
- **Don't break the dashboard.** If editing `index.html`, check that it still renders correctly before saving. The HTML file depends on the structure of `teams_data.json` — don't change the JSON schema without also updating the dashboard.
- **Always commit changes to GitHub directly.** After making any changes to project files, commit them to the GitHub repo (NicMuffins/hockey-sale-tracker) immediately using the Claude in Chrome JavaScript tool and the GitHub Contents API. Never ask Nic to commit or push — do it automatically. The sandbox cannot reach GitHub directly; use `mcp__Claude_in_Chrome__javascript_tool` with an authenticated fetch() call instead.
- **GitHub Pages serves `index.html`.** The live dashboard URL (nicmuffins.github.io/hockey-sale-tracker/) serves `index.html`, not `dashboard.html`. Always verify which file is actually being served before editing.
- **Ask before restructuring.** If a change would affect multiple files, rename/remove files, or significantly alter how the data is organized, confirm with Nic first.
- **Keep it simple.** Only add features or fields that Nic has asked for. Don't expand scope on your own.

## Context

- This is for personal use only — no sharing or handoff needed.
- Teams covered include NHL (Red Wings), ECHL (Toledo Walleye), OHL (Windsor Spitfires), and others in the metro region.
- Sale dates are seasonal — most activity happens May through July after seasons end.


## Sale Verification Workflow (added 2026-07-06)

Each team in `teams_data.json` has a `last_confirmed_sale` field (year, date, notes, verified_at, source). This is the ONLY thing the dashboard displays as a settled "last sale" date — it is seeded from `historical_sales` but is never auto-updated by the monitor.

The GitHub Actions monitor still writes raw finds to `latest_news` with `is_announcement: true`, but the monitor's guess is frequently wrong (wrong team, stale listing, unrelated product page, etc.). The dashboard (`index.html`) deliberately does NOT treat `is_announcement: true` as confirmed — it renders those as an amber "🔍 Possible Sale — Needs Your OK" box. Only a `latest_news.verified: true` flag renders the green "✅ Verified Sale" style.

**When Nic confirms a find in chat** (e.g. "yes, that Toledo sale is real, it was July 12"):
1. Update that team's `last_confirmed_sale` with the confirmed year/date/notes and set `verified_at` to today's date.
2. Set `latest_news.verified = true` on that team so the dashboard shows it as verified.
3. Commit both changes to GitHub (per the rule above — never ask Nic to do this).

Never set `last_confirmed_sale` or `latest_news.verified` from monitor output alone — Nic decides what counts as confirmed.
