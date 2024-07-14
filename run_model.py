import json
from typing import Any, Dict
from flask import Flask, request, jsonify, make_response, url_for
from celery import Celery
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from datetime import datetime
import os
from flask import render_template, redirect
from pyssem.model import Model
from dotenv import load_dotenv
load_dotenv()
import psycopg2
from psycopg2.extras import Json
from cors import _build_cors_preflight_response, _corsify_actual_response
import uuid

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST')}/{os.getenv('POSTGRES_DATABASE')}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

# Celery configuration
app.config['CELERY_BROKER_URL'] = 'redis://redis:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://redis:6379/0'

db = SQLAlchemy(app)
ma = Marshmallow(app)

class Simulation(db.Model):
    __tablename__ = 'simulations'
    id = db.Column(db.String, primary_key=True)
    simulation_name = db.Column(db.String, nullable=False)
    owner = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    modified = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    scenario_properties = db.Column(db.JSON, nullable=False)
    species = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String, nullable=False, default='pending')

    def to_dict(self):
        """Serialize the object to a dictionary."""
        return {
            "id": str(self.id),
            "simulation_name": self.simulation_name,
            "owner": self.owner,
            "description": self.description,
            "created": self.created.isoformat() if self.created else None,
            "modified": self.modified.isoformat() if self.modified else None,
            "scenario_properties": self.scenario_properties,
            "species": self.species,
            "status": self.status
        }

class SimulationSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Simulation

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

simulation_schema = SimulationSchema()
simulations_schema = SimulationSchema(many=True)

@celery.task(bind=True)
def update_progress(self, current , status):
    self.update_state(state='PROGRESS',
                        meta={'current':current, 'total': 99,
                            'status': status})

@celery.task(bind=True)
def run_model(self, simulation_data, postgres_url):
    def update_progress(current, status):
        self.update_state(state='PROGRESS',
                          meta={'current': current, 'total': 100,
                                'status': status})
    update_progress(1, "starting")

    simulation_data = json.loads(simulation_data)
    print(simulation_data)

    if not simulation_data:
        raise ValueError("No simulation data provided")

    scenario_props = simulation_data['scenario_properties']

    update_progress(20, "loading model")

    model = Model(
        start_date=scenario_props["start_date"].split("T")[0],  # Assuming date is in ISO format
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
        fragment_spreading=False
    )

    update_progress(30, "loading species")
    
    species = simulation_data["species"]
    
    update_progress(40, "configure species")
    model.configure_species(species)
    update_progress(50, "run model")
    model.run_model()
    update_progress(60, "save results to db")
    output = model.results_to_json()
    output = json.loads(output)

    def insert_data(conn, simulation_id, results_data):
        new_id = str(uuid.uuid4())
        
        # Query to check if an entry with the same simulation_id exists
        check_query = '''
        SELECT id FROM results WHERE simulation_id = %s
        '''
        
        insert_update_query = '''
        INSERT INTO results (id, times, n_shells, species, Hmid, max_altitude, min_altitude, population_data, launch, simulation_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (simulation_id) DO UPDATE SET
            times = EXCLUDED.times,
            n_shells = EXCLUDED.n_shells,
            species = EXCLUDED.species,
            Hmid = EXCLUDED.Hmid,
            max_altitude = EXCLUDED.max_altitude,
            min_altitude = EXCLUDED.min_altitude,
            population_data = EXCLUDED.population_data,
            launch = EXCLUDED.launch
        '''
        
        update_query = '''
        UPDATE simulations SET status = %s WHERE id = %s
        '''
        
        with conn.cursor() as cursor:
            # Check if an entry with the same simulation_id exists
            cursor.execute(check_query, (simulation_id,))
            existing_entry = cursor.fetchone()
            
            if existing_entry:
                entry_id = existing_entry[0]
            else:
                entry_id = new_id
            
            cursor.execute(insert_update_query, (
                entry_id, results_data['times'], results_data['n_shells'],
                results_data['species'], results_data['Hmid'], results_data['max_altitude'],
                results_data['min_altitude'], Json(results_data['population_data']),
                Json(results_data['launch']), simulation_id
            ))
            
            cursor.execute(update_query, ('completed', simulation_id))
            
            conn.commit()
        
        print('Inserted/Updated results data and updated simulation status')
        conn.close()

    try:
        conn = psycopg2.connect(postgres_url)
        insert_data(conn, simulation_data['id'], output)
    except Exception as e:
        return {'current': 100, 'total': 100, 'status': 'Task failed!',
            'result': str(e)}
    finally:
        conn.close()

    return {'current': 100, 'total': 100, 'status': 'Task completed!',
            'result': "finished!"}

@app.route('/status/<task_id>',methods=["GET", "OPTIONS"])
def taskstatus(task_id):
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    elif request.method == "GET":
        print(f"Request for task status:{task_id}")
        task = run_model.AsyncResult(task_id)
        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'current': 0,
                'total': 1,
                'status': 'Pending...'
            }
        elif task.state != 'FAILURE':
            response = {
                'state': task.state,
                'current': task.info.get('current', 0),
                'total': task.info.get('total', 1),
                'status': task.info.get('status', '')
            }
            if 'result' in task.info:
                response['result'] = task.info['result']
        else:
            response = {
                'state': task.state,
                'current': 1,
                'total': 1,
                'status': str(task.info),
            }
        response = jsonify(response)
        return _corsify_actual_response(response)
    
@app.route('/health2', methods=['GET'])
def health():
    print("health check") 
    return 'OK', 200

@app.route("/runmodel", methods=["POST", "OPTIONS"])
def api_create_order():
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    elif request.method == "POST":

        simulation_id = request.json["id"]

        simulation_data = Simulation.query.get(simulation_id)
        if simulation_data is None:
            print(simulation_id)
            return jsonify({"error": "Simulation not found"}), 404
        
        simulation_dict = simulation_data.to_dict()
        simulation_json = json.dumps(simulation_dict)
        
        task = run_model.delay(simulation_json, os.getenv('POSTGRES_URL'))

        response = jsonify({
            'task_id': url_for('taskstatus', task_id=task.id, _external=True)
        })
        response.status_code = 202
        return _corsify_actual_response(response)
    else:
        raise RuntimeError("Weird - don't know how to handle method {}".format(request.method))


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template('index.html')

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)