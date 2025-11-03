# app.py
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
ATLAS_URI = os.getenv('ATLAS_URI')
MONGO_DB = str(os.getenv('MONGO_DB'))
MONGO_COLLECTION = str(os.getenv('MONGO_COLLECTION'))

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
def parse_datetime_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if {'Date', 'Time'}.issubset(df.columns):
        df['DateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['Time'].astype(str), errors='coerce')
    elif 'Ingested At UTC' in df.columns:
        df['DateTime'] = pd.to_datetime(df['Ingested At UTC'], errors='coerce')
    else:
        df['DateTime'] = pd.NaT
    return df

def latest_per_city(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or 'City' not in df.columns:
        return df
    # ensure DateTime exists
    if 'DateTime' not in df.columns:
        df = parse_datetime_cols(df)
    latest = df.sort_values(['City', 'DateTime']).groupby('City', as_index=False).tail(1)
    # Make AQI numeric for sorting/plotting
    if 'AQI (US)' in latest.columns:
        latest['AQI (US)'] = pd.to_numeric(latest['AQI (US)'], errors='coerce')
    return latest.replace({'-1': pd.NA, 'Error': pd.NA})

def numeric_columns(df: pd.DataFrame) -> list:
    # start with likely metrics, include all iaqi_*
    prefer = ['AQI (US)', 'Temperature (°C)', 'Humidity (%)', 'Pressure (hPa)', 'Wind Speed (m/s)']
    candidates = [c for c in df.columns if c.startswith('iaqi_')] + prefer
    out = []
    for c in candidates:
        if c in df.columns and pd.to_numeric(df[c], errors='coerce').notna().sum() > 0:
            out.append(c)
    # include any other numeric columns discovered
    for c in df.select_dtypes(include=['number']).columns:
        if c not in out and c != '_id':
            out.append(c)
    # stable order: prefer, then iaqi_*, then others
    return sorted(set(out), key=lambda x: (0 if x in prefer else (1 if x.startswith('iaqi_') else 2), x))

def forecast_to_df(rec: dict, field: str) -> pd.DataFrame | None:
    """
    Convert forecast arrays (e.g., 'Forecast PM25 Daily') to tidy df with day/avg/max/min.
    Stores under keys exactly as in loader: 'Forecast PM25 Daily', 'Forecast PM10 Daily', 'Forecast UVI Daily'
    """
    arr = rec.get(field)
    if not isinstance(arr, list) or not arr:
        return None
    df = pd.DataFrame(arr)
    required = {'day', 'avg', 'max', 'min'}
    if not required.issubset(df.columns):
        return None
    df['day'] = pd.to_datetime(df['day'], errors='coerce')
    tidy = df.melt(id_vars='day', value_vars=['avg', 'max', 'min'], var_name='stat', value_name='value')
    tidy['value'] = pd.to_numeric(tidy['value'], errors='coerce')
    return tidy.dropna(subset=['day', 'value'])

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

# -----------------------------
# Sidebar Filters
# -----------------------------
with st.sidebar:
    st.header("Filters")

    # Country filter (if exists)
    if 'Country' in df.columns:
        countries = sorted(df['Country'].dropna().unique().tolist())
        default_countries = countries[:min(2, len(countries))] if countries else []
        selected_countries = st.multiselect("Country", countries, default=default_countries)
    else:
        selected_countries = []

    # City filter
    all_cities = sorted(df['City'].dropna().unique().tolist()) if 'City' in df.columns else []
    selected_cities = st.multiselect("City", all_cities, default=all_cities[:min(10, len(all_cities))])

    # AQI Category filter (if exists)
    if 'AQI Category' in df.columns:
        aqi_cats = sorted(df['AQI Category'].dropna().unique().tolist())
        selected_cats = st.multiselect("AQI Category", aqi_cats, default=[])
    else:
        selected_cats = []

    # Date range filter
    date_range = st.date_input("Date range", [])

def apply_filters(df_in: pd.DataFrame) -> pd.DataFrame:
    out = df_in.copy()
    if selected_countries:
        out = out[out.get('Country', pd.Series(index=out.index)).isin(selected_countries)]
    if selected_cities:
        out = out[out.get('City', pd.Series(index=out.index)).isin(selected_cities)]
    if selected_cats and 'AQI Category' in out.columns:
        out = out[out['AQI Category'].isin(selected_cats)]
    if date_range and len(date_range) == 2:
        start, end = pd.to_datetime(date_range)
        mask = (out['DateTime'] >= start) & (out['DateTime'] <= end + pd.Timedelta(days=1))
        out = out[mask]
    return out

df_f = apply_filters(df)

# -----------------------------
# Latest Snapshot
# -----------------------------
st.subheader("📊 Latest Snapshot per City")
latest_df = latest_per_city(df_f)
cols_show = [c for c in ['Country', 'City', 'AQI (US)', 'AQI Category',
                         'Main Pollutant (US)', 'Station Time (local)', 'DateTime']
             if c in latest_df.columns]
if latest_df.empty:
    st.info("No records to show.")
else:
    st.dataframe(latest_df[cols_show] if cols_show else latest_df.drop(columns=['_id'], errors='ignore'),
                 use_container_width=True)

# -----------------------------
# Top 10 AQI (All Cities) Chart
# -----------------------------
st.subheader("🌫 AQI (US) — Top 10 Cities by Latest Reading")
if not df_f.empty and {'City', 'DateTime', 'AQI (US)'}.issubset(df_f.columns):
    # ensure numeric
    df_f = df_f.copy()
    df_f['AQI (US)'] = pd.to_numeric(df_f['AQI (US)'], errors='coerce')
    # find latest per city, then take top 10 by AQI
    latest_for_top = latest_per_city(df_f).dropna(subset=['AQI (US)'])
    if latest_for_top.empty:
        st.info("No numeric AQI values available.")
    else:
        top10_cities = latest_for_top.sort_values('AQI (US)', ascending=False).head(10)['City'].tolist()
        series_top = df_f[df_f['City'].isin(top10_cities)].dropna(subset=['AQI (US)', 'DateTime'])
        if series_top.empty:
            st.info("No time-series data for the Top 10 cities.")
        else:
            fig_top = px.line(series_top, x='DateTime', y='AQI (US)', color='City',
                              markers=True, title='AQI (US) Variation — Top 10 Cities')
            fig_top.update_layout(xaxis_title='Date/Time', yaxis_title='AQI (US)')
            st.plotly_chart(fig_top, use_container_width=True)
else:
    st.info("Insufficient data to plot Top 10 AQI chart.")

# -----------------------------
# City-level Explorer
# -----------------------------
st.subheader("🏙 City Explorer")
if 'City' in df_f.columns and len(df_f['City'].dropna().unique()) > 0:
    city_pick = st.selectbox("Select a City", sorted(df_f['City'].dropna().unique().tolist()))
    cdf = df_f[df_f['City'] == city_pick].copy()
else:
    cdf = pd.DataFrame()

if not cdf.empty:
    metrics = numeric_columns(cdf)
    if metrics:
        metric = st.selectbox("Select Metric", metrics, index=0)
        cdf[metric] = pd.to_numeric(cdf[metric], errors='coerce')
        plot_df = cdf.dropna(subset=['DateTime', metric])
        if plot_df.empty:
            st.info("No time-series values available for the selected metric.")
        else:
            fig = px.line(plot_df, x='DateTime', y=metric, title=f'{metric} in {city_pick}', markers=True)
            fig.update_layout(xaxis_title='Date/Time', yaxis_title=metric)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No numeric IAQI/AQI fields to plot for this city.")
else:
    st.info("Select a city to explore its metrics.")

# -----------------------------
# Forecasts (optional, if stored)
# -----------------------------
with st.expander("📈 Forecasts (if available)"):
    if not latest_df.empty:
        rec = latest_df.iloc[0].to_dict()
        forecast_fields = [("Forecast PM25 Daily", "PM2.5 (µg/m³)"),
                           ("Forecast PM10 Daily", "PM10 (µg/m³)"),
                           ("Forecast UVI Daily", "UV Index")]
        any_found = False
        for field, y_label in forecast_fields:
            fdf = forecast_to_df(rec, field)
            if fdf is not None and not fdf.empty:
                any_found = True
                fig_f = px.line(fdf, x="day", y="value", color="stat", markers=True,
                                title=f"{field.replace('Forecast ', '').replace(' Daily', '')} — {rec.get('City','')}")
                fig_f.update_layout(xaxis_title="Day", yaxis_title=y_label, legend_title="stat")
                st.plotly_chart(fig_f, use_container_width=True)
        if not any_found:
            st.info("No forecast arrays found in the latest record.")
    else:
        st.info("No recent record available to show forecast.")

# -----------------------------
# Station metadata (helpful for provenance)
# -----------------------------
with st.expander("📍 Station Metadata"):
    meta_cols = [c for c in ['Station IDX', 'Station URL', 'Station Geo Lat', 'Station Geo Lon',
                             'Station Time (local)', 'Station Time TZ', 'Station Time ISO']
                 if c in latest_df.columns]
    if not latest_df.empty and meta_cols:
        st.dataframe(latest_df[['City'] + meta_cols], use_container_width=True)
    else:
        st.info("No station metadata available.")

# -----------------------------
# Attribution
# -----------------------------
st.caption("Data © World Air Quality Index Project (aqicn.org). Results are real-time and may be unverified.")