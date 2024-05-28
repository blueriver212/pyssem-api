# import os
# import logging
# from flask import Flask
# from dotenv import load_dotenv
# from flask_sqlalchemy import SQLAlchemy
# from flask_marshmallow import Marshmallow
# from celery import Celery

# load_dotenv()

# # Load environment variables
# POSTGRES_USER = os.getenv('POSTGRES_USER')
# POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
# POSTGRES_HOST = os.getenv('POSTGRES_HOST')
# POSTGRES_DATABASE = os.getenv('POSTGRES_DATABASE')

# if not all([POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DATABASE]):
#     raise ValueError("One or more environment variables are missing. Please check your .env file.")

# # Initialize app
# app = Flask(__name__)
# app.config.from_object('config')

# # Initialize extensions
# db = SQLAlchemy(app)
# ma = Marshmallow(app)

# # Configure Celery
# celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'], backend=app.config['CELERY_BROKER_URL'])
# celery.conf.update(app.config)

# # Import models and routes
# from models import Simulation
# from routes import register_routes

# register_routes(app)

# if __name__ == '__main__':
#     app.run(debug=True, host='0.0.0.0')
