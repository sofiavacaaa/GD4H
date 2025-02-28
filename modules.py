import requests
import zipfile
import geopandas as gpd
import pandas as pd
import io
from shapely.geometry import Point, Polygon, MultiPolygon, shape
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def download_carreaus(epsg):
    # Charger uniquement les carreaux pour la Martinique
    shapefile_path_mart = r"D:\ECOLAB\GD4H\Filosofi2017_carreaux_200m_shp\Filosofi2017_carreaux_200m_shp\Filosofi2017_carreaux_200m_mart.shp"
    carreaus_geo = gpd.read_file(shapefile_path_mart)
    carreaus_geo = carreaus_geo.to_crs(epsg=epsg)
    carreaus_geo["longitude"] = carreaus_geo.geometry.centroid.x
    carreaus_geo["latitude"] = carreaus_geo.geometry.centroid.y
    return carreaus_geo


def download_bpe():
    # File paths
    geojson_path = os.path.join('data', 'insee', 'bpe_geojson.geojson')
    csv_path = os.path.join('data', 'insee', 'bpe.csv')

    try:
        # Check if GeoJSON file exists
        if os.path.exists(geojson_path):
            logging.info(f"GeoJSON file already exists at {geojson_path}. Loading existing file.")
            df_bpe = gpd.read_file(geojson_path)
        else:
            logging.info("GeoJSON file not found. Downloading and processing CSV data.")

            # Download and extract ZIP file
            zip_url = 'https://www.insee.fr/fr/statistiques/fichier/8217525/BPE23.zip'
            response = requests.get(zip_url)
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                file_name = z.namelist()[0]  # Get the first file in the ZIP archive
                with z.open(file_name) as csv_file:
                    df_bpe = pd.read_csv(csv_file, delimiter=';')

            # Save CSV locally
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            df_bpe.to_csv(csv_path, index=False)
            logging.info(f"CSV file saved at {csv_path}")

            # Create geometry column (Vectorized)
            df_bpe = gpd.GeoDataFrame(
                df_bpe, 
                geometry=gpd.points_from_xy(df_bpe["LONGITUDE"], df_bpe["LATITUDE"]),
                crs="EPSG:32620"
            )


            # Save as GeoJSON
            os.makedirs(os.path.dirname(geojson_path), exist_ok=True)
            df_bpe.to_file(geojson_path, driver="GeoJSON")
            logging.info(f"GeoJSON file saved at {geojson_path}")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
    return df_bpe