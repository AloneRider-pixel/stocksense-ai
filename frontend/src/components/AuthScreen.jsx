import Brand from "./Brand";

export default function AuthScreen({
  mode,
  email,
  password,
  fullName,
  busy,
  error,
  setMode,
  setEmail,
  setPassword,
  setFullName,
  onSubmit,
}) {
  return (
    <main className="auth-shell">
      <section className="auth-card">
        <Brand />
        <p className="eyebrow">MARKET INTELLIGENCE PLATFORM</p>
        <h1>
          {mode === "login"
            ? "Market intelligence, built for decisions."
            : "Create your StockSense account."}
        </h1>

        <form onSubmit={onSubmit}>
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

          <button disabled={busy}>
            {busy ? "Working..." : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        {error && <div className="error">{error}</div>}

        <button
          className="switch-auth"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
          }}
        >
          {mode === "login" ? "Create an account" : "Back to sign in"}
        </button>
      </section>
    </main>
  );
}
