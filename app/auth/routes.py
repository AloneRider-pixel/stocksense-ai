from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.api.public_rate_limit import enforce_public_rate_limit
from app.auth.dependencies import get_current_user
from app.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.service import AuthService
from app.core.config import settings
from app.db.database import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_public_rate_limit)],
)
def register(request: RegisterRequest) -> UserResponse:
    session = get_session()
    try:
        user = AuthService(session).register(
            email=request.email,
            password=request.password,
            full_name=request.full_name,
        )
        return UserResponse.model_validate(user, from_attributes=True)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REGISTRATION_FAILED",
                "message": str(exc),
            },
        ) from exc
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_UNAVAILABLE",
                "message": "Account registration is temporarily unavailable.",
            },
        ) from exc
    finally:
        session.close()


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(enforce_public_rate_limit)],
)
def login(request: LoginRequest) -> TokenResponse:
    session = get_session()
    try:
        user = AuthService(session).authenticate(
            email=request.email,
            password=request.password,
        )
        return TokenResponse(
            access_token=AuthService.issue_token(user),
            expires_in=settings.access_token_minutes * 60,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": str(exc),
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_UNAVAILABLE",
                "message": "Login is temporarily unavailable.",
            },
        ) from exc
    finally:
        session.close()


@router.get("/me", response_model=UserResponse)
def me(current_user=Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user, from_attributes=True)
