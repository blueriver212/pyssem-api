from flask import Flask
from flask_pymongo import MongoClient
from pymongo.server_api import ServerApi
import os
from app.celery_utils import celery_init_app
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

app.config.from_mapping(
    CELERY=dict(
        broker_url="redis://localhost:6379/0",
        result_backend="redis://localhost:6379/0",
        task_ignore_result=True,
    ),
)
celery_app = celery_init_app(app)

uri = os.getenv("MONGO_URI")
if not uri:
    raise ValueError("No MONGO_URI set for MongoDB connection")

print(uri)
mongo = MongoClient(uri, server_api=ServerApi('1'), tlsAllowInvalidCertificates=True)

try:
    mongo.db.command('ping')
    print("Pinged the simulation database. You are now connected!")
except Exception as e:
    print(f"Failed to connect to MongoDB (Simulation Database): {e}")

from app import views