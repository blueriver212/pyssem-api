import json
from flask import Flask, request, render_template, session, flash, redirect, \
    url_for, jsonify
from flask_cors import CORS
from celery import Celery
from pyssem.pyssem.model import Model

app = Flask(__name__)
CORS(app)

app.config['CELERY_BROKER_URL'] = 'redis://redis:6379/0'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'], backend=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

@celery.task(bind=True)
def update_progress(self, current , status):
    self.update_state(state='PROGRESS',
                        meta={'current':current, 'total': 99,
                            'status': status})

@celery.task(bind=True)
def run_model(self, arg1, arg2):
    def update_progress(current , status):
        self.update_state(state='PROGRESS',
                            meta={'current':current, 'total': 99,
                                'status': status})
        
    print(arg1, arg2)
    update_progress(1, "starting")
    with open('./three_species.json') as f:
        simulation_data = json.load(f)

    print("hello")
    print(simulation_data['scenario_properties'])

    scenario_props = simulation_data['scenario_properties']

    update_progress(20, "loading model")

    model = Model(
        start_date=scenario_props["start_date"].split(
            "T")[0],  # Assuming date is in ISO format
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
    )


    update_progress(30, "loading species")
    species = simulation_data["species"]
    update_progress(40, "configure species")
    model.configure_species(species)
    model.run_model()
    return {'current': 100, 'total': 100, 'status': 'Task completed!',
            'result': "finished!"}


@app.route('/runmodel', methods=['POST'])
def runmodel():
    # task = run_model.apply_async()
    task = run_model.delay("test1","test2")
    return jsonify({}), 202, {'Location': url_for('taskstatus',
                                                  task_id=task.id)}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template('index.html')

    return redirect(url_for('index'))


@app.route('/status/<task_id>')
def taskstatus(task_id):
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
    return jsonify(response)

if __name__ == '__main__':\
    app.run(debug=True)