from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.auth import RefreshRequest, TokenResponse
from app.services.token_service import refresh_tokens

router = APIRouter(prefix="/auth", tags=["Tokens"])


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return refresh_tokens(payload.refresh_token, db)
