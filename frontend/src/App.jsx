import { useEffect, useState } from "react";
import { api, clearToken, setToken } from "./lib/api";
import AuthScreen from "./components/AuthScreen";
import Dashboard from "./components/Dashboard";

export default function App() {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [symbol, setSymbol] = useState("DEMO");
  const [user, setUser] = useState(null);
  const [market, setMarket] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem("stocksense_token")) return;
    api("/auth/me").then(setUser).catch(() => clearToken());
  }, []);

  useEffect(() => {
    if (!user) return;

    api("/predictions?limit=10")
      .then(setHistory)
      .catch(() => setHistory([]));

    api("/stocks/" + symbol + "/history?limit=1")
      .then((result) => setMarket(result[0] || null))
      .catch(() => setMarket(null));
  }, [user, symbol]);

  async function submitAuth(event) {
    event.preventDefault();
    setBusy(true);
    setError("");

    try {
      if (mode === "register") {
        await api("/auth/register", {
          method: "POST",
          body: JSON.stringify({
            email,
            password,
            full_name: fullName || null,
          }),
        });
      }

      const result = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      setToken(result.access_token);
      setUser(await api("/auth/me"));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function runPrediction() {
    setBusy(true);
    setError("");

    try {
      const bars = await api("/stocks/" + symbol + "/history?limit=100");

      if (bars.length < 11) {
        throw new Error("Not enough market history is available for this symbol.");
      }

      setMarket(bars[bars.length - 1]);

      const result = await api("/predict", {
        method: "POST",
        body: JSON.stringify({
          symbol,
          history: bars.map((bar) => ({
            date: bar.date,
            close: bar.close,
            volume: bar.volume,
          })),
        }),
      });

      setPrediction(result);
      setHistory(await api("/predictions?limit=10"));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!user) {
    return (
      <AuthScreen
        mode={mode}
        email={email}
        password={password}
        fullName={fullName}
        busy={busy}
        error={error}
        setMode={setMode}
        setEmail={setEmail}
        setPassword={setPassword}
        setFullName={setFullName}
        onSubmit={submitAuth}
      />
    );
  }

  return (
    <Dashboard
      user={user}
      symbol={symbol}
      setSymbol={setSymbol}
      market={market}
      prediction={prediction}
      history={history}
      busy={busy}
      error={error}
      onPredict={runPrediction}
      onSignOut={() => {
        clearToken();
        setUser(null);
      }}
    />
  );
}
