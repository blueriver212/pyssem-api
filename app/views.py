from flask import request, jsonify
from app import app
from app import mongo
from flask_marshmallow import Marshmallow
from marshmallow import fields, ValidationError, validate
from bson.json_util import dumps
from bson.objectid import ObjectId
import json
from pyssem import pySSEM_model
from app import celery_app
import traceback

ma = Marshmallow(app)

# Create a simulation schema - which can then be tested against using marshmallow (essentially just creates an object)
class SimulationSchema(ma.Schema):
    simulation_name = fields.String(required=True)
    id = fields.String(required=True)
    owner = fields.String(required=True)
    description = fields.String(required=True)
    created = fields.DateTime(required=True)
    modified = fields.DateTime(required=True)
    scenario_properties = fields.Dict(keys=fields.String(), required=True)
    species = fields.Dict(keys=fields.String(), required=True)
    status = fields.String(required=True, validate=validate.OneOf(["running", "completed", "failed", "pending"]))

simulation_schema = SimulationSchema()

@app.route('/')
def index():
    return 'Hello, welcome to the pyssem API!'

@app.route('/simulation', methods=['POST'])
def create_simulation():
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400

    if simulation_schema.validate(data):
        return jsonify({"error": "Invalid data", "messages": simulation_schema.validate(data)}), 400
    
    existing_simulation = mongo.db.simulations.find_one({"id": data.get("id")})
    if existing_simulation:
        return jsonify({"error": "A simulation with this ID already exists"}), 409
    
    try:
        # data['status'] = 'running'
        # result = mongo.db.simulations.insert_one(data)
        # inserted_id = str(result.inserted_id)  # Convert ObjectId to string

        # Asynchronously run the simulation with Celery
        run_simulation.delay(data)

        return jsonify({"message": "Simulation created successfully"}), 201
    except Exception as e:
        return jsonify({"error": "Failed to create simulation", "message": str(traceback.format_exc())}), 500
    

@celery_app.task
def run_simulation(simulation_data):
    try:
        # Retrieve the document to update
        # simulation = mongo.db.simulations.find_one({"_id": ObjectId(simulation_id)})
        
        # if not simulation:
        #     print("Simulation not found.")
        #     return
        scenario_props = simulation_data['scenario_properties']
        species = simulation_data['species']
        
        model = pySSEM_model(**scenario_props)
        model.configure_species(species)
        
        # Run full model
        results = model.run_model()
        
        print("Simulation completed successfully.")
    except Exception as e:
        traceback.print_exc()

def search_simulations(query):
    simulations = mongo.db.simulations.find(query)
    simulations_list = list(simulations)  # Convert cursor to list
    if simulations_list:
        return jsonify([json.loads(dumps(sim)) for sim in simulations_list]), 200
    return jsonify({"error": "No simulations found"}), 404

@app.route('/simulation/id/<string:simulation_id>', methods=['GET'])
def get_simulation_by_id(simulation_id):
    return search_simulations({"id": simulation_id})

@app.route('/simulation/owner/<string:owner>', methods=['GET'])
def get_simulations_by_owner(owner):
    return search_simulations({"owner": owner})

@app.route('/simulation/name/<string:name>', methods=['GET'])
def get_simulations_by_name(name):
    return search_simulations({"simulation_name": name})

@app.route('/simulation/status/<string:status>', methods=['GET'])
def get_simulations_by_status(status):
    return search_simulations({"status": status})

@app.route('/deleteall', methods=['GET'])
def delete_all_simulations():
    try:
        # Delete all instances in the database
        result = mongo.db.simulations.delete_many({})
        return jsonify({"message": f"{result.deleted_count} simulations deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": "Failed to delete simulations", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)