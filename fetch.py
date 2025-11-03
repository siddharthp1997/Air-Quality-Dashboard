# AQICN-compliant loader (updated for dew/time.iso/forecast)
import os
import requests
import pandas as pd
from urllib.parse import quote
from datetime import datetime, timezone
from time import sleep
from pymongo import MongoClient
from dotenv import load_dotenv
import pytz

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
ATLAS_URI    = os.getenv("ATLAS_URI")
MONGO_DB     = str(os.getenv("MONGO_DB"))
MONGO_COLL   = str(os.getenv("MONGO_COLLECTION"))

if not API_TOKEN:
    raise RuntimeError("Missing API_TOKEN in environment")

# keep your USA list (example), you can add non-US cities too
CITIES = [
    {"city": "Los Angeles", "state": "California"},
    {"city": "New York City", "state": "New York"},
    # ...
]

API_TMPL = "https://api.waqi.info/feed/{q}/?token={token}"

def now_est_date_time():
    eastern = pytz.timezone("America/New_York")
    now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
    now_est = now_utc.astimezone(eastern)
    return now_est.strftime("%Y-%m-%d"), now_est.strftime("%H:%M:%S")

def to_number_or_none(x):
    try:
        if isinstance(x, str) and x.strip() == "-":
            return None
        return float(x)
    except (TypeError, ValueError):
        return None

def aqi_category(aqi):
    v = to_number_or_none(aqi)
    if v is None: return "Unknown"
    if v <= 50:   return "Good"
    if v <= 100:  return "Moderate"
    if v <= 150:  return "Unhealthy for Sensitive Groups"
    if v <= 200:  return "Unhealthy"
    if v <= 300:  return "Very Unhealthy"
    return "Hazardous"

def flatten_iaqi(iaqi):
    out = {}
    if not isinstance(iaqi, dict):
        return out
    for k, obj in iaqi.items():
        if isinstance(obj, dict) and "v" in obj:
            out[f"iaqi_{k}"] = obj["v"]  # includes iaqi_dew, iaqi_pm25, iaqi_t, etc.
    return out

def extract_forecast(daily):
    """Return dict with arrays for pm25/pm10/uvi if present."""
    f = {}
    if not isinstance(daily, dict):
        return f
    if "pm25" in daily:
        f["Forecast PM25 Daily"] = daily["pm25"]  # list of {day, avg, max, min}
    if "pm10" in daily:
        f["Forecast PM10 Daily"] = daily["pm10"]
    if "uvi" in daily:
        f["Forecast UVI Daily"] = daily["uvi"]
    return f

def fetch_feed(query_text):
    url = API_TMPL.format(q=quote(query_text), token=API_TOKEN)
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()

def to_record(city_label, state, payload):
    date_str, time_str = now_est_date_time()

    status = payload.get("status")
    if status != "ok":
        return {
            "City": city_label, "State": state, "Country": "USA",
            "AQI (US)": "NA", "AQI Category": "Unknown",
            "Main Pollutant (US)": "Error",
            "AQI (CN)": "NA", "Main Pollutant (CN)": "NA",
            "Date": date_str, "Time": time_str,
            "Source": "aqicn", "status": status or "unknown",
        }

    d = payload.get("data", {}) or {}

    aqi = d.get("aqi")
    dominent = d.get("dominentpol")
    idx = d.get("idx")

    city_block = d.get("city") or {}
    name = city_block.get("name") or city_label
    url = city_block.get("url")
    geo = city_block.get("geo") or []
    lat = to_number_or_none(geo[0]) if len(geo) > 0 else None
    lon = to_number_or_none(geo[1]) if len(geo) > 1 else None

    time_block = d.get("time") or {}
    t_local = time_block.get("s")
    t_tz    = time_block.get("tz")
    t_v     = time_block.get("v")
    t_iso   = time_block.get("iso")  # <-- new: present in your sample

    iaqi_flat = flatten_iaqi(d.get("iaqi") or {})
    forecast_daily = extract_forecast((d.get("forecast") or {}).get("daily"))

    rec = {
        # your existing fields
        "City": name,
        "State": state,
        "Country": "USA",
        "AQI (US)": aqi,
        "AQI Category": aqi_category(aqi),
        "Main Pollutant (US)": dominent,
        "AQI (CN)": "NA",
        "Main Pollutant (CN)": "NA",
        "Date": date_str,
        "Time": time_str,

        # station/time meta
        "Station IDX": idx,
        "Station URL": url,
        "Station Geo Lat": lat if lat is not None else "NA",
        "Station Geo Lon": lon if lon is not None else "NA",
        "Station Time (local)": t_local if t_local is not None else "NA",
        "Station Time TZ": t_tz if t_tz is not None else "NA",
        "Station Time (v)": t_v if t_v is not None else "NA",
        "Station Time ISO": t_iso if t_iso is not None else "NA",  # <-- new

        # ingest stamp
        "Ingested At UTC": datetime.now(timezone.utc).isoformat(),

        "Source": "aqicn",
        "status": "ok",
    }

    # include all iaqi_* (dew, pm25, pm10, o3, no2, so2, co, t, h, w, p, etc.)
    rec.update({k: (v if v is not None else "NA") for k, v in iaqi_flat.items()})

    # include forecast arrays (store as lists of dicts)
    rec.update(forecast_daily)

    # normalize remaining None -> 'NA'
    for k, v in list(rec.items()):
        if v is None:
            rec[k] = "NA"

    return rec

def fetch_city(city_info):
    city = city_info["city"]
    state = city_info.get("state", "")
    # Prefer “City, State, USA” for US; for non-US you can pass “City, Country”
    query_primary = f"{city}, {state}, USA" if state else city
    try:
        payload = fetch_feed(query_primary)
        if payload.get("status") == "ok":
            return to_record(city, state, payload)
    except requests.RequestException as e:
        print(f"[warn] {query_primary}: {e}")

    # Fallback: just the city (works for things like 'bangalore')
    try:
        payload = fetch_feed(city)
        return to_record(city, state, payload)
    except requests.RequestException as e:
        print(f"[error] {city}, {state}: {e}")
        date_str, time_str = now_est_date_time()
        return {
            "City": city, "State": state, "Country": "USA",
            "AQI (US)": "NA", "AQI Category": "Unknown",
            "Main Pollutant (US)": "Error",
            "AQI (CN)": "NA", "Main Pollutant (CN)": "NA",
            "Date": date_str, "Time": time_str,
            "Source": "aqicn", "status": "error",
        }

def process_cities_in_batches(cities, batch_size=4, delay_seconds=60):
    out = []
    for i in range(0, len(cities), batch_size):
        batch = cities[i:i+batch_size]
        for c in batch:
            out.append(fetch_city(c))
        if i + batch_size < len(cities):
            print(f"Processed batch {i//batch_size + 1}/{(len(cities)+batch_size-1)//batch_size}; sleeping {delay_seconds}s")
            sleep(delay_seconds)
    return out

def save_to_mongodb(records):
    client = MongoClient(ATLAS_URI, tls=True)
    try:
        db = client[MONGO_DB]
        coll = db[MONGO_COLL]
        if records:
            coll.insert_many(records)
    finally:
        client.close()

if __name__ == "__main__":
    records = process_cities_in_batches(CITIES, batch_size=4, delay_seconds=60)
    save_to_mongodb(records)
    print(pd.DataFrame(records)[:3])