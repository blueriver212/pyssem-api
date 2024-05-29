# General
import time
import os

# pyssem
from pyssem.model import Model

# Flask
from flask import Flask, jsonify
from flask import request, jsonify

# Celery
from celery import Celery
from celery.result import AsyncResult
import logging

# PostgreSQL
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from marshmallow import fields, validate
from dotenv import load_dotenv
load_dotenv()
import json

## APP SET UP
app = Flask(__name__)
app.config['CELERY_BROKER_URL'] = 'redis://redis:6379/0'

# Load database configuration from .env file
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST')}/{os.getenv('POSTGRES_DATABASE')}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Celery set up
# Configure Celery to use the same logger as Flask
celery_logger = logging.getLogger('celery')

# Set the logging level for Celery logger
celery_logger.setLevel(logging.INFO)

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'], backend=app.config['CELERY_BROKER_URL'])

# Database set up
db = SQLAlchemy(app)
ma = Marshmallow(app)

# Simulation model
class Simulation(db.Model):
    __tablename__ = 'simulations'
    id = db.Column(db.String, primary_key=True)
    simulation_name = db.Column(db.String, nullable=False)
    owner = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    created = db.Column(db.DateTime, nullable=False)
    modified = db.Column(db.DateTime, nullable=False)
    scenario_properties = db.Column(db.JSON, nullable=False)
    species = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String, nullable=False, default='pending')

# Marshmallow schema
class SimulationSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Simulation

simulation_schema = SimulationSchema()
simulations_schema = SimulationSchema(many=True)

## ROUTES
@celery.task(bind=True)
def simulate_task(self, scenario_props, species, id):
    celery_logger.info('Starting simulate_task')

    print(scenario_props)
    # Create an instance of the pySSEM_model with the simulation parameters
    model = Model(
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
            launchfile='x0_launch_repeatlaunch_2018to2022_megaconstellationLaunches_Constellations.csv'
        )

    model.configure_species(species)
    results = model.run_model()

    # Update the simulation status in the database
    simulation = Simulation.query.get(id)
    simulation.status = 'completed'
    db.session.commit()

    return results

@app.route('/')
def hello():
    return 'Hello, welcome to the Pyssem API!'

@app.route('/task_status', methods=['GET'])
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

    existing_simulation = Simulation.query.get(data.get("id"))
    if existing_simulation:
        app.logger.error('Simulation with this ID already exists')
        return jsonify({"error": "A simulation with this ID already exists"}), 409
    
    # Add to the database
    try:
        data['status'] = 'running'
        new_simulation = Simulation(**data)
        db.session.add(new_simulation)
        db.session.commit()
        app.logger.info(f'Created simulation with ID: {data.get("id")}')

        scenario_props = data["scenario_properties"]
        species = data["species"]

        task = simulate_task.delay(scenario_props=scenario_props, species=species, id=data.get("id"))

        # Return log that simulation has started successfully
        return jsonify({'result_id': task.id}), 201
    
    except Exception as e:
        app.logger.error('Failed to create simulation')
        # return error message
        return jsonify({"error": str(e)}), 500
    
# Run a simulation from a get request
@app.route('/simulation/run/<string:simulation_id>', methods=['GET'])
def run_simulation_from_id(simulation_id):
    simulation = Simulation.query.get(simulation_id)
    if not simulation:
        return jsonify({"error": "Simulation not found"}), 404
    
    # Check if simulation is already running
    if simulation.status == 'running':
        return jsonify({"error": "Simulation is already running"}), 400
    
    # Update status to running
    simulation.status = 'running'
    db.session.commit()

    # Run simulation
    try:
        task = simulate_task.delay(scenario_props=simulation.scenario_properties, species=simulation.species, id=simulation_id)
    except Exception as e:
        simulation.status = 'failed'
        db.session.commit()
        return jsonify({"error": str(e)}), 500


# This will return any param that is passed after an id
@app.route('/simulation/<string:simulation_id>/<string:param>', methods=['GET'])
def get_simulation_param(simulation_id, param):
    simulation = Simulation.query.get(simulation_id)
    if simulation:
        if hasattr(simulation, param):
            return jsonify({param: getattr(simulation, param)}), 200
        else:
            return jsonify({"error": f"Parameter '{param}' not found"}), 404
    return jsonify({"error": "Simulation not found"}), 404

# Delete all simulations
@app.route('/simulation', methods=['DELETE'])
def delete_all_simulations():
    num_deleted = db.session.query(Simulation).delete()
    db.session.commit()
    return jsonify({"deleted_count": num_deleted}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')