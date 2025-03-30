import pathlib
import os

MAIN_DIR = os.path.join(pathlib.Path(__file__).parent.parent.parent.resolve())

DATA_DIR = os.path.join(MAIN_DIR, "data")
LOGS_DIR = os.path.join(MAIN_DIR, "logs")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
FUTURE_PAIRS_PATH = os.path.join(DATA_DIR, "pairs.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
