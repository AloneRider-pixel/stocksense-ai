import { useState } from "react";
import Brand from "./Brand";
import { IS_DEMO } from "../config";

export default function AuthScreen({ initialMode, busy, error, onSubmit, onDemo, onBack }) {
  const [mode, setMode] = useState(initialMode || "login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");

  function submit(event) {
    event.preventDefault();
    onSubmit({ mode, email, password, fullName });
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <Brand />
        <p className="eyebrow">MARKET INTELLIGENCE PLATFORM</p>
        <h1>
          {mode === "login"
            ? "Welcome back."
            : "Create your StockSense account."}
        </h1>

        <form onSubmit={submit} aria-busy={busy}>
          {mode === "register" && (
            <>
              <label htmlFor="auth-name">Full name</label>
              <input
                id="auth-name"
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                maxLength={120}
              />
            </>
          )}

          <label htmlFor="auth-email">Email</label>
          <input
            id="auth-email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            required
          />

          <label htmlFor="auth-password">Password</label>
          <input
            id="auth-password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            minLength={8}
            required
          />

          <button className="btn-primary" disabled={busy}>
            {busy ? "Working..." : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        {busy && <p className="muted" role="status">Connecting to the server. A cold start can take several minutes. Your form stays here if the request times out; retry only when you are ready.</p>}
        {error && <div className="error" role="alert">{error}</div>}

        <button
          className="switch-auth"
          disabled={busy}
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "Create an account" : "Back to sign in"}
        </button>

        {IS_DEMO && mode === "login" && (
          <button className="switch-auth" onClick={onDemo} disabled={busy}>
            Just looking? Explore the dashboard
          </button>
        )}

        <button className="switch-auth" onClick={onBack}>
          Back to the home page
        </button>
      </section>
    </main>
  );
}
