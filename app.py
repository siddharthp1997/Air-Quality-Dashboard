import os
import streamlit as st
from pymongo import MongoClient
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from datetime import datetime
import pytz

# -----------------------------
# Env
# -----------------------------
load_dotenv()
ATLAS_URI = os.getenv('ATLAS_URI')
MONGO_DB = str(os.getenv('MONGO_DB'))
MONGO_COLLECTION = str(os.getenv('MONGO_COLLECTION'))

# -----------------------------
# Data access
# -----------------------------
@st.cache_resource
def get_collection():
    client = MongoClient(ATLAS_URI, tls=True)
    return client[MONGO_DB][MONGO_COLLECTION], client

@st.cache_data(ttl=300)
def fetch_data_from_mongodb():
    try:
        collection, client = get_collection()
        docs = list(collection.find())
        # don't close client; cache_resource keeps it
        return docs
    except Exception as e:
        st.error(f"Error connecting to MongoDB or fetching data: {str(e)}")
        return []

# -----------------------------
# Helpers
# -----------------------------
def parse_datetime_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure a combined DateTime column exists from 'Date' and 'Time' (EST in your loader).
    Coerce invalid rows to NaT so we can still plot around them.
    """
    if {'Date', 'Time'}.issubset(df.columns):
        dt = pd.to_datetime(df['Date'].astype(str) + ' ' + df['Time'].astype(str), errors='coerce')
        df = df.assign(DateTime=dt)
    elif 'Ingested At UTC' in df.columns:
        df = df.assign(DateTime=pd.to_datetime(df['Ingested At UTC'], errors='coerce'))
    else:
        # fallback: nothing to parse
        df = df.assign(DateTime=pd.NaT)
    return df

def numeric_columns(df: pd.DataFrame) -> list:
    """
    Return numeric columns, prioritizing AQI + iaqi_* fields and common metrics.
    """
    prefer_first = [
        'AQI (US)', 'AQI (CN)', 'Station Time (v)',
        'Temperature (°C)', 'Humidity (%)', 'Wind Speed (m/s)', 'Pressure (hPa)'
    ]
    # Convert plausible numeric columns
    candidate_cols = []
    for c in df.columns:
        if c.startswith('iaqi_') or c in prefer_first:
            candidate_cols.append(c)
    # make sure they are numeric
    out = []
    for c in candidate_cols:
        if c in df.columns:
            s = pd.to_numeric(df[c], errors='coerce')
            if s.notna().sum() > 0:
                out.append(c)
    # add any other numeric columns
    for c in df.select_dtypes(include=['number']).columns:
        if c not in out and c not in ['_id']:
            out.append(c)
    # stable order: prefer_first then iaqi_* then others
    out = sorted(set(out), key=lambda x: (0 if x in prefer_first else (1 if x.startswith('iaqi_') else 2), x))
    return out

def latest_per_city(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    sort_cols = [c for c in ['City', 'DateTime'] if c in df.columns]
    if not sort_cols:
        return df
    latest = df.sort_values(sort_cols).groupby('City', as_index=False).tail(1)
    # Clean '-1'/'Error' placeholders
    latest = latest.replace({'-1': pd.NA, 'Error': pd.NA})
    return latest

# -----------------------------
# App
# -----------------------------
st.set_page_config(page_title="Air Quality Dashboard", layout="wide")
st.title("Air Quality Dashboard")

data = fetch_data_from_mongodb()
if not data:
    st.error("Failed to fetch data from MongoDB or no data found.")
    st.stop()

df = pd.DataFrame(data)

# Optional: handle Weather Icons only if present (AQICN typically doesn't provide them)
icon_mapping = {
    '01d': ('https://raw.githubusercontent.com/siddharthp1997/Air-Quality-Dashboard/main/Images/01d.png', 'Clear sky (day)'),
    '01n': ('https://raw.githubusercontent.com/siddharthp1997/Air-Quality-Dashboard/main/Images/01n.png', 'Clear sky (night)'),
    '02d': ('https://raw.githubusercontent.com/siddharthp1997/Air-Quality-Dashboard/main/Images/02d.png', 'Few clouds (day)'),
    '02n': ('https://raw.githubusercontent.com/siddharthp1997/Air-Quality-Dashboard/main/Images/02n.png', 'Few clouds (night)'),
    '03d': ('https://raw.githubusercontent.com/siddharthp1997/Air-Quality-Dashboard/main/Images/03d.png', 'Scattered clouds'),
    '04d': ('https://raw.githubusercontent.com/siddharthp1997/Air-Quality-Dashboard/main/Images/04d.png', 'Broken clouds'),
    '09d': ('https://raw.githubusercontent.com/siddharthp1997/Air-Quality-Dashboard/main/Images/09d.png', 'Shower rain'),
    '10d': ('https://raw.githubusercontent.com/siddharthp1997/Air-Quality-Dashboard/main/Images/10d.png', 'Rain (day)'),
    '10n': ('https://raw.githubusercontent.com/siddharthp1997/Air-Quality-Dashboard/main/Images/10n.png', 'Rain (night)'),
    '11d': ('https://raw.githubusercontent.com/siddharthp1997/Air-Quality-Dashboard/main/Images/11d.png', 'Thunderstorm'),
    '13d': ('https://raw.githubusercontent.com/siddharthp1997/Air-Quality-Dashboard/main/Images/13d.png', 'Snow'),
    '50d': ('https://raw.githubusercontent.com/siddharthp1997/Air-Quality-Dashboard/main/Images/50d.png', 'Mist'),
}
if 'Weather Icon' in df.columns:
    df['Weather Icon URL'] = df['Weather Icon'].map(lambda x: icon_mapping[x][0] if x in icon_mapping else None)
    df['Weather Icon Description'] = df['Weather Icon'].map(lambda x: icon_mapping[x][1] if x in icon_mapping else 'Unknown')

# Parse times, tidy types
df = parse_datetime_cols(df)

# Sidebar filters
with st.sidebar:
    st.header("Filters")
    cities = sorted([c for c in df.get('City', pd.Series([])).dropna().unique()])
    selected_cities = st.multiselect("Cities", cities, default=cities[: min(5, len(cities))])
    date_range = st.date_input("Date range", [])
    # Optional: filter by AQI category if present
    aqi_cats = sorted([c for c in df.get('AQI Category', pd.Series([])).dropna().unique()])
    aqi_filter = st.multiselect("AQI Category", aqi_cats, default=[])

def apply_filters(df):
    out = df.copy()
    if selected_cities:
        out = out[out['City'].isin(selected_cities)]
    if 'AQI Category' in out.columns and aqi_filter:
        out = out[out['AQI Category'].isin(aqi_filter)]
    if date_range:
        # date_range may be single or pair
        if len(date_range) == 2:
            start, end = date_range
            if 'DateTime' in out.columns:
                mask = (out['DateTime'] >= pd.to_datetime(start)) & (out['DateTime'] <= pd.to_datetime(end) + pd.Timedelta(days=1))
                out = out[mask]
    return out

df_f = apply_filters(df)

# Latest snapshot table
st.subheader("Latest snapshot per city")
latest_df = latest_per_city(df_f)
cols_to_show = [c for c in ['City', 'AQI (US)', 'AQI Category', 'Main Pollutant (US)', 'Station Time (local)', 'DateTime'] if c in latest_df.columns]
if not cols_to_show:
    cols_to_show = [c for c in latest_df.columns if c not in ['_id']]
st.dataframe(latest_df[cols_to_show].sort_values(by=cols_to_show[0]), use_container_width=True)

# Multi-city AQI line
if 'AQI (US)' in df_f.columns and 'DateTime' in df_f.columns:
    st.subheader("AQI (US) across selected cities")
    aqi_df = df_f.dropna(subset=['AQI (US)', 'DateTime'])
    # coerce AQI to numeric if stored as strings
    aqi_df = aqi_df.assign(**{'AQI (US)': pd.to_numeric(aqi_df['AQI (US)'], errors='coerce')})
    fig_all = px.line(aqi_df, x='DateTime', y='AQI (US)', color='City', markers=True)
    fig_all.update_layout(xaxis_title='Date/Time', yaxis_title='AQI (US)')
    st.plotly_chart(fig_all, use_container_width=True)

# City-specific explorer
st.subheader("City explorer")
if 'City' in df_f.columns and len(df_f['City'].unique()) > 0:
    city_pick = st.selectbox("Select a city", sorted(df_f['City'].dropna().unique()))
    city_df = df_f[df_f['City'] == city_pick].copy()
else:
    city_pick = None
    city_df = pd.DataFrame()

if not city_df.empty:
    # Which metrics to plot?
    metrics = numeric_columns(city_df)
    if metrics:
        metric = st.selectbox("Metric", metrics, index=0)
        plot_df = city_df.copy()
        plot_df[metric] = pd.to_numeric(plot_df[metric], errors='coerce')
        plot_df = plot_df.dropna(subset=['DateTime', metric])
        fig = px.line(plot_df, x='DateTime', y=metric, title=f'{metric} in {city_pick}', markers=True)
        fig.update_layout(xaxis_title='Date/Time', yaxis_title=metric)
        # Optional: overlay icons only if present and selected metric is AQI
        if 'Weather Icon URL' in plot_df.columns and metric == 'AQI (US)':
            for _, row in plot_df.iterrows():
                if pd.notna(row.get('Weather Icon URL')):
                    fig.add_layout_image(
                        dict(
                            source=row['Weather Icon URL'],
                            x=row['DateTime'],
                            y=row[metric],
                            xref="x",
                            yref="y",
                            sizex=0.1,
                            sizey=0.1,
                            xanchor="center",
                            yanchor="middle"
                        )
                    )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No numeric IAQI or AQI fields found to plot for this city.")

# Station metadata (optional)
with st.expander("Station metadata (from AQICN)"):
    meta_cols = [c for c in ['Station IDX', 'Station URL', 'Station Geo Lat', 'Station Geo Lon', 'Station Time (local)', 'Station Time TZ'] if c in df_f.columns]
    if meta_cols:
        st.dataframe(latest_df[['City'] + [c for c in meta_cols if c in latest_df.columns]], use_container_width=True)
    else:
        st.write("No station metadata fields found.")

# Footer / attribution
st.caption(
    "Data © World Air Quality Index Project (aqicn.org). Results are real-time and may be unverified."
)