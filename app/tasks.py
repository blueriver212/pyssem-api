import logging
from app import celery, db
from models import Simulation
from pyssem import Model

celery_logger = logging.getLogger('celery')

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
