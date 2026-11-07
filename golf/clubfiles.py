"""Club files: what OpenStreetMap can't say about a club, written by hand from the club's own scorecard (#2).

One file per club, clubs/<club id>.json, keyed by the club's stable id (format 2). It holds:
- loops: per course key, its par on every hole (the club's own, from its scorecard: never taken from OSM, never a
  correction of OSM's), its ranking 1–9 (the order of its holes by difficulty), the index as the scorecard prints it
  when the course is played alone (e.g. 2, 4 … 18 on a 9-hole course), and lengths per tee. A course OSM doesn't have
  yet ("new": its name and par) is added without positions;
- combos: combinations of loops, in order, and which loop takes the odd indexes. With onlyTheseCombos the club
  plays these only and the others OSM gives are dropped; else they are kept;
- source: where it came from (the club's scorecard or slope tables, who wrote it down, when, and what was checked
  against the printed card since), and source.par, where the par comes from;
- slope: course and slope rating per course or combination key, for men and women, from the club's slope tables
  (golf/slope.py): { key: { "men" | "women": { par, rated, tees: { name: { cr, slope } } } } }. A table is always
  for an 18-hole round, also on a shorter course (played to 18 holes);
- as18, on a loop of fewer than 18 holes that is also played as 18 (a 12-hole course, then its holes 1–6 again, Kvarnby
  and Oxie): { "play": [the course's hole played as hole 1, 2 … 18], "index": [the 18 hole indexes of that round, as
  printed on the card or the tee signs] }. Par and lengths of a hole played again are its own; only the index differs.

The weekly run merges the files into format 2, as additions an older reader skips:
- a loop's holes get the club's par and, as their index, the scorecard's index, else the loop's ranking (OSM's own
  index on a loop is often the first loop's, copied); OSM's notes about par and index no longer apply and are dropped;
- a new course is added with its par, index and tees, "mapped": false and no positions;
- a loop gets "tees": [{"name", "lengths": [m per hole]}];
- each combination of the file gets "index": the 18 indexes (the odd loop's holes 2 × rank − 1, the other's
  2 × rank), and is added if OSM didn't pair those loops;
- a course or combination gets "slope": { "men" | "women": { par, rated, tees: [{name, cr, slope}] } };
- the club gets "clubFile": the file's source.

check() says what is wrong with a file against the club's OSM data; a file with problems is not merged.

Sources: the club's own data where there is any, or openly published data; nothing from a source whose terms forbid it.
Each file says where its data came from and how it was checked (source).
"""
import json
import re
import os

FIELDS = {"id", "name", "source", "loops", "combos", "onlyTheseCombos", "slope"}


def load(folder="clubs"):
    """The club files by club id."""
    files = {}
    if not os.path.isdir(folder):
        return files
    for name in sorted(os.listdir(folder)):
        if name.endswith(".json"):
            with open(os.path.join(folder, name)) as f:
                data = json.load(f)
            files[data.get("id")] = data
    return files


PAR_NOTE = re.compile(r"^(No par\b.*|Hole \d+ is \d+ m for par \d+)$")
INDEX_NOTE = "The same index on more than one hole"


def drop_notes(notes, par=False, index=False):
    """OSM's notes about the par or the index of a course, which no longer hold once the club's own values are used."""
    return [n for n in notes if not (par and PAR_NOTE.match(n)) and not (index and n == INDEX_NOTE)]


def check(file, club):
    """What is wrong with a club file against the club's format-2 data, as sentences; empty when it can be merged."""
    problems = []
    unknown = set(file) - FIELDS
    if unknown:
        problems.append("unknown fields: %s" % ", ".join(sorted(unknown)))
    if not file.get("source"):
        problems.append("no source")
    courses = {c["key"]: c for c in club.get("courses", [])}
    for key, loop in file.get("loops", {}).items():
        course = courses.get(key)
        new = loop.get("new")
        if course and new:
            problems.append("loop %s: OSM has this course now, it is no longer new" % key)
            continue
        if not course and not new:
            problems.append("loop %s: no such course in OSM" % key)
            continue
        if new:
            if not new.get("name") or not isinstance(new.get("par"), list) or not all(isinstance(p, int) for p in new["par"]):
                problems.append("loop %s: a new course needs its name and par on every hole" % key)
                continue
            course = {"holes": [{"n": i + 1, "par": p} for i, p in enumerate(new["par"])]}
        n = len(course["holes"])
        index = loop.get("index")
        if index is not None and (len(index) != n or len(set(index)) != n or not all(isinstance(i, int) and 1 <= i <= 2 * n for i in index)):
            problems.append("loop %s: the index must be %d different hole indexes" % (key, n))
        in_combo = any(key in c.get("loops", []) for c in file.get("combos", []))
        if in_combo and ranking_missing(loop):
            problems.append("loop %s: a ranking or an index, for its combinations" % key)
        if ranking_missing(loop) and not loop.get("tees") and not loop.get("par") and not new:
            problems.append("loop %s: nothing to add" % key)
        ranking = loop.get("ranking")
        if ranking is not None and sorted(ranking) != list(range(1, n + 1)):
            problems.append("loop %s: the ranking must hold 1–%d once each" % (key, n))
        as18 = loop.get("as18")
        if as18 is not None:
            play, idx = as18.get("play"), as18.get("index")
            if not (isinstance(play, list) and len(play) == 18 and all(isinstance(h, int) and 1 <= h <= n for h in play)):
                problems.append("loop %s: as18 play must be 18 holes of the course (1–%d)" % (key, n))
            elif not (isinstance(idx, list) and len(idx) == 18 and sorted(idx) == list(range(1, 19))):
                problems.append("loop %s: as18 index must hold 1–18 once each" % key)
            elif n >= 18:
                problems.append("loop %s: as18 is for a course of fewer than 18 holes" % key)
            elif isinstance(loop.get("index"), list) and len(loop["index"]) == n:
                # The holes played for the first time carry the course's own index; the two must agree.
                seen = set()
                for i, h in enumerate(play):
                    if h not in seen and idx[i] != loop["index"][h - 1]:
                        problems.append("loop %s: as18 index %d for hole %d is not the course's index %d" % (key, idx[i], h, loop["index"][h - 1]))
                    seen.add(h)
        for tee, lengths in loop.get("tees", {}).items():
            if len(lengths) != n or not all(isinstance(m, int) and m > 0 for m in lengths):
                problems.append("loop %s, tee %s: %d lengths in metres" % (key, tee, n))
        par = loop.get("par")
        if not new and not (isinstance(par, list) and len(par) == n and all(isinstance(p, int) and 3 <= p <= 6 for p in par)):
            problems.append("loop %s: par on all %d holes, each 3–6, the club's own (not corrections to OSM's, nothing from OSM)" % (key, n))
    known = set(courses) | {k for k, l in file.get("loops", {}).items() if l.get("new")}
    for combo in file.get("combos", []):
        loops = combo.get("loops", [])
        if len(loops) != 2 or any(k not in file.get("loops", {}) or k not in known for k in loops):
            problems.append("combination %s: two loops of this file and of OSM" % "+".join(loops))
        elif combo.get("odd") not in loops:
            problems.append("combination %s: odd must be one of its loops" % "+".join(loops))
        elif any(file["loops"][k].get("ranking") is None for k in loops):
            problems.append("combination %s: both loops need a ranking" % "+".join(loops))
    if file.get("onlyTheseCombos"):
        combos = {"+".join(c.get("loops", [])) for c in file.get("combos", [])}
    else:
        combos = {c["key"] for c in club.get("combos", [])} | {"+".join(c.get("loops", [])) for c in file.get("combos", [])}
    for key, genders in file.get("slope", {}).items():
        if key not in known and key not in combos:
            problems.append("slope %s: no such course or combination" % key)
            continue
        for gender, table in genders.items():
            what = "slope %s %s" % (key, gender)
            if gender not in ("men", "women"):
                problems.append("%s: men or women" % what)
            elif not isinstance(table.get("par"), int) or not table.get("tees"):
                problems.append("%s: its par and tees" % what)
            else:
                for tee, value in table["tees"].items():
                    if not 50 <= value.get("cr", 0) <= 90 or not 55 <= value.get("slope", 0) <= 155:
                        problems.append("%s, tee %s: course rating 50–90 and slope 55–155" % (what, tee))
    if file.get("loops") and not (file.get("source") or {}).get("par"):
        problems.append("source.par: where the par comes from")
    if file.get("slope") and not (file.get("source") or {}).get("slope"):
        problems.append("slope: the tables it was read from, under source")
    return problems


def ranking_missing(loop):
    return loop.get("ranking") is None and loop.get("index") is None


def merge(club, file):
    """The club's format-2 data with the file merged in (a new dict; the club is left as it was)."""
    out = json.loads(json.dumps(club))
    out.setdefault("courses", [])
    for key, loop in file.get("loops", {}).items():
        new = loop.get("new")
        if new:
            out["courses"].append({"key": key, "name": new["name"], "complete": True, "mapped": False,
                                   "holeCount": len(new["par"]), "notes": ["Not on the map yet"],
                                   "holes": [{"n": i + 1, "par": p, "index": None, "path": []} for i, p in enumerate(new["par"])]})
    courses = {c["key"]: c for c in out["courses"]}
    for key, loop in file.get("loops", {}).items():
        course = courses[key]
        if isinstance(loop.get("par"), list):
            for hole, value in zip(course["holes"], loop["par"]):
                hole["par"] = value
            course["notes"] = drop_notes(course.get("notes", []), par=True)
        if loop.get("index") or loop.get("ranking"):
            for hole, value in zip(course["holes"], loop.get("index") or loop["ranking"]):
                hole["index"] = value
            course["notes"] = drop_notes(course.get("notes", []), index=True)
        if loop.get("tees"):
            course["tees"] = [{"name": name, "lengths": lengths} for name, lengths in loop["tees"].items()]
        if loop.get("as18"):
            course["as18"] = {"play": list(loop["as18"]["play"]), "index": list(loop["as18"]["index"])}
    if file.get("combos"):
        names = {c["key"]: c["name"] for c in out.get("combos", [])}
        combos = [] if file.get("onlyTheseCombos") else [c for c in out.get("combos", [])
                                                         if c["key"] not in {"+".join(x["loops"]) for x in file["combos"]}]
        for combo in file["combos"]:
            first, second = combo["loops"]
            key = "%s+%s" % (first, second)
            index = []
            for k in (first, second):
                odd = k == combo["odd"]
                index += [2 * rank - 1 if odd else 2 * rank for rank in file["loops"][k]["ranking"]]
            combos.append({"key": key, "name": names.get(key) or "%s + %s" % (courses[first].get("name") or first,
                                                                           courses[second].get("name") or second),
                           "loops": [first, second], "index": index})
        out["combos"] = combos
    combos = {c["key"]: c for c in out.get("combos", [])}
    for key, genders in file.get("slope", {}).items():
        target = courses.get(key) or combos[key]
        target["slope"] = {gender: {"par": t["par"], "rated": t.get("rated"),
                                    "tees": [{"name": name, "cr": v["cr"], "slope": v["slope"]} for name, v in t["tees"].items()]}
                           for gender, t in genders.items()}
    out["clubFile"] = file["source"]
    return out


def overlay(file):
    """What a club file adds, as a separate piece of data to be joined to the club's OSM data by club id and course key
    where it is used, instead of being mixed into the OSM data (the OSM database stays apart from ours, ODbL).

    { "loops": { key: { new?: { name, par }, par?: [par on every hole], index?: [..], tees?: [{ name, lengths }],
                        as18?: { play: [18 holes], index: [18] } } },
      "combos": [{ key, loops: [a, b], index: [18] }], "onlyTheseCombos"?: true,
      "slope": { key: { men|women: { par, rated, tees: [{ name, cr, slope }] } } }, "clubFile": source }
    apply_overlay(club, overlay(file)) gives what merge(club, file) gives."""
    out = {"loops": {}}
    for key, loop in file.get("loops", {}).items():
        item = {}
        if loop.get("new"):
            item["new"] = loop["new"]
        if loop.get("par"):
            item["par"] = loop["par"]
        if loop.get("index") or loop.get("ranking"):
            item["index"] = loop.get("index") or loop["ranking"]
        if loop.get("tees"):
            item["tees"] = [{"name": name, "lengths": lengths} for name, lengths in loop["tees"].items()]   # in order
        if loop.get("as18"):
            item["as18"] = {"play": list(loop["as18"]["play"]), "index": list(loop["as18"]["index"])}
        if item:
            out["loops"][key] = item
    if file.get("combos"):
        out["combos"] = []
        for combo in file["combos"]:
            first, second = combo["loops"]
            index = []
            for k in (first, second):
                odd = k == combo["odd"]
                index += [2 * rank - 1 if odd else 2 * rank for rank in file["loops"][k]["ranking"]]
            out["combos"].append({"key": "%s+%s" % (first, second), "loops": [first, second], "index": index})
        if file.get("onlyTheseCombos"):
            out["onlyTheseCombos"] = True
    for key, genders in file.get("slope", {}).items():
        out.setdefault("slope", {})[key] = {
            gender: {"par": t["par"], "rated": t.get("rated"),
                     "tees": [{"name": name, "cr": v["cr"], "slope": v["slope"]} for name, v in t["tees"].items()]}
            for gender, t in genders.items()}
    out["clubFile"] = {k: v for k, v in file["source"].items() if isinstance(v, str)}   # where it came from, as text
    return out


def apply_overlay(club, extra, osm_scoring=False):
    """The club's format-2 data with an overlay joined to it (a new dict). The same join the app makes when it opens.
    The app never uses OSM's par or hole index: a hole has them only from the overlay, else None (osm_scoring=True keeps
    OSM's, for comparing with merge())."""
    out = json.loads(json.dumps(club))
    out.setdefault("courses", [])
    if not osm_scoring:
        for course in out["courses"]:
            for hole in course.get("holes", []):
                hole["par"] = None
                hole["index"] = None
    for key, loop in extra.get("loops", {}).items():
        new = loop.get("new")
        if new:
            out["courses"].append({"key": key, "name": new["name"], "complete": True, "mapped": False,
                                   "holeCount": len(new["par"]), "notes": ["Not on the map yet"],
                                   "holes": [{"n": i + 1, "par": p, "index": None, "path": []} for i, p in enumerate(new["par"])]})
    courses = {c["key"]: c for c in out["courses"]}
    for key, loop in extra.get("loops", {}).items():
        course = courses[key]
        if isinstance(loop.get("par"), list):
            for hole, value in zip(course["holes"], loop["par"]):
                hole["par"] = value
            course["notes"] = drop_notes(course.get("notes", []), par=True)
        if loop.get("index"):
            for hole, value in zip(course["holes"], loop["index"]):
                hole["index"] = value
            course["notes"] = drop_notes(course.get("notes", []), index=True)
        if loop.get("tees"):
            course["tees"] = [dict(t) for t in loop["tees"]]
        if loop.get("as18"):
            course["as18"] = {"play": list(loop["as18"]["play"]), "index": list(loop["as18"]["index"])}
    if extra.get("combos"):
        names = {c["key"]: c["name"] for c in out.get("combos", [])}
        made = {c["key"] for c in extra["combos"]}
        combos = [] if extra.get("onlyTheseCombos") else [c for c in out.get("combos", []) if c["key"] not in made]
        for combo in extra["combos"]:
            first, second = combo["loops"]
            combos.append({"key": combo["key"], "name": names.get(combo["key"]) or "%s + %s" % (
                courses[first].get("name") or first, courses[second].get("name") or second),
                "loops": combo["loops"], "index": combo["index"]})
        out["combos"] = combos
    combos = {c["key"]: c for c in out.get("combos", [])}
    for key, genders in extra.get("slope", {}).items():
        target = courses.get(key) or combos[key]
        target["slope"] = json.loads(json.dumps(genders))
    out["clubFile"] = extra["clubFile"]
    return out


def build_overlay(files, clubs, made):
    """{ format, made, clubs: { id: overlay } } for the club files that check out against the clubs (format 2) given, and
    what went wrong with the others."""
    flags, out = [], {}
    by_id = {c["id"]: c for c in clubs}
    for club_id, file in sorted(files.items()):
        if club_id not in by_id:
            flags.append("club file %s: no such club" % club_id)
            continue
        problems = check(file, by_id[club_id])
        if problems:
            flags += ["club file %s: %s" % (club_id, p) for p in problems]
            continue
        out[club_id] = overlay(file)
    return {"format": 1, "made": made, "clubs": out}, flags


def apply(clubs, files):
    """Merges the files into the clubs (format 2) that have one. Returns the clubs and what went wrong, per club."""
    flags = []
    by_id = {c["id"]: i for i, c in enumerate(clubs)}
    for club_id, file in files.items():
        if club_id not in by_id:
            flags.append("club file %s: no such club this week" % club_id)
            continue
        club = clubs[by_id[club_id]]
        problems = check(file, club)
        if problems:
            flags += ["club file %s: %s" % (club_id, p) for p in problems]
            continue
        clubs[by_id[club_id]] = merge(club, file)
    return clubs, flags


if __name__ == "__main__":
    # Merges the club files into a format-2 file that is already made (e.g. the published one, or the app's copy),
    # without fetching or cleaning anything: the quick way to try a club file in the app the same day.
    #   python3 -m golf.clubfiles <format-2 file in> <file out>
    import sys
    if sys.argv[1] == "--overlay":
        # python3 -m golf.clubfiles --overlay <folder of club files> <format-2 file> <out>
        import datetime
        folder, source, target = sys.argv[2], sys.argv[3], sys.argv[4]
        with open(source) as f:
            clubs = json.load(f)["clubs"]
        data, problems = build_overlay(load(folder), clubs, datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        for problem in problems:
            print(problem)
        with open(target, "w") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        print("%s: %d club files" % (target, len(data["clubs"])))
        sys.exit(1 if problems else 0)
    source, target = sys.argv[1], sys.argv[2]
    with open(source) as f:
        data = json.load(f)
    data["clubs"], problems = apply(data["clubs"], load())
    # Stamped now, so an app that already has the file takes this one as newer.
    import datetime
    data["made"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for problem in problems:
        print(problem)
    with open(target, "w") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print("%s: club files merged into %d clubs" % (target, sum(1 for c in data["clubs"] if "clubFile" in c)))
