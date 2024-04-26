from flask import Flask
from flask_pymongo import MongoClient
from pymongo.server_api import ServerApi
import os

app = Flask(__name__)

uri="mongodb+srv://indybrownhall:<password>@simulation.ckprzup.mongodb.net/?retryWrites=true&w=majority"
mongo = MongoClient(uri, server_api=ServerApi('1'), tlsAllowInvalidCertificates=True)

try:
    mongo.db.command('ping')
    print("Pinged the simulation database. You are now connected!")
except Exception as e:
    print(f"Failed to connect to MongoDB (Simulation Database): {e}")

from app import views