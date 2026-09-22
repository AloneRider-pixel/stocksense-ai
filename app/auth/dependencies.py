from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt import decode_access_token
from app.db.database import get_session
from app.db.repository import UserRepository


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "A bearer access token is required.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(decode_access_token(credentials.credentials))
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
