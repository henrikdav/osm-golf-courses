"""Turns a country's raw Overpass answers into clean clubs, courses and holes.

A club is a golf course outline (`leisure=golf_course`, a way or a multipolygon relation). Its holes are the
`golf=hole` lines inside it, each from the back tee to the pin. One outline often holds more than one course, and
clubs map that in three ways (seen in southern Sweden, 2026-10):

- one course: every hole numbered once (Vellinge GK)
- by a course name on each hole, `golf:course:name` (Bokskogen: Gamla Banan and Kungsbanan), or `course:name`
  or `course` at some clubs
- in the hole's own name, with no course name: "Blå 1", "Gul 1", "Pay & Play 1" (Örestad)
- holes 1–27 in one run, as three 9-hole loops (Malmö Burlöv since 2026-10-24, course name "1-27")
- no names at all, every number twice: two courses (Båstad, Halmstad); split by which hole follows which

A number twice at the same spot (pins within 30 m) is one hole drawn twice, e.g. from two tees: the longer line,
from the back tee, is kept.

Every club is kept, also without holes, and each course gets notes on what looks wrong, so the app can show
what there is and say how far to trust it. Pure: no network, so it is tested on saved answers.
"""
import math
import re

FORMAT = 1
ATTRIBUTION = "© OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)"

# Lengths along the line, back tee to pin, that are plausible for each par. Outside them the hole is likely
# mapped wrong (e.g. Malmö Burlöv's Black Course: a par 5 of 309 m).
PLAUSIBLE_LENGTH = {3: (60, 260), 4: (200, 500), 5: (350, 650), 6: (450, 800)}


def meters(a, b):
    """Distance between two (lat, lng) points; equirectangular, plenty for one hole."""
    lat = math.radians((a[0] + b[0]) / 2)
    return math.hypot((a[0] - b[0]) * 111195, (a[1] - b[1]) * 111195 * math.cos(lat))


def length(path):
    return sum(meters(path[i], path[i + 1]) for i in range(len(path) - 1))


def point(p):
    return (round(p["lat"], 6), round(p["lon"], 6))


def rings(element):
    """The outer rings of a course outline, as lists of (lat, lng)."""
    if element["type"] == "way":
        return [[point(p) for p in element.get("geometry", [])]]
    return [[point(p) for p in m["geometry"]] for m in element.get("members", [])
            if m.get("type") == "way" and m.get("role", "outer") in ("outer", "") and m.get("geometry")]


def inside(pt, ring):
    """Ray casting: is the point inside the ring?"""
    y, x = pt
    hit = False
    for i in range(len(ring)):
        y1, x1 = ring[i]
        y2, x2 = ring[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def bbox(points):
    lats = [p[0] for p in points]
    lngs = [p[1] for p in points]
    return [min(lats), min(lngs), max(lats), max(lngs)]


COURSE_NAME_KEYS = ("golf:course:name", "course:name", "golf:course", "course")
SAME_HOLE = 30   # meters between the pins of two lines with one number: the same hole


def says_nothing(name):
    """A course name that is only a range of numbers ("1-27", "1–18") names nothing."""
    return re.fullmatch(r"\d+\s*[-–]\s*\d+", name) is not None


def loop_name(tags):
    """The course a hole belongs to within its club: its course name, else its own name without its number
    ("Blå 1" with ref 1 → "Blå"); "" when neither says ("Hole 1" says nothing)."""
    for key in COURSE_NAME_KEYS:
        name = (tags.get(key) or "").strip()
        if name and not says_nothing(name) and not re.fullmatch(r"\d+", name):
            return name
    own = (tags.get("name") or "").strip()
    ref = (tags.get("ref") or "").strip()
    if ref and own.endswith(" " + ref):
        # "Gamla banan hål 1" → "Gamla banan"; "Hole 1" → nothing.
        loop = re.sub(r"(^|\s+)(hole|hål|hull)$", "", own[: -len(ref)].strip(" -–:#"), flags=re.IGNORECASE)
        return loop.strip(" -–:#")
    return ""


def number(value):
    value = (value or "").strip()
    return int(value) if re.fullmatch(r"\d{1,2}", value) else None


def hole_lines(lines):
    """The lines by hole number, a hole drawn twice at the same spot kept once (the longer line, from the back
    tee), and how many lines had no usable number."""
    by_number = {}
    unnumbered = 0
    for line in lines:
        n = number(line.get("tags", {}).get("ref"))
        if n is None or n == 0 or len(line.get("geometry") or []) < 2:
            unnumbered += 1
            continue
        kept = by_number.setdefault(n, [])
        pin = pin_of(line)
        twin = next((i for i, k in enumerate(kept) if meters(pin_of(k), pin) <= SAME_HOLE), None)
        if twin is None:
            kept.append(line)
        elif line_length(line) > line_length(kept[twin]):
            kept[twin] = line
    return by_number, unnumbered


def tee_of(line):
    return point(line["geometry"][0])


def pin_of(line):
    return point(line["geometry"][-1])


def line_length(line):
    return length([point(p) for p in line["geometry"]])


def split_twins(by_number):
    """Every number twice, far apart: two courses with no names. Each takes, hole by hole, the line whose tee is
    nearer the green of its previous hole. None unless every number is there twice."""
    numbers = sorted(by_number)
    if len(numbers) < 9 or any(len(by_number[n]) != 2 for n in numbers):
        return None
    chains = [{numbers[0]: by_number[numbers[0]][0]}, {numbers[0]: by_number[numbers[0]][1]}]
    previous = numbers[0]
    for n in numbers[1:]:
        a, b = by_number[n]
        ends = [pin_of(chains[0][previous]), pin_of(chains[1][previous])]
        keep = meters(ends[0], tee_of(a)) + meters(ends[1], tee_of(b))
        swap = meters(ends[0], tee_of(b)) + meters(ends[1], tee_of(a))
        chains[0][n], chains[1][n] = (a, b) if keep <= swap else (b, a)
        previous = n
    return chains


def course(name, lines_by_number, unnumbered=0, offset=0):
    """One course from its lines by hole number (the first line of a number kept if it is still there twice),
    numbered from 1 (offset: a loop of holes 10–18 becomes 1–9), with notes on what looks wrong."""
    holes = {}
    repeated = set()
    for n in sorted(lines_by_number):
        lines = lines_by_number[n]
        if isinstance(lines, list):
            if len(lines) > 1:
                repeated.add(n - offset)
            lines = lines[0]
        tags = lines.get("tags", {})
        par = number(tags.get("par"))
        index = number(tags.get("handicap"))
        holes[n - offset] = {"n": n - offset, "par": par if par in PLAUSIBLE_LENGTH else None,
                             "index": index if index and 1 <= index <= 18 else None,
                             "path": [list(point(p)) for p in lines["geometry"]]}
    ordered = [holes[n] for n in sorted(holes)]
    last = max(holes) if holes else 0
    missing = [n for n in range(1, last + 1) if n not in holes]
    # Every hole there once, numbered from 1 without gaps, however many: a 12-hole course is complete. Whether
    # that is the whole course (or the first 12 holes mapped of 18) is for the app to judge.
    complete = bool(holes) and not missing and not repeated

    notes = []
    if missing:
        notes.append("Holes missing: " + ", ".join(map(str, missing)))
    if repeated:
        notes.append("Numbered twice (the first kept): " + ", ".join(map(str, sorted(repeated))))
    if unnumbered:
        notes.append("%d hole line%s without a number left out" % (unnumbered, "" if unnumbered == 1 else "s"))
    no_par = [h["n"] for h in ordered if h["par"] is None]
    if no_par and len(no_par) < len(ordered):
        notes.append("No par on hole " + ", ".join(map(str, no_par)))
    elif ordered and no_par:
        notes.append("No par")
    for h in ordered:
        if h["par"]:
            low, high = PLAUSIBLE_LENGTH[h["par"]]
            meters_along = length(h["path"])
            if not low <= meters_along <= high:
                notes.append("Hole %d is %d m for par %d" % (h["n"], round(meters_along), h["par"]))
    indexes = [h["index"] for h in ordered if h["index"]]
    if len(set(indexes)) != len(indexes):
        notes.append("The same index on more than one hole")
    return {"name": name or None, "complete": complete, "holeCount": len(ordered), "holes": ordered, "notes": notes}


def courses_of(lines, club):
    """A club's courses from its hole lines, grouped by course name, then by the rules for unnamed twins and runs
    of 27 holes."""
    groups = {}
    spelled = {}   # by lower case: "Ringenäs gul" and "Ringenäs Gul" are one course, named as first seen
    for line in lines:
        key = loop_name(line.get("tags", {}))
        key = "" if key.lower() == club.lower() else key
        groups.setdefault(spelled.setdefault(key.lower(), key), []).append(line)
    courses = []
    for name, group in groups.items():
        by_number, unnumbered = hole_lines(group)
        twins = split_twins(by_number) if not name else None
        if twins:
            for i, chain in enumerate(twins):
                courses.append(course("Course %d" % (i + 1), chain, unnumbered if i == 0 else 0))
            continue
        if sorted(by_number) == list(range(1, 28)) and all(len(v) == 1 for v in by_number.values()):
            for first in (1, 10, 19):
                loop = {n: by_number[n] for n in range(first, first + 9)}
                label = "%d–%d" % (first, first + 8)   # as the club calls them: 1–9, 10–18, 19–27
                courses.append(course("%s, %s" % (name, label) if name else label, loop, offset=first - 1))
            continue
        courses.append(course(name, by_number, unnumbered))
    return sorted((c for c in courses if c["holes"]), key=lambda c: natural(c["name"] or ""))


def natural(text):
    """Sorts "1–9" before "10–18", and "Course 2" before "Course 10"."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


NUMBERED = re.compile(r"^(?:(.*), )?(\d+)–(\d+)$")


def combo_name(first, second, last):
    """Two loops played one after the other. Numbered loops that follow on are named as the club calls the round:
    1–9 then 10–18 is "1–18", 10–18 then 19–27 "10–27", and 19–27 then 1–9 (round the run of `last` holes) "19–09".
    Anything else is the two names: "Blå + Gul", "1–9 + 19–27"."""
    a, b = NUMBERED.match(first or ""), NUMBERED.match(second or "")
    if a and b and a.group(1) == b.group(1):
        start, end, next_start, next_end = int(a.group(2)), int(a.group(3)), int(b.group(2)), int(b.group(3))
        prefix = "%s, " % a.group(1) if a.group(1) else ""
        if next_start == end + 1:
            return "%s%d–%d" % (prefix, start, next_end)
        if next_start == 1 and end == last:
            return "%s%d–%02d" % (prefix, start, next_end)
    return "%s + %s" % (first, second)


def combos(courses):
    """For an 18-hole round at a club of 9-hole loops: every two loops, one after the other, as indexes into its
    courses (the second loop's holes become 10–18 in the app)."""
    loops = [i for i, c in enumerate(courses)
             if c["name"] and c["complete"] and len(c["holes"]) == 9]
    last = max((int(m.group(3)) for m in (NUMBERED.match(courses[i]["name"]) for i in loops) if m), default=0)
    return [{"name": combo_name(courses[a]["name"], courses[b]["name"], last), "courses": [a, b]}
            for a in loops for b in loops if a != b]


def clean(outlines, holes, greens):
    """Clubs from the raw elements: outlines (ways and relations), hole lines, and greens and tees (with centers).
    Returns the clubs and the counts the publishing checks compare."""
    clubs = []
    for e in outlines:
        rs = [r for r in rings(e) if len(r) > 2]
        if not rs:
            continue
        box = bbox([p for r in rs for p in r])
        clubs.append({"element": e, "rings": rs, "box": box, "lines": [], "greens": [],
                      "area": (box[2] - box[0]) * (box[3] - box[1])})

    def owner(pt):
        found = [c for c in clubs
                 if c["box"][0] <= pt[0] <= c["box"][2] and c["box"][1] <= pt[1] <= c["box"][3]
                 and any(inside(pt, r) for r in c["rings"])]
        # A small outline inside a larger one (a short course within a club's grounds) takes what is in it.
        return min(found, key=lambda c: c["area"]) if found else None

    outside = 0
    for line in holes:
        g = line.get("geometry") or []
        if len(g) < 2:
            continue
        club = owner(point(g[len(g) // 2]))
        if club:
            club["lines"].append(line)
        else:
            outside += 1
    for e in greens:
        if e.get("tags", {}).get("golf") != "green" or not e.get("center"):
            continue
        c = e["center"]
        club = owner((round(c["lat"], 6), round(c["lon"], 6)))
        if club:
            club["greens"].append([round(c["lat"], 6), round(c["lon"], 6)])

    result = []
    for club in clubs:
        e = club["element"]
        name = (e.get("tags", {}).get("name") or "").strip() or "Golf course"
        courses = courses_of(club["lines"], name)
        box = club["box"]
        entry = {"id": "%s/%d" % (e["type"], e["id"]), "name": name,
                 "lat": round((box[0] + box[2]) / 2, 6), "lng": round((box[1] + box[3]) / 2, 6),
                 "bbox": [round(v, 6) for v in box], "courses": courses}
        pairs = combos(courses)
        if pairs:
            entry["combos"] = pairs
        if not courses and club["greens"]:
            entry["greens"] = club["greens"]
        result.append(entry)
    result.sort(key=lambda c: (c["name"].lower(), c["id"]))

    counts = {
        "clubs": len(result),
        "clubsWithHoles": sum(1 for c in result if c["courses"]),
        "clubsWithCompleteCourse": sum(1 for c in result if any(x["complete"] for x in c["courses"])),
        "completeCourses": sum(1 for c in result for x in c["courses"] if x["complete"]),
        "complete9or18": sum(1 for c in result for x in c["courses"] if x["complete"] and x["holeCount"] in (9, 18)),
        "clubsWithGreensOnly": sum(1 for c in result if "greens" in c),
        "holeLinesOutsideClubs": outside,
    }
    return result, counts


def country_file(code, name, clubs, counts, made):
    return {"format": FORMAT, "country": code, "name": name, "made": made, "attribution": ATTRIBUTION,
            "counts": counts, "clubs": clubs}
