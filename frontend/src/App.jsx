import { useEffect, useState } from "react";
import { api, clearToken, setToken } from "./lib/api";

const demoHistory = [
  { close: 108.4, volume: 1370000 },
  { close: 109.1, volume: 1380000 },
  { close: 109.7, volume: 1400000 },
  { close: 110.0, volume: 1410000 },
  { close: 110.6, volume: 1420000 },
  { close: 111.0, volume: 1430000 },
  { close: 111.4, volume: 1440000 },
  { close: 112.1, volume: 1450000 },
  { close: 112.7, volume: 1460000 },
  { close: 113.3, volume: 1470000 },
  { close: 114.0, volume: 1480000 },
];

export default function App() {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [symbol, setSymbol] = useState("DEMO");
  const [user, setUser] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem("stocksense_token")) return;
    api("/auth/me").then(setUser).catch(() => clearToken());
  }, []);

  async function submitAuth(event) {
    event.preventDefault();
    setBusy(true);
    setError("");

    try {
      if (mode === "register") {
        await api("/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password, full_name: fullName || null }),
        });
      }

      const result = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      setToken(result.access_token);
      setUser(await api("/auth/me"));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function runPrediction() {
    setBusy(true);
    setError("");

    try {
      const result = await api("/predict", {
        method: "POST",
        body: JSON.stringify({ symbol, history: demoHistory }),
      });

      setPrediction(result);
      setHistory(await api("/predictions?limit=10"));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!user) {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <div className="brand">StockSense <span>AI</span></div>
          <p className="eyebrow">MARKET INTELLIGENCE PLATFORM</p>
          <h1>{mode === "login" ? "Market intelligence, built for decisions." : "Create your StockSense account."}</h1>

          <form onSubmit={submitAuth}>
            {mode === "register" && (
              <>
                <label>Full name</label>
                <input value={fullName} onChange={(e) => setFullName(e.target.value)} maxLength={120} />
              </>
            )}

            <label>Email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />

            <label>Password</label>
            <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" minLength={8} required />

            <button disabled={busy}>
              {busy ? "Working..." : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          {error && <div className="error">{error}</div>}

          <button
            className="switch-auth"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError("");
            }}
          >
            {mode === "login" ? "Create an account" : "Back to sign in"}
          </button>
        </section>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <aside>
        <div className="brand">StockSense <span>AI</span></div>
        <nav>
          <a className="active">Overview</a>
          <a>Watchlist</a>
          <a>Predictions</a>
          <a>Portfolio</a>
          <a>Alerts</a>
        </nav>
        <button className="ghost" onClick={() => { clearToken(); setUser(null); }}>Sign out</button>
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
          <article><span>Model</span><strong>RF v0.2</strong><small>Next-period regression</small></article>
          <article><span>Prediction state</span><strong>{prediction ? "Ready" : "Waiting"}</strong><small>{prediction ? "Latest inference complete" : "Run an inference"}</small></article>
          <article><span>History records</span><strong>{history.length}</strong><small>Per-user predictions</small></article>
        </section>

        <section className="workspace">
          <article className="panel">
            <div className="panel-head">
              <div><p className="eyebrow">PREDICTION ENGINE</p><h2>Next-period close</h2></div>
              <input className="symbol-input" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} maxLength={16} />
            </div>

            <div className="prediction-box">
              <div><span>Predicted close</span><strong>{prediction ? prediction.predicted_close.toFixed(2) : "—"}</strong></div>
              <div><span>Expected change</span><strong className={(prediction?.expected_change_pct ?? 0) >= 0 ? "positive" : "negative"}>{prediction ? prediction.expected_change_pct.toFixed(2) + "%" : "—"}</strong></div>
            </div>

            <button onClick={runPrediction} disabled={busy}>{busy ? "Running model..." : "Run prediction"}</button>
            {error && <div className="error">{error}</div>}
          </article>

          <article className="panel">
            <p className="eyebrow">RECENT ACTIVITY</p>
            <h2>Prediction history</h2>
            <div className="table">
              {history.length === 0 && <div className="empty">No predictions recorded yet.</div>}
              {history.map((item) => (
                <div className="row" key={item.id}>
                  <span>{item.symbol}</span>
                  <span>{item.predicted_close.toFixed(2)}</span>
                  <span>{item.expected_change_pct.toFixed(2)}%</span>
                  <span>{new Date(item.created_at).toLocaleString()}</span>
                </div>
              ))}
            </div>
          </article>
        </section>
      </main>
    </div>
  );
}
