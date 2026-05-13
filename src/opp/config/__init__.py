import os
from pathlib import Path
from typing import Dict, Any, Optional

from opp.logger import logger


class OPPConfig:
    _instance: Optional["OPPConfig"] = None

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self._find_config()
        self._config: Dict[str, Any] = {}
        self._load()

    @classmethod
    def get_instance(cls) -> "OPPConfig":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    def _find_config(self) -> Path:
        candidates = [
            Path.cwd() / "opp_config.yaml",
            Path(__file__).parent.parent.parent / "opp_config.yaml",
        ]
        for path in candidates:
            if path.exists():
                return path
        return candidates[0]

    def _load(self):
        if not self.config_path.exists():
            self._config = self._default_config()
            return

        try:
            import yaml
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load config from {self.config_path}: {e}")
            self._config = self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        return {
            "pdf": "simple",
            "html": "simple",
        }

    def get_extractor_mode(self, fmt: str) -> str:
        return self._config.get(fmt, "simple")


def load_config(config_path: Optional[Path] = None) -> OPPConfig:
    OPPConfig.reset_instance()
    return OPPConfig(config_path)


def get_config() -> OPPConfig:
    return OPPConfig.get_instance()
