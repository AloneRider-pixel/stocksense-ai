# StockSense data foundation - local candidate

Reviewed 18 November 2026. Base: main 75b2ca7. This candidate does not change the deployed app, enable the scanner, schedule collection, call a paid feed, or alter the production database. Local tests use synthetic records and model fixtures only.

## What to collect first

| Priority | Dataset | Minimum evidence and checks | Source path and current restriction |
|---|---|---|---|
| 1 | Security master and daily prices | Symbol, exchange, ISIN where available, currency, session calendar, daily OHLCV, adjustment basis, corporate actions, delistings and symbol changes | Approved exchange/vendor agreement or user-supplied file with known rights. Do not silently turn Yahoo/yfinance into a public commercial feed. |
| 2 | Company financials and filings | Revenue, profit, operating cash flow, debt/cash, share count; reporting period, publication date, consolidated/standalone, units, audited status, restatements and original filing link | Issuer investor-relations filings or an approved vendor. Each issuer's collection and reuse terms need checking. Automated BSE collection is held. |
| 3 | Corporate events and regulatory updates | Results, dividends, splits, buybacks, governance disclosures and regulatory notices; source and publication time | SEBI officially supplies RSS for regulatory headlines. This is not a full company-news feed. Exchange corporate data rights remain relevant. |
| 4 | Benchmark and economic context | A like-for-like benchmark, rates, inflation, FX reference series, publication/revision dates and units | RBI DBIE is a primary macro reference candidate. Automated reuse has not been cleared here. Index data also needs appropriate rights. |
| 5 | Independent model evidence | Observed vs predicted, frozen forecast time, data cutoff, baseline comparison, sample size, error by symbol/window and unavailable outputs | Derived from data the app may use. Keep historical simulation distinct from forward results. Do not imply a prediction or news sentiment is a verified fact. |

Not first: full-web news copying, social-media sentiment, anonymous tips, real-time derivatives/options coverage or a buy/sell recommendation engine. They add data, rights and quality risks before the basic product is reliable.

## Trust contract

Every dataset should expose its source, source URL, publication/session time, collection time, currency/units, adjustment basis, coverage and use restriction. Missing or stale values stay missing/stale, not zero. Never silently swap providers or combine adjusted and raw prices. Calendar-aware freshness requires an explicit last completed trading session, not a weekday approximation. A valid record is not automatically licensed for public display.

Further integration work: session/holiday calendar, corporate-action reconciliation, duplicate/conflicting provider checks, field lineage, data revision history, calendar-aware signal suppression wired into existing application flows. These are requirements, not claims that this candidate already implements them.

## Implemented locally

- `app/market_data/trust.py`: source-policy registry; official SEBI RSS headline/link parser; UTC publication and collection timestamps; payload hash; URL allowlist; duplicate removal; rejection of missing/future timestamps, unsafe XML declarations and oversized feeds.
- Daily-bar quality validator: finite numeric fields, OHLC bounds, volume sanity, instrument identity and adjustment basis, explicit caller-provided completed session, stale/current signal eligibility and separate public-display status.
- `scripts/collect_data_evidence.py`: explicit manual or offline run, pinned official feed only, no redirects, one-hour per-output-file attempt cooldown, bounded response size/timeout, atomic successful output and preservation of previous output on errors. No retries after HTTP failure. It is a local tool, not a distributed scheduled service. Using another output path would not share the cooldown; central rate limiting is required before production use.
- `app/market_data/service.py`: existing ingestion now rejects nonfinite/bool/nonnumeric OHLCV, malformed or noncanonical dates, fractional volume, and conflicting same-date duplicates. Identical duplicates still deduplicate.
- Authenticated `GET /api/v1/data-health`: read-only aggregates of actual stored provider/count/symbol/latest-session/ingestion evidence. Never fetches a provider. It does not certify calendar freshness, price accuracy or public-display rights.
- Dashboard Data health tab: source cards, missing-data state, source limitations, loading, error and explicit retry. Mobile 320/390 and desktop 1280 widths, keyboard operation and no-horizontal-overflow checks passed.
- Full pinned backend suite: **354 passed, zero skipped** against a disposable local PostgreSQL server. The prior run without PostgreSQL was331passed/23skipped. Migration adoption/lifecycle and wallet/alert concurrency tests now pass too; no production database was accessed. Ruff across app/tests/scripts passed. Build, API timeout checks and all 10 existing mocked startup browser regressions passed.
- Real local integration: browser authenticates against a local FastAPI server and displays data-health aggregates from a disposable SQLite database. Synthetic source/date/count visible in the inspected mobile screenshot. Other dashboard routes are mocked to avoid any provider fetch. This is stronger than UI-only fixtures, but is not deployed end-to-end verification.

## Commands

```sh
python -m scripts.collect_data_evidence --input saved-feed.xml --output /tmp/sebi-evidence.json
python -m scripts.collect_data_evidence --fetch-sebi --output /tmp/sebi-evidence.json
python -m pytest -q
ruff check app tests scripts
cd frontend
npm run test:startup
node tests/data-health.mjs
# Requires local port8000 free and a Python environment with requirements installed:
PYTHON=/path/to/venv/bin/python node tests/data-health-integration.mjs
```

A single direct public read of the official feed at about 21:33 IST returned HTTP 200 with a channel and zero item entries. The parser reported `empty_or_all_rejected`, zero records and a coverage warning. That is proof the collector handles an empty response, not proof of successful real headline ingestion or of no regulatory events. Item parsing and rejection behavior are covered by synthetic fixtures. No market-price scraping was performed.

## Source decisions

1. SEBI RSS documentation: https://www.sebi.gov.in/rss.html . Official feed for automatic RSS delivery of regulatory headlines/links/summaries. Current pinned feed: https://www.sebi.gov.in/sebirss.xml . This candidate stores headline/link metadata only; public display remains review-required.
2. NSE policy: https://www.nse.in/static/market-data/nse-data-policy . Covers real-time, delayed, end-of-day, historical and corporate data; agreements define use, redistribution and restrictions. A non-commercial waiver is a possibility to investigate, not an entitlement.
3. BSE website policy: https://beta.bseindia.com/static/about/website_policy.html . Automated collection needs express written consent; linking to source material is distinct from copying it. No BSE collector is included.
4. Twelve Data usage: https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage . Business display remains exchange-dependent, and redistribution requires a separate agreement. Listing an exchange in metadata is not proof of price-data access.
5. yfinance documentation: https://ranaroussi.github.io/yfinance/ . Points users to Yahoo's data terms and identifies personal-use limitations. The library's availability does not establish public/commercial data rights.
6. RBI DBIE: https://data.rbi.org.in/DBIE/ . Official source candidate for macroeconomic series and publication context; no automated adapter or reuse clearance in this candidate.

These are observed source policies and engineering gates, not a legal opinion. No spend, provider application, external permission email, repository publication or deployment is included.

## Cold-start diagnosis and local fix

Owner Render dashboard on18November showed deployed main75b2ca7 on a Free instance with inactivity spin-down. Instance rsh6q completed startup at21:44:47IST. The existing synchronous demo bootstrap spent44.16seconds training live-symbol models and11.27seconds in sample-model work, before accounting for earlier phases. Existing code already skips model artifacts that exist. No HTTP health-check path was configured in Render. These observations identify a startup-delay contributor, not an established permanent outage or a measured fix.

Local change: minimal database and demo-account setup stays before service availability; existing optional demo ingestion/model work runs off the event-loop/startup path. Auth and stored-data evidence remain accessible during model warmup. Market/application routes return explicit503 while bootstrap is pending or failed, rather than serving partial models or implying predictions are ready. Readiness returns503 while starting/failed and for unavailable database/Redis checks. Liveness remains independent. Sample-model failure now propagates rather than silently allowing a ready state. No new provider or collection job is introduced; existing nonproduction/demo-mode conditions remain. Startup preparation failure is logged and leaves the service unavailable. Shutdown waits for active bootstrap rather than abandoning its DB/model writes.

Cold-start regression tests cover pending startup with liveness/login, blocked market access and CORS, successful release to ordinary auth checks, failed bootstrap, unavailable dependency readiness, sample-model failure propagation, initial database failure and the production no-demo-bootstrap boundary. The pending test holds synthetic training on a barrier until after successful login; it is not a claimed production timing benchmark. Free-host cold-start delay, CPU contention and model/provider time are not eliminated. A real-host/live-provider verification and reviewed deployment are still needed.

Bounded local one-core run: a new subprocess with one allowed CPU core, empty disposable SQLite/model paths and actual checked-in CSV bootstrap served liveness at1.57s and authenticated the demo login at1.64s while bootstrap was pending. Readiness and market routes correctly returned503 during warmup. Bootstrap finished at2.33s; the market route then reached ordinary401authentication. Redis was deliberately unavailable and final readiness correctly stayed503degraded with databaseok/bootstrapready. This is one local sample run, not a before/after production benchmark, not16live-symbol training, and not a Render timing claim. No external providers or forecast writes. Result in evidence/ss-cold-one-core-result.json.

Diagnostic sources:
- https://dashboard.render.com/web/srv-db9lkovbtjjs73c6fgmg/logs?t=app&r=1h
- https://dashboard.render.com/web/srv-db9lkovbtjjs73c6fgmg/settings
- https://dashboard.render.com/web/srv-db9lkovbtjjs73c6fgmg/deploys/dep-dbrvqcp5efls73e6eik0

## Remaining release gates

No push, PR, deployment, restart, paid upgrade, source activation or production database mutation is included. Existing freeze/publication restrictions remain. Actual nonempty approved ingestion remains unproven: the SEBI feed read returned zero items. Source/display permissions, session calendar, corporate actions, revisions and cross-provider reconciliation remain open. The standalone daily-bar trust validator is not yet a universal gate for every prediction route. The status endpoint exposes these gaps; it does not repair them. Provider-enabled/real-host behavior and controlled deployed auth/read-data verification remain. These must follow an approved release; disposable PostgreSQL and one-core synthetic bootstrap/load checks are now complete locally. Configure a Render HTTP readiness path only after its dependency semantics and release plan are reviewed; nothing was saved in the dashboard.

## Final isolated PostgreSQL and16symbol validation

A standard test-only pgserver0.1.4 helper supplied an isolated local server where system server binaries were absent. It is not added to application requirements. No account credentials, production database, user data or paid infrastructure were used. The full suite passed354tests, zero skipped, in38.69seconds, including all previously gated migration and concurrency tests. Local server data was temporary and cleaned up when the harness ended.

An additional actual-bootstrap subprocess used sixteen configured symbols,500synthetic stored bars per symbol (8000total), empty model paths and one allowed CPU core. PostgreSQL held synthetic records, and fresh ingestion timestamps skipped network refresh. A provider factory guard would fail if any provider were requested. It trained all16per-symbol artifacts. Liveness responded at1.44seconds; real demo login returned200at1.52seconds during pending bootstrap. Twenty concurrent liveness/data-health reads through four workers all returned200, maximum88milliseconds. Market/prediction routes correctly returned503while pending. All16models completed by4.48seconds; authenticated prediction-history read then returned200and empty history. The data-health aggregate API returned8000rows/16symbols from PostgreSQL. No forecast write was made. Redis was deliberately absent, so final readiness remained503degraded with databaseok and bootstrapready.

This is one local CPU-constrained synthetic workload. It does not reproduce Render memory limits, CPU throttling, provider/network latency or data shape, and cannot support a promised production startup time. It does validate useful request service during actual16symbol training and PostgreSQL access. Result and harness are included under evidence/.

Recommended next operational step is a reviewed scoped release of the ordinary data-quality/read-evidence/startup fix, not a claim that the whole trustworthy-data product is finished. Release restarts services and existing startup can regenerate ephemeral models or refresh current-provider data. Market routes explicitly503during bootstrap; rollback of code cannot restore ephemeral artifacts or undo a refresh. New feed collection schedules, scanner activation, paid sources and broader display rights remain separate and off.
