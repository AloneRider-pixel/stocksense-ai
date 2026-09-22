from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.auth.jwt import decode_access_token
from app.db.database import get_session
from app.db.repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        subject = decode_access_token(token)
        user_id = int(subject)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_TOKEN",
                "message": "The access token is invalid or expired.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    session = get_session()
    try:
        user = UserRepository(session).get_by_id(user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "UNAUTHORIZED",
                    "message": "The authenticated user is not active.",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    finally:
        session.close()
