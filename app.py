# General
import time
import os

# pyssem
from pyssem import ScenarioProperties

# Flask
from flask import Flask, jsonify
from flask import request, jsonify

# Celery
from celery import Celery
from celery.result import AsyncResult
import logging

# MongoDB
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from flask_marshmallow import Marshmallow
from marshmallow import fields, validate
from dotenv import load_dotenv
load_dotenv()
import json
from bson.json_util import dumps

## APP SET UP
app = Flask(__name__)
app.config['CELERY_BROKER_URL'] = 'redis://redis:6379/0'

# Celery set up
# Configure Celery to use the same logger as Flask
celery_logger = logging.getLogger('celery')

# Set the logging level for Celery logger
celery_logger.setLevel(logging.INFO)

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'], backend=app.config['CELERY_BROKER_URL'])



# MongoDB configuration
uri = os.getenv("MONGO_URI")
if not uri:
    raise ValueError("No MONGO_URI set for MongoDB connection")

mongo = MongoClient(uri, server_api=ServerApi('1'), tlsAllowInvalidCertificates=True)

try:
    mongo.db.command('ping')
    print("Pinged the simulation database. You are now connected!")
except Exception as e:
    print(f"Failed to connect to MongoDB (Simulation Database): {e}")


# Marshmellow Set Up for Object Declaration
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

## ROUTES
@celery.task(bind=True)
def simulate_task(self, scenario_props, species):
    celery_logger.info('Starting simulate_task')


    # Create an instance of the pySSEM_model with the simulation parameters
    model = ScenarioProperties(
        start_date=scenario_props["start_date"].split("T")[0],  # Assuming the date is in ISO format
        simulation_duration=scenario_props["simulation_duration"],
        steps=scenario_props["steps"],
        min_altitude=scenario_props["min_altitude"],
        max_altitude=scenario_props["max_altitude"],
        n_shells=scenario_props["n_shells"],
        launch_function=scenario_props["launch_function"],
        integrator=scenario_props["integrator"],
        density_model=scenario_props["density_model"],
        LC=scenario_props["LC"],
        v_imp=scenario_props["v_imp"],
        launchfile=r'C:\Users\IT\Documents\UCL\pyssem\pyssem\utils\launch\data\x0_launch_repeatlaunch_2018to2022_megaconstellationLaunches_Constellations.csv'
    )

    species = scenario_props["species"]
    model.configure_species(species)
    results = model.run_model()
    results = {"result": "Simulation complete"}

    return results

@app.route('/')
def hello():
    return 'Hello, Tester!'

@app.route('/simulate', methods=['POST'])
def simulate():
    data = request.get_json()
    task = simulate_task.delay(data)
    return jsonify({'result_id': task.id})

@app.route('/simulate', methods=['POST'])
def task_status():
    data = request.get_json()
    task = simulate_task.AsyncResult(data['result_id'])
    if task.state == 'PENDING':
        response = {
            'status': 'pending',
            'message': 'Simulation task has not started yet.'
        }
    elif task.state == 'SUCCESS':
        response = {
            'status': 'success',
            'message': 'Simulation task has completed successfully.'
        }
    elif task.state == 'FAILURE':
        response = {
            'status': 'failed',
            'message': 'Simulation task has failed.'
        }
    else:
        response = {
            'status': task.state,
            'message': 'Simulation task is still running.'
        }
    return jsonify(response)


## Actual simulations
@app.route('/simulation', methods=['POST'])
def create_simulation():
    app.logger.info('Received request to create simulation')
    data = request.get_json()

    if not data:
        app.logger.error('No data provided')
        return jsonify({"error": "No data provided"}), 400

    errors = simulation_schema.validate(data)
    if errors:
        app.logger.error(f'Invalid data: {errors}')
        return jsonify({"error": "Invalid data", "messages": errors}), 400

    # existing_simulation = mongo.db.simulations.find_one({"id": data.get("id")})
    # if existing_simulation:
    #     app.logger.error('Simulation with this ID already exists')
    #     return jsonify({"error": "A simulation with this ID already exists"}), 409
    
    # Add to the database
    try:
        data['status'] = 'running'
        result = mongo.db.simulations.insert_one(data)
        app.logger.info(f'Created simulation with ID: {data.get("id")}')

        # data = json.load(data)
        scenario_props = data["scenario_properties"]
        species = data["species"]

        task = simulate_task.delay(scenario_props=scenario_props, species=species)

        model = pyssem.pySSEM_model(
            start_date=scenario_props["start_date"].split("T")[0],  # Assuming the date is in ISO format
            simulation_duration=scenario_props["simulation_duration"],
            steps=scenario_props["steps"],
            min_altitude=scenario_props["min_altitude"],
            max_altitude=scenario_props["max_altitude"],
            n_shells=scenario_props["n_shells"],
            launch_function=scenario_props["launch_function"],
            integrator=scenario_props["integrator"],
            density_model=scenario_props["density_model"],
            LC=scenario_props["LC"],
            v_imp=scenario_props["v_imp"],
            launchfile=r'C:\Users\IT\Documents\UCL\pyssem\pyssem\utils\launch\data\x0_launch_repeatlaunch_2018to2022_megaconstellationLaunches_Constellations.csv'
        )

        # Return log that simulation has started successfully
        return jsonify({'result_id': data['id']}), 201
    
    except Exception as e:
        app.logger.error('Failed to create simulation')
        # return error message
        return jsonify({"error": str(e)}), 500

# Search for simulations
def search_simulations(query):
    simulations = mongo.db.simulations.find(query)
    simulations_list = list(simulations)  # Convert cursor to list
    if simulations_list:
        return jsonify([json.loads(dumps(sim)) for sim in simulations_list]), 200
    return jsonify({"error": "No simulations found"}), 404

@app.route('/simulation/id/<string:simulation_id>', methods=['GET'])
def get_simulation_by_id(simulation_id):
    return search_simulations({"id": simulation_id})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
