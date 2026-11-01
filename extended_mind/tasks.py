import logging

from procrastinate.contrib.django import app

logger = logging.getLogger(__name__)


@app.task
def ping():
    logger.info("pong")
