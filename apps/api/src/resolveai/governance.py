import json
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class DataClassification(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    SENSITIVE_PII = "SENSITIVE_PII"
    RESTRICTED = "RESTRICTED"


class RetentionRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: int | None = Field(default=None, ge=1)
    derived_classes: tuple[str, ...] = ()


class RetentionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    production_configuration_required: bool
    rules: dict[str, RetentionRule]

    def expires_at(self, data_class: str, created_at: datetime) -> datetime | None:
        rule = self.rules[data_class]
        return created_at + timedelta(days=rule.days) if rule.days is not None else None

    def deletion_classes(self, data_class: str) -> tuple[str, ...]:
        rule = self.rules[data_class]
        return (data_class, *rule.derived_classes)


class ProviderRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow: frozenset[DataClassification]


class ProviderDataPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    default_external_provider_allow: frozenset[DataClassification]
    providers: dict[str, ProviderRule]
    rules: dict[str, str]

    def allows(self, provider: str, classification: DataClassification) -> bool:
        if classification is DataClassification.RESTRICTED:
            return False
        rule = self.providers.get(provider)
        allowed = rule.allow if rule else self.default_external_provider_allow
        return classification in allowed


def _load_json(path: str | Path) -> object:
    with Path(path).open(encoding="utf-8") as source:
        return json.load(source)


def load_retention_policy(path: str | Path) -> RetentionPolicy:
    return RetentionPolicy.model_validate(_load_json(path))


def load_provider_data_policy(path: str | Path) -> ProviderDataPolicy:
    return ProviderDataPolicy.model_validate(_load_json(path))
