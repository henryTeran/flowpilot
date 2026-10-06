import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validRecipe, type Recipe } from "../recipe-utils";
import { instituteMidnight, validOutlook, validScenario, type Outlook, type Scenario } from "../outlook-utils";
import { stockMilli, stockDisplay, stockUnits } from "../inventory-utils";
import type { Service } from "../types";
import { instituteTimeZone } from "../institute-time";
import { StockSourceOutlook } from "./StockSourceOutlook";
const base = (id: string) => `/inventory/institutes/${encodeURIComponent(id)}`;
type Chosen = { service_id: string; name: string; recipe: Recipe | null; input: string };
type Frozen = { scenario: Scenario; choices: Chosen[] };
const signature = (recipe: Recipe) => JSON.stringify(recipe);
export function StockOutlook(props: { institute: string; timezone: string; services: Service[]; usable: boolean }) {
  if (!props.institute || !["accueil", "responsable_institut"].includes(getOperatorRole() || "")) return null;
  return <Modes key={JSON.stringify([props.institute, getAccessToken(), props.timezone])} {...props} />;
}
function Modes(props: { institute: string; timezone: string; services: Service[]; usable: boolean }) {
  const [source, select] = useState(false);
  return <><div className="bm-stock-pages bm-stock-view-switch" role="group" aria-label="Vue des besoins"><button type="button" aria-pressed={!source} onClick={() => select(false)}>Stock et scénario</button><button type="button" aria-pressed={source} onClick={() => select(true)}>Prestations et usage</button></div>
    <div hidden={source}><View {...props} timezone={instituteTimeZone(props.timezone)} usable={props.usable && !source} /></div>
    <div hidden={!source}><StockSourceOutlook institute={props.institute} timezone={props.timezone} usable={props.usable && source} /></div></>;
}
function View({ institute, timezone, services, usable }: { institute: string; timezone: string; services: Service[]; usable: boolean }) {
  const token = getAccessToken(), [facts, setFacts] = useState<Outlook>(), [offset, page] = useState(0), [frozen, freeze] = useState<Frozen>();
  const [choices, choose] = useState<Chosen[]>([]), [start, setStart] = useState(""), [end, setEnd] = useState(""), [service, select] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const mounted = useRef(false), sequence = useRef(0), pending = useRef(false);
  const current = (request: number) => mounted.current && request === sequence.current && token === getAccessToken();
  function edit() { sequence.current++; setFacts(undefined); freeze(undefined); page(0); setError(undefined); }
  async function read(value: Frozen | null | undefined = frozen, next = offset) {
    if (!usable || token !== getAccessToken()) return;
    const request = ++sequence.current; setFacts(undefined); setBusy(true); setError(undefined);
    try {
      if (value) for (const chosen of value.choices) {
        if (!chosen.recipe) continue;
        const original = await apiGet<Recipe>(`${base(institute)}/recipes/${encodeURIComponent(chosen.recipe.id)}`);
        if (!current(request)) return;
        if (!validRecipe(original, institute, chosen.service_id) || signature(original) !== signature(chosen.recipe)) throw new Error("Version originale de la norme à vérifier");
      }
      const path = `${base(institute)}/${value ? "forecast" : "outlook"}?limit=20&offset=${next}`;
      const result = value ? await apiPost<Outlook>(path, value.scenario) : await apiGet<Outlook>(path);
      if (!current(request)) return;
      if (!validOutlook(result, institute, next, value?.scenario)) throw new Error("Lecture des besoins à vérifier");
      if (value) {
        for (const demand of result.demands) { const chosen = value.choices.find(row => row.service_id === demand.service_id)!; if (demand.recipe_revision !== (chosen.recipe?.revision ?? null) || demand.state !== (chosen.recipe ? chosen.recipe.enabled ? "enabled" : "disabled" : "missing_selected_norm")) throw new Error("Normes du scénario à vérifier"); }
        for (const item of result.items) { const expected = value.choices.reduce((sum, row) => sum + (row.recipe?.enabled ? row.recipe.entries.filter(entry => entry.item_id === item.item_id).reduce((sum, entry) => { if (entry.unit !== item.unit) throw new Error("Unité de norme à vérifier"); return sum + stockMilli(entry.quantity) * BigInt(row.input); }, 0n) : 0n), 0n); if (expected !== stockMilli(item.known_demand)) throw new Error("Quantités originales du scénario à vérifier"); }
      }
      setFacts(result);
    } catch (error) { if (current(request)) setError(error instanceof Error ? error.message : "Besoins indisponibles"); }
    finally { if (current(request)) setBusy(false); }
  }
  useEffect(() => { mounted.current = true; if (usable) void read(); else { sequence.current++; setFacts(undefined); setBusy(false); } return () => { mounted.current = false; sequence.current++; }; }, [offset, usable]);
  async function calculate(event: FormEvent) {
    event.preventDefault(); if (!usable || pending.current || token !== getAccessToken()) return;
    const starts_at = instituteMidnight(start, timezone), ends_at = instituteMidnight(end, timezone);
    const scenario = { starts_at, ends_at, demands: choices.map(row => ({ service_id: row.service_id, recipe_id: row.recipe?.id ?? null, quantity: /^([1-9]\d{0,5})$/.test(row.input) ? Number(row.input) : 0 })) };
    if (!validScenario(scenario)) { setError("Dates de l’institut et volumes entiers de 1 à 100000 requis, horizon limité à 366 jours."); return; }
    const saved = { scenario, choices: choices.map(row => ({ ...row })) }; freeze(saved); if (offset) { page(0); return; } pending.current = true;
    try { await read(saved, 0); } finally { pending.current = false; }
  }
  return <section className="bm-stock-detail bm-stock-outlook" aria-label="Besoins et réapprovisionnement"><h2>Besoins et réapprovisionnement</h2><p>Le stock physique reste distinct des commandes non reçues. Les seuils sont des minima, pas des quantités à acheter.</p>
    <button type="button" disabled={busy || !usable} onClick={() => void read()}>Actualiser les besoins</button>
    <form aria-label="Scénario de prestations" className="bm-stock-form" onSubmit={event => void calculate(event)}><h3>Scénario de prestations</h3><p>Saisissez vos volumes pour la période choisie. Ce scénario ne prédit pas le nombre de clientes et ne débite aucun article. Dates : {timezone}.</p>
      <fieldset disabled={busy || !usable}><label>Premier jour<input type="date" required value={start} onChange={event => { edit(); setStart(event.target.value); }} /></label><label>Fin de période (jour exclu)<input type="date" required value={end} onChange={event => { edit(); setEnd(event.target.value); }} /></label>
      <label>Prestation du scénario<select value={service} onChange={event => select(event.target.value)}><option value="">Choisir une prestation</option>{services.filter(row => !choices.some(chosen => chosen.service_id === row.id)).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      {service && <NormPicker key={JSON.stringify([institute, service, token])} institute={institute} service={service} disabled={choices.length >= 50} onChoose={recipe => { const selected = services.find(row => row.id === service); if (!selected) return; edit(); choose(rows => [...rows, { service_id: service, name: selected.name, recipe, input: "" }]); select(""); }} />}
      {choices.map(row => <div key={row.service_id}><p>{row.name} · {row.recipe ? `Norme originale v${row.recipe.revision} · ${row.recipe.enabled ? "active" : "désactivée"}` : "Norme non sélectionnée : besoins inconnus"}</p><label>Volume de {row.name}<input required inputMode="numeric" value={row.input} onChange={event => { edit(); choose(rows => rows.map(chosen => chosen.service_id === row.service_id ? { ...chosen, input: event.target.value } : chosen)); }} /></label><button type="button" onClick={() => { edit(); choose(rows => rows.filter(chosen => chosen.service_id !== row.service_id)); }}>Retirer {row.name} du scénario</button></div>)}
      <button type="submit" disabled={!choices.length}>Calculer les besoins du scénario</button></fieldset></form>
    <button type="button" disabled={busy} onClick={() => { edit(); choose([]); select(""); void read(null, 0); }}>Voir uniquement le stock enregistré</button>
    {busy && <p role="status">Lecture des besoins…</p>}{error && <p role="alert">{error}</p>}
    {usable && facts && <><p>Lecture : {new Date(facts.generated_at).toLocaleString("fr-CH", { timeZone: timezone })}</p>{facts.source === "explicit_service_volume_scenario" && <p>{facts.coverage === "partial_selected_norms" ? "Couverture partielle : besoins totaux inconnus. Les quantités ci-dessous ne couvrent que les normes choisies." : "Besoins du scénario uniquement : toutes les normes choisies sont connues."}</p>}<p>Après toutes les commandes : résultat conditionnel, sans garantie de date de livraison. Aucune commande n’est créée ici.</p>
      {!facts.items.length && <p>Aucun article sur cette page.</p>}<div className="bm-stock-grid">{facts.items.map(row => <article className="bm-stock-card" key={row.item_id}><h3>{row.item_name} · {row.item_sku}</h3><p>Stock physique : {stockDisplay(row.on_hand)} {stockUnits[row.unit]}</p><p>Seuil : {stockDisplay(row.threshold)} {stockUnits[row.unit]}{row.at_or_below_threshold && " · Au seuil ou en dessous"}</p><p>Manque pour atteindre le seuil : {stockDisplay(row.threshold_shortfall)} {stockUnits[row.unit]}</p><p>Commandé, non reçu : {stockDisplay(row.pending_order_quantity)} {stockUnits[row.unit]}</p>{frozen && <p>Besoins connus du scénario : {stockDisplay(row.known_demand)} {stockUnits[row.unit]} · Total {row.complete_demand === null ? "inconnu" : stockDisplay(row.complete_demand)}</p>}<p>Manque physique {frozen ? "avec besoins connus" : "au seuil"} : {stockDisplay(row.known_demand_shortfall)} {stockUnits[row.unit]}</p><p>Manque si toutes les commandes arrivent : {stockDisplay(row.conditional_shortfall_after_all_orders)} {stockUnits[row.unit]}</p></article>)}</div><div className="bm-stock-pages"><button disabled={busy || !offset} onClick={() => page(offset - 20)}>Besoins précédents</button><button disabled={busy || facts.items.length < 20} onClick={() => page(offset + 20)}>Besoins suivants</button></div></>}
  </section>;
}
function NormPicker({ institute, service, disabled, onChoose }: { institute: string; service: string; disabled: boolean; onChoose: (recipe: Recipe | null) => void }) {
  const token = getAccessToken(), [rows, setRows] = useState<Recipe[]>(), [offset, page] = useState(0), [reload, refresh] = useState(0), [choice, select] = useState(""), [error, setError] = useState<string>();
  useEffect(() => { let active = true; setRows(undefined); select(""); setError(undefined); void apiGet<Recipe[]>(`${base(institute)}/services/${encodeURIComponent(service)}/recipes?limit=10&offset=${offset}`).then(result => { if (!Array.isArray(result) || result.length > 10 || !result.every(row => validRecipe(row, institute, service)) || new Set(result.map(row => row.id)).size !== result.length) throw new Error("Versions originales à vérifier"); if (active && token === getAccessToken()) setRows(result); }).catch(error => { if (active && token === getAccessToken()) setError(String(error)); }); return () => { active = false; }; }, [offset, reload]);
  return <div><button type="button" disabled={disabled} onClick={() => refresh(reload + 1)}>Actualiser les normes du scénario</button>{error && <p role="alert">{error}</p>}<label>Version de norme du scénario<select disabled={disabled || !rows} value={choice} onChange={event => select(event.target.value)}><option value="">Choisir explicitement une norme</option><option value="unknown">Aucune norme sélectionnée (besoins inconnus)</option>{rows?.map(row => <option key={row.id} value={row.id}>Version {row.revision} · {row.enabled ? "Active" : "Désactivée"}</option>)}</select></label><button type="button" disabled={disabled || !rows || !choice} onClick={() => { if (token === getAccessToken()) onChoose(choice === "unknown" ? null : rows!.find(row => row.id === choice)!); }}>Ajouter la prestation au scénario</button><div className="bm-stock-pages"><button type="button" disabled={disabled || !rows || !offset} onClick={() => page(offset - 10)}>Normes précédentes du scénario</button><button type="button" disabled={disabled || rows?.length !== 10} onClick={() => page(offset + 10)}>Normes suivantes du scénario</button></div></div>;
}
