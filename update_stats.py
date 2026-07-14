#!/usr/bin/env python3
"""Refresh the live numbers inside terminal.svg.

Run by .github/workflows/update-stats.yml on a schedule. Uses the GitHub API
to compute, for GH_LOGIN:
  - repo count + total stars (owned repos)
  - followers
  - total commits, lines added, lines removed, net lines of code
    (your contributions to owned non-fork repos + EXTRA_REPOS)
then patches the <tspan id="..."> targets in terminal.svg in place.
"""
import os
import re
import sys
import time

import requests

TOKEN = os.environ["GH_TOKEN"]
LOGIN = os.environ.get("GH_LOGIN", "Chase-Fournier")
# extra logins whose commits also count as yours (e.g. an old account)
LOGINS = {LOGIN.lower()} | {s.strip().lower() for s in os.environ.get("ALT_LOGINS", "").split(",") if s.strip()}
EXTRA = [s.strip() for s in os.environ.get("EXTRA_REPOS", "").split(",") if s.strip()]
SVG = os.environ.get("SVG_PATH", "terminal.svg")

API = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def gh(url, **params):
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


# ----------------------------------------------------------- repos & stars --
repos, page = [], 1
while True:
    batch = gh(f"{API}/users/{LOGIN}/repos", per_page=100, page=page, type="owner")
    if not batch:
        break
    repos += batch
    page += 1

repo_count = len(repos)
stars = sum(r["stargazers_count"] for r in repos)

# scan own non-fork repos, plus upstream projects you contribute to.
# forks are skipped so commits that also live upstream aren't counted twice.
scan = [r["full_name"] for r in repos if not r["fork"]] + EXTRA

# --------------------------------------------------------------- followers --
followers = gh(f"{API}/users/{LOGIN}")["followers"]

# ------------------------------------------- commits + lines added/removed --
commits = additions = deletions = 0
for full_name in scan:
    # /stats/contributors returns 202 while GitHub computes; poll briefly
    data = None
    for _ in range(10):
        r = requests.get(f"{API}/repos/{full_name}/stats/contributors",
                         headers=HEADERS, timeout=30)
        if r.status_code == 202:
            time.sleep(3)
            continue
        if r.status_code == 200:
            data = r.json()
        break
    if not data:
        print(f"  skip {full_name} (status {r.status_code})")
        continue
    repo_c = repo_a = repo_d = 0
    for contributor in data:
        author = contributor.get("author") or {}
        if author.get("login", "").lower() not in LOGINS:
            continue
        repo_c += contributor["total"]
        for week in contributor["weeks"]:
            repo_a += week["a"]
            repo_d += week["d"]
    commits += repo_c
    additions += repo_a
    deletions += repo_d
    # per-repo audit line — compare against the repo's Insights > Contributors graph
    print(f"  {full_name}: commits={repo_c} +{repo_a:,} / -{repo_d:,}")

loc = additions - deletions

# ------------------------------------------------------------- patch svg ----
svg = open(SVG, encoding="utf-8").read()


def put(tspan_id, text):
    global svg
    svg, n = re.subn(
        rf'(<tspan id="{tspan_id}"[^>]*>)[^<]*(</tspan>)',
        rf"\g<1>{text}\g<2>",
        svg,
    )
    if n != 1:
        sys.exit(f"error: expected exactly one <tspan id={tspan_id!r}>, found {n}")


# each stats line is padded with dot leaders to exactly COLS characters,
# so the leaders must be resized whenever the numbers change width
COLS = 78


def dots(label, parts):
    n = COLS - len(label) - 1 - sum(len(p) for p in parts)
    return "." * max(n, 2)


repos_parts = [f"{repo_count} public", "  |  ", "Stars: ", f"{stars:,}"]
commits_parts = [f"{commits:,}", "  |  ", "Followers: ", f"{followers:,}"]
loc_parts = [f"{loc:,}", "  ( ", f"{additions:,}++", ", ", f"{deletions:,}--", " )"]

put("repos", repos_parts[0])
put("stars", repos_parts[3])
put("dots_repos", dots("Repos: ", repos_parts))
put("commits", commits_parts[0])
put("followers", commits_parts[3])
put("dots_commits", dots("Commits: ", commits_parts))
put("loc", loc_parts[0])
put("loc_add", loc_parts[2])
put("loc_del", loc_parts[4])
put("dots_loc", dots("Lines.of.Code: ", loc_parts))

open(SVG, "w", encoding="utf-8").write(svg)
print(f"updated {SVG}: repos={repo_count} stars={stars} followers={followers} "
      f"commits={commits:,} loc={loc:,} (+{additions:,} / -{deletions:,})")
