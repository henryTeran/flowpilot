import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { StockItemPicker } from "./StockItemPicker";
import { validSupplier, type Supplier } from "../supplier-utils";
import { stockQuantity, stockMilli, stockDisplay, stockUnits, type StockItem } from "../inventory-utils";
import { validOrder, validProgress, validReceipt, validPurchaseIntent, orderSignature, type Order, type OrderEntry, type Receipt, type Progress } from "../order-utils";
import { usePurchaseWrite } from "./purchase-write";
import type { PurchaseSaved } from "./purchase-write";
const base = (institute: string) => `/inventory/institutes/${encodeURIComponent(institute)}`;
const message = (error: unknown) => error instanceof Error ? error.message : "Commandes indisponibles";
const captions = { pending: "À recevoir", partial: "Réception partielle", received: "Entièrement reçue" };
export function StockOrders(props: { institute: string; timezone?: string; onStockRefresh: () => Promise<boolean>; onStockInvalidate: () => void }) {
  if (!props.institute || !["accueil", "responsable_institut"].includes(getOperatorRole() || "")) return null;
  return <Orders key={JSON.stringify([props.institute, getAccessToken()])} {...props} />;
}
function Orders({ institute, timezone = "UTC", onStockRefresh, onStockInvalidate }: { institute: string; timezone?: string; onStockRefresh: () => Promise<boolean>; onStockInvalidate: () => void }) {
  const token = getAccessToken(), [rows, setRows] = useState<Order[]>(), [offset, page] = useState(0), [selected, select] = useState<string>();
  const [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  const mounted = useRef(false), sequence = useRef(0);
  const [recoveries, setRecoveries] = useState<Order[]>([]);
  function readRecoveries() {
    const found: Order[] = [];
    try { for (let index = 0; index < sessionStorage.length; index++) {
      const key = sessionStorage.key(index)!;
      if (!key.startsWith("flowpilot.purchase-request:")) continue;
      try {
      const scope = JSON.parse(key.slice("flowpilot.purchase-request:".length));
      if (!Array.isArray(scope) || scope.length !== 4 || scope[0] !== institute || scope[1] !== getOperatorSubject() || scope[2] !== "receipt") continue;
      const saved = JSON.parse(sessionStorage.getItem(key)!) as PurchaseSaved;
      if (validOrder(saved?.order, institute) && saved.order.id === scope[3] && !found.some(row => row.id === saved.order!.id)) found.push(saved.order);
      } catch { /* One unreadable entry must not hide other recoverable deliveries. */ }
    } } catch { /* The write editor keeps unreadable requests blocked. */ }
    setRecoveries(found);
  }
  async function load() {
    const request = ++sequence.current, current = () => mounted.current && request === sequence.current && token === getAccessToken();
    setRows(undefined); setLoading(true); setError(undefined);
    try {
      const result = await apiGet<Order[]>(`${base(institute)}/orders?limit=20&offset=${offset}`);
      if (!Array.isArray(result) || result.length > 20 || !result.every(row => validOrder(row, institute)) || new Set(result.map(row => row.id)).size !== result.length) throw new Error("Commandes originales à vérifier");
      if (!current()) return false; setRows(result); readRecoveries(); return true;
    } catch (error) { if (current()) setError(message(error)); return false; }
    finally { if (current()) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false; sequence.current++; }; }, [offset]);
  return <section className="bm-stock-detail bm-stock-orders" aria-label="Commandes de l’institut"><h2>Commandes et réceptions</h2><p>Une commande ne modifie pas le stock. Confirmez uniquement les quantités physiquement reçues.</p>
    <button type="button" disabled={loading} onClick={() => void load()}>Actualiser les commandes</button>
    {loading && <p role="status">Lecture des commandes…</p>}{error && <p role="alert">{error}</p>}
    {!!recoveries.length && <div aria-label="Réceptions à reprendre"><h3>Réceptions conservées</h3>{recoveries.map(row => <button type="button" key={row.id} onClick={() => select(row.id)}>Reprendre la réception de {row.reference}</button>)}</div>}
    {rows && <><div className="bm-stock-grid">{rows.map(row => <button type="button" className="bm-stock-card" key={row.id} aria-pressed={selected === row.id} onClick={() => select(row.id)}><strong>{row.reference}</strong><span>{row.supplier_name} · {row.supplier_reference}</span></button>)}</div>{!rows.length && <p>Aucune commande sur cette page.</p>}<div className="bm-stock-pages"><button disabled={loading || !offset} onClick={() => page(offset - 20)}>Commandes précédentes</button><button disabled={loading || rows.length < 20} onClick={() => page(offset + 20)}>Commandes suivantes</button></div></>}
    {getOperatorRole() === "responsable_institut" && <CreateOrder institute={institute} ready={!!rows && !loading} refresh={load} select={select} />}
    {selected && <OrderDetail key={JSON.stringify([selected, token])} institute={institute} id={selected} timezone={timezone} usable={!!rows && !loading} refreshList={load} onStockRefresh={onStockRefresh} onStockInvalidate={onStockInvalidate} onRecovered={() => setRecoveries(rows => rows.filter(row => row.id !== selected))} />}
  </section>;
}
function SupplierPicker({ institute, disabled, onChoose }: { institute: string; disabled: boolean; onChoose: (row: Supplier) => void }) {
  const token = getAccessToken(), [rows, setRows] = useState<Supplier[]>(), [offset, page] = useState(0), [reload, refresh] = useState(0), [error, setError] = useState<string>();
  useEffect(() => { let active = true; setRows(undefined); setError(undefined); void apiGet<Supplier[]>(`${base(institute)}/suppliers?limit=50&offset=${offset}`).then(result => {
    if (!Array.isArray(result) || result.length > 50 || !result.every(row => validSupplier(row, institute)) || new Set(result.map(row => row.id)).size !== result.length) throw new Error("Fournisseurs à vérifier");
    if (active && token === getAccessToken()) setRows(result);
  }).catch(error => { if (active && token === getAccessToken()) setError(message(error)); }); return () => { active = false; }; }, [offset, reload]);
  return <div><label>Choisir le fournisseur<select disabled={disabled || !rows} defaultValue="" onChange={event => { const row = rows?.find(row => row.id === event.target.value); if (row) onChoose(row); }}><option value="">Choisir un fournisseur</option>{rows?.map(row => <option key={row.id} value={row.id}>{row.name} · {row.reference}</option>)}</select></label>{error && <p role="alert">{error}</p>}<div className="bm-stock-pages"><button type="button" disabled={disabled} onClick={() => refresh(reload + 1)}>Actualiser les fournisseurs de commande</button><button type="button" disabled={disabled || !rows || !offset} onClick={() => page(offset - 50)}>Fournisseurs de commande précédents</button><button type="button" disabled={disabled || rows?.length !== 50} onClick={() => page(offset + 50)}>Fournisseurs de commande suivants</button></div></div>;
}
function WriteStatus({ write }: { write: ReturnType<typeof usePurchaseWrite> }) {
  return <>{write.saved && <><p>Demande conservée : {write.saved.label}{write.saved.supplier_name && ` · ${write.saved.supplier_name}`}</p><ul>{write.saved.entries.map(row => <li key={row.item_id}>{row.item_name} · {row.item_sku} : {stockDisplay(row.quantity)} {stockUnits[row.unit]}</li>)}</ul><p>Motif conservé : {write.saved.payload.reason}</p><button type="button" disabled={write.busy || !write.ready} onClick={() => void write.run(write.saved!)}>Reprendre la demande originale</button></>}{write.rejected && <button type="button" disabled={write.busy} onClick={write.correct}>Corriger la demande refusée</button>}{write.error && <p role="alert">{write.error}</p>}{write.success && <p role="status">{write.success}</p>}</>;
}
function CreateOrder({ institute, ready, refresh, select }: { institute: string; ready: boolean; refresh: () => Promise<boolean>; select: (id: string) => void }) {
  const write = usePurchaseWrite(institute, "order", undefined, ready, refresh, () => {}, select);
  const [supplier, choose] = useState<Supplier>(), [reference, setReference] = useState(""), [reason, setReason] = useState("");
  const [entries, setEntries] = useState<Array<OrderEntry & { input: string }>>([]), [error, setError] = useState<string>();
  const blocked = !ready || write.busy || !!write.saved || write.blocked;
  function add(item: StockItem) { setEntries(rows => rows.length < 50 && !rows.some(row => row.item_id === item.id) ? [...rows, { item_id: item.id, item_name: item.name, item_sku: item.sku, unit: item.unit, quantity: "0.000", input: "" }] : rows); }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (blocked || !supplier) return;
    const named = entries.map(row => ({ item_id: row.item_id, item_name: row.item_name, item_sku: row.item_sku, unit: row.unit, quantity: stockQuantity(row.input, row.unit) || "0.000" }));
    const payload = { supplier_id: supplier.id, reference: reference.trim(), entries: named.map(({ item_name, item_sku, ...row }) => row), reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    if (!validPurchaseIntent(payload, "order")) { setError("Fournisseur, référence, motif et quantités positives requis"); return; }
    setError(undefined);
    if (await write.run({ payload, label: payload.reference, entries: named, supplier_name: supplier.name, supplier_reference: supplier.reference })) { setEntries([]); setReference(""); setReason(""); }
  }
  return <form className="bm-stock-form" aria-label="Créer une commande" onSubmit={event => void submit(event)}><h3>Créer une commande</h3><fieldset disabled={blocked}><SupplierPicker institute={institute} disabled={blocked} onChoose={choose} />{supplier && <p>Fournisseur sélectionné : {supplier.name} · {supplier.reference}</p>}<label>Référence de commande<input required maxLength={80} value={reference} onChange={event => setReference(event.target.value)} /></label><StockItemPicker institute={institute} disabled={blocked || entries.length >= 50} selected={entries.map(row => row.item_id)} onAdd={add} action="commande" />
    {entries.map(row => <div key={row.item_id}><label>Quantité commandée pour {row.item_name} ({stockUnits[row.unit]})<input inputMode="decimal" required value={row.input} onChange={event => setEntries(rows => rows.map(item => item.item_id === row.item_id ? { ...item, input: event.target.value } : item))} /></label><button type="button" onClick={() => setEntries(rows => rows.filter(item => item.item_id !== row.item_id))}>Retirer {row.item_name}</button></div>)}<label>Motif de commande<input required minLength={3} maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /></label><button type="submit" disabled={!supplier || !entries.length}>Enregistrer la commande</button></fieldset>{error && <p role="alert">{error}</p>}<WriteStatus write={write} /></form>;
}
type DetailFacts = { order: Order; progress: Progress; receipts: Receipt[] };
function OrderDetail({ institute, id, timezone, usable, refreshList, onStockRefresh, onStockInvalidate, onRecovered }: { institute: string; id: string; timezone: string; usable: boolean; refreshList: () => Promise<boolean>; onStockRefresh: () => Promise<boolean>; onStockInvalidate: () => void; onRecovered: () => void }) {
  const token = getAccessToken(), [facts, setFacts] = useState<DetailFacts>(), [original, setOriginal] = useState<Order>(), [offset, page] = useState(0), [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  const mounted = useRef(false), sequence = useRef(0), pinned = useRef<string | undefined>(undefined);
  async function load(minimum?: Receipt) {
    const request = ++sequence.current, current = () => mounted.current && request === sequence.current && token === getAccessToken();
    setFacts(undefined); setLoading(true); setError(undefined);
    try {
      const path = `${base(institute)}/orders/${encodeURIComponent(id)}`;
      const order = await apiGet<Order>(path);
      if (!validOrder(order, institute) || order.id !== id || (pinned.current && pinned.current !== orderSignature(order))) throw new Error("Commande originale à vérifier");
      const [progress, receipts] = await Promise.all([apiGet<Progress>(`${path}/progress`), apiGet<Receipt[]>(`${path}/receipts?limit=50&offset=${offset}`)]);
      if (!validProgress(progress, order) || !Array.isArray(receipts) || receipts.length > 50 || !receipts.every(row => validReceipt(row, order)) || new Set(receipts.map(row => row.id)).size !== receipts.length) throw new Error("Réceptions et reste à recevoir à vérifier");
      if (minimum && (!validReceipt(minimum, order) || minimum.entries.some(entry => stockMilli(entry.quantity) > stockMilli(progress.entries.find(row => row.item_id === entry.item_id)!.received)))) throw new Error("Réception originale absente de la progression");
      for (const entry of progress.entries) { const total = receipts.flatMap(row => row.entries).filter(row => row.item_id === entry.item_id).reduce((sum, row) => sum + stockMilli(row.quantity), 0n); if (total > stockMilli(entry.received)) throw new Error("Historique et progression à vérifier"); }
      if (!current()) return false;
      pinned.current = orderSignature(order); setOriginal(order); setFacts({ order, progress, receipts }); return true;
    } catch (error) { if (current()) setError(message(error)); return false; }
    finally { if (current()) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false; sequence.current++; }; }, [offset]);
  async function refresh(original: Order | Receipt) { if (!await load("order_id" in original ? original : undefined) || !mounted.current || token !== getAccessToken()) return false; if (!await refreshList() || !mounted.current || token !== getAccessToken()) return false; return await onStockRefresh(); }
  let zone = timezone;
  try { new Intl.DateTimeFormat("fr-CH", { timeZone: zone }); } catch { zone = "UTC"; }
  const stamp = (instant: string) => new Date(instant).toLocaleString("fr-CH", { timeZone: zone });
  return <section className="bm-stock-detail" aria-label="Détail de commande"><button type="button" disabled={loading} onClick={() => void load()}>Actualiser la commande sélectionnée</button>{loading && <p role="status">Lecture de la commande…</p>}{error && <p role="alert">{error}</p>}
    {usable && facts && <><h3>{facts.order.reference} · {facts.order.supplier_name}</h3><p>{facts.order.reason} · {facts.order.actor_id} · {stamp(facts.order.created_at)}</p><p>Dates : {zone}</p><p>{captions[facts.progress.state]}</p><table><thead><tr><th>Article</th><th>Commandé</th><th>Reçu</th><th>Reste à recevoir</th></tr></thead><tbody>{facts.progress.entries.map(row => <tr key={row.item_id}><th>{row.item_name} · {row.item_sku}</th><td>{stockDisplay(row.quantity)} {stockUnits[row.unit]}</td><td>{stockDisplay(row.received)} {stockUnits[row.unit]}</td><td>{stockDisplay(row.remaining)} {stockUnits[row.unit]}</td></tr>)}</tbody></table><h4>Réceptions enregistrées</h4>{!facts.receipts.length && <p>Aucune réception sur cette page.</p>}{facts.receipts.map(row => <article key={row.id}><p>{row.reason} · {row.actor_id} · {stamp(row.occurred_at)}</p><ul>{row.entries.map(entry => <li key={entry.item_id}>{facts.order.entries.find(item => item.item_id === entry.item_id)!.item_name} : {stockDisplay(entry.quantity)} {stockUnits[entry.unit]}</li>)}</ul></article>)}<div className="bm-stock-pages"><button disabled={!offset} onClick={() => page(offset - 50)}>Réceptions précédentes</button><button disabled={facts.receipts.length < 50} onClick={() => page(offset + 50)}>Réceptions suivantes</button></div></>}
    {original && getOperatorRole() === "responsable_institut" && <Receive order={original} ready={usable && !!facts && !loading} complete={facts?.progress.state === "received"} refresh={refresh} invalidate={onStockInvalidate} onRecovered={onRecovered} />}
  </section>;
}
function Receive({ order, ready, complete, refresh, invalidate, onRecovered }: { order: Order; ready: boolean; complete: boolean; refresh: (original: Order | Receipt) => Promise<boolean>; invalidate: () => void; onRecovered: () => void }) {
  const write = usePurchaseWrite(order.institute_id, "receipt", order, ready, refresh, invalidate, onRecovered);
  const [amounts, edit] = useState<Record<string, string>>({}), [reason, setReason] = useState(""), [error, setError] = useState<string>();
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!ready || complete || write.saved || write.busy || write.blocked) return;
    const named = order.entries.filter(row => !!amounts[row.item_id]?.trim()).map(row => ({ ...row, quantity: stockQuantity(amounts[row.item_id], row.unit) || "0.000" }));
    const payload = { entries: named.map(({ item_name, item_sku, ...row }) => row), reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    if (!validPurchaseIntent(payload, "receipt")) { setError("Saisissez les quantités réellement reçues et leur motif"); return; }
    setError(undefined); if (await write.run({ payload, label: order.reference, entries: named, order })) { edit({}); setReason(""); }
  }
  return <form className="bm-stock-form" aria-label="Recevoir une livraison" onSubmit={event => void submit(event)}><h4>Recevoir une livraison</h4><p>Laissez vides les articles non reçus. Aucune quantité n’est préremplie.</p><fieldset disabled={!ready || complete || write.busy || !!write.saved || write.blocked}>{order.entries.map(row => <label key={row.item_id}>Quantité reçue pour {row.item_name} ({stockUnits[row.unit]})<input inputMode="decimal" value={amounts[row.item_id] || ""} onChange={event => edit(rows => ({ ...rows, [row.item_id]: event.target.value }))} /></label>)}<label>Motif de réception<input required minLength={3} maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /></label><button type="submit">Confirmer la réception</button></fieldset>{error && <p role="alert">{error}</p>}<WriteStatus write={write} /></form>;
}
