# LPK Studio — Project Scope

> A web-based GUI wrapping the `steam-lpk-packager` pipeline. Makes it dead simple to discover, filter, and batch-package Live2D and Spine models from the Steam Workshop (Live2DViewerEX, App ID: 616720).

---

## Workshop Catalog — Live Numbers

Queried 2026-07-03 via Steam Workshop browse scrape:

| Tag | Count |
|---|---|
| Live2D | **6,289** |
| Spine | **4,710** |
| **Total (all)** | **14,917** |

~74% of all items are Live2D or Spine tagged. There's a roughly **57% Live2D / 43% Spine split** in the tagged subset.

---

## Repo Restructuring

The existing Python CLI is the root of a repo people already know and link to. We keep that equity.

### New Structure

```
steam-lpk-packager/             ← same repo, same URL, same name
├── cli/                        ← was the old repo root (Python pipeline)
│   ├── process_batch2_safe.py
│   ├── batch_extract_models.py
│   ├── verify_spine_versions.py
│   ├── lpk2moc3-spine/         ← submodule stays here (update .gitmodules)
│   ├── packages/
│   ├── live2d_packages/
│   ├── spine_packages/
│   └── README.md               ← "see root README for GUI, this is the CLI"
├── server.js                   ← Express server
├── package.json                ← npm install && npm start
├── db/
│   └── catalog.sqlite          ← pre-built index, committed to repo
├── public/
│   ├── index.html
│   ├── app.js
│   └── style.css
└── README.md                   ← Updated root: describes LPK Studio GUI + CLI reference
```

**Migration notes:**
- Move all Python scripts + submodule under `cli/`
- Update `.gitmodules` to point `lpk2moc3-spine` submodule to `cli/lpk2moc3-spine`
- Node's `server.js` will reference `cli/process_batch2_safe.py` and `cli/batch_extract_models.py` via absolute path
- Output dirs (`live2d_packages/`, `spine_packages/`) can stay under `cli/` — server reads them from there

---

## Architecture Overview

**Stack**: Node.js (Express) + plain HTML/JS/CSS — no build step.

```
steam-lpk-packager/
├── server.js              # Express: API bridge + static file server + SSE
├── package.json           # npm install && npm start — done
├── db/
│   └── catalog.sqlite     # SQLite: pre-built model index, shipped with repo
├── public/
│   ├── index.html         # Single-page app shell
│   ├── app.js
│   └── style.css
└── cli/                   # Python pipeline (untouched, just relocated)
    └── ...
```

**Why Node stays as the server layer:**
- Zero new Python web dependencies
- `child_process` + SSE = native live log streaming to browser with no websocket lib
- `better-sqlite3` is fast, sync, zero-config for local SQLite
- `npm install && npm start` — one command

**Why Python stays:**
- `lpk2moc3-spine` decryption library is Python-only (no cross-platform Node port exists)
- The Node server **never touches LPK files** — it shells out to `python3 cli/process_batch2_safe.py` exactly as today
- The Python environment (Pillow, SteamCMD, FFmpeg) still needs to exist, but the GUI handles surfacing errors if it's missing

---

## Steam API Key

### Anyone Can Get One — Free, Instant

`IPublishedFileService/QueryFiles/v1` is the correct endpoint for paginated Workshop catalog browsing and it works with a **regular free Steam Web API key** — no publisher relationship, no Steamworks partner status needed.

**How to get one:**
1. Log in to [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)
2. Your Steam account must be non-limited (spent $5+ on Steam store)
3. Enter any domain name — `localhost` works fine for local tools
4. Copy the key — that's it

The key lives in a `.env` file the user creates after cloning. It never touches the codebase.

### Why Not Sequential ID Scanning?

Steam `publishedfileid` values are **globally incrementing across all of Steam** — not scoped per-app. ID `3,000,000` might be a CS2 skin, `3,000,001` a Garry's Mod map, `3,000,002` a Live2DViewerEX model — all interleaved. The IDs from ~2019 to now span 1–2 billion sequential values globally. To find all 14,917 Live2DViewerEX items by brute-force scan would require ~10–20 million API calls at a ~0.001% hit rate. Not viable.

### The Clean Approach: QueryFiles with Cursor Pagination

```
GET https://api.steampowered.com/IPublishedFileService/QueryFiles/v1/
  ?key=STEAM_API_KEY
  &appid=616720
  &query_type=1          ← ranked by most subscribed
  &numperpage=100
  &cursor=*              ← start; use next_cursor for subsequent pages
  &return_details=1      ← includes title, description, creator
  &return_tags=1         ← includes Live2D / Spine tags
  &return_previews=1     ← includes thumbnail URLs
  &return_vote_data=1    ← subscription counts
```

Walks all ~14,917 items in **~150 API calls**. Returns everything in one shot — IDs, titles, tags, thumbnails, file sizes, subscription counts. No HTML parsing, no fragility.

### .env Configuration

```
# .env (gitignored — user creates this after cloning)
STEAM_API_KEY=your_key_here
PORT=3000
```

`server.js` reads the key from `process.env.STEAM_API_KEY` via `dotenv`. If the key is missing, catalog sync and index refresh are disabled but the rest of the app (batch pipeline, package browser) still works.

### First-Run Onboarding

If no `.env` key is detected on startup, the Settings panel opens automatically with a prompt:

```
┌──────────────────────────────────────────────────────────┐
│  ⚙️  Setup — Steam API Key Required for Catalog Browser  │
│                                                          │
│  Get your free key at:                                   │
│  steamcommunity.com/dev/apikey  (any domain works)       │
│                                                          │
│  Steam API Key: [________________________________]       │
│                                                          │
│  [ Save & Test Connection ]   [ Skip — use batch only ]  │
└──────────────────────────────────────────────────────────┘
```

The server writes the key to `.env` on save. A test call to `GetSteamLevel` confirms the key is valid before proceeding.

---

## Phase 1: MVP — Batch UI

**Goal**: Replace the manual `.txt` batch file with a browser form.

### UI Layout

```
┌─────────────────────────────────────────────────────┐
│  LPK Studio                                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Paste Steam Workshop URLs (one per line):          │
│  ┌───────────────────────────────────────────────┐  │
│  │ https://steamcommunity.com/...?id=123456      │  │
│  │ https://steamcommunity.com/...?id=789012      │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  [ Run Report ]          [ Download & Package ]     │
│  (dry-run + size est.)   (live SSE log stream)      │
│                                                     │
├─────────────────────────────────────────────────────┤
│  ● LIVE PROGRESS                                    │
│  ┌───────────────────────────────────────────────┐  │
│  │ ✅ 123456 — "Uma Musume Trainer"               │  │
│  │    Live2D | 42.3 MB | AIRI-Ready              │  │
│  │ ⏳ 789012 — Downloading... [████░░░░] 45%     │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  Disk: [███████░░░] 287 GB free  ✅ Safe to proceed │
│                                                     │
│  [ 📦 Browse Packaged Models ]                      │
└─────────────────────────────────────────────────────┘
```

### Features
- **Textarea** — paste raw URLs or bare IDs, one per line
- **Run Report** — dry-run: queries Steam API for each ID, returns title/type/size/status table, disk space check
- **Download & Package** — spawns `python3 cli/process_batch2_safe.py`, streams stdout via SSE
- **Live log panel** — terminal-styled, color-coded output (green/yellow/red)
- **Disk gauge** — free space vs. estimated download size
- **Package browser** — reads `cli/live2d_packages/` + `cli/spine_packages/`, lists ZIPs with download buttons

### Express Endpoints (MVP)
```
POST /api/dry-run         → runs --dry-run, returns structured JSON
POST /api/process         → SSE stream of pipeline stdout
GET  /api/packages        → list all packaged ZIPs
GET  /api/packages/:file  → serve ZIP for download
GET  /api/disk-space      → free/used/total stats
```

---

## Phase 2: Catalog Browser

**Goal**: Browse all ~14,917 Workshop models in a local filterable UI — no downloads needed.

### Index Strategy
- Use `IPublishedFileService/QueryFiles/v1` with cursor pagination (requires free Steam API key)
- Walks all ~14,917 items in ~150 API calls — returns titles, tags, thumbnails, sizes, subscription counts all at once
- Upserts results into SQLite — additive, never destructive
- The pre-built catalog is **committed to the repo** so users get day-one value on `git clone` without running a sync

### Update Catalog Flow
- **"Refresh Index" button** in the Catalog UI
- Server queries `QueryFiles` sorted by `time_created` descending, walks pages until it hits an ID already in the database
- Only the diff (new items added since last sync) is fetched — a typical weekly refresh is 50–200 new items, ~2–5 API calls
- Additive updates only — existing fingerprint/compat data is never overwritten during a metadata refresh

### Optional: Auto-download newest on refresh
When refreshing the index, offer a checkbox: "Also download & package new items (compatible only)". Off by default. If enabled, new items pass through the fingerprinting step and get packaged if compatible.

### Catalog Database Schema

```sql
CREATE TABLE models (
  id              TEXT PRIMARY KEY,
  title           TEXT,
  description     TEXT,
  creator         TEXT,
  thumbnail_url   TEXT,
  thumbnail_local TEXT,           -- path to cached local copy
  file_size       INTEGER,        -- bytes
  tags            TEXT,           -- JSON array
  subscriptions   INTEGER,
  steam_type      TEXT,           -- "Live2D" | "Spine" | "Other"

  -- Fingerprinting (Phase 3 only)
  fingerprinted   INTEGER DEFAULT 0,
  cubism_version  TEXT,
  spine_version   TEXT,
  compatible      INTEGER,        -- 1=yes 0=no NULL=unknown
  compat_reason   TEXT,

  -- Status
  packaged        INTEGER DEFAULT 0,

  -- Timestamps
  created_at      INTEGER,
  updated_at      INTEGER,
  indexed_at      INTEGER
);
```

### Catalog Browser UI

```
┌──────────────────────────────────────────────────────────────┐
│  LPK Studio          [ Batch Input ]  [ Index ]  [ Settings ]│
├──────────────────┬───────────────────────────────────────────┤
│  FILTERS         │  14,917 models in catalog                 │
│                  │  Sort: [Most Subscribed ▾]  Page 1 / 150  │
│  Type            │  ──────────────────────────────────────── │
│  ☑ Live2D (6,289)│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐ │
│  ☑ Spine  (4,710)│  │thumb │  │thumb │  │thumb │  │thumb │ │
│  ☐ Other  (3,918)│  │      │  │      │  │      │  │      │ │
│                  │  │ Uma  │  │ Blue │  │ Miku │  │ ...  │ │
│  Compatibility   │  │  4.2 │  │  Arc │  │  Sp4 │  │  ❓  │ │
│  ☑ AIRI-Ready    │  │  ✅  │  │  ✅  │  │  ✅  │  │  ❓  │ │
│  ☐ Incompatible  │  └──────┘  └──────┘  └──────┘  └──────┘ │
│  ☑ Unknown       │                                           │
│                  │  [ ☐ Select All ]  [ Download Selected ]  │
│  Cubism Version  │  ──────────────────────────────────────── │
│  ☑ 3.x           │  100 shown / 14,917 total                 │
│  ☑ 4.x           │  [ ← ]  Page 1 of 150  [ → ]             │
│  ☑ 5.0–5.2       │                                           │
│  ☐ 5.3+          │                                           │
│  Spine Version   │                                           │
│  ☑ 4.x           │                                           │
│  ☐ 3.x           │                                           │
│  ☐ 2.x           │                                           │
│                  │                                           │
│  Status          │                                           │
│  ☐ Packaged      │                                           │
│  ☐ Not Packaged  │                                           │
└──────────────────┴───────────────────────────────────────────┘
```

### Express Endpoints (Catalog)
```
POST /api/catalog/sync      → QueryFiles cursor walk → upsert SQLite (requires API key)
GET  /api/catalog           → query catalog with filters + pagination
GET  /api/catalog/:id       → single model detail
GET  /api/catalog/stats     → counts by type/compat/status
GET  /api/settings          → return current config (key presence, paths)
POST /api/settings          → save API key to .env, validate with test call
```

---

## Phase 3: Fingerprinting (Index Mode)

**Goal**: Download → inspect binary → record exact runtime version → update `compatible` flag.
**Storage**: Inspect-only. Temp download is deleted after fingerprinting.
**Decoupled**: Downloading for actual use is a separate user-driven action from the Catalog browser.

### Per-Model Process
1. SteamCMD download
2. Find `.lpk` in Workshop folder
3. Extract via `python3 cli/batch_extract_models.py`
4. Inspect binary:
   - `.moc3`: header contains Cubism version string in first ~50 bytes
   - `.skel` (binary): first 4 bytes = Spine version as little-endian float
   - `.skel` (JSON): `"spine"` key is a version string
5. Classify against AIRI compatibility rules
6. Cache thumbnail locally
7. Delete temp download
8. Write version + compat data to SQLite

### Compatibility Matrix

| Type | Version | Compatible with AIRI? |
|---|---|---|
| Live2D Cubism | 1.x, 2.x | ❌ No |
| Live2D Cubism | 3.x | ✅ Yes |
| Live2D Cubism | 4.x | ✅ Yes |
| Live2D Cubism | 5.0–5.2 | ✅ Yes |
| Live2D Cubism | 5.3+ | ❌ No (too new) |
| Spine | 2.x, 3.x | ❌ No |
| Spine | 4.x | ✅ Yes |

### Fingerprint Runner UI

```
┌──────────────────────────────────────────────────────────────┐
│  Index Mode                                                  │
│                                                              │
│  14,917 in catalog                                           │
│  ✅ 3,241 fingerprinted    ❓ 11,676 unknown                  │
│                                                              │
│  [▶ Start Fingerprinting]    [⏸ Pause]                      │
│                                                              │
│  Priority: [Most Subscribed ▾]                               │
│  ☐ Auto-download & package compatible models during index    │
│                                                              │
│  Progress ──────────────────────────── 21.7%                │
│  Est. remaining: ~18h 33m  (~1.8 models/min avg)            │
│                                                              │
│  Current: ID 2847193 — "Hana Summer Live2D"                 │
│  Phase: Extracting LPK... [████████░░░░] 60%               │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ ✅ 2847193 — Cubism 4.2.03 — COMPATIBLE              │   │
│  │ ❌ 2847105 — Spine 3.8.99  — INCOMPATIBLE            │   │
│  │ ✅ 2846991 — Cubism 3.3.00 — COMPATIBLE              │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Rate Estimates

| Operation | Avg time |
|---|---|
| SteamCMD download (~30MB avg) | 30–90s |
| LPK extraction | 5–15s |
| Binary inspection | ~1s |
| Cleanup | ~2s |
| **Per model total** | **~1–2 min** |

~14,900 models at 1.5 min avg = ~370 hours total indexing time. Run overnight prioritizing Most Subscribed. After 500–1,000 models, the catalog has better compatibility data than anything else available publicly.

---

## Shipped Index (Pre-built SQLite)

The repo will ship with a `db/catalog.sqlite` that includes:
- All ~14,917 model IDs, titles, thumbnails, file sizes, tags
- Metadata-only (no fingerprinting needed to use the catalog browser)
- Updated periodically before major releases
- Users can refresh their copy at any time via the "Update Index" button

This means **day-one value on first `git clone`** — full catalog browser works immediately without running anything.

---

## Implementation Roadmap

| Phase | Deliverable | Effort |
|---|---|---|
| **Repo restructure** | Move Python CLI to `cli/`, update `.gitmodules`, update paths | ~1 hr |
| **Phase 1 MVP** | Express server + textarea UI + SSE logs + dry-run table + package browser | ~2–3 days |
| **Phase 2 Catalog** | ID harvest + metadata fetch + SQLite + catalog browser + filters | ~1 week |
| **Ship initial index** | Run full crawl, commit `catalog.sqlite` to repo | ~1 day (mostly waiting) |
| **Phase 3 Fingerprinting** | Binary inspector + overnight runner + compat flags | Large (ongoing) |

---

## Open Questions

- **Thumbnail caching**: Cache all ~14k Steam preview images during catalog sync? Or lazy on first view? (lazy-load is much lighter for the initial commit)
- **Fingerprinting priority queue**: Most subscribed first, or user-defined custom order?
- **"Auto-download newest on refresh" toggle**: Off by default, user opt-in. Worth building in Phase 2?
- **LAN access**: Bind to `0.0.0.0` so other machines on the local network can hit the server?

---

## Prerequisites

### Required for all features
- **Node.js** 18+ 
- **Python 3.x** (LPK extraction — not optional, `lpk2moc3-spine` is Python-only)
- **SteamCMD** on PATH (for downloading Workshop items)
- **FFmpeg** on PATH (for audio conversion during extraction)
- **Pillow** — `pip install Pillow`

### Required for Catalog Browser + Index Refresh
- **Steam Web API Key** — free, get at [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)
  - Any non-limited Steam account qualifies ($5+ spent)
  - `localhost` is a valid domain for the registration form
  - Stored in `.env` — never committed to the repo (`.gitignore`d)

### npm packages
- `express` — web server
- `better-sqlite3` — SQLite driver
- `dotenv` — loads `STEAM_API_KEY` from `.env`

---

*Last updated: 2026-07-03 — Live count data: 6,289 Live2D / 4,710 Spine / 14,917 total*
*API strategy: `IPublishedFileService/QueryFiles/v1` with free user-level Steam API key — ~150 calls to index all 14,917 items*
