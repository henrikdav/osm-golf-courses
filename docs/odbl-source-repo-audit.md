# Technical audit: ODbL and OpenStreetMap data architecture

**Repository examined:** `henrikdav/osm-golf-courses`, checkout at commit `2d77d09` (`main`, 2026-11-05).  
**Scope:** Technical data lineage and architecture only. This is not a legal opinion or a conclusion about ODbL compliance.

## 1. Executive summary

The published country files are primarily a transformed and filtered representation of OSM data. They retain substantial OSM-origin information: golf-course outlines and names, hole-way geometry, hole references, par and handicap tags, and mapped green locations. The cleaner groups and filters these objects, computes spatial summaries and quality indicators, and creates a useful golf-course-oriented structure. It is a domain-shaped model, but its core facts and entity membership are sourced from OSM rather than an independently assembled golf-course database.

Format 2 introduces locally generated identifiers, but it does not sever data lineage. Each published club still contains an explicit `osm` outline reference. The registry carries that reference and assigns the local `id` by exact OSM identity when possible, then by name or proximity when OSM identity changes. Course keys are normalized from course names, which are themselves generally obtained or inferred from OSM tags. Hole numbers are sourced from OSM `ref` tags, except where the cleaner renumbers 10–27 loops to 1–9. Combination keys and relationships are generated from those course keys.

At this checkout, the weekly workflow publishes OSM-derived files without the optional club overlay. However, Git history shows that earlier revisions merged club-file data into the published v2 file. This included scorecard-derived hole indexes, tee lengths, par corrections, new unmapped courses, selected loop combinations, and slope/course ratings. The current `clubs/` directory is ignored and not present in the checkout, but history contains club-file commits. An audit of only the current working tree would miss this prior publication state.

For Stroke Counter, Scenario A has concrete structural coupling: the private database uses the public dataset’s locally generated club IDs, course keys, and hole positions/numbers. The two files being loaded separately does not remove their semantic and referential dependency. Scenario B would materially reduce that coupling if its domain records use independently maintained IDs and facts, with OSM references kept in an optional mapping layer. It would still retain a geographic/entity association to OSM wherever it maps an independently sourced course to an OSM club or uses OSM geometry/discovery.

The repository evidence supports describing the current release as an OSM-derived database with a generated golf-domain schema, plus a distinct optional overlay mechanism. Whether a particular combined app, database, or distribution constitutes a derivative database or collective database requires specialist legal analysis of the actual use, distribution, provenance, and jurisdiction.

## 2. Repository and build-pipeline overview

### Pipeline

```text
GitHub Actions (Monday 02:00 UTC or manual)
  └─ unittest on saved fixtures
  └─ golf.fetch.fetch(country, raw/<code>/)
       └─ Overpass API: outlines, relations, holes, greens/tees
  └─ build.py
       ├─ golf.clean.clean(): assign holes spatially, group courses, filter and summarize
       ├─ format 1: OSM object IDs and positional combo references
       ├─ golf.ids.assign(): consult/update registry/<code>.json
       ├─ golf.ids.format2(): stable local club IDs, course keys, combo references
       ├─ optional clubfiles.apply() only when --clubs is explicitly supplied
       ├─ write country JSON, indexes and reports under site/
       └─ update reports history
  └─ check.py: compare with live GitHub Pages, reject >20% count drops
  └─ commit changed registry/reports; upload site/ artifact and deploy Pages
```

`golf/fetch.py` uses `https://overpass-api.de/api/interpreter` (constant `ENDPOINT`, lines 16–17) and issues four Overpass QL queries (lines 21–30), scoped to the ISO country area. It retrieves:

| Query/output | OSM selection and output |
|---|---|
| `outlines.json` | `way[leisure=golf_course]`, tags and geometry |
| `relations.json` | `relation[leisure=golf_course]`, relation member geometry |
| `holes.json` | `way[golf=hole]`, tags and geometry |
| `greens.json` | golf greens and tees, tags and centers |

Requests use a 300-second Overpass timeout, 400-second client timeout, retry busy responses (429, 502–504) up to six times with 60-second pauses, and identify the client with a repository URL. Python `urllib` is used, with curl fallback on TLS errors (`golf/fetch.py:34–79`). No other OSM endpoint or API is used by this build path. `golf.slope` and `tools/solve_calculator.py` concern third-party golf information, not OSM acquisition.

The scheduled workflow is weekly, every Monday at 02:00 UTC, and can also be run manually (`.github/workflows/publish.yml:7–10`). It runs tests, fetches and builds, compares with Pages, commits registry/report changes, and deploys when changed (`:31–48`). `check.py:17,60–67` rejects a country if club or complete-course counts fall below 80% of the prior published count and ignores the `made` timestamp when comparing club data. This is a plausibility safeguard, not a full raw-data snapshot/version-control system.

The tracked tree includes code, tests, `registry/SE.json`, workflow files, README and MIT `LICENSE`. `raw/` and `site/` are ignored by `.gitignore` and are present only as local ignored artifacts in this checkout; they are not tracked source snapshots. No `reports/` history file is tracked at this revision, although the workflow is designed to commit it. Consequently, the current checkout alone does not provide a versioned raw input snapshot with which to reproduce the checked-in local `site/` bytes. With the Overpass response for a given date, code, registry, and runtime available, the transformations are deterministic except for generated timestamps and external-service state. The local raw snapshot, registry revision, runtime invocation, and Pages artifact for a particular public release are not all preserved together here.

## 3. Data provenance table

The table describes current format 2 (`site/v2/sweden.json` in the ignored local checkout) and the generator. Its schema and current counts are observed local artifacts, not tracked release fixtures.

| Published field | Provenance/classification | Technical details and caveats |
|---|---|---|
| Top-level `format`, `country`, `name`, `made` | Generated by repository logic | Format constants; country metadata from `golf/countries.py`; UTC build time in `build.py:36,69`. |
| `attribution` | Manually specified constant | `golf/clean.py:24`; propagated into country files and indexes. |
| `counts` | Derived from OSM-derived output by repository logic | Counts clubs, courses, mapped greens and geometry-based assignment outcomes (`golf/clean.py:315–322`). |
| Format 1 club `id` | Direct OSM reference, reformatted | `way/<id>` or `relation/<id>` from the selected outline (`golf/clean.py:299–305`). |
| Format 2 club `id` | Generated by repository logic, indirectly OSM-linked | Sequential local ID like `se-0338`, retained by a registry whose primary identity lookup is the OSM ID and whose fallback uses same name or <=500 m (`golf/ids.py:44–79`). |
| Format 2 club `osm` | Direct OSM reference, reformatted | Copies the outline type and numeric OSM ID; emitted alongside local ID (`golf/ids.py:108–119`). |
| Club `name` | Directly copied/normalized from OSM | Outline `name` tag, trimmed; if absent/blank, generated fallback `Golf course` (`golf/clean.py:299`). |
| Club `lat`, `lng` | Derived from OSM geometry | Midpoint of outline geometry bounding box, rounded to six decimals; not necessarily a surveyed clubhouse point (`golf/clean.py:300–304`). |
| Club `bbox` | Derived from OSM geometry | Minimum/maximum outline latitude and longitude (`golf/clean.py:65–68, 300–304`). |
| Course `name` | Direct, reformatted, or generated from OSM tags/custom logic | Prefer hole tags `golf:course:name`, `course:name`, `golf:course`, `course`; otherwise strip trailing ref from hole `name`; unnamed 27-hole runs receive generated range labels; unnamed duplicate tracks may be labeled `Course 1/2` (`golf/clean.py:71–93, 199–223`). |
| Course `key` (v2) | Generated from course name; indirectly OSM-derived | Accent folding, lowercasing, punctuation/range normalization, and collision suffixes; registry persists keys by name (`golf/ids.py:33–41, 82–107`). `main` represents an unnamed only course. |
| Hole `n` | OSM-derived then possibly renumbered | OSM way `ref` parsed as an integer. For 1–27 runs, loops 10–18 and 19–27 are shifted to local 1–9 (`golf/clean.py:101–118, 151–167, 216–220`). |
| Hole `par` | Directly copied from OSM `par` tag, range-filtered | Kept only for values 3–6 with plausible-length thresholds declared in repository; else null (`golf/clean.py:26–28, 162–167`). No current overlay is applied in weekly publishing. |
| Hole `index` | Directly copied from OSM `handicap` tag, validated | Integer 1–18 or null (`golf/clean.py:162–167`). A unique-index check only emits a note; it does not substitute another source (`:193–195`). Historical overlay versions replaced or populated indexes from club scorecards. |
| Hole `path` | OSM geometry reformatted | Ordered coordinates from `golf=hole` way geometry, lat/lon pairs rounded to six decimal places. The code/doc describes direction as back tee to pin, but the repository does not independently verify that every mapper follows this orientation (`golf/clean.py:41–43, 121–130, 165–167`). |
| Course `complete` | Derived by repository logic | True if holes exist, all local numbers from 1 through max occur, and no duplicate remains; does not prove the real course is complete (`golf/clean.py:168–173`). |
| `holeCount` | Derived | Number of retained holes (`golf/clean.py:168–169,196`). |
| Course `notes` | Generated by repository logic from OSM fields/geometry | Missing/repeated/unnumbered holes, missing par, duplicate index, and path-length/par plausibility checks (`golf/clean.py:175–195`). These are quality flags, not independently verified facts. |
| `greens` | OSM center coordinates, filtered | For clubs with no grouped courses, outputs centers of OSM green ways; fetched tees are not emitted. Coordinates rounded to six decimals (`golf/fetch.py:30`; `golf/clean.py:286–309`). |
| Course-combination `key` | Generated from course keys | Concatenates ordered loop keys with `+` in format 2 (`golf/ids.py:120–124`). |
| Combination `name` | Generated from OSM-derived course labels and custom rules | All ordered pairs of named complete 9-hole loops are offered. Sequential number ranges receive range-style names; other pairs use loop labels (`golf/clean.py:226–256`). Not evidence that a club actually offers or plays every pairing. |
| Combination `loops` | Repository relationship over course keys | In format 2 references course keys; in format 1 the pair stores course-array indexes. Both are generated from qualifying loops. |
| `mapped` | Not present in current published data | `mapped:false` is only added for new unmapped courses by optional historical/current overlay code (`golf/clubfiles.py:222–231`). |
| `tees`, `slope`, `clubFile`, scorecard corrections | External/manual sources, optional overlay; absent from current weekly v2 build | Club files describe provenance and corrections; `golf.clubfiles` can join them. Weekly workflow calls `build.py --fetch` without `--clubs`, so these are not in its current published outputs (`build.py:63–67`, workflow `:33–34`). Historical commits show such fields were once merged. |

The current local v2 file has 542 clubs, 214 courses and 2,666 holes. Example `se-0338` is Malmö Burlöv Golfklubb, with `osm: way/73898411`, course keys `1-9`, `10-18`, `19-27`, and combination references such as `1-9+10-18`. The key and hole numbering are local schema decisions, but the record is still attached to an OSM outline and course/hole tags and geometry.

## 4. Identifier architecture

### Club identifiers

Format 1 identifies a club with its OSM outline ID (`way/<id>` or `relation/<id>`). Format 2 adds the local-looking identifier `se-####` and retains the current OSM outline as `osm`. The register `registry/SE.json` stores, for each local ID, the OSM reference, name, bounding-box midpoint coordinates, and course-name-to-key mapping.

`golf.ids.assign()` first matches exact OSM IDs. If an OSM ID is new, it searches IDs whose OSM object disappeared in this build; exactly one same-name or <=500 m candidate inherits the old local ID, while ambiguity causes a new ID and a flag (`golf/ids.py:49–79`). A missing OSM object does not delete its registry entry (`:110–111`). Thus `se-0338` is an identifier generated by this repository, but it is operationally a persistent identity wrapper around a record discovered and reconciled through OSM objects. It is not an opaque, independently curated golf-club identity: the fallback is heuristic and can misidentify nearby clubs or fail on splits/mergers.

### Course and hole identifiers

Courses have no independent OSM entity identifier in the published format. Their v2 `key` is scoped to the club and derived from the cleaner's course label, then persisted by the registry. For example `19-27` derives from the label `19–27`; `gamla-banan` derives from `Gamla Banan`; an unnamed sole course uses `main`. A key survives course renames when normalization produces the same key, and a stored `main` can be transferred when a sole unnamed course gains a name (`golf/ids.py:82–107`). This persistence depends on the prior registry and its matching club identity.

Holes have no stable identifier in the output. A hole is addressed by a course key plus local `n` (and an app can join on club ID/course key/hole number). It is derived from OSM way `ref`, sometimes shifted to a loop-local numbering. If a way changes `ref`, a duplicate is resolved, course grouping changes, or numbering shifts, the same physical hole may receive a different logical tuple; conversely a different mapped hole can occupy the same tuple in later versions.

### OSM object cardinality and change behavior

One selected outline way/relation yields one club record. Its holes are not referenced by OSM ID in output; geometry and selected tags of multiple OSM hole ways are consolidated into course/hole structures. One outline may contain several courses. A hole way is assigned to the smallest containing outline based on its midpoint, so nested outlines can change membership (`golf/clean.py:259–298`). OSM ways can be split or remapped, multiple ways with one reference may collapse to the longer line when pins are within 30 m, and two distant ways with duplicate numbering may be interpreted as different unnamed courses (`:101–148`). No hole-level OSM identifiers are retained. Relation members contribute outline geometry; the output preserves only the outline relation ID and calculated bounds, not member references.

If an outline changes from way to relation, the local club ID may persist through the registry's name/proximity fallback. If a course is renamed, keys may persist via normalization and registry handling. If a club splits or merges, the code flags ambiguous identity matches but still emits records with generated IDs. Hole identity has no comparable reconciliation registry.

Therefore `se-0338` and `19-27` are generated identifiers, but they function as references to OSM-derived entities in this data model. The former is explicitly paired with an OSM ID; the latter is a key for a course inferred from OSM tags/refs and held within that OSM-linked club. Neither is currently a wholly independent identifier layer.

## 5. Entity relationship overview

```text
OSM golf_course way/relation
  ├─ outline geometry → club bbox, midpoint location
  ├─ name tag → club name
  └─ contains (by hole-way midpoint; smallest containing outline wins)
       └─ OSM golf=hole ways
            ├─ ref → hole number → course grouping / loop-local number
            ├─ par → hole par
            ├─ handicap → hole index
            ├─ course/name tags → course grouping/name
            └─ geometry → ordered hole path and length checks

OSM golf=green/tee ways → center fetched; green center may appear for courses with no grouped holes

club record → one or more generated courses (each scoped to club)
club record → generated pairings among qualifying 9-hole courses
format 2 registry → local club ID + course key → generated combination keys
```

The published relation is club → courses → holes, with combinations referencing courses and each hole embedded by value rather than linked to an external hole table. Format 1 uses the OSM outline ID, course array positions, and hole numbers. Format 2 uses local club ID plus OSM ID, course key, and loop keys. Hole geometry has no backward OSM way reference. There are no external references for par/index fields.

The output is more organized and usable for golf scoring than raw OSM responses, but its course membership, mapped holes, names, par/index values and paths depend heavily on OSM data. It is a golf-domain-shaped transformed dataset, not a substantial independent golf-domain database assembled from separate source records. Repository-generated concepts include completeness, issue notes, area ownership, synthesized course/loop labels, stable key wrappers, and proposed combinations.

## 6. Source-to-output transformation analysis

`golf.clean.clean()` converts raw elements into output records. It converts way geometry and relation outer members to coordinate rings, rounds points to six decimal places, and uses ray-casting containment of each hole-way midpoint to choose an outline. For nested outlines, the smallest containing bounding-box area wins (`golf/clean.py:45–68,259–298`). It groups holes by course-name tags or by stripping the hole reference from a name (`:71–93,199–223`).

The transformation does not preserve the complete OSM object model. It drops OSM node/way/relation IDs for hole/green/tee objects, most tags, user/edit metadata, timestamps, version numbers, relation member structure, inner rings, and exact unrounded serialization. It keeps selected tags (`name`, course-name fields, `ref`, `par`, `handicap`) through their transformed values and retains hole path coordinates. For the outline, it does not publish the polygon itself—only a local OSM reference, its derived bbox/midpoint, name, and resulting child content. Green geometry is reduced to centers; tee centers are queried but discarded by current cleaning logic.

The cleaner adds inferred course grouping, local numbering, geometry-based duplicate suppression and twin-track splitting, completeness flags, plausibility notes, and potential course combinations. Combination generation enumerates ordered pairs of named, complete nine-hole loops; that is repository logic, not a direct OSM relation. Par is filtered using length plausibility thresholds but not replaced. `index` in this current published build is OSM `handicap`; a repeated or questionable index produces notes rather than independent enrichment.

The output can often be regenerated from a sufficiently complete copy of the queried OSM elements plus repository code and the right historical registry. It cannot be exactly regenerated from the tracked repository alone because raw Overpass responses are not versioned, current raw/site artifacts are ignored, and output includes `made` time. The v2 stable IDs additionally require the right registry revision. Some output fields (completeness, notes, coordinates, course labels/keys and combos) are deterministic transformations or generated structure, but are not independent source facts. Current independent data in the published country records is limited primarily to schema metadata, IDs/keys, aggregation rules and computed checks.

## 7. Current licensing and attribution implementation

Verified repository references:

- `README.md:148–153` states data is © OpenStreetMap contributors and available under ODbL 1.0; it calls the published files a derived database under the same licence and requests credit wherever shown.
- `golf/clean.py:24` places an attribution string in country data. `build.py:84–87` puts attribution in the format 1 and format 2 country indexes. `build.py:91–97` emits an HTML index with linked OpenStreetMap contributor attribution and ODbL reference.
- `LICENSE` is the MIT software license, not an ODbL text or separate data license. README distinguishes code MIT from data ODbL.
- Country JSON has a `made` timestamp; the index describes format and byte count. There is no dataset version/hash, pinned Overpass timestamp, or archived raw query response manifest in the tracked files examined.
- The weekly GitHub workflow keeps the registry and report totals in Git and publishes GitHub Pages. The actual JSON is generated at build time; `site/` is ignored and not committed in this checkout. No standalone download/reuse document beyond README was found.

Current country-level attribution is machine-readable and the site index displays linked credit. The repository does not establish how Stroke Counter renders the downloaded JSON or whether the required attribution is visible in the app in every relevant view. The repository also cannot show whether every historical Pages deployment or cached app dataset included attribution. A specialist should assess attribution placement, database notices, offer/source availability, licensing statements for derived output, and treatment in app distribution based on actual shipped product behavior.

### Relevant Git history

The commit history changes the factual picture over time:

- Commit `91a05e1` added club-file overlay support and documented scorecard-derived additions.
- Commits `52fcaff`, `f2a2840`, and `77d8711` added club-file data from app-entered/scanned scorecards and checked scorecard corrections.
- Commit `c7be19f` (2026-11-05) changed `build.py` so club files are merged only if `--clubs` is given; it states prior weekly publishing merged index, slope and combinations into format 2.
- Commit `cfe2288` removed the club files from the working repository and documented the overlay as separate data.
- Commit `7476633` explicitly documents that club data is never in published files. The current scheduled workflow runs `python build.py --fetch` without `--clubs`.

Thus current source configuration omits the overlay, but previous repository versions/build configuration did merge additional material into format 2. Git history confirms earlier club-file commits; current local filesystem and history do not by themselves prove the exact set of historical public deployment artifacts or their retention/accessibility. The earlier commit contents and any archived Pages artifacts should be included in a complete publication-history review.

## 8. Scenario A versus Scenario B

### Scenario A — current described app architecture

The public dataset contains OSM-derived club/course/hole records with stable local IDs and keys. The private golf database separately stores tee lengths, ratings, indexes, par, combinations, and corrections, but uses the public `id`, `key`, and hole number as join keys. At runtime the app forms a combined view and uses it for courses and scorecards.

Technically, the private store is structurally dependent on the public model's entity boundaries and identifiers: public club identity selects the private club record; a course key selects loop-specific fields; hole numbering aligns private values to embedded public holes. Changes to OSM or cleaner logic can affect resolution even if the private bytes remain separate. If OSM splitting, course-name changes, course grouping, loop numbering, or registry reconciliation changes, joins can fail or attach facts to the wrong course/hole. The persistent registry reduces routine ID churn but is an OSM-aware reconciliation mechanism, not independent provenance.

Runtime joining and physical file separation are relevant technical facts, but alone they do not establish independent databases. The meaningful relationship includes shared schema, keys, row alignment and use of combined results. The repository also has a direct overlay implementation (`golf.clubfiles.apply_overlay`, `:222–260`) and a build-time merge path (`build.py:63–67`); those mechanisms make a combined representation possible. Current scheduled publication does not invoke that merge.

### Scenario B — independent golf database plus OSM mapping layer

If club/course/hole entities and golf-specific facts are created, maintained and identified independently, their core records can exist without an OSM record. A separate mapping table can associate independent entities with OSM outlines/holes where needed for discovery, geographic display, or geometry. This materially reduces structural coupling: private course and hole references no longer depend on OSM-derived course grouping, keys, or numbering, and a missing or changed OSM feature need not redefine a golf-domain entity.

Residual linkage remains wherever the app uses OSM geometry, location, name, or discovery results; where the mapping layer identifies an OSM outline; where a private entity is matched to an OSM entity using the mapping; or where a display joins both sets to show a course. If the mapping table is populated by matching and storing OSM-derived identity/relationships, it remains an explicit OSM-linked layer. Independent identifiers alone do not remove that association, but can isolate it from the authoritative golf domain model. If private facts are actually copied or corrected from OSM, changing identifiers does not change those facts' provenance.

### What changes technically

| Concern | Scenario A | Scenario B |
|---|---|---|
| Club/course identity | Public local ID and OSM-derived course key are private DB keys | Independent IDs are authoritative; mapping to OSM stored separately |
| Hole alignment | Shared `n`/course structure | Independent hole ID/order; optional mapping records OSM way or spatial association |
| OSM edits | Can change public entity grouping and break/misroute joins | Can update/delete map references without necessarily changing golf records |
| Golf facts | Private data aligned to OSM schema; some facts also OSM-derived/public | Facts sourced and maintained independently, as stated in Scenario B |
| App result | Runtime combined golf-domain view | Runtime composition still possible, but distinct entity ownership and mapping boundary |

These are technical comparisons. Whether either architecture qualifies for a particular database-right/license treatment is a legal question.

## 9. Technical risks and uncertainties

1. **No tracked raw snapshot.** Current raw and output directories are ignored. Current Overpass data cannot be reconstructed exactly from this checkout, and live data changes.
2. **Identifier semantics.** Local-looking IDs are generated but anchored/reconciled through OSM. Course keys derive from OSM-derived labels. Hole number is not a stable entity ID.
3. **Heuristic identity and grouping.** Name/proximity matching, point-in-polygon membership, tag interpretation, duplicate suppression and 27-hole splitting can misclassify entities. Code emits flags for some ambiguities but not all.
4. **Source of index differs by time.** Current weekly output takes OSM `handicap`. Historical club-file overlays populated/overrode indexes from scorecards. Runtime/app data may have additional sources outside this repository.
5. **Historical publication state.** History confirms an earlier merge path and committed club data. Exact content of each deployment and whether any app version consumed those versions must be established externally.
6. **No Stroke Counter source or runtime implementation in this repository.** The app architecture in this audit section is based on the user-supplied context. This repository cannot verify app data files, join code, attribution UI, persistence, offline caches, or distribution packaging.
7. **External data provenance.** `golf.slope` documents extraction from club sites/federation calculators and source tracking, and `golf.from_app` documents scorecard scans. The actual private database and current source records are outside the present checkout.
8. **Contribution/transform source uncertainty.** OSM tags and geometry are treated as OSM-derived here; the repo does not establish the upstream mapper's original source, contributor authorization, or independent origin of individual facts.
9. **Output reduction.** Hole IDs and most raw tags/metadata are dropped. This makes the output less like a full OSM dump but does not erase its reliance on the selected OSM facts and relationships.

## 10. Recommendations for improving architectural separation

These are architecture recommendations, not legal conclusions or implemented changes:

1. Define an independent golf-domain schema with immutable IDs for club, course, loop and hole, each owned by the golf database. Do not make OSM-derived keys the primary or foreign keys for those records.
2. Maintain a separate mapping table with explicit source/type, e.g. `golf_hole_id ↔ OSM way ID`, confidence, method, reviewer, and observation/version time. Treat mapping as optional and replaceable; avoid making it the only route to retrieve core golf facts.
3. Record per-field provenance and revision metadata for par, index, tees, ratings, combinations, names, and geometry. Distinguish direct OSM values, club scorecard values, federation/club-site sources, and manual corrections.
4. Avoid using OSM course labels as the authoritative private course identity. Match OSM to independent course IDs through reviewable mappings; store human course names and official loop order as golf-domain data.
5. Preserve an audit trail for mapping changes and avoid silently copying public OSM identifiers into proprietary records as their only identifiers. If interoperability requires an OSM reference, make its purpose explicit.
6. Keep OSM-derived output and private golf records separate in generation and publication workflows. For current design, make the no-overlay publishing mode explicit in CI/release checks and preserve provenance/version metadata for the published OSM database.
7. Pin source snapshots or maintain dated raw extracts and build manifests where operationally appropriate, including Overpass query definitions and registry revision. This improves reproducibility and lets reviewers compare exact releases.
8. Review repository history and deployment artifacts for prior merged overlays. Decide whether historical public snapshots need continued hosting, correction, annotation, or removal only after qualified advice; this audit does not prescribe a legal remedy.
9. Independently verify product-level attribution and notices in Stroke Counter, including offline and cached data presentation. The repository only verifies attribution embedded in generated files and HTML index.

## 11. Questions requiring legal interpretation / specialist follow-up

An ODbL/database licensing specialist would need, at minimum:

- The actual Stroke Counter schema, private database contents, source records, provenance records, and representative app queries/screens showing how datasets are joined and used.
- Whether the private data is truly independently sourced field-by-field, including par/index corrections, course/loop structures and any information originally copied from OSM or this repository.
- Whether storing OSM references, mappings, derived keys, copied geometry, or combined runtime records constitutes a relevant derivative/produced/collective database relationship under the applicable terms and law.
- How the app distributes or makes available the OSM-derived database and any combined outputs, including offline caches, exports, backups, APIs, and user-generated contributions.
- Which exact public dataset versions were published or downloaded historically, especially versions when overlays were merged; whether those versions remain accessible or in app caches.
- The intended commercial and distribution model, attribution surfaces, notices, source access, and any offer/share-alike mechanisms that may apply.
- Whether OSM tags or golf-specific facts have independent sources and whether facts, database structure, and selection/arrangement are treated differently for the relevant rights analysis.
- Whether the current per-country files, overlay files, app database, and joined runtime result are separate databases, a combined database, or another legally relevant arrangement under the specific circumstances.

### Explicit answers to the audit questions

1. **Primarily transformed OSM or independent model?** Primarily a transformed OSM-derived database, organized into a golf-specific schema. It has meaningful generated structure but no substantial independent golf facts in current weekly outputs.
2. **Which identifiers are OSM-based?** Format 1 club IDs are direct OSM IDs. Format 2 `osm` is direct; `id` is custom but matched through OSM IDs and OSM-change heuristics. Course keys derive from names/grouping derived from OSM tags. Hole numbers derive from OSM `ref` with loop renumbering. Combination keys derive from course keys.
3. **Does current identifier model make private data structurally dependent?** Yes, as described: the private records use public club/course/hole join fields and boundaries. Separate files do not remove that relationship.
4. **Would independent IDs materially change it?** Yes, if those IDs are authoritative and golf records can function independently. A separate OSM mapping still preserves geographic/entity linkage where used.
5. **Clearly OSM-derived fields?** `osm`, format 1 club `id`, club name, outline-derived bbox/location, hole path, hole `n` source, par, handicap/index, most course names, green centers, and course membership.
6. **Independently generated/manually maintained?** Local club IDs and keys, geometry assignment, grouping/numbering heuristics, completeness, notes, counts, pairings/combination names and keys, schema/version/time/attribution. Current published output has no club-entered tee lengths or slope. The repository's optional overlays and historical versions include manually/external-source data.
7. **Systematic extraction/enrichment beyond display/mapping?** Yes, systematic Overpass extraction of all selected country golf-course outlines, hole ways, greens and tees; geometry-based assignment, course splitting, tag interpretation, plausibility checks, loop/combination generation, registry reconciliation, and in prior revisions systematic overlay of scorecard/slope material. It is not merely a map display client.
8. **What improves independence?** Independent golf IDs and entity model; independent source/provenance per fact; a separately maintained, optional OSM mapping layer; no OSM-derived identifiers as private primary keys; reproducible and distinct build/distribution boundaries.
9. **What does counsel still need?** Actual app schema/runtime behavior, full private data and field provenance, distribution/caching details, exact historical merged releases, attribution/notice implementation, source terms and geography, plus a fact-specific assessment of database relationships and obligations.

---

**Evidence note:** File/line citations refer to the repository checkout described at the top. Current ignored `raw/` and `site/` samples were inspected for concrete examples; they are not tracked artifacts and may not correspond to the latest public Pages response. Historical conclusions are based on Git commits available in this clone.
