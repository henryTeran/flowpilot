import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { getAccessToken } from "../api/session";
import type { Customer } from "../types";

export function CustomerPicker({ instituteId, selected, onSelect, clearLabel = "Passage anonyme" }: {
  instituteId: string; selected?: Pick<Customer, "id" | "display_name" | "phone">;
  onSelect: (customer?: Customer) => void; clearLabel?: string;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Customer[]>([]);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lifetime = useRef(0);
  const intent = useRef({ fingerprint: "", key: "" });
  useEffect(() => {
    lifetime.current++; setQuery(""); setName(""); setPhone(""); setBusy(false); setCreating(false);
    intent.current = { fingerprint: "", key: "" };
    return () => { lifetime.current++; };
  }, [instituteId]);
  useEffect(() => {
    let cancelled = false;
    setResults([]); setError(null);
    const token = getAccessToken();
    if (query.trim().length < 2 || !instituteId) return;
    const timer = window.setTimeout(() => {
      apiGet<Customer[]>(`/customers/institutes/${encodeURIComponent(instituteId)}?q=${encodeURIComponent(query.trim())}`)
        .then(value => { if (!cancelled && token === getAccessToken()) setResults(value); })
        .catch(reason => { if (!cancelled && token === getAccessToken()) setError(reason instanceof Error ? reason.message : "Recherche indisponible"); });
    }, 200);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [query, instituteId]);
  async function create() {
    if (busy || name.trim().length < 2) return;
    const stamp = lifetime.current;
    const token = getAccessToken();
    const payload = { display_name: name.trim(), phone: phone.trim() || null };
    const fingerprint = JSON.stringify({ instituteId, ...payload });
    if (intent.current.fingerprint !== fingerprint || !intent.current.key) {
      intent.current = { fingerprint, key: crypto.randomUUID() };
    }
    const current = () => lifetime.current === stamp && token === getAccessToken();
    setBusy(true); setError(null);
    try {
      const customer = await apiPost<Customer>(`/customers/institutes/${encodeURIComponent(instituteId)}`,
        { ...payload, idempotency_key: intent.current.key });
      if (!current()) return;
      intent.current = { fingerprint: "", key: "" };
      onSelect(customer); setCreating(false); setQuery("");
    } catch (reason) {
      if (current()) setError(reason instanceof Error ? reason.message : "Impossible d'enregistrer la cliente");
    } finally { if (current()) setBusy(false); }
  }
  return <div className="customer-picker">
    {selected && <p><strong>{selected.display_name}</strong> {selected.phone}
      <button type="button" onClick={() => onSelect(undefined)}>{clearLabel}</button></p>}
    <label>Rechercher une cliente
      <input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Nom ou téléphone" />
    </label>
    <div className="customer-search-results">
      {results.map(customer => <button type="button" key={customer.id} onClick={() => { onSelect(customer); setQuery(""); }}>
        <strong>{customer.display_name}</strong><span>{customer.phone}</span>
      </button>)}
    </div>
    {!creating && <button type="button" onClick={() => { setCreating(true); setName(query); }}>Nouvelle cliente</button>}
    {creating && <div>
      <label>Nom de la cliente<input value={name} maxLength={160} disabled={busy} onChange={event => setName(event.target.value)} /></label>
      <label>Téléphone (facultatif)<input type="tel" value={phone} maxLength={40} disabled={busy} onChange={event => setPhone(event.target.value)} /></label>
      <button type="button" disabled={busy || name.trim().length < 2} onClick={() => void create()}>{busy ? "Enregistrement..." : "Enregistrer la cliente"}</button>
      <button type="button" disabled={busy} onClick={() => setCreating(false)}>Annuler</button>
    </div>}
    {error && <p role="alert">{error}</p>}
  </div>;
}
