import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { FALLBACK_SYMBOLS, IS_DEMO } from "../config";
import Brand from "./Brand";
import PriceChart from "./PriceChart";

function fmtPct(v) {
  if (v == null) return "—";
  return (v >= 0 ? "+" : "") + Number(v).toFixed(2) + "%";
}

export default function Dashboard({ user, onSignOut }) {
  const [tab, setTab] = useState("overview");
  const [symbols, setSymbols] = useState(FALLBACK_SYMBOLS);
  const [symbol, setSymbol] = useState(FALLBACK_SYMBOLS[0]);
  const [bars, setBars] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [history, setHistory] = useState([]);
  const [evaluation, setEvaluation] = useState(null);
  const [offlineMetrics, setOfflineMetrics] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [dataSource, setDataSource] = useState("");

  useEffect(() => {
    api("/public/market-overview")
      .then((ov) => {
        if (ov?.symbols?.length) {
          const list = ov.symbols.map((s) => s.symbol);
          setSymbols(list);
          setSymbol((cur) => (list.includes(cur) ? cur : list[0]));
          setDataSource(ov.data_source || "");
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    setBars([]);
    api("/stocks/" + symbol + "/history?limit=150")
      .then(setBars)
      .catch(() => setBars([]));
  }, [symbol]);

  useEffect(() => {
    api("/predictions?limit=20").then(setHistory).catch(() => setHistory([]));
    api("/predictions/evaluation").then(setEvaluation).catch(() => setEvaluation(null));
    api("/metrics").then((m) => {
      if (m && m.status !== "not_available") setOfflineMetrics(m);
    }).catch(() => {});
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

  const firstName = user.full_name || user.email.split("@")[0];

  return (
    <div className="app-shell">
      <aside>
        <Brand />
        <nav>
          <a className={tab === "overview" ? "active" : ""} onClick={() => setTab("overview")}>Overview</a>
          <a className={tab === "activity" ? "active" : ""} onClick={() => setTab("activity")}>Prediction activity</a>
          <a className={tab === "evaluation" ? "active" : ""} onClick={() => setTab("evaluation")}>Model evaluation</a>
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
              <article><span>Latest close · {symbol}</span><strong>{market ? "$" + market.close.toFixed(2) : "—"}</strong><small>{market ? market.date : "Loading market data"}</small></article>
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
                  <h2>{symbol} · daily bars</h2>
                </div>
                <div className="symbol-pills">
                  {symbols.map((s) => (
                    <button key={s} className={"pill" + (s === symbol ? " active" : "")} onClick={() => setSymbol(s)}>{s}</button>
                  ))}
                </div>
              </div>
              <PriceChart bars={bars} />
              <p className="chart-note">Source: {bars[0]?.source_provider === "csv-sample" ? "checked-in sample data" : dataSource || "Twelve Data"} · daily bars · may be delayed</p>
            </section>

            <section className="workspace">
              <article className="panel">
                <div className="panel-head">
                  <div><p className="eyebrow">PREDICTION ENGINE</p><h2>Next-period close · {symbol}</h2></div>
                </div>
                <div className="prediction-box">
                  <div>
                    <span>Predicted close</span>
                    <strong>{prediction ? "$" + prediction.predicted_close.toFixed(2) : "—"}</strong>
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
                  <span>${item.predicted_close.toFixed(2)}</span>
                  <span>{item.actual_close ? "$" + item.actual_close.toFixed(2) : "Pending"}</span>
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
      </main>
    </div>
  );
}
