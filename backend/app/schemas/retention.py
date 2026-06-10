from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RetentionSlotCost(BaseModel):
    slot: int
    cost_cr: Decimal


class RetentionPlayerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int
    name: str
    country: str
    role: str
    is_captain: bool
    is_overseas: bool
    base_price_cr: Decimal


class RetentionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int
    retention_slot: int
    retention_cost_cr: Decimal
    player: RetentionPlayerRead


class RetentionSummary(BaseModel):
    initial_purse_cr: Decimal
    total_retention_cost_cr: Decimal
    remaining_purse_cr: Decimal
    slots_selected: int


class RetentionView(BaseModel):
    session_id: str
    team_id: int
    team_name: str
    short_name: str
    phase: str
    retention_costs: list[RetentionSlotCost]
    eligible_players: list[RetentionPlayerRead]
    selected_retentions: list[RetentionItemRead]
    summary: RetentionSummary
    is_confirmed: bool


class RetentionSubmitItem(BaseModel):
    player_id: int = Field(..., ge=1)
    slot: int = Field(..., ge=1, le=3)


class RetentionSubmit(BaseModel):
    retentions: list[RetentionSubmitItem] = Field(..., min_length=3, max_length=3)


class RetentionConfirmResponse(BaseModel):
    session_id: str
    phase: str
    retentions: list[RetentionItemRead]
    summary: RetentionSummary
    is_confirmed: bool = True
    ai_teams_retained: int = 0
    all_retentions_complete: bool = False


class TeamRetentionSummary(BaseModel):
    team_id: int
    team_name: str
    short_name: str
    is_user_team: bool
    retentions: list[RetentionItemRead]
    summary: RetentionSummary
    is_confirmed: bool


class AllRetentionsView(BaseModel):
    session_id: str
    phase: str
    teams: list[TeamRetentionSummary]
    all_retentions_complete: bool
