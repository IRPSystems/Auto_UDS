import logging
import colorlog
import os

def setup_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Define a custom formatter with colors for console output
    console_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',  # INFO logs will be green
            'WARNING': 'blue',
            'ERROR': 'red',   # ERROR logs will be red in the console
            'CRITICAL': 'bold_red',
        }
    )

    # Create a stream handler for the console
    ch = logging.StreamHandler()
    ch.setFormatter(console_formatter)
    logger.addHandler(ch)

    # Get the current script's directory and set the log file path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file_path = os.path.join(script_dir, "output.log")

    # Remove the old log file if it exists
    if os.path.exists(log_file_path):
        os.remove(log_file_path)

    # Create a file handler and set the plain text formatter
    fh = logging.FileHandler(log_file_path)
    fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(fh)

    return logger
