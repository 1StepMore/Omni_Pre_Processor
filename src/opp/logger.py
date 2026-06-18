import logging
import os
from pathlib import Path
from datetime import datetime


def get_log_dir():
    project_root = Path(__file__).parent.parent.parent
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir


def _build_formatter(json_mode: bool) -> logging.Formatter:
    """Return text or JSON formatter based on OMNI_LOG_FORMAT."""
    if json_mode:
        from pythonjsonlogger.json import JsonFormatter
        return JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            rename_fields={
                "asctime": "timestamp",
                "levelname": "level",
                "name": "module",
            },
        )
    return logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s',
                             datefmt='%Y-%m-%d %H:%M:%S')


def setup_logger(verbose: bool = False) -> logging.Logger:
    env_level = os.environ.get("OPP_LOG_LEVEL", "").upper()
    if env_level == "DEBUG":
        verbose = True
    level = logging.DEBUG if verbose else logging.INFO
    log_dir = get_log_dir()

    json_mode = os.environ.get("OMNI_LOG_FORMAT", "console").lower() == "json"

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
    log_file = log_dir / f"opp_{timestamp}.log"

    logger = logging.getLogger('opp')
    logger.setLevel(level)

    if not logger.handlers:
        console = logging.StreamHandler()
        console.setLevel(level)
        if json_mode:
            console.setFormatter(_build_formatter(json_mode=True))
        else:
            console.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
        logger.addHandler(console)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(_build_formatter(json_mode=json_mode))
        logger.addHandler(file_handler)

        logger.info(f"Log file: {log_file}")

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger('opp')


logger = setup_logger()
