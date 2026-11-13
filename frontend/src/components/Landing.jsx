import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { GITHUB_URL, IS_DEMO } from "../config";
import Brand from "./Brand";

const STEPS = [
  {
    n: "01",
    title: "Ingest",
    body: "Daily bars for the NIFTY 50 universe, spot gold and silver, and USD/INR, EUR/INR and GBP/INR pairs are pulled server-side from Yahoo Finance (Twelve Data for optional US symbols), then stored with provider provenance.",
  },
  {
    n: "02",
    title: "Features",
    body: "Returns, moving-average ratios, volatility and volume change are computed only from data available at that point in time.",
  },
  {
    n: "03",
    title: "Model",
    body: "A scikit-learn model produces next-period NSE-equity close estimates from supported positive-volume input. Zero-volume gold, silver and FX inputs are not supported for predictions.",
  },
  {
    n: "04",
    title: "Reconcile",
    body: "Stored predictions can be scored once matching realized closes are available. Only reconciled records enter the reported statistics; pending forecasts are not scored results.",
  },
];

const STACK = ["FastAPI", "PostgreSQL", "Redis", "scikit-learn", "React", "Docker", "GitHub Actions"];

function fmtPct(v, signed = true) {
  if (v == null) return "—";
  return (signed && v >= 0 ? "+" : "") + Number(v).toFixed(2) + "%";
}

export default function Landing({ onSignIn, onRegister, onDemo, demoBusy, demoError }) {
  const [overview, setOverview] = useState(null);
  const [accuracy, setAccuracy] = useState(null);
  const [latest, setLatest] = useState(null);
  const [warming, setWarming] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const warmTimer = useRef(null);

  useEffect(() => {
    warmTimer.current = setTimeout(() => setWarming(true), 3000);
    const done = () => {
      clearTimeout(warmTimer.current);
      setWarming(false);
      setLoaded(true);
    };
    api("/public/market-overview")
      .then(setOverview)
      .catch(() => setOverview(null))
      .finally(done);
    api("/public/accuracy").then(setAccuracy).catch(() => setAccuracy(null));
    api("/public/predictions/latest").then(setLatest).catch(() => setLatest(null));
    return () => clearTimeout(warmTimer.current);
  }, []);

  const predictions = latest?.predictions || [];
  const fallbackSymbols = overview?.symbols || [];
  const overall = accuracy?.overall || {};
  const scored = overall.evaluated_predictions || 0;

  const stats = [
    { label: "Predictions scored", value: scored > 0 ? String(scored) : null, hint: "reconciled vs real closes" },
    { label: "Pooled model hit rate", value: overall.directional_accuracy_pct != null ? Number(overall.directional_accuracy_pct).toFixed(1) + "%" : null, hint: "all scored symbols and versions" },
    { label: "Pooled mean absolute error", value: overall.mae != null ? Number(overall.mae).toFixed(2) : null, hint: "may mix price units; not per-symbol accuracy" },
    { label: "Naive baseline hit rate", value: overall.baseline_directional_accuracy_pct != null ? Number(overall.baseline_directional_accuracy_pct).toFixed(1) + "%" : null, hint: "always-up guess, same period" },
  ];

  return (
    <div className="landing">
      <nav className="landing-nav">
        <Brand />
        <div className="landing-nav-links">
          <a href="#proof">Track record</a>
          <a href="#how">How it works</a>
          <a href={GITHUB_URL} target="_blank" rel="noreferrer">Source</a>
        </div>
        <div className="landing-nav-actions">
          <button className="btn-ghost" onClick={onSignIn}>Sign in</button>
          <button className="btn-primary btn-inline" onClick={onRegister}>Create account</button>
        </div>
      </nav>

      <header className="hero">
        <p className="eyebrow">MARKET INTELLIGENCE PLATFORM</p>
        <h1>Market history and supported<br />NSE-equity forecasts.</h1>
        <p className="hero-sub">
          Explore NSE, gold, silver and INR-pair history in a research sandbox. Forecasts
          require supported positive-volume inputs: zero-volume gold, silver and FX
          predictions are not supported. Stored forecasts are scored only when matching
          realized closes are available.
        </p>
        <div className="hero-cta">
          <button className="btn-primary btn-hero" onClick={IS_DEMO ? onDemo : onRegister} disabled={demoBusy}>
            {demoBusy ? "Signing you in..." : "Live dashboard"}
          </button>
        </div>
        {IS_DEMO && (
          <p className="hero-note">One click signs you in, no signup needed.</p>
        )}
        {demoBusy && <p className="warmup-note" role="status">Connecting to the demo. A sleeping server can take several minutes to start. This does not run a forecast.</p>}
        {demoError && <div className="error" role="alert">{demoError}</div>}
        {warming && (
          <p className="warmup-note">Market data is taking longer to load. The server may be starting; this can take several minutes.</p>
        )}

        <div className="ticker-strip">
          {!loaded && predictions.length === 0 && fallbackSymbols.length === 0 &&
            [0, 1, 2, 3].map((i) => <div className="ticker-card skeleton" key={i} />)}
          {predictions.length > 0
            ? predictions.map((p) => (
                <div className="ticker-card" key={p.symbol}>
                  <span className="ticker-symbol">{p.symbol}</span>
                  <strong>{fmtPct(p.expected_change_pct)}</strong>
                  <span className={(p.expected_change_pct ?? 0) >= 0 ? "positive" : "negative"}>
                    predicted {p.prediction_date}
                  </span>
                  <small>stored forecast</small>
                </div>
              ))
            : fallbackSymbols.map((s) => (
                <div className="ticker-card" key={s.symbol}>
                  <span className="ticker-symbol">{s.symbol}</span>
                  <strong>{(s.currency === "INR" ? "₹" : "$") + s.close.toLocaleString(s.currency === "INR" ? "en-IN" : "en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
                  <span className={(s.change_pct ?? 0) >= 0 ? "positive" : "negative"}>
                    {s.change_pct == null ? "—" : fmtPct(s.change_pct)}
                  </span>
                  <small>{s.date}</small>
                </div>
              ))}
        </div>
        <p className="ticker-source">
          {predictions.length > 0
            ? "Latest stored forecasts · may include pending and scored records"
            : "Real market data · " + (overview?.data_source || "Twelve Data and Yahoo Finance daily bars") + " · may be delayed"}
        </p>
      </header>

      <section className="section" id="proof">
        <p className="eyebrow">LIVE TRACK RECORD</p>
        <h2>Stored results, with limits.</h2>
          <p className="muted">Historical figures can include older inference versions and pooled all-symbol statistics. They are not per-symbol accuracy evidence, separate validation of corrected latest-bar-v1 inference, or a measure of future returns.</p>
        <p className="hero-sub">
          Only stored forecasts with matching realized closes count as scored results.
          The directional baseline is an always-up guess over the same scored predictions;
          the per-symbol table also compares percentage error with last-close persistence.
          Pending forecasts, cached responses and failed saves are not new scored records.
        </p>
        <div className="stat-grid">
          {stats.map((s) => (
            <article className={"stat-card" + (s.value == null ? " skeleton-card" : "")} key={s.label}>
              <span>{s.label}</span>
              <strong>{s.value ?? (loaded ? "Building" : "…")}</strong>
              <small>{s.value == null && loaded ? "track record fills as predictions get scored" : s.hint}</small>
            </article>
          ))}
        </div>
        {accuracy?.symbols?.length > 0 && (
          <div className="accuracy-wrap">
            <table className="accuracy-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Scored predictions</th>
                  <th>Model MAPE</th>
                  <th>Persistence MAPE</th>
                  <th>Vs baseline</th>
                  <th>Hit rate</th>
                </tr>
              </thead>
              <tbody>
                {accuracy.symbols.map((row) => (
                  <tr key={row.symbol}>
                    <td>{row.symbol}</td>
                    <td>{row.evaluated_predictions}</td>
                    <td>{row.mape_pct == null ? "n/a" : Number(row.mape_pct).toFixed(2) + "%"}</td>
                    <td>{row.baseline_mape_pct == null ? "n/a" : Number(row.baseline_mape_pct).toFixed(2) + "%"}</td>
                    <td className={row.improvement_vs_persistence_pct == null ? "" : row.improvement_vs_persistence_pct >= 0 ? "positive" : "negative"}>
                      {row.improvement_vs_persistence_pct == null ? "n/a" : fmtPct(row.improvement_vs_persistence_pct, true).replace("%", "") + "%"}
                    </td>
                    <td>{row.directional_accuracy_pct == null ? "n/a" : Number(row.directional_accuracy_pct).toFixed(1) + "%"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="accuracy-note">
              Live track record since {overall.first_prediction_date}, not a backtest. Sample
              sizes are small by design and shown on purpose. Research and engineering project.
              Not investment advice. Not a SEBI-registered research analyst or investment
              adviser. Past model performance does not indicate future results. Do not trade
              on this.
            </p>
          </div>
        )}
      </section>

      <section className="section" id="how">
        <p className="eyebrow">HOW IT WORKS</p>
        <h2>Ingest, featurize, predict, reconcile.</h2>
        <div className="arch-diagram">
          {["Twelve Data + Yahoo Finance", "FastAPI ingest", "Feature pipeline", "scikit-learn model", "Prediction store", "Reconciliation"].map((label, i) => (
            <div className="arch-node" key={label}>
              <span>{label}</span>
              {i < 5 && <em>→</em>}
            </div>
          ))}
        </div>
        <div className="steps">
          {STEPS.map((s) => (
            <article className="step-card" key={s.n}>
              <span className="step-n">{s.n}</span>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </article>
          ))}
        </div>
        <div className="stack-row">
          {STACK.map((s) => <span className="stack-badge" key={s}>{s}</span>)}
        </div>
      </section>

      <section className="section landing-final">
        <h2>Inspect the record, including its limits.</h2>
        <p className="hero-sub">
          The dashboard separates stored forecasts, reconciled results and historical
          backtests. Small samples and older inference versions limit what the numbers
          can show. Backtests and simulated trading are not live investment performance.
        </p>
        <div className="hero-cta">
          <button className="btn-primary btn-hero" onClick={IS_DEMO ? onDemo : onRegister} disabled={demoBusy}>
            {demoBusy ? "Signing you in..." : "Open the dashboard"}
          </button>
          <button className="btn-outline btn-hero" onClick={onSignIn}>Sign in</button>
        </div>
      </section>

      <footer className="landing-footer">
        <Brand />
        <div className="stack-row footer-stack">
          {STACK.map((s) => <span className="stack-badge" key={s}>{s}</span>)}
        </div>
        <p>
          Research and engineering project. Not investment advice. Not a SEBI-registered research analyst or investment adviser. Past model performance does not indicate future results. Do not trade on this. Market data may be
          delayed. This site runs on free-tier hosting; a cold start can take several minutes.
          If sign-in times out, wait a moment and retry manually.
        </p>
        <p className="muted">
          Built by Himanshu Bisht with friends · <a href={GITHUB_URL} target="_blank" rel="noreferrer">Source on GitHub</a>
        </p>
      </footer>
    </div>
  );
}
