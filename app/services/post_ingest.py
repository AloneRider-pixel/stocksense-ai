"""Post-ingestion hooks shared by the worker and the API ingest route.

After new bars land for a symbol, alert rules are evaluated and paper
wallets holding the symbol get a deduped equity snapshot, so the wallet
card, the equity curve and notifications all move with the same ingest.
Failures propagate: the worker lets arq retry the job, the API returns
an error the caller can retry - per-bar and per-date dedupe make retries
safe. Nothing here is silently dropped."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.alerts import AlertService
from app.services.wallet import WalletService


def run_post_ingest(session: Session, symbol: str) -> dict[str, int]:
    alerts = AlertService(session).evaluate_symbol(symbol)
    snapshots = WalletService(session).snapshot_holders(symbol)
    return {"alerts_triggered": alerts, "equity_snapshots": snapshots}
