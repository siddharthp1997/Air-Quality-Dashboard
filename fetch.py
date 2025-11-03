# fetch.py — AQICN loader with correct Country handling
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

API_TOKEN  = os.getenv("API_TOKEN")          # your AQICN token
ATLAS_URI  = os.getenv("ATLAS_URI")
MONGO_DB   = str(os.getenv("MONGO_DB"))
MONGO_COLL = str(os.getenv("MONGO_COLLECTION"))

if not API_TOKEN:
    raise RuntimeError("Missing API_TOKEN in environment")

# --- Countries & US states for inference ---
US_STATES = {
  "Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut","Delaware",
  "Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa","Kansas","Kentucky","Louisiana",
  "Maine","Maryland","Massachusetts","Michigan","Minnesota","Mississippi","Missouri","Montana",
  "Nebraska","Nevada","New Hampshire","New Jersey","New Mexico","New York","North Carolina",
  "North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania","Rhode Island","South Carolina",
  "South Dakota","Tennessee","Texas","Utah","Vermont","Virginia","Washington","West Virginia",
  "Wisconsin","Wyoming"
}

# ---------- Cities (USA + India top-20) with explicit country ----------
CITIES = [
    # USA
    {"city": "New York City", "state": "New York", "country": "USA"},
    {"city": "Los Angeles", "state": "California", "country": "USA"},
    {"city": "Chicago", "state": "Illinois", "country": "USA"},
    {"city": "Houston", "state": "Texas", "country": "USA"},
    {"city": "Phoenix", "state": "Arizona", "country": "USA"},
    {"city": "Philadelphia", "state": "Pennsylvania", "country": "USA"},
    {"city": "San Antonio", "state": "Texas", "country": "USA"},
    {"city": "San Diego", "state": "California", "country": "USA"},
    {"city": "Dallas", "state": "Texas", "country": "USA"},
    {"city": "San Jose", "state": "California", "country": "USA"},
    {"city": "Austin", "state": "Texas", "country": "USA"},
    {"city": "Jacksonville", "state": "Florida", "country": "USA"},
    {"city": "San Francisco", "state": "California", "country": "USA"},
    {"city": "Indianapolis", "state": "Indiana", "country": "USA"},
    {"city": "Columbus", "state": "Ohio", "country": "USA"},
    {"city": "Fort Worth", "state": "Texas", "country": "USA"},
    {"city": "Charlotte", "state": "North Carolina", "country": "USA"},
    {"city": "Seattle", "state": "Washington", "country": "USA"},
    {"city": "Denver", "state": "Colorado", "country": "USA"},
    {"city": "Boston", "state": "Massachusetts", "country": "USA"},
    {"city": "El Paso", "state": "Texas", "country": "USA"},
    {"city": "Nashville", "state": "Tennessee", "country": "USA"},
    {"city": "Detroit", "state": "Michigan", "country": "USA"},
    {"city": "Oklahoma City", "state": "Oklahoma", "country": "USA"},
    {"city": "Portland", "state": "Oregon", "country": "USA"},
    {"city": "Las Vegas", "state": "Nevada", "country": "USA"},
    {"city": "Memphis", "state": "Tennessee", "country": "USA"},
    {"city": "Louisville", "state": "Kentucky", "country": "USA"},
    {"city": "Baltimore", "state": "Maryland", "country": "USA"},
    {"city": "Milwaukee", "state": "Wisconsin", "country": "USA"},
    {"city": "Albuquerque", "state": "New Mexico", "country": "USA"},
    {"city": "Tucson", "state": "Arizona", "country": "USA"},
    {"city": "Fresno", "state": "California", "country": "USA"},
    {"city": "Sacramento", "state": "California", "country": "USA"},
    {"city": "Kansas City", "state": "Missouri", "country": "USA"},
    {"city": "Atlanta", "state": "Georgia", "country": "USA"},
    {"city": "Miami", "state": "Florida", "country": "USA"},
    {"city": "Honolulu", "state": "Hawaii", "country": "USA"},

    # India (Top 20)
    {"city": "Delhi", "state": "Delhi", "country": "India"},
    {"city": "Mumbai", "state": "Maharashtra", "country": "India"},
    {"city": "Bengaluru", "state": "Karnataka", "country": "India"},
    {"city": "Hyderabad", "state": "Telangana", "country": "India"},
    {"city": "Ahmedabad", "state": "Gujarat", "country": "India"},
    {"city": "Chennai", "state": "Tamil Nadu", "country": "India"},
    {"city": "Kolkata", "state": "West Bengal", "country": "India"},
    {"city": "Surat", "state": "Gujarat", "country": "India"},
    {"city": "Pune", "state": "Maharashtra", "country": "India"},
    {"city": "Jaipur", "state": "Rajasthan", "country": "India"},
    {"city": "Kanpur", "state": "Uttar Pradesh", "country": "India"},
    {"city": "Lucknow", "state": "Uttar Pradesh", "country": "India"},
    {"city": "Nagpur", "state": "Maharashtra", "country": "India"},
    {"city": "Indore", "state": "Madhya Pradesh", "country": "India"},
    {"city": "Thane", "state": "Maharashtra", "country": "India"},
    {"city": "Bhopal", "state": "Madhya Pradesh", "country": "India"},
    {"city": "Visakhapatnam", "state": "Andhra Pradesh", "country": "India"},
    {"city": "Patna", "state": "Bihar", "country": "India"},
    {"city": "Vadodara", "state": "Gujarat", "country": "India"},
    {"city": "Ghaziabad", "state": "Uttar Pradesh", "country": "India"},
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
            out[f"iaqi_{k}"] = obj["v"]
    return out

def extract_forecast(daily):
    f = {}
    if not isinstance(daily, dict):
        return f
    if "pm25" in daily:
        f["Forecast PM25 Daily"] = daily["pm25"]
    if "pm10" in daily:
        f["Forecast PM10 Daily"] = daily["pm10"]
    if "uvi" in daily:
        f["Forecast UVI Daily"] = daily["uvi"]
    return f

def fetch_feed(query_text):
    url = API_TMPL.format(q=quote(query_text), token=API_TOKEN)
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    return r.json()

def infer_country(city_block, provided_country, state):
    # 1) Honor explicit country from CITIES
    if provided_country:
        return provided_country
    # 2) Infer from AQICN city metadata
    url = (city_block or {}).get("url") or ""
    name = (city_block or {}).get("name") or ""
    Lurl, Lname = url.lower(), name.lower()
    if "/india/" in Lurl or "india" in Lname:
        return "India"
    # 3) US by state membership
    if state in US_STATES:
        return "USA"
    return "Unknown"

def to_record(city_label, state, payload, provided_country=None):
    date_str, time_str = now_est_date_time()

    status = payload.get("status")
    if status != "ok":
        return {
            "City": city_label, "State": state, "Country": provided_country or ("USA" if state in US_STATES else "Unknown"),
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
    t_iso   = time_block.get("iso")

    iaqi_flat = flatten_iaqi(d.get("iaqi") or {})
    forecast_daily = extract_forecast((d.get("forecast") or {}).get("daily"))

    country = infer_country(city_block, provided_country, state)

    rec = {
        "City": name,
        "State": state,
        "Country": country,
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
        "Station Time ISO": t_iso if t_iso is not None else "NA",

        "Ingested At UTC": datetime.now(timezone.utc).isoformat(),

        "Source": "aqicn",
        "status": "ok",
    }

    rec.update({k: (v if v is not None else "NA") for k, v in iaqi_flat.items()})
    rec.update(forecast_daily)

    for k, v in list(rec.items()):
        if v is None:
            rec[k] = "NA"
    return rec

def fetch_city(city_info):
    city = city_info["city"]
    state = city_info.get("state", "")
    provided_country = city_info.get("country")

    # Build a disambiguated query: "City, State, Country" when possible
    parts = [city, state, provided_country]
    query_primary = ", ".join([p for p in parts if p])

    # Try main query
    try:
        payload = fetch_feed(query_primary)
        if payload.get("status") == "ok":
            return to_record(city, state, payload, provided_country)
    except requests.RequestException as e:
        print(f"[warn] {query_primary}: {e}")

    # Fallback: just the city
    try:
        payload = fetch_feed(city)
        return to_record(city, state, payload, provided_country)
    except requests.RequestException as e:
        print(f"[error] {city}, {state}: {e}")
        date_str, time_str = now_est_date_time()
        return {
            "City": city, "State": state, "Country": provided_country or ("USA" if state in US_STATES else "Unknown"),
            "AQI (US)": "NA", "AQI Category": "Unknown",
            "Main Pollutant (US)": "Error",
            "AQI (CN)": "NA", "Main Pollutant (CN)": "NA",
            "Date": date_str, "Time": time_str,
            "Source": "aqicn", "status": "error",
        }

def process_cities_in_batches(cities, batch_size=3, delay_seconds=1):
    out = []
    for i in range(0, len(cities), batch_size):
        batch = cities[i:i+batch_size]
        for c in batch:
            out.append(fetch_city(c))
        if i + batch_size < len(cities):
            print(f"Processed batch {i//batch_size + 1}/{(len(cities)+batch_size-1)//batch_size}; sleeping {delay_seconds}s")
            sleep(delay_seconds)  # be kind to free-tier rate limits
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
    records = process_cities_in_batches(CITIES, batch_size=3, delay_seconds=1)
    save_to_mongodb(records)
    print(pd.DataFrame(records).head(3))