"""
Configuration loader for Heckler.

Loads settings from config.yaml in the project root.
"""

import logging
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

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

        # Load .env from project root (silently ignored if absent)
        env_path = config_path.parent / ".env"
        load_dotenv(env_path)

        with open(config_path) as f:
            self._config: dict[str, Any] = yaml.safe_load(f)

        logger.info(f"Loaded configuration from {config_path}")

    @property
    def llm_backend(self) -> str:
        """LLM backend to use: claude, ollama_remote, or ollama_local."""
        return self._config.get("llm_backend", "ollama_remote")

    @property
    def ollama_host(self) -> str:
        """Ollama remote server host."""
        return self._config["ollama"]["host"]

    @property
    def ollama_port(self) -> int:
        """Ollama remote server port."""
        return self._config["ollama"]["port"]

    @property
    def ollama_model(self) -> str:
        """Ollama remote model name."""
        return self._config["ollama"]["model"]

    @property
    def ollama_local_host(self) -> str:
        """Ollama local server host."""
        return self._config.get("ollama_local", {}).get("host", "localhost")

    @property
    def ollama_local_port(self) -> int:
        """Ollama local server port."""
        return self._config.get("ollama_local", {}).get("port", 11434)

    @property
    def ollama_local_model(self) -> str:
        """Ollama local model name (should be small/CPU-friendly)."""
        return self._config.get("ollama_local", {}).get("model", "qwen2.5-coder:3b")

    @property
    def claude_model(self) -> str:
        """Claude model name."""
        return self._config.get("claude", {}).get("model", "claude-haiku-4-5-20251001")

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
    def startup_frontend(self) -> bool:
        """Whether start.py should launch the Vite frontend."""
        return self._config.get("startup", {}).get("frontend", True)

    @property
    def startup_browser(self) -> bool:
        """Whether start.py should open a browser window."""
        return self._config.get("startup", {}).get("browser", True)

    @property
    def startup_browser_cmd(self) -> str:
        """Browser command to use."""
        return self._config.get("startup", {}).get("browser_cmd", "chromium-browser")

    @property
    def startup_network_profile(self) -> str:
        """nmcli connection profile to bring up (only used for ollama_remote)."""
        return self._config.get("startup", {}).get("network_profile", "direct-link")

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
