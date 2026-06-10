from fastapi import APIRouter

from app.api.v1 import auction, retention, sessions, teams

api_router = APIRouter()
api_router.include_router(teams.router)
api_router.include_router(sessions.router)
api_router.include_router(retention.router)
api_router.include_router(auction.router)
