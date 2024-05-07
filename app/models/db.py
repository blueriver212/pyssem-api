from pymongo import MongoClient
from pymongo.server_api import ServerApi
from flask import current_app as app

def get_db():
    client = MongoClient(app.config['MONGO_URI'], server_api=ServerApi('1'), tlsAllowInvalidCertificates=True)
    return client.db
