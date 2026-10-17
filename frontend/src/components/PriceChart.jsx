import { useMemo, useState } from "react";

const W = 860;
const PAD = { top: 18, right: 16, bottom: 22, left: 74 };
const VOL_H = 40;
const PRICE_H = 240;
const SUB_H = 90;

function linePath(pts) {
  let d = "";
  let open = false;
  pts.forEach((p) => {
    if (!p) { open = false; return; }
    d += (open ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1) + " ";
    open = true;
  });
  return d;
}

export default function PriceChart({ bars, indicators, overlays, currency }) {
  const [hover, setHover] = useState(null);

  const showRsi = overlays?.rsi;
  const showMacd = overlays?.macd;
  const subCount = (showRsi ? 1 : 0) + (showMacd ? 1 : 0);
  const H = PAD.top + PRICE_H + 10 + VOL_H + (subCount * (SUB_H + 12)) + PAD.bottom;

  const geom = useMemo(() => {
    if (!bars || bars.length === 0) return null;
    let min = Infinity;
    let max = -Infinity;
    bars.forEach((b) => {
      if (b.low != null) min = Math.min(min, b.low);
      if (b.high != null) max = Math.max(max, b.high);
      if (b.low == null || b.high == null) {
        min = Math.min(min, b.close);
        max = Math.max(max, b.close);
      }
    });
    // Include active price overlays in the scale.
    if (indicators) {
      ["sma20", "sma50", "bb_upper", "bb_lower"].forEach((k) => {
        if (!overlays?.[k === "bb_upper" || k === "bb_lower" ? "bollinger" : k]) return;
        (indicators[k] || []).forEach((v) => {
          if (v != null) { min = Math.min(min, v); max = Math.max(max, v); }
        });
      });
    }
    const pad = (max - min || 1) * 0.06;
    min -= pad;
    max += pad;
    const iw = W - PAD.left - PAD.right;
    const x = (i) => PAD.left + (bars.length === 1 ? iw / 2 : (i / (bars.length - 1)) * iw);
    const y = (c) => PAD.top + (1 - (c - min) / (max - min || 1)) * PRICE_H;
    const volY = PAD.top + PRICE_H + 10;
    const vMax = Math.max(...bars.map((b) => b.volume || 0), 1);
    const tickIdx = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * (bars.length - 1)));
    const bw = Math.max(2, Math.min(12, iw / bars.length - 2));
    return { min, max, x, y, volY, vMax, tickIdx, bw, iw };
  }, [bars, indicators, overlays]);

  const subGeom = useMemo(() => {
    if (!bars || !bars.length) return null;
    let top = PAD.top + PRICE_H + 10 + VOL_H + 12;
    const panels = {};
    if (showRsi && indicators?.rsi14) {
      panels.rsi = { top, values: indicators.rsi14, min: 0, max: 100 };
      top += SUB_H + 12;
    }
    if (showMacd && indicators?.macd) {
      const all = [...(indicators.macd || []), ...(indicators.macd_signal || [])].filter((v) => v != null);
      const lo = Math.min(...all, 0);
      const hi = Math.max(...all, 0);
      panels.macd = { top, min: lo, max: hi };
      top += SUB_H + 12;
    }
    return panels;
  }, [bars, indicators, showRsi, showMacd]);

  if (!geom) return <div className="chart-empty">No price history loaded yet.</div>;

  const overlayLine = (key, color, width, dash) => {
    if (!indicators || !indicators[key]) return null;
    const pts = indicators[key].map((v, i) => (v == null ? null : [geom.x(i), geom.y(v)]));
    return <path key={key} d={linePath(pts)} fill="none" stroke={color} strokeWidth={width || 1.4} strokeDasharray={dash || "none"} opacity="0.9" />;
  };

  const subY = (panel, v) => panel.top + (1 - (v - panel.min) / (panel.max - panel.min || 1)) * SUB_H;

  function onMove(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    let best = 0;
    let bestDist = Infinity;
    bars.forEach((b, i) => {
      const d = Math.abs(geom.x(i) - px);
      if (d < bestDist) { bestDist = d; best = i; }
    });
    setHover(best);
  }

  const hb = hover != null ? bars[hover] : null;
  const cur = currency === "INR" ? "₹" : "$";

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} onMouseMove={onMove} onMouseLeave={() => setHover(null)} role="img" aria-label="Candlestick chart">
        {[0, 0.5, 1].map((f) => {
          const price = geom.max - f * (geom.max - geom.min);
          const y = geom.y(price);
          const locale = currency === "INR" ? "en-IN" : "en-US";
          const label = price >= 1000
            ? Math.round(price).toLocaleString(locale)
            : price.toFixed(2);
          return (
            <g key={f}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y} y2={y} stroke="#1a2840" strokeWidth="1" />
              <text x={PAD.left - 8} y={y + 4} textAnchor="end" className="axis-label">{label}</text>
            </g>
          );
        })}

        {overlays?.bollinger && indicators && (
          <>
            {overlayLine("bb_upper", "#8a6fd6", 1, "4 3")}
            {overlayLine("bb_mid", "#8a6fd6", 1, "2 3")}
            {overlayLine("bb_lower", "#8a6fd6", 1, "4 3")}
          </>
        )}
        {overlays?.sma20 && overlayLine("sma20", "#f0b35e", 1.5)}
        {overlays?.sma50 && overlayLine("sma50", "#4ec9b0", 1.5)}
        {overlays?.ema && (
          <>
            {overlayLine("ema12", "#e0628b", 1.2)}
            {overlayLine("ema26", "#62b5e0", 1.2)}
          </>
        )}

        {bars.map((b, i) => {
          const up = b.close >= b.open;
          const color = up ? "#2ebd85" : "#f6465d";
          const cx = geom.x(i);
          const bodyTop = geom.y(Math.max(b.open, b.close));
          const bodyBot = geom.y(Math.min(b.open, b.close));
          const vh = ((b.volume || 0) / geom.vMax) * VOL_H;
          return (
            <g key={b.date + i}>
              <rect x={cx - geom.bw / 2} y={geom.volY + (VOL_H - vh)} width={geom.bw} height={vh} fill={color} opacity="0.35" />
              <line x1={cx} x2={cx} y1={geom.y(b.high)} y2={geom.y(b.low)} stroke={color} strokeWidth="1.2" />
              <rect x={cx - geom.bw / 2} y={bodyTop} width={geom.bw} height={Math.max(1, bodyBot - bodyTop)} fill={color} />
            </g>
          );
        })}

        {subGeom?.rsi && (
          <g>
            <text x={PAD.left} y={subGeom.rsi.top + 11} className="axis-label panel-label">RSI 14</text>
            {[30, 70].map((lvl) => (
              <line key={lvl} x1={PAD.left} x2={W - PAD.right} y1={subY(subGeom.rsi, lvl)} y2={subY(subGeom.rsi, lvl)} stroke="#2a3b55" strokeWidth="1" strokeDasharray="3 3" />
            ))}
            <path d={linePath(subGeom.rsi.values.map((v, i) => (v == null ? null : [geom.x(i), subY(subGeom.rsi, v)])))} fill="none" stroke="#c792ea" strokeWidth="1.4" />
            <text x={PAD.left - 10} y={subY(subGeom.rsi, 70) + 3} textAnchor="end" className="axis-label">70</text>
            <text x={PAD.left - 10} y={subY(subGeom.rsi, 30) + 3} textAnchor="end" className="axis-label">30</text>
          </g>
        )}

        {subGeom?.macd && indicators && (
          <g>
            <text x={PAD.left} y={subGeom.macd.top + 11} className="axis-label panel-label">MACD 12 · 26 · 9</text>
            <line x1={PAD.left} x2={W - PAD.right} y1={subY(subGeom.macd, 0)} y2={subY(subGeom.macd, 0)} stroke="#2a3b55" strokeWidth="1" />
            {bars.map((b, i) => {
              const h = indicators.macd_hist?.[i];
              if (h == null) return null;
              const y0 = subY(subGeom.macd, 0);
              const y1 = subY(subGeom.macd, h);
              return <rect key={i} x={geom.x(i) - geom.bw / 2} y={Math.min(y0, y1)} width={geom.bw} height={Math.max(1, Math.abs(y1 - y0))} fill={h >= 0 ? "#2ebd85" : "#f6465d"} opacity="0.5" />;
            })}
            <path d={linePath((indicators.macd || []).map((v, i) => (v == null ? null : [geom.x(i), subY(subGeom.macd, v)])))} fill="none" stroke="#62b5e0" strokeWidth="1.3" />
            <path d={linePath((indicators.macd_signal || []).map((v, i) => (v == null ? null : [geom.x(i), subY(subGeom.macd, v)])))} fill="none" stroke="#f0b35e" strokeWidth="1.3" />
          </g>
        )}

        {geom.tickIdx.map((i) => (
          <text key={i} x={geom.x(i)} y={H - 6} textAnchor="middle" className="axis-label">
            {bars[i].date.slice(5)}
          </text>
        ))}

        {hover != null && (
          <line x1={geom.x(hover)} x2={geom.x(hover)} y1={PAD.top} y2={H - PAD.bottom} stroke="#3d5a80" strokeWidth="1" />
        )}
      </svg>

      {hb && (
        <div className="chart-tip">
          <strong>{hb.date}</strong>
          <span className={hb.close >= hb.open ? "positive" : "negative"}>
            {cur}O {hb.open?.toFixed(2)} · H {hb.high?.toFixed(2)} · L {hb.low?.toFixed(2)} · C {hb.close.toFixed(2)}
          </span>
          <span>Vol {(hb.volume || 0).toLocaleString("en-IN")}</span>
          {indicators && overlays?.rsi && indicators.rsi14?.[hover] != null && <span>RSI {indicators.rsi14[hover].toFixed(1)}</span>}
          {indicators && overlays?.macd && indicators.macd?.[hover] != null && <span>MACD {indicators.macd[hover].toFixed(2)}</span>}
        </div>
      )}
    </div>
  );
}
