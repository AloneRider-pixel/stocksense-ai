import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";

function inr(v) {
  if (v == null) return "—";
  return "₹" + Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function EquitySpark({ points }) {
  const values = points.map((p) => Number(p.equity));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const w = 600;
  const h = 120;
  const step = w / (values.length - 1);
  const path = values
    .map((v, i) => (i === 0 ? "M" : "L") + (i * step).toFixed(1) + "," + (h - ((v - min) / span) * (h - 16) - 8).toFixed(1))
    .join(" ");
  return (
    <div>
      <svg viewBox={"0 0 " + w + " " + h} className="equity-spark" role="img" aria-label="Paper wallet equity curve">
        <path d={path} fill="none" stroke="#5b9dff" strokeWidth="2" />
      </svg>
      <p className="muted">
        {points.length} snapshots · {inr(points[0].equity)} → {inr(points[points.length - 1].equity)}
        {" ·"}valued at settled closes as of {points[points.length - 1].as_of || "—"}.
        Recorded at fills and after each daily ingest.
      </p>
    </div>
  );
}

export default function Wallet({ symbols }) {
  const [summary, setSummary] = useState(null);
  const [orders, setOrders] = useState([]);
  const [equity, setEquity] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ symbol: "", side: "buy", quantity: "" });

  const refresh = useCallback(() => {
    api("/wallet").then(setSummary).catch((e) => setError(e.message));
    api("/wallet/orders").then((r) => setOrders(r.orders || [])).catch(() => {});
    api("/wallet/equity").then((r) => setEquity(r.snapshots || [])).catch(() => {});
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  async function placeOrder(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const order = await api("/wallet/orders", {
        method: "POST",
        body: JSON.stringify({
          symbol: form.symbol.trim(),
          side: form.side,
          quantity: Number(form.quantity),
        }),
      });
      if (order.status === "filled") {
        setNotice(`Filled ${order.side} ${order.quantity} ${order.symbol} at ${inr(order.fill_price)} (${order.fill_bar_date} close).`);
      } else {
        setNotice(`Order rejected: ${order.reject_code || order.status}.`);
      }
      setForm((f) => ({ ...f, quantity: "" }));
      refresh();
    } catch (e2) {
      setError(e2.message);
    } finally {
      setBusy(false);
    }
  }

  async function resetWallet() {
    if (!window.confirm("Reset the paper wallet back to ₹10,00,000 and clear all simulated positions and orders?")) return;
    setError("");
    setNotice("");
    try {
      await api("/wallet/reset", { method: "POST" });
      setNotice("Paper wallet reset.");
      refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <section>
      <div className="sim-banner">
        Paper trading · simulated only. No real money, no broker, no live quotes.
        Fills use stored daily closes and may be delayed.
      </div>

      {summary && (
        <div className="metric-grid">
          <article><span>Cash</span><strong>{inr(summary.cash)}</strong><small>virtual</small></article>
          <article><span>Market value</span><strong>{inr(summary.market_value)}</strong><small>{summary.as_of ? "closes as of " + summary.as_of : ""}</small></article>
          <article><span>Equity</span><strong>{inr(summary.equity)}</strong><small>cash + holdings</small></article>
          <article><span>Realized P&amp;L</span><strong className={Number(summary.realized_pnl) >= 0 ? "positive" : "negative"}>{inr(summary.realized_pnl)}</strong><small>booked</small></article>
        </div>
      )}

      {equity.length > 1 && (
        <div className="card">
          <h3>Equity curve (simulated)</h3>
          <EquitySpark points={equity} />
        </div>
      )}

      <div className="card">
        <h3>Place a simulated order</h3>
        <form className="order-form" onSubmit={placeOrder}>
          <input
            list="wallet-symbols"
            placeholder="Symbol (e.g. RELIANCE)"
            value={form.symbol}
            onChange={(e) => setForm((f) => ({ ...f, symbol: e.target.value }))}
            required
          />
          <datalist id="wallet-symbols">
            {(symbols || []).map((s) => <option key={s} value={s} />)}
          </datalist>
          <select value={form.side} onChange={(e) => setForm((f) => ({ ...f, side: e.target.value }))}>
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
          <input
            type="number"
            min="1"
            step="1"
            placeholder="Quantity"
            value={form.quantity}
            onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))}
            required
          />
          <button className="btn-primary btn-inline" disabled={busy} type="submit">
            {busy ? "Placing…" : "Place paper order"}
          </button>
        </form>
        {notice && <p className="muted">{notice}</p>}
        {error && <p className="error-text">{error}</p>}
      </div>

      {summary && summary.positions.length > 0 && (
        <div className="card">
          <h3>Positions</h3>
          <div className="table positions-grid">
            <div className="table-head positions-grid">
              <span>Symbol</span><span>Qty</span><span>Avg cost</span><span>Last close</span><span>Value</span><span>Unrealized</span><span>Realized</span>
            </div>
            {summary.positions.map((p) => (
              <div className="row" key={p.symbol}>
                <span>{p.symbol}</span>
                <span>{p.quantity}</span>
                <span>{inr(p.avg_cost)}</span>
                <span>{inr(p.last_close)} <small className="muted">{p.bar_date}</small></span>
                <span>{inr(p.market_value)}</span>
                <span className={Number(p.unrealized_pnl) >= 0 ? "positive" : "negative"}>{inr(p.unrealized_pnl)}</span>
                <span className={Number(p.realized_pnl) >= 0 ? "positive" : "negative"}>{inr(p.realized_pnl)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <h3>Order history</h3>
        {orders.length === 0 && <div className="empty">No paper orders yet.</div>}
        {orders.length > 0 && (
          <div className="table orders-grid">
            <div className="table-head orders-grid">
              <span>Time</span><span>Symbol</span><span>Side</span><span>Qty</span><span>Status</span><span>Fill</span>
            </div>
            {orders.map((o) => (
              <div className="row" key={o.id}>
                <span>{o.created_at ? new Date(o.created_at).toLocaleString("en-IN") : "—"}</span>
                <span>{o.symbol}</span>
                <span>{o.side}</span>
                <span>{o.quantity}</span>
                <span className={o.status === "filled" ? "positive" : "negative"}>
                  {o.status}{o.reject_code ? " · " + o.reject_code : ""}
                </span>
                <span>{o.fill_price ? inr(o.fill_price) + " (" + o.fill_bar_date + ")" : "—"}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <button className="ghost" onClick={resetWallet}>Reset paper wallet</button>
    </section>
  );
}
