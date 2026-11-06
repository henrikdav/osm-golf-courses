"""Builds the published files, under site/v3/: one per country (clubs, courses, holes with their number and line, greens;
stable club ids and course keys from golf/ids.py, carried week to week in registry/), countries.json listing them and the
report of what is mapped; and a small index page. Geography only: no par, hole index or other golf data.

    python3 build.py --fetch          # fetch every country from Overpass, then clean and write site/
    python3 build.py                  # clean what is already in raw/ (no network)
"""
import argparse
import datetime
import json
import os

from golf import report
from golf.clean import ATTRIBUTION, FORMAT, SOURCE, clean, country_file
from golf.countries import COUNTRIES
from golf.fetch import fetch
from golf.ids import assign, with_ids


def load(path):
    with open(path) as f:
        return json.load(f)["elements"]


def osm_base(raw_dir):
    """The oldest timestamp_osm_base of the four Overpass answers in raw_dir (when the data was current), or None."""
    stamps = []
    for name in ("outlines", "relations", "holes", "greens"):
        try:
            with open(os.path.join(raw_dir, name + ".json")) as f:
                stamp = (json.load(f).get("osm3s") or {}).get("timestamp_osm_base")
        except (OSError, ValueError):
            stamp = None
        if stamp:
            stamps.append(stamp)
    return min(stamps) if len(stamps) == 4 else None


def build(raw_root, out, do_fetch, registry_root="registry", reports_root="reports"):
    """The published files, under out/v3/: per country one file of geography (clubs, courses, holes with their number and
    line, greens, with the stable ids from the register, which is kept for next week), the list of them, and the report of
    what is mapped. Golf data (par, hole index, tees, slope) is not in them, and nothing of any club's own is merged in."""
    folder = os.path.join(out, "v3")
    os.makedirs(folder, exist_ok=True)
    os.makedirs(registry_root, exist_ok=True)
    reports, histories, listed = [], {}, []
    made = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for code, name, filename in COUNTRIES:
        raw = os.path.join(raw_root, code)
        if do_fetch:
            fetch(code, raw)
        outlines = load(os.path.join(raw, "outlines.json")) + load(os.path.join(raw, "relations.json"))
        clubs, counts = clean(outlines, load(os.path.join(raw, "holes.json")), load(os.path.join(raw, "greens.json")))
        register_path = os.path.join(registry_root, code + ".json")
        register = load_register(register_path)
        register, flags = assign(code, clubs, register)
        with open(register_path, "w") as f:
            json.dump(register, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        for flag in flags:
            print("%s: %s" % (code, flag), flush=True)
        stable = [with_ids(c) for c in clubs]
        data = country_file(code, name, stable, counts, made, osm_base(raw))
        path = os.path.join(folder, filename)
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        size = os.path.getsize(path)
        listed.append({"code": code, "name": name, "file": filename, "bytes": size, "made": made,
                       "clubs": counts["clubs"], "clubsWithCompleteCourse": counts["clubsWithCompleteCourse"]})
        print("%s: %s, %d kB" % (code, json.dumps(counts), round(size / 1000)), flush=True)

        # What is mapped and what is not, club by club, and the week's totals added to the country's history.
        rep = report.report(code, stable, made)
        with open(os.path.join(folder, "report-" + filename), "w") as f:
            json.dump(rep, f, ensure_ascii=False, separators=(",", ":"))
        histories[code] = report.add_to_history(os.path.join(reports_root, code + ".json"), rep)
        reports.append(rep)
        print("%s report: %s" % (code, json.dumps(rep["totals"])), flush=True)
    with open(os.path.join(folder, "report.html"), "w") as f:
        f.write(report.page(reports, histories))
    with open(os.path.join(folder, "countries.json"), "w") as f:
        json.dump({"format": FORMAT, "attribution": ATTRIBUTION, "source": SOURCE, "countries": listed}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out, "index.html"), "w") as f:
        rows = "".join('<li><a href="v3/%s">%s</a>: %d clubs, %d with a complete course</li>'
                       % (c["file"], c["name"], c["clubs"], c["clubsWithCompleteCourse"]) for c in listed)
        f.write('<!doctype html><meta charset="utf-8"><title>OSM golf courses</title>'
                '<h1>Golf courses from OpenStreetMap</h1><p>Where golf courses are: clubs, courses and holes (their numbers and lines), '
                'cleaned every week. Geography only; par, hole index and other golf data are not part of it. Made %s. '
                '<a href="v3/countries.json">countries.json</a> lists the files. '
                '<a href="v3/report.html">What is mapped</a>, club by club.</p><ul>%s</ul>'
                '<p>Data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>, '
                'available under the Open Database License (ODbL 1.0): <a href="https://opendatacommons.org/licenses/odbl/1-0/">'
                'opendatacommons.org/licenses/odbl/1-0</a>. '
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
    parser.add_argument("--reports", default="reports", help="where each country's weekly totals are kept")
    args = parser.parse_args()
    build(args.raw, args.out, args.fetch, args.registry, args.reports)
