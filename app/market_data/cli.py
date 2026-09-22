from __future__ import annotations

import argparse
import json

from app.db.database import get_session
from app.db.repository import MarketDataRepository, PredictionRepository
from app.market_data.factory import get_market_data_provider
from app.market_data.ingestion import MarketDataIngestionService


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest market data into StockSense AI.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    session = get_session()
    try:
        service = MarketDataIngestionService(
            provider=get_market_data_provider(),
            repository=MarketDataRepository(session),
            prediction_repository=PredictionRepository(session),
        )
        result = service.ingest(args.symbol, limit=args.limit)
        print(json.dumps(result, indent=2))
    finally:
        session.close()


if __name__ == "__main__":
    main()
