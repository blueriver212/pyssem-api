from flask import jsonify, request
from ..models.simulation_schema import SimulationSchema
from ..simulation.simulation_tasks import simulate_task
from ..models.db import get_db
from json import dumps
import json
from flask import current_app as app

simulation_schema = SimulationSchema()

@app.route('/', methods=['GET'])
def hello():
    return 'Hello, welcome to the Pyssem API!'

## Actual simulations
@app.route('/simulation', methods=['POST'])
def create_simulation():
    mongo = get_db()
    app.logger.info('Received request to create simulation')
    data = request.get_json()

    if not data:
        app.logger.error('No data provided')
        return jsonify({"error": "No data provided"}), 400

    errors = simulation_schema.validate(data)
    if errors:
        app.logger.error(f'Invalid data: {errors}')
        return jsonify({"error": "Invalid data", "messages": errors}), 400

    existing_simulation = mongo.db.simulations.find_one({"id": data.get("id")})
    if existing_simulation:
        app.logger.error('Simulation with this ID already exists')
        return jsonify({"error": "A simulation with this ID already exists"}), 409
    
    # Add to the database
    try:
        data['status'] = 'running'
        result = mongo.db.simulations.insert_one(data)
        app.logger.info(f'Created simulation with ID: {data.get("id")}')

        # data = json.load(data)
        scenario_props = data["scenario_properties"]
        species = data["species"]

        task = simulate_task.delay(scenario_props=scenario_props, species=species, id=data.get("id"))

        # Return log that simulation has started successfully
        return jsonify({'result_id': task.id}), 201
    
    except Exception as e:
        app.logger.error('Failed to create simulation')
        # return error message
        return jsonify({"error": str(e)}), 500

# Search for simulations
def search_simulations(query):
    mongo = get_db()

    simulations = mongo.db.simulations.find(query)
    simulations_list = list(simulations)  # Convert cursor to list
    if simulations_list:
        return jsonify([json.loads(dumps(sim)) for sim in simulations_list]), 200
    return jsonify({"error": "No simulations found"}), 404

@app.route('/simulation/id/<string:simulation_id>', methods=['GET'])
def get_simulation_by_id(simulation_id):
    return search_simulations({"id": simulation_id})


# Delete all simulations
@app.route('/simulation', methods=['DELETE'])
def delete_all_simulations():
    mongo = get_db()

    result = mongo.db.simulations.delete_many({})
    return jsonify({"deleted_count": result.deleted_count}), 200
