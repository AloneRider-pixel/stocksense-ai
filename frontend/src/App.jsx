import { useEffect, useState } from "react";
import { api, clearToken, setToken } from "./lib/api";
import { DEMO_EMAIL, DEMO_PASSWORD, IS_DEMO } from "./config";
import Landing from "./components/Landing";
import AuthScreen from "./components/AuthScreen";
import Dashboard from "./components/Dashboard";

export default function App() {
  const [view, setView] = useState("landing");
  const [authMode, setAuthMode] = useState("login");
  const [user, setUser] = useState(null);
  const [authError, setAuthError] = useState("");
  const [demoError, setDemoError] = useState("");
  const [busy, setBusy] = useState(false);
  const [booting, setBooting] = useState(true);

  const [bootError, setBootError] = useState("");
  const [bootAttempt, setBootAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setBootError("");
    if (!localStorage.getItem("stocksense_token")) {
      setBooting(false);
      return () => { active = false; };
    }
    setBooting(true);
    const timer = setTimeout(() => {
      if (!active) return;
      setBootError("The server is taking too long to check your saved login. Your session has not been cleared. Retry, or continue to the sign-in page.");
      setBooting(false);
      controller.abort();
    }, 12000);
    api("/auth/me", { signal: controller.signal })
      .then((me) => {
        if (!active || controller.signal.aborted) return;
        setUser(me);
        setView("app");
      })
      .catch((error) => {
        if (!active || controller.signal.aborted) return;
        if (error.status === 401) {
          clearToken();
        } else {
          setBootError("We could not check your saved login. Your session has not been cleared. Retry, or continue to the sign-in page.");
        }
      })
      .finally(() => {
        clearTimeout(timer);
        if (active && !controller.signal.aborted) setBooting(false);
      });
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [bootAttempt]);

  async function login(email, password) {
    const result = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setToken(result.access_token);
    const me = await api("/auth/me");
    setUser(me);
    setView("app");
  }

  async function submitAuth({ mode, email, password, fullName }) {
    setBusy(true);
    setAuthError("");
    try {
      if (mode === "register") {
        await api("/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password, full_name: fullName || null }),
        });
      }
      await login(email, password);
    } catch (err) {
      setAuthError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function exploreDemo() {
    setBusy(true);
    setDemoError("");
    setAuthError("");
    try {
      await login(DEMO_EMAIL, DEMO_PASSWORD);
    } catch (err) {
      setDemoError("Demo sign-in failed: " + err.message);
    } finally {
      setBusy(false);
    }
  }

  function signOut() {
    clearToken();
    setUser(null);
    setView("landing");
  }

  if (booting) {
    return <div className="boot-screen">Loading StockSense AI…</div>;
  }

  if (bootError) {
    return (
      <main className="boot-screen">
        <section className="boot-recovery" aria-labelledby="boot-recovery-title">
          <h1 id="boot-recovery-title">We could not restore your session yet</h1>
          <p role="alert">{bootError}</p>
          <button className="btn-primary" type="button" onClick={() => setBootAttempt((attempt) => attempt + 1)}>Retry connection</button>
          <button className="btn-outline" type="button" onClick={() => {
            clearToken();
            setBootError("");
            setAuthMode("login");
            setView("auth");
          }}>Continue to sign in</button>
        </section>
      </main>
    );
  }

  if (view === "app" && user) {
    return (
      <>
        {IS_DEMO && (
          <div className="demo-banner">
            Market data: Twelve Data (US) and Yahoo Finance (NSE) daily bars, may be
            delayed. Research and engineering project. Not investment advice. Not a SEBI-registered research analyst or investment adviser. Past model performance does not indicate future results. Do not trade on this.
          </div>
        )}
        <Dashboard user={user} onSignOut={signOut} />
      </>
    );
  }

  if (view === "auth") {
    return (
      <AuthScreen
        initialMode={authMode}
        busy={busy}
        error={authError}
        onSubmit={submitAuth}
        onDemo={IS_DEMO ? exploreDemo : undefined}
        onBack={() => setView("landing")}
      />
    );
  }

  return (
    <Landing
      onSignIn={() => {
        setAuthMode("login");
        setAuthError("");
        setView("auth");
      }}
      onRegister={() => {
        setAuthMode("register");
        setAuthError("");
        setView("auth");
      }}
      onDemo={exploreDemo}
      demoBusy={busy}
      demoError={demoError}
    />
  );
                                  }
