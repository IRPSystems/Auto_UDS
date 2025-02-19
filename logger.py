
import logging
import colorlog
import os

def setup_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger

    # """Set up the logger with color formatting and file logging."""
    #def setup_logger(log_filename="uds_log.txt"):
        # log_format = "%(log_color)s%(levelname)s:%(reset)s %(message)s"
        # log_colors = {
        #     'DEBUG': 'cyan',
        #     'INFO': 'green',
        #     'WARNING': 'yellow',
        #     'ERROR': 'red',
        #     'CRITICAL': 'bold_red',
        # }
        #
        # # Create a logger
        # logger = logging.getLogger("UDS_Logger")
        # logger.setLevel(logging.DEBUG)  # Capture all log levels
        #
        # # Ensure no duplicate handlers
        # if logger.hasHandlers():
        #     logger.handlers.clear()
        #
        # # Console handler with colors
        # console_handler = logging.StreamHandler()
        # console_formatter = colorlog.ColoredFormatter(log_format, log_colors=log_colors)
        # console_handler.setFormatter(console_formatter)
        # logger.addHandler(console_handler)
        #
        # # File handler (without colors)
        # log_dir = "logs"
        # os.makedirs(log_dir, exist_ok=True)  # Ensure logs directory exists
        # file_handler = logging.FileHandler(os.path.join(log_dir, log_filename), mode='w', encoding="utf-8")
        # file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        # file_handler.setFormatter(file_formatter)
        # logger.addHandler(file_handler)
        #
        # return logger
