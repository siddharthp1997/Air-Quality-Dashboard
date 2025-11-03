import os
import streamlit as st
from pymongo import MongoClient
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from datetime import datetime
import pytz

# -----------------------------
# Environment & DB setup
# -----------------------------
load_dotenv()
ATLAS_URI = os.getenv('ATLAS_URI')
MONGO_DB = str(os.getenv('MONGO_DB'))
MONGO_COLLECTION = str(os.getenv('MONGO_COLLECTION'))

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
def parse_datetime_cols(df):
    if {'Date', 'Time'}.issubset(df.columns):
        df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], errors='coerce')
    elif 'Ingested At UTC' in df.columns:
        df['DateTime'] = pd.to_datetime(df['Ingested At UTC'], errors='coerce')
    else:
        df['DateTime'] = pd.NaT
    return df

def latest_per_city(df):
    if 'City' not in df.columns or df.empty:
        return df
    latest = df.sort_values(['City', 'DateTime']).groupby('City', as_index=False).tail(1)
    return latest.replace({'-1': pd.NA, 'Error': pd.NA})

def numeric_columns(df):
    candidates = [c for c in df.columns if c.startswith('iaqi_')] + [
        'AQI (US)', 'Temperature (°C)', 'Humidity (%)',
        'Pressure (hPa)', 'Wind Speed (m/s)'
    ]
    result = []
    for c in candidates:
        if c in df.columns and pd.to_numeric(df[c], errors='coerce').notna().sum() > 0:
            result.append(c)
    for c in df.select_dtypes(include=['number']).columns:
        if c not in result:
            result.append(c)
    return sorted(set(result))

def forecast_to_df(rec, field):
    arr = rec.get(field)
    if not isinstance(arr, list):
        return None
    df = pd.DataFrame(arr)
    if not {'day', 'avg', 'max', 'min'}.issubset(df.columns):
        return None
    df['day'] = pd.to_datetime(df['day'], errors='coerce')
    df = df.melt(id_vars='day', value_vars=['avg', 'max', 'min'],
                 var_name='stat', value_name='value')
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    return df.dropna(subset=['day', 'value'])

# -----------------------------
# App UI
# -----------------------------
st.set_page_config(page_title="Air Quality Dashboard", layout="wide")
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

    # ✅ Country filter (new)
    if 'Country' in df.columns:
        countries = sorted(df['Country'].dropna().unique())
        selected_countries = st.multiselect(
            "Country",
            countries,
            default=countries[:min(2, len(countries))]
        )
    else:
        selected_countries = []  # fallback if column missing

    # City filter
    cities = sorted(df['City'].dropna().unique().tolist())
    selected_cities = st.multiselect(
        "City",
        cities,
        default=cities[:min(10, len(cities))]
    )

    # AQI Category filter
    if 'AQI Category' in df.columns:
        aqi_cats = sorted(df['AQI Category'].dropna().unique())
        selected_cats = st.multiselect("AQI Category", aqi_cats, default=[])
    else:
        selected_cats = []

    # Date range filter
    date_range = st.date_input("Date range", [])

# Apply filters
def apply_filters(df):
    out = df.copy()
    if selected_countries:
        out = out[out['Country'].isin(selected_countries)]
    if selected_cities:
        out = out[out['City'].isin(selected_cities)]
    if selected_cats and 'AQI Category' in out.columns:
        out = out[out['AQI Category'].isin(selected_cats)]
    if date_range and len(date_range) == 2:
        start, end = pd.to_datetime(date_range)
        mask = (out['DateTime'] >= start) & (out['DateTime'] <= end + pd.Timedelta(days=1))
        out = out[mask]
    return out

df_filtered = apply_filters(df)

# -----------------------------
# Latest Snapshot
# -----------------------------
st.subheader("📊 Latest Snapshot per City")
latest_df = latest_per_city(df_filtered)
cols_show = [c for c in ['Country', 'City', 'AQI (US)', 'AQI Category',
                         'Main Pollutant (US)', 'Station Time (local)', 'DateTime']
             if c in latest_df.columns]
st.dataframe(latest_df[cols_show], use_container_width=True)

# -----------------------------
# Multi-city AQI line
# -----------------------------
if {'AQI (US)', 'DateTime'}.issubset(df_filtered.columns):
    st.subheader("🌫 AQI (US) Across Selected Cities")
    df_filtered['AQI (US)'] = pd.to_numeric(df_filtered['AQI (US)'], errors='coerce')
    df_plot = df_filtered.dropna(subset=['AQI (US)', 'DateTime'])
    if not df_plot.empty:
        fig = px.line(
            df_plot, x='DateTime', y='AQI (US)', color='City',
            markers=True, title='AQI (US) Variation'
        )
        st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# City-level Explorer
# -----------------------------
st.subheader("🏙 City Explorer")
if 'City' in df_filtered.columns and len(df_filtered['City'].unique()) > 0:
    city_pick = st.selectbox("Select a City", sorted(df_filtered['City'].unique()))
    city_df = df_filtered[df_filtered['City'] == city_pick].copy()

    metrics = numeric_columns(city_df)
    if metrics:
        metric = st.selectbox("Select Metric", metrics, index=0)
        city_df[metric] = pd.to_numeric(city_df[metric], errors='coerce')
        fig = px.line(city_df, x='DateTime', y=metric, title=f'{metric} in {city_pick}', markers=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No numeric IAQI/AQI fields found for this city.")

# -----------------------------
# Forecasts (optional)
# -----------------------------
with st.expander("📈 Forecasts (if available)"):
    if not latest_df.empty:
        rec = latest_df.iloc[0].to_dict()
        for field in ["Forecast PM25 Daily", "Forecast PM10 Daily", "Forecast UVI Daily"]:
            fdf = forecast_to_df(rec, field)
            if fdf is not None and not fdf.empty:
                fig = px.line(fdf, x="day", y="value", color="stat",
                              markers=True, title=f"{field} — {rec.get('City','')}")
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No forecast data found.")

# -----------------------------
# Station metadata
# -----------------------------
with st.expander("📍 Station Metadata"):
    meta_cols = [c for c in ['Station IDX', 'Station URL', 'Station Geo Lat', 'Station Geo Lon',
                             'Station Time (local)', 'Station Time TZ', 'Station Time ISO']
                 if c in latest_df.columns]
    if meta_cols:
        st.dataframe(latest_df[['City'] + meta_cols], use_container_width=True)
    else:
        st.info("No station metadata available.")

# Footer
st.caption("Data © World Air Quality Index Project (aqicn.org) • Dashboard by Siddharth P.")