import { StockConsumptions } from "./StockConsumptions";
import { StockRecipes } from "./StockRecipes";
import type { Service } from "../types";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { stockCategories, stockUnits, stockQuantity, stockDisplay, stockMilli, validStockItem, validStockMovement, type StockItem, type StockMovement } from "../inventory-utils";

const prefix = (institute: string) => `/inventory/institutes/${encodeURIComponent(institute)}`;
const errorText = (error: unknown) => error instanceof Error ? error.message : "Inventaire indisponible";
export function InventoryPanel({ instituteId, timezone = "UTC", services = [] }: { instituteId: string; timezone?: string; services?: Service[] }) {
  if (!instituteId || !["accueil", "responsable_institut"].includes(getOperatorRole() || "")) return null;
  return <Catalogue key={JSON.stringify([instituteId, getAccessToken()])} institute={instituteId} timezone={timezone} services={services} />;
}
function Catalogue({ institute, timezone, services }: { institute: string; timezone: string; services: Service[] }) {
  const token = getAccessToken(), manager = getOperatorRole() === "responsable_institut";
  const [consumptionRevision, setConsumptionRevision] = useState(0);
  const [items, setItems] = useState<StockItem[]>(), [offset, setOffset] = useState(0), [selected, select] = useState<string>();
  const [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  const mounted = useRef(false), sequence = useRef(0);
  async function load() {
    const request = ++sequence.current;
    const current = () => mounted.current && request === sequence.current && token === getAccessToken();
    setItems(undefined); setLoading(true); setError(undefined);
    try {
      const rows = await apiGet<StockItem[]>(`${prefix(institute)}/items?limit=50&offset=${offset}`);
      if (!Array.isArray(rows) || rows.length > 50 || !rows.every(row => validStockItem(row, institute)) || new Set(rows.map(row => row.id)).size !== rows.length || new Set(rows.map(row => row.sku)).size !== rows.length) throw new Error("Lecture du stock incomplète");
      if (!current()) return false;
      setItems(rows); return true;
    } catch (error) { if (current()) setError(errorText(error)); return false; }
    finally { if (current()) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false; sequence.current++; }; }, [offset]);
  return <main className="bm-inventory" aria-label="Inventaire">
    <header><h2>Inventaire</h2><button type="button" onClick={() => void load()} disabled={loading}>Actualiser le stock</button></header>
    <p>Quantités enregistrées par article et unité. Les entrées et ajustements conservent leur historique.</p>
    {loading && <p role="status">Lecture du stock…</p>}{error && <p role="alert">{error}</p>}
    {items?.length === 0 && <p>{offset ? "Aucun article sur cette page." : "Aucun article enregistré."}</p>}
    {items && <><div className="bm-stock-grid">{items.map(item => <button type="button" key={item.id} className="bm-stock-card" onClick={() => select(item.id)} aria-pressed={item.id === selected}>
      <strong>{item.name}</strong><span>{item.sku} · {stockCategories[item.category]}</span>
      <span>{stockDisplay(item.on_hand)} {stockUnits[item.unit]}</span><span>Seuil : {stockDisplay(item.reorder_threshold)} {stockUnits[item.unit]}</span>
      {item.at_or_below_threshold && <em>Au seuil ou en dessous</em>}
    </button>)}</div><div className="bm-stock-pages"><button disabled={loading || offset === 0} onClick={() => setOffset(offset - 50)}>Articles précédents</button><button disabled={loading || items.length < 50} onClick={() => setOffset(offset + 50)}>Articles suivants</button></div></>}
    {manager && <StockWrite key="create" readReady={!!items && !loading} institute={institute} onRefresh={load} onCreated={select} />}
    <StockRecipes institute={institute} services={services} />
    <StockConsumptions institute={institute} timezone={timezone} onStockRefresh={async () => { setConsumptionRevision(value => value + 1); return await load(); }} />
    {selected && <ItemDetail key={JSON.stringify([selected, token])} institute={institute} id={selected} timezone={timezone} externalRevision={consumptionRevision} usable={!!items && !loading} onRefresh={load} />}
  </main>;
}
function ItemDetail({ institute, id, onRefresh, usable: parentUsable, timezone, externalRevision }: { institute: string; id: string; timezone: string; externalRevision: number; usable: boolean; onRefresh: () => Promise<boolean> }) {
  const token = getAccessToken(), manager = getOperatorRole() === "responsable_institut";
  const [resolvedRevision, setResolvedRevision] = useState(-1);
  const usable = parentUsable && resolvedRevision === externalRevision;
  const [identity, setIdentity] = useState<StockItem>();
  const [item, setItem] = useState<StockItem>(), [history, setHistory] = useState<StockMovement[]>(), [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  const mounted = useRef(false), sequence = useRef(0);
  async function load() {
    const request = ++sequence.current;
    const current = () => mounted.current && request === sequence.current && token === getAccessToken();
    setItem(undefined); setHistory(undefined); setLoading(true); setError(undefined);
    try {
      const path = `${prefix(institute)}/items/${encodeURIComponent(id)}`;
      const [row, rows] = await Promise.all([apiGet<StockItem>(path), apiGet<StockMovement[]>(`${path}/movements?limit=50&offset=${offset}`)]);
      if (!validStockItem(row, institute) || row.id !== id || !Array.isArray(rows) || rows.length > 50 || !rows.every(move => validStockMovement(move, row)) || new Set(rows.map(move => move.id)).size !== rows.length) throw new Error("Lecture de l'article incomplète");
      if (!current()) return false;
      setItem(row); setIdentity(row); setHistory(rows); setResolvedRevision(externalRevision); return true;
    } catch (error) { if (current()) setError(errorText(error)); return false; }
    finally { if (current()) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false; sequence.current++; }; }, [offset, externalRevision]);
  async function refresh() { return await onRefresh() && await load(); }
  let zone = timezone;
  try { new Intl.DateTimeFormat("fr-CH", { timeZone: zone }); } catch { zone = "UTC"; }
  return <section aria-label="Article de stock" className="bm-stock-detail">
    <header><h3>{item?.name || "Article de stock"}</h3><button onClick={() => void load()} disabled={loading}>Actualiser l'article</button></header>
    {loading && <p role="status">Lecture de l'article…</p>}{error && <p role="alert">{error}</p>}
    {usable && item && <p>Stock enregistré : {stockDisplay(item.on_hand)} {stockUnits[item.unit]} · Seuil : {stockDisplay(item.reorder_threshold)} {stockUnits[item.unit]}</p>}
    {manager && identity && <StockWrite institute={institute} item={identity} readReady={usable && !!item && !loading} onRefresh={refresh} />}
    {usable && item && <>
      <h4>Historique des mouvements</h4><p>Dates : {zone}</p>{history?.length === 0 && <p>Aucun mouvement sur cette page.</p>}
      <ol>{history?.map(move => <li key={move.id}><strong>{move.kind === "receipt" ? "Entrée" : move.kind === "consumption" ? "Consommation" : "Ajustement"} : {stockDisplay(move.quantity)} {stockUnits[move.unit]}</strong><span>{move.reason} · {move.actor_id} · {new Date(move.occurred_at).toLocaleString("fr-CH", { timeZone: zone })}</span></li>)}</ol>
      <div className="bm-stock-pages"><button disabled={loading || !offset} onClick={() => setOffset(offset - 50)}>Mouvements précédents</button><button disabled={loading || (history?.length || 0) < 50} onClick={() => setOffset(offset + 50)}>Mouvements suivants</button></div>
    </>}
  </section>;
}
type WriteIntent = { name?: string; sku?: string; category?: StockItem["category"]; unit?: StockItem["unit"]; reorder_threshold?: string; kind?: StockMovement["kind"]; quantity?: string; reason: string; idempotency_key: string };
function validIntent(row: WriteIntent, item?: StockItem) {
  if (!row || typeof row.reason !== "string" || row.reason.trim().length < 3 || row.reason.length > 240 || typeof row.idempotency_key !== "string" || !row.idempotency_key.trim() || row.idempotency_key.length > 120) return false;
  if (item) return Object.keys(row).sort().join() === "idempotency_key,kind,quantity,reason" && ["receipt", "adjustment"].includes(row.kind || "") && typeof row.quantity === "string" && stockQuantity(row.quantity, item.unit, true) === row.quantity && stockMilli(row.quantity) !== 0n && (row.kind !== "receipt" || stockMilli(row.quantity) > 0n);
  return Object.keys(row).sort().join() === "category,idempotency_key,name,reason,reorder_threshold,sku,unit" && typeof row.name === "string" && !!row.name.trim() && row.name.length <= 120 && typeof row.sku === "string" && /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(row.sku) && typeof row.category === "string" && Object.prototype.hasOwnProperty.call(stockCategories, row.category) && typeof row.unit === "string" && Object.prototype.hasOwnProperty.call(stockUnits, row.unit) && typeof row.reorder_threshold === "string" && stockQuantity(row.reorder_threshold, row.unit!) === row.reorder_threshold;
}
function StockWrite({ institute, item, onRefresh, onCreated, readReady = true }: { institute: string; item?: StockItem; readReady?: boolean; onRefresh: () => Promise<boolean>; onCreated?: (id: string) => void }) {
  const token = getAccessToken(), actor = getOperatorSubject();
  const storage = `flowpilot.stock-request:${JSON.stringify([institute, actor, item?.id || "create"])}`;
  const [intent, setIntent] = useState<WriteIntent | undefined>(() => { try { const row = JSON.parse(sessionStorage.getItem(storage) || "null"); return validIntent(row, item) ? row : undefined; } catch { return; } });
  const [name, setName] = useState(""), [sku, setSku] = useState(""), [category, setCategory] = useState<StockItem["category"]>("retail"), [unit, setUnit] = useState<StockItem["unit"]>("unit");
  const [quantity, setQuantity] = useState(""), [kind, setKind] = useState<StockMovement["kind"]>("receipt"), [threshold, setThreshold] = useState(""), [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>(), [message, setMessage] = useState<string>();
  const lifetime = useRef(0), pending = useRef(false), callbacks = useRef({ onRefresh, onCreated }); callbacks.current = { onRefresh, onCreated };
  useEffect(() => { lifetime.current++; return () => { lifetime.current++; }; }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!readReady || pending.current || !actor || getOperatorRole() !== "responsable_institut" || token !== getAccessToken()) return;
    const row = intent || (item ? { kind, quantity: stockQuantity(quantity, item.unit, true), reason: reason.trim(), idempotency_key: crypto.randomUUID() } : { name: name.trim(), sku: sku.trim(), category, unit, reorder_threshold: stockQuantity(threshold, unit), reason: reason.trim(), idempotency_key: crypto.randomUUID() }) as WriteIntent;
    if (!validIntent(row, item)) { setError("Vérifiez la référence, le motif et les quantités : trois décimales au maximum, unités entières pour les articles comptés."); return; }
    const generation = lifetime.current, current = () => generation === lifetime.current && token === getAccessToken();
    pending.current = true; setBusy(true); setError(undefined); setMessage(undefined); setIntent(row);
    try {
      sessionStorage.setItem(storage, JSON.stringify(row));
      let result: StockItem | StockMovement;
      try { result = await apiPost(`${prefix(institute)}/items${item ? `/${encodeURIComponent(item.id)}/movements` : ""}`, row); }
      catch (error) { if (current() && error instanceof ApiError && [400, 404, 422].includes(error.status)) { sessionStorage.removeItem(storage); setIntent(undefined); } throw error; }
      if (!current()) return;
      if (item ? !validStockMovement(result, item) || (result as StockMovement).kind !== row.kind || (result as StockMovement).quantity !== row.quantity || (result as StockMovement).reason !== row.reason || (result as StockMovement).idempotency_key !== row.idempotency_key || result.actor_id !== actor : !validStockItem(result, institute) || (result as StockItem).sku !== row.sku || (result as StockItem).name !== row.name || (result as StockItem).category !== row.category || (result as StockItem).unit !== row.unit || (result as StockItem).reorder_threshold !== row.reorder_threshold || result.actor_id !== actor) throw new Error("Résultat de la demande à vérifier");
      if (!await callbacks.current.onRefresh()) throw new Error("Actualisez le stock avant de poursuivre");
      if (!current()) return;
      sessionStorage.removeItem(storage); setIntent(undefined); setMessage(item ? "Mouvement enregistré." : "Article enregistré."); setQuantity(""); setReason("");
      if (!item) { setName(""); setSku(""); callbacks.current.onCreated?.(result.id); }
    } catch (error) { if (current()) setError(errorText(error)); }
    finally { if (current()) { pending.current = false; setBusy(false); } }
  }
  return <form className="bm-stock-form" aria-label={item ? "Enregistrer un mouvement" : "Créer un article"} onSubmit={event => void submit(event)}>
    <h3>{item ? "Entrée ou ajustement" : "Créer un article"}</h3>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {intent ? <p>Demande conservée : {item ? `${stockDisplay(intent.quantity!)} ${stockUnits[item.unit]}` : `${intent.sku} · ${intent.name}`} · {intent.reason}. Reprenez cette demande pour vérifier son enregistrement.</p> : <div className="bm-stock-fields">
      {!item && <><label>Référence<input value={sku} onChange={event => setSku(event.target.value)} maxLength={80} required /></label><label>Nom de l'article<input value={name} onChange={event => setName(event.target.value)} maxLength={120} required /></label>
        <label>Catégorie<select value={category} onChange={event => setCategory(event.target.value as StockItem["category"])}>{Object.entries(stockCategories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Unité<select value={unit} onChange={event => setUnit(event.target.value as StockItem["unit"])}>{Object.entries(stockUnits).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Seuil de réapprovisionnement<input inputMode="decimal" value={threshold} onChange={event => setThreshold(event.target.value)} required /></label></>}
      {item && <><label>Type de mouvement<select value={kind} onChange={event => setKind(event.target.value as StockMovement["kind"])}><option value="receipt">Entrée</option><option value="adjustment">Ajustement</option></select></label><label>Quantité ({stockUnits[item.unit]})<input inputMode="decimal" value={quantity} onChange={event => setQuantity(event.target.value)} required /></label><p>Un ajustement ajoute ou retire la quantité saisie ; une valeur négative retire du stock.</p></>}
      <label>Motif<input value={reason} onChange={event => setReason(event.target.value)} minLength={3} maxLength={240} required /></label>
    </div>}
    <button type="submit" disabled={busy || !actor || !readReady}>{intent ? "Reprendre la demande conservée" : item ? "Enregistrer le mouvement" : "Enregistrer l'article"}</button>
  </form>;
}
