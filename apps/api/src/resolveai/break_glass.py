from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BreakGlassRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=10, max_length=500)
    ticket_reference: str = Field(min_length=3, max_length=120)
    mfa_verified: bool
    requested_minutes: int = Field(default=15, ge=1, le=60)
    write_access: bool = False
    second_elevation_reference: str | None = Field(default=None, min_length=3, max_length=120)

    @model_validator(mode="after")
    def validate_elevation(self) -> "BreakGlassRequest":
        if not self.mfa_verified:
            raise ValueError("break-glass access requires MFA verification")
        if self.write_access and not self.second_elevation_reference:
            raise ValueError("write access requires a second explicit elevation")
        return self

    def expires_at(self, now: datetime | None = None) -> datetime:
        started = now or datetime.now(tz=UTC)
        return started + timedelta(minutes=self.requested_minutes)
