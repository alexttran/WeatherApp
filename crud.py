import os
import requests
import re
from typing import Optional, Dict, Any, List, Tuple
from psycopg2.extras import RealDictCursor
from db_raw import get_conn
from validators import validate_range

GEOCODIFY_API_KEY = os.getenv("GEOCODIFY_API_KEY", "")
HEADERS = {"Accept": "application/json", "User-Agent": "WeatherApp/1.0 (+server)"}

COORDS_RE = re.compile(r"^\s*([+-]?(?:\d+(?:\.\d+)?)),\s*([+-]?(?:\d+(?:\.\d+)?))\s*$")

def parse_coords(text: str) -> Tuple[float, float] | None:
    match = COORDS_RE.match(text)
    if match:
        lat = float(match.group(1))
        lon = float(match.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return (lat, lon)
    return None

def _geo_get(params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"https://api.geocodify.com/v2/geocode"
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if r.status_code == 429:
           return {"_error": "rate_limited"}
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": str(e)}

def resolve_location_from_query(q: str) -> Dict[str, Any]:
    if not GEOCODIFY_API_KEY:
        raise RuntimeError("Missing GEOCODIFY_API_KEY")
    coords = parse_coords(q)
    if coords:
        return {"label": q, "lat": coords[0], "lon": coords[1]}
    if not GEOCODIFY_API_KEY:
        return {"error": "Missing GEOCODIFY_API_KEY on server"}, 500
    
    data = _geo_get("geocode", {"api_key": GEOCODIFY_API_KEY, "q": q})
    if data.get("_error") == "rate_limited":
        return {"error": "Geocodify rate limit hit. Type slower or upgrade the plan."}, 429
    if "_error" in data:
        return {"error": f"Geocoding failed: {data['_error']}"}, 502
    c = data['response']['features'][0]['geometry']['coordinates']
    return {"label": q, "lat": c[1], "lon": c[0]}
    

def upsert_location(label: str, lat: float, lon: float) -> int:
    sql = """
    INSERT INTO locations (label, lat, lon)
    VALUES (%s, %s, %s)
    ON CONFLICT (lat, lon) DO UPDATE SET label = EXCLUDED.label
    RETURNING id;
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (label, lat, lon))
        return cur.fetchone()[0]