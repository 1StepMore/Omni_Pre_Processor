import os
import threading
from pathlib import Path
from typing import Any

from opp.logger import logger
from opp.config.constants import DEFAULT_CONFIG_NAME


class OPPConfig:
    _instance: "OPPConfig | None" = None
    _lock = threading.Lock()

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or self._find_config()
        self._config: dict[str, Any] = {}
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
        # Walk up from __file__ to find repo root (handles editable installs
        # where __file__ is at src/opp/config/__init__.py and config/ sits at
        # the project root, one level above src/).
        candidates = [Path.cwd()]
        _f = Path(__file__).resolve().parent  # start from config/ dir
        for _ in range(5):  # max 5 levels up
            candidates.append(_f)
            _f = _f.parent
        seen = set()
        for base in candidates:
            base_s = str(base.resolve())
            if base_s in seen:
                continue
            seen.add(base_s)
            for rel in [DEFAULT_CONFIG_NAME, "config/default.yml"]:
                candidate = base / rel
                if candidate.exists():
                    return candidate

        # Tier 3: legacy opp_config.yaml (back-compat with deprecation warning)
        seen = set()
        for base in candidates:
            base_s = str(base.resolve())
            if base_s in seen:
                continue
            seen.add(base_s)
            candidate = base / "opp_config.yaml"
            if candidate.exists():
                warnings.warn(
                    f"opp_config.yaml is deprecated; migrate to {DEFAULT_CONFIG_NAME}",
                    DeprecationWarning,
                    stacklevel=2,
                )
                return candidate

        raise FileNotFoundError(
            "No OPP config found. Set OPP_CONFIG_PATH or place "
            f"{DEFAULT_CONFIG_NAME} in repo root or CWD."
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

    def _default_config(self) -> dict[str, Any]:
        return {
            "pdf": "simple",
            "html": "simple",
        }

    def get_extractor_mode(self, fmt: str) -> str:
        return self._config.get(fmt, "simple")


def load_config(config_path: Path | None = None) -> OPPConfig:
    OPPConfig.reset_instance()
    return OPPConfig(config_path)


def get_config() -> OPPConfig:
    return OPPConfig.get_instance()
