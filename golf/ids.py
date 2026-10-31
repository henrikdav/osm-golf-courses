"""Stable ids for clubs and keys for their courses and loops (format 2).

OpenStreetMap ids change, most often when someone turns a club's outline from a simple line (`way`) into a combined
area (`relation`). An app that keeps a player's tees, lengths and corrections per club and course must not lose them
then, so every club gets an id of our own ("se-0042") and every course or loop a key within its club ("1-9",
"gamla-banan"). Both are kept in a register in this repo (registry/<country>.json, in git) and carried from week to
week:

- a club whose OSM id is in the register keeps its id;
- a club with a new OSM id takes the id of a club that disappeared this week, if exactly one has the same name or lies
  within 500 m; two or more such clubs (a club split or merged) are flagged instead of guessed, and it gets a new id;
- anything else gets the next free id.

A course's key comes from its name (lower case, no accents, words joined by "-": "Pay & Play" → "pay-play",
"1–9" → "1-9"); a club's only course, with no name, is "main". A key once given to a course stays with that name,
so the register also keeps the keys; a course renamed so that its key stays the same ("Holes 1–9" → "1–9") keeps it. Pure: no files or network here; build.py reads and writes the register.
"""
import re
import unicodedata

from golf.clean import meters

MOVED = 500   # meters: a club with a new OSM id within this of one that disappeared is taken to be the same club


def fold(text):
    """Lower case, without accents: "Malmö Burlöv" → "malmo burlov"."""
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").lower().strip()


def course_key(name):
    """A course's key from its name: "Gamla Banan" → "gamla-banan", "10–18" (or "Holes 10–18") → "10-18", None → "main"."""
    if not name:
        return "main"
    text = fold(name).replace("&", " ")
    text = re.sub(r"^(holes|hal)\s+(?=\d)", "", text)
    text = text.replace("–", "-")
    words = re.findall(r"\d+-\d+|[a-z0-9]+", text)
    return "-".join(words) or "course"


def assign(country, clubs, register):
    """Gives each club its id and each course its key, in place, and returns the updated register and what needs a
    look. `register` is {"next": n, "clubs": {id: {"osm", "name", "lat", "lng", "keys": {course name: key}}}}."""
    entries = {k: dict(v, keys=dict(v.get("keys", {}))) for k, v in register.get("clubs", {}).items()}
    next_number = register.get("next", 1)
    by_osm = {v["osm"]: k for k, v in entries.items()}
    present = {c["id"] for c in clubs}
    gone = {k for k, v in entries.items() if v["osm"] not in present}
    flags = []

    def new_id():
        nonlocal next_number
        made = "%s-%04d" % (country.lower(), next_number)
        next_number += 1
        return made

    # Keep the order stable: clubs already known first, so a new club never takes an id that a known one needs.
    for club in sorted(clubs, key=lambda c: (c["id"] not in by_osm, fold(c["name"]), c["id"])):
        osm = club["id"]
        if osm in by_osm:
            cid = by_osm[osm]
        else:
            candidates = [k for k in gone
                          if fold(entries[k]["name"]) == fold(club["name"])
                          or meters((entries[k]["lat"], entries[k]["lng"]), (club["lat"], club["lng"])) <= MOVED]
            if len(candidates) == 1:
                cid = candidates[0]
                gone.discard(cid)
                flags.append("%s: %s is now %s (was %s)" % (cid, club["name"], osm, entries[cid]["osm"]))
            else:
                cid = new_id()
                if candidates:
                    flags.append("%s: %s (%s) could be any of %s; given a new id"
                                 % (cid, club["name"], osm, ", ".join(sorted(candidates))))
        entry = entries.setdefault(cid, {"keys": {}})
        entry.update(osm=osm, name=club["name"], lat=club["lat"], lng=club["lng"])
        keys = entry["keys"]
        used = set(keys.values())
        names_now = {c["name"] or "" for c in club["courses"]}
        for course in club["courses"]:
            name = course["name"] or ""
            if name not in keys:
                base = course_key(course["name"])
                # Renamed, with the same key: it is the same course ("Holes 1–9" → "1–9").
                renamed = next((old for old, k in keys.items() if k == base and old not in names_now), None)
                if renamed is not None:
                    del keys[renamed]
                    keys[name] = base
                    course["key"] = base
                    continue
                key = base
                n = 2
                while key in used:
                    key = "%s-%d" % (base, n)
                    n += 1
                keys[name] = key
                used.add(key)
            course["key"] = keys[name]
        club["osm"] = osm
        club["id"] = cid
    for k in sorted(gone):
        flags.append("%s: %s (%s) is gone from OpenStreetMap; its id is kept" % (k, entries[k]["name"], entries[k]["osm"]))
    return {"next": next_number, "clubs": dict(sorted(entries.items()))}, flags


def format2(club):
    """A club as format 2 has it: the stable id with the OSM id beside it, a key on every course, and combinations
    naming the keys of their loops (every pair until the club's own data says which are played)."""
    out = {"id": club["id"], "osm": club["osm"]}
    out.update({k: v for k, v in club.items() if k not in ("id", "osm", "combos")})
    if club.get("combos"):
        courses = club["courses"]
        out["combos"] = [{"key": "%s+%s" % (courses[a]["key"], courses[b]["key"]), "name": combo["name"],
                          "loops": [courses[a]["key"], courses[b]["key"]]}
                         for combo in club["combos"] for a, b in [combo["courses"]]]
    return out
