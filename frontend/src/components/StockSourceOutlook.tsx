import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiPost } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { instituteTimeZone } from "../institute-time";
import { instituteMidnight } from "../outlook-utils";
import { stockDisplay, stockUnits } from "../inventory-utils";
import { validObserved, validPlanned, validPeriod, type Planned, type Observed, type PlannedRequest, type ObservedRequest } from "../source-outlook-utils";
type Query = { kind: "planned"; body: PlannedRequest } | { kind: "observed"; body: ObservedRequest };
type Facts = { kind: "planned"; value: Planned } | { kind: "observed"; value: Observed };
export function StockSourceOutlook(props: { institute: string; timezone: string; usable: boolean }) {
  if (!props.institute || !["accueil", "responsable_institut"].includes(getOperatorRole() || "")) return null;
  return <View key={JSON.stringify([props.institute, getAccessToken(), props.timezone])} {...props} timezone={instituteTimeZone(props.timezone)} />;
}
function View({ institute, timezone, usable }: { institute: string; timezone: string; usable: boolean }) {
  const token = getAccessToken(), [kind, mode] = useState<"planned" | "observed">("planned");
  const [start, starts] = useState(""), [end, ends] = useState(""), [historyStart, historyStarts] = useState(""), [historyEnd, historyEnds] = useState("");
  const [queue, include] = useState(false), [query, save] = useState<Query>(), [facts, publish] = useState<Facts>(), [offset, page] = useState(0);
  const [busy, loading] = useState(false), [error, fail] = useState<string>();
  const sequence = useRef(0), mounted = useRef(false);
  const current = (id: number) => mounted.current && id === sequence.current && token === getAccessToken();
  function edit() { sequence.current++; publish(undefined); save(undefined); page(0); loading(false); fail(undefined); }
  async function read(value: Query, next: number) {
    if (!usable || token !== getAccessToken()) return;
    const id = ++sequence.current; publish(undefined); fail(undefined); loading(true);
    try {
      const result = await apiPost<unknown>(`/inventory/institutes/${encodeURIComponent(institute)}/${value.kind === "planned" ? "planned-demand" : "observed-projection"}?limit=20&offset=${next}`, value.body);
      if (!current(id)) return;
      if (value.kind === "planned") {
        if (!validPlanned(result, institute, next, value.body)) throw new Error("Demandes enregistrées à vérifier");
        publish({ kind: "planned", value: result });
      } else {
        if (!validObserved(result, institute, next, value.body)) throw new Error("Usage observé à vérifier");
        publish({ kind: "observed", value: result });
      }
    } catch (e) { if (current(id)) fail(e instanceof Error ? e.message : "Lecture indisponible"); }
    finally { if (current(id)) loading(false); }
  }
  useEffect(() => { mounted.current = true; if (usable && query) void read(query, offset); else { sequence.current++; publish(undefined); loading(false); } return () => { mounted.current = false; sequence.current++; }; }, [offset, usable, query]);
  function calculate(event: FormEvent) {
    event.preventDefault(); if (busy || !usable || token !== getAccessToken()) return;
    const starts_at = instituteMidnight(start, timezone), ends_at = instituteMidnight(end, timezone);
    if (!starts_at || !ends_at || !validPeriod({ starts_at, ends_at })) { fail("Dates valides de l’institut requises, fin exclue et horizon de 366 jours maximum."); return; }
    let value: Query = { kind: "planned", body: { starts_at, ends_at, include_waiting_queue: queue } };
    if (kind === "observed") {
      const observed_starts_at = instituteMidnight(historyStart, timezone), observed_ends_at = instituteMidnight(historyEnd, timezone);
      if (!observed_starts_at || !observed_ends_at || !validPeriod({ starts_at: observed_starts_at, ends_at: observed_ends_at })) { fail("Période historique valide requise, fin exclue et 366 jours maximum."); return; }
      value = { kind: "observed", body: { starts_at, ends_at, observed_starts_at, observed_ends_at } };
    }
    publish(undefined); page(0); save(value);
  }
  const date = (value: string) => new Date(value).toLocaleString("fr-CH", { timeZone: timezone });
  return <section className="bm-stock-detail bm-stock-outlook" aria-label="Prévisions depuis les prestations"><h2>Prévisions depuis les prestations</h2>
    <p>Deux vues alternatives : les besoins des prestations enregistrées et le rythme des consommations signées. Leurs résultats ne s’additionnent pas.</p>
    <form className="bm-stock-form" aria-label="Périodes des prévisions" onSubmit={calculate}><fieldset disabled={busy || !usable}>
      <label>Source des prévisions<select value={kind} onChange={e => { edit(); mode(e.target.value as typeof kind); }}><option value="planned">Demandes à venir enregistrées</option><option value="observed">Rythme de l’usage observé</option></select></label>
      <p>Dates de l’institut : {timezone}. Les dates de fin sont exclues. La partie déjà écoulée de l’horizon futur est retirée.</p>
      <label>Début de l’horizon futur<input type="date" required value={start} onChange={e => { edit(); starts(e.target.value); }} /></label>
      <label>Fin de l’horizon futur (exclue)<input type="date" required value={end} onChange={e => { edit(); ends(e.target.value); }} /></label>
      {kind === "planned" ? <><label className="bm-stock-queue-option"><input type="checkbox" checked={queue} onChange={e => { edit(); include(e.target.checked); }} />Inclure la file en attente au moment de la lecture</label><p>La file n’a pas d’heure garantie et peut être réalisée hors de l’horizon choisi. Les normes des prestations non démarrées sont provisoires et peuvent changer.</p></> : <><label>Début de la période observée<input type="date" required value={historyStart} onChange={e => { edit(); historyStarts(e.target.value); }} /></label><label>Fin de la période observée (exclue)<input type="date" required value={historyEnd} onChange={e => { edit(); historyEnds(e.target.value); }} /></label><p>La période observée doit être terminée. Le rythme est supposé constant sur le temps écoulé ; ce calcul ne garantit pas la demande future.</p></>}
      <button type="submit">Lire les prévisions des prestations</button>
    </fieldset></form>
    <button type="button" disabled={busy || !usable || !query} onClick={() => query && void read(query, offset)}>Actualiser les prévisions des prestations</button>
    {busy && <p role="status">Lecture des prestations…</p>}{error && <p role="alert">{error}</p>}
    {usable && facts && <><p>Lecture : {date(facts.value.generated_at)} · Horizon restant : {date(facts.value.effective_starts_at)} au {date(facts.value.ends_at)} (fin exclue).</p>
      {facts.kind === "planned" ? <><p>Rendez-vous non démarrés : {facts.value.appointment_count} · Lignes en attente incluses : {facts.value.waiting_line_count} · Quantité de prestations : {facts.value.service_quantity}.</p><p>Normes provisoires au moment de la lecture. Quantités sans norme : {facts.value.missing_norm_quantity} · Avec norme désactivée : {facts.value.disabled_norm_quantity}.</p><p>{facts.value.coverage === "partial_recorded_norms" ? "Couverture partielle : besoins totaux inconnus." : "Normes connues pour les sources enregistrées sélectionnées uniquement."} Les arrivées non enregistrées ne sont pas prédites.</p></> : <><p>Période observée : {date(facts.value.observed_starts_at)} au {date(facts.value.observed_ends_at)} (fin exclue), selon la fin réelle des prestations.</p><p>Exécutions terminées : {facts.value.completed_executions} · Lignes capturées : {facts.value.captured_bases} · Confirmations signées : {facts.value.signed_confirmations} · À confirmer : {facts.value.pending_bases}.</p><p>Exécutions historiques sans base : {facts.value.legacy_completed_executions} · Sans date de fin, dans tout l’institut : {facts.value.undated_completed_executions}.</p><p>{facts.value.coverage === "no_completed_sample" ? "Aucun échantillon terminé dans la période : projection totale inconnue." : facts.value.coverage === "partial_signed_sample" ? "Échantillon incomplet : projection totale inconnue." : "Échantillon signé complet. Cela ne garantit pas la précision de la prévision."} Une confirmation vide est un zéro mesuré ; une confirmation absente reste inconnue. Le rythme du sous-ensemble enregistré n’est pas un minimum garanti.</p></>}
      <p>Les commandes attendues restent conditionnelles, sans garantie de livraison. Aucune commande ou consommation n’est créée ici.</p>
      {!facts.value.items.length && <p>Aucun article sur cette page.</p>}
      <div className="bm-stock-grid">{facts.value.items.map(row => <article className="bm-stock-card" key={row.item_id}><h3>{row.item_name} · {row.item_sku}</h3><p>Stock physique : {stockDisplay(row.on_hand)} {stockUnits[row.unit]}</p><p>Seuil : {stockDisplay(row.threshold)} {stockUnits[row.unit]}{row.at_or_below_threshold && " · Au seuil ou en dessous"}</p><p>Manque au seuil : {stockDisplay(row.threshold_shortfall)} {stockUnits[row.unit]} · Commandé, non reçu : {stockDisplay(row.pending_order_quantity)} {stockUnits[row.unit]}</p>
        {"observed_quantity" in row ? <><p>Usage signé observé : {stockDisplay(row.observed_quantity)} {stockUnits[row.unit]}</p><p>Projection du rythme enregistré : {stockDisplay(row.recorded_pace_projection)} {stockUnits[row.unit]} · Projection totale : {row.complete_pace_projection === null ? "inconnue" : stockDisplay(row.complete_pace_projection)}</p><p>Manque physique avec ce rythme : {stockDisplay(row.recorded_projection_shortfall)} {stockUnits[row.unit]}</p></> : <><p>Besoins connus enregistrés : {stockDisplay(row.known_demand)} {stockUnits[row.unit]} · Total : {row.complete_demand === null ? "inconnu" : stockDisplay(row.complete_demand)}</p><p>Manque physique avec ces besoins : {stockDisplay(row.known_demand_shortfall)} {stockUnits[row.unit]}</p></>}
        <p>Manque si toutes les commandes arrivent : {stockDisplay(row.conditional_shortfall_after_all_orders)} {stockUnits[row.unit]}</p></article>)}</div>
      <div className="bm-stock-pages"><button disabled={busy || !offset} onClick={() => page(offset - 20)}>Prévisions précédentes</button><button disabled={busy || facts.value.items.length < 20 || offset >= 100000} onClick={() => page(offset + 20)}>Prévisions suivantes</button></div>
    </>}
  </section>;
}
