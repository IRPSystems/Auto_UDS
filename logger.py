import logging
import colorlog
import os

def setup_logger(script_name, logs_folder):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    console_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s [%(levelname)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'blue',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    )
    ch = logging.StreamHandler()
    ch.setFormatter(console_formatter)
    logger.addHandler(ch)

    if isinstance(script_name, tuple):
        script_name = script_name[0]
    log_file_path = os.path.join(logs_folder, f"{script_name}.log")

    fh = logging.FileHandler(log_file_path)
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fh.setFormatter(file_formatter)
    logger.addHandler(fh)

    return logger