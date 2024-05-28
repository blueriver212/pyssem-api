import os
import logging
from flask import Flask, jsonify, request
from flask_marshmallow import Marshmallow
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from celery import Celery
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from pyssem import model

load_dotenv()

# Load environment variables
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_HOST = os.getenv('POSTGRES_HOST')
POSTGRES_DATABASE = os.getenv('POSTGRES_DATABASE')

if not all([POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DATABASE]):
    raise ValueError("One or more environment variables are missing. Please check your .env file.")

## APP SET UP
app = Flask(__name__)
app.config['CELERY_BROKER_URL'] = 'redis://redis:6379/0'
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DATABASE}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_POOL_SIZE'] = 10
app.config['SQLALCHEMY_MAX_OVERFLOW'] = 20
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 30

# Configure Celery to use the same logger as Flask
celery_logger = logging.getLogger('celery')
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
    
    try:
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
    except Exception as e:
        celery_logger.error(f"Simulation task failed: {str(e)}")
        # Update the simulation status to 'failed'
        simulation = Simulation.query.get(id)
        simulation.status = 'failed'
        db.session.commit()
        raise e

@app.route('/')
def hello():
    return 'Hello, welcome to the Pyssem API!'

@app.route('/task_status', methods=['GET'])
def task_status():
    data = request.get_json()
    if not data or 'result_id' not in data:
        return jsonify({"error": "result_id is required"}), 400
    
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
        app.logger.error(f'Failed to create simulation: {str(e)}')
        # return error message
        return jsonify({"error": str(e)}), 500

# Search for simulations
def search_simulations(query):
    simulations = Simulation.query.filter_by(**query).all()
    if simulations:
        return simulations_schema.jsonify(simulations), 200
    return jsonify({"error": "No simulations found"}), 404

@app.route('/simulation/id/<string:simulation_id>', methods=['GET'])
def get_simulation_by_id(simulation_id):
    return search_simulations({"id": simulation_id})


# Delete all simulations
@app.route('/simulation', methods=['DELETE'])
def delete_all_simulations():
    num_deleted = db.session.query(Simulation).delete()
    db.session.commit()
    return jsonify({"deleted_count": num_deleted}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
