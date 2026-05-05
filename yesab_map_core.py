"""Shared data-shaping helpers for the YESAB static map builders."""

from __future__ import annotations

import csv
import json
import math
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import compression.zstd as zstd

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
API_CACHE_FILE = DATA_DIR / "api" / "projects_merged.json.zst"
API_STATE_FILE = DATA_DIR / "api" / "state.json"
API_LOCATION_OVERRIDES_FILE = DATA_DIR / "api" / "location_overrides.csv"
ZIP_STATE_FILE = DATA_DIR / "yesab_all_zip.state.json"
PROJECT_MAP_PAGE_URL = "https://yesab.ca/project-map"
PROJECT_MAP_ARCHIVE_URL = (
    "https://yesab.ca/wp-content/plugins/yesab-map-wp-plugin/geojson/all.zip"
)
REGISTRY_FRONT_URL = "https://yesabregistry.ca/"
REGISTRY_API_URL = "https://yesabregistry.ca/api/integration/projects"
YST = timezone(timedelta(hours=-7), name="YST")

API_FALLBACK_LAYER_NAME = "API_Approximate_Points"
API_FALLBACK_LAYER_COLOR = "#0f766e"
BAD_COORDINATE_DISPLAY_LATITUDE = 65.0
BAD_COORDINATE_DISPLAY_LONGITUDE = -127.0
YUKON_LATITUDE_RANGE = (59.0, 70.5)
YUKON_LONGITUDE_RANGE = (-142.5, -123.0)
GENERIC_LONGITUDES = (-141.00001, -140.00001, -124.00001)
GRS80_A = 6378137.0
GRS80_INV_F = 298.257222101
YUKON_ALBERS_FALSE_EASTING = 500000.0
YUKON_ALBERS_FALSE_NORTHING = 500000.0
YUKON_ALBERS_CENTRAL_MERIDIAN = math.radians(-132.5)
YUKON_ALBERS_STANDARD_PARALLEL_1 = math.radians(61.66666666666666)
YUKON_ALBERS_STANDARD_PARALLEL_2 = math.radians(68.0)
YUKON_ALBERS_LATITUDE_OF_ORIGIN = math.radians(59.0)

LABEL_FIELDS = (
    "Prj_Name",
    "PROPERTY_N",
    "ProjectID",
    "Prj_ID",
    "YESAB_PROJ",
    "Number",
)

PROJECT_NUMBER_FIELDS = (
    "projectNumber",
    "ProjectID",
    "Prj_ID",
    "YESAB_PROJ",
    "Number",
)


def round_coord(value: float) -> float:
    """Round projected coordinates to a compact precision for browser delivery."""
    return round(value, 1)


def albers_q(phi: float, eccentricity: float) -> float:
    """Return the ellipsoidal q term used by Albers equal-area projection."""
    sin_phi = math.sin(phi)
    e_sin_phi = eccentricity * sin_phi
    return (1 - eccentricity**2) * (
        sin_phi / (1 - e_sin_phi * e_sin_phi)
        - (1 / (2 * eccentricity)) * math.log((1 - e_sin_phi) / (1 + e_sin_phi))
    )


def albers_m(phi: float, eccentricity: float) -> float:
    """Return the ellipsoidal m term used by Albers equal-area projection."""
    sin_phi = math.sin(phi)
    return math.cos(phi) / math.sqrt(1 - eccentricity**2 * sin_phi * sin_phi)


def project_lonlat_to_yukon_albers(longitude: float, latitude: float) -> list[float]:
    """Project WGS84/NAD83-style lon/lat to the Yukon Albers map coordinates."""
    flattening = 1 / GRS80_INV_F
    eccentricity = math.sqrt(2 * flattening - flattening * flattening)
    m1 = albers_m(YUKON_ALBERS_STANDARD_PARALLEL_1, eccentricity)
    m2 = albers_m(YUKON_ALBERS_STANDARD_PARALLEL_2, eccentricity)
    q0 = albers_q(YUKON_ALBERS_LATITUDE_OF_ORIGIN, eccentricity)
    q1 = albers_q(YUKON_ALBERS_STANDARD_PARALLEL_1, eccentricity)
    q2 = albers_q(YUKON_ALBERS_STANDARD_PARALLEL_2, eccentricity)
    q = albers_q(math.radians(latitude), eccentricity)
    n = (m1 * m1 - m2 * m2) / (q2 - q1)
    c = m1 * m1 + n * q1
    rho0 = GRS80_A * math.sqrt(c - n * q0) / n
    rho = GRS80_A * math.sqrt(max(0.0, c - n * q)) / n
    theta = n * (math.radians(longitude) - YUKON_ALBERS_CENTRAL_MERIDIAN)
    x = YUKON_ALBERS_FALSE_EASTING + rho * math.sin(theta)
    y = YUKON_ALBERS_FALSE_NORTHING + rho0 - rho * math.cos(theta)
    return [round_coord(x), round_coord(y)]


def decimal_places(value: float) -> int:
    """Return the number of decimal places needed to represent a coordinate."""
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    if "." not in text:
        return 0
    return len(text.split(".", maxsplit=1)[1])


def is_world_coordinate(latitude: float, longitude: float) -> bool:
    """Return true when the coordinate is valid lon/lat anywhere on earth."""
    return -90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0


def is_yukon_coordinate(latitude: float, longitude: float) -> bool:
    """Return true when the coordinate is inside a broad Yukon map range."""
    return (
        YUKON_LATITUDE_RANGE[0] <= latitude <= YUKON_LATITUDE_RANGE[1]
        and YUKON_LONGITUDE_RANGE[0] <= longitude <= YUKON_LONGITUDE_RANGE[1]
    )


def classify_api_coordinate(
    latitude: float, longitude: float, coordinate_count: int
) -> tuple[str, list[str]]:
    """Classify an API fallback coordinate for QA and post-processing."""
    if not is_world_coordinate(latitude, longitude):
        return "bad_coordinates", ["outside_world_range"]
    if not is_yukon_coordinate(latitude, longitude):
        return "bad_coordinates", ["outside_yukon_range"]

    flags: list[str] = []
    if coordinate_count >= 5:
        flags.append("repeated_coordinate_5plus")
    if any(abs(longitude - item) < 0.000001 for item in GENERIC_LONGITUDES):
        flags.append("sentinel_like_longitude")
    if (
        abs(latitude - round(latitude)) < 0.00011
        and abs(longitude - round(longitude)) < 0.00011
    ):
        flags.append("near_integer_coordinate")
    if flags:
        return "generic_coordinates", flags

    if decimal_places(latitude) <= 2 or decimal_places(longitude) <= 2:
        return "low_precision_coordinates", ["low_precision_2dp"]
    return "plausible_api_coordinates", []


def load_api_location_overrides() -> dict[tuple[str, str], tuple[float, float]]:
    """Load API coordinate overrides keyed by project number and project ID."""
    if not API_LOCATION_OVERRIDES_FILE.exists():
        return {}
    overrides: dict[tuple[str, str], tuple[float, float]] = {}
    with API_LOCATION_OVERRIDES_FILE.open(newline="", encoding="utf-8-sig") as handle:
        rows = (
            line
            for line in handle
            if line.strip() and not line.lstrip().startswith(("#", ";"))
        )
        for row in csv.DictReader(rows):
            project_number = (row.get("ProjectNumber") or "").strip()
            project_id = (row.get("ProjectID") or "").strip()
            if not project_number or not project_id:
                continue
            try:
                latitude = float((row.get("Replace_Lat") or "").strip())
                longitude = float((row.get("Replace_Long") or "").strip())
            except ValueError:
                continue
            overrides[(project_number, project_id)] = (latitude, longitude)
    return overrides


def clean_props(record: dict[str, str]) -> dict[str, str]:
    """Drop blank DBF fields and normalize whitespace in the remaining values."""
    cleaned: dict[str, str] = {}
    for key, value in record.items():
        text = value.strip()
        if not text:
            continue
        cleaned[key] = text
    return cleaned


def label_for(record: dict[str, str], fallback: str) -> str:
    """Choose a human-friendly feature label from the preferred attribute fields."""
    for field in LABEL_FIELDS:
        value = record.get(field, "").strip()
        if value:
            return value
    return fallback


def project_number_for(record: dict[str, str]) -> str:
    """Return the first available project-number style identifier from a feature record."""
    for field in PROJECT_NUMBER_FIELDS:
        value = record.get(field, "").strip()
        if value:
            return value
    return ""


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def format_yukon_time(value: str) -> str:
    """Convert ISO-8601 or RFC-1123 timestamps to Yukon Standard Time."""
    if not value:
        return ""
    parsed: datetime | None = None
    try:
        parsed = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S GMT").replace(
            tzinfo=UTC
        )
    except ValueError:
        pass
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(YST).strftime("%Y-%m-%d %H:%M YST")


def read_json_file(path: Path) -> dict[str, object]:
    """Return JSON content from ``path`` when present, otherwise an empty mapping."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_zstd_json_file(path: Path) -> dict[str, object]:
    """Return compressed JSON content from ``path`` when present, otherwise an empty mapping."""
    if not path.exists():
        return {}
    with zstd.open(path, "rt", encoding="utf-8") as handle:
        loaded = json.load(handle)
    return loaded if isinstance(loaded, dict) else {}


def load_source_info() -> dict[str, object]:
    """Return source links and currency dates embedded into the built page."""
    zip_state = read_json_file(ZIP_STATE_FILE)
    api_state = read_json_file(API_STATE_FILE)
    merged = api_state.get("merged", {}) if isinstance(api_state, dict) else {}
    return {
        "pageBuiltAt": format_yukon_time(utc_now_iso()),
        "shapefile": {
            "label": "YESAB Project Map File",
            "pageUrl": PROJECT_MAP_PAGE_URL,
            "dataUrl": PROJECT_MAP_ARCHIVE_URL,
            "sourceDate": format_yukon_time(zip_state.get("last_modified", ""))
            if isinstance(zip_state, dict)
            else "",
            "contentLength": zip_state.get("content_length", "")
            if isinstance(zip_state, dict)
            else "",
        },
        "registry": {
            "label": "YESAB Online Registry",
            "pageUrl": REGISTRY_FRONT_URL,
            "apiUrl": REGISTRY_API_URL,
            "sourceDate": format_yukon_time(merged.get("generatedAt", ""))
            if isinstance(merged, dict)
            else "",
            "bucketCount": merged.get("bucketCount", 0)
            if isinstance(merged, dict)
            else 0,
            "projectCount": merged.get("projectCount", 0)
            if isinstance(merged, dict)
            else 0,
        },
    }


def load_api_projects() -> dict[str, dict[str, object]]:
    """Load merged YESAB API records keyed by project number, if available."""
    if not API_CACHE_FILE.exists():
        return {}
    payload = read_zstd_json_file(API_CACHE_FILE)
    projects = payload.get("projects", [])
    lookup: dict[str, dict[str, object]] = {}
    for project in projects:
        project_number = str(project.get("projectNumber", "")).strip()
        if project_number:
            lookup[project_number] = project
    return lookup


def qa_project_summary(project: dict[str, object]) -> dict[str, object]:
    """Return a compact QA summary for one cached API project."""
    return {
        "projectNumber": project.get("projectNumber", ""),
        "projectId": project.get("projectId", ""),
        "title": project.get("title", ""),
        "projectTypeName": project.get("projectTypeName", ""),
        "proponentName": project.get("proponentName", ""),
        "stageName": project.get("stage", {}).get("name", ""),
        "districts": [
            item.get("name", "") for item in project.get("assessmentDistricts", [])
        ],
        "sectors": [item.get("name", "") for item in project.get("sectors", [])],
        "locationCount": len(project.get("locations", [])),
    }


def api_fallback_feature(
    project: dict[str, object],
    feature_id: int,
    coordinate_counts: dict[tuple[float, float], int],
    location_overrides: dict[tuple[str, str], tuple[float, float]],
) -> dict[str, object] | None:
    """Build one approximate map point from an API project location."""
    project_number = str(project.get("projectNumber", "")).strip()
    project_id = str(project.get("projectId", "")).strip()
    if not project_number:
        return None
    for location in project.get("locations", []):
        if not isinstance(location, dict):
            continue
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        if latitude is None or longitude is None:
            continue
        try:
            source_latitude = float(latitude)
            source_longitude = float(longitude)
        except (TypeError, ValueError):
            continue
        coordinate_key = (round(source_latitude, 5), round(source_longitude, 5))
        coordinate_class, coordinate_flags = classify_api_coordinate(
            source_latitude,
            source_longitude,
            coordinate_counts.get(coordinate_key, 1),
        )
        map_latitude = source_latitude
        map_longitude = source_longitude
        override = location_overrides.get((project_number, project_id))
        coordinate_override = ""
        if override is not None:
            map_latitude, map_longitude = override
            coordinate_override = "location_overrides.csv"
        elif coordinate_class == "bad_coordinates":
            map_latitude = BAD_COORDINATE_DISPLAY_LATITUDE
            map_longitude = BAD_COORDINATE_DISPLAY_LONGITUDE
            coordinate_override = "bad_coordinate_display_fallback"
        try:
            point = project_lonlat_to_yukon_albers(map_longitude, map_latitude)
        except (TypeError, ValueError):
            continue
        properties = {
            "projectNumber": project_number,
            "projectId": project_id,
            "title": str(project.get("title", "")).strip(),
            "projectTypeName": str(project.get("projectTypeName", "")).strip(),
            "proponentName": str(project.get("proponentName", "")).strip(),
            "stage": str(project.get("stage", {}).get("name", "")).strip(),
            "locationSource": "YESAB API location",
            "locationApproximate": "Yes",
            "locationCoordinateClass": coordinate_class,
            "locationCoordinateFlags": ", ".join(coordinate_flags),
            "locationCoordinateOverride": coordinate_override,
            "latitude": str(map_latitude),
            "longitude": str(map_longitude),
            "sourceLatitude": str(source_latitude),
            "sourceLongitude": str(source_longitude),
        }
        return {
            "id": feature_id,
            "label": str(project.get("title", "")).strip() or project_number,
            "bbox": [point[0], point[1], point[0], point[1]],
            "properties": {key: value for key, value in properties.items() if value},
            "geometry": {"type": "Point", "coordinates": point},
            "apiProjectNumber": project_number,
            "isApiFallback": True,
        }
    return None
