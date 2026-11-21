"""Service configuration, read from APISENTINEL_* environment variables only."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(RuntimeError):
    """Raised at startup with a message that never echoes configured values."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APISENTINEL_", extra="ignore")

    # Shared secret the Java backend sends in X-Internal-Token. Required; no default.
    internal_token: SecretStr = Field(min_length=32)
    max_spec_mb: float = Field(default=5.0, gt=0, le=50)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Interactive /docs and /openapi.json are off unless explicitly enabled.
    enable_docs: bool = False

    @property
    def max_spec_bytes(self) -> int:
        return int(self.max_spec_mb * 1024 * 1024)

    @property
    def max_request_bytes(self) -> int:
        # Two specs, JSON string escaping can roughly double their size, plus envelope room.
        return self.max_spec_bytes * 4 + 256 * 1024


def load_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]  # values come from the environment
    except ValidationError as exc:
        problems = ", ".join(
            f"APISENTINEL_{'_'.join(str(p) for p in err['loc']).upper()} ({err['msg']})"
            for err in exc.errors(include_input=False)
        )
        raise ConfigurationError(f"Invalid analyzer configuration: {problems}") from None
