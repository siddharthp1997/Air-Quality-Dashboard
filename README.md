# 🌍 Air-Quality-Dashboard

This Python-based project uses the AQICN (World Air Quality Index) API to fetch real-time air quality data for major cities across the USA and India.
All data is stored in MongoDB Atlas and visualized using a Streamlit web dashboard, featuring interactive maps, graphs, and forecasts for AQI, pollutants, and weather metrics.
The project can be automated via GitHub Actions to continuously update readings and maintain live dashboards.


## ✨ Features
- **Global Coverage:** Fetches live air quality data from AQICN for top US and Indian cities.
- **MongoDB Integration:** Stores and updates city-level AQI data in MongoDB Atlas.
- **Interactive Streamlit Dashboard:**
	- Real-time AQI visualization by city and pollutant.
	- Dynamic maps for AQI and other IAQI metrics.
	- Forecast charts for PM2.5, PM10, and UVI.
	- Country → City dependent filters.
- **Automated Data Collection:** GitHub Actions or cron-based automation every few hours.
- **Secure Configuration:** Environment variables handle API tokens and database credentials.


## 🌐 Live Demo

Explore the live dashboard here:

👉 [**Air Quality Dashboard (Streamlit)**](https://air-quality-dashboard-nbx2nvgermtrpweyadgjqh.streamlit.app/?embed_options=show_toolbar,show_padding,show_footer,light_theme,show_colored_line)


## ⚙️ Usage

### 🧩 Prerequisites
- Python 3.11 or higher
- MongoDB Atlas account (for data storage)
- AQICN API token (from aqicn.org/data-platform/token/)
- GitHub repository (for hosting and automation)


### 🚀 Installation
1.	Clone the repository:

		git clone https://github.com/siddharthp1997/Air-Quality-Dashboard.git
		cd air-quality-dashboard


2.	Install dependencies:

		pip install -r requirements.txt


3.	Set up environment variables:

  	Create a .env file and add:

		ATLAS_URI=mongodb+srv://your-username:your-password@cluster0.mongodb.net/?retryWrites=true&w=majority
		API_TOKEN=your-aqicn-api-token
		MONGO_DB=air_quality
		MONGO_COLLECTION=city_data

Also add these as GitHub Secrets for automation workflows.

### 🧮 Data Loader

To fetch air quality data and store it in MongoDB:

		python fetch.py
		
- Queries AQICN API for all major Indian and US cities.
- Parses AQI, pollutant indices, and forecast arrays.
- Inserts records into MongoDB with timestamps and geolocation.


### 💻 Streamlit Dashboard

To visualize the data interactively:

		streamlit run app.py

#### Dashboard Features:
- Overview Tab: Filterable AQI table and top-10 cities chart.
- City Explorer: Metric-wise historical graphs.
- Maps: Interactive Mapbox views for AQI or any IAQI metric.
- Forecasts: Multi-day PM2.5, PM10, and UVI predictions per city.
- Metadata: Station coordinates, timestamps, and source info.

Default metric: AQI (US).


### 🔐 GitHub Secrets Configuration

This project uses GitHub Secrets to store sensitive environment variables securely.
These secrets are injected automatically into the GitHub Actions workflows when the automation runs (e.g., every 6 hours).

 Add the following secrets in your repository’s settings:

| Secret Name | Description | Example Value |
|--------------|-------------|----------------|
| `API_TOKEN` | Your AQICN API key used for fetching live air quality data. Obtain from [https://aqicn.org/data-platform/token/](https://aqicn.org/data-platform/token/). | `your-aqicn-api-token` |
| `ATLAS_URI` | The MongoDB Atlas connection URI. Used by the GitHub Action and Streamlit app to connect to your cluster. | `mongodb+srv://username:password@cluster0.mongodb.net/?retryWrites=true&w=majority` |
| `MONGO_DB` | The MongoDB database name where data will be stored. | `air_quality` |
| `MONGO_COLLECTION` | The MongoDB collection name (inside the DB) where documents are inserted. | `city_data` |
| `STREAMLIT_SECRET_KEY` *(optional)* | If deploying on Streamlit Cloud, you can store an app-level secret (like an API key or analytics token). | `your-secret-key` |


### 🧭 Where These Are Used

Environment Variables and Their Usage

| Variable | Used In | Purpose |
|-----------|----------|----------|
| `API_TOKEN` | `fetch.py` | Authenticates your requests to AQICN API. |
| `ATLAS_URI` | `fetch.py`, `app.py` | Connects to your MongoDB Atlas cluster for reading/writing AQI data. |
| `MONGO_DB` | `fetch.py`, `app.py` | Specifies which MongoDB database to read/write from. |
| `MONGO_COLLECTION` | `fetch.py`, `app.py` | Defines which MongoDB collection (e.g., `city_data`) stores your air-quality records. |
| `STREAMLIT_SECRET_KEY` | `app.py` *(optional)* | Enables secured Streamlit session state or analytics. |



### ⚙️ How to Add Secrets in GitHub
1. Go to your GitHub repository.
2. Click Settings → Secrets and variables → Actions.
3. Under “Repository Secrets”, click New repository secret.
4. Add each key-value pair above.
5. Once saved, these values are automatically available to your GitHub Actions workflows as environment variables.


### 🤖 GitHub Actions Workflow

This repo includes workflow YAMLs for automation:

- Data Fetch Workflow: Runs fetch.py every 6 hours to update MongoDB.
- Streamlit Deployment Workflow: Keeps your hosted dashboard in sync.


## 🪪 License

This project is licensed under the MIT License — see the LICENSE file for details.
