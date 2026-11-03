"""A club file from a course entered in the Fairly app (Stroke Counter), e.g. from a scanned scorecard: its par,
hole index and lengths per tee become the club file's loops, so what one player scanned is there for everyone.

    python3 -m golf.from_app --data data.json --osm sweden.json --course <app course id> --club se-0381 \\
        --keys gul,bla [--new "Name"] [--by "Who"] [--source "the club's scorecard"]

--keys says which of the club's OSM courses the app course is, in order: one key for a course played alone (its
index is kept as the scorecard prints it), two for 9 + 9 holes played as 18 (each loop's ranking comes from the
index: the nine with the odd indexes ranks by (index + 1) / 2, the other by index / 2, and the pair is written as a
combination). --new adds a course OSM doesn't have yet, by that name, with the one key given.

The file is written to clubs/<club>.json, added to what is there (other loops and combinations kept). Par that
differs from OSM is written as a correction saying what OSM had. What it did and what looks odd (a tee whose
lengths are missing on some holes, an index that doesn't follow the odd/even rule) is printed, and nothing is
written when something is wrong: check it, then run golf.clubfiles' check through the weekly build or the tests.
"""
import argparse
import datetime
import json
import os
import sys

from golf.clubfiles import check


def app_course(data, course_id):
    """The app course's holes as the scorecard has them: par, index and lengths per tee, in hole order."""
    course = next((c for c in data["courses"] if c["id"] == course_id), None)
    if not course:
        sys.exit("no course %s in the app's data" % course_id)
    club = next(c for c in data["clubs"] if c["id"] == course["clubId"])
    shared = (data.get("shared", {}).get("clubs", {}) or {}).get(club.get("shared") or "")
    if course.get("shared"):
        combo = next((x for x in (shared or {}).get("combos", []) if x["key"] == course["shared"]), None)
        loops = combo["loops"] if combo else course["shared"].split("+")
        keys = ["%s:%d" % (k, h["n"]) for k in loops for h in next(c for c in shared["courses"] if c["key"] == k)["holes"]]
    else:
        keys = course.get("holes") or []
    index = course.get("index") or []
    holes = []
    for i, key in enumerate(keys):
        record = club.get("holes", {}).get(key, {})
        par = record.get("par")
        if par is None and shared and ":" in key:
            loop, n = key.split(":")
            osm = next((c for c in shared["courses"] if c["key"] == loop), None)
            par = osm["holes"][int(n) - 1].get("par") if osm else None
        lengths = {t["name"]: (record.get("tees", {}).get(t["name"]) or {}).get("length") for t in course["tees"]}
        holes.append({"par": par, "index": index[i] if i < len(index) else None, "lengths": lengths})
    return holes


def loop_from(holes, osm_course, key, new_name=None, alone=True):
    """A club file's loop from the app's holes for one OSM course (or a new one), and what to tell about it."""
    notes = []
    loop = {}
    pars = [h["par"] for h in holes]
    if new_name:
        loop["new"] = {"name": new_name, "par": pars}
    else:
        osm_pars = [h.get("par") for h in osm_course["holes"]]
        diff = {str(i + 1): p for i, (p, o) in enumerate(zip(pars, osm_pars)) if p is not None and p != o}
        if diff:
            loop["par"] = diff
            had = sorted({str(osm_pars[int(h) - 1]) for h in diff})
            loop["why"] = ("OSM has no par on these holes" if had == ["None"] else
                           "OSM has other par on holes %s than the scorecard" % ", ".join(diff))
            notes.append("%s: par from the scorecard on holes %s (OSM had %s)" % (key, ", ".join(diff), ", ".join(had)))
    index = [h["index"] for h in holes]
    if alone and all(isinstance(i, int) for i in index):
        loop["index"] = index
        if sorted(index) == list(range(1, len(index) + 1)):
            loop["ranking"] = index
        elif sorted(index) == list(range(2, 2 * len(index) + 1, 2)):
            loop["ranking"] = [i // 2 for i in index]
        elif sorted(index) == list(range(1, 2 * len(index), 2)):
            loop["ranking"] = [(i + 1) // 2 for i in index]
    tees = {}
    for name in holes[0]["lengths"]:
        lengths = [h["lengths"].get(name) for h in holes]
        if all(isinstance(m, int) and m > 0 for m in lengths):
            tees[name] = lengths
        else:
            notes.append("%s, tee %s: lengths missing on some holes, left out" % (key, name))
    if tees:
        loop["tees"] = tees
    return loop, notes


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", required=True, help="the app's data.json")
    parser.add_argument("--osm", required=True, help="a format-2 country file")
    parser.add_argument("--course", required=True, help="the app course's id")
    parser.add_argument("--club", required=True, help="the club's id in the course data")
    parser.add_argument("--keys", required=True, help="the OSM course keys it is, in order, comma-separated")
    parser.add_argument("--new", help="the name of a course OSM doesn't have yet")
    parser.add_argument("--by", default="", help="who scanned or wrote it down")
    parser.add_argument("--source", default="the club's scorecard, scanned in the Fairly app")
    parser.add_argument("--clubs", default="clubs")
    args = parser.parse_args()

    with open(args.data) as f:
        data = json.load(f)
    with open(args.osm) as f:
        osm = next((c for c in json.load(f)["clubs"] if c["id"] == args.club), None)
    if not osm:
        sys.exit("no club %s in %s" % (args.club, args.osm))
    holes = app_course(data, args.course)
    keys = args.keys.split(",")
    courses = {c["key"]: c for c in osm.get("courses", [])}
    path = os.path.join(args.clubs, args.club + ".json")
    file = {"id": args.club, "name": osm["name"], "source": {}, "loops": {}}
    if os.path.exists(path):
        with open(path) as f:
            file = json.load(f)
    notes = []
    if len(keys) == 1:
        loop, said = loop_from(holes, courses.get(keys[0]), keys[0], new_name=args.new)
        file["loops"][keys[0]] = dict(file["loops"].get(keys[0], {}), **loop)
        notes += said
    elif len(keys) == 2 and len(holes) % 2 == 0:
        half = len(holes) // 2
        parts = [holes[:half], holes[half:]]
        odd = [all(isinstance(h["index"], int) and h["index"] % 2 == 1 for h in part) for part in parts]
        even = [all(isinstance(h["index"], int) and h["index"] % 2 == 0 for h in part) for part in parts]
        if not ((odd[0] and even[1]) or (even[0] and odd[1])):
            sys.exit("the index doesn't split into an odd nine and an even nine: no rankings")
        for k, part, is_odd in zip(keys, parts, odd):
            loop, said = loop_from(part, courses.get(k), k, alone=False)
            loop["ranking"] = [(h["index"] + 1) // 2 if is_odd else h["index"] // 2 for h in part]
            file["loops"][k] = dict(file["loops"].get(k, {}), **loop)
            notes += said
        combo = {"loops": keys, "odd": keys[0] if odd[0] else keys[1]}
        file["combos"] = [c for c in file.get("combos", []) if c["loops"] != keys] + [combo]
    else:
        sys.exit("--keys: one course, or two loops for a course of 9 + 9 holes")
    file["source"] = {"what": args.source, "by": args.by,
                      "date": datetime.date.today().isoformat()} if not file.get("source") else file["source"]
    problems = check(file, osm)
    for note in notes:
        print("note:", note)
    if problems:
        for problem in problems:
            print("problem:", problem)
        sys.exit("not written")
    os.makedirs(args.clubs, exist_ok=True)
    with open(path, "w") as f:
        json.dump(file, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("written: %s (%s)" % (path, ", ".join(file["loops"])))


if __name__ == "__main__":
    main()
