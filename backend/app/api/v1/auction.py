from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auction import AuctionInitializationResult, AuctionSnapshot
from app.services.auction_engine import AuctionEngineService
from app.services.auction_initialization_service import AuctionInitializationService
from app.services.errors import (
    AuctionNotReadyError,
    InvalidAuctionStateError,
    InvalidPhaseError,
    RetentionsIncompleteError,
)
from app.services.session_service import SessionNotFoundError

router = APIRouter(prefix="/sessions/{session_id}/auction", tags=["auction"])


@router.post("/initialize", response_model=AuctionInitializationResult)
def initialize_auction(session_id: str, db: Session = Depends(get_db)) -> AuctionInitializationResult:
    """
    Initialize the auction for a session where user retentions are already stored.

    Completes any pending AI retentions, removes retained players from the pool,
    reconciles purses, and positions the auction at the first available lot.
    """
    service = AuctionInitializationService(db)
    try:
        return service.initialize(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RetentionsIncompleteError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except InvalidPhaseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/initialize", response_model=AuctionInitializationResult)
def get_auction_initialization_state(
    session_id: str,
    db: Session = Depends(get_db),
) -> AuctionInitializationResult:
    """Return the current auction initialization snapshot (idempotent read)."""
    service = AuctionInitializationService(db)
    try:
        return service.initialize(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RetentionsIncompleteError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except InvalidPhaseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# State-machine foundation endpoints
# ---------------------------------------------------------------------------


@router.get("/state", response_model=AuctionSnapshot)
def get_auction_state(
    session_id: str,
    db: Session = Depends(get_db),
) -> AuctionSnapshot:
    """Return the current auction engine state snapshot (read-only).

    Returns the live_state, current lot, and team purses.  Safe to call at any
    point; does not modify any state.
    """
    engine = AuctionEngineService(db)
    try:
        return engine.get_snapshot(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/start", response_model=AuctionSnapshot, status_code=status.HTTP_200_OK)
def start_auction(
    session_id: str,
    db: Session = Depends(get_db),
) -> AuctionSnapshot:
    """Apply START_AUCTION event: transition from READY → SET_INTRO.

    Must be called after auction initialization (phase must be AUCTION and
    live_state.public_run_state must be READY).  Records a SET_STARTED history
    event and returns the updated snapshot.
    """
    engine = AuctionEngineService(db)
    try:
        return engine.start_auction(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AuctionNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidAuctionStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/open-lot", response_model=AuctionSnapshot, status_code=status.HTTP_200_OK)
def open_lot(
    session_id: str,
    db: Session = Depends(get_db),
) -> AuctionSnapshot:
    """Apply OPEN_LOT event: transition from SET_INTRO → LOT_OPEN.

    Marks the current lot as LIVE and seeds bid-tracking fields
    (current_bid_cr = base_price_cr, leading_team_id = null, bid_count = 0).
    BiddingService will update those fields when actual bids arrive.
    Records a LOT_OPENED history event and returns the updated snapshot.
    """
    engine = AuctionEngineService(db)
    try:
        return engine.open_lot(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AuctionNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidAuctionStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

