from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded only from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="RESOLVEAI_",
        extra="ignore",
    )

    environment: str = "local"
    database_url: str = "sqlite+pysqlite:///./resolveai.db"
    migration_database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    auth_mode: Literal["local_hs256", "oidc"] = "local_hs256"
    jwt_algorithm: str = "HS256"
    jwt_secret: SecretStr = Field(default=SecretStr("local-development-secret-change-me-32"))
    jwt_issuer: str = "resolveai-local"
    jwt_audience: str = "resolveai-api"
    oidc_jwks_url: str | None = None
    oidc_algorithms: str = "RS256"
    approval_refund_autonomous_limit_minor: int = Field(default=5_000, ge=0)
    approval_refund_single_approval_limit_minor: int = Field(default=50_000, ge=1)
    approval_refund_hard_ceiling_minor: int = Field(default=100_000, ge=1)
    approval_ttl_minutes: int = Field(default=30, ge=1, le=1440)
    artifact_endpoint_url: str = "http://localhost:9000"
    artifact_bucket: str = "resolveai-artifacts"
    artifact_region: str = "us-east-1"
    artifact_access_key: SecretStr = Field(default=SecretStr("resolveai-local"))
    artifact_secret_key: SecretStr = Field(default=SecretStr("resolveai-local-change-me"))
    retention_policy_path: str = "config/retention-policy.json"
    provider_data_policy_path: str = "config/provider-data-policy.json"
    external_adapter_mode: Literal["mock", "rest"] = "mock"
    adapter_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    adapter_max_attempts: int = Field(default=2, ge=1, le=3)
    erp_base_url: str | None = None
    wms_base_url: str | None = None
    payment_base_url: str | None = None
    shipment_base_url: str | None = None
    external_adapter_api_key: SecretStr | None = None
    model_provider_mode: Literal[
        "deterministic", "openai_compatible", "ollama", "hosted"
    ] = "deterministic"
    model_base_url: str = "http://localhost:11434/v1"
    model_name: str = "resolveai-local"
    model_api_key: SecretStr | None = None
    log_level: str = "INFO"

    @model_validator(mode="after")
    def validate_security_configuration(self) -> "Settings":
        if self.environment not in {"local", "test"} and self.auth_mode == "local_hs256":
            raise ValueError("local HS256 authentication is disabled outside local/test")
        if self.auth_mode == "oidc" and not self.oidc_jwks_url:
            raise ValueError("OIDC authentication requires RESOLVEAI_OIDC_JWKS_URL")
        if not (
            self.approval_refund_autonomous_limit_minor
            < self.approval_refund_single_approval_limit_minor
            < self.approval_refund_hard_ceiling_minor
        ):
            raise ValueError("refund policy thresholds must be strictly increasing")
        return self

    @property
    def alembic_database_url(self) -> str:
        return self.migration_database_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
