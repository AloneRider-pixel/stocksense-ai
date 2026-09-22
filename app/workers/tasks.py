from __future__ import annotations

from arq import Retry

from app.core.config import settings
from app.db.database import get_session
from app.db.repository import MarketDataRepository, PredictionRepository
from app.market_data.factory import get_market_data_provider
from app.market_data.ingestion import MarketDataIngestionService


async def refresh_market_data(ctx, symbol: str) -> dict[str, int | str]:
    session = get_session()
    try:
        service = MarketDataIngestionService(
            provider=get_market_data_provider(),
            repository=MarketDataRepository(session),
            prediction_repository=PredictionRepository(session),
        )
        return service.ingest(symbol, limit=settings.market_data_max_rows)
    except Exception as exc:
        raise Retry(defer=ctx["job_try"] * 15) from exc
    finally:
        session.close()


async def refresh_configured_markets(ctx) -> dict[str, int]:
    total_fetched = 0
    total_inserted = 0
    total_evaluated = 0

    for symbol in settings.market_data_symbol_list:
        result = await refresh_market_data(ctx, symbol)
        total_fetched += int(result["fetched"])
        total_inserted += int(result["inserted"])
        total_evaluated += int(result["predictions_evaluated"])

    return {
        "symbols": len(settings.market_data_symbol_list),
        "fetched": total_fetched,
        "inserted": total_inserted,
        "predictions_evaluated": total_evaluated,
    }
