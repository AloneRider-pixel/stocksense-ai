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

        <form onSubmit={submit}>
          {mode === "register" && (
            <>
              <label>Full name</label>
              <input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                maxLength={120}
              />
            </>
          )}

          <label>Email</label>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            required
          />

          <label>Password</label>
          <input
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

        {error && <div className="error">{error}</div>}

        <button
          className="switch-auth"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "Create an account" : "Back to sign in"}
        </button>

        {IS_DEMO && mode === "login" && (
          <button className="switch-auth" onClick={onDemo} disabled={busy}>
            Just looking? Explore the demo account
          </button>
        )}

        <button className="switch-auth" onClick={onBack}>
          Back to the home page
        </button>
      </section>
    </main>
  );
}
