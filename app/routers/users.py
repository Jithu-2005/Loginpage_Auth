from fastapi import APIRouter, Depends
from app.dependencies.current_user import get_current_user
from app.models.user import User
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def read_my_profile(current_user: User = Depends(get_current_user)) -> User:
    return current_user
