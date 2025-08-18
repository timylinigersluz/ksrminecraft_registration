import logging
import os
from datetime import datetime

# Konfigurieren des Loggers
logger = logging.getLogger('my_logger')
logger.setLevel(logging.INFO)

# Definieren des FileHandlers mit dynamischem Dateinamen (falls noch nicht vorhanden, dann erstellen)
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_filename = datetime.now().strftime("%Y-%m-%d") + '_logfile.log'
file_handler = logging.FileHandler(os.path.join(log_dir, log_filename), encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

# Definieren des StreamHandlers
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

# Hinzufügen der Handler zum Logger
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

# Hinzufügen eines zusätzlichen Handlers zum Fangen aller Exceptions
exception_handler = logging.FileHandler(os.path.join(log_dir, 'fehler.log'), encoding='utf-8')
exception_handler.setLevel(logging.ERROR)
exception_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logger.addHandler(exception_handler)
