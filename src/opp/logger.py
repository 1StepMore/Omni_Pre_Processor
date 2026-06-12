import logging
import os
from pathlib import Path
from datetime import datetime


def get_log_dir():
    project_root = Path(__file__).parent.parent.parent
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir


def setup_logger(verbose: bool = False) -> logging.Logger:
    # Allow env var override: OPP_LOG_LEVEL=DEBUG
    env_level = os.environ.get("OPP_LOG_LEVEL", "").upper()
    if env_level == "DEBUG":
        verbose = True
    level = logging.DEBUG if verbose else logging.INFO
    log_dir = get_log_dir()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
    log_file = log_dir / f"opp_{timestamp}.log"

    logger = logging.getLogger('opp')
    logger.setLevel(level)

    if not logger.handlers:
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
        logger.addHandler(console)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        logger.addHandler(file_handler)

        logger.info(f"Log file: {log_file}")

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger('opp')


logger = setup_logger()
