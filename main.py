from flask import Flask
from celery import Celery
import logging

app = Flask(__name__)
app.config['CELERY_BROKER_URL'] = 'redis://redis:6379/0'

# Celery set up
# Configure Celery to use the same logger as Flask
celery_logger = logging.getLogger('celery')

# Set the logging level for Celery logger
celery_logger.setLevel(logging.INFO)

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'], backend=app.config['CELERY_BROKER_URL'])

if __name__ == '__main__':
    app.run(debug=True)