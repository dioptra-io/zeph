import logging

logger = logging.getLogger("zeph")
logger.setLevel(logging.DEBUG)
script_formatter = logging.Formatter(
    "%(asctime)s :: SCRIPT :: %(levelname)s :: %(message)s"
)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(script_formatter)
logger.addHandler(stream_handler)
