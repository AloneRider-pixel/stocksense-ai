import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { GITHUB_URL, IS_DEMO } from "../config";
import Brand from "./Brand";

const FEATURES = [
  {
    title: "Authenticated accounts",
    body: "JWT sign-in with per-user prediction history, so every forecast you run is stored and scored against your own record.",
  },
  {
    title: "Next-close prediction engine",
    body: "A scikit-learn model turns recent price action into features and predicts the next period's close, with the expected change shown up front.",
  },
  {
    title: "Honest evaluation",
    body: "Walk-forward evaluation is strictly chronological: each period is scored only on information available before it. No leakage, no cherry-picking.",
  },
  {
    title: "Prediction vs actual",
    body: "Every stored prediction is reconciled against the realized close, so directional accuracy and error are measured, not claimed.",
  },
  {
    title: "Real market data",
    body: "Daily bars are ingested server-side from Twelve Data and cached in PostgreSQL and Redis. Provider keys never leave the backend.",
  },
  {
    title: "Production discipline",
    body: "Rate-limited API, Docker delivery, CI with lint and 90+ backend tests, and fail-closed production configuration checks.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Ingest",
    body: "Daily market bars for tracked symbols are pulled from Twelve Data and stored with provider provenance.",
  },
  {
    n: "02",
    title: "Predict",
    body: "Recent history becomes model features; the engine returns a next-period close and expected change.",
  },
  {
    n: "03",
    title: "Reconcile",
    body: "When the actual close arrives, the prediction is scored and rolled into accuracy and error metrics.",
  },
];

const STACK = ["FastAPI", "PostgreSQL", "Redis", "scikit-learn", "React", "Docker", "GitHub Actions"];

export default function Landing({ onSignIn, onRegister, onDemo, demoBusy, demoError }) {
  const [overview, setOverview] = useState(null);

  useEffect(() => {
    api("/public/market-overview")
      .then(setOverview)
      .catch(() => setOverview(null));
  }, []);

  const symbols = overview?.symbols || [];

  return (
    <div className="landing">
      <nav className="landing-nav">
        <Brand />
        <div className="landing-nav-links">
          <a href="#product">Product</a>
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
        <h1>Predictions you can<br />actually audit.</h1>
        <p className="hero-sub">
          StockSense AI ingests real market data, predicts the next period's close,
          and then scores every prediction against what actually happened, with the
          accuracy and error metrics on the dashboard, not in a pitch deck.
        </p>
        <div className="hero-cta">
          {IS_DEMO && (
            <button className="btn-primary btn-hero" onClick={onDemo} disabled={demoBusy}>
              {demoBusy ? "Signing you in..." : "Explore the live demo"}
            </button>
          )}
          <button className="btn-outline btn-hero" onClick={onRegister}>Create a free account</button>
        </div>
        {IS_DEMO && (
          <p className="hero-note">One click signs you into the shared demo account, no signup needed.</p>
        )}
        {demoError && <div className="error">{demoError}</div>}

        <div className="ticker-strip">
          {symbols.length === 0 && (
            <div className="ticker-loading">Loading live market snapshot…</div>
          )}
          {symbols.map((s) => (
            <div className="ticker-card" key={s.symbol}>
              <span className="ticker-symbol">{s.symbol}</span>
              <strong>{(s.currency === "INR" ? "₹" : "$") + s.close.toLocaleString(s.currency === "INR" ? "en-IN" : "en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
              <span className={(s.change_pct ?? 0) >= 0 ? "positive" : "negative"}>
                {s.change_pct == null ? "—" : (s.change_pct >= 0 ? "+" : "") + s.change_pct.toFixed(2) + "%"}
              </span>
              <small>{s.date}</small>
            </div>
          ))}
        </div>
        <p className="ticker-source">
          Real market data · {overview?.data_source || "Twelve Data daily bars"} · may be delayed
        </p>
      </header>

      <section className="section" id="product">
        <p className="eyebrow">WHAT IT DOES</p>
        <h2>A full pipeline, not a screenshot of one.</h2>
        <div className="feature-grid">
          {FEATURES.map((f) => (
            <article className="feature-card" key={f.title}>
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section" id="how">
        <p className="eyebrow">HOW IT WORKS</p>
        <h2>Ingest, predict, reconcile.</h2>
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
        <h2>Judge the model by its track record.</h2>
        <p className="hero-sub">
          The dashboard shows measured directional accuracy and realized error for
          every prediction the demo account has made. Create an account and your
          own predictions get scored the same way.
        </p>
        <div className="hero-cta">
          {IS_DEMO && (
            <button className="btn-primary btn-hero" onClick={onDemo} disabled={demoBusy}>
              {demoBusy ? "Signing you in..." : "Open the dashboard"}
            </button>
          )}
          <button className="btn-outline btn-hero" onClick={onSignIn}>Sign in</button>
        </div>
      </section>

      <footer className="landing-footer">
        <Brand />
        <p>
          Predictions are illustrative and are not investment advice. Market data may be
          delayed. Demo runs on free-tier hosting; the first load can take up to a minute
          while the instance wakes.
        </p>
        <p className="muted">
          Designed and built by Himanshu Bisht · <a href={GITHUB_URL} target="_blank" rel="noreferrer">Source on GitHub</a>
        </p>
      </footer>
    </div>
  );
}
