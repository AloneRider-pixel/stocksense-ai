import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import TradingViewChart from "./TradingViewChart";

const pct = (v) => (v == null ? "—" : (v >= 0 ? "+" : "") + Number(v).toFixed(1) + "%");
const cls = (v) => ((v ?? 0) >= 0 ? "positive" : "negative");

const VIEWS = [
  ["rs", "Relative strength"],
  ["industries", "Industries"],
  ["breakouts", "Breakouts"],
  ["changes", "What changed"],
  ["scorecard", "Signal scorecard"],
  ["backtest", "Rule backtest"],
];

export default function Scanner() {
  const [view, setView] = useState("rs");
  const [rsLimit, setRsLimit] = useState(50);
  const [sigLimit, setSigLimit] = useState(25);
  const [coverage, setCoverage] = useState(null);
  const [breadth, setBreadth] = useState(null);
  const [rs, setRs] = useState(null);
  const [industries, setIndustries] = useState(null);
  const [breakouts, setBreakouts] = useState(null);
  const [bo, setBo] = useState({ lookback_days: 55, min_rel_volume: 1.5 });
  const [explain, setExplain] = useState(null);
  const [rule, setRule] = useState({ symbol: "RELIANCE", entry: "breakout", entry_n: 55, entry_fast: 20, entry_threshold_pct: 10, exit: "below_sma", exit_n: 20, exit_stop_pct: 10, cost_bps: 10, slippage_bps: 10 });
  const [bt, setBt] = useState(null);
  const [changes, setChanges] = useState(null);
  const [card, setCard] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const loadCoverage = useCallback(async () => {
    try { const cov = await api("/scanner/coverage"); setCoverage(cov); return cov; } catch (e) { setError(e.message); return null; }
  }, []);

  const loadAll = useCallback(async () => {
    setError("");
    try {
      const [r, i, b, br, ch, sc] = await Promise.all([
        api("/scanner/rs?limit=50"),
        api("/scanner/industries"),
        api("/scanner/breadth"),
        api("/scanner/breakouts?lookback_days=" + bo.lookback_days + "&min_rel_volume=" + bo.min_rel_volume),
        api("/scanner/changes"),
        api("/scanner/scorecard"),
      ]);
      setRs(r); setIndustries(i); setBreadth(b); setBreakouts(br); setChanges(ch); setCard(sc);
    } catch (e) { setError(e.message); }
  }, [bo.lookback_days, bo.min_rel_volume]);

  useEffect(() => {
    loadCoverage().then((cov) => { if (cov && (cov.loading || cov.symbols_with_data > 0)) loadAll(); });
  }, []); // eslint-disable-line

  async function startLoad() {
    setError("");
    try { await api("/scanner/refresh", { method: "POST" }); await loadCoverage(); } catch (e) { setError(e.message); }
  }
  async function openExplain(symbol) {
    setExplain({ symbol, loading: true });
    try { setExplain(await api("/scanner/stock/" + symbol)); } catch (e) { setExplain({ symbol, error: e.message }); }
  }
  async function runBacktest() {
    setBusy(true); setError(""); setBt(null);
    try {
      const body = { ...rule, symbol: rule.symbol.trim().toUpperCase() };
      for (const k of ["entry_n", "entry_fast", "entry_threshold_pct", "exit_n", "exit_stop_pct", "cost_bps", "slippage_bps"]) body[k] = Number(body[k]);
      setBt(await api("/scanner/backtest", { method: "POST", body: JSON.stringify(body) }));
    } catch (e) { setError(e.message); }
    setBusy(false);
  }
  const set = (k) => (e) => setRule({ ...rule, [k]: e.target.value });

  const dataPending = coverage && !coverage.loading && coverage.symbols_with_data === 0;

  return (
    <section className="panel scanner">
      <p className="eyebrow">NIFTY 500 SCANNER</p>
      <h2>Strength, rotation and breakouts</h2>
      <p className="muted small-print">
        Computed from delayed daily bars. Formulas are StockSense's own and shown on each view. Descriptive only, not advice or a prediction.
      </p>
      {coverage && !dataPending && (
        <p className="muted small-print" data-testid="coverage">
          Coverage: {coverage.symbols_with_data} of {coverage.universe_size} stocks loaded, {coverage.symbols_with_12m_history} with 12 months of history
          {coverage.as_of ? " · data through " + coverage.as_of : ""}
          {coverage.excluded_by_quality_check ? " · " + coverage.excluded_by_quality_check + " excluded by data checks (" + coverage.excluded_examples.slice(0, 3).map((e) => e.symbol).join(", ") + (coverage.excluded_by_quality_check > 3 ? ", …" : "") + ")" : ""}
          {coverage.loading ? " · loading in background…" : ""}{" "}
          {coverage.refresh_enabled && <button className="linklike" onClick={startLoad} disabled={coverage.loading}>Refresh data</button>}
        </p>
      )}
      {error && <div className="error">{error}</div>}

      {dataPending && (
        <div className="panel" style={{ marginTop: 12 }}>
          <h3>Scanner rankings aren't live yet</h3>
          <p className="muted">
            The scanner is built and tested, but StockSense doesn't yet have a permitted source for the
            NSE daily data it computes from. Instead of showing sample or stale numbers, rankings stay
            off until a licensed or permitted feed is connected.
          </p>
          <p className="muted">
            Once connected you'll get: relative-strength ratings (1-99) across the Nifty 500, industry
            rotation, breakout setups, a daily what-changed view, a forward-only signal scorecard, and
            rule backtests with costs included.
          </p>
          <h3 style={{ marginTop: 16 }}>Market chart</h3>
          <p className="muted small-print">
            BSE data, end-of-day, by TradingView. Display only; it doesn't power the scanner rankings.
          </p>
          <TradingViewChart symbol="BSE:SENSEX" />
        </div>
      )}

      {breadth && (
        <div className="stat-grid">
          <article className="stat-card"><span>Above 50-day avg</span><strong>{breadth.pct_above_50dma ?? "—"}%</strong></article>
          <article className="stat-card"><span>Above 200-day avg</span><strong>{breadth.pct_above_200dma ?? "—"}%</strong></article>
          <article className="stat-card"><span>Near 52-week high</span><strong>{breadth.near_52w_high}</strong><small>of {breadth.counted_52w}</small></article>
          <article className="stat-card"><span>Near 52-week low</span><strong>{breadth.near_52w_low}</strong><small>of {breadth.counted_52w}</small></article>
        </div>
      )}

      {explain && (
        <aside className="panel explain" role="dialog" aria-label="Why this stock">
          <div className="panel-head">
            <h3>{explain.name || explain.symbol} {explain.rs_rating ? "· RS " + explain.rs_rating : ""}</h3>
            <button className="linklike" onClick={() => setExplain(null)}>Close</button>
          </div>
          {explain.loading && <p className="muted">Loading…</p>}
          {explain.error && <div className="error">{explain.error}</div>}
          {explain.reasons && (
            <>
              <p className="eyebrow">WHY IT APPEARS</p>
              <ul>{explain.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              <p className="eyebrow">THE SETUP IS INVALIDATED IF</p>
              <ul>{explain.invalidations.map((i) => <li key={i.rule}>{i.rule}: <strong>{i.level}</strong></li>)}</ul>
              <p className="muted small-print">Last close {explain.last_close} on {explain.as_of}. {explain.note}</p>
            </>
          )}
        </aside>
      )}

      {!dataPending && (
        <div className="pill-row">
          {VIEWS.map(([k, label]) => (
            <button key={k} className={"pill" + (view === k ? " active" : "")} onClick={() => setView(k)}>{label}</button>
          ))}
        </div>
      )}

      {view === "rs" && rs && (
        <>
          <p className="muted small-print">{rs.method} Industry = NSE's industry classification. {rs.ranked} of {rs.universe} ranked.</p>
          <div className="table table-head scanner-grid"><span>Stock</span><span>RS</span><span>Excess vs NIFTY 50</span><span>Industry</span></div>
          <div className="table scanner-grid g-rs">
            {rs.results.slice(0, rsLimit).map((r) => (
              <div className="row" key={r.symbol}>
                <span><button className="linklike" onClick={() => openExplain(r.symbol)}>{r.name} · {r.symbol}</button></span>
                <span>{r.rs_rating}</span>
                <span className={cls(r.excess_return_pct)}>{pct(r.excess_return_pct)}</span>
                <span>{r.industry}</span>
              </div>
            ))}
          </div>
          {rs.results.length > rsLimit && <button className="btn-secondary" onClick={() => setRsLimit(rsLimit + 50)}>Show 50 more ({rsLimit} of {rs.results.length})</button>}
        </>
      )}

      {view === "industries" && industries && (
        <>
          <p className="muted small-print">{industries.method}</p>
          <div className="table table-head scanner-grid"><span>Industry</span><span>Median RS now</span><span>Before</span><span>Change</span></div>
          <div className="table scanner-grid g-ind">
            {industries.results.map((r) => (
              <div className="row" key={r.industry}>
                <span>{r.industry} ({r.members})</span><span>{r.median_rs_now}</span><span>{r.median_rs_before ?? "—"}</span>
                <span className={cls(r.change)}>{r.change == null ? "—" : (r.change >= 0 ? "+" : "") + r.change}</span>
              </div>
            ))}
          </div>
        </>
      )}

      {view === "breakouts" && breakouts && (
        <>
          <div className="screener-filters">
            <label>Lookback (days)<input type="number" min="10" max="250" value={bo.lookback_days} onChange={(e) => setBo({ ...bo, lookback_days: e.target.value })} /></label>
            <label>Min volume vs 20-day avg<input type="number" step="0.1" min="0" value={bo.min_rel_volume} onChange={(e) => setBo({ ...bo, min_rel_volume: e.target.value })} /></label>
            <button className="btn-primary" onClick={loadAll}>Scan</button>
          </div>
          <p className="muted small-print">{breakouts.method} {breakouts.results.length} match.</p>
          <div className="table table-head scanner-grid"><span>Stock</span><span>Close vs level</span><span>Volume x</span><span>Setup breaks if close below</span></div>
          <div className="table scanner-grid g-bo">
            {breakouts.results.length === 0 && <div className="empty">No breakouts match these settings today.</div>}
            {breakouts.results.map((r) => (
              <div className="row" key={r.symbol}>
                <span><button className="linklike" onClick={() => openExplain(r.symbol)}>{r.name} · {r.symbol}</button></span>
                <span>{r.close} vs {r.breakout_level}</span><span>{r.rel_volume}x</span><span>{r.invalidation_close_below}</span>
              </div>
            ))}
          </div>
        </>
      )}

      {view === "changes" && changes && (
        <>
          <p className="muted small-print">{changes.note}</p>
          <p className="eyebrow">NEW BREAKOUTS TODAY</p>
          <p className="muted small-print">{changes.new_breakouts.length ? changes.new_breakouts.join(", ") : "None today."}</p>
          <p className="eyebrow">BREAKOUT LEVELS LOST (LAST 10 SESSIONS)</p>
          <div className="table table-head scanner-grid"><span>Stock</span><span>Days ago</span><span>Level</span><span>Close</span></div>
          <div className="table scanner-grid g-lost">
            {changes.breakout_levels_lost.length === 0 && <div className="empty">None.</div>}
            {changes.breakout_levels_lost.map((r) => (
              <div className="row" key={r.symbol}><span>{r.name} · {r.symbol}</span><span>{r.breakout_sessions_ago}</span><span>{r.level}</span><span className="negative">{r.close}</span></div>
            ))}
          </div>
          <p className="eyebrow">LARGEST RS DROPS SINCE PREVIOUS SESSION</p>
          <div className="table table-head scanner-grid"><span>Stock</span><span>Now</span><span>Before</span><span>Change</span></div>
          <div className="table scanner-grid g-drop">
            {changes.rs_weakened.map((r) => (
              <div className="row" key={r.symbol}><span>{r.name} · {r.symbol}</span><span>{r.rs_now}</span><span>{r.rs_before}</span><span className="negative">{r.change}</span></div>
            ))}
          </div>
        </>
      )}

      {view === "scorecard" && card && (
        <>
          <p className="muted small-print">{card.method}</p>
          {card.forward_signals === 0 ? (
            <div className="empty">No forward signals yet. The forward record starts with the first live refresh made promptly after a session closes, and fills as trading days pass. Nothing is back-filled.</div>
          ) : (
            <div className="table scanner-grid g-sum">
              <div className="row"><span><strong>Forward signals (headline)</strong></span><span /><span /><span /></div>
              {Object.entries(card.summary_forward_only).flatMap(([kind, hs]) => Object.entries(hs).map(([h, v]) => (
                <div className="row" key={kind + h}><span>{kind === "breakout" ? "Breakout" : "RS 90+"}</span><span>{h.slice(1)} days</span>
                  <span>{v.scored ? v.beat_nifty + " of " + v.scored + " beat NIFTY 50" : "not yet scorable"}</span><span>{v.scored ? "median " + pct(v.median_vs_nifty_pct) : "—"}</span></div>
              )))}
            </div>
          )}
          {card.retrospective_signals > 0 && (
            <p className="muted small-print"><strong>Retrospective:</strong> {card.retrospective_signals} signals came from runs that were imported, recomputed, delayed or on a stale bar date, so they were found after the data was known. They are shown for transparency and are not part of any track record.</p>
          )}
          <p className="eyebrow">RUNS</p>
          <div className="table table-head scanner-grid"><span>Observed</span><span>Type</span><span>Bar date</span><span>Ranked of listed · excluded</span></div>
          <div className="table scanner-grid g-runs">
            {card.runs.map((r) => (
              <div className="row" key={r.observed_at}><span>{r.observed_at.slice(0, 16).replace("T", " ")} UTC</span><span title={r.origin_reason}>{r.origin}</span><span>{r.as_of}</span><span>{r.ranked_count} of {r.universe_count} · {r.excluded_count} excluded</span></div>
            ))}
          </div>
          <p className="eyebrow">SIGNALS</p>
          <div className="table table-head scanner-grid"><span>Signal</span><span>Type</span><span>5d vs NIFTY</span><span>20d / 60d vs NIFTY</span></div>
          <div className="table scanner-grid g-sig">
            {card.recent.slice(0, sigLimit).map((r) => (
              <div className="row" key={r.source_bar_date + r.symbol + r.kind + r.origin}>
                <span>{r.symbol} · {r.kind === "breakout" ? "breakout" : "RS 90+"} · {r.source_bar_date}</span><span>{r.origin}</span>
                <span>{r.d5 ? pct(r.d5.vs_nifty_pct) : "pending"}</span><span>{(r.d20 ? pct(r.d20.vs_nifty_pct) : "pending") + " / " + (r.d60 ? pct(r.d60.vs_nifty_pct) : "pending")}</span>
              </div>
            ))}
          </div>
          {card.recent.length > sigLimit && <button className="btn-secondary" onClick={() => setSigLimit(sigLimit + 25)}>Show 25 more ({sigLimit} of {card.recent.length})</button>}
        </>
      )}

      {view === "backtest" && (
        <>
          <p className="muted small-print">Pick from a fixed menu of rules; no custom code runs. Long-only, signals on the close, position from the next day, fees and slippage charged each way.</p>
          <div className="screener-filters">
            <label>Symbol<input value={rule.symbol} onChange={set("symbol")} /></label>
            <label>Entry
              <select value={rule.entry} onChange={set("entry")}>
                <option value="breakout">Breakout of N-day high</option>
                <option value="sma_cross">Fast SMA above slow SMA</option>
                <option value="momentum">N-day return above %</option>
              </select>
            </label>
            <label>N / slow days<input type="number" value={rule.entry_n} onChange={set("entry_n")} /></label>
            {rule.entry === "sma_cross" && <label>Fast days<input type="number" value={rule.entry_fast} onChange={set("entry_fast")} /></label>}
            {rule.entry === "momentum" && <label>Return above %<input type="number" value={rule.entry_threshold_pct} onChange={set("entry_threshold_pct")} /></label>}
            <label>Exit
              <select value={rule.exit} onChange={set("exit")}>
                <option value="below_sma">Close below N-day average</option>
                <option value="trailing_stop">Trailing stop %</option>
                <option value="hold_days">Hold N days</option>
              </select>
            </label>
            {rule.exit === "trailing_stop" ? <label>Stop %<input type="number" value={rule.exit_stop_pct} onChange={set("exit_stop_pct")} /></label> : <label>Exit N days<input type="number" value={rule.exit_n} onChange={set("exit_n")} /></label>}
            <label>Fees bps/side<input type="number" value={rule.cost_bps} onChange={set("cost_bps")} /></label>
            <label>Slippage bps/side<input type="number" value={rule.slippage_bps} onChange={set("slippage_bps")} /></label>
            <button className="btn-primary" onClick={runBacktest} disabled={busy}>{busy ? "Running…" : "Run backtest"}</button>
          </div>
          {bt && (
            <>
              <div className="table table-head scanner-grid bt-head"><span>{bt.symbol} · {bt.trades} trades · {bt.time_in_market_pct}% in market</span><span>Return</span><span>Max drawdown</span><span>Days</span></div>
              <div className="table scanner-grid g-bt">
                {[
                  ["Rule · full period", bt.full.strategy], ["Buy and hold", bt.full.buy_and_hold], ["NIFTY 50", bt.full.nifty50_buy_and_hold],
                  ["Rule · out-of-sample from " + bt.out_of_sample.starts, bt.out_of_sample.strategy], ["Buy and hold · out-of-sample", bt.out_of_sample.buy_and_hold],
                ].map(([label, s]) => (
                  <div className="row" key={label}><span>{label}</span><span className={cls(s.return_pct)}>{pct(s.return_pct)}</span><span className="negative">{s.max_drawdown_pct}%</span><span>{s.days}</span></div>
                ))}
              </div>
              <ul className="muted small-print">{bt.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
            </>
          )}
        </>
      )}

      <p className="muted small-print">{coverage?.disclaimer}</p>
    </section>
  );
}
