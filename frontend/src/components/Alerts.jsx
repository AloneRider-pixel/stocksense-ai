import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";

export default function Alerts({ symbols }) {
  const [rules, setRules] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ symbol: "", direction: "above", target: "" });

  const refresh = useCallback(() => {
    api("/alerts").then((r) => setRules(r.rules || [])).catch((e) => setError(e.message));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  async function createRule(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api("/alerts", {
        method: "POST",
        body: JSON.stringify({
          symbol: form.symbol.trim(),
          direction: form.direction,
          target_price: form.target,
        }),
      });
      setNotice("Alert rule created. It fires only on crossings in newer daily closes - existing price history is not backfilled.");
      setForm((f) => ({ ...f, target: "" }));
      refresh();
    } catch (e2) {
      setError(e2.message);
    } finally {
      setBusy(false);
    }
  }

  async function deactivate(id) {
    setError("");
    try {
      await api("/alerts/" + id + "/deactivate", { method: "POST" });
      refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <section>
      <div className="sim-banner">
        Price alerts are simulated on stored daily closes, which may be delayed.
        Delivery is in-app only right now - no emails are sent.
      </div>

      <div className="card">
        <h3>New alert rule</h3>
        <form className="order-form" onSubmit={createRule}>
          <input
            list="alert-symbols"
            placeholder="Symbol (e.g. RELIANCE)"
            value={form.symbol}
            onChange={(e) => setForm((f) => ({ ...f, symbol: e.target.value }))}
            required
          />
          <datalist id="alert-symbols">
            {(symbols || []).map((s) => <option key={s} value={s} />)}
          </datalist>
          <select value={form.direction} onChange={(e) => setForm((f) => ({ ...f, direction: e.target.value }))}>
            <option value="above">Crosses above</option>
            <option value="below">Crosses below</option>
          </select>
          <input
            type="number"
            min="0.0001"
            step="any"
            placeholder="Target price"
            value={form.target}
            onChange={(e) => setForm((f) => ({ ...f, target: e.target.value }))}
            required
          />
          <button className="btn-primary btn-inline" disabled={busy} type="submit">
            {busy ? "Creating…" : "Create alert"}
          </button>
        </form>
        {notice && <p className="muted">{notice}</p>}
        {error && <p className="error-text">{error}</p>}
      </div>

      <div className="card">
        <h3>Your alert rules</h3>
        {rules.length === 0 && <div className="empty">No alert rules yet.</div>}
        {rules.length > 0 && (
          <div className="table alerts-grid">
            <div className="table-head alerts-grid">
              <span>Symbol</span><span>Rule</span><span>Status</span><span>Watching from</span><span>Last triggered</span><span></span>
            </div>
            {rules.map((r) => (
              <div className="row" key={r.id}>
                <span>{r.symbol}</span>
                <span>{r.direction} {Number(r.target_price).toLocaleString("en-IN")}</span>
                <span className={r.active ? "positive" : "muted"}>{r.active ? "active" : "inactive"}</span>
                <span>{r.baseline_bar_date || "—"}</span>
                <span>{r.last_triggered_bar_date || "Never"}</span>
                <span>
                  {r.active && (
                    <button className="btn-ghost btn-inline" onClick={() => deactivate(r.id)}>Deactivate</button>
                  )}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
