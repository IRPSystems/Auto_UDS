import logging
#
# def setup_logger():
#     logging.basicConfig(
#         level=logging.INFO,  # Ensure this is set to INFO or lower
#         #format='%(asctime)s %(message)s'
#         format='%(message)s'
#     )
#     return logging.getLogger(__name__)
#
# logger = setup_logger()

# logger.py
def setup_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger