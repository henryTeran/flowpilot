import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { stockDisplay, stockQuantity, stockUnits, validStockItem, type StockItem } from "../inventory-utils";
import { validWork, validWorkDetail, validConsumption, validConsumptionIntent, matchesConsumption, normTerms, type Work, type WorkDetail, type Consumption, type ConsumptionIntent, type NamedEntry } from "../consumption-utils";
import { StockItemPicker } from "./StockItemPicker";
const base = (institute: string) => `/inventory/institutes/${encodeURIComponent(institute)}`;
const message = (error: unknown) => error instanceof Error ? error.message : "Consommation indisponible";
function saved(institute: string) {
  const actor = getOperatorSubject(), rows: Array<{ id: string; name: string }> = [];
  try { for (let index = 0; index < sessionStorage.length; index++) {
    const key = sessionStorage.key(index)!;
    if (!key.startsWith("flowpilot.consumption-request:")) continue;
    try {
      const scope = JSON.parse(key.slice("flowpilot.consumption-request:".length));
      const intent = JSON.parse(sessionStorage.getItem(key) || "null");
      if (Array.isArray(scope) && scope.length === 3 && scope[0] === institute && scope[2] === actor && typeof scope[1] === "string" && !!scope[1].trim() && scope[1] === scope[1].trim() && scope[1].length <= 80 && validConsumptionIntent(intent)) rows.push({ id: scope[1], name: intent.basis_name });
    } catch { continue; }
  } } catch { /* Unavailable storage cannot select a foreign request. */ }
  return rows;
}
export function StockConsumptions(props: { institute: string; timezone?: string; onStockRefresh: () => Promise<boolean> }) {
  if (!props.institute || !["accueil", "responsable_institut"].includes(getOperatorRole() || "")) return null;
  return <ConsumptionWork key={JSON.stringify([props.institute, getAccessToken()])} {...props} />;
}
function ConsumptionWork({ institute, timezone = "UTC", onStockRefresh }: { institute: string; timezone?: string; onStockRefresh: () => Promise<boolean> }) {
  const token = getAccessToken(), [rows, setRows] = useState<Work[]>(), [state, filter] = useState("pending"), [offset, setOffset] = useState(0), [selected, select] = useState<string>();
  const [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  const mounted = useRef(false), sequence = useRef(0);
  async function load() {
    const request = ++sequence.current, current = () => mounted.current && request === sequence.current && token === getAccessToken();
    setRows(undefined); setLoading(true); setError(undefined);
    try {
      const result = await apiGet<Work[]>(`${base(institute)}/consumption-work?state=${state}&limit=20&offset=${offset}`);
      if (!Array.isArray(result) || result.length > 20 || !result.every(row => validWork(row, institute) && row.source_status === "completed" && (state === "all" || (state === "pending" ? row.consumption_id === null : row.consumption_id !== null))) || new Set(result.map(row => row.basis_id)).size !== result.length) throw new Error("File des consommations à vérifier");
      if (!current()) return false; setRows(result); return true;
    } catch (error) { if (current()) setError(message(error)); return false; }
    finally { if (current()) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false; sequence.current++; }; }, [state, offset]);
  if (!institute || !["accueil", "responsable_institut"].includes(getOperatorRole() || "")) return null;
  const requests = saved(institute);
  let zone = timezone; try { new Intl.DateTimeFormat("fr-CH", { timeZone: zone }); } catch { zone = "UTC"; }
  return <section className="bm-stock-detail bm-stock-consumptions" aria-label="Consommations par prestation">
    <h2>Consommations par prestation</h2><p>Confirmez les quantités réellement utilisées après la fin de prestation. Les normes prévues ne débitent pas automatiquement le stock.</p>
    <p>Les prestations anciennes sans base capturée ne sont pas reconstituées à partir des recettes actuelles.</p>
    <label>Afficher les consommations<select value={state} onChange={event => { filter(event.target.value); setOffset(0); }}><option value="pending">À confirmer</option><option value="confirmed">Confirmées</option><option value="all">Toutes</option></select></label>
    <button type="button" disabled={loading} onClick={() => void load()}>Actualiser les consommations</button>
    {requests.map(row => <button type="button" key={row.id} onClick={() => select(row.id)}>Demande conservée : {row.name}</button>)}
    {loading && <p role="status">Lecture des consommations…</p>}{error && <p role="alert">{error}</p>}
    {rows && <><div className="bm-stock-grid">{rows.map(row => <button type="button" key={row.basis_id} aria-pressed={selected === row.basis_id} className="bm-stock-card" onClick={() => select(row.basis_id)}>
      <strong>{row.service_name}</strong><span>{row.source_kind === "sessions" ? "Séance" : "Rendez-vous"} {row.ticket_number || ""} · {row.employee_name}</span><span>{row.completed_at ? `Fin : ${new Date(row.completed_at).toLocaleString("fr-CH", { timeZone: zone })}` : "Date de fin non renseignée"}</span><span>{row.quantity} prestation(s) · {row.consumption_id ? "Confirmée" : "À confirmer"}</span>
    </button>)}</div>{!rows.length && <p>Aucune prestation sur cette page.</p>}<div className="bm-stock-pages"><button disabled={loading || !offset} onClick={() => setOffset(offset - 20)}>Consommations précédentes</button><button disabled={loading || rows.length < 20} onClick={() => setOffset(offset + 20)}>Consommations suivantes</button></div></>}
    {selected && <WorkView key={JSON.stringify([selected, token])} institute={institute} id={selected} usable={!!rows && !loading} timezone={timezone} onWorkRefresh={load} onStockRefresh={onStockRefresh} />}
  </section>;
}
async function labels(institute: string, detail: WorkDetail) {
  const entries = [...(detail.expected_entries || []), ...(detail.consumption?.entries || [])];
  const ids = [...new Set(entries.map(entry => entry.item_id))];
  return await Promise.all(ids.map(async id => {
    const row = await apiGet<StockItem>(`${base(institute)}/items/${encodeURIComponent(id)}`);
    if (!validStockItem(row, institute) || row.id !== id || entries.some(entry => entry.item_id === id && entry.unit !== row.unit)) throw new Error("Articles de la consommation à vérifier");
    return row;
  }));
}
type Facts = { detail: WorkDetail; items: StockItem[] };
function WorkView({ institute, id, usable, timezone, onWorkRefresh, onStockRefresh }: { institute: string; id: string; usable: boolean; timezone: string; onWorkRefresh: () => Promise<boolean>; onStockRefresh: () => Promise<boolean> }) {
  const token = getAccessToken(), [facts, setFacts] = useState<Facts>(), [basis, setBasis] = useState<Facts>();
  const [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  const mounted = useRef(false), sequence = useRef(0), originalBasis = useRef<WorkDetail | undefined>(undefined);
  async function load() {
    const request = ++sequence.current, current = () => mounted.current && request === sequence.current && token === getAccessToken();
    setFacts(undefined); setLoading(true); setError(undefined);
    try {
      const detail = await apiGet<WorkDetail>(`${base(institute)}/bases/${encodeURIComponent(id)}/work`);
      if (!validWorkDetail(detail, institute, id)) throw new Error("Base originale à vérifier");
      const old = originalBasis.current;
      if (old && (old.source_id !== detail.source_id || old.source_kind !== detail.source_kind || old.service_id !== detail.service_id || old.quantity !== detail.quantity || old.state !== detail.state || normTerms(old.expected_entries) !== normTerms(detail.expected_entries))) throw new Error("La base originale ne peut pas être remplacée");
      if (!current()) return false;
      const items = await labels(institute, detail);
      if (!current()) return false;
      originalBasis.current = detail; const value = { detail, items }; setFacts(value); setBasis(value); return true;
    } catch (error) { if (current()) setError(message(error)); return false; }
    finally { if (current()) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false; sequence.current++; }; }, []);
  async function refresh() {
    if (!await load() || !mounted.current || token !== getAccessToken()) return false;
    if (!await onWorkRefresh() || !mounted.current || token !== getAccessToken()) return false;
    return await onStockRefresh();
  }
  let zone = timezone; try { new Intl.DateTimeFormat("fr-CH", { timeZone: zone }); } catch { zone = "UTC"; }
  return <section aria-label="Détail de consommation" className="bm-stock-detail">
    <button type="button" disabled={loading} onClick={() => void load()}>Actualiser la prestation</button>
    {loading && <p role="status">Lecture de la prestation…</p>}{error && <p role="alert">{error}</p>}
    {usable && facts && <><h3>{facts.detail.service_name}</h3><p>Début enregistré : {new Date(facts.detail.captured_at).toLocaleString("fr-CH", { timeZone: zone })} · {zone} · {facts.detail.quantity} prestation(s)</p>
      <h4>Quantités prévues à l'origine</h4>{facts.detail.expected_entries === null ? <p>Aucune norme configurée au démarrage. Saisissez les quantités mesurées explicitement.</p> : !facts.detail.expected_entries.length ? <p>Recette explicitement désactivée au démarrage.</p> : <ul>{facts.detail.expected_entries.map(entry => <li key={entry.item_id}>{facts.items.find(item => item.id === entry.item_id)?.name} : {stockDisplay(entry.quantity)} {stockUnits[entry.unit]}</li>)}</ul>}
      {facts.detail.consumption && <section aria-label="Consommation originale"><h4>Consommation confirmée</h4><p>{facts.detail.consumption.matches_norm === null ? "Comparaison indisponible : norme non configurée." : facts.detail.consumption.matches_norm ? "Quantités conformes à la norme originale." : "Écart entre quantités prévues et réelles."}</p>
        {!facts.detail.consumption.entries.length && <p>Aucun article consommé, confirmation explicite.</p>}<ul>{facts.detail.consumption.entries.map(entry => <li key={entry.item_id}>{facts.items.find(item => item.id === entry.item_id)?.name} : {stockDisplay(entry.quantity)} {stockUnits[entry.unit]}</li>)}</ul><p>{facts.detail.consumption.reason} · {facts.detail.consumption.actor_id}</p></section>}
    </>}
    {getOperatorRole() === "responsable_institut" && basis && <ConsumptionEditor institute={institute} basis={basis} ready={usable && !!facts && !loading} onRefresh={refresh} />}
  </section>;
}
function ConsumptionEditor({ institute, basis, ready, onRefresh }: { institute: string; basis: Facts; ready: boolean; onRefresh: () => Promise<boolean> }) {
  const token = getAccessToken(), actor = getOperatorSubject(), id = basis.detail.basis_id;
  const key = `flowpilot.consumption-request:${JSON.stringify([institute, id, actor])}`;
  const [intent, setIntent] = useState<ConsumptionIntent | undefined>(() => { try { const row = JSON.parse(sessionStorage.getItem(key) || "null"); return validConsumptionIntent(row) ? row : undefined; } catch { return; } });
  const [entries, setEntries] = useState<NamedEntry[]>([]), [none, setNone] = useState(false), [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>(), [success, setSuccess] = useState<string>();
  const lifetime = useRef(0), pending = useRef(false), refresh = useRef(onRefresh); refresh.current = onRefresh;
  useEffect(() => { lifetime.current++; return () => { lifetime.current++; }; }, []);
  function useNorm() {
    const planned = basis.detail.expected_entries;
    if (!planned?.length || !planned.every(entry => stockQuantity(entry.quantity, entry.unit) === entry.quantity)) { setError("La norme dépasse la quantite saisissable; indiquez les quantités réelles."); return; }
    setEntries(planned.map(entry => ({ ...entry, name: basis.items.find(item => item.id === entry.item_id)!.name, sku: basis.items.find(item => item.id === entry.item_id)!.sku }))); setNone(false); setError(undefined);
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!ready || pending.current || !actor || token !== getAccessToken() || getOperatorRole() !== "responsable_institut" || (!intent && (basis.detail.consumption || basis.detail.source_status !== "completed"))) return;
    const row = intent || { basis_name: basis.detail.service_name, basis_state: basis.detail.state, expected_entries: basis.detail.expected_entries,
      no_material: none, entries: none ? [] : entries.map(entry => ({ ...entry, quantity: stockQuantity(entry.quantity, entry.unit)! })), reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    if (!validConsumptionIntent(row) || row.basis_state !== basis.detail.state || normTerms(row.expected_entries) !== normTerms(basis.detail.expected_entries)) { setError("Saisissez les quantités positives ou confirmez explicitement aucun article, avec un motif."); return; }
    const stamp = lifetime.current, current = () => stamp === lifetime.current && token === getAccessToken();
    pending.current = true; setBusy(true); setIntent(row); setError(undefined); setSuccess(undefined);
    try {
      sessionStorage.setItem(key, JSON.stringify(row));
      let result: Consumption;
      try { result = await apiPost(`${base(institute)}/bases/${encodeURIComponent(id)}/consumption`, { entries: row.entries.map(entry => ({ item_id: entry.item_id, quantity: entry.quantity })), reason: row.reason, idempotency_key: row.idempotency_key }); }
      catch (error) { if (current() && error instanceof ApiError && [400, 404, 422].includes(error.status)) { sessionStorage.removeItem(key); setIntent(undefined); } throw error; }
      if (!current()) return;
      if (!validConsumption(result, institute, id) || !matchesConsumption(result, row, actor)) throw new Error("Résultat de la consommation à vérifier");
      const original = await apiGet<Consumption>(`${base(institute)}/consumptions/${encodeURIComponent(result.id)}`);
      if (!current()) return;
      if (!validConsumption(original, institute, id) || original.id !== result.id || !matchesConsumption(original, row, actor)) throw new Error("Confirmation originale à vérifier");
      if (!await refresh.current()) throw new Error("Actualisez la prestation, la file et le stock avant de poursuivre");
      if (!current()) return;
      sessionStorage.removeItem(key); setIntent(undefined); setSuccess("Consommation enregistrée.");
    } catch (error) { if (current()) setError(message(error)); }
    finally { if (current()) { pending.current = false; setBusy(false); } }
  }
  if (!intent && basis.detail.consumption) return success ? <p role="status">{success}</p> : null;
  return <form aria-label="Confirmer la consommation" className="bm-stock-form bm-recipe-form" onSubmit={event => void submit(event)}>
    <h4>Quantités réellement utilisées</h4>{error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
    {intent ? <><p>Demande conservée : {intent.reason}</p><ul>{intent.entries.map(entry => <li key={entry.item_id}>{entry.name} : {stockDisplay(entry.quantity)} {stockUnits[entry.unit]}</li>)}</ul>{intent.no_material && <p>Aucun article consommé, déclaration conservée.</p>}</> : <>
      {basis.detail.expected_entries?.length ? <button type="button" className="bm-recipe-reset" disabled={!ready || busy} onClick={useNorm}>Utiliser les quantités prévues</button> : null}
      <p>Vérifiez les quantités mesurées. Aucune valeur n'est confirmée automatiquement.</p>
      <label className="bm-recipe-toggle"><input type="checkbox" checked={none} disabled={!ready || busy} onChange={event => setNone(event.target.checked)} /> Aucun article consommé</label>
      {!none && <><StockItemPicker institute={institute} action="consommation" disabled={!ready || busy || entries.length >= 50} selected={entries.map(entry => entry.item_id)} onAdd={item => setEntries([...entries, { item_id: item.id, name: item.name, sku: item.sku, unit: item.unit, quantity: "" }])} />
        <div className="bm-stock-fields">{entries.map(entry => <div key={entry.item_id}><label>Quantité réelle pour {entry.name} ({stockUnits[entry.unit]})<input inputMode="decimal" required value={entry.quantity} disabled={!ready || busy} onChange={event => setEntries(entries.map(row => row.item_id === entry.item_id ? { ...row, quantity: event.target.value } : row))} /></label><button type="button" disabled={!ready || busy} onClick={() => setEntries(entries.filter(row => row.item_id !== entry.item_id))}>Retirer {entry.name}</button></div>)}</div></>}
      <label>Motif de la consommation<input required minLength={3} maxLength={240} value={reason} disabled={!ready || busy} onChange={event => setReason(event.target.value)} /></label>
    </>}
    <button type="submit" disabled={!ready || busy || !actor || (!intent && basis.detail.source_status !== "completed")}>{intent ? "Reprendre la consommation conservée" : "Confirmer les quantités réelles"}</button>
  </form>;
}
