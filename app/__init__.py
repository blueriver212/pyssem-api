import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from celery import Celery
from dotenv import load_dotenv

db = SQLAlchemy()
ma = Marshmallow()
celery = Celery(__name__)

def create_app():
    load_dotenv()
    
    # Load environment variables
    POSTGRES_USER = os.getenv('POSTGRES_USER')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
    POSTGRES_HOST = os.getenv('POSTGRES_HOST')
    POSTGRES_DATABASE = os.getenv('POSTGRES_DATABASE')

    if not all([POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DATABASE]):
        raise ValueError("One or more environment variables are missing. Please check your .env file.")

    app = Flask(__name__)
    app.config.from_object('config')

    # Initialize extensions
    db.init_app(app)
    ma.init_app(app)
    celery.conf.update(app.config)

    # Register blueprints
    from app.routes.simulation_routes import simulation_blueprint
    app.register_blueprint(simulation_blueprint)

    return app
