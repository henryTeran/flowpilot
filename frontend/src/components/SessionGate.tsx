import { useState, type FormEvent } from "react";
import App from "../App";
import { apiPost } from "../api/client";
import { getAccessToken, setAccessToken } from "../api/session";

export function SessionGate() {
  const [authenticated, setAuthenticated] = useState(() => Boolean(getAccessToken()));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function login(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await apiPost<{ access_token: string; role: string }>("/auth/login", { email, password });
      if (!["accueil", "responsable_institut"].includes(result.role)) {
        throw new Error("Ce compte n’a pas accès aux opérations de l’institut.");
      }
      setAccessToken(result.access_token);
      setPassword("");
      setAuthenticated(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connexion impossible");
    } finally {
      setSubmitting(false);
    }
  }

  if (authenticated) return <>
    <App />
    <button className="flow-session-exit" onClick={() => { setAccessToken(null); setAuthenticated(false); }}>
      Déconnexion
    </button>
  </>;

  return <main className="flow-login-screen">
    <form className="flow-login-card" onSubmit={(event) => void login(event)}>
      <p className="eyebrow">FlowPilot</p>
      <h1>Ouvrir mon institut</h1>
      <p>Connectez-vous pour accéder à la file et au planning.</p>
      <label htmlFor="flow-email">Adresse e-mail</label>
      <input id="flow-email" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required />
      <label htmlFor="flow-password">Mot de passe</label>
      <input id="flow-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
      {error && <p role="alert">{error}</p>}
      <button className="primary-button" disabled={submitting}>{submitting ? "Connexion…" : "Se connecter"}</button>
    </form>
  </main>;
}
