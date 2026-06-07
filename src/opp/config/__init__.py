import os
import threading
from pathlib import Path
from typing import Dict, Any, Optional

from opp.logger import logger


class OPPConfig:
    _instance: Optional["OPPConfig"] = None
    _lock = threading.Lock()

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self._find_config()
        self._config: Dict[str, Any] = {}
        self._load()

    @classmethod
    def get_instance(cls) -> "OPPConfig":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        with cls._lock:
            cls._instance = None

    def _find_config(self) -> Path:
        """Locate the OPP config, with 3-tier fallback.

        Tier 1: $OPP_CONFIG_PATH (explicit env override)
        Tier 2: config/default.yaml (or .yml) at CWD or repo root
        Tier 3: opp_config.yaml at CWD or repo root (deprecated, warns)

        Raises FileNotFoundError if no candidate exists.
        """
        import warnings

        # Tier 1: explicit env override
        env_path = os.environ.get("OPP_CONFIG_PATH")
        if env_path:
            candidate = Path(env_path)
            if candidate.exists():
                return candidate

        # Tier 2: bundled config/default.yaml
        for base in [Path.cwd(), Path(__file__).parent.parent.parent]:
            for rel in ["config/default.yaml", "config/default.yml"]:
                candidate = base / rel
                if candidate.exists():
                    return candidate

        # Tier 3: legacy opp_config.yaml (back-compat with deprecation warning)
        for base in [Path.cwd(), Path(__file__).parent.parent.parent]:
            candidate = base / "opp_config.yaml"
            if candidate.exists():
                warnings.warn(
                    "opp_config.yaml is deprecated; migrate to config/default.yaml",
                    DeprecationWarning,
                    stacklevel=2,
                )
                return candidate

        raise FileNotFoundError(
            "No OPP config found. Set OPP_CONFIG_PATH or place "
            "config/default.yaml in repo root or CWD."
        )

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
