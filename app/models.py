from app import db

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
