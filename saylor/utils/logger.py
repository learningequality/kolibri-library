import logging
from ricecooker.config import LOGGER

def get_logger():
    LOGGER.setLevel(logging.DEBUG)
    return LOGGER