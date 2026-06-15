#!/usr/bin/env python3
"""
monitor.py â Hockey Sale Tracker (GitHub Actions edition)
Runs on GitHub's servers on a daily schedule. No computer required.

Searches all teams whose sale window is active or upcoming.
Only reads/writes teams_data.json when a new find is recorded.
Sends Gmail alerts via SMTP app password.
"""

import base64
import json
import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

# ââ Config ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
REPO       = 'NicMuffins/hockey-sale-tracker'
BRANCH     = 'main'
ALERT_TO   = 'noknic@gmail.com'
GH_API     = 'https://api.github.com'

GITHUB_TOKEN   = os.environ['GITHUB_TOKEN']
TAVILY_KEY     = os.environ['TAVILY_API_KEY']
GMAIL_USER     = os.environ['GMAIL_USER']
GMAIL_PASS     = os.environ['GMAIL_APP_PASSWORD']

GH_HEADERS = {
    'Authorization':        f'Bearer {GITHUB_TOKEN}',
    'Accept':               'application/vnd.github.v3+json',
    'X-GitHub-Api-Version': '2022-11-28',
}


# ââ GitHub helpers ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
def gh_get(path: str) -> tuple[str, str]:
    """Fetch a repo file. Returns (text, sha)."""
    r = requests.get(
        f'{GH_API}/repos/{REPO}/contents/{path}',
        params={'ref': BRANCH},
        headers=GH_HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    d = r.json()
    return base64.b64decode(d['content']).decode(), d['sha']


def gh_put(path: str, text: str, sha: str, message: str) -> str:
    """Commit text to path. Returns new SHA."""
    r = requests.put(
        f'{GH_API}/repos/{REPO}/contents/{path}',
        json={
            'message': message,
            'content': base64.b64encode(text.encode()).decode(),
            'sha':     sha,
            'branch':  BRANCH,
        },
        headers=GH_HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()['content']['sha']


# ââ Search ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
def tavily_search(query: str) -> list[dict]:
    """Run a Tavily web search. Returns list of result dicts."""
    r = requests.post(
        'https://api.tavily.com/search',
        json={
            'api_key':      TAVILY_KEY,
            'query':        query,
            'search_depth': 'basic',
            'max_results':  8,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get('results', [])


# ââ Window status âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
def window_status(pw: dict | None) -> str:
    if not pw:
        return 'active'
    try:
        today  = date.today()
        y      = today.year
        sm, sd = map(int, pw['start'].split('-'))
        em, ed = map(int, pw['end'].split('-'))
        start  = date(y, sm, sd)
        end    = date(y, em, ed)
        if end < start:               # window spans year boundary
            end = date(y + 1, em, ed)
        if today > end:               return 'past'
        if today >= start:            return 'active'
        return 'upcoming' if (start - today).days <= 30 else 'waiting'
    except Exception:
        return 'active'


# ââ Result evaluation âââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
SALE_KEYWORDS = [
    'equipment sale', 'gear sale', 'equipment and clothing sale',
    'pro stock', 'game-used', 'game used', 'used equipment',
    'jersey sale', 'stick sale', 'skate sale', 'annual sale',
    'end of year sale', 'end-of-year sale',
    'end of season sale', 'end-of-season sale',
    'season-end sale', 'clearance sale', 'locker room sale',
]
SKIP_DOMAINS = [
    'sidelineswap.com', 'ebay.com', 'fanatics.com', 'amazon.com',
    'walmart.com', 'fansedge.com', 'rallyhouse.com', 'sportchek.ca',
    'gameworn.us', 'mitchellandness.com', 'redbubble.com',
    'hockeyworld.com', 'shopncaasports.com', 'shop.nhl.com',
    'picclick.com', 'vividseats.com', 'seatgeek.com', 'ticketmaster.com',
    'vividseat', 'axs.com', 'stubhub.com',
]
SURPLUS_DOMAINS  = ['dispo.umich.edu', 'msusurplusstore.com']
SURPLUS_KEYWORDS = ['hockey', 'skate', 'stick', 'helmet', 'jersey',
                    'pants', 'glove', 'puck', 'ice']


def is_find(result: dict) -> bool:
    url      = result.get('url', '').lower()
    combined = (result.get('title', '') + ' ' + result.get('content', '')).lower()

    if any(d in url for d in SKIP_DOMAINS):
        return False
    # Surplus sites: any hockey-relevant item counts
    if any(d in url for d in SURPLUS_DOMAINS):
        return any(kw in combined for kw in SURPLUS_KEYWORDS)
    # General: must contain a sale keyword
    return any(kw in combined for kw in SALE_KEYWORDS)


# ââ Email âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
def send_alert(team_name: str, league: str, finds: list[dict]):
    rows = ''.join(
        f'<li style="margin-bottom:10px">'
        f'<a href="{f["url"]}">{f["title"]}</a><br>'
        f'<span style="color:#666;font-size:12px">{f["snippet"]}</span></li>'
        for f in finds
    )
    html = f'''<p><strong>{team_name}</strong> ({league})<br>
<strong>Detected:</strong> {date.today().isoformat()}</p>
<ul style="padding-left:18px">{rows}</ul>
<p style="font-size:12px;color:#888;margin-top:16px">
Dashboard (auto-refreshes):
<a href="https://nicmuffins.github.io/hockey-sale-tracker/">
nicmuffins.github.io/hockey-sale-tracker/</a></p>'''

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'ð Hockey sale alert: {team_name}'
    msg['From']    = GMAIL_USER
    msg['To']      = ALERT_TO
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
        s.login(GMAIL_USER, GMAIL_PASS)
        s.sendmail(GMAIL_USER, ALERT_TO, msg.as_string())
    print(f'  ð§ Alert sent for {team_name}')


def send_daily_summary(today: str, run_count: int,
                       teams_searched: list[dict], skipped_teams: list[dict],
                       finds_by_team: dict):
    """Send a daily digest email â always, regardless of finds."""
    sales_found = sum(len(v) for v in finds_by_team.values())

    # Teams searched table
    team_rows = ''.join(
        f'<tr><td style="padding:3px 8px">{t["name"]}</td>'
        f'<td style="padding:3px 8px;color:#888">{t.get("league","")}</td>'
        f'<td style="padding:3px 8px;text-align:center">'
        f'{"â " + str(len(finds_by_team[t["id"]])) + " find(s)" if t["id"] in finds_by_team else "â"}'
        f'</td></tr>'
        for t in teams_searched
    )

    # Skipped teams (window past)
    skipped_rows = ''.join(
        f'<tr style="color:#aaa"><td style="padding:3px 8px">{t["name"]}</td>'
        f'<td style="padding:3px 8px">{t.get("league","")}</td>'
        f'<td style="padding:3px 8px">window closed</td></tr>'
        for t in skipped_teams
    )

    # Finds detail (if any)
    if finds_by_team:
        find_items = ''.join(
            f'<li style="margin-bottom:10px">'
            f'<strong>{f["team_name"]}</strong> â '
            f'<a href="{f["url"]}">{f["title"]}</a><br>'
            f'<span style="color:#666;font-size:12px">{f["snippet"]}</span></li>'
            for items in finds_by_team.values()
            for f in items
        )
        finds_section = f'<h3 style="color:#c0392b">ð¨ New finds ({sales_found})</h3><ul style="padding-left:18px">{find_items}</ul>'
    else:
        finds_section = '<p style="color:#27ae60">â Nothing new found â no sales announced yet.</p>'

    html = f'''
<h2 style="margin-bottom:4px">ð Hockey Sale Monitor â Daily Summary</h2>
<p style="color:#888;margin-top:0">{today} &nbsp;|&nbsp; Run #{run_count}</p>

{finds_section}

<h3>Teams searched ({len(teams_searched)})</h3>
<table style="border-collapse:collapse;font-size:13px">
  <thead>
    <tr style="background:#f0f0f0">
      <th style="padding:4px 8px;text-align:left">Team</th>
      <th style="padding:4px 8px;text-align:left">League</th>
      <th style="padding:4px 8px">Result</th>
    </tr>
  </thead>
  <tbody>{team_rows}{skipped_rows}</tbody>
</table>

<p style="font-size:12px;color:#888;margin-top:20px">
Dashboard: <a href="https://nicmuffins.github.io/hockey-sale-tracker/">nicmuffins.github.io/hockey-sale-tracker/</a>
</p>
'''

    subject = (
        f'ð Hockey monitor: {sales_found} new find(s) â {today}'
        if sales_found else
        f'ð Hockey monitor: ran OK, nothing new â {today}'
    )

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = GMAIL_USER
    msg['To']      = ALERT_TO
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
        s.login(GMAIL_USER, GMAIL_PASS)
        s.sendmail(GMAIL_USER, ALERT_TO, msg.as_string())
    print(f'  ð§ Daily summary sent')


# ââ Main ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
def main():
    today = date.today().isoformat()
    print(f'\n=== Hockey Sale Monitor â {today} ===')

    # Step 1 â Load state
    ms_txt,   ms_sha   = gh_get('monitor_state.json')
    seen_txt, seen_sha = gh_get('seen_announcements.json')
    log_txt,  log_sha  = gh_get('monitor_log.txt')
    ms   = json.loads(ms_txt)
    seen = json.loads(seen_txt)

    run_count = ms.get('run_count', 0)
    print(f'run_count={run_count}')

    # Step 2 â Determine teams to search (all with active/upcoming windows)
    team_lookup = {t['id']: t for t in ms['teams']}
    to_search = [
        t for t in ms['teams']
        if window_status(t.get('predicted_window')) not in ('past', 'waiting')
    ]
    skipped = [
        t for t in ms['teams']
        if window_status(t.get('predicted_window')) in ('past', 'waiting')
    ]
    print(f'Teams to search: {[t["id"] for t in to_search]}')
    print(f'Teams skipped (window closed/waiting): {[t["id"] for t in skipped]}')

    # Step 3 â Collect known URLs
    seen_urls: set[str] = {
        e['url']
        for entries in seen.values()
        for e in entries
    }

    # Step 4 â Search and evaluate
    finds_by_team: dict[str, list[dict]] = {}

    def record(team_id: str, team_name: str, team_league: str, result: dict):
        url = result.get('url', '')
        if not url or url in seen_urls or not is_find(result):
            return
        seen_urls.add(url)
        finds_by_team.setdefault(team_id, []).append({
            'title':        result.get('title', url)[:140],
            'url':          url,
            'snippet':      result.get('content', '')[:220],
            'team_name':    team_name,
            'team_league':  team_league,
        })
        print(f'    â {url}')

    # Per-team searches
    for team in to_search:
        q = team['search_query']
        if '2026' not in q:
            q += ' 2026'
        print(f'  [{team["id"]}] {q}')
        try:
            for r in tavily_search(q):
                record(team['id'], team['name'], team['league'], r)
        except Exception as e:
            print(f'  â  search error: {e}')

    # Meta-source searches (always run)
    for meta in ms.get('meta_sources', []):
        print(f'  [meta:{meta["id"]}]')
        team_id = meta.get('team_id', meta['id'])
        t = team_lookup.get(team_id, {})
        try:
            for r in tavily_search(meta['search_query']):
                record(team_id, t.get('name', team_id), t.get('league', ''), r)
        except Exception as e:
            print(f'  â  search error: {e}')

    sales_found = sum(len(v) for v in finds_by_team.values())
    print(f'\nNew finds: {sales_found}')

    # Step 5 â Commit finds (only if any)
    if finds_by_team:
        # Update seen_announcements.json
        for team_id, items in finds_by_team.items():
            seen.setdefault(team_id, []).extend(
                {'title': f['title'], 'url': f['url'], 'detected_at': today}
                for f in items
            )
        seen_sha = gh_put(
            'seen_announcements.json',
            json.dumps(seen, indent=2, ensure_ascii=False),
            seen_sha,
            f'monitor: update seen_announcements {today}',
        )
        print('  Committed seen_announcements.json')

        # Update teams_data.json (only fetched when needed)
        td_txt, td_sha = gh_get('teams_data.json')
        td = json.loads(td_txt)
        td['last_updated'] = today
        td_map = {t['id']: t for t in td['teams']}
        for team_id, items in finds_by_team.items():
            if team_id not in td_map:
                continue
            primary = items[0]
            extras  = [{'label': f['title'][:60], 'url': f['url']} for f in items[1:]]
            td_map[team_id]['latest_news'] = {
                'summary':         f'{len(items)} new find(s) â {primary["title"]}',
                'url':             primary['url'],
                'detected_at':     today,
                'is_announcement': True,
                'source':          'GitHub Actions Monitor',
                **(({'extra_sources': extras}) if extras else {}),
            }
        gh_put(
            'teams_data.json',
            json.dumps(td, indent=2, ensure_ascii=False),
            td_sha,
            f'monitor: new find(s) {today}',
        )
        print('  Committed teams_data.json')

        # Send individual alert emails per team
        for team_id, items in finds_by_team.items():
            try:
                send_alert(items[0]['team_name'], items[0]['team_league'], items)
            except Exception as e:
                print(f'  â  email error ({team_id}): {e}')

    # Step 6 â Always update monitor_state.json
    ms['run_count']      = run_count + 1
    ms['last_monitored'] = today
    gh_put(
        'monitor_state.json',
        json.dumps(ms, indent=2, ensure_ascii=False),
        ms_sha,
        f'monitor: state update {today} (run_count={run_count + 1})',
    )
    print(f'  Committed monitor_state.json (run_count={run_count + 1})')

    # Step 7 â Append to log
    log_line = (
        f'{today} | run_count={run_count + 1}'
        f' | teams_searched={len(to_search)} | sales_found={sales_found}\n'
    )
    gh_put(
        'monitor_log.txt',
        log_txt + log_line,
        log_sha,
        f'monitor: log {today}',
    )
    print(f'  Logged: {log_line.strip()}')

    # Step 8 â Always send daily summary email
    try:
        send_daily_summary(today, run_count + 1, to_search, skipped, finds_by_team)
    except Exception as e:
        print(f'  â  summary email error: {e}')

    print('=== Done ===\n')


if __name__ == '__main__':
    main()
