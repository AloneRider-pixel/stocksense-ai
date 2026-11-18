import { useEffect, useState } from "react";
import { api } from "../lib/api";

export default function DataHealth() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null);
    setError("");
    api("/data-health").then((value) => { if (active) setData(value); })
      .catch((e) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [attempt]);
  return <section className="data-health" aria-labelledby="data-health-title">
    <h2 id="data-health-title">Data health and sources</h2>
    <p>See what is stored, what is missing, and what has not been cleared for public use. Stored data is not a live-price guarantee.</p>
    {error && <div role="alert" className="market-error"><p>Data health could not be checked: {error}</p><button type="button" className="btn-outline" onClick={() => setAttempt((n) => n + 1)}>Retry data check</button></div>}
    {!data && !error && <p role="status">Checking stored data evidence…</p>}
    {data && <>
      <p><strong>Live quotes not verified.</strong> Trading-calendar freshness and cross-source price checks are not integrated. Do not treat a recent download as a recent market price.</p>
      <p>Checked: {data.checked_at}. Scope: stored rows only.</p>
      {!data.stored_sources.length && <p role="status">No market bars are stored. This is missing data, not a zero price.</p>}
      <div className="data-health-grid">{data.stored_sources.map((source) => <article key={source.provider} className="data-health-card">
        <h3>{source.provider || "Unknown provider"}</h3>
        <dl><dt>Stored records</dt><dd>{source.stored_rows}</dd><dt>Symbols represented</dt><dd>{source.symbols}</dd><dt>Latest stored session</dt><dd>{source.latest_session || "Unknown"}</dd><dt>Last stored ingestion timestamp</dt><dd>{source.last_ingested_at || "Unknown"}</dd><dt>Freshness</dt><dd>Not verified against a trading calendar</dd><dt>Public display</dt><dd>{source.public_display.replaceAll("_", " ")}</dd></dl>
        <p>{source.warning}</p>{source.policy_url && <a href={source.policy_url} target="_blank" rel="noreferrer">Read provider policy</a>}
      </article>)}</div>
      <h3>Collection and display limits</h3>
      <ul>{data.limitations.map((limit) => <li key={limit}>{limit}</li>)}</ul>
      <div className="data-health-grid">{data.source_policies.map((source) => <article className="data-health-card" key={source.id}>
        <h3>{source.id}</h3><p>Collection: {source.collection.replaceAll("_", " ")}</p><p>Public display: {source.public_display.replaceAll("_", " ")}</p>{source.note && <p>{source.note}</p>}
        {source.policy_url && <a href={source.policy_url} target="_blank" rel="noreferrer">Source policy</a>}
      </article>)}</div>
    </>}
  </section>;
}
