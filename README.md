# Golf courses from OpenStreetMap

Clubs, courses and holes from [OpenStreetMap](https://www.openstreetmap.org), cleaned every week and published as
one JSON file per country, for golf apps that want course data at once instead of querying Overpass themselves.

- **Countries:** <https://henrikdav.github.io/osm-golf-courses/countries.json>
- **Sweden:** <https://henrikdav.github.io/osm-golf-courses/sweden.json>

## What a country's file holds

```jsonc
{
  "format": 1,                       // a new number means an incompatible change
  "country": "SE", "name": "Sweden",
  "made": "2026-10-24T20:00:00Z",
  "attribution": "© OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)",
  "counts": { "clubs": 542, "clubsWithCompleteCourse": 107, "complete9or18": 125, … },
  "clubs": [{
    "id": "way/23727737",            // the OpenStreetMap outline
    "name": "Bokskogens Golfklubb",
    "lat": 55.55, "lng": 13.24, "bbox": [south, west, north, east],
    "courses": [{
      "name": "Gamla Banan",         // null for a club's only course
      "complete": true,              // every hole once, numbered from 1 without gaps
      "holeCount": 18,               // a complete 12-hole course is complete too: the app judges if that's all
      "notes": [],                   // what looks wrong, e.g. "Holes missing: 4", "Hole 2 is 309 m for par 5"
      "holes": [{ "n": 1, "par": 4, "index": 7, "path": [[lat, lng], …] }]   // back tee → pin
    }],
    "combos": [{ "name": "Blå + Gul", "courses": [0, 1] }],   // two 9-hole loops as 18; the second becomes 10–18
    "greens": [[lat, lng], …]        // only for a club whose holes aren't mapped
  }]
}
```

Every club outline is kept, also without holes, so an app can tell "not mapped yet" from "not there".

## Format 2: stable ids and keys

The same clubs in format 2, beside format 1 until the apps have moved over:

- **Countries:** <https://henrikdav.github.io/osm-golf-courses/v2/countries.json>
- **Sweden:** <https://henrikdav.github.io/osm-golf-courses/v2/sweden.json>

```jsonc
{
  "format": 2, …,
  "clubs": [{
    "id": "se-0338",                 // our own, stable: kept when OpenStreetMap's id changes
    "osm": "way/73898411",           // the OpenStreetMap outline it is now
    "name": "Malmö Burlöv Golfklubb", …,
    "courses": [{ "key": "1-9", "name": "1–9", … }],   // key: stable within the club ("main" for an only course)
    "combos": [{ "key": "1-9+10-18", "name": "1–18", "loops": ["1-9", "10-18"] }]
  }]
}
```

An app that keeps a player's tees, lengths and corrections per club and course points at `id` and `key`, never at
OpenStreetMap's id or a place in a list. OpenStreetMap ids change, most often when an outline is redrawn from a
`way` into a `relation`. The ids and keys are kept in `registry/<country>.json` (committed back by the weekly run):

- a club whose OpenStreetMap id is in the register keeps its id;
- a club with a new OpenStreetMap id takes the id of a club gone that week if exactly one has the same name or lies
  within 500 m; when two could be meant (a club split or merged) it gets a new id and the run says so for a person to
  look at;
- a club gone keeps its id in the register, so it is the same club if it comes back;
- a course's key comes from its name (`gamla-banan`, `bla`, `pay-play`, `1-9`) and stays with it;
- a club's only course, unnamed until then (`main`), keeps its key when it is the one course that gets a name
  (The National's 18 holes named Lakes Course stay `main`); a course mapped later gets a key of its own.

Every pair of loops is offered as a combination until a club's own data says which are played.

### Club files: what OpenStreetMap can't say

A club file (`<club id>.json`) adds what OpenStreetMap has no way to hold (#2): how a club's 9-hole loops are combined,
the index, lengths per tee, par corrections, and slope and course rating. **The club files are not in this repository
and not in the published files.** They are separate data, kept privately by the app that uses them, apart from the OSM
database (OpenStreetMap's licence, ODbL, covers the OSM data and what is derived from it, not data that sits beside it).
This repository holds the OSM data, the code, the format and the checks; the files are joined to the OSM data by club id
and course key where they are used. **Club data is never put into the files published here**: no `clubFile`, index, tees or
slope in `v2/sweden.json`, and `build.py` merges club files only when given `--clubs`, which the weekly run does not.

Where a club file's data comes from: the best source is the club itself (its scorecard, slope tables or slope
calculator), and openly published data is fine too. Keep to what is lawful: nothing is taken from a source whose terms
forbid it, and requests follow the site's `robots.txt`. Each file says where its data came from and how it was checked
(`source`), and later players' corrections can come in the same way, after review.

The code (all in `golf/`):

- `golf.clubfiles` checks a file against a club's OSM data and makes an **overlay**, only what the file adds:
  `python3 -m golf.clubfiles --overlay <folder of club files> <a format-2 file> <out>`. The app joins an overlay to a
  club's data when it opens (`apply_overlay` is the same join). `build.py --clubs <folder>` merges the files into a
  format-2 file the old way, for trying one locally; the published files are made without.
- `golf.slope` reads a club's slope tables from its own site (`--club`), and finds out which clubs' sites have tables or
  the Swedish Golf Federation's calculator (`--all`, nothing read or written).
- `golf.from_app` makes a club file from a course scanned in the app.

A combination's index comes from its loops' rankings: one loop takes the odd indexes (2 × rank − 1), the other the
even ones. Which loop is odd is in the file (the first nine at Malmö Burlöv; the harder loop at some clubs). A file with
a problem (a ranking that isn't 1–9 once each, lengths that don't fit, a loop OSM doesn't have, a par correction
without why) is left out of the overlay and the tool says why.

## What the data has: the report

Every week the run also writes, per country, what each club has and lacks, by what a player gets when starting a
round there: name only, holes but no course whole, par (GPS and a score against par), index (net scoring), tees (the
full scorecard, from a club file). It shows where mapping or a club file pays most.

- **Page:** <https://henrikdav.github.io/osm-golf-courses/v2/report.html>, with the totals week by week
- **Data:** `v2/report-<country file>`, one row per club with its level and what it lacks
- **History:** `reports/<country>.json`, the totals of each week, committed back by the weekly run

## How it is cleaned

`golf/clean.py`. A club's holes are the `golf=hole` lines inside its `leisure=golf_course` outline (the smallest one
when outlines nest). Clubs map several courses in different ways, and each is handled:

| Mapped as | Example | Becomes |
| --- | --- | --- |
| Every hole numbered once | Vellinge GK | one course |
| A course name on each hole (`golf:course:name`, `course:name`, `course`) | Bokskogen: Gamla Banan, Kungsbanan | a course per name |
| The loop in the hole's own name, "Blå 1" | Örestad: Blå, Gul, Röd, Pay & Play | a course per loop |
| Holes 1–27 in one run | Malmö Burlöv | three 9-hole loops, 1–9, 10–18 and 19–27 |
| No names, every number twice, far apart | Båstad | two courses, split by which tee follows which green |
| One number twice at one spot | Landeryd | one hole (the longer line, from the back tee) |

Named 9-hole loops are offered two by two for 18 holes (`combos`). Numbered loops that follow on are named as the
club calls the round (1–9 then 10–18: "1–18"; 19–27 then 1–9: "19–09"), other pairs by both names ("Blå + Gul"). Each course is checked: numbering, par 3–6,
length against par, and a unique index. A course is complete when every hole is there once, numbered from 1 without
gaps, however many holes: 12 holes in a row may be a 12-hole course or the first 12 of 18 mapped, which only the
app (knowing the course) can tell. The word for hole is dropped from a course name taken from the hole's name
("Gamla banan hål 1" → Gamla banan).

## Running it

Python 3.9 or later, nothing to install.

```sh
python3 -m unittest -v        # the cleaning, on saved answers in tests/fixtures
python3 build.py --fetch      # fetch every country from Overpass (about two minutes for Sweden), write site/
python3 build.py              # clean what is already in raw/
python3 check.py              # compare site/ with what is published
```

The **Publish** workflow does this every Monday at 02:00 UTC, and by hand from the Actions tab. It publishes only
when something changed, and refuses when a country lost more than a fifth of its clubs or complete courses at once
(Overpass sometimes gives half answers). Add a country in `golf/countries.py`.

## Licence

- **The data** is © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) and available under the
  [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/). The files published here are a
  derived database under the same licence; credit OpenStreetMap wherever you show it.
- **The code** in this repository is under the MIT licence (`LICENSE`).
