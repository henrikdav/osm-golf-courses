"""Builds the published files: one per country, plus countries.json listing them, plus a small index page.

    python3 build.py --fetch          # fetch every country from Overpass, then clean and write site/
    python3 build.py                  # clean what is already in raw/ (no network)
"""
import argparse
import datetime
import json
import os

from golf.clean import ATTRIBUTION, FORMAT, clean, country_file
from golf.countries import COUNTRIES
from golf.fetch import fetch


def load(path):
    with open(path) as f:
        return json.load(f)["elements"]


def build(raw_root, out, do_fetch):
    os.makedirs(out, exist_ok=True)
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
    with open(os.path.join(out, "countries.json"), "w") as f:
        json.dump({"format": FORMAT, "attribution": ATTRIBUTION, "countries": listed}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out, "index.html"), "w") as f:
        rows = "".join('<li><a href="%s">%s</a>: %d clubs, %d with a complete course</li>'
                       % (c["file"], c["name"], c["clubs"], c["clubsWithCompleteCourse"]) for c in listed)
        f.write('<!doctype html><meta charset="utf-8"><title>OSM golf courses</title>'
                '<h1>Golf courses from OpenStreetMap</h1><p>Clubs, courses and holes, cleaned every week. '
                'Made %s. <a href="countries.json">countries.json</a> lists the files.</p><ul>%s</ul>'
                '<p>Data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>, '
                'available under the Open Database License (ODbL 1.0). '
                '<a href="https://github.com/henrikdav/osm-golf-courses">How it is made</a>.</p>' % (made, rows))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true", help="fetch from Overpass first")
    parser.add_argument("--raw", default="raw", help="where the raw answers are kept")
    parser.add_argument("--out", default="site", help="where the published files are written")
    args = parser.parse_args()
    build(args.raw, args.out, args.fetch)
