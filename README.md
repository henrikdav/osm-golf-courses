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

## How it is cleaned

`golf/clean.py`. A club's holes are the `golf=hole` lines inside its `leisure=golf_course` outline (the smallest one
when outlines nest). Clubs map several courses in different ways, and each is handled:

| Mapped as | Example | Becomes |
| --- | --- | --- |
| Every hole numbered once | Vellinge GK | one course |
| A course name on each hole (`golf:course:name`, `course:name`, `course`) | Bokskogen: Gamla Banan, Kungsbanan | a course per name |
| The loop in the hole's own name, "Blå 1" | Örestad: Blå, Gul, Röd, Pay & Play | a course per loop |
| Holes 1–27 in one run | Malmö Burlöv | three 9-hole loops |
| No names, every number twice, far apart | Båstad | two courses, split by which tee follows which green |
| One number twice at one spot | Landeryd | one hole (the longer line, from the back tee) |

Named 9-hole loops are offered two by two for 18 holes (`combos`). Each course is checked: numbering, par 3–6,
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
