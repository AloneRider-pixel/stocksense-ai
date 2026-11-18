"""Manual local evidence collector. No scheduler or production application wiring.

Offline: python -m scripts.collect_data_evidence --input feed.xml --output /tmp/evidence.json
One public-feed read: python -m scripts.collect_data_evidence --fetch-sebi --output /tmp/evidence.json
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.market_data.trust import SEBI_FEED, parse_sebi_feed, snapshot_json


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("feed redirect requires source review")


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
        temporary = f.name
        f.write(text)
    try:
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def collect(output: Path, *, raw: bytes | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    if raw is None:
        state_path = output.with_suffix(output.suffix + ".attempt.json")
        if state_path.exists():
            prior = datetime.fromisoformat(json.loads(state_path.read_text())["attempted_at"])
            if now - prior < timedelta(hours=1):
                raise ValueError("SEBI feed cooldown: at least one hour between manual attempts")
        # Persist failures too: a 403/429 must not become an immediate retry loop.
        atomic_write(state_path, json.dumps({"attempted_at": now.isoformat()}))
        request = Request(SEBI_FEED, headers={
            "User-Agent": "StockSenseResearch/0.1 (manual RSS reader)",
            "Accept": "application/rss+xml, application/xml, text/xml",
        })
        try:
            with build_opener(NoRedirect).open(request, timeout=15) as response:
                if response.status != 200:
                    raise ValueError(f"feed returned HTTP {response.status}; no automatic retry")
                raw = response.read(2_000_001)
        except HTTPError as exc:
            raise ValueError(f"feed returned HTTP {exc.code}; hold source, no automatic retry") from exc
    result = parse_sebi_feed(raw, fetched_at=now)
    atomic_write(output, snapshot_json(result))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input", type=Path, help="offline RSS file")
    mode.add_argument("--fetch-sebi", action="store_true", help="one manual official feed read")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = collect(args.output, raw=args.input.read_bytes() if args.input else None)
    except (ValueError, OSError, ET.ParseError) as exc:
        parser.exit(1, f"Collection not completed: {exc}\nPrevious successful output preserved.\n")
    print(json.dumps({"status": result["collection_status"], "records": len(result["records"]),
                      "rejected": len(result["rejected"]), "output": str(args.output),
                      "public_display": "review_required"}))


if __name__ == "__main__":
    main()
