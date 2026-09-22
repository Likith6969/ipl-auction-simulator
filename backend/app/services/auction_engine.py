"""
auction_engine.py
=================
AuctionEngineService — the main orchestrator for the IPL auction loop.

Orchestration pattern (applied to every operation)
---------------------------------------------------
    VALIDATE        →  check session phase, live_state version, guard conditions
    DELEGATE        →  call auction_transitions for the next state
    UPDATE RUNTIME  →  mutate live_state and/or auction_pool in-memory
    RECORD HISTORY  →  append an AuctionHistory event
    COMMIT          →  flush & commit the DB transaction
    NOTIFY          →  (future) broadcast via WebSocket

What IS implemented here (state-machine foundation)
----------------------------------------------------
* get_snapshot()     — read-only snapshot of current engine state
* start_auction()    — READY → SET_INTRO
* open_lot()         — SET_INTRO → LOT_OPEN  (marks the lot LIVE, seeds bid fields)

What is NOT YET implemented
---------------------------
* place_bid()        — deferred to BiddingService
* skip_lot()         — deferred to LotProgressionService
* advance_countdown()— deferred to CountdownService
* close_lot()        — deferred to LotProgressionService + SquadReconciliationService
* rtm_decision()     — deferred to RTMService
* WebSocket push     — deferred to NotificationService
* AI bidding         — deferred to AIBiddingStrategy

The engine deliberately does NOT contain bid logic, squad accounting, countdown
execution, or RTM resolution.  Those responsibilities belong in focused helper
services that will be wired here as the project evolves.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.domain.auction_timing import build_initial_live_state
from app.domain.auction_transitions import (
    InvalidTransitionError,
    assert_not_internal,
    get_next_state,
)
from app.domain.enums import (
    LIVE_STATE_VERSION,
    AuctionEvent,
    AuctionPhase,
    HistoryEventType,
    LotStatus,
    PublicRunState,
)
from app.models.auction_history import AuctionHistory
from app.models.auction_state import AuctionState
from app.repositories.session_repository import SessionRepository
from app.repositories.team_repository import TeamRepository
from app.schemas.auction import (
    AuctionSnapshot,
    CurrentLotSnapshot,
    LiveStateRead,
    TeamPurseState,
)
from app.services.errors import AuctionNotReadyError, InvalidAuctionStateError
from app.services.session_service import SessionNotFoundError

logger = logging.getLogger(__name__)


class AuctionEngineService:
    """Orchestrates the auction state machine.

    All public methods follow the VALIDATE → DELEGATE → UPDATE RUNTIME →
    RECORD HISTORY → COMMIT → NOTIFY pattern.  State transitions are strictly
    handled by ``auction_transitions.get_next_state()``; this service never
    hard-codes next-state logic directly.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.session_repo = SessionRepository(db)
        self.team_repo = TeamRepository(db)

    # -------------------------------------------------------------------------
    # Read operations
    # -------------------------------------------------------------------------

    def get_snapshot(self, session_id: str) -> AuctionSnapshot:
        """Return the current auction state snapshot (no writes).

        Works for sessions in any phase; live_state is lazily initialised to
        READY if the column contains an empty dict (e.g. for rows that were
        created before the live_state migration ran).
        """
        auction_state = self._get_session(session_id)
        live_state = self._read_or_default_live_state(auction_state)
        return self._build_snapshot(session_id, auction_state, live_state)

    # -------------------------------------------------------------------------
    # State-machine operations  (READY → SET_INTRO → LOT_OPEN)
    # -------------------------------------------------------------------------

    def start_auction(self, session_id: str) -> AuctionSnapshot:
        """Apply the START_AUCTION event: READY → SET_INTRO.

        The SET_INTRO state signals to the frontend that the auction is about
        to begin and the first set's intro screen should be displayed.

        Raises
        ------
        AuctionNotReadyError
            If the session is not in AUCTION phase.
        InvalidAuctionStateError
            If the current public_run_state is not READY.
        """
        # VALIDATE
        auction_state = self._get_session(session_id)
        self._assert_auction_phase(session_id, auction_state)
        live_state = self._read_or_default_live_state(auction_state)
        current_prs = PublicRunState(live_state["public_run_state"])

        # DELEGATE — pure transition lookup (raises on invalid)
        next_prs = self._do_transition(
            session_id, live_state, current_prs, AuctionEvent.START_AUCTION
        )

        # UPDATE RUNTIME
        auction_state.live_state = live_state
        flag_modified(auction_state, "live_state")

        # RECORD HISTORY
        self.db.add(AuctionHistory(
            auction_state_id=auction_state.id,
            event_type=HistoryEventType.SET_STARTED,
            payload={
                "auction_set": auction_state.current_auction_set,
                "from_state": current_prs.value,
                "to_state": next_prs.value,
                "event": AuctionEvent.START_AUCTION.value,
            },
        ))

        # COMMIT
        self.db.commit()
        self.db.refresh(auction_state)

        logger.info(
            "Session %s: start_auction → %s → %s",
            session_id, current_prs.value, next_prs.value,
        )
        return self._build_snapshot(session_id, auction_state, auction_state.live_state)

    def open_lot(self, session_id: str) -> AuctionSnapshot:
        """Apply the OPEN_LOT event: SET_INTRO → LOT_OPEN.

        This transitions the current PENDING pool lot to LIVE and seeds the
        bid-tracking fields (current_bid_cr, leading_team_id, bid_count) that
        BiddingService will later update.  The lot's base_price_cr is recorded
        as the starting bid floor — no team has bid yet.

        Raises
        ------
        AuctionNotReadyError
            If the session is not in AUCTION phase.
        InvalidAuctionStateError
            If the current public_run_state does not permit OPEN_LOT
            (expected SET_INTRO).
        """
        # VALIDATE
        auction_state = self._get_session(session_id)
        self._assert_auction_phase(session_id, auction_state)
        live_state = self._read_or_default_live_state(auction_state)
        current_prs = PublicRunState(live_state["public_run_state"])

        # DELEGATE — transition lookup
        next_prs = self._do_transition(
            session_id, live_state, current_prs, AuctionEvent.OPEN_LOT
        )

        # UPDATE RUNTIME — mark current lot as LIVE and seed bid fields
        pool = dict(auction_state.auction_pool)
        lots: list[dict] = pool.get("lots", [])
        lot_index: int = pool.get("current_lot_index", 0)
        lot_snapshot: dict | None = None

        if lots and lot_index < len(lots):
            lot = dict(lots[lot_index])
            lot["status"] = LotStatus.LIVE.value

            # Seed bid-tracking fields so BiddingService has a consistent
            # starting point.  These will be overwritten by BiddingService.
            # current_bid_cr starts at the base price (the minimum valid bid).
            if "current_bid_cr" not in lot:
                lot["current_bid_cr"] = lot["base_price_cr"]
                lot["leading_team_id"] = None
                lot["bid_count"] = 0

            lots[lot_index] = lot
            pool["lots"] = lots
            auction_state.auction_pool = pool
            flag_modified(auction_state, "auction_pool")
            lot_snapshot = lot

        auction_state.live_state = live_state
        flag_modified(auction_state, "live_state")

        # RECORD HISTORY
        history_payload: dict = {
            "from_state": current_prs.value,
            "to_state": next_prs.value,
            "event": AuctionEvent.OPEN_LOT.value,
            "lot_index": lot_index,
        }
        if lot_snapshot:
            history_payload.update({
                "player_id": lot_snapshot.get("player_id"),
                "player_name": lot_snapshot.get("player_name"),
                "auction_set": lot_snapshot.get("auction_set"),
                "base_price_cr": lot_snapshot.get("base_price_cr"),
            })

        self.db.add(AuctionHistory(
            auction_state_id=auction_state.id,
            event_type=HistoryEventType.LOT_OPENED,
            payload=history_payload,
        ))

        # COMMIT
        self.db.commit()
        self.db.refresh(auction_state)

        logger.info(
            "Session %s: open_lot (index=%d) → %s → %s",
            session_id, lot_index, current_prs.value, next_prs.value,
        )
        return self._build_snapshot(session_id, auction_state, auction_state.live_state)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _get_session(self, session_id: str) -> AuctionState:
        """Load the AuctionState or raise SessionNotFoundError."""
        state = self.session_repo.get_by_id(session_id)
        if state is None:
            raise SessionNotFoundError(session_id)
        return state

    def _assert_auction_phase(self, session_id: str, auction_state: AuctionState) -> None:
        """Raise AuctionNotReadyError if phase != AUCTION."""
        if auction_state.phase != AuctionPhase.AUCTION:
            raise AuctionNotReadyError(session_id, auction_state.phase)

    def _read_or_default_live_state(self, auction_state: AuctionState) -> dict:
        """Return the current live_state dict, defaulting to READY if unset.

        Rows created before the live_state migration have ``{}`` as the column
        value.  In that case we return the canonical initial state without
        persisting it (that happens on the next write operation).
        """
        existing = auction_state.live_state or {}
        if existing.get("version") == LIVE_STATE_VERSION:
            return dict(existing)
        # Unversioned or empty — return the canonical default (not yet written)
        return build_initial_live_state()

    def _do_transition(
        self,
        session_id: str,
        live_state: dict,
        current_prs: PublicRunState,
        event: AuctionEvent,
    ) -> PublicRunState:
        """Apply *event* to *live_state*, returning the next PublicRunState.

        Mutates *live_state* in-place (sets public_run_state).
        Wraps InvalidTransitionError with session context.
        """
        try:
            next_prs = get_next_state(current_prs, event)
        except InvalidTransitionError as exc:
            raise InvalidAuctionStateError(session_id, exc.from_state, exc.event) from exc

        # Safety guard: next state must be a public state, never internal
        assert_not_internal(next_prs.value)

        live_state["public_run_state"] = next_prs.value
        return next_prs

    def _build_snapshot(
        self,
        session_id: str,
        auction_state: AuctionState,
        live_state_raw: dict,
    ) -> AuctionSnapshot:
        """Build the full AuctionSnapshot response object."""
        # Ensure we always have a fully-structured live_state for serialisation
        if not live_state_raw or live_state_raw.get("version") != LIVE_STATE_VERSION:
            live_state_raw = build_initial_live_state()

        live_state_read = LiveStateRead(
            version=live_state_raw["version"],
            public_run_state=live_state_raw["public_run_state"],
            speed_profile=live_state_raw["speed_profile"],
            is_accelerated=live_state_raw["is_accelerated"],
            pause=live_state_raw["pause"],
            countdown=live_state_raw["countdown"],
            rtm_window=live_state_raw["rtm_window"],
            internal_phase=live_state_raw.get("internal_phase"),
            timing_ms=live_state_raw["timing_ms"],
        )

        current_lot = self._build_current_lot(auction_state)
        team_purses = self._build_team_purses(auction_state)

        return AuctionSnapshot(
            session_id=session_id,
            phase=auction_state.phase,
            current_auction_set=auction_state.current_auction_set,
            current_player_id=auction_state.current_player_id,
            live_state=live_state_read,
            current_lot=current_lot,
            team_purses=team_purses,
        )

    def _build_current_lot(self, auction_state: AuctionState) -> CurrentLotSnapshot | None:
        """Derive the CurrentLotSnapshot from auction_pool.lots[current_lot_index]."""
        pool = auction_state.auction_pool
        if not pool:
            return None
        lots: list[dict] = pool.get("lots", [])
        lot_index: int = pool.get("current_lot_index", 0)
        if not lots or lot_index >= len(lots):
            return None

        lot = lots[lot_index]
        raw_current_bid = lot.get("current_bid_cr")

        return CurrentLotSnapshot(
            lot_index=lot_index,
            player_id=lot["player_id"],
            player_name=lot["player_name"],
            auction_set=lot["auction_set"],
            set_name=lot["set_name"],
            base_price_cr=Decimal(str(lot["base_price_cr"])),
            is_overseas=bool(lot.get("is_overseas", False)),
            status=lot["status"],
            current_bid_cr=(
                Decimal(str(raw_current_bid)) if raw_current_bid is not None else None
            ),
            leading_team_id=lot.get("leading_team_id"),
            bid_count=int(lot.get("bid_count", 0)),
        )

    def _build_team_purses(self, auction_state: AuctionState) -> list[TeamPurseState]:
        """Build team purse list from team_states JSON."""
        result: list[TeamPurseState] = []
        teams = self.team_repo.list_all()
        for team in teams:
            state = auction_state.team_states.get(str(team.team_id), {})
            result.append(TeamPurseState(
                team_id=team.team_id,
                short_name=team.short_name,
                purse_remaining_cr=Decimal(str(state.get("purse_remaining_cr", "0"))),
                retention_spent_cr=Decimal(str(state.get("retention_spent_cr", "0"))),
                auction_spent_cr=Decimal(str(state.get("auction_spent_cr", "0"))),
                squad_count=int(state.get("squad_count", 0)),
                overseas_count=int(state.get("overseas_count", 0)),
            ))
        return result
