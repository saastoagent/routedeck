from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _read_local_env(path: Path = DEFAULT_ENV_PATH) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _env_value(name: str, env_file: dict[str, str], default: str | None = None) -> str | None:
    return os.getenv(name) or env_file.get(name) or default


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None = None
    medusa_agent_model: str = "gpt-5-mini"
    medusa_backend_url: str | None = None
    medusa_publishable_api_key: str | None = None
    keepalive_interval: float = 15.0
    model_timeout_seconds: float = 30.0
    medusa_store_timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "Settings":
        env_file = _read_local_env(DEFAULT_ENV_PATH)
        return cls(
            openai_api_key=_env_value("OPENAI_API_KEY", env_file),
            medusa_agent_model=_env_value("MEDUSA_AGENT_MODEL", env_file, "gpt-5-mini") or "gpt-5-mini",
            medusa_backend_url=_env_value("MEDUSA_BACKEND_URL", env_file),
            medusa_publishable_api_key=_env_value("MEDUSA_PUBLISHABLE_API_KEY", env_file),
        )


settings = Settings.from_env()
