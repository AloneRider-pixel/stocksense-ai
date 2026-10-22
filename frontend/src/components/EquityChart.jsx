const W = 860;
const H = 260;
const PAD = { top: 16, right: 16, bottom: 24, left: 60 };

function path(pts) {
  return pts
    .map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + " " + p[1].toFixed(1))
    .join(" ");
}

export default function EquityChart({ curve }) {
  if (!curve || curve.length === 0) {
    return <div className="empty">No backtest observations yet.</div>;
  }

  const values = curve.flatMap((p) => [p.strategy, p.buy_hold]);
  let min = Math.min(...values, 0);
  let max = Math.max(...values, 0);
  const pad = (max - min || 1) * 0.08;
  min -= pad;
  max += pad;

  const iw = W - PAD.left - PAD.right;
  const ih = H - PAD.top - PAD.bottom;
  const x = (i) => PAD.left + (curve.length === 1 ? iw / 2 : (i / (curve.length - 1)) * iw);
  const y = (v) => PAD.top + (1 - (v - min) / (max - min)) * ih;

  const strategy = path(curve.map((p, i) => [x(i), y(p.strategy)]));
  const buyHold = path(curve.map((p, i) => [x(i), y(p.buy_hold)]));
  const ticks = [min, (min + max) / 2, max];

  return (
    <div className="equity-chart">
      <svg viewBox={"0 0 " + W + " " + H} width="100%" role="img" aria-label="Strategy vs buy-and-hold equity curve">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="#1f2f47" strokeWidth="1" />
            <text x={PAD.left - 8} y={y(t) + 4} fill="#7590b0" fontSize="11" textAnchor="end">
              {t.toFixed(1)}%
            </text>
          </g>
        ))}
        <line x1={PAD.left} x2={W - PAD.right} y1={y(0)} y2={y(0)} stroke="#3d5380" strokeWidth="1" strokeDasharray="4 4" />
        <path d={buyHold} fill="none" stroke="#8ea1bb" strokeWidth="1.6" />
        <path d={strategy} fill="none" stroke="#5b9dff" strokeWidth="2" />
        <text x={PAD.left} y={H - 6} fill="#7590b0" fontSize="11">{curve[0].date}</text>
        <text x={W - PAD.right} y={H - 6} fill="#7590b0" fontSize="11" textAnchor="end">{curve[curve.length - 1].date}</text>
      </svg>
      <div className="equity-legend">
        <span><i className="legend-dot" style={{ background: "#5b9dff" }} />Model strategy (long/flat)</span>
        <span><i className="legend-dot" style={{ background: "#8ea1bb" }} />Buy and hold</span>
      </div>
    </div>
  );
}
