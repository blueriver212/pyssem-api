from flask import request, jsonify
from app import app
from app import mongo
from flask_marshmallow import Marshmallow
from marshmallow import fields, ValidationError, validate
from bson.json_util import dumps
import json

ma = Marshmallow(app)

# Create a simulation schema - which can then be tested against
class SimulationSchema(ma.Schema):
    simulation_name = fields.String(required=True)
    id = fields.String(required=True)
    owner = fields.String(required=True)
    description = fields.String(required=True)
    created = fields.DateTime(required=True)
    modified = fields.DateTime(required=True)
    scenario_properties = fields.Dict(keys=fields.String(), required=True)
    species = fields.Dict(keys=fields.String(), required=True)#
    status = fields.String(required=True, validate=validate.OneOf(["running", "completed", "failed", "pending"]))

simulation_schema = SimulationSchema()

@app.route('/')
def index():
    return 'Hello, welcome to the pyssem API!'

@app.route('/simulation', methods=['POST'])
def create_simulation():
    data = request.get_json()  # Get data from POST request

    # Data validation
    if not data:
        return jsonify({"error": "No data provided"}), 400
    errors = simulation_schema.validate(data)
    if errors:
        return jsonify({"error": "Invalid data", "messages": errors}), 400
    
    # Check to see if a simulation already exists with the same Id
    existing_simulation = mongo.db.simulations.find_one({"id": data.get("id")})
    if existing_simulation:
        return jsonify({"error": "A simulation with this ID already exists"}), 409

    # Insert data into MongoDB
    try:
        mongo.db.simulations.insert_one(data)
        return jsonify({"message": "Simulation created successfully"}), 201
    except Exception as e:
        return jsonify({"error": "Failed to create simulation", "message": str(e)}), 500


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

if __name__ == '__main__':
    app.run(debug=True)