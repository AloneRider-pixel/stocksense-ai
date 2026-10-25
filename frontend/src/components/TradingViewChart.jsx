import { useEffect, useRef } from "react";

// Official TradingView Advanced Chart embed, attribution intact.
// Display-only: the widget must never be used as a scanner data source.
export default function TradingViewChart({ symbol = "BSE:SENSEX", height = 420 }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current) return;
    ref.current.innerHTML = "";
    const container = document.createElement("div");
    container.className = "tradingview-widget-container";
    container.style.height = "100%";
    const widget = document.createElement("div");
    widget.className = "tradingview-widget-container__widget";
    widget.style.height = "100%";
    container.appendChild(widget);
    const copyright = document.createElement("div");
    copyright.className = "tradingview-widget-copyright";
    copyright.innerHTML =
      '<a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank">' +
      '<span class="blue-text">Track all markets on TradingView</span></a>';
    container.appendChild(copyright);
    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol,
      interval: "D",
      timezone: "Asia/Kolkata",
      theme: "light",
      style: "1",
      locale: "en",
      allow_symbol_change: true,
      support_host: "https://www.tradingview.com",
    });
    container.appendChild(script);
    ref.current.appendChild(container);
  }, [symbol]);

  return <div ref={ref} style={{ height, width: "100%" }} />;
}
