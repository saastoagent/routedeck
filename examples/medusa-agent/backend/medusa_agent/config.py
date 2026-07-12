from __future__ import annotations

import os
from pathlib import Path

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr


_DEFAULT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env.local"


class Settings(BaseModel):
    """Required Medusa/RouteDeck runtime configuration.

    IDs and secrets intentionally have no product-code defaults. The protected
    demo provisioner writes them to ``examples/medusa-agent/.env.local``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    medusa_base_url: AnyHttpUrl
    medusa_publishable_key: SecretStr
    medusa_region_id: str = Field(min_length=1)
    medusa_country_code: str = Field(min_length=2, max_length=2)
    medusa_sales_channel_id: str = Field(min_length=1)
    medusa_payment_provider_id: str = Field(min_length=1)
    routedeck_database_path: Path
    routedeck_state_encryption_key: SecretStr
    openai_api_key: SecretStr | None
    openai_model: str = Field(min_length=1)
    medusa_timeout_seconds: float = Field(default=15.0, gt=0)

    @classmethod
    def from_env(cls, env_file: Path = _DEFAULT_ENV_PATH) -> Settings:
        values = _read_env_file(env_file)
        values.update(
            {name: value for name, value in os.environ.items() if name in _ENV_FIELDS}
        )
        payload: dict[str, object] = {
            field_name: values[environment_name]
            for environment_name, field_name in _FIELD_BY_ENV.items()
            if environment_name in values
        }
        payload["openai_api_key"] = values.get("OPENAI_API_KEY") or None
        return cls.model_validate(payload)


_ENV_FIELDS = frozenset(
    {
        "MEDUSA_BASE_URL",
        "MEDUSA_PUBLISHABLE_KEY",
        "MEDUSA_REGION_ID",
        "MEDUSA_COUNTRY_CODE",
        "MEDUSA_SALES_CHANNEL_ID",
        "MEDUSA_PAYMENT_PROVIDER_ID",
        "ROUTEDECK_DATABASE_PATH",
        "ROUTEDECK_STATE_ENCRYPTION_KEY",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "MEDUSA_TIMEOUT_SECONDS",
    }
)

_FIELD_BY_ENV = {
    "MEDUSA_BASE_URL": "medusa_base_url",
    "MEDUSA_PUBLISHABLE_KEY": "medusa_publishable_key",
    "MEDUSA_REGION_ID": "medusa_region_id",
    "MEDUSA_COUNTRY_CODE": "medusa_country_code",
    "MEDUSA_SALES_CHANNEL_ID": "medusa_sales_channel_id",
    "MEDUSA_PAYMENT_PROVIDER_ID": "medusa_payment_provider_id",
    "ROUTEDECK_DATABASE_PATH": "routedeck_database_path",
    "ROUTEDECK_STATE_ENCRYPTION_KEY": "routedeck_state_encryption_key",
    "OPENAI_MODEL": "openai_model",
    "MEDUSA_TIMEOUT_SECONDS": "medusa_timeout_seconds",
}


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name in _ENV_FIELDS:
            values[name] = value.strip().strip('"').strip("'")
    return values


__all__ = ["Settings"]
