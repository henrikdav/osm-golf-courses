"""Fetches a country's golf data from OpenStreetMap through the Overpass API, in four large queries.

The Overpass server is shared and slow: about two minutes for Sweden in all, and it is often busy (429, 502–504),
so each query is retried with a pause. It turns away clients without a name of their own, so the requests say
who they are with this repository's address.
"""
import json
import os
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = "https://overpass-api.de/api/interpreter"
USER_AGENT = "osm-golf-courses (https://github.com/henrikdav/osm-golf-courses)"
BUSY = {429, 502, 503, 504}


def queries(code):
    area = 'area["ISO3166-1"="%s"][admin_level=2]->.c;' % code
    return {
        # Course outlines. Relations need their members' geometry, so "out geom" (not "out tags geom").
        "outlines": '[out:json][timeout:300];%sway[leisure=golf_course](area.c);out tags geom;' % area,
        "relations": '[out:json][timeout:300];%srelation[leisure=golf_course](area.c);out geom;' % area,
        # Each hole: a line from the back tee to the pin.
        "holes": '[out:json][timeout:300];%sway[golf=hole](area.c);out tags geom;' % area,
        # Greens and tees, for clubs whose holes aren't mapped.
        "greens": '[out:json][timeout:300];%s(way[golf=green](area.c);way[golf=tee](area.c););out tags center;' % area,
    }


def post(query):
    body = ("data=" + urllib.parse.quote(query, safe="-._~")).encode()
    request = urllib.request.Request(ENDPOINT, data=body, headers={
        "User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(request, timeout=400) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, b""
    except urllib.error.URLError as error:
        if not isinstance(error.reason, ssl.SSLError):
            raise
        return post_with_curl(body)
    except ssl.SSLError:
        return post_with_curl(body)


# Old Python builds (e.g. macOS's own 3.9) can't do TLS with the server: curl can.
def post_with_curl(body):
    out = subprocess.run(["curl", "-s", "-w", "\n%{http_code}", "-A", USER_AGENT, "--max-time", "400",
                          "-H", "Content-Type: application/x-www-form-urlencoded", "--data-binary", "@-", ENDPOINT],
                         input=body, capture_output=True, check=True).stdout
    payload, _, status = out.rpartition(b"\n")
    return int(status or 0), payload


def fetch(code, raw_dir, tries=6, pause=60):
    """Saves the country's four answers as JSON in raw_dir; returns their paths by name."""
    os.makedirs(raw_dir, exist_ok=True)
    paths = {}
    for name, query in queries(code).items():
        for attempt in range(1, tries + 1):
            status, payload = post(query)
            if status == 200:
                elements = json.loads(payload)["elements"]
                break
            print("%s %s: %s, try %d of %d" % (code, name, status, attempt, tries), flush=True)
            if status not in BUSY or attempt == tries:
                raise RuntimeError("Overpass answered %s for %s %s" % (status, code, name))
            time.sleep(pause)
        path = os.path.join(raw_dir, name + ".json")
        with open(path, "w") as f:
            json.dump({"elements": elements}, f)
        print("%s %s: %d elements" % (code, name, len(elements)), flush=True)
        paths[name] = path
    return paths
