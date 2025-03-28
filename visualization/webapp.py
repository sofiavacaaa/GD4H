from flask import Flask, jsonify, request, render_template, send_from_directory
from pymongo import MongoClient
import os

app = Flask(__name__)

# Replace with your actual MongoDB connection string and database name.
client = MongoClient("mongodb://user-rpowers-ensae:9o6lb8vmnxuay3h0fe5d@mongodb-0.mongodb-headless:27017,mongodb-1.mongodb-headless:27017/defaultdb")
db = client.defaultdb    # Replace with your actual database name

@app.route('/')
def index():
    # Renders the HTML file from the templates folder.
    return render_template('webapp.html')

@app.route('/favicon.ico')
def favicon():
    # Serve a favicon if you have one, otherwise this route prevents a 404 error.
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')

@app.route('/api/collections', methods=['GET'])
def get_collections():
    try:
        collections = db.list_collection_names()
        return jsonify(collections)
    except Exception as e:
        print("Error listing collections:", e)  # <-- Add a print to see the error
        return jsonify({"error": str(e)}), 500

@app.route('/api/geojson', methods=['GET'])
def get_geojson():
    collections_param = request.args.get('collections')
    if not collections_param:
        return "No collections specified", 400
    
    collection_names = collections_param.split(',')
    features = []
    
    try:
        for col_name in collection_names:
            collection = db[col_name]
            # Assuming each document is a valid GeoJSON feature.
            data = list(collection.find({}))
            features.extend(data)
            
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        return jsonify(geojson)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Use the PORT environment variable if available, default to 3000.
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=True)


