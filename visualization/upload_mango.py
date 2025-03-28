import geopandas as gpd
from pymongo import MongoClient
import json
import ast

LORRAINE_car = "lorraine_car.geojson"
ALSACE_car = "alsace_car.geojson"
BRETAGNE_car = "bretagne_car.geojson"
CENTRAL_LOIRE_car = "central_loire_car.geojson"
CORSE_car = "corse_car.geojson"
IDF_car = "idf_car.geojson"
PACA_car = "paca_car.geojson"
PAYS_LOIRE_car = "pays_loire_car.geojson"
REUN_car = "reun_car.geojson"

gdf = gpd.read_file(REGION_car)
records = json.loads(gdf.to_json())['features']

client = MongoClient("secret")
db = client.defaultdb   

#Collections
paca_collection = db["provence-alps-cote-dazur"]     
corse_collection = db["corse"]
bretagne_collection = db["bretagne"]
idf_collection = db["ile-de-france"]
reunion_collection = db["la-reunion"]
#martinique_collection = db["martinique"]
pays_loire_collection = db["pays-de-la-loire"]
central_loire_collection = db["central-val-de-loire"]
grand_est_collection = db["grand-est"]


#Extra tools to manipulate MongoDB
#----------------------------------
#db.drop_collection("geo-collection")
#----------------------------------
#grand_est_collection.insert_many(records)
#----------------------------------
#for doc in grand_est_collection.find():
#    loc_val = doc.get("properties", {}).get("locations")
#    if isinstance(loc_val, str):
#        try:
            # Convert the string representation to a Python object.
#            loc_array = ast.literal_eval(loc_val)
            # Ensure the conversion returned a list with at least one coordinate pair.
#            if isinstance(loc_array, list) and loc_array and isinstance(loc_array[0], list):
                # Convert to a GeoJSON Point using the first coordinate pair.
#                geojson_point = {"type": "Point", "coordinates": loc_array[0]}
#            else:
                # Fallback: use the converted value directly.
#                geojson_point = loc_array
#            result = grand_est_collection.update_one(
#                {"_id": doc["_id"]},
#                {"$set": {"properties.locations": geojson_point}}
#           )
#            print(f"Updated document {doc['_id']} with {geojson_point}")
#        except Exception as e:
#            print(f"Error converting document {doc['_id']}: {e}")

# After migration, attempt to create a 2dsphere index on the 'properties.locations' field.
#    index_name = grand_est_collection.create_index({"properties.locations": "2dsphere"})
#    print("Created index:", index_name)
#except Exception as e:
#    print("Error creating index:", e)