from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token
from app.auth.passwords import hash_password, verify_password
from app.db.models import User
from app.db.repository import UserRepository


class AuthService:
    def __init__(self, session: Session) -> None:
        self.users = UserRepository(session)

    def register(self, email: str, password: str, full_name: str | None) -> User:
        normalized_email = email.strip().lower()
        if self.users.get_by_email(normalized_email):
            raise ValueError("An account with this email already exists")

        user = User(
            email=normalized_email,
            password_hash=hash_password(password),
            full_name=full_name.strip() if full_name else None,
            is_active=True,
        )

        try:
            return self.users.create(user)
        except IntegrityError as exc:
            raise ValueError("An account with this email already exists") from exc

    def authenticate(self, email: str, password: str) -> User:
        user = self.users.get_by_email(email.strip().lower())

        if user is None or not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is inactive")

        return user

    @staticmethod
    def issue_token(user: User) -> str:
        return create_access_token(str(user.id))
