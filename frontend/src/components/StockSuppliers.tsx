import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { validSupplier, validSupplierIntent, matchesSupplier, type Supplier, type SupplierIntent } from "../supplier-utils";
const base = (institute: string) => `/inventory/institutes/${encodeURIComponent(institute)}/suppliers`;
const message = (error: unknown) => error instanceof Error ? error.message : "Fournisseurs indisponibles";

export function StockSuppliers({ institute }: { institute: string }) {
  if (!institute || !["accueil", "responsable_institut"].includes(getOperatorRole() || "")) return null;
  return <Directory key={JSON.stringify([institute, getAccessToken()])} institute={institute} />;
}
function Directory({ institute }: { institute: string }) {
  const token = getAccessToken(), [rows, setRows] = useState<Supplier[]>(), [offset, page] = useState(0);
  const [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  const mounted = useRef(false), sequence = useRef(0);
  async function load() {
    const request = ++sequence.current, current = () => mounted.current && request === sequence.current && token === getAccessToken();
    setRows(undefined); setLoading(true); setError(undefined);
    try {
      const result = await apiGet<Supplier[]>(`${base(institute)}?limit=50&offset=${offset}`);
      if (!Array.isArray(result) || result.length > 50 || !result.every(row => validSupplier(row, institute)) || new Set(result.map(row => row.id)).size !== result.length || new Set(result.map(row => row.reference)).size !== result.length) throw new Error("Répertoire fournisseur à vérifier");
      if (!current()) return false; setRows(result); return true;
    } catch (error) { if (current()) setError(message(error)); return false; }
    finally { if (current()) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false; sequence.current++; }; }, [offset]);
  return <section className="bm-stock-detail bm-stock-suppliers" aria-label="Fournisseurs de l’institut">
    <h2>Fournisseurs</h2><p>Références enregistrées pour les commandes de cet institut. Ajouter un fournisseur ne crée aucun mouvement de stock.</p>
    <button type="button" disabled={loading} onClick={() => void load()}>Actualiser les fournisseurs</button>
    {loading && <p role="status">Lecture des fournisseurs…</p>}{error && <p role="alert">{error}</p>}
    {rows && <><ul>{rows.map(row => <li key={row.id}><strong>{row.name}</strong> · {row.reference}<p>{row.reason} · {row.actor_id}</p></li>)}</ul>{!rows.length && <p>Aucun fournisseur sur cette page.</p>}
      <div className="bm-stock-pages"><button disabled={loading || !offset} onClick={() => page(offset - 50)}>Fournisseurs précédents</button><button disabled={loading || rows.length < 50} onClick={() => page(offset + 50)}>Fournisseurs suivants</button></div></>}
    {getOperatorRole() === "responsable_institut" && <Create institute={institute} ready={!!rows && !loading} onRefresh={load} />}
  </section>;
}
function Create({ institute, ready, onRefresh }: { institute: string; ready: boolean; onRefresh: () => Promise<boolean> }) {
  const token = getAccessToken(), actor = getOperatorSubject(), key = `flowpilot.supplier-request:${JSON.stringify([institute, actor])}`;
  const [intent, freeze] = useState<SupplierIntent | undefined>(() => { try { const value = JSON.parse(sessionStorage.getItem(key) || "null"); return validSupplierIntent(value) ? value : undefined; } catch { return; } });
  const [reference, setReference] = useState(intent?.reference || ""), [name, setName] = useState(intent?.name || ""), [reason, setReason] = useState(intent?.reason || "");
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>(), [success, setSuccess] = useState<string>(), [rejected, reject] = useState(false);
  const mounted = useRef(false), pending = useRef(false), refresh = useRef(onRefresh); refresh.current = onRefresh;
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const current = () => mounted.current && token === getAccessToken();
  async function run(value: SupplierIntent) {
    if (pending.current || !ready || !actor) return;
    pending.current = true; setBusy(true); setError(undefined); setSuccess(undefined); reject(false);
    let postReturned = false;
    try {
      sessionStorage.setItem(key, JSON.stringify(value)); freeze(value);
      const reply = await apiPost<Supplier>(base(institute), value);
      postReturned = true;
      if (!current()) return;
      if (!validSupplier(reply, institute) || !matchesSupplier(reply, value, actor)) throw new Error("Fournisseur original à vérifier");
      const original = await apiGet<Supplier>(`${base(institute)}/${encodeURIComponent(reply.id)}`);
      if (!current()) return;
      if (!validSupplier(original, institute) || original.id !== reply.id || original.created_at !== reply.created_at || !matchesSupplier(original, value, actor)) throw new Error("Lecture originale du fournisseur à vérifier");
      if (!await refresh.current() || !current()) throw new Error("Actualisez les fournisseurs avant de poursuivre");
      sessionStorage.removeItem(key); freeze(undefined); setReference(""); setName(""); setReason(""); setSuccess(`Fournisseur enregistré : ${original.name}`);
    } catch (error) {
      if (current()) { setError(message(error)); reject(!postReturned && error instanceof ApiError && [400, 422].includes(error.status)); }
    } finally { pending.current = false; if (current()) setBusy(false); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (intent || busy) return;
    const value = { reference: reference.trim(), name: name.trim(), reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    if (!validSupplierIntent(value)) { setError("Référence, nom et motif valides requis"); return; }
    await run(value);
  }
  function correct() {
    try { sessionStorage.removeItem(key); freeze(undefined); reject(false); setError(undefined); }
    catch (error) { setError(message(error)); }
  }
  return <form className="bm-stock-form" aria-label="Ajouter un fournisseur" onSubmit={event => void submit(event)}>
    <h3>Ajouter un fournisseur</h3><fieldset disabled={busy || !!intent || !ready}>
      <label>Référence fournisseur<input required maxLength={80} pattern="[A-Za-z0-9][A-Za-z0-9._-]*" value={reference} onChange={event => setReference(event.target.value)} /></label>
      <label>Nom du fournisseur<input required maxLength={120} value={name} onChange={event => setName(event.target.value)} /></label>
      <label>Motif d’ajout du fournisseur<input required minLength={3} maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /></label>
      <button type="submit">Enregistrer le fournisseur</button>
    </fieldset>
    {intent && <><p>Demande conservée : {intent.name} · {intent.reference}. Reprenez cette demande pour vérifier son résultat original.</p><button type="button" disabled={busy || !ready} onClick={() => void run(intent)}>Reprendre le fournisseur conservé</button></>}
    {rejected && intent && <button type="button" disabled={busy} onClick={correct}>Corriger la demande refusée</button>}
    {error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
  </form>;
}
