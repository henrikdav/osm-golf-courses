"""What the data has and lacks, club by club, so it shows where work pays and how it improves week by week.

Each club gets a level, by what a player gets when starting a round there:
- 0 name only: no holes on the map;
- 1 holes, not complete: some holes mapped, no course whole;
- 2 par: a course whole, with par on every hole (GPS distances and a score against par);
- 3 index: and the hole index on every hole of a course or combination (net scoring);
- 4 tees: and lengths per tee from a club file (the full scorecard).

And what it lacks for the next level, in words. The report is written beside the country's format-2 file
(report-<file>.json and report.html), and each week's totals are added to reports/<country>.json, which the weekly
run commits back, so the totals can be followed over time.
"""
import html
import json
import os

LEVELS = ["name only", "holes, not complete", "par", "index", "tees"]


def playable(club):
    """What a round can be played on, as (name, holes): the complete courses (a loop alone too), and combinations."""
    courses = {c["key"]: c for c in club.get("courses", [])}
    out = [(c.get("name") or "main", c["holes"]) for c in courses.values() if c.get("complete")]
    for combo in club.get("combos", []):
        loops = [courses.get(k) for k in combo["loops"]]
        if all(l and l.get("complete") for l in loops):
            holes = loops[0]["holes"] + loops[1]["holes"]
            index = combo.get("index") or [None] * 18
            out.append((combo["name"], [dict(h, index=i) for h, i in zip(holes, index)]))
    return out


def club_row(club):
    courses = club.get("courses", [])
    complete = [c for c in courses if c.get("complete")]
    with_par = [c for c in complete if all(isinstance(h.get("par"), int) for h in c["holes"])]
    rounds = playable(club)
    indexed = [name for name, holes in rounds if all(isinstance(h.get("index"), int) for h in holes)]
    tees = sorted({t["name"] for c in courses for t in c.get("tees", [])})
    if not courses:
        level, lacks = 0, "holes on the map"
    elif not complete:
        level, lacks = 1, "a course with every hole mapped"
    elif not with_par:
        level, lacks = 1, "par on every hole"
    elif not indexed:
        level, lacks = 2, "hole index"
    elif not tees:
        level, lacks = 3, "lengths per tee (club file)"
    else:
        level, lacks = 4, ""
    return {"id": club["id"], "name": club["name"], "level": level, "lacks": lacks,
            "courses": len(courses), "complete": len(complete), "combos": len(club.get("combos", [])),
            "indexed": indexed, "tees": tees, "clubFile": "clubFile" in club,
            "notes": sum(len(c.get("notes", [])) for c in courses)}


def report(country, clubs, made):
    rows = sorted((club_row(c) for c in clubs), key=lambda r: (-r["level"], r["name"]))
    totals = {name: sum(1 for r in rows if r["level"] == i) for i, name in enumerate(LEVELS)}
    totals.update({"clubs": len(rows), "clubFiles": sum(1 for r in rows if r["clubFile"]),
                   "withNotes": sum(1 for r in rows if r["notes"])})
    return {"country": country, "made": made, "levels": LEVELS, "totals": totals, "clubs": rows}


def add_to_history(path, rep):
    """Adds this week's totals to the country's history (one entry a day at most), and returns the history."""
    history = []
    if os.path.exists(path):
        with open(path) as f:
            history = json.load(f)
    day = rep["made"][:10]
    history = [h for h in history if h["date"] != day] + [dict(rep["totals"], date=day)]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return history


def page(reports, histories):
    """report.html: per country, the totals week by week and every club with what it lacks."""
    e = html.escape
    parts = ['<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
             '<title>OSM golf courses: what the data has</title>'
             '<style>body{font:15px/1.4 system-ui,sans-serif;margin:16px;max-width:900px}'
             'table{border-collapse:collapse;width:100%;margin:8px 0 24px}th,td{text-align:left;padding:3px 8px;'
             'border-bottom:1px solid #ddd}td.n{text-align:right}h2{margin-top:32px}</style>'
             '<h1>What the data has</h1><p>Each club by what a player gets when starting a round there: '
             '<b>par</b> (GPS and par), <b>index</b> (net scoring), <b>tees</b> (the full scorecard, from a club '
             'file). Club files: <a href="https://github.com/henrikdav/osm-golf-courses/issues/2">#2</a>.</p>']
    for rep in reports:
        country = rep["country"]
        parts.append("<h2>%s</h2><p>Made %s.</p>" % (e(country), e(rep["made"])))
        head = "".join("<th>%s</th>" % e(n) for n in ["Week"] + LEVELS + ["club files"])
        rows = "".join("<tr><td>%s</td>%s<td class=n>%d</td></tr>" % (
            e(h["date"]), "".join("<td class=n>%d</td>" % h.get(n, 0) for n in LEVELS), h.get("clubFiles", 0))
            for h in reversed(histories.get(country, [])[-12:]))
        parts.append("<table><tr>%s</tr>%s</table>" % (head, rows))
        parts.append("<table><tr><th>Club</th><th>Has</th><th>Lacks</th><th>Notes</th></tr>")
        for r in rep["clubs"]:
            parts.append("<tr><td>%s%s</td><td>%s</td><td>%s</td><td class=n>%s</td></tr>" % (
                e(r["name"]), " (club file)" if r["clubFile"] else "", e(LEVELS[r["level"]]), e(r["lacks"]),
                r["notes"] or ""))
        parts.append("</table>")
    return "".join(parts)
