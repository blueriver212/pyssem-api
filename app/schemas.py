from app import ma
from .models import Simulation
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

class SimulationSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Simulation

simulation_schema = SimulationSchema()
simulations_schema = SimulationSchema(many=True)
