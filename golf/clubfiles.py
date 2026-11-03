"""Club files: what OpenStreetMap can't say about a club, written by hand from the club's own scorecard (#2).

One file per club, clubs/<club id>.json, keyed by the club's stable id (format 2). It holds:
- loops: per course key, its ranking 1–9 (the order of its holes by difficulty), lengths per tee, and corrections
  to OSM's par (each with why);
- combos: the combinations the club plays, loops in order, and which loop takes the odd indexes;
- source: where it came from (the club's scorecard or slope tables, who wrote it down, when);
- slope: room for course and slope rating per tee and combination, filled in later.

The weekly run merges the files into format 2, as additions an older reader skips:
- a loop's holes get their par corrected and, as their index, the loop's ranking 1–9 (OSM's own index on a loop
  is often the first loop's, copied);
- a loop gets "tees": [{"name", "lengths": [m per hole]}];
- "combos" becomes the club's combinations only, each with "index": the 18 indexes (the odd loop's holes
  2 × rank − 1, the other's 2 × rank);
- the club gets "clubFile": the file's source.

check() says what is wrong with a file against the club's OSM data; a file with problems is not merged.

Never copied from other apps' or sites' databases.
"""
import json
import os

FIELDS = {"id", "name", "source", "loops", "combos", "slope"}


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
        if not course:
            problems.append("loop %s: no such course in OSM" % key)
            continue
        n = len(course["holes"])
        ranking = loop.get("ranking")
        if ranking is not None and sorted(ranking) != list(range(1, n + 1)):
            problems.append("loop %s: the ranking must hold 1–%d once each" % (key, n))
        for tee, lengths in loop.get("tees", {}).items():
            if len(lengths) != n or not all(isinstance(m, int) and m > 0 for m in lengths):
                problems.append("loop %s, tee %s: %d lengths in metres" % (key, tee, n))
        par = loop.get("par", {})
        if par and not loop.get("why"):
            problems.append("loop %s: a par correction says why" % key)
        for hole, value in par.items():
            if not hole.isdigit() or not 1 <= int(hole) <= n:
                problems.append("loop %s: no hole %s" % (key, hole))
            elif course["holes"][int(hole) - 1].get("par") == value:
                problems.append("loop %s, hole %s: OSM has par %d now, the correction can go" % (key, hole, value))
    for combo in file.get("combos", []):
        loops = combo.get("loops", [])
        if len(loops) != 2 or any(k not in file.get("loops", {}) or k not in courses for k in loops):
            problems.append("combination %s: two loops of this file and of OSM" % "+".join(loops))
        elif combo.get("odd") not in loops:
            problems.append("combination %s: odd must be one of its loops" % "+".join(loops))
        elif any(file["loops"][k].get("ranking") is None for k in loops):
            problems.append("combination %s: both loops need a ranking" % "+".join(loops))
    return problems


def merge(club, file):
    """The club's format-2 data with the file merged in (a new dict; the club is left as it was)."""
    out = json.loads(json.dumps(club))
    courses = {c["key"]: c for c in out.get("courses", [])}
    for key, loop in file.get("loops", {}).items():
        course = courses[key]
        corrected = set()
        for hole, value in loop.get("par", {}).items():
            course["holes"][int(hole) - 1]["par"] = value
            corrected.add(int(hole))
        if corrected:
            # The notes OSM's data gave on those holes (e.g. a length that doesn't fit the par) no longer hold.
            course["notes"] = [n for n in course.get("notes", []) if not any(n.startswith("Hole %d " % h) for h in corrected)]
        if loop.get("ranking"):
            for hole, rank in zip(course["holes"], loop["ranking"]):
                hole["index"] = rank
        if loop.get("tees"):
            course["tees"] = [{"name": name, "lengths": lengths} for name, lengths in loop["tees"].items()]
    if file.get("combos"):
        names = {c["key"]: c["name"] for c in out.get("combos", [])}
        combos = []
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
    out["clubFile"] = file["source"]
    return out


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
