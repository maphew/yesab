# YESAB Static Map Builders

This repo contains scripts for:

- downloading the YESAB shapefile archive
- caching the YESAB registry API in year buckets
- building static map outputs from the zipped shapefiles in `data/`

## Scripts

- `dnld-yesab-project-map-file.py`
  Downloads `all.zip` only when the remote file changed.
- `cache_yesab_api.py`
  Caches YESAB API project records into local year-bucket JSON files and writes a merged dataset.
- `build_static_map.py`
  Builds a single self-contained HTML file.
- `build_static_map_split.py`
  Builds a multi-file static site with separate HTML, CSS, JS, and layer data files.

## Usage

Both scripts accept an optional output directory argument. If you omit it, they write to `./out`.

```powershell
python .\dnld-yesab-project-map-file.py

python .\cache_yesab_api.py
python .\cache_yesab_api.py --force
python .\cache_yesab_api.py --start-year 2024 --end-year 2025 --force
python .\cache_yesab_api.py --years 2022 2023 2024 --force

python .\build_static_map.py
python .\build_static_map.py .\some-output-dir

python .\build_static_map_split.py
python .\build_static_map_split.py .\some-output-dir
```

## Output

Default output locations:

- `dnld-yesab-project-map-file.py` writes:
  - `data/yesab_all.zip`
  - `data/yesab_all_zip.state.json`
- `cache_yesab_api.py` writes:
  - `data/api/buckets/projects_<start>-<end>.json`
  - `data/api/projects_merged.json`
  - `data/api/state.json`
- `build_static_map.py` writes `out/yesab_map.html`
- `build_static_map_split.py` writes:
  - `out/index.html`
  - `out/app.css`
  - `out/app.js`
  - `out/data/`

The split builder removes and recreates its target output directory before writing files.

## API Cache Behavior

`cache_yesab_api.py` defaults to refreshing only recent "hot" buckets:

- previous two years as one bucket
- current year as one bucket

Older cache buckets stay on disk until you explicitly refresh them with `--force`.
This keeps the sync logic simple while still updating the projects most likely to change.
