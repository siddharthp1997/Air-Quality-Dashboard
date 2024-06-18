import os
import streamlit as st
from pymongo import MongoClient
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# MongoDB connection settings
ATLAS_URI = os.getenv('ATLAS_URI')
MONGO_DB = str(os.getenv('MONGO_DB'))
MONGO_COLLECTION = str(os.getenv('MONGO_COLLECTION'))

# Function to fetch data from MongoDB
def fetch_data_from_mongodb():
    try:
        # Connect to MongoDB
        client = MongoClient(ATLAS_URI)
        db = client[MONGO_DB]
        collection = db[MONGO_COLLECTION]

        # Fetch data from MongoDB
        data = list(collection.find())

        # Close MongoDB connection
        client.close()

        return data

    except Exception as e:
        st.error(f"Error connecting to MongoDB or fetching data: {str(e)}")
        return None

# Fetch data from MongoDB
data = fetch_data_from_mongodb()

if data:
    # Convert data to DataFrame
    df = pd.DataFrame(data)

    # Weather icon mapping (example, you need to have these images)
    icon_mapping = {
        '01d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/01d.png', 'Clear sky (day)'),
        '01n': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/01n.png', 'Clear sky (night)'),
        '02d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/02d.png', 'Few clouds (day)'),
        '02n': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/02n.png', 'Few clouds (night)'),
        '03d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/03d.png', 'Scattered clouds'),
        '04d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/04d.png', 'Broken clouds'),
        '09d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/09d.png', 'Shower rain'),
        '10d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/10d.png', 'Rain (day time)'),
        '10n': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/10n.png', 'Rain (night time)'),
        '11d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/11d.png', 'Thunderstorm'),
        '13d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/13d.png', 'Snow'),
        '50d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/50d.png', 'Mist'),
    }

    # Check if 'Weather Icon' column exists in df
    if 'Weather Icon' in df.columns:
        # Replace Weather Icon codes with image URLs and descriptions
        df['Weather Icon URL'] = df['Weather Icon'].map(lambda x: icon_mapping[x][0] if x in icon_mapping else None)
        df['Weather Icon Description'] = df['Weather Icon'].map(lambda x: icon_mapping[x][1] if x in icon_mapping else 'Error')
    else:
        # If 'Weather Icon' column does not exist, handle gracefully or log an error
        st.error("Weather icon data not found in the database. Please ensure the data is correctly stored.")

    # Streamlit dashboard
    st.title("Air Quality Dashboard")

    # Show the latest data for each city as a table
    st.header("Latest Air Quality Data for Each City")

    # Check if there is data in the DataFrame
    if df.empty:
        st.write("No data available in the database.")
    else:
        latest_df = df.sort_values(by=['City', 'Date', 'Time']).groupby('City').tail(1)

        # Filter out rows with '-1' or 'Error'
        filtered_latest_df = latest_df.replace({'-1': pd.NA, 'Error': pd.NA}).dropna()

        # Display the latest data for each city in a pretty table
        st.table(filtered_latest_df[['City', 'State', 'Country', 'AQI (US)', 'Main Pollutant (US)', 
                                     'AQI (CN)', 'Main Pollutant (CN)', 'Temperature (°C)', 
                                     'Pressure (hPa)', 'Humidity (%)', 'Wind Speed (m/s)', 
                                     'Wind Direction (°)', 'Date', 'Time']])

    # Dropdown to select a city to see variation
    st.header("Variation of Air Quality Data Over Time")
    city = st.selectbox("Select a city", df['City'].unique(), index=0)
    city_df = df[df['City'] == city]

    # Display graphs for all columns with multiple readings per day
    for col in city_df.columns:
        if col not in ['_id', 'City', 'State', 'Country', 'Date', 'Time', 'Weather Icon', 'Weather Icon URL', 'Weather Icon Description']:  # Exclude non-numeric columns and icon columns
            filtered_city_df = city_df.replace({'-1': pd.NA, 'Error': pd.NA}).dropna(subset=[col])
            if not filtered_city_df.empty:
                fig = px.line(filtered_city_df, x='Time', y=col, title=f'{col} Variation in {city}', markers=True)
                fig.update_layout(xaxis_title='Time', yaxis_title=col)
                
                # Add weather icons to the plot
                for i, row in filtered_city_df.iterrows():
                    if row['Weather Icon URL'] and pd.notna(row['Weather Icon URL']):
                        fig.add_layout_image(
                            dict(
                                source=row['Weather Icon URL'],
                                x=row['Time'],
                                y=row[col],
                                xref="x",
                                yref="y",
                                sizex=0.1,
                                sizey=0.1,
                                xanchor="center",
                                yanchor="middle"
                            )
                        )
                st.plotly_chart(fig)
            else:
                st.write(f"No data available for {city}.")
else:
    st.error("Failed to fetch data from MongoDB. Please check your database connection.")
