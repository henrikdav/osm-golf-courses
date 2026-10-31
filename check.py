"""Before publishing: compares the new files with the ones published, country by country.

Fails (exit 1) when a country lost many clubs or complete courses at once: Overpass sometimes gives half or broken
answers, and a bad week must not replace good data. Says whether anything changed (ignoring the date), so an
unchanged week publishes nothing; in GitHub Actions as the output `changed`.

    python3 check.py --site site --published https://henrikdav.github.io/osm-golf-courses
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

DROP = 0.8   # less than 80 % of last week's clubs or complete courses: refuse


def published(url):
    """The published file as JSON, or None when there is none yet."""
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    except urllib.error.URLError:
        out = subprocess.run(["curl", "-s", "-f", url], capture_output=True)
        return json.loads(out.stdout) if out.returncode == 0 else None


def main(site, base):
    changed = False
    ok = True
    # Format 1 and format 2 (v2/) are checked alike; either changing publishes both.
    for folder in ("", "v2"):
        part_changed, part_ok = compare(os.path.join(site, folder), base.rstrip("/") + ("/" + folder if folder else ""))
        changed, ok = changed or part_changed, ok and part_ok
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("changed=%s\n" % ("true" if changed and ok else "false"))
    return 0 if ok else 1


def compare(site, base):
    with open(os.path.join(site, "countries.json")) as f:
        countries = json.load(f)["countries"]
    changed = False
    ok = True
    for c in countries:
        with open(os.path.join(site, c["file"])) as f:
            new = json.load(f)
        old = published(base + "/" + c["file"])
        if old is None:
            print("%s (format %s): nothing published yet" % (c["code"], new.get("format")))
            changed = True
            continue
        for key in ("clubs", "completeCourses"):
            before, now = old["counts"].get(key, 0), new["counts"].get(key, 0)
            if before and now < DROP * before:
                print("%s: %s fell from %d to %d; not publishing" % (c["code"], key, before, now))
                ok = False
        same = old.get("format") == new.get("format") and old["clubs"] == new["clubs"]
        print("%s%s: %s" % (c["code"], " (format %s)" % new.get("format"), "unchanged" if same else "changed"))
        changed = changed or not same
    return changed, ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="site")
    parser.add_argument("--published", default="https://henrikdav.github.io/osm-golf-courses")
    args = parser.parse_args()
    sys.exit(main(args.site, args.published))
