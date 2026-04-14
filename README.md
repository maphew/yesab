# YESAB Static Map Builders

This repo contains two Python scripts that build static map outputs from the zipped shapefiles in `data/`.

## Scripts

- `build_static_map.py`
  Builds a single self-contained HTML file.
- `build_static_map_split.py`
  Builds a multi-file static site with separate HTML, CSS, JS, and layer data files.

## Usage

Both scripts accept an optional output directory argument. If you omit it, they write to `./out`.

```powershell
python .\build_static_map.py
python .\build_static_map.py .\some-output-dir

python .\build_static_map_split.py
python .\build_static_map_split.py .\some-output-dir
```

## Output

Default output locations:

- `build_static_map.py` writes `out/yesab_map.html`
- `build_static_map_split.py` writes:
  - `out/index.html`
  - `out/app.css`
  - `out/app.js`
  - `out/data/`

The split builder removes and recreates its target output directory before writing files.
