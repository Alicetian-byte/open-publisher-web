from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.redis_client import redis_client

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health(db: Session = Depends(get_db)):
    result = {"status": "ok", "database": "ok", "redis": "ok"}

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        result["database"] = "error"
        result["status"] = "degraded"

    try:
        redis_client.ping()
    except Exception:
        result["redis"] = "error"
        result["status"] = "degraded"

    return result
