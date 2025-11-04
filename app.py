# app.py — Full Streamlit Air Quality Dashboard (AQICN + Maps + Charts) with unique keys
import os
import streamlit as st
from pymongo import MongoClient
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

# -----------------------------
# Environment & DB setup
# -----------------------------
load_dotenv()
ATLAS_URI = os.getenv("ATLAS_URI")
MONGO_DB = str(os.getenv("MONGO_DB"))
MONGO_COLLECTION = str(os.getenv("MONGO_COLLECTION"))

st.set_page_config(page_title="Air Quality Dashboard", layout="wide")

@st.cache_resource
def get_collection():
    client = MongoClient(ATLAS_URI, tls=True)
    return client[MONGO_DB][MONGO_COLLECTION], client

@st.cache_data(ttl=300)
def fetch_data():
    try:
        collection, _ = get_collection()
        return list(collection.find())
    except Exception as e:
        st.error(f"MongoDB connection failed: {e}")
        return []

# -----------------------------
# Helpers
# -----------------------------
US_STATES = {
    "Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut","Delaware",
    "Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa","Kansas","Kentucky","Louisiana",
    "Maine","Maryland","Massachusetts","Michigan","Minnesota","Mississippi","Missouri","Montana",
    "Nebraska","Nevada","New Hampshire","New Jersey","New Mexico","New York","North Carolina",
    "North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania","Rhode Island","South Carolina",
    "South Dakota","Tennessee","Texas","Utah","Vermont","Virginia","Washington","West Virginia",
    "Wisconsin","Wyoming"
}

def parse_datetime_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if {"Date", "Time"}.issubset(df.columns):
        df["DateTime"] = pd.to_datetime(df["Date"].astype(str) + " " + df["Time"].astype(str), errors="coerce")
    elif "Ingested At UTC" in df.columns:
        df["DateTime"] = pd.to_datetime(df["Ingested At UTC"], errors="coerce")
    else:
        df["DateTime"] = pd.NaT
    return df

def latest_per_city(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "City" not in df.columns:
        return df
    if "DateTime" not in df.columns:
        df = parse_datetime_cols(df)
    latest = df.sort_values(["City", "DateTime"]).groupby("City", as_index=False).tail(1)
    if "AQI (US)" in latest.columns:
        latest["AQI (US)"] = pd.to_numeric(latest["AQI (US)"], errors="coerce")
    for c in latest.columns:
        if c.startswith("iaqi_"):
            latest[c] = pd.to_numeric(latest[c], errors="coerce")
    return latest.replace({"-1": pd.NA, "Error": pd.NA})

def numeric_columns(df: pd.DataFrame) -> list:
    prefer = ["AQI (US)", "Temperature (°C)", "Humidity (%)", "Pressure (hPa)", "Wind Speed (m/s)"]
    candidates = [c for c in df.columns if c.startswith("iaqi_")] + prefer
    out = []
    for c in candidates:
        if c in df.columns and pd.to_numeric(df[c], errors="coerce").notna().sum() > 0:
            out.append(c)
    for c in df.select_dtypes(include=["number"]).columns:
        if c not in out and c != "_id":
            out.append(c)
    return sorted(set(out), key=lambda x: (0 if x in prefer else (1 if x.startswith("iaqi_") else 2), x))

def forecast_to_df(rec: dict, field: str) -> pd.DataFrame | None:
    arr = rec.get(field)
    if not isinstance(arr, list) or not arr:
        return None
    df = pd.DataFrame(arr)
    req = {"day", "avg", "max", "min"}
    if not req.issubset(df.columns):
        return None
    df["day"] = pd.to_datetime(df["day"], errors="coerce")
    tidy = df.melt(id_vars="day", value_vars=["avg", "max", "min"], var_name="stat", value_name="value")
    tidy["value"] = pd.to_numeric(tidy["value"], errors="coerce")
    return tidy.dropna(subset=["day", "value"])

def ui_infer_country_row(row) -> str:
    c = row.get("Country")
    if isinstance(c, str) and c not in ["", "NA", "Unknown"]:
        return c
    url = (row.get("Station URL") or "").lower()
    name = (row.get("City") or "").lower()
    if "/india/" in url or "india" in name:
        return "India"
    st_name = row.get("State")
    if isinstance(st_name, str) and st_name in US_STATES:
        return "USA"
    return c or "Unknown"

def build_map_df(latest: pd.DataFrame, metric: str | None = "AQI (US)") -> pd.DataFrame:
    if latest.empty:
        return latest
    mdf = latest.copy()
    mdf["lat"] = pd.to_numeric(mdf.get("Station Geo Lat"), errors="coerce")
    mdf["lon"] = pd.to_numeric(mdf.get("Station Geo Lon"), errors="coerce")
    if metric and metric in mdf.columns:
        mdf[metric] = pd.to_numeric(mdf[metric], errors="coerce")
        subset = ["lat", "lon", metric]
    else:
        subset = ["lat", "lon"]
    return mdf.dropna(subset=subset)

def plot_map(df_map: pd.DataFrame, metric: str, title: str, key: str, zoom: int | None = None):
    if df_map.empty:
        st.info("No geocoded data available to display on the map.")
        return
    if zoom is None:
        zoom = 2 if df_map.get("Country", pd.Series([""])).nunique() > 1 else 3
    fig = px.scatter_mapbox(
        df_map,
        lat="lat",
        lon="lon",
        color=metric if metric in df_map.columns else None,
        size=metric if metric in df_map.columns else None,
        size_max=28,
        color_continuous_scale="Turbo",
        hover_name="City",
        hover_data={
            "Country": "Country" in df_map.columns,
            metric: metric in df_map.columns,
            "AQI Category": "AQI Category" in df_map.columns,
            "Main Pollutant (US)": "Main Pollutant (US)" in df_map.columns,
            "Station Time (local)": "Station Time (local)" in df_map.columns,
            "lat": False, "lon": False,
        },
        zoom=zoom,
        height=520,
        title=title,
    )
    fig.update_layout(mapbox_style="open-street-map", margin=dict(l=0, r=0, t=0, b=0))
    if metric in df_map.columns:
        fig.update_layout(coloraxis_colorbar=dict(title=metric))
    st.plotly_chart(fig, use_container_width=True, key=key)

# -----------------------------
# Load data
# -----------------------------
st.title("🌍 Air Quality Dashboard")

data = fetch_data()
if not data:
    st.warning("No data found in MongoDB.")
    st.stop()

df = pd.DataFrame(data)
df = parse_datetime_cols(df)

# Ensure Country exists and infer if missing/unknown (UI fallback)
if "Country" not in df.columns:
    df["Country"] = pd.NA
df["Country"] = df.apply(ui_infer_country_row, axis=1)

# -----------------------------
# Sidebar Filters (Country → City dependent)
# -----------------------------
with st.sidebar:
    st.header("Filters")

    countries = sorted(df["Country"].dropna().unique().tolist()) if "Country" in df.columns else []
    default_countries = countries[: min(2, len(countries))] if countries else []
    selected_countries = st.multiselect("Country", countries, default=default_countries, key="filter_countries")

    df_for_cities = df[df["Country"].isin(selected_countries)] if selected_countries else df
    all_cities = sorted(df_for_cities["City"].dropna().unique().tolist()) if "City" in df_for_cities.columns else []
    selected_cities = st.multiselect("City", all_cities, default=all_cities, key="filter_cities")

    if "AQI Category" in df.columns:
        aqi_cats = sorted(df["AQI Category"].dropna().unique().tolist())
        selected_cats = st.multiselect("AQI Category", aqi_cats, default=[], key="filter_aqi_cats")
    else:
        selected_cats = []

    date_range = st.date_input("Date range", [], key="filter_date_range")

def apply_filters(df_in: pd.DataFrame) -> pd.DataFrame:
    out = df_in.copy()
    if selected_countries:
        out = out[out.get("Country", pd.Series(index=out.index)).isin(selected_countries)]
    if selected_cities:
        out = out[out.get("City", pd.Series(index=out.index)).isin(selected_cities)]
    if selected_cats and "AQI Category" in out.columns:
        out = out[out["AQI Category"].isin(selected_cats)]
    if date_range and len(date_range) == 2:
        start, end = pd.to_datetime(date_range)
        mask = (out["DateTime"] >= start) & (out["DateTime"] <= end + pd.Timedelta(days=1))
        out = out[mask]
    return out

df_f = apply_filters(df)
latest_all = latest_per_city(df)      # unfiltered (for global map)
latest_filt = latest_per_city(df_f)   # filtered snapshot (for tables/charts)

# -----------------------------
# Tabs
# -----------------------------
tab_overview, tab_city, tab_maps, tab_forecast, tab_meta = st.tabs(
    ["Overview", "City Explorer", "Maps", "Forecasts", "Station Metadata"]
)

# -----------------------------
# Overview Tab
# -----------------------------
with tab_overview:
    st.subheader("📊 Latest Snapshot per City (Filtered)")
    cols_show = [c for c in ["Country","City","AQI (US)","AQI Category","Main Pollutant (US)","Station Time (local)","DateTime"]
                 if c in latest_filt.columns]
    if latest_filt.empty:
        st.info("No records to show.")
    else:
        st.dataframe(
            latest_filt[cols_show] if cols_show else latest_filt.drop(columns=["_id"], errors="ignore"),
            use_container_width=True
        )

    st.subheader("🌫 AQI (US) — Top 10 Cities by Latest Reading (Filtered)")
    if not df_f.empty and {"City","DateTime","AQI (US)"}.issubset(df_f.columns):
        tmp = df_f.copy()
        tmp["AQI (US)"] = pd.to_numeric(tmp["AQI (US)"], errors="coerce")
        latest_for_top = latest_per_city(tmp).dropna(subset=["AQI (US)"])
        if latest_for_top.empty:
            st.info("No numeric AQI values available.")
        else:
            top10_cities = latest_for_top.sort_values("AQI (US)", ascending=False).head(10)["City"].tolist()
            series_top = tmp[tmp["City"].isin(top10_cities)].dropna(subset=["AQI (US)", "DateTime"])
            if series_top.empty:
                st.info("No time-series data for the Top 10 cities.")
            else:
                fig_top = px.line(
                    series_top, x="DateTime", y="AQI (US)", color="City",
                    markers=True, title="AQI (US) Variation — Top 10 Cities"
                )
                fig_top.update_layout(xaxis_title="Date/Time", yaxis_title="AQI (US)")
                st.plotly_chart(fig_top, use_container_width=True, key="top10_chart")
    else:
        st.info("Insufficient data to plot Top 10 AQI chart.")

# -----------------------------
# City Explorer Tab
# -----------------------------
with tab_city:
    st.subheader("🏙 City Explorer (Filtered)")
    if "City" in df_f.columns and len(df_f["City"].dropna().unique()) > 0:
        city_pick = st.selectbox("Select a City", sorted(df_f["City"].dropna().unique().tolist()), key="city_pick")
        cdf = df_f[df_f["City"] == city_pick].copy()
    else:
        cdf = pd.DataFrame()

    if not cdf.empty:
        metrics = numeric_columns(cdf)
        if metrics:
            metric_idx = metrics.index("AQI (US)") if "AQI (US)" in metrics else 0
            metric = st.selectbox("Select Metric", metrics, index=metric_idx, key="city_metric_select")
            cdf[metric] = pd.to_numeric(cdf[metric], errors="coerce")
            plot_df = cdf.dropna(subset=["DateTime", metric])
            if plot_df.empty:
                st.info("No time-series values available for the selected metric.")
            else:
                fig = px.line(plot_df, x="DateTime", y=metric, title=f"{metric} in {city_pick}", markers=True)
                fig.update_layout(xaxis_title="Date/Time", yaxis_title=metric)
                st.plotly_chart(fig, use_container_width=True, key=f"city_metric_chart_{metric}")
        else:
            st.info("No numeric IAQI/AQI fields to plot for this city.")
    else:
        st.info("Select a city to explore its metrics.")

# -----------------------------
# Maps Tab
# -----------------------------
with tab_maps:
    st.subheader("🗺️ Global AQI Map — Latest Reading per City (All Cities, Unfiltered)")
    # Always show ALL cities' latest AQI (ignores filters)
    map_global = build_map_df(latest_all, metric="AQI (US)")
    plot_map(map_global, metric="AQI (US)", title="Global AQI Map", key="global_aqi_map")

    st.subheader("🗺️ Metric Map — Choose Any Metric (All vs Filtered)")
    # Metric selection
    num_cols_all = numeric_columns(latest_all)
    default_idx = num_cols_all.index("AQI (US)") if "AQI (US)" in num_cols_all else 0
    metric_choice = st.selectbox("Metric", num_cols_all, index=default_idx, key="metric_map_choice")
    scope = st.radio("Scope", ["All Cities", "Filtered Cities"], horizontal=True, key="map_scope")

    if scope == "All Cities":
        map_df = build_map_df(latest_all, metric=metric_choice)
    else:
        map_df = build_map_df(latest_filt, metric=metric_choice)

    map_key = f"metric_map_{scope.replace(' ', '_')}_{metric_choice}"
    plot_map(map_df, metric=metric_choice, title=f"{metric_choice} Map ({scope})", key=map_key)

# -----------------------------
# Forecasts Tab (Filtered) — with City selector
# -----------------------------
with tab_forecast:
    st.subheader("📈 Forecasts (if available)")

    if latest_filt.empty:
        st.info("No recent filtered records to show forecast.")
    else:
        # Build city list from the latest filtered snapshot
        forecast_cities = sorted(latest_filt["City"].dropna().unique().tolist())
        city_fc = st.selectbox("Select a city for forecast", forecast_cities, key="forecast_city_select")

        rec_row = latest_filt[latest_filt["City"] == city_fc]
        if rec_row.empty:
            st.info(f"No forecast-capable record found for {city_fc}.")
        else:
            rec = rec_row.iloc[0].to_dict()

            forecast_fields = [
                ("Forecast PM25 Daily", "PM2.5 (µg/m³)"),
                ("Forecast PM10 Daily", "PM10 (µg/m³)"),
                ("Forecast UVI Daily", "UV Index"),
            ]

            any_found = False
            for field, y_label in forecast_fields:
                fdf = forecast_to_df(rec, field)
                if fdf is not None and not fdf.empty:
                    any_found = True
                    fig_f = px.line(
                        fdf, x="day", y="value", color="stat", markers=True,
                        title=f"{field.replace('Forecast ', '').replace(' Daily', '')} — {city_fc}"
                    )
                    fig_f.update_layout(xaxis_title="Day", yaxis_title=y_label, legend_title="stat")
                    st.plotly_chart(fig_f, use_container_width=True, key=f"forecast_chart_{city_fc}_{field}")
            if not any_found:
                st.info(f"No forecast arrays found for {city_fc}.")

# -----------------------------
# Station Metadata Tab (Filtered)
# -----------------------------
with tab_meta:
    st.subheader("📍 Station Metadata (Filtered)")
    meta_cols = [c for c in [
        "Station IDX", "Station URL", "Station Geo Lat", "Station Geo Lon",
        "Station Time (local)", "Station Time TZ", "Station Time ISO"
    ] if c in latest_filt.columns]
    if not latest_filt.empty and meta_cols:
        st.dataframe(latest_filt[["City"] + meta_cols], use_container_width=True)
    else:
        st.info("No station metadata available.")

# -----------------------------
# Attribution
# -----------------------------
st.caption("Data © World Air Quality Index Project (aqicn.org). Results are real-time and may be unverified.")