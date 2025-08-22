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
    

def create_weather_request(loc: Dict[str, Any], start_s: str, end_s: str, unit: str = "fahrenheit") -> int:
    start, end = validate_range(start_s, end_s)
    unit = "celsius" if str(unit).lower().startswith("c") else "fahrenheit"
    loc_id = upsert_location(loc["label"], float(loc["lat"]), float(loc["lon"]))
    sql = """
    INSERT INTO weather_requests (location_id, start_date, end_date, unit)
    VALUES (%s, %s, %s, %s)
    RETURNING id;
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (loc_id, start, end, unit))
        return cur.fetchone()[0]

def list_requests_db(limit: int = 200) -> List[Dict[str, Any]]:
    sql = """
      SELECT wr.id, wr.start_date, wr.end_date, wr.unit, wr.created_at,
             l.id AS location_id, l.label, l.lat, l.lon
      FROM weather_requests wr
      JOIN locations l ON wr.location_id = l.id
      ORDER BY wr.created_at DESC
      LIMIT %s;
    """
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (limit,))
        return cur.fetchall()

def get_request_db(req_id: int) -> Optional[Dict[str, Any]]:
    sql = """
      SELECT wr.id, wr.start_date, wr.end_date, wr.unit, wr.created_at,
             l.id AS location_id, l.label, l.lat, l.lon
      FROM weather_requests wr
      JOIN locations l ON wr.location_id = l.id
      WHERE wr.id = %s;
    """
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (req_id,))
        return cur.fetchone()