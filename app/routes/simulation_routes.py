from flask import Blueprint, request, jsonify, current_app as app
from app import db, celery
from app.models import Simulation
from app.schemas import simulation_schema, simulations_schema
from app.tasks import simulate_task

simulation_blueprint = Blueprint('simulation', __name__)

@simulation_blueprint.route('/')
def hello():
    return 'Hello, welcome to the Pyssem API!'

@simulation_blueprint.route('/task_status', methods=['GET'])
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

@simulation_blueprint.route('/simulation', methods=['POST'])
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

@simulation_blueprint.route('/simulation/id/<string:simulation_id>', methods=['GET'])
def get_simulation_by_id(simulation_id):
    return search_simulations({"id": simulation_id})

@simulation_blueprint.route('/simulation', methods=['DELETE'])
def delete_all_simulations():
    num_deleted = db.session.query(Simulation).delete()
    db.session.commit()
    return jsonify({"deleted_count": num_deleted}), 200

@simulation_blueprint.route('/simulation', methods=['GET'])
def get_all_simulations():
    simulations = Simulation.query.all()
    return simulations_schema.jsonify(simulations), 200

def search_simulations(query):
    simulations = Simulation.query.filter_by(**query).all()
    if simulations:
        return simulations_schema.jsonify(simulations), 200
    return jsonify({"error": "No simulations found"}), 404
