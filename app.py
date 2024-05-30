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

import psycopg2
from psycopg2.extras import NamedTupleCursor
from celery import Task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

class BaseTask(Task):
    abstract = True
    _db = None

    @property
    def db(self):
        if self._db is not None:
            return self._db
        self._db = psycopg2.connect(
            host=self.app.conf.POSTGRES_HOST,
            port=self.app.conf.POSTGRES_PORT,
            dbname=self.app.conf.POSTGRES_DBNAME,
            user=self.app.conf.POSTGRES_USER,
            password=self.app.conf.POSTGRES_PASSWORD,
            cursor_factory=NamedTupleCursor,
        )
        return self._db

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        if self._db is not None:
            self._db.close()
            self._db = None


import time

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

@app.route('/simulation/tasks', methods=['GET'])
def get_all_simulation_tasks():
    simulations = Simulation.query.all()
    if not simulations:
        return jsonify({"error": "No simulations found"}), 404
    
    result = []
    for sim in simulations:
        result.append({
            "id": str(sim.id),
            "status": sim.status
        })

    return jsonify(result), 200


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
    

class SimulationTask(BaseTask):
    abstract = True

@celery.task(bind=True, base=SimulationTask)
def simulate_task(self, scenario_props, species, id):

    # Simulate a task running for a few seconds
    time.sleep(5)  
    try:
        with self.db.cursor() as cursor:
            cursor.execute(
                "UPDATE simulation SET status = %s WHERE id = %s",
                ('completed', id)
            )
            self.db.commit()
        
    except Exception as e:
        
        self.db.rollback()

    return True
    
# Run a simulation from a get request
@app.route('/simulation/run/<uuid:simulation_id>', methods=['GET'])
def run_simulation_from_id(simulation_id):
    simulation = Simulation.query.get(simulation_id)
    if not simulation:
        return jsonify({"error": "Simulation not found"}), 404
    
    # Update status to running
    simulation.status = 'running'
    db.session.commit()

    # Run simulation
    try:
        print('running simulation')
        task = simulate_task.delay(scenario_props=simulation.scenario_properties, species=simulation.species, id=simulation_id)
        return jsonify({"message": "Simulation started", "task_id": task.id}), 202
    except Exception as e:
        simulation.status = 'failed'
        db.session.commit()
        return jsonify({"error": str(e)}), 500

    
# Return all simulations in the database
@app.route('/simulation', methods=['GET'])
def get_simulations():
    all_simulations = Simulation.query.all()
    result = simulations_schema.dump(all_simulations)
    return jsonify(result), 200

# Return a specific simulation based off ID
@app.route('/simulation/<uuid:simulation_id>', methods=['GET'])
def get_simulation(simulation_id):
    simulation = Simulation.query.get(simulation_id)
    if simulation:
        return simulation_schema.jsonify(simulation), 200
    return jsonify({"error": "Simulation not found"}), 404


# This will return any param that is passed after an id
@app.route('/simulation/<uuid:simulation_id>/<string:param>', methods=['GET'])
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