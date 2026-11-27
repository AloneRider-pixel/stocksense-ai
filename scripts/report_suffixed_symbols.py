"""Read-only diagnostic: stored symbols that carry an exchange suffix (".NS", ".BO", ".L", ...).

SELECT only. It never writes, merges or renames anything. Run it against the real database only with the
owner's go-ahead; it prints counts per table so someone can decide what, if anything, to do.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.market_data.symbols import normalize_symbol

SUFFIXED = re.compile(r"\.[A-Z]{1,4}$")
_US_SHARE_CLASSES = {"BRK.A", "BRK.B", "BF.A", "BF.B"}


def find_suffixed_symbols(db) -> dict[str, dict[str, object]]:
    from app.db.models import AlertRule, MarketBarRecord, PaperOrder, PaperPosition, PredictionRecord, ScannerBar, WatchlistItem

    tables = {
        "market_bars": MarketBarRecord,
        "predictions": PredictionRecord,
        "watchlist": WatchlistItem,
        "alert_rules": AlertRule,
        "paper_orders": PaperOrder,
        "paper_positions": PaperPosition,
        "scanner_bars": ScannerBar,
    }
    out: dict[str, dict[str, object]] = {}
    for name, model in tables.items():
        column = getattr(model, "symbol", None)
        if column is None:
            continue
        counts = {sym: n for sym, n in db.execute(select(column, func.count()).group_by(column)).all()}
        suffixed = {s: n for s, n in counts.items() if s and SUFFIXED.search(s.upper()) and s.upper() not in _US_SHARE_CLASSES}
        would_normalize = {s: normalize_symbol(s) for s in suffixed if normalize_symbol(s) != s.upper()}
        out[name] = {"suffixed": suffixed, "bare_form_if_normalized": would_normalize, "rows_total": sum(counts.values())}
    return out


def main() -> None:
    from app.db.database import SessionLocal

    with SessionLocal() as db:
        result = find_suffixed_symbols(db)
    print("Read-only. Counts of stored symbols that end in an exchange suffix. Nothing was changed.")
    for table, info in result.items():
        print(f"{table}: {len(info['suffixed'])} suffixed symbol(s) in {info['rows_total']} rows")
        for sym, n in sorted(info["suffixed"].items()):
            bare = info["bare_form_if_normalized"].get(sym)
            print(f"  {sym}: {n} row(s)" + (f"  (bare form {bare} may also exist as a separate series)" if bare else ""))


if __name__ == "__main__":
    main()
