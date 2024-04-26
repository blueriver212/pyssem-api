from flask import Flask
from flask_pymongo import MongoClient
from pymongo.server_api import ServerApi
import os
from dotenv import load_dotenv

app = Flask(__name__)


load_dotenv()

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