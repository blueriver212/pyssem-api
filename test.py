from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

uri = "mongodb+srv://indybrownhall:lJbhGH407gKDTJgU@simulation.ckprzup.mongodb.net/?retryWrites=true&w=majority"

# Create a new client and connect to the server, currently ssl certificates are turned off
client = MongoClient(uri, server_api=ServerApi('1'), tlsAllowInvalidCertificates=True)

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)