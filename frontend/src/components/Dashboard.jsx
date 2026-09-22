import Brand from "./Brand";

export default function Dashboard({
  user,
  symbol,
  setSymbol,
  market,
  prediction,
  history,
  evaluation,
  busy,
  error,
  onPredict,
  onSignOut,
}) {
  return (
    <div className="app-shell">
      <aside>
        <Brand />
        <nav>
          <a className="active">Overview</a>
          <a>Watchlist</a>
          <a>Predictions</a>
          <a>Portfolio</a>
          <a>Alerts</a>
        </nav>
        <button className="ghost" onClick={onSignOut}>Sign out</button>
      </aside>

      <main className="dashboard">
        <header>
          <div>
            <p className="eyebrow">OVERVIEW</p>
            <h1>Good evening, {user.full_name || user.email.split("@")[0]}</h1>
            <p className="muted">Market analytics, model signals, and prediction history.</p>
          </div>
          <div className="user-chip">{user.email}</div>
        </header>

        <section className="metric-grid">
          <article><span>Tracked symbol</span><strong>{symbol}</strong><small>Configured market feed</small></article>
          <article><span>Latest close</span><strong>{market ? market.close.toFixed(2) : "—"}</strong><small>{market ? market.date : "Waiting for data"}</small></article>
          <article><span>Model</span><strong>{prediction?.model || "RF v0.3"}</strong><small>Next-period regression</small></article>
          <article><span>History records</span><strong>{history.length}</strong><small>Per-user predictions</small></article>
          <article><span>Evaluated</span><strong>{evaluation?.evaluated_predictions ?? 0}</strong><small>Predictions with actuals</small></article>
          <article><span>Directional accuracy</span><strong>{evaluation?.directional_accuracy_pct != null ? evaluation.directional_accuracy_pct.toFixed(1) + "%" : "—"}</strong><small>Online evaluation</small></article>
          <article><span>Online MAE</span><strong>{evaluation?.mae != null ? evaluation.mae.toFixed(3) : "—"}</strong><small>Realized prediction error</small></article>
        </section>

        <section className="workspace">
          <article className="panel">
            <div className="panel-head">
              <div><p className="eyebrow">PREDICTION ENGINE</p><h2>Next-period close</h2></div>
              <input
                className="symbol-input"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                maxLength={16}
              />
            </div>

            <div className="prediction-box">
              <div>
                <span>Predicted close</span>
                <strong>{prediction ? prediction.predicted_close.toFixed(2) : "—"}</strong>
              </div>
              <div>
                <span>Expected change</span>
                <strong className={(prediction?.expected_change_pct ?? 0) >= 0 ? "positive" : "negative"}>
                  {prediction ? prediction.expected_change_pct.toFixed(2) + "%" : "—"}
                </strong>
              </div>
            </div>

            <button onClick={onPredict} disabled={busy}>
              {busy ? "Running model..." : "Run prediction"}
            </button>
            {error && <div className="error">{error}</div>}
          </article>

          <article className="panel">
            <p className="eyebrow">RECENT ACTIVITY</p>
            <h2>Prediction history</h2>
            <div className="table">
              {history.length === 0 && <div className="empty">No predictions recorded yet.</div>}
              {history.map((item) => (
                <div className="row" key={item.id}>
                  <span>{item.symbol} · {item.prediction_date}</span>
                  <span>{item.predicted_close.toFixed(2)}</span>
                  <span>{item.actual_close ? item.actual_close.toFixed(2) : "Pending"}</span>
                  <span>
                    {item.actual_close
                      ? "Error " + item.percentage_error.toFixed(2) + "%"
                      : "Awaiting actual"}
                  </span>
                </div>
              ))}
            </div>
          </article>
        </section>
      </main>
    </div>
  );
}
