"""Slope tables: course rating and slope per tee, read from the slope tables a Swedish club publishes on its own website
(the Swedish Golf Federation's, the same layout at every club), into the club's club file (#2).

    python3 -m golf.slope --club se-0338 [--site https://…] [--pdf url …] [--osm v2/sweden.json] [--write]

Without --pdf it looks for them: the club's website (--site, else OSM's website tag on the club), and the pages it
links to about the course (bana, spela, slope, …) on the same site, for PDF links with "slope" in the address or the
link's text, any PDF on a page whose address says slope, and the federation's own file names (…_Men.pdf). A site that refuses automatic fetching (HTTP 403, 406, 429, a challenge page) is flagged, never worked
around: those clubs get theirs by hand (--pdf with a file or an address found otherwise).

Each table page gives the club, the course or combination ("1-18", "Blå&Gul", "Gamla Banan"), men or women, par, when
the course was rated, and per tee its name, course rating and slope. Pages are matched to the club's course keys by
name (a combination by its name or its loops' names, a course by its name, the club's only course whatever it is
called); what can't be matched is listed, not guessed. Checks: course rating 50–80, slope 55–155, par as the course
data has it.

With --write the result goes into clubs/<club>.json as "slope": { key: { "men" | "women": { par, rated,
tees: { name: { cr, slope } } } } }, with the tables' addresses under "source". A table is always for an 18-hole
round: on a 9- or 12-hole course it is the course played to 18 holes (Burlöv's 1-9: par 70 on a par-35 loop)."""
import argparse
import datetime
import html as htmllib
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from urllib.parse import urljoin, urlparse

from golf import clubfiles

AGENT = "osm-golf-courses slope reader (+https://github.com/henrikdav/osm-golf-courses)"
PAGE_WORDS = ("bana", "banan", "spela", "slope", "course", "scorekort", "banguide", "golfbana", "banor", "tee")
HEADER = re.compile(r"^(?:(?P<course>.+?)\s*·\s*)?(?P<gender>Herrar|Damer|Men|Women|Herr|Dam)\s*·\s*Par\s*(?P<par>\d+)\s*$", re.I)
RATED = re.compile(r"(?:Banan värderad|Rated)\s+(\d{4}-\d{2}-\d{2})", re.I)
DECIMAL = re.compile(r"^\d{2}\.\d$")
SLOPE = re.compile(r"^\d{2,3}$")


def fold(text):
    text = re.sub(r"[\u2010-\u2015&+/]", " ", text or "")   # dashes, "Blå&Gul": word breaks, not dropped
    text = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def fetch(url, binary=False):
    """(status, body) with curl (this Mac's Python can't always do TLS); body is bytes when binary."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
    try:
        out = subprocess.run(["curl", "-sL", "--max-time", "30", "-A", AGENT, "-o", path, "-w", "%{http_code}", url],
                             capture_output=True, text=True)
        status = int(out.stdout or 0)
        with open(path, "rb") as f:
            body = f.read()
    finally:
        os.unlink(path)
    return status, body if binary else body.decode("utf-8", "replace")


def blocked(status, body):
    if status in (401, 403, 406, 429, 503):
        return "HTTP %d" % status
    if isinstance(body, str) and re.search(r"cf-challenge|captcha|access denied|are you a robot", body[:5000], re.I):
        return "a challenge page"
    return None


def links(page_url, body):
    out = []
    for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", body, re.I | re.S):
        text = htmllib.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))
        out.append((urljoin(page_url, htmllib.unescape(m.group(1))), " ".join(text.split())))
    for m in re.finditer(r"(?:href|src|data-src)=[\"']([^\"']+\.pdf)[\"']", body, re.I):
        out.append((urljoin(page_url, htmllib.unescape(m.group(1))), ""))
    return out


def find_pdfs(site, max_pages=10):
    """The slope table PDFs a club's site links to, and what got in the way (a blocked site)."""
    status, body = fetch(site)
    why = blocked(status, body)
    if why or status >= 400 or not body:
        return [], "%s: %s" % (site, why or "HTTP %d" % status)
    host = urlparse(site).netloc.replace("www.", "")
    pages = [site]
    seen = {site}
    pdfs = []
    queue = [(site, body)]
    while queue:
        url, body = queue.pop(0)
        for target, text in links(url, body):
            words = fold(target + " " + text)
            if target.lower().split("?")[0].endswith(".pdf"):
                federation = re.search(r"_(men|women)(_klar)?\.pdf$", target.lower().split("?")[0])   # its own file names
                if ("slope" in words or "slope" in fold(url) or federation) and target not in pdfs:   # or on a slope page
                    pdfs.append(target)
                continue
            same = urlparse(target).netloc.replace("www.", "") == host
            if same and target not in seen and len(pages) < max_pages and any(w in words.split() or w in words for w in PAGE_WORDS):
                seen.add(target)
                status, page = fetch(target)
                why = blocked(status, page)
                if why:
                    return pdfs, "%s: %s" % (target, why)
                if status < 400:
                    pages.append(target)
                    queue.append((target, page))
    return pdfs, None


def pdf_pages(path):
    tool = os.path.join(os.path.dirname(__file__), "..", "tools", "pdftext.swift")
    out = subprocess.run(["swift", tool, path], capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(out.stderr.strip()[:300])
    return json.loads(out.stdout)


def read_page(lines):
    """One slope table page: { course, gender, par, rated, tees: [{ name, cr, slope }] }, or None.

    Read by where things are on the page (lines with x, y, w, h; y up), as the text's order mixes the columns: each
    tee's column starts with the label "Course Rating", its value on the same row to the right, and "Slope Rating"
    with its slope (55–155) on the row below; the tee's name is above the column, inside its width. A line naming
    several tees ("61 57 53 48") gives them to the columns under it in order. Anything that doesn't add up gives
    None, never a guess."""
    texts = [l["text"] for l in lines]
    header = next((HEADER.match(t) for t in texts if HEADER.match(t)), None)
    if not header:
        return None
    rated = next((RATED.search(t).group(1) for t in texts if RATED.search(t)), None)

    def right_of(label, pattern):
        """The value on the label's row (or in the label's own line) to its right."""
        inline = re.search(r"(\d{2,3}(?:\.\d)?)\s*$", label["text"])
        if inline:
            return inline.group(1), label["x"] + label["w"]
        row = [l for l in lines if pattern.match(l["text"]) and abs(l["y"] - label["y"]) < label["h"] * 0.6
               and 0 <= l["x"] - (label["x"] + label["w"]) < 120]
        if not row:
            return None, None
        best = min(row, key=lambda l: l["x"])
        return best["text"], best["x"] + best["w"]

    columns = []
    for label in lines:
        if not label["text"].lower().startswith("course rating"):
            continue
        cr, right = right_of(label, DECIMAL)
        slope_label = min((l for l in lines if l["text"].lower().startswith("slope rating") and abs(l["x"] - label["x"]) < 5
                           and 0 < label["y"] - l["y"] < label["h"] * 2.5), key=lambda l: label["y"] - l["y"], default=None)
        slope, right2 = right_of(slope_label, SLOPE) if slope_label else (None, None)
        if not cr or not slope or not 55 <= int(slope) <= 155:
            return None
        columns.append({"x": label["x"], "right": max(right, right2), "y": label["y"], "h": label["h"],
                        "cr": float(cr), "slope": int(slope), "name": None})
    if not columns:
        return None
    skip = re.compile(r"course rating|slope rating|handicap|spelhcp|banan värderad|·", re.I)
    for line in lines:
        if skip.search(line["text"]) or " - " in line["text"] or DECIMAL.match(line["text"]):
            continue
        under = sorted((c for c in columns if 0 < line["y"] - c["y"] < c["h"] * 4
                        and line["x"] < c["right"] and line["x"] + line["w"] > c["x"]), key=lambda c: c["x"])
        if not under:
            continue
        words = line["text"].split()
        if len(under) == 1:
            names = [line["text"]]
        elif len(words) == len(under):
            names = words
        else:
            return None
        for c, n in zip(under, names):
            if c["name"] is not None:
                return None
            c["name"] = n
    if any(c["name"] is None for c in columns):
        return None
    columns.sort(key=lambda c: (-round(c["y"] / 20), c["x"]))
    gender = "women" if header.group("gender").lower().startswith(("d", "w")) else "men"
    return {"course": (header.group("course") or "").strip(), "gender": gender, "par": int(header.group("par")), "rated": rated,
            "tees": [{"name": c["name"], "cr": c["cr"], "slope": c["slope"]} for c in columns]}


def course_keys(club):
    """What a table's course name may mean at this club: folded names → key, for courses and combinations."""
    out = {}
    courses = club.get("courses", [])
    for c in courses:
        if c.get("name"):
            out[fold(c["name"])] = c["key"]
        out[fold(c["key"])] = c["key"]
    names = {c["key"]: fold(c.get("name") or c["key"]) for c in courses}
    for combo in club.get("combos", []):
        out[fold(combo["name"])] = combo["key"]
        first, second = combo["loops"]
        for a in (names.get(first, first), fold(first)):
            for b in (names.get(second, second), fold(second)):
                out[fold(a + " " + b)] = combo["key"]
    return out


def match(table, club):
    keys = course_keys(club)
    name = re.sub(r"^(hal|holes|hole)\s+", "", fold(table["course"]))
    if name in keys:
        return keys[name]
    whole = [c for c in club.get("courses", []) if c.get("complete")]
    if len(whole) == 1 and not club.get("combos"):
        return whole[0]["key"]
    return None


def par_of(club, key):
    courses = {c["key"]: c for c in club.get("courses", [])}
    combo = next((c for c in club.get("combos", []) if c["key"] == key), None)
    holes = [h for k in (combo["loops"] if combo else [key]) for h in courses.get(k, {}).get("holes", [])]
    pars = [h.get("par") for h in holes]
    return sum(pars) if holes and all(isinstance(p, int) for p in pars) else None, len(holes)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--club", required=True)
    parser.add_argument("--site", help="the club's website, when OSM has none")
    parser.add_argument("--pdf", nargs="*", help="slope table PDFs (addresses or files) instead of looking for them")
    parser.add_argument("--osm", default="site/v2/sweden.json", help="a format-2 country file")
    parser.add_argument("--osm-raw", default="raw/SE", help="the raw OSM answers, for the club's website tag")
    parser.add_argument("--clubs", default="clubs")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    club = next((c for c in json.load(open(args.osm))["clubs"] if c["id"] == args.club), None)
    if not club:
        sys.exit("no club %s in %s" % (args.club, args.osm))
    own = os.path.join(args.clubs, args.club + ".json")
    if os.path.exists(own):   # its par corrections and combinations count, as they will once merged
        with open(own) as f:
            own_file = json.load(f)
        if not clubfiles.check(dict(own_file, slope={}), club):
            club = clubfiles.merge(club, own_file)
    pdfs, problem = args.pdf or [], None
    if not pdfs:
        site = args.site
        if not site:
            raw = [e for f in ("outlines.json", "relations.json") for e in json.load(open(os.path.join(args.osm_raw, f)))["elements"]]
            tags = next((e.get("tags", {}) for e in raw if "%s/%s" % (e["type"], e["id"]) == club["osm"]), {})
            site = tags.get("website") or tags.get("contact:website") or tags.get("url")
        if not site:
            sys.exit("%s %s: no website known; give --site or --pdf" % (args.club, club["name"]))
        pdfs, problem = find_pdfs(site)
    print("%s %s: %d slope table PDF(s)%s" % (args.club, club["name"], len(pdfs), "; flagged: " + problem if problem else ""))
    tables = []
    for pdf in pdfs:
        path = pdf
        if re.match(r"https?://", pdf):
            status, body = fetch(pdf, binary=True)
            why = blocked(status, body)
            if why or status >= 400 or not body.startswith(b"%PDF"):
                print("  flagged: %s: %s" % (pdf, why or "not a PDF (HTTP %d)" % status))
                continue
            fd, path = tempfile.mkstemp(suffix=".pdf")
            os.write(fd, body)
            os.close(fd)
        for lines in pdf_pages(path):
            table = read_page(lines)
            if table:
                tables.append(dict(table, pdf=pdf))
    result, unmatched, problems = {}, [], []
    for t in tables:
        key = match(t, club)
        if not key:
            unmatched.append("%s (%s)" % (t["course"], t["gender"]))
            continue
        par, holes = par_of(club, key)
        if par is not None and par != t["par"] and holes == 18:
            problems.append("%s %s: par %d in the table, %d in the course data" % (t["course"], t["gender"], t["par"], par))
        for tee in t["tees"]:
            if not 50 <= tee["cr"] <= 80:
                problems.append("%s %s tee %s: course rating %.1f" % (t["course"], t["gender"], tee["name"], tee["cr"]))
        entry = {"par": t["par"], "rated": t["rated"], "tees": {x["name"]: {"cr": x["cr"], "slope": x["slope"]} for x in t["tees"]}}
        result.setdefault(key, {})[t["gender"]] = entry
        print("  %-14s %-5s par %d, rated %s: %s" % (key, t["gender"], t["par"], t["rated"],
                                                     ", ".join("%s %.1f/%d" % (x["name"], x["cr"], x["slope"]) for x in t["tees"])))
    for u in unmatched:
        print("  not matched to a course: %s" % u)
    for p in problems:
        print("  problem: %s" % p)
    if args.write and result and not problems:
        path = os.path.join(args.clubs, args.club + ".json")
        file = json.load(open(path)) if os.path.exists(path) else {"id": args.club, "name": club["name"], "loops": {}}
        for key, genders in result.items():   # added to what the file has: one run may read one course's tables
            file.setdefault("slope", {}).setdefault(key, {}).update(genders)
        known = file.setdefault("source", {}).get("slope", {}).get("tables", [])
        file["source"]["slope"] = {"tables": sorted(set(known) | {t["pdf"] for t in tables if match(t, club)}),
                                   "read": datetime.date.today().isoformat()}
        with open(path, "w") as f:
            json.dump(file, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print("  written: %s" % path)
    elif args.write:
        print("  not written: %s" % ("problems" if problems else "nothing read"))


if __name__ == "__main__":
    main()
