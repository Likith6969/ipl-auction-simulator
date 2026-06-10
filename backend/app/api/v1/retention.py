from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.retention import (
    AllRetentionsView,
    RetentionConfirmResponse,
    RetentionSubmit,
    RetentionView,
)
from app.services.retention_service import (
    InvalidPhaseError,
    InvalidRetentionError,
    RetentionAlreadyConfirmedError,
    RetentionService,
)
from app.services.session_service import SessionNotFoundError

router = APIRouter(prefix="/sessions/{session_id}/retention", tags=["retention"])


@router.get("", response_model=RetentionView)
def get_retention_view(session_id: str, db: Session = Depends(get_db)) -> RetentionView:
    service = RetentionService(db)
    try:
        return service.get_retention_view(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/all", response_model=AllRetentionsView)
def get_all_retentions(session_id: str, db: Session = Depends(get_db)) -> AllRetentionsView:
    service = RetentionService(db)
    try:
        return service.get_all_retentions(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=RetentionConfirmResponse, status_code=status.HTTP_201_CREATED)
def confirm_retentions(
    session_id: str,
    body: RetentionSubmit,
    db: Session = Depends(get_db),
) -> RetentionConfirmResponse:
    service = RetentionService(db)
    try:
        return service.submit_user_retentions(session_id, body)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RetentionAlreadyConfirmedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidPhaseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InvalidRetentionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
