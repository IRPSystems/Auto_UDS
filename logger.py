import logging
import colorlog
import os

def setup_logger(script_name, logs_folder, custom_folder=None):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)


    for handler in logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            handler.close()
            logger.removeHandler(handler)


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


    ch = logging.StreamHandler()
    ch.setFormatter(console_formatter)
    logger.addHandler(ch)


    if custom_folder:
        log_file_path = os.path.join(logs_folder, custom_folder, f"{script_name}.log")
    else:
        log_file_path = os.path.join(logs_folder, f"{script_name}.log")

    if os.path.exists(log_file_path):
        try:
            os.remove(log_file_path)
        except PermissionError as e:
            logger.error(f"Failed to remove log file: {e}")

    # Create a file handler and set the plain text formatter
    fh = logging.FileHandler(log_file_path)
    fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(fh)

    return logger