"""Builds the published files: one per country, plus countries.json listing them, plus a small index page; and the
same in format 2 under v2/ (stable club ids and course keys, golf/ids.py), carried week to week in registry/.

    python3 build.py --fetch          # fetch every country from Overpass, then clean and write site/
    python3 build.py                  # clean what is already in raw/ (no network)
"""
import argparse
import copy
import datetime
import json
import os

from golf.clean import ATTRIBUTION, FORMAT, clean, country_file
from golf.countries import COUNTRIES
from golf.fetch import fetch
from golf.ids import assign, format2

FORMAT_2 = 2


def load(path):
    with open(path) as f:
        return json.load(f)["elements"]


def build(raw_root, out, do_fetch, registry_root="registry"):
    os.makedirs(out, exist_ok=True)
    os.makedirs(os.path.join(out, "v2"), exist_ok=True)
    os.makedirs(registry_root, exist_ok=True)
    listed_2 = []
    made = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    listed = []
    for code, name, filename in COUNTRIES:
        raw = os.path.join(raw_root, code)
        if do_fetch:
            fetch(code, raw)
        outlines = load(os.path.join(raw, "outlines.json")) + load(os.path.join(raw, "relations.json"))
        clubs, counts = clean(outlines, load(os.path.join(raw, "holes.json")), load(os.path.join(raw, "greens.json")))
        data = country_file(code, name, clubs, counts, made)
        path = os.path.join(out, filename)
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        size = os.path.getsize(path)
        listed.append({"code": code, "name": name, "file": filename, "bytes": size, "made": made,
                       "clubs": counts["clubs"], "clubsWithCompleteCourse": counts["clubsWithCompleteCourse"]})
        print("%s: %s, %d kB" % (code, json.dumps(counts), round(size / 1000)), flush=True)

        # Format 2: the same clubs with stable ids and keys from the register, which is kept for next week.
        register_path = os.path.join(registry_root, code + ".json")
        register = load_register(register_path)
        clubs_2 = copy.deepcopy(clubs)
        register, flags = assign(code, clubs_2, register)
        with open(register_path, "w") as f:
            json.dump(register, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        for flag in flags:
            print("%s: %s" % (code, flag), flush=True)
        data_2 = dict(country_file(code, name, [format2(c) for c in clubs_2], counts, made), format=FORMAT_2)
        path_2 = os.path.join(out, "v2", filename)
        with open(path_2, "w") as f:
            json.dump(data_2, f, ensure_ascii=False, separators=(",", ":"))
        listed_2.append(dict(listed[-1], bytes=os.path.getsize(path_2)))
    with open(os.path.join(out, "countries.json"), "w") as f:
        json.dump({"format": FORMAT, "attribution": ATTRIBUTION, "countries": listed}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out, "v2", "countries.json"), "w") as f:
        json.dump({"format": FORMAT_2, "attribution": ATTRIBUTION, "countries": listed_2}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out, "index.html"), "w") as f:
        rows = "".join('<li><a href="%s">%s</a>: %d clubs, %d with a complete course</li>'
                       % (c["file"], c["name"], c["clubs"], c["clubsWithCompleteCourse"]) for c in listed)
        f.write('<!doctype html><meta charset="utf-8"><title>OSM golf courses</title>'
                '<h1>Golf courses from OpenStreetMap</h1><p>Clubs, courses and holes, cleaned every week. '
                'Made %s. <a href="countries.json">countries.json</a> lists the files.</p><ul>%s</ul>'
                '<p>Data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>, '
                'available under the Open Database License (ODbL 1.0). '
                '<a href="https://github.com/henrikdav/osm-golf-courses">How it is made</a>.</p>' % (made, rows))


def load_register(path):
    """The register of club ids and course keys, or an empty one the first time."""
    if not os.path.exists(path):
        return {"next": 1, "clubs": {}}
    with open(path) as f:
        return json.load(f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true", help="fetch from Overpass first")
    parser.add_argument("--raw", default="raw", help="where the raw answers are kept")
    parser.add_argument("--out", default="site", help="where the published files are written")
    parser.add_argument("--registry", default="registry", help="where the club ids and course keys are kept")
    args = parser.parse_args()
    build(args.raw, args.out, args.fetch, args.registry)
