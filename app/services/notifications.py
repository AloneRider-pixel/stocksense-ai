"""Notification delivery seam.

Alerts write an in-app notification row first. External delivery goes
through the Notifier interface; the only implementation right now is
LogNotifier, which logs and sends nothing. Real email delivery is added
only after the owner approves the provider, recipient and wording."""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class Notifier(Protocol):
    def send(self, *, user_id: int, title: str, body: str) -> None: ...


class LogNotifier:
    """Default notifier: log-only, never sends anything anywhere."""

    def send(self, *, user_id: int, title: str, body: str) -> None:
        logger.info("notification (log-only) user=%s title=%s", user_id, title)


def get_notifier() -> Notifier:
    return LogNotifier()
