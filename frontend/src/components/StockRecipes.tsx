import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { stockDisplay, stockQuantity, stockUnits, validStockItem, type StockItem } from "../inventory-utils";
import { matchesRecipe, validRecipe, validRecipeIntent, type Recipe, type RecipeIntent } from "../recipe-utils";
import type { Service } from "../types";
const base = (institute: string) => `/inventory/institutes/${encodeURIComponent(institute)}`;
const message = (error: unknown) => error instanceof Error ? error.message : "Recette indisponible";
type Basis = { recipe: Recipe | null; items: StockItem[] };

async function readItems(institute: string, recipe: Recipe | null) {
  return await Promise.all((recipe?.entries || []).map(async entry => {
    const item = await apiGet<StockItem>(`${base(institute)}/items/${encodeURIComponent(entry.item_id)}`);
    if (!validStockItem(item, institute) || item.id !== entry.item_id || item.unit !== entry.unit) throw new Error("Articles de la recette à vérifier");
    return item;
  }));
}
function pendingServices(institute: string) {
  const actor = getOperatorSubject(), rows: Array<{ id: string; name: string }> = [];
  try {
    for (let index = 0; index < sessionStorage.length; index++) {
      const key = sessionStorage.key(index)!;
      if (!key.startsWith("flowpilot.recipe-request:")) continue;
      try {
      const scope = JSON.parse(key.slice("flowpilot.recipe-request:".length));
      const row = JSON.parse(sessionStorage.getItem(key) || "null") as RecipeIntent;
      if (Array.isArray(scope) && scope.length === 3 && scope[0] === institute && scope[2] === actor && typeof scope[1] === "string" && !!scope[1].trim() && scope[1] === scope[1].trim() && scope[1].length <= 80 && validRecipeIntent(row)) rows.push({ id: scope[1], name: row.service_name || `Demande conservée : ${scope[1]}` });
      } catch { continue; }
    }
  } catch { /* Malformed local recovery data cannot select another scope. */ }
  return rows;
}
export function StockRecipes({ institute, services }: { institute: string; services: Service[] }) {
  const [selected, select] = useState(""), [selectedName, setSelectedName] = useState("");
  const choices = [...services.map(row => ({ id: row.id, name: row.name })), ...pendingServices(institute).filter(row => !services.some(service => service.id === row.id))];
  if (selected && !choices.some(row => row.id === selected)) choices.push({ id: selected, name: selectedName || "Prestation conservée" });
  if (!institute || !["accueil", "responsable_institut"].includes(getOperatorRole() || "")) return null;
  return <section className="bm-stock-detail bm-stock-recipes" aria-label="Recettes par prestation">
    <h2>Recettes par prestation</h2><p>Quantités prévues par prestation. Configurer une recette ne débite pas le stock.</p>
    <label>Prestation de la recette<select value={selected} onChange={event => { select(event.target.value); setSelectedName(choices.find(row => row.id === event.target.value)?.name || ""); }}><option value="">Choisir une prestation</option>{choices.map(service => <option key={service.id} value={service.id}>{service.name}</option>)}</select></label>
    {selected && choices.some(service => service.id === selected) && <RecipeView key={JSON.stringify([institute, selected, getAccessToken()])} institute={institute} service={selected} serviceName={choices.find(row => row.id === selected)!.name} />}
  </section>;
}
function RecipeView({ institute, service, serviceName }: { institute: string; service: string; serviceName: string }) {
  const token = getAccessToken(), manager = getOperatorRole() === "responsable_institut";
  const [facts, setFacts] = useState<Basis>(), [basis, setBasis] = useState<Basis>(), [history, setHistory] = useState<Recipe[]>(), [offset, setOffset] = useState(0), [original, selectOriginal] = useState<string>();
  const [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  const mounted = useRef(false), sequence = useRef(0);
  async function load() {
    const request = ++sequence.current, current = () => mounted.current && request === sequence.current && token === getAccessToken();
    setFacts(undefined); setHistory(undefined); setLoading(true); setError(undefined);
    try {
      const path = `${base(institute)}/services/${encodeURIComponent(service)}`;
      const [row, rows] = await Promise.all([apiGet<Recipe | null>(`${path}/recipe`), apiGet<Recipe[]>(`${path}/recipes?limit=10&offset=${offset}`)]);
      if ((row !== null && !validRecipe(row, institute, service)) || !Array.isArray(rows) || rows.length > 10 || !rows.every(row => validRecipe(row, institute, service)) || new Set(rows.map(row => row.id)).size !== rows.length || new Set(rows.map(row => row.revision)).size !== rows.length) throw new Error("Lecture des recettes incomplète");
      if (!current()) return false;
      const items = await readItems(institute, row);
      if (!current()) return false;
      const value = { recipe: row, items }; setFacts(value); setBasis(value); setHistory(rows); return true;
    } catch (error) { if (current()) setError(message(error)); return false; }
    finally { if (current()) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false; sequence.current++; }; }, [offset]);
  return <div>
    <button type="button" onClick={() => void load()} disabled={loading}>Actualiser les recettes</button>
    {loading && <p role="status">Lecture des recettes…</p>}{error && <p role="alert">{error}</p>}
    {facts && (facts.recipe ? <RecipeFacts recipe={facts.recipe} items={facts.items} /> : <p>Aucune recette configurée pour cette prestation.</p>)}
    {manager && basis && <RecipeEditor institute={institute} service={service} serviceName={serviceName} basis={basis} ready={!!facts && !loading} onRefresh={load} />}
    {history && <><h3>Versions enregistrées</h3>{history.map(row => <button type="button" key={row.id} onClick={() => selectOriginal(row.id)}>Version {row.revision} · {row.enabled ? "Active" : "Désactivée"}</button>)}
      <div className="bm-stock-pages"><button disabled={loading || !offset} onClick={() => setOffset(offset - 10)}>Versions précédentes</button><button disabled={loading || history.length < 10} onClick={() => setOffset(offset + 10)}>Versions suivantes</button></div></>}
    {!!facts && original && <OriginalRecipe key={JSON.stringify([original, token])} institute={institute} service={service} id={original} />}
  </div>;
}
function RecipeFacts({ recipe, items }: { recipe: Recipe; items: StockItem[] }) {
  return <section aria-label={`Recette version ${recipe.revision}`}><h3>Version {recipe.revision} · {recipe.enabled ? "Active" : "Désactivée"}</h3>
    <ul>{recipe.entries.map(entry => <li key={entry.item_id}>{items.find(item => item.id === entry.item_id)?.name} · {stockDisplay(entry.quantity)} {stockUnits[entry.unit]}</li>)}</ul>
    <p>{recipe.reason} · {recipe.actor_id}</p></section>;
}
function OriginalRecipe({ institute, service, id }: { institute: string; service: string; id: string }) {
  const token = getAccessToken(), [value, setValue] = useState<Basis>(), [error, setError] = useState<string>();
  useEffect(() => { let active = true; void (async () => { try {
    const row = await apiGet<Recipe>(`${base(institute)}/recipes/${encodeURIComponent(id)}`);
    if (!validRecipe(row, institute, service) || row.id !== id) throw new Error("Version originale à vérifier");
    const items = await readItems(institute, row);
    if (active && token === getAccessToken()) setValue({ recipe: row, items });
  } catch (error) { if (active && token === getAccessToken()) setError(message(error)); } })(); return () => { active = false; }; }, []);
  return <section aria-label="Version originale de la recette"><h3>Version originale</h3>{error && <p role="alert">{error}</p>}{value?.recipe ? <RecipeFacts recipe={value.recipe} items={value.items} /> : !error && <p>Lecture de la version…</p>}</section>;
}
function RecipeEditor({ institute, service, serviceName, basis, ready, onRefresh }: { institute: string; service: string; serviceName: string; basis: Basis; ready: boolean; onRefresh: () => Promise<boolean> }) {
  const token = getAccessToken(), actor = getOperatorSubject(), storage = `flowpilot.recipe-request:${JSON.stringify([institute, service, actor])}`;
  const [intent, setIntent] = useState<RecipeIntent | undefined>(() => { try { const row = JSON.parse(sessionStorage.getItem(storage) || "null"); return validRecipeIntent(row) ? row : undefined; } catch { return; } });
  const [revision, setRevision] = useState(basis.recipe?.revision || 0), [enabled, setEnabled] = useState(basis.recipe?.enabled || false);
  const initialEntries = () => (basis.recipe?.entries || []).map(entry => ({ ...entry, name: basis.items.find(item => item.id === entry.item_id)!.name, sku: basis.items.find(item => item.id === entry.item_id)!.sku }));
  const [entries, setEntries] = useState(initialEntries), [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>(), [success, setSuccess] = useState<string>();
  const lifetime = useRef(0), pending = useRef(false), refresh = useRef(onRefresh); refresh.current = onRefresh;
  useEffect(() => { lifetime.current++; return () => { lifetime.current++; }; }, []);
  function reset() { setRevision(basis.recipe?.revision || 0); setEnabled(basis.recipe?.enabled || false); setEntries(initialEntries()); setReason(""); setError(undefined); setSuccess(undefined); }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!ready || pending.current || !actor || token !== getAccessToken() || getOperatorRole() !== "responsable_institut") return;
    const row = intent || { service_name: serviceName, base_revision: revision, enabled, entries: enabled ? entries.map(entry => ({ ...entry, quantity: stockQuantity(entry.quantity, entry.unit)! })) : [], reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    if (!validRecipeIntent(row)) { setError("Vérifiez les articles, les quantités positives et le motif avant enregistrement."); return; }
    const stamp = lifetime.current, current = () => stamp === lifetime.current && token === getAccessToken();
    pending.current = true; setBusy(true); setIntent(row); setError(undefined); setSuccess(undefined);
    try {
      sessionStorage.setItem(storage, JSON.stringify(row));
      let result: Recipe;
      try { result = await apiPost(`${base(institute)}/services/${encodeURIComponent(service)}/recipes`, { base_revision: row.base_revision, enabled: row.enabled, reason: row.reason, idempotency_key: row.idempotency_key, entries: row.entries.map(entry => ({ item_id: entry.item_id, quantity: entry.quantity })) }); }
      catch (error) { if (current() && error instanceof ApiError && [400, 404, 422].includes(error.status)) { sessionStorage.removeItem(storage); setIntent(undefined); } throw error; }
      if (!current()) return;
      if (!validRecipe(result, institute, service) || !matchesRecipe(result, row, actor)) throw new Error("Résultat de la recette à vérifier");
      const original = await apiGet<Recipe>(`${base(institute)}/recipes/${encodeURIComponent(result.id)}`);
      if (!current()) return;
      if (!validRecipe(original, institute, service) || original.id !== result.id || !matchesRecipe(original, row, actor)) throw new Error("Version originale à vérifier");
      if (!await refresh.current()) throw new Error("Actualisez les recettes avant de poursuivre");
      if (!current()) return;
      sessionStorage.removeItem(storage); setIntent(undefined); setRevision(result.revision); setEnabled(row.enabled); setEntries(row.entries); setReason(""); setSuccess(`Version ${result.revision} enregistrée.`);
    } catch (error) { if (current()) setError(message(error)); }
    finally { if (current()) { pending.current = false; setBusy(false); } }
  }
  return <form className="bm-stock-form bm-recipe-form" aria-label="Configurer la recette" onSubmit={event => void submit(event)}>
    <h3>Configurer la recette</h3>{error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
    {intent ? <><p>Demande conservée depuis la version {intent.base_revision} · {intent.reason}</p><ul>{intent.entries.map(entry => <li key={entry.item_id}>{entry.name} · {stockDisplay(entry.quantity)} {stockUnits[entry.unit]}</li>)}</ul></> : <>
      <p>Modification depuis la version {revision}. Les autres versions sont conservées.</p>
      <button type="button" className="bm-recipe-reset" disabled={!ready || busy} onClick={reset}>Repartir de la version courante</button>
      <label className="bm-recipe-toggle"><input type="checkbox" checked={enabled} disabled={busy} onChange={event => setEnabled(event.target.checked)} /> Activer cette recette</label>
      {enabled && <><ItemPicker institute={institute} disabled={!ready || busy || entries.length >= 50} selected={entries.map(entry => entry.item_id)} onAdd={item => setEntries([...entries, { item_id: item.id, name: item.name, sku: item.sku, unit: item.unit, quantity: "" }])} />
        <div className="bm-stock-fields">{entries.map(entry => <div key={entry.item_id}><label>Quantité pour {entry.name} ({stockUnits[entry.unit]})<input inputMode="decimal" value={entry.quantity} onChange={event => setEntries(entries.map(row => row.item_id === entry.item_id ? { ...row, quantity: event.target.value } : row))} required /></label><button type="button" onClick={() => setEntries(entries.filter(row => row.item_id !== entry.item_id))}>Retirer {entry.name}</button></div>)}</div></>}
      <label>Motif de la recette<input value={reason} minLength={3} maxLength={240} required onChange={event => setReason(event.target.value)} /></label>
    </>}
    <button type="submit" disabled={!ready || busy || !actor}>{intent ? "Reprendre la recette conservée" : "Enregistrer la recette"}</button>
  </form>;
}
function ItemPicker({ institute, disabled, selected, onAdd }: { institute: string; disabled: boolean; selected: string[]; onAdd: (item: StockItem) => void }) {
  const token = getAccessToken(), [items, setItems] = useState<StockItem[]>(), [offset, setOffset] = useState(0), [reload, setReload] = useState(0), [choice, choose] = useState("");
  const [error, setError] = useState<string>();
  useEffect(() => { let active = true; setItems(undefined); setError(undefined); choose(""); void apiGet<StockItem[]>(`${base(institute)}/items?limit=50&offset=${offset}`).then(rows => {
    if (!Array.isArray(rows) || rows.length > 50 || !rows.every(row => validStockItem(row, institute)) || new Set(rows.map(row => row.id)).size !== rows.length) throw new Error("Articles disponibles à vérifier");
    if (active && token === getAccessToken()) setItems(rows);
  }).catch(error => { if (active && token === getAccessToken()) setError(message(error)); }); return () => { active = false; }; }, [offset, reload]);
  const item = items?.find(row => row.id === choice);
  return <div><button type="button" disabled={disabled} onClick={() => setReload(reload + 1)}>Actualiser les articles de recette</button>{error && <p role="alert">{error}</p>}<label>Article à ajouter<select disabled={disabled || !items} value={choice} onChange={event => choose(event.target.value)}><option value="">Choisir un article</option>{items?.filter(item => !selected.includes(item.id)).map(item => <option key={item.id} value={item.id}>{item.name} · {item.sku} · {stockUnits[item.unit]}</option>)}</select></label>
    <button type="button" disabled={disabled || !item || selected.includes(item.id)} onClick={() => { if (item) { onAdd(item); choose(""); } }}>Ajouter à la recette</button>
    <div className="bm-stock-pages"><button type="button" disabled={disabled || !items || !offset} onClick={() => setOffset(offset - 50)}>Articles précédents pour la recette</button><button type="button" disabled={disabled || items?.length !== 50} onClick={() => setOffset(offset + 50)}>Articles suivants pour la recette</button></div>
  </div>;
}
