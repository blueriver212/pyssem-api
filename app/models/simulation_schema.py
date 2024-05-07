from marshmallow import Schema, fields, validate
import marshmallow as ma

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