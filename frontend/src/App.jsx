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

  useEffect(() => {
    if (!localStorage.getItem("stocksense_token")) {
      setBooting(false);
      return;
    }
    api("/auth/me")
      .then((me) => {
        setUser(me);
        setView("app");
      })
      .catch(() => clearToken())
      .finally(() => setBooting(false));
  }, []);

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

  if (view === "app" && user) {
    return (
      <>
        {IS_DEMO && (
          <div className="demo-banner">
            Public demo on free-tier hosting. Market data: Twelve Data (US) and Yahoo Finance (NSE) daily bars, may be
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
