"""
Configuration loader for Heckler.

Loads settings from config.yaml in the project root.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class Config:
    """Configuration container loaded from config.yaml."""

    def __init__(self, config_path: Path | str | None = None):
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to config.yaml (defaults to project root)
        """
        if config_path is None:
            # Default to config.yaml in project root (two levels up from this file)
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path) as f:
            self._config: dict[str, Any] = yaml.safe_load(f)

        logger.info(f"Loaded configuration from {config_path}")

    @property
    def ollama_host(self) -> str:
        """Ollama server host."""
        return self._config["ollama"]["host"]

    @property
    def ollama_port(self) -> int:
        """Ollama server port."""
        return self._config["ollama"]["port"]

    @property
    def ollama_model(self) -> str:
        """Ollama model name."""
        return self._config["ollama"]["model"]

    @property
    def osc_host(self) -> str:
        """OSC server host."""
        return self._config["osc"]["host"]

    @property
    def osc_port(self) -> int:
        """OSC server port."""
        return self._config["osc"]["port"]

    @property
    def ws_host(self) -> str:
        """WebSocket server host."""
        return self._config["websocket"]["host"]

    @property
    def ws_port(self) -> int:
        """WebSocket server port."""
        return self._config["websocket"]["port"]

    @property
    def log_level(self) -> str:
        """Logging level."""
        return self._config.get("logging", {}).get("level", "INFO")

    @property
    def memes_enabled(self) -> bool:
        """Whether meme generation is enabled."""
        return self._config.get("memes", {}).get("enabled", True)

    @property
    def memes_save_to_disk(self) -> bool:
        """Whether to save generated memes to disk."""
        return self._config.get("memes", {}).get("save_to_disk", False)

    @property
    def memes_output_directory(self) -> str:
        """Directory to save generated memes."""
        return self._config.get("memes", {}).get("output_directory", "generated_memes")

    @property
    def memes_min_interval(self) -> int:
        """Minimum number of text responses between memes."""
        return self._config.get("memes", {}).get("min_interval", 5)

    @property
    def memes_max_interval(self) -> int:
        """Maximum number of text responses between memes."""
        return self._config.get("memes", {}).get("max_interval", 10)
