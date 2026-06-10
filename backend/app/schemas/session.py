from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    user_team_id: int = Field(..., ge=1, le=10)


class TeamSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: int
    team_name: str
    short_name: str


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_team_id: int
    phase: str
    initial_purse_cr: Decimal
    user_team: TeamSummary
    created_at: datetime
