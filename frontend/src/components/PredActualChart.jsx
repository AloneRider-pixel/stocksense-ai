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

export default function PredActualChart({ items, currency }) {
  const scored = (items || [])
    .filter((i) => i.actual_close != null)
    .slice()
    .sort((a, b) => (a.prediction_date < b.prediction_date ? -1 : 1));

  if (scored.length < 2) {
    return <div className="empty">Predicted-vs-actual lines appear once at least two predictions have been scored.</div>;
  }

  const values = scored.flatMap((i) => [i.predicted_close, i.actual_close]);
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
  const ticks = [min, (min + max) / 2, max];
  const sym = currency === "INR" ? "₹" : "$";

  return (
    <div className="equity-chart">
      <svg viewBox={"0 0 " + W + " " + H} width="100%" role="img" aria-label="Predicted vs actual closes">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="#1f2f47" strokeWidth="1" />
            <text x={PAD.left - 8} y={y(t) + 4} fill="#7590b0" fontSize="11" textAnchor="end">
              {sym + t.toFixed(2)}
            </text>
          </g>
        ))}
        <path d={predicted} fill="none" stroke="#5b9dff" strokeWidth="2" />
        <path d={actual} fill="none" stroke="#4ade9d" strokeWidth="1.6" />
        <text x={PAD.left} y={H - 6} fill="#7590b0" fontSize="11">{scored[0].prediction_date}</text>
        <text x={W - PAD.right} y={H - 6} fill="#7590b0" fontSize="11" textAnchor="end">{scored[scored.length - 1].prediction_date}</text>
      </svg>
      <div className="equity-legend">
        <span><i className="legend-dot" style={{ background: "#5b9dff" }} />Predicted close</span>
        <span><i className="legend-dot" style={{ background: "#4ade9d" }} />Actual close</span>
      </div>
    </div>
  );
}
