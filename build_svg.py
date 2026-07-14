#!/usr/bin/env python3
"""Build terminal.svg from profile.toml.

Edit profile.toml (not this file, and not the SVG) to change the card.
Stdlib only — no packages needed. Run:  python build_svg.py
"""
import html
import re
import sys
import tomllib

CFG = tomllib.load(open("profile.toml", "rb"))

# ---------------------------------------------------------------- palette ---
C = {
    "background": "#0b0b14", "border": "#232640",
    "cyan": "#28f2e4", "magenta": "#ff2ea6", "orange": "#ffab70",
    "body": "#b6bfe2", "dim": "#4c5470", "muted": "#8891b0",
    "green": "#5dff8f", "red": "#ff5c7a",
}
C.update(CFG.get("colors", {}))

# ---------------------------------------------------------------- layout ----
W        = 940
LINE_H   = 17.5
FS_INFO  = 12.5
CHAR_W   = 7.52
TOP      = 40
PAD_BOT  = 26
INFO_X   = 318
RIGHT_X  = W - 34
COLS     = int((RIGHT_X - INFO_X) / CHAR_W)   # 78 characters per row
FS_CF    = 23
ART_X    = 32
TAG_GAP  = 22

esc = lambda s: html.escape(s, quote=False)

# ------------------------------------------------- value markup -> tspans ---
MARKS = {"g": "ok", "r": "bad", "d": "dim", "c": "label"}

def parse_value(s):
    """'35,000+ ( {g}JupiTerp++{/} )' -> [(class, text), ...]"""
    out, cls = [], "value"
    for tok in re.split(r"(\{[grdc]\}|\{/\})", s):
        if tok == "{/}":
            cls = "value"
        elif re.fullmatch(r"\{[grdc]\}", tok):
            cls = MARKS[tok[1]]
        elif tok:
            out.append((cls, tok))
    return out

def seg_tspans(segs):
    out = []
    for seg in segs:
        c, t = seg[0], seg[1]
        idattr = f' id="{seg[2]}"' if len(seg) > 2 else ""
        out.append(f'<tspan{idattr} class="{c}">{esc(t)}</tspan>')
    return "".join(out)

# --------------------------------------------------------------- info rows --
# self-updating rows; ids are the contract with update_stats.py
AUTO_STATS = [
    ("Repos: ",         [("value", "…", "repos"), ("dim", "  |  "),
                         ("label", "Stars: "), ("value", "…", "stars")], "dots_repos"),
    ("Commits: ",       [("value", "…", "commits"), ("dim", "  |  "),
                         ("label", "Followers: "), ("value", "…", "followers")], "dots_commits"),
    ("Lines.of.Code: ", [("value", "…", "loc"), ("dim", "  ( "), ("ok", "…++", "loc_add"),
                         ("dim", ", "), ("bad", "…--", "loc_del"), ("dim", " )")], "dots_loc"),
]

INFO = [("name", CFG["title"])]
for section in CFG["sections"]:
    if "name" in section:
        INFO.append(None)
        INFO.append(("sect", section["name"]))
    if section.get("auto_stats"):
        for label, segs, dots_id in AUTO_STATS:
            INFO.append(("kv", label, segs, dots_id))
    for label, value in section.get("fields", []):
        INFO.append(("kv", label + ": ", parse_value(value)))
INFO += [None, ("full", [("prompt", "❯ "), ("cursor", "▮")])]

# ---------------------------------------------------------------- validate --
errors = []
for row in INFO:
    if row and row[0] == "kv":
        label, vlen = row[1], sum(len(s[1]) for s in row[2])
        over = len(label) + 1 + vlen + 2 - COLS   # keep at least 2 leader dots
        if over > 0 and len(row) < 4:             # auto rows resize themselves
            errors.append(f'  "{label.rstrip(": ")}" is {over} character(s) too long — trim the value')
if errors:
    sys.exit("profile.toml lines do not fit the card:\n" + "\n".join(errors))

# -------------------------------------------------------------------- art ---
ART = CFG["art"]
n = len(INFO)
body_h = n * LINE_H
H = int(TOP + body_h + PAD_BOT)
art_h = len(ART) * FS_CF + TAG_GAP + FS_INFO
art_y0 = TOP + (body_h - art_h) / 2 + FS_CF
art_center_x = ART_X + max(len(l) for l in ART) * FS_CF * 0.6 / 2
tag_y = art_y0 + len(ART) * FS_CF + TAG_GAP - FS_CF + FS_INFO

def art_lines(cls):
    return "\n    ".join(
        f'<text xml:space="preserve" class="cfart {cls}" x="{ART_X}" '
        f'y="{art_y0 + i * FS_CF:.1f}">{esc(line)}</text>'
        for i, line in enumerate(ART)
    )

# ------------------------------------------------------------------ render --
rows = []
for i, row in enumerate(INFO):
    if row is None:
        continue
    y = TOP + i * LINE_H + FS_INFO
    kind = row[0]
    if kind == "name":
        name = row[1]
        rule = "─" * (COLS - len(name) - 1)
        rows.append(f'<text xml:space="preserve" class="info" x="{INFO_X}" y="{y:.1f}">'
                    f'<tspan class="prompt">{esc(name)}</tspan><tspan class="dim"> {rule}</tspan></text>')
    elif kind == "sect":
        word = row[1]
        rule = "─" * (COLS - len(word) - 3)
        rows.append(f'<text xml:space="preserve" class="info" x="{INFO_X}" y="{y:.1f}">'
                    f'<tspan class="dim">─ </tspan><tspan class="muted">{esc(word)}</tspan>'
                    f'<tspan class="dim"> {rule}</tspan></text>')
    elif kind == "kv":
        label, vsegs = row[1], row[2]
        dots_id = row[3] if len(row) > 3 else None
        vlen = sum(len(s[1]) for s in vsegs)
        dots_n = max(COLS - len(label) - 1 - vlen, 2)
        idattr = f' id="{dots_id}"' if dots_id else ""
        rows.append(f'<text xml:space="preserve" class="info" x="{INFO_X}" y="{y:.1f}">'
                    f'<tspan class="label">{esc(label)}</tspan>'
                    f'<tspan{idattr} class="dim">{"." * dots_n}</tspan>'
                    f'<tspan> </tspan>{seg_tspans(vsegs)}</text>')
    elif kind == "full":
        rows.append(f'<text xml:space="preserve" class="info" x="{INFO_X}" y="{y:.1f}">{seg_tspans(row[1])}</text>')
info_block = "\n    ".join(rows)

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{esc(CFG["title"])} — terminal profile card">
  <style>
    .mono   {{ font-family: ui-monospace, 'Cascadia Code', 'JetBrains Mono', Menlo, Consolas, monospace; }}
    .cfart  {{ font-size: {FS_CF}px; }}
    .info   {{ font-size: {FS_INFO}px; fill: {C["body"]}; }}
    .cf     {{ fill: {C["cyan"]}; }}
    .ghost  {{ fill: {C["magenta"]}; opacity: .5; }}
    .prompt {{ fill: {C["cyan"]}; font-weight: bold; }}
    .label  {{ fill: {C["cyan"]}; }}
    .value  {{ fill: {C["orange"]}; }}
    .muted  {{ fill: {C["muted"]}; }}
    .dim    {{ fill: {C["dim"]}; }}
    .ok     {{ fill: {C["green"]}; }}
    .bad    {{ fill: {C["red"]}; }}
    .cursor {{ fill: {C["cyan"]}; animation: blink 1.1s steps(1) infinite; }}
    .glitch {{ animation: flicker 6s steps(1) infinite; }}
    @keyframes blink   {{ 50% {{ opacity: 0; }} }}
    @keyframes flicker {{
      0%,91%,94%,100% {{ transform: translate(0,0); opacity:.5; }}
      92%             {{ transform: translate(-3px,2px); opacity:.75; }}
      93%             {{ transform: translate(4px,-2px); opacity:.3;  }}
    }}
    @media (prefers-reduced-motion: reduce) {{ .cursor, .glitch {{ animation: none; }} }}
  </style>

  <rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="8" fill="{C["background"]}" stroke="{C["border"]}" stroke-width="1"/>

  <g class="mono glitch" transform="translate(-3,2)">
    {art_lines("ghost")}
  </g>
  <g class="mono">
    {art_lines("cf")}
  </g>
  <text class="mono info dim" x="{art_center_x:.0f}" y="{tag_y:.1f}" text-anchor="middle">{esc(CFG["tag"])}</text>

  <g class="mono">
    {info_block}
  </g>
</svg>
'''

open("terminal.svg", "w").write(svg)
print(f"wrote terminal.svg  ({W}x{H})")
