from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auction import AuctionInitializationResult
from app.services.auction_initialization_service import AuctionInitializationService
from app.services.errors import InvalidPhaseError, RetentionsIncompleteError
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
