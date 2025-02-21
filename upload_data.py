import tkinter as tk
from tkinter import filedialog
import pandas as pd
import sys
import zipfile
import requests
import io
import openrouteservice
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point, Polygon, MultiPolygon, shape
import folium

API_KEY_ORS = "5b3ce3597851110001cf6248e1c21942e51e45a9ba5e6081a595bc3d"  # Replace with your actual key
client = openrouteservice.Client(key=API_KEY_ORS)

def accept_user_file():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(title="Select a file", filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt")])
    
    if not file_path:
        sys.exit()
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    elif file_path.endswith('.txt'):
        df = pd.read_csv(file_path, delimiter="\t")
    else:
        raise ValueError("Unsupported file format. Please provide a .csv or .txt file.")
    return df

def identify_lat_long(df):
    predefined_lat = ['latitude', 'lat', 'lattitude', 'latitide', 'latitude_fr', 'x']
    predefined_lon = ['longitude', 'long', 'lng', 'longtitude', 'longitude_fr', 'y']

    #latitude and longitude on the same column
    #datacheck for centroid
    #add for shapefiles
    #standardize the BPE and AtlasSante in a 

    lat_candidates = [col for col in df.columns if col.lower() in predefined_lat]
    lon_candidates = [col for col in df.columns if col.lower() in predefined_lon]

    if not lat_candidates:
        lat_candidates = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col]) and df[col].apply(lambda x: -90 <= float(x) <= 90 if pd.notna(x) else False).any()]
        
    if not lon_candidates:
        lon_candidates = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col]) and df[col].apply(lambda x: -180 <= float(x) <= 180 if pd.notna(x) else False).any()]

    if len(lat_candidates) == 1 and len(lon_candidates) == 1:
        df.rename(columns={lat_candidates[0]: 'latitude', lon_candidates[0]: 'longitude'}, inplace=True)
        
    else:
       print("Potential Latitude columns: ", lat_candidates)
       print("Potential Longitude columns: ", lon_candidates)

       lat_column = input("Please select the correct Latitude column from the options above: ")
       lon_column = input("Please select the correct Longitude column from the options above: ")

       if lat_column not in lat_candidates or lon_column not in lon_candidates:
           raise ValueError("Selected columns do not match the identified candidates.")

       df.rename(columns={lat_column: 'latitude', lon_column: 'longitude'}, inplace=True)

def download_bpe():
    zip_url = 'https://www.insee.fr/fr/statistiques/fichier/8217525/BPE23.zip'

    response = requests.get(zip_url)
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        file_name = z.namelist()[0]
        with z.open(file_name) as csv_file:
            df_bpe = pd.read_csv(csv_file, delimiter = ';')
    df_bpe.head()
    df_bpe["geometry"] = df_bpe.apply(lambda row: Point(row["LONGITUDE"], row["LATITUDE"]), axis=1)
    df_bpe = gpd.GeoDataFrame(df_bpe, geometry="geometry", crs="EPSG:4326")
    return df_bpe

def download_carreaus():
    #CARREAU_url = "https://www.insee.fr/fr/statistiques/fichier/6215138/Filosofi2017_carreaux_200m_shp.zip"

    shapefile_path_mart = "/Users/cpowers/Desktop/DEPP/In_Progress/EcoLab/GD4H/Filosofi2017_carreaux_200m_shp/Filosofi2017_carreaux_200m_mart.shp"
    shapefile_path_reun = "/Users/cpowers/Desktop/DEPP/In_Progress/EcoLab/GD4H/Filosofi2017_carreaux_200m_shp/Filosofi2017_carreaux_200m_reun.shp"
    shapefile_path_met = "/Users/cpowers/Desktop/DEPP/In_Progress/EcoLab/GD4H/Filosofi2017_carreaux_200m_shp/Filosofi2017_carreaux_200m_met.shp"
    
    carreaus_geo_mart = gpd.read_file(shapefile_path_mart)
    carreaus_geo_mart = carreaus_geo_mart.to_crs(epsg=4326)
    
    carreaus_geo_reun = gpd.read_file(shapefile_path_reun)
    carreaus_geo_reun = carreaus_geo_reun.to_crs(epsg=4326)
    
    #carreaus_geo_met = gpd.read_file(shapefile_path_met)
    #carreaus_geo_met = carreaus_geo_met.to_crs(epsg=4326)
    
    carreaus_geo = gpd.GeoDataFrame(pd.concat([carreaus_geo_mart, carreaus_geo_reun], ignore_index=True))
    
    carreaus_geo["longitude"] = carreaus_geo.geometry.centroid.x
    carreaus_geo["latitude"] = carreaus_geo.geometry.centroid.y

    return carreaus_geo

def map_carreaus_osrm(carr_geo, df):
    ORS_URL = "https://api.openrouteservice.org/v2/isochrones/"    
    transport_methods = ["driving-car", "cycling-regular", "foot-walking"]
    headers = {
    "Authorization": API_KEY_ORS,
    "Content-Type": "application/json"
    }
    
    for mode in transport_methods:
        carr_geo[f"{mode}_score"] = 0
    selected_indices = [1000, 1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009,1010,1011,1012,1013]
    
    for idx, row in carr_geo.iterrows():
    
        if idx in selected_indices:
            lat = row['latitude']
            lon = row['longitude']
        
            payload = {
            "locations": [[lon, lat]],
            "range": [900],
            "range_type": "time"
            }
        
            gdfs = []
            for mode in transport_methods:
                travel_url = f"{ORS_URL}{mode}"
                osrm_response = requests.post(travel_url, json=payload, headers=headers)
                if osrm_response.status_code != 200:
                    print(f"Error for {mode}: {osrm_response.text}")
                    carr_geo.at[idx, f"{mode}_score"] = None
                    continue
                isochrone_geojson = osrm_response.json()["features"][0]["geometry"]
                isochrone_polygon = shape(isochrone_geojson)
                isochrone_gdf = gpd.GeoDataFrame({"transport_mode": [mode], "geometry": [isochrone_polygon]}, crs="EPSG:4326")
                gdfs.append(isochrone_gdf)
                
                carr_geo.at[idx, f"{mode}_score"] = df.geometry.within(isochrone_polygon).sum()
                
            if gdfs:
                merged_isochrones_gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True))
            else:
                merged_isochrones_gdf = None            
            
            fig, ax = plt.subplots(figsize=(8, 8))
            merged_isochrones_gdf.plot(ax=ax, edgecolor="red", facecolor="none", linestyle="--", label="OSRM Polygon")
            ax.scatter(lon, lat, color="blue", marker="o", label="Centroid (Origin)")
            plt.legend()
            plt.show()
            
    for mode in transport_methods:
        fig, ax = plt.subplots(figsize=(10, 10))
        carr_geo[carr_geo.index.isin(selected_indices)].plot(column=f"{mode}_score", ax=ax, cmap="OrRd", edgecolor="black", legend=True, alpha=0.5)
        plt.title(f"Choropleth Map for {mode} Score")
        plt.show()
    return carr_geo

m = folium.Map(location=[2.3522, 48.8566], zoom_start=12)

#folium.GeoJson(isochrone_gdf, style_function=lambda x: {"color": "blue"}).add_to(m)

#df_user_add = accept_user_file()
#identify_lat_long(df_user_add)
df_bpe = download_bpe()
carreaus = download_carreaus()
carreaus = map_carreaus_osrm(carreaus, df_bpe)
gdf = gpd.GeoDataFrame(df_bpe, geometry="geometry", crs="EPSG:4326")
pd.set_option("display.max_columns", None)
m.save("isochrone_map.html")
        
m
        