#!/usr/bin/env python3
"""
generate_dashboard.py — Updates the DATA blob in dashboard.html from teams_data.json.

For LOCAL USE only — the scheduled monitor no longer uses this script.
The live dashboard artifact now fetches teams_data.json directly from GitHub.

Run manually after any local update to teams_data.json:
    python3 "/Users/nic/Desktop/Claude CoWork/Projects/Hockey Sale Tracker/generate_dashboard.py"

Prints one of:
    "changed: <reason>"  — meaningful update, call update_artifact
    "unchanged"          — no status or news changes, skip update_artifact
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

BASE = Path("/Users/nic/Desktop/Claude CoWork/Projects/Hockey Sale Tracker")
TEAMS_DATA = BASE / "teams_data.json"
DASHBOARD  = BASE / "dashboard.html"

MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def compute_status(window):
    if not window:
        return "active"
    start_s = window.get("start", "")
    end_s   = window.get("end", "")
    if not start_s or not end_s:
        return "active"
    today = date.today()
    year  = today.year
    try:
        sm, sd = map(int, start_s.split("-"))
        em, ed = map(int, end_s.split("-"))
        start = date(year, sm, sd)
        end   = date(year, em, ed)
        if end < start:                         # window spans year boundary
            end = date(year + 1, em, ed)
    except Exception:
        return "active"

    if today > end:
        return "past"
    elif today >= start:
        return "active"
    elif (start - today).days <= 30:
        return "upcoming"
    else:
        return "waiting"


def format_window(window):
    """Returns 'Mon D – Mon D' string, or None if window missing."""
    if not window:
        return None
    start_s = window.get("start", "")
    end_s   = window.get("end", "")
    if not start_s or not end_s:
        return None
    try:
        sm, sd = map(int, start_s.split("-"))
        em, ed = map(int, end_s.split("-"))
        return f"{MONTHS[sm]} {sd} – {MONTHS[em]} {ed}"
    except Exception:
        return None


def build_news(ln):
    """Convert a teams_data latest_news entry into a dashboard news object."""
    if not ln:
        return None
    sources = []
    url    = ln.get("url", "")
    source = ln.get("source", "")
    if source:                                  # only add if source label is non-empty
        sources.append({"label": source, "url": url})
    for s in ln.get("extra_sources", []):       # optional additional sources
        sources.append(s)
    return {
        "label":    ln.get("news_label"),       # e.g. "⚠ Watch Closely — Date Unconfirmed"
        "warn":     ln.get("news_warn", False),
        "html":     ln.get("news_html"),        # if set, used as innerHTML (overrides text)
        "text":     None if ln.get("news_html") else ln.get("summary"),
        "detected": ln.get("detected_display") or ln.get("detected_at", ""),
        "sources":  sources,
    }


def main():
    today     = date.today()
    today_str = today.strftime("%Y-%m-%d")

    # ── load teams_data ───────────────────────────────────────────────────────
    with open(TEAMS_DATA, encoding="utf-8") as f:
        td = json.load(f)
    teams_by_id = {t["id"]: t for t in td["teams"]}

    # ── read current DATA blob from dashboard ─────────────────────────────────
    html = DASHBOARD.read_text(encoding="utf-8")
    m = re.search(r"// BEGIN_DATA\n(.*?)\n// END_DATA", html, re.DOTALL)
    if not m:
        print("ERROR: BEGIN_DATA marker not found in dashboard.html", file=sys.stderr)
        sys.exit(1)

    raw = m.group(1).strip()
    raw = re.sub(r"^const DATA\s*=\s*", "", raw)
    if raw.endswith(";"):
        raw = raw[:-1]
    data = json.loads(raw)

    # ── update each team ──────────────────────────────────────────────────────
    reasons = []

    data["last_updated"] = today_str

    for team in data["teams"]:
        tid     = team["id"]
        td_team = teams_by_id.get(tid)
        if not td_team:
            continue

        # Status
        new_status = compute_status(td_team.get("predicted_window"))
        if team.get("status") != new_status:
            reasons.append(f"{tid}: {team.get('status')} → {new_status}")
            team["status"] = new_status

        # Window display (teams_data may supply an override string directly)
        override = td_team.get("window_display")
        if override:
            team["window_display"] = override
        else:
            wdisplay = format_window(td_team.get("predicted_window"))
            if wdisplay:
                team["window_display"] = wdisplay

        # News — update if detected_at changed
        ln       = td_team.get("latest_news")
        new_news = build_news(ln)
        old_news = team.get("news")
        old_det  = (old_news or {}).get("detected", "")
        new_det  = (new_news or {}).get("detected", "")
        if new_det != old_det or (new_news is None) != (old_news is None):
            reasons.append(f"{tid}: news updated ({old_det} → {new_det})")
            team["news"] = new_news

    # ── write updated DATA back to dashboard ──────────────────────────────────
    new_data_line = "const DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";"
    new_block     = "// BEGIN_DATA\n" + new_data_line + "\n// END_DATA"
    new_html      = re.sub(
        r"// BEGIN_DATA\n.*?\n// END_DATA",
        new_block,
        html,
        flags=re.DOTALL,
    )
    DASHBOARD.write_text(new_html, encoding="utf-8")

    if reasons:
        print("changed: " + "; ".join(reasons))
    else:
        print("unchanged")


if __name__ == "__main__":
    main()
