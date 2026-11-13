import { useState } from "react";

const W = 860;
const H = 240;
const PAD = { top: 16, right: 16, bottom: 24, left: 70 };

function path(pts) {
  let d = "";
  let open = false;
  pts.forEach((p, i) => {
    if (!p) { open = false; return; }
    d += (open ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1) + " ";
    open = true;
  });
  return d;
}

export default function PredActualChart({ items, symbolMeta = {} }) {
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const symbols = [...new Set((items || []).filter((i) => i.actual_close != null).map((i) => i.symbol))].sort();
  const symbol = symbols.includes(selectedSymbol) ? selectedSymbol : symbols[0];
  const currency = symbolMeta[symbol]?.currency;
  const scored = (items || [])
    .filter((i) => i.symbol === symbol)
    .filter((i) => i.actual_close != null)
    .slice()
    .sort((a, b) => (a.prediction_date < b.prediction_date ? -1 : 1));

  const selector = symbols.length > 0 && (
    <label className="chart-symbol-control">Chart symbol
      <select aria-label="Chart symbol" value={symbol} onChange={(event) => setSelectedSymbol(event.target.value)}>
        {symbols.map((value) => <option key={value} value={value}>{value}</option>)}
      </select>
    </label>
  );
  if (scored.length < 2) {
    return <div>{selector}<p className="empty">At least two scored records for the same symbol are needed for a line chart. Different symbols are never joined.</p></div>;
  }

  const hasBaseline = scored.some((i) => i.baseline_close != null);
  const values = scored.flatMap((i) =>
    [i.predicted_close, i.actual_close, i.baseline_close].filter((v) => v != null)
  );
  let min = Math.min(...values);
  let max = Math.max(...values);
  const pad = (max - min || 1) * 0.08;
  min -= pad;
  max += pad;

  const iw = W - PAD.left - PAD.right;
  const ih = H - PAD.top - PAD.bottom;
  const x = (i) => PAD.left + (scored.length === 1 ? iw / 2 : (i / (scored.length - 1)) * iw);
  const y = (v) => PAD.top + (1 - (v - min) / (max - min)) * ih;

  const predicted = path(scored.map((p, i) => [x(i), y(p.predicted_close)]));
  const actual = path(scored.map((p, i) => [x(i), y(p.actual_close)]));
  const baseline = hasBaseline
    ? path(scored.map((p, i) => (p.baseline_close == null ? null : [x(i), y(p.baseline_close)])))
    : null;
  const ticks = [min, (min + max) / 2, max];
  const sym = currency === "INR" ? "₹" : currency === "USD" ? "$" : "";

  return (
    <div className="equity-chart">
      {selector}
      <p className="muted small-print">{symbol} · {currency || "currency not provided"} · {scored.length} scored records shown</p>
      <div className="record-chart-scroll" tabIndex={0} aria-label="Scrollable prediction chart">
      <svg viewBox={"0 0 " + W + " " + H} width="100%" role="img" aria-label={"Predicted vs actual closes for " + symbol}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="#1f2f47" strokeWidth="1" />
            <text x={PAD.left - 8} y={y(t) + 4} fill="#7590b0" fontSize="11" textAnchor="end">
              {sym + t.toFixed(2)}
            </text>
          </g>
        ))}
        {baseline && (
          <path d={baseline} fill="none" stroke="#8a97ab" strokeWidth="1.4" strokeDasharray="5 4" />
        )}
        <path d={predicted} fill="none" stroke="#5b9dff" strokeWidth="2" />
        <path d={actual} fill="none" stroke="#4ade9d" strokeWidth="1.6" />
        <text x={PAD.left} y={H - 6} fill="#7590b0" fontSize="11">{scored[0].prediction_date}</text>
        <text x={W - PAD.right} y={H - 6} fill="#7590b0" fontSize="11" textAnchor="end">{scored[scored.length - 1].prediction_date}</text>
      </svg>
      </div>
      <div className="equity-legend">
        <span><i className="legend-dot" style={{ background: "#5b9dff" }} />Predicted close</span>
        <span><i className="legend-dot" style={{ background: "#4ade9d" }} />Actual close</span>
        {baseline && (
          <span><i className="legend-dot" style={{ background: "#8a97ab" }} />Naive baseline (previous close)</span>
        )}
      </div>
    </div>
  );
      }
