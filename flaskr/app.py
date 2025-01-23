from flask import Flask, request, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import re
from datetime import datetime
from threading import Thread, Event
import time
import requests

app = Flask(__name__)

BASE_URL = "http://127.0.0.1:5000"
client = MongoClient('mongodb://localhost:27017/')
db = client['travel_registration_system']
clients_collection = db['clients']
vehicles_collection = db['vehicles']
journeys_collection = db['journeys']
journey_points_collection = db["journey_points"]

## Klientų kolekcija
clients_collection.create_index("email", unique=True)  # Indeksas pagal el. paštą, užtikrinant unikalumą
clients_collection.create_index("_id")  # Indeksas pagal pagrindinį raktą (_id) (nebūtina)

# Transporto priemonių kolekcija
vehicles_collection.create_index("vin", unique=True)  # Indeksas pagal VIN, užtikrinant unikalumą
vehicles_collection.create_index("client_id")  # Indeksas pagal klientų ID

# Kelionių kolekcija
journeys_collection.create_index("_id")  # Indeksas pagal pagrindinį raktą (_id)
journeys_collection.create_index("vehicle_id")  # Indeksas pagal transporto priemonės ID
journeys_collection.create_index([("start_time", 1), ("end_time", 1)])  # Indeksas pagal kelionės pradžios ir pabaigos laiką

# Kelionės taškų kolekcija
journey_points_collection.create_index("journey_id")  # Indeksas pagal kelionės ID
journey_points_collection.create_index([("latitude", 1), ("longitude", 1)])  # Sudėtinis indeksas pagal platumą ir ilgumą


def is_valid_email(email):
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_regex, email) is not None

# 1. Registruoti naują klientą
@app.route('/clients', methods=['PUT'])
def register_client():
    try:
        data = request.get_json()

        # Įvestis
        required_fields = ["first_name", "last_name", "email", "birth_date"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Trūksta duomenų: {field}"}), 400
        if not is_valid_email(data["email"]):
            return jsonify({"error": "Netinkamas pašto formatas."})
        if clients_collection.find_one({"email": data["email"]}):
            return jsonify({"error": "Klientas jau egzistuoja!"}), 400
        # birth_date paverčiama į datetime tipą
        try:
            birth_date = datetime.strptime(data["birth_date"], "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Netinkamas datos formatas. Naudokite YYYY-MM-DD."}), 400

        # client data
        client_data = {
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "email": data["email"],
            "birth_date": birth_date
        }
        # client data pridedama į duomenų bazę
        result = clients_collection.insert_one(client_data)

        return jsonify({"message": "Klientas užregistruotas sėkmingai", "client_id": str(result.inserted_id)}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 2. Gauti kliento duomenis
@app.route('/clients/<string:clientId>', methods=['GET'])
def get_client_details(clientId):
    try:
        if not ObjectId.is_valid(clientId):
            return jsonify({"error": "Netinkamas client_id formatas!"}), 400

        # Gauti kliento duomenis iš duomenų bazės
        client_data = clients_collection.find_one({"_id": ObjectId(clientId)})

        if not client_data:
            return jsonify({"error": "Klientas nerastas"}), 404

        response = {
            "id": str(client_data["_id"]),
            "first_name": client_data["first_name"],
            "last_name": client_data["last_name"],
            "email": client_data["email"],
            "birth_date": client_data["birth_date"].strftime("%Y-%m-%d")
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 3. Registruoti transporto priemonę 
@app.route("/vehicles", methods=["PUT"])
def register_vehicle():
    data = request.json
    # Konvertuojamas client_id iš string į ObjectId
    try:
        client_id = ObjectId(data["client_id"])
    except Exception:
        return jsonify({"error": "Neteisingas client_id formatas!"}), 400

    # Tikrinama, ar klientas egzistuoja
    if not clients_collection.find_one({"_id": client_id}):
        return jsonify({"error": "Klientas nerastas!"}), 400

    # Tikrinama, ar transporto priemonė su tokiu VIN jau egzistuoja
    if vehicles_collection.find_one({"vin": data["vin"]}):
        return jsonify({"error": "Transporto priemonė su šiuo VIN jau egzistuoja!"}), 400

    # Pridedama transporto priemonė į duomenų bazę
    vehicle_data = {
        "client_id": client_id,
        "model": data["model"],
        "manufacturer": data["manufacturer"],
        "license_plate": data["license_plate"],
        "vin": data["vin"],
        "year": data["year"]
    }
    result = vehicles_collection.insert_one(vehicle_data)
    return jsonify({"message": "Transporto priemonė užregistruota sėkmingai!", "id": str(result.inserted_id)})


# 4. Gauti transporto priemonės duomenis
@app.route("/clients/<client_id>/vehicles", methods=["GET"])
def get_vehicles_by_client(client_id):
    # Konvertuojamas client_id iš string į ObjectId
    try:
        client_id_object = ObjectId(client_id)
    except Exception:
        return jsonify({"error": "Neteisingas client_id formatas!"}), 400

    # Tikrinama, ar klientas egzistuoja
    if not clients_collection.find_one({"_id": client_id_object}):
        return jsonify({"error": "Klientas nerastas!"}), 400

    # Gaunamos visos transporto priemonės, susietos su klientu
    vehicles = list(vehicles_collection.find({"client_id": client_id_object}))
    # Konvertuojamas ObjectId į string JSON serializavimui
    for vehicle in vehicles:
        vehicle["_id"] = str(vehicle["_id"])
        vehicle["client_id"] = str(vehicle["client_id"])
    return jsonify(vehicles)

# Signalas sustabdyti kelionę
stop_signal = Event()

# 5. Pradėti naują kelionę
@app.route("/journeys", methods=["PUT"])
def start_journey():
    try:
        data = request.json

        # Tikrinama, ar būtini laukai yra pateikti
        if "vehicle_id" not in data or "interval" not in data:
            return jsonify({"error": "Trūksta laukelių: vehicle_id arba interval"}), 400

        # Tikrinamas intervalas (mažiausiai 5 sekundės)
        interval = int(data["interval"])
        if interval < 5:
            return jsonify({"error": "Intervalas turi būti ne mažesnis kaip 5 sekundės!"}), 400

        # Tikrinamas vehicle_id formatas
        try:
            vehicle_id = ObjectId(data["vehicle_id"])
        except Exception:
            return jsonify({"error": "Neteisingas vehicle_id formatas!"}), 400

        # Tikrinama, ar transporto priemonė egzistuoja
        if not vehicles_collection.find_one({"_id": vehicle_id}):
            return jsonify({"error": "Transporto priemonė nerasta!"}), 404

        # Sukuriamas naujas kelionės įrašas
        journey_data = {
            "vehicle_id": vehicle_id,
            "start_time": datetime.now(),
            "is_completed": False,
            "interval": interval
        }
        result = journeys_collection.insert_one(journey_data)

        # Pradedama užduotis koordinatėms registruoti
        journey_id = result.inserted_id
        thread = Thread(target=log_coordinates_periodically, args=(str(journey_id), interval))
        thread.start()

        return jsonify({"message": "Kelionė pradėta!", "id": str(journey_id)}), 201

    except Exception as e:
        return jsonify({"error": f"Serverio klaida: {str(e)}"}), 500


# 6. Registruoti transporto priemonės koordinates
@app.route("/journeys/<string:journey_id>/coordinates", methods=["POST"])
def log_coordinates(journey_id):
    try:
        # Tikrinamas journey_id formatas
        if not ObjectId.is_valid(journey_id):
            return jsonify({"error": "Neteisingas journey_id formatas!"}), 400

        # Tikrinama, ar kelionė egzistuoja ir nėra baigta
        journey = journeys_collection.find_one({"_id": ObjectId(journey_id), "is_completed": False})
        if not journey:
            return jsonify({"error": "Kelionė nerasta arba jau baigta!"}), 404

        # Gauti koordinates iš užklausos
        data = request.json
        required_fields = ["latitude", "longitude", "timestamp"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Trūksta laukelio: {field}"}), 400

        # Įrašomos koordinatės į duomenų bazę
        coordinates = {
            "journey_id": ObjectId(journey_id),
            "timestamp": datetime.strptime(data["timestamp"], "%Y-%m-%dT%H:%M:%S"),
            "latitude": float(data["latitude"]),
            "longitude": float(data["longitude"])
        }
        journey_points_collection.insert_one(coordinates)

        # Konvertuojama atsakymui
        response = {
            "message": "Koordinatės sėkmingai įkeltos!",
            "data": {
                "journey_id": journey_id,
                "timestamp": data["timestamp"],
                "latitude": coordinates["latitude"],
                "longitude": coordinates["longitude"]
            }
        }
        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": f"Serverio klaida: {str(e)}"}), 500



# Periodiškai kviečiama koordinatės įkėlimo funkcija
def log_coordinates_periodically(journey_id, interval):
    try:
        print(f"Pradedamas periodinis užkrovimas kelionei {journey_id} su intervalu {interval} sekundžių.")

        while not stop_signal.is_set():
            # Tikrinama, ar kelionė vis dar vyksta
            journey = journeys_collection.find_one({"_id": ObjectId(journey_id)})
            if not journey or journey.get("is_completed"):
                print(f"Kelionė {journey_id} baigta. Periodinis užkrovimas sustabdytas.")
                break

            # Generuojamos atsitiktinės koordinatės (simuliacija)
            latitude = round(54.6872 + (time.time() % 0.01), 6)
            longitude = round(25.2797 + (time.time() % 0.01), 6)
            timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

            # Siunčiama į endpoint'ą /journeys/{journey_id}/coordinates
            url = f"{BASE_URL}/journeys/{journey_id}/coordinates"
            input = {
                "latitude": latitude,
                "longitude": longitude,
                "timestamp": timestamp
            }
            response = requests.post(url, json=input)

            if response.status_code == 200:
                print(f"Koordinatės įkeltos kelionei {journey_id}: {input}")
            else:
                print(f"Klaida siunčiant koordinates: {response.json()}")

            # Palaukiama nustatytą intervalą
            time.sleep(interval)

    except Exception as e:
        print(f"Klaida periodinio užkrovimo metu: {str(e)}")

# 6. Gauti kelionės informaciją (naudojant pipeline)
@app.route("/journeys/<string:journey_id>", methods=["GET"])
def get_journey_details(journey_id):
    try:
        # Tikrinamas journey_id formatas
        if not ObjectId.is_valid(journey_id):
            return jsonify({"error": "Neteisingas journey_id formatas!"}), 400

        # Pipeline skirtas apskaičiuoti bendrą atstumą ir taškų sąrašą
        pipeline = [
    {"$match": {"_id": ObjectId(journey_id)}},
    {
        "$lookup": {
            "from": "journey_points",
            "localField": "_id",
            "foreignField": "journey_id",
            "as": "points"
        }
    },
    {
        "$project": {
            "vehicle_id": {"$toString": "$vehicle_id"},
            "start_time": 1,
            "end_time": 1,
            "points": {
                "$cond": {
                    "if": {"$isArray": "$points"},
                    "then": "$points",
                    "else": []
                }
            }
        }
    },
    {
        "$addFields": {
            "total_distance": {
                "$reduce": {
                    "input": {"$range": [0, {"$size": "$points"}]},
                    "initialValue": 0,
                    "in": {
                        "$add": [
                            "$$value",
                            {
                                "$cond": {
                                    "if": {"$and": [{"$gt": ["$$this", 0]}, {"$gt": ["$$this", 1]}]},
                                    "then": {
                                        "$let": {
                                            "vars": {
                                                "prev": {"$arrayElemAt": ["$points", {"$subtract": ["$$this", 1]}]},
                                                "current": {"$arrayElemAt": ["$points", "$$this"]}
                                            },
                                            "in": {
                                                "$sqrt": {
                                                    "$add": [
                                                        {
                                                            "$pow": [
                                                                {"$subtract": ["$$current.latitude", "$$prev.latitude"]},
                                                                2
                                                            ]
                                                        },
                                                        {
                                                            "$pow": [
                                                                {"$subtract": ["$$current.longitude", "$$prev.longitude"]},
                                                                2
                                                            ]
                                                        }
                                                    ]
                                                }
                                            }
                                        }
                                    },
                                    "else": 0
                                }
                            }
                        ]
                    }
                }
            },
            "total_duration": {
                "$divide": [
                    {"$subtract": ["$end_time", "$start_time"]}, 60000
                ]
            }
        }
    },
    {
        "$project": {
            "_id": 0,
            "journey_id": {"$toString": "$_id"},
            "vehicle_id": 1,
            "start_time": 1,
            "end_time": 1,
            "total_duration": 1,
            "total_distance": 1
        }
    }
]

        # Vykdomas pipeline ir gaunamas rezultatas
        result = list(journeys_collection.aggregate(pipeline))

        if not result:
            return jsonify({"error": "Kelionė nerasta!"}), 404

        return jsonify(result[0]), 200

    except Exception as e:
        return jsonify({"error": f"Serverio klaida: {str(e)}"}), 500


# 7. Gauti bendrą konkrečios transporto priemonės kelionių statistiką (naudojant pipeline)
@app.route("/vehicles/<string:vehicle_id>/statistics", methods=["GET"])
def get_vehicle_statistics(vehicle_id):
    try:
        # vehicle_id formatas
        if not ObjectId.is_valid(vehicle_id):
            return jsonify({"error": "Neteisingas vehicle_id formatas!"}), 400

        pipeline = [
            # journeys pagal atitinkamą vehicle_id
            {"$match": {"vehicle_id": ObjectId(vehicle_id)}},
            {
                "$lookup": {
                    "from": "journey_points",  # Sujungiama su journey_points
                    "localField": "_id",      # journey _id atitinka su journey_points.journey_id
                    "foreignField": "journey_id",
                    "as": "points"
                }
            },
            {
                "$addFields": {
                    # Užtikrinama, kad taškai (points) visada yra masyve
                    "points": {
                        "$cond": {
                            "if": {"$isArray": "$points"},
                            "then": "$points",
                            "else": []
                        }
                    }
                }
            },
            {
                "$addFields": {
                    # Skaičiuojama bendras atstumas kiekvienai kelionei
                    "total_distance": {
                        "$reduce": {
                            "input": {"$range": [1, {"$size": "$points"}]},
                            "initialValue": 0,
                            "in": {
                                "$add": [
                                    "$$value",
                                    {
                                        "$let": {
                                            "vars": {
                                                "prev": {"$arrayElemAt": ["$points", {"$subtract": ["$$this", 1]}]},
                                                "current": {"$arrayElemAt": ["$points", "$$this"]}
                                            },
                                            "in": {
                                                "$sqrt": {
                                                    "$add": [
                                                        {"$pow": [{"$subtract": ["$$current.latitude", "$$prev.latitude"]}, 2]},
                                                        {"$pow": [{"$subtract": ["$$current.longitude", "$$prev.longitude"]}, 2]}
                                                    ]
                                                }
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    },
                    # Skaičiuojamas bendras laikas kiekvienai kelionei
                    "total_duration": {
                        "$cond": {
                            "if": {"$and": ["$end_time", "$start_time"]},
                            "then": {
                                "$divide": [
                                    {"$subtract": ["$end_time", "$start_time"]}, 60000  # Konvertuojama ms į minutes
                                ]
                            },
                            "else": 0
                        }
                    }
                }
            },
            {
                "$group": {
                    "_id": "$vehicle_id",
                    "total_distance": {"$sum": "$total_distance"},  # Bendra atstumų suma
                    "total_duration": {"$sum": "$total_duration"}   # Bendra laiko trukmė
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "vehicle_id": {"$toString": "$_id"},
                    "total_distance_km": "$total_distance",
                    "total_duration_minutes": "$total_duration"
                }
            }
        ]

        # Vydomas pipeline
        result = list(db.journeys.aggregate(pipeline))

        if not result:
            return jsonify({"error": "Statistika nerasta arba transporto priemonė neturi kelionių!"}), 404

        return jsonify(result[0]), 200

    except Exception as e:
        return jsonify({"error": f"Serverio klaida: {str(e)}"}), 500

    
# 8. Baigti kelionę
@app.route("/journeys/<journey_id>/end", methods=["PUT"])
def end_journey(journey_id):
    try:
        # Tikrinamas journey_id formatas
        if not ObjectId.is_valid(journey_id):
            return jsonify({"error": "Neteisingas journey_id formatas!"}), 400

        # Konvertuojamas journey_id į ObjectId
        journey_id_object = ObjectId(journey_id)

        # Tikrinama, ar kelionė egzistuoja ir nėra baigta
        journey = journeys_collection.find_one({"_id": journey_id_object, "is_completed": False})
        if not journey:
            return jsonify({"error": "Kelionė nerasta arba jau baigta!"}), 404

        # Pažymima, kad kelionė baigta
        update_result = journeys_collection.update_one(
            {"_id": journey_id_object},
            {"$set": {"end_time": datetime.now(), "is_completed": True}}
        )

        # Tikrinama, ar atnaujinimas pavyko
        if update_result.modified_count == 0:
            return jsonify({"error": "Nepavyko užbaigti kelionės. Bandykite dar kartą!"}), 500

        return jsonify({"message": "Kelionė sėkmingai baigta!"}), 200

    except Exception as e:
        return jsonify({"error": f"Serverio klaida: {str(e)}"}), 500


#9. Išvalyti duomenų bazę
@app.route('/cleanup', methods=['POST'])
def flush_all():
    try:
        client.drop_database('travel_registration_system')
        return jsonify({'message': 'Duomenų bazė išvalyta'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

clients_collection.create_index(
    [("first_name", "text"), ("last_name", "text"), ("email", "text")],
    default_language="english"
)

vehicles_collection.create_index(
    [("model", "text"), ("manufacturer", "text"), ("license_plate", "text")],
    default_language="english"
)

journeys_collection.create_index(
    [("description", "text")],
    default_language="english"
)

@app.route('/search', methods=['GET'])
def full_text_search():
    try:
        query = request.args.get('q')

        if not query:
            return jsonify({"error": "Search query is missing"}), 400

        # Aggregation pipelines for full-text search
        client_pipeline = [
            {"$match": {"$text": {"$search": query}}},
            {"$addFields": {"score": {"$meta": "textScore"}}},
            {"$sort": {"score": -1}},
            {"$project": {"_id": 1, "first_name": 1, "last_name": 1, "email": 1, "score": 1}}
        ]

        vehicle_pipeline = [
            {"$match": {"$text": {"$search": query}}},
            {"$addFields": {"score": {"$meta": "textScore"}}},
            {"$sort": {"score": -1}},
            {"$project": {"_id": 1, "model": 1, "manufacturer": 1, "license_plate": 1, "client_id": 1, "score": 1}}
        ]

        journey_pipeline = [
            {"$match": {"$text": {"$search": query}}},
            {"$addFields": {"score": {"$meta": "textScore"}}},
            {"$sort": {"score": -1}},
            {"$project": {"_id": 1, "description": 1, "vehicle_id": 1, "score": 1}}
        ]

        client_results = list(clients_collection.aggregate(client_pipeline))
        vehicle_results = list(vehicles_collection.aggregate(vehicle_pipeline))
        journey_results = list(journeys_collection.aggregate(journey_pipeline))

        # ObjectId verčiamas į string
        for client in client_results:
            client["_id"] = str(client["_id"])

        for vehicle in vehicle_results:
            vehicle["_id"] = str(vehicle["_id"])
            vehicle["client_id"] = str(vehicle.get("client_id", ""))

        for journey in journey_results:
            journey["_id"] = str(journey["_id"])
            journey["vehicle_id"] = str(journey.get("vehicle_id", ""))

        if ObjectId.is_valid(query):
            # Pagal journey_id
            journey_results_by_id = list(journeys_collection.aggregate([
                {"$match": {"_id": ObjectId(query)}},
                {"$project": {"_id": 1, "description": 1, "vehicle_id": 1}}
            ]))

            for journey in journey_results_by_id:
                journey["_id"] = str(journey["_id"])
                journey["vehicle_id"] = str(journey.get("vehicle_id", ""))

            journey_results.extend(journey_results_by_id)

            # Pagal vehicle_id
            journey_results_by_vehicle_id = list(journeys_collection.aggregate([
                {"$match": {"vehicle_id": ObjectId(query)}},
                {"$project": {"_id": 1, "description": 1, "vehicle_id": 1}}
            ]))

            for journey in journey_results_by_vehicle_id:
                journey["_id"] = str(journey["_id"])
                journey["vehicle_id"] = str(journey.get("vehicle_id", ""))

            journey_results.extend(journey_results_by_vehicle_id)

        return jsonify({
            "clients": client_results,
            "vehicles": vehicle_results,
            "journeys": journey_results
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    try:
        print("Serveris paleistas...")
        app.run(debug=True, use_reloader=False, threaded=True, port=5000)
    except KeyboardInterrupt:
        print("Serveris stabdomas...")
        stop_signal.set()