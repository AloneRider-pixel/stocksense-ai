import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { FALLBACK_SYMBOLS, IS_DEMO } from "../config";
import Brand from "./Brand";
import PriceChart from "./PriceChart";
import EquityChart from "./EquityChart";
import PredActualChart from "./PredActualChart";
import Scanner from "./Scanner";

function fmtPct(v) {
  if (v == null) return "—";
  return (v >= 0 ? "+" : "") + Number(v).toFixed(2) + "%";
}

function fmtPrice(currency, v) {
  if (v == null) return "—";
  const sym = currency === "INR" ? "₹" : "$";
  const locale = currency === "INR" ? "en-IN" : "en-US";
  return sym + Number(v).toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const INDICATOR_TOGGLES = [
  ["sma20", "SMA 20"],
  ["sma50", "SMA 50"],
  ["ema", "EMA 12·26"],
  ["bollinger", "Bollinger"],
  ["rsi", "RSI"],
  ["macd", "MACD"],
];

export default function Dashboard({ user, onSignOut }) {
  const [tab, setTab] = useState("overview");
  const [symbols, setSymbols] = useState(FALLBACK_SYMBOLS);
  const [symbol, setSymbol] = useState(FALLBACK_SYMBOLS[0]);
  const [bars, setBars] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [history, setHistory] = useState([]);
  const [evaluation, setEvaluation] = useState(null);
  const [offlineMetrics, setOfflineMetrics] = useState(null);
  const [symbolMeta, setSymbolMeta] = useState({});
  const [exchange, setExchange] = useState("ALL");
  const [indicators, setIndicators] = useState(null);
  const [overlays, setOverlays] = useState({ sma20: true, sma50: false, ema: false, bollinger: false, rsi: false, macd: false });
  const [watchlist, setWatchlist] = useState([]);
  const [screenerRows, setScreenerRows] = useState(null);
  const [screenerMeta, setScreenerMeta] = useState(null);
  const [filters, setFilters] = useState({ exchange: "", min_change_pct: "", max_change_pct: "", min_rsi: "", max_rsi: "", above_sma20: "", min_volume: "" });
  const [screenerBusy, setScreenerBusy] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [dataSource, setDataSource] = useState("");
  const [symbolQuery, setSymbolQuery] = useState("");
  const [publicAccuracy, setPublicAccuracy] = useState(null);
  const [backtest, setBacktest] = useState(null);
  const [backtestSymbol, setBacktestSymbol] = useState(null);
  const [backtestBusy, setBacktestBusy] = useState(false);
  const [backtestError, setBacktestError] = useState("");

  useEffect(() => {
    api("/public/market-overview")
      .then((ov) => {
        if (ov?.symbols?.length) {
          const list = ov.symbols.map((s) => s.symbol);
          setSymbols(list);
          setSymbol((cur) => (list.includes(cur) ? cur : list[0]));
          setDataSource(ov.data_source || "");
          setSymbolMeta((prev) => {
            const next = { ...prev };
            ov.symbols.forEach((s) => { next[s.symbol] = { ...next[s.symbol], ...s }; });
            return next;
          });
        }
      })
      .catch(() => {});
    api("/symbols")
      .then((list) => {
        if (Array.isArray(list)) {
          setSymbolMeta((prev) => {
            const next = { ...prev };
            list.forEach((s) => { next[s.symbol] = { ...next[s.symbol], ...s }; });
            return next;
          });
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    setBars([]);
    setIndicators(null);
    setPrediction(null);
    api("/stocks/" + symbol + "/history?limit=150")
      .then(setBars)
      .catch(() => setBars([]));
    api("/stocks/" + symbol + "/indicators?limit=150")
      .then(setIndicators)
      .catch(() => setIndicators(null));
  }, [symbol]);

  useEffect(() => {
    api("/watchlist").then((w) => setWatchlist(w.symbols || [])).catch(() => {});
    api("/predictions?limit=20").then(setHistory).catch(() => setHistory([]));
    api("/predictions/evaluation").then(setEvaluation).catch(() => setEvaluation(null));
    api("/metrics").then((m) => {
      if (m && m.status !== "not_available") setOfflineMetrics(m);
    }).catch(() => {});
    api("/public/accuracy").then(setPublicAccuracy).catch(() => setPublicAccuracy(null));
  }, []);

  const market = bars.length ? bars[bars.length - 1] : null;
  const prev = bars.length > 1 ? bars[bars.length - 2] : null;
  const dayChange = market && prev && prev.close
    ? ((market.close - prev.close) / prev.close) * 100
    : null;

  async function runPrediction() {
    setBusy(true);
    setError("");
    try {
      const hist = await api("/stocks/" + symbol + "/history?limit=100");
      if (hist.length < 11) {
        throw new Error("Not enough market history is available for this symbol yet.");
      }
      const result = await api("/predict", {
        method: "POST",
        body: JSON.stringify({
          symbol,
          history: hist.map((bar) => ({ date: bar.date, close: bar.close, volume: bar.volume })),
        }),
      });
      setPrediction(result);
      setHistory(await api("/predictions?limit=20"));
      setEvaluation(await api("/predictions/evaluation"));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleWatch(sym) {
    try {
      if (watchlist.includes(sym)) {
        const r = await api("/watchlist/" + sym, { method: "DELETE" });
        setWatchlist(r.symbols || []);
      } else {
        const r = await api("/watchlist", { method: "POST", body: JSON.stringify({ symbol: sym }) });
        setWatchlist(r.symbols || []);
      }
    } catch (e) { setError(e.message); }
  }

  async function runScreener() {
    setScreenerBusy(true);
    try {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => { if (v !== "" && v != null) params.set(k, v); });
      const r = await api("/screener" + (params.toString() ? "?" + params.toString() : ""));
      setScreenerRows(r.results || []);
      setScreenerMeta({ scanned: r.scanned, universe: r.universe });
    } catch (e) {
      setError(e.message);
      setScreenerRows([]);
    } finally {
      setScreenerBusy(false);
    }
  }

  function openSymbol(sym) {
    setSymbol(sym);
    setTab("overview");
  }

  async function runBacktest(sym) {
    setBacktestBusy(true);
    setBacktestError("");
    setBacktest(null);
    setBacktestSymbol(sym);
    try {
      const result = await api("/backtest/" + sym);
      setBacktest(result);
    } catch (e) {
      setBacktestError(e.message);
    } finally {
      setBacktestBusy(false);
    }
  }

  const firstName = user.full_name || user.email.split("@")[0];
  const currency = symbolMeta[symbol]?.currency || "USD";
  const exchangeOf = (s) => symbolMeta[s]?.exchange || "US";
  const exchangeSymbols = exchange === "ALL" ? symbols : symbols.filter((s) => exchangeOf(s) === exchange);
  const q = symbolQuery.trim().toLowerCase();
  const visibleSymbols = q
    ? exchangeSymbols.filter((s) => s.toLowerCase().includes(q) || (symbolMeta[s]?.name || "").toLowerCase().includes(q))
    : exchangeSymbols;
  const hasNse = symbols.some((s) => exchangeOf(s) === "NSE");

  return (
    <div className="app-shell">
      <aside>
        <Brand />
        <nav>
          <a className={tab === "overview" ? "active" : ""} onClick={() => setTab("overview")}>Overview</a>
          <a className={tab === "watchlist" ? "active" : ""} onClick={() => setTab("watchlist")}>Watchlist</a>
          <a className={tab === "scanner" ? "active" : ""} onClick={() => setTab("scanner")}>Scanner</a>
          <a className={tab === "screener" ? "active" : ""} onClick={() => setTab("screener")}>Screener</a>
          <a className={tab === "activity" ? "active" : ""} onClick={() => setTab("activity")}>Prediction activity</a>
          <a className={tab === "evaluation" ? "active" : ""} onClick={() => setTab("evaluation")}>Model evaluation</a>
          <a className={tab === "backtest" ? "active" : ""} onClick={() => setTab("backtest")}>Backtest</a>
        </nav>
        {dataSource && <p className="aside-note">Market data: {dataSource}. May be delayed.</p>}
        <button className="ghost" onClick={onSignOut}>Sign out</button>
      </aside>

      <main className="dashboard">
        <header>
          <div>
            <p className="eyebrow">OVERVIEW</p>
            <h1>Good evening, {firstName}</h1>
            <p className="muted">Real market data, model signals, and a scored prediction record.</p>
          </div>
          <div className="user-chip">{user.email}</div>
        </header>

        {tab === "overview" && (
          <>
            <section className="metric-grid">
              <article><span>Latest close · {symbol}</span><strong>{market ? fmtPrice(currency, market.close) : "—"}</strong><small>{market ? market.date : "Loading market data"}</small></article>
              <article><span>Last session change</span><strong className={(dayChange ?? 0) >= 0 ? "positive" : "negative"}>{fmtPct(dayChange)}</strong><small>{prev ? "vs " + prev.date : ""}</small></article>
              <article><span>Model</span><strong>{prediction?.model || "Random Forest"}</strong><small>Next-period regression</small></article>
              <article><span>Your predictions</span><strong>{history.length}</strong><small>Stored and scored</small></article>
              <article><span>Directional accuracy</span><strong>{evaluation?.directional_accuracy_pct != null ? evaluation.directional_accuracy_pct.toFixed(1) + "%" : "—"}</strong><small>Measured, not claimed</small></article>
              <article><span>Online MAE</span><strong>{evaluation?.mae != null ? Number(evaluation.mae).toFixed(3) : "—"}</strong><small>Realized prediction error</small></article>
            </section>

            <section className="panel chart-panel">
              <div className="panel-head">
                <div>
                  <p className="eyebrow">PRICE HISTORY</p>
                  <h2>{symbolMeta[symbol]?.name || symbol} · {symbol} · daily candles{exchangeOf(symbol) === "NSE" ? " · NSE · IST" : ""}
                    <button className={"star" + (watchlist.includes(symbol) ? " active" : "")} title={watchlist.includes(symbol) ? "Remove from watchlist" : "Add to watchlist"} onClick={() => toggleWatch(symbol)}>
                      {watchlist.includes(symbol) ? "★" : "☆"}
                    </button>
                  </h2>
                </div>
                <div className="symbol-pills">
                  <input
                    className="symbol-search"
                    placeholder="Search symbol"
                    value={symbolQuery}
                    onChange={(e) => setSymbolQuery(e.target.value)}
                  />
                  {hasNse && (
                    <>
                      <button className={"pill" + (exchange === "ALL" ? " active" : "")} onClick={() => setExchange("ALL")}>All</button>
                      <button className={"pill" + (exchange === "US" ? " active" : "")} onClick={() => setExchange("US")}>US</button>
                      <button className={"pill" + (exchange === "NSE" ? " active" : "")} onClick={() => setExchange("NSE")}>India · NSE</button>
                      <span className="pill-sep" />
                    </>
                  )}
                  {visibleSymbols.map((s) => (
                    <button key={s} className={"pill" + (s === symbol ? " active" : "")} onClick={() => setSymbol(s)}>{s}</button>
                  ))}
                </div>
              </div>
              <div className="indicator-toggles">
                {INDICATOR_TOGGLES.map(([key, label]) => (
                  <button
                    key={key}
                    className={"chip" + (overlays[key] ? " active" : "")}
                    onClick={() => setOverlays((o) => ({ ...o, [key]: !o[key] }))}
                  >{label}</button>
                ))}
              </div>
              <PriceChart bars={bars} indicators={indicators} overlays={overlays} currency={currency} />
              <p className="chart-note">Source: {bars[0]?.source_provider === "csv-sample" ? "checked-in sample data" : (exchangeOf(symbol) === "NSE" ? "Yahoo Finance (NSE)" : "Twelve Data")} · daily bars · may be delayed · not investment advice</p>
            </section>

            <section className="workspace">
              <article className="panel">
                <div className="panel-head">
                  <div><p className="eyebrow">PREDICTION ENGINE</p><h2>Next-period close · {symbol}</h2></div>
                </div>
                <div className="prediction-box">
                  <div>
                    <span>Predicted close</span>
                    <strong>{prediction ? fmtPrice(currency, prediction.predicted_close) : "—"}</strong>
                  </div>
                  <div>
                    <span>Expected change</span>
                    <strong className={(prediction?.expected_change_pct ?? 0) >= 0 ? "positive" : "negative"}>
                      {prediction ? fmtPct(prediction.expected_change_pct) : "—"}
                    </strong>
                  </div>
                </div>
                <button className="btn-primary" onClick={runPrediction} disabled={busy}>
                  {busy ? "Running model..." : "Run prediction"}
                </button>
                {error && <div className="error">{error}</div>}
                <p className="muted small-print">Predictions are illustrative and are not investment advice.</p>
              </article>

              <article className="panel">
                <p className="eyebrow">HOW THIS IS SCORED</p>
                <h2>Every prediction gets graded.</h2>
                <p className="muted">
                  When the real close for a predicted date lands, the platform stores it next to
                  your prediction and updates measured accuracy and error. Nothing is deleted or
                  restated. The record you see under Prediction activity is the whole record.
                </p>
                <p className="muted">
                  Offline model quality is evaluated with walk-forward windows: each period is
                  scored only on information available before it. See Model evaluation for the
                  numbers.
                </p>
              </article>
            </section>
          </>
        )}

        {tab === "watchlist" && (
          <section className="panel">
            <p className="eyebrow">WATCHLIST</p>
            <h2>Symbols you follow</h2>
            <div className="table table-head watchlist-head">
              <span>Symbol</span><span>Market</span><span>Last close</span><span></span>
            </div>
            <div className="table">
              {watchlist.length === 0 && <div className="empty">Nothing saved yet. Use the ☆ next to a symbol on the Overview chart.</div>}
              {watchlist.map((sym) => (
                <div className="row" key={sym}>
                  <span><button className="linklike" onClick={() => openSymbol(sym)}>{symbolMeta[sym]?.name || sym} · {sym}</button></span>
                  <span>{symbolMeta[sym]?.exchange === "NSE" ? "NSE · IST" : "US"}</span>
                  <span>{symbolMeta[sym]?.close != null ? fmtPrice(symbolMeta[sym]?.currency, symbolMeta[sym].close) : "—"}</span>
                  <span><button className="chip" onClick={() => toggleWatch(sym)}>Remove</button></span>
                </div>
              ))}
            </div>
          </section>
        )}

        {tab === "scanner" && <Scanner />}

        {tab === "screener" && (
          <section className="panel">
            <p className="eyebrow">SCREENER</p>
            <h2>Scan the universe</h2>
            <p className="muted small-print">Metrics computed from stored daily bars (may be delayed). {screenerMeta ? screenerMeta.scanned + " of " + screenerMeta.universe + " symbols scanned." : ""}</p>
            <div className="screener-filters">
              <label>Market
                <select value={filters.exchange} onChange={(e) => setFilters({ ...filters, exchange: e.target.value })}>
                  <option value="">All</option>
                  <option value="US">US</option>
                  <option value="NSE">India · NSE</option>
                </select>
              </label>
              <label>Change % min<input type="number" step="0.1" value={filters.min_change_pct} onChange={(e) => setFilters({ ...filters, min_change_pct: e.target.value })} /></label>
              <label>Change % max<input type="number" step="0.1" value={filters.max_change_pct} onChange={(e) => setFilters({ ...filters, max_change_pct: e.target.value })} /></label>
              <label>RSI min<input type="number" min="0" max="100" value={filters.min_rsi} onChange={(e) => setFilters({ ...filters, min_rsi: e.target.value })} /></label>
              <label>RSI max<input type="number" min="0" max="100" value={filters.max_rsi} onChange={(e) => setFilters({ ...filters, max_rsi: e.target.value })} /></label>
              <label>Price vs SMA20
                <select value={filters.above_sma20} onChange={(e) => setFilters({ ...filters, above_sma20: e.target.value })}>
                  <option value="">Any</option>
                  <option value="true">Above</option>
                  <option value="false">Below</option>
                </select>
              </label>
              <button className="btn-primary" onClick={runScreener} disabled={screenerBusy}>{screenerBusy ? "Scanning..." : "Run screen"}</button>
            </div>
            <div className="table table-head screener-head screener-grid">
              <span>Symbol</span><span>Close</span><span>Change</span><span>RSI 14</span><span>SMA 20</span><span>Rel vol</span>
            </div>
            <div className="table screener-grid">
              {screenerRows === null && <div className="empty">Set filters and run the screen.</div>}
              {screenerRows !== null && screenerRows.length === 0 && <div className="empty">No symbols match.</div>}
              {(screenerRows || []).map((r) => (
                <div className="row" key={r.symbol}>
                  <span><button className="linklike" onClick={() => openSymbol(r.symbol)}>{r.name} · {r.symbol}</button></span>
                  <span>{fmtPrice(r.currency, r.close)}</span>
                  <span className={(r.change_pct ?? 0) >= 0 ? "positive" : "negative"}>{fmtPct(r.change_pct)}</span>
                  <span>{r.rsi14 ?? "—"}</span>
                  <span>{r.above_sma20 == null ? "—" : r.above_sma20 ? "Above" : "Below"}</span>
                  <span>{r.rel_volume ?? "—"}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {tab === "activity" && (
          <section className="panel">
            <p className="eyebrow">PREDICTION ACTIVITY</p>
            <h2>Your prediction record</h2>
            <div className="table table-head">
              <span>Symbol · date</span><span>Predicted</span><span>Actual</span><span>Outcome</span>
            </div>
            <div className="table">
              {history.length === 0 && <div className="empty">No predictions yet. Run one from the Overview tab.</div>}
              {history.map((item) => (
                <div className="row" key={item.id}>
                  <span>{item.symbol} · {item.prediction_date}</span>
                  <span>{fmtPrice(symbolMeta[item.symbol]?.currency, item.predicted_close)}</span>
                  <span>{item.actual_close ? fmtPrice(symbolMeta[item.symbol]?.currency, item.actual_close) : "Pending"}</span>
                  <span className={item.actual_close ? (item.percentage_error <= 2 ? "positive" : "negative") : ""}>
                    {item.actual_close ? "Error " + item.percentage_error.toFixed(2) + "%" : "Awaiting actual close"}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {tab === "evaluation" && (
          <>
            <section className="metric-grid">
              <article><span>Evaluated predictions</span><strong>{evaluation?.evaluated_predictions ?? 0}</strong><small>With realized actuals</small></article>
              <article><span>Directional accuracy</span><strong>{evaluation?.directional_accuracy_pct != null ? evaluation.directional_accuracy_pct.toFixed(1) + "%" : "—"}</strong><small>Online, your record</small></article>
              <article><span>Online MAE</span><strong>{evaluation?.mae != null ? Number(evaluation.mae).toFixed(3) : "—"}</strong><small>Realized error</small></article>
              <article><span>Baseline MAE</span><strong>{evaluation?.baseline_mae != null ? Number(evaluation.baseline_mae).toFixed(3) : "—"}</strong><small>Last-close persistence</small></article>
              <article><span>Baseline hit rate</span><strong>{evaluation?.baseline_directional_accuracy_pct != null ? evaluation.baseline_directional_accuracy_pct.toFixed(1) + "%" : "—"}</strong><small>Always-up baseline</small></article>
              <article><span>Vs persistence baseline</span><strong className={evaluation?.improvement_vs_persistence_pct != null ? (Number(evaluation.improvement_vs_persistence_pct) >= 0 ? "positive" : "negative") : ""}>{evaluation?.improvement_vs_persistence_pct != null ? fmtPct(evaluation.improvement_vs_persistence_pct) : "—"}</strong><small>Positive means the model wins</small></article>
              {offlineMetrics && offlineMetrics.mae != null && (
                <article><span>Offline MAE</span><strong>{Number(offlineMetrics.mae).toFixed(3)}</strong><small>Walk-forward, sample dataset</small></article>
              )}
              {offlineMetrics && offlineMetrics.directional_accuracy_pct != null && (
                <article><span>Offline directional accuracy</span><strong>{Number(offlineMetrics.directional_accuracy_pct).toFixed(1)}%</strong><small>Walk-forward, sample dataset</small></article>
              )}
              {offlineMetrics && offlineMetrics.improvement_vs_last_close_pct != null && (
                <article><span>Vs last-close baseline</span><strong className={Number(offlineMetrics.improvement_vs_last_close_pct) >= 0 ? "positive" : "negative"}>{fmtPct(offlineMetrics.improvement_vs_last_close_pct)}</strong><small>Walk-forward, sample dataset</small></article>
              )}
            </section>
            <section className="panel">
              <p className="eyebrow">PREDICTED VS ACTUAL</p>
              <h2>Every scored prediction vs the naive baseline.</h2>
              <PredActualChart items={history} currency={currency} />
              <p className="muted small-print">Only predictions with a realized close are drawn; pending ones are excluded, not hidden. The dashed line is last-close persistence - the model must beat it to add value. This chart reads the stored record on every load, so it updates as new closes land.</p>
            </section>
            {publicAccuracy && publicAccuracy.symbols?.length > 0 && (
              <section className="panel">
                <p className="eyebrow">ACCURACY BY SYMBOL</p>
                <h2>Live record vs the naive baseline.</h2>
                <div className="table table-head accuracy-grid">
                  <span>Symbol</span><span>Scored</span><span>Model MAPE</span><span>Baseline MAPE</span><span>Hit rate</span>
                </div>
                <div className="table accuracy-grid">
                  {publicAccuracy.symbols.map((row) => (
                    <div className="row" key={row.symbol}>
                      <span>{row.symbol}</span>
                      <span>{row.evaluated_predictions}</span>
                      <span>{row.mape_pct == null ? "—" : Number(row.mape_pct).toFixed(2) + "%"}</span>
                      <span>{row.baseline_mape_pct == null ? "—" : Number(row.baseline_mape_pct).toFixed(2) + "%"}</span>
                      <span>{row.directional_accuracy_pct == null ? "—" : Number(row.directional_accuracy_pct).toFixed(1) + "%"}</span>
                    </div>
                  ))}
                </div>
                <p className="muted small-print">Baseline is last-close persistence over the same scored predictions. Live record, not a backtest.</p>
              </section>
            )}
            <section className="panel">
              <p className="eyebrow">EVALUATION CONTRACT</p>
              <h2>Chronological, or it does not count.</h2>
              <p className="muted">
                Offline evaluation uses expanding walk-forward windows: every scored period is
                restricted to information available before that period. Sample-fixture results are
                reproducibility evidence, not universal performance claims. Backtests can fail to
                generalize, and nothing here is investment advice.
              </p>
            </section>
          </>
        )}

        {tab === "backtest" && (
          <section className="panel">
            <p className="eyebrow">BACKTEST</p>
            <h2>Model strategy vs buy-and-hold.</h2>
            <p className="muted">
              Walk-forward out-of-sample predictions decide a long-or-flat position for the
              next bar. No transaction costs, no shorting, no leverage. Pick a symbol to run
              it on stored daily bars.
            </p>
            <div className="symbol-pills">
              {symbols.map((s) => (
                <button key={s} className={"pill" + (s === backtestSymbol ? " active" : "")} onClick={() => runBacktest(s)} disabled={backtestBusy}>
                  {s}
                </button>
              ))}
            </div>
            {backtestBusy && <p className="muted">Running walk-forward backtest…</p>}
            {backtestError && <div className="error">{backtestError}</div>}
            {backtest && (
              <>
                <section className="metric-grid">
                  <article><span>Periods</span><strong>{backtest.metrics.periods}</strong><small>Out-of-sample steps</small></article>
                  <article><span>Strategy return</span><strong className={backtest.metrics.strategy_return_pct >= 0 ? "positive" : "negative"}>{fmtPct(backtest.metrics.strategy_return_pct)}</strong><small>Long/flat, no costs</small></article>
                  <article><span>Buy-and-hold return</span><strong className={backtest.metrics.buy_hold_return_pct >= 0 ? "positive" : "negative"}>{fmtPct(backtest.metrics.buy_hold_return_pct)}</strong><small>Same period</small></article>
                  <article><span>Strategy max drawdown</span><strong className="negative">{Number(backtest.metrics.strategy_max_drawdown_pct).toFixed(1)}%</strong><small>Peak to trough</small></article>
                  <article><span>Buy-hold max drawdown</span><strong className="negative">{Number(backtest.metrics.buy_hold_max_drawdown_pct).toFixed(1)}%</strong><small>Peak to trough</small></article>
                  <article><span>Direction hit rate</span><strong>{Number(backtest.metrics.directional_hit_rate_pct).toFixed(1)}%</strong><small>Out-of-sample</small></article>
                </section>
                <EquityChart curve={backtest.equity_curve} />
                <p className="muted small-print">{backtest.assumptions} {backtest.disclaimer}</p>
              </>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
