import { useMemo, useState } from "react";

const W = 860;
const H = 320;
const PAD = { top: 18, right: 16, bottom: 30, left: 56 };
const VOL_H = 46;

export default function PriceChart({ bars }) {
  const [hover, setHover] = useState(null);

  const geom = useMemo(() => {
    if (!bars || bars.length === 0) return null;
    const closes = bars.map((b) => b.close);
    const vols = bars.map((b) => b.volume || 0);
    let min = Math.min(...closes);
    let max = Math.max(...closes);
    const pad = (max - min || 1) * 0.08;
    min -= pad;
    max += pad;
    const vMax = Math.max(...vols, 1);
    const iw = W - PAD.left - PAD.right;
    const chartH = H - PAD.top - PAD.bottom - VOL_H - 10;
    const x = (i) => PAD.left + (bars.length === 1 ? iw / 2 : (i / (bars.length - 1)) * iw);
    const y = (c) => PAD.top + (1 - (c - min) / (max - min || 1)) * chartH;
    const pts = bars.map((b, i) => [x(i), y(b.close)]);
    const line = pts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
    const area = line + ` L${x(bars.length - 1).toFixed(1)} ${(PAD.top + chartH).toFixed(1)} L${x(0).toFixed(1)} ${(PAD.top + chartH).toFixed(1)} Z`;
    const volY = PAD.top + chartH + 10;
    const tickIdx = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * (bars.length - 1)));
    return { min, max, x, y, pts, line, area, vols, vMax, volY, chartH, tickIdx };
  }, [bars]);

  if (!geom) return <div className="chart-empty">No price history loaded yet.</div>;

  function onMove(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    let best = 0;
    let bestDist = Infinity;
    geom.pts.forEach((p, i) => {
      const d = Math.abs(p[0] - px);
      if (d < bestDist) { bestDist = d; best = i; }
    });
    setHover(best);
  }

  const hb = hover != null ? bars[hover] : null;

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} onMouseMove={onMove} onMouseLeave={() => setHover(null)} role="img" aria-label="Price history chart">
        <defs>
          <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#5b9dff" stopOpacity="0.32" />
            <stop offset="100%" stopColor="#5b9dff" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {[0, 0.5, 1].map((f) => {
          const price = geom.max - f * (geom.max - geom.min);
          const y = geom.y(price);
          return (
            <g key={f}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y} y2={y} stroke="#1a2840" strokeWidth="1" />
              <text x={PAD.left - 10} y={y + 4} textAnchor="end" className="axis-label">{price.toFixed(2)}</text>
            </g>
          );
        })}

        {bars.map((b, i) => {
          const bw = Math.max(2, (W - PAD.left - PAD.right) / bars.length - 3);
          const vh = (geom.vols[i] / geom.vMax) * VOL_H;
          return (
            <rect key={b.date + i} x={geom.x(i) - bw / 2} y={geom.volY + (VOL_H - vh)} width={bw} height={vh} fill="#22334f" rx="1" />
          );
        })}

        <path d={geom.area} fill="url(#areaFill)" />
        <path d={geom.line} fill="none" stroke="#5b9dff" strokeWidth="2.2" strokeLinejoin="round" />

        {geom.tickIdx.map((i) => (
          <text key={i} x={geom.x(i)} y={H - 8} textAnchor="middle" className="axis-label">
            {bars[i].date.slice(5)}
          </text>
        ))}

        {hover != null && (
          <g>
            <line x1={geom.pts[hover][0]} x2={geom.pts[hover][0]} y1={PAD.top} y2={geom.volY + VOL_H} stroke="#3d5a80" strokeWidth="1" />
            <circle cx={geom.pts[hover][0]} cy={geom.pts[hover][1]} r="4.5" fill="#5b9dff" stroke="#0a0f1c" strokeWidth="2" />
          </g>
        )}
      </svg>

      {hb && (
        <div className="chart-tip">
          <strong>{hb.date}</strong>
          <span>Close ${hb.close.toFixed(2)}</span>
          <span>O {hb.open?.toFixed(2)} · H {hb.high?.toFixed(2)} · L {hb.low?.toFixed(2)}</span>
          <span>Vol {(hb.volume || 0).toLocaleString()}</span>
        </div>
      )}
    </div>
  );
}
