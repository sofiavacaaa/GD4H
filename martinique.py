import tkinter as tk 
from tkinter import filedialog
import pandas as pd
import sys
import zipfile
import requests
import io
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point, Polygon, MultiPolygon, shape
import folium

# Définir l'URL de base de votre instance locale d'ORS
ORS_URL = "http://localhost:8082/ors/isochrones/"

def download_bpe():
    zip_url = 'https://www.insee.fr/fr/statistiques/fichier/8217525/BPE23.zip'
    response = requests.get(zip_url)
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        file_name = z.namelist()[0]
        with z.open(file_name) as csv_file:
            df_bpe = pd.read_csv(csv_file, delimiter=';')
    # Création de la géométrie à partir des colonnes LONGITUDE et LATITUDE
    df_bpe["geometry"] = df_bpe.apply(lambda row: Point(row["LONGITUDE"], row["LATITUDE"]), axis=1)
    df_bpe = gpd.GeoDataFrame(df_bpe, geometry="geometry", crs="EPSG:4326")
    return df_bpe

def split_by_dom(df_bpe):
    df_filtered = df_bpe.loc[
        df_bpe["DOM"].isin(["D", "F", "C"]) |
        df_bpe["TYPEQU"].isin(["E108", "E109"]) |
        df_bpe["SDOM"].isin(["A1", "B1", "B2"])
    ].copy()
    df_filtered["ID"] = range(1, len(df_filtered) + 1)
    cols_to_keep = [
        "ID", "AN", "NOMRS", "CNOMRS", "NUMVOIE", "INDREP", "TYPVOIE", "LIBVOIE",
        "CADR", "LIBCOM", "CODPOS", "DEPCOM", "REG", "DOM", "SDOM", "TYPEQU", "SIRET", 
        "LAMBERT_X", "LAMBERT_Y", "LONGITUDE", "LATITUDE"
    ]
    existing_cols = [col for col in cols_to_keep if col in df_filtered.columns]
    df_filtered = df_filtered[existing_cols].copy()

    def process_region(df, region_code):
        df_region = df[df["DEPCOM"].astype(str).str.startswith(region_code)].copy()
        df_d_dom = df_region[df_region["SDOM"].isin(["D1", "D3", "D4", "D6", "D7"])].copy()

        def combine_typequ(series):
            unique_vals = series.dropna().unique()
            return ", ".join(map(str, unique_vals))

        if not df_d_dom.empty:
            df_d_dom["TYPEQU"] = df_d_dom.groupby(["NOMRS", "LIBCOM", "DOM", "LIBVOIE"])["TYPEQU"].transform(combine_typequ)
            df_unique_D_dom = df_d_dom.drop_duplicates(subset=["NOMRS", "LIBCOM", "DOM", "LIBVOIE"])
        else:
            df_unique_D_dom = df_d_dom

        df_dom_rest = df_region[~df_region["SDOM"].isin(["D1", "D3", "D4", "D6", "D7"])]
        df_unique = pd.concat([df_dom_rest, df_unique_D_dom], ignore_index=True)
        return df_unique

    martinique_df = process_region(df_filtered, "972")
    reunion_df = process_region(df_filtered, "974")
    
    return martinique_df, reunion_df

def download_carreaus():
    # Charger uniquement les carreaux pour la Martinique
    shapefile_path_mart = r"D:\ECOLAB\GD4H\Filosofi2017_carreaux_200m_shp\Filosofi2017_carreaux_200m_shp\Filosofi2017_carreaux_200m_mart.shp"
    carreaus_geo = gpd.read_file(shapefile_path_mart)
    carreaus_geo = carreaus_geo.to_crs(epsg=4326)
    carreaus_geo["longitude"] = carreaus_geo.geometry.centroid.x
    carreaus_geo["latitude"] = carreaus_geo.geometry.centroid.y
    return carreaus_geo

def map_carreaus_osrm(carr_geo, df):
    # Puisque vous utilisez ORS en local, nous n'utilisons pas de clé API
    headers = {
        "Content-Type": "application/json"
    }
    
    transport_methods = ["driving-car", "cycling-regular", "foot-walking"]
    for mode in transport_methods:
        carr_geo[f"{mode}_score"] = 0

    # Parcourir toutes les entités (pour la Martinique)
    for idx, row in carr_geo.iterrows():
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
                print(f"Erreur pour {mode}: {osrm_response.text}")
                carr_geo.at[idx, f"{mode}_score"] = None
                continue
            isochrone_geojson = osrm_response.json()["features"][0]["geometry"]
            isochrone_polygon = shape(isochrone_geojson)
            
            # Optionnel : découper l'isochrone avec la frontière de la Martinique
            try:
                martinique_boundary = gpd.read_file(r"D:\ECOLAB\GD4H\Filosofi2017_carreaux_200m_shp\Filosofi2017_carreaux_200m_shp\Filosofi2017_carreaux_200m_mart.shp")
                martinique_boundary = martinique_boundary.to_crs(epsg=4326)
                isochrone_polygon = isochrone_polygon.intersection(martinique_boundary.unary_union)
            except Exception as e:
                print("Échec du découpage à la frontière de la Martinique :", e)
            
            isochrone_gdf = gpd.GeoDataFrame({"transport_mode": [mode], "geometry": [isochrone_polygon]}, crs="EPSG:4326")
            gdfs.append(isochrone_gdf)
            
            # Calculer le score : nombre de points BPE dans l'isochrone
            carr_geo.at[idx, f"{mode}_score"] = df.geometry.within(isochrone_polygon).sum()
            
        if gdfs:
            merged_isochrones_gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True))
        else:
            merged_isochrones_gdf = None            
        
        # Affichage de l'isochrone et du centroïde
        fig, ax = plt.subplots(figsize=(8, 8))
        if merged_isochrones_gdf is not None:
            merged_isochrones_gdf.plot(ax=ax, edgecolor="red", facecolor="none", linestyle="--", label="Isochrone")
        ax.scatter(lon, lat, color="blue", marker="o", label="Centroid (Origine)")
        plt.legend()
        plt.show()
        
    # Affichage des cartes choroplèth pour chaque mode
    for mode in transport_methods:
        fig, ax = plt.subplots(figsize=(10, 10))
        carr_geo.plot(column=f"{mode}_score", ax=ax, cmap="OrRd", edgecolor="black", legend=True, alpha=0.5)
        plt.title(f"Carte Choroplèth pour {mode}")
        plt.show()
    return carr_geo

# Création d'une carte Folium centrée sur la Martinique
m = folium.Map(location=[14.6415, -61.0242], zoom_start=10)

# Chargement et traitement des données
df_bpe = download_bpe()
carreaus = download_carreaus()
carreaus = map_carreaus_osrm(carreaus, df_bpe)
gdf = gpd.GeoDataFrame(df_bpe, geometry="geometry", crs="EPSG:4326")
pd.set_option("display.max_columns", None)

# Sauvegarde de la carte isochrone au format HTML
m.save("isochrone_map.html")

