import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { instituteInstants } from "../institute-calendar";
import { certificationInstant as instant } from "../certification-utils";
import { validWaitlistLifecycleState, type WaitlistLifecycleState } from "../waitlist-lifecycle-utils";
import { validWaitlistMatching, validWaitlistDetection, validWaitlistPolicy, type WaitlistPolicy, type WaitlistMatching, type WaitlistDetection, type WaitlistMatchingSelection } from "../waitlist-matching-utils";
import type { Employee, Service } from "../types";
type Props = { institute: string; timezone?: string; selection?: WaitlistLifecycleState; services?: Service[]; employees?: Employee[];
  onReviewed?: (value: WaitlistMatchingSelection | undefined) => void };
const reasons: Record<string, string> = { cancelled: "Liste annulée", registration_unavailable: "Inscription cliente à vérifier", active_service_unavailable: "Prestation active indisponible",
  history_requirement_unmet: "L’historique enregistré ne satisfait pas la règle choisie", permission_requirement_unmet: "Aucun accord actuel enregistré pour le canal choisi",
  constraints_unknown: "Contraintes clientes inconnues", duration_changed: "La durée actuelle diffère de la déclaration", resource_configuration_unknown: "Configuration des ressources inconnue",
  customer_capacity_unknown: "Occupation cliente à vérifier", queue_projection_unknown: "Projection de la file à vérifier", no_matching_recorded_capacity: "Aucun créneau correspondant dans la capacité enregistrée" };
function zoneValid(zone?: string) { if (!zone || /^[+-]/.test(zone)) return false; try { new Intl.DateTimeFormat("fr-CH", { timeZone: zone }); return true; } catch { return false; } }
export function WaitlistMatchingReview(props: Props) {
  if (!props.institute || getOperatorRole() !== "responsable_institut") return null;
  return <Reader key={JSON.stringify([props.institute, props.timezone, getAccessToken()])} {...props} />;
}
function Reader({ institute, timezone, selection, services = [], employees = [], onReviewed }: Props) {
  const token = getAccessToken(), sequence = useRef(0), mounted = useRef(false), section = useRef<HTMLElement>(null);
  const current = (n: number) => mounted.current && n === sequence.current && token === getAccessToken() && getOperatorRole() === "responsable_institut";
  const [selected, setSelected] = useState<WaitlistLifecycleState>(), [date, setDate] = useState(""), [time, setTime] = useState(""), [occurrence, setOccurrence] = useState("");
  const [channel, setChannel] = useState(""), [history, setHistory] = useState(""), [permission, setPermission] = useState("");
  const [report, setReport] = useState<WaitlistMatching>(), [detection, setDetection] = useState<WaitlistDetection>();
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; sequence.current++; }; }, []);
  function clear() { sequence.current++; setReport(undefined); setDetection(undefined); setError(undefined); setBusy(false); onReviewed?.(undefined); }
  useEffect(() => {
    clear(); setSelected(undefined);
    if (!selection) return;
    const n = sequence.current;
    void (async () => {
      const snapshot = structuredClone(selection);
      if (!await validWaitlistLifecycleState(snapshot, institute) || snapshot.state !== "active") {
        if (current(n)) setError("Sélection à vérifier : relisez les états conservés."); return;
      }
      if (current(n)) { setSelected(snapshot); section.current?.focus(); section.current?.scrollIntoView?.({ block: "start" }); }
    })();
  }, [selection]);
  const choices = zoneValid(timezone) ? instituteInstants(date, time, timezone) : [];
  const horizon = choices.length === 1 ? choices[0] : choices.includes(occurrence) ? occurrence : undefined;
  const policy = { channel, history_requirement: history, permission_requirement: permission };
  const ready = !!horizon && validWaitlistPolicy(policy);
  function format(value: string) { try { return new Intl.DateTimeFormat("fr-CH", { timeZone: timezone || "UTC", dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); } catch { return value; } }
  async function load(mode: "selected" | "all", offset = 0) {
    const n = ++sequence.current, state = selected ? structuredClone(selected) : undefined;
    setReport(undefined); setDetection(undefined); setError(undefined);
    if (!current(n)) return;
    onReviewed?.(undefined);
    if (!ready || !horizon || !validWaitlistPolicy(policy) || mode === "selected" && !state) { setError("Choisissez une fin d’horizon et toutes les règles de revue."); return; }
    const rules: WaitlistPolicy = { ...policy }, end = horizon;
    setBusy(true);
    try {
      const query = new URLSearchParams({ horizon_end: end, ...rules });
      const base = `/waitlist/institutes/${encodeURIComponent(institute)}`;
      if (mode === "selected") {
        if (!state || !await validWaitlistLifecycleState(state, institute) || !current(n)) return;
        const latest = state.events[state.events.length - 1];
        query.set("expected_event_id", latest.original.id); query.set("expected_event_fingerprint", latest.fingerprint);
        const value = await apiGet<WaitlistMatching>(`${base}/lifecycle/states/${encodeURIComponent(state.root.original.id)}/matching?${query}`);
        if (!await validWaitlistMatching(value, institute, { state, horizon_end: end, policy: rules })) throw new Error("Invalid matching proof");
        if (current(n)) { setReport(value); onReviewed?.({ state, horizon_end: end, policy: rules }); }
      } else {
        query.set("offset", String(offset)); query.set("limit", "20");
        const value = await apiGet<WaitlistDetection>(`${base}/detection?${query}`);
        if (!await validWaitlistDetection(value, institute, end, rules, offset)) throw new Error("Invalid detection proof");
        if (current(n)) setDetection(value);
      }
    } catch { if (current(n)) setError("Créneaux et sources à vérifier. Relisez les états si la version a changé, puis relancez la revue."); }
    finally { if (current(n)) setBusy(false); }
  }
  function view(r: WaitlistMatching) {
    const demand = r.state.current_demand.original.demand, e = r.evidence, c = r.review?.capture.customer;
    const service = services.find(s => s.id === demand.service_id)?.name || demand.service_id;
    const latest = r.state.events[r.state.events.length - 1];
    const recordedHistory = c?.history ?? (e && (Object.values(e.care_diagnostics).some(n => n > 0) || instant(e.registered_at) === instant(r.captured_at)) ? "unknown" : e?.latest_care ? "observed" : "no_recorded_care");
    const recordedPermission = c?.permission ?? (e?.permission_reason === "current_declaration" ? e.permission_original?.declaration.communications.find(x => x.channel === r.policy.channel && x.purpose === "service_follow_up")?.permission : undefined) ?? "unknown";
    return <article key={r.state.root.original.id} aria-label={`Revue : ${r.state.root.original.reason}`}>
      <h3>{r.state.root.original.reason}</h3><p>Déclaration examinée : {r.state.current_demand.original.reason}.</p>
      <p>Cliente {demand.customer_id} · {service} · durée déclarée {demand.duration_minutes} min{r.review && ` · durée actuelle ${r.review.capture.service.duration_minutes} min`}.</p>
      <p>Contraintes {demand.constraints_review === "confirmed" ? "relues selon la déclaration" : "inconnues"}.</p>
      {(r.unavailable_reason || r.review?.unavailable_reason) && <p>{reasons[r.unavailable_reason || r.review!.unavailable_reason!]}</p>}
      {r.review?.options.length ? <><h4>Options conditionnelles à relire</h4><ul>{r.review.options.map((o, n) => <li key={n}>Du {format(o.start)} au {format(o.end)} · collaboratrice {employees.find(x => x.id === o.employee_id && x.institute_id === institute)?.first_name || o.employee_id}
        {o.resource_ids.length ? ` · ressources distinctes : ${o.resource_ids.join(", ")}` : " · aucune ressource requise selon le catalogue capturé"}.</li>)}</ul></> : <p>Aucune option présentée pour cette revue.</p>}
      {e && <><p>Historique enregistré : {({ observed: "soins observés", no_recorded_care: "aucun soin enregistré", unknown: "à vérifier" })[recordedHistory]}. {e.observed_care_episodes} épisodes enregistrés.</p>
        {e.latest_care && <p>Dernier soin enregistré : {format(e.latest_care.completed_at)}.</p>}
        <p>Accord de suivi par {r.policy.channel === "email" ? "e-mail" : "SMS"} : {({ granted: "accord enregistré", refused: "refus enregistré", unknown: "inconnu" })[recordedPermission]}
          {e.permission_reason === "declaration_absent" ? " — aucune déclaration" : e.permission_reason === "future_declaration" ? " — déclaration future" : ` — déclaration du ${format(e.permission_original!.created_at)}`}.</p>
        <p>File enregistrée : {e.waiting_tickets} demandes · {e.queue_slots.length} projections connues · {e.unprojectable_queue_tickets} à vérifier. Les projections contraignent les créneaux, sans réserver.</p>
        <p>Capacité fondée sur les occupations enregistrées. Horaires d’ouverture non vérifiés ; cette lecture n’accorde aucune autorisation de contact.</p></>}
      <details><summary>Voir la version et les sources de cette revue</summary><p>Capture au {format(r.captured_at)} · horizon jusqu’au {format(r.horizon_end)}.</p>
        <p>Action sélectionnée {latest.original.id} · empreinte {latest.fingerprint}.</p><pre>{JSON.stringify(r, null, 2)}</pre></details>
    </article>;
  }
  return <section ref={section} tabIndex={-1} className="revenue-guardian-panel waitlist-matching-review" aria-label="Revue des créneaux de liste d’attente">
    <h2>Revue des créneaux de liste d’attente</h2><p>Choisissez les règles et l’horizon avant de lire. Les options sont des alternatives indépendantes : aucune réservation ni aucun contact n’est effectué.</p>
    <p>Horaires : {timezone || "fuseau institut indisponible"}.</p>{!zoneValid(timezone) && <p role="alert">Un fuseau institut valide est requis pour choisir l’horizon.</p>}
    {selected ? <p>Liste sélectionnée : {selected.root.original.reason} · déclaration courante : {selected.current_demand.original.reason}. La revue vérifie cette version.</p>
      : <p>Pour examiner une liste, sélectionnez-la dans les états conservés. La détection examine toutes les listes actives.</p>}
    <div className="revenue-guardian-period">
      <label>Fin de l’horizon — date<input type="date" value={date} disabled={busy} onChange={e => { clear(); setDate(e.target.value); setOccurrence(""); }} /></label>
      <label>Fin de l’horizon — heure<input type="time" value={time} disabled={busy} onChange={e => { clear(); setTime(e.target.value); setOccurrence(""); }} /></label>
      {choices.length > 1 && <label>Fin de l’horizon — occurrence<select value={occurrence} disabled={busy} onChange={e => { clear(); setOccurrence(e.target.value); }}>
        <option value="">Choisir l’occurrence</option>{choices.map((x, n) => <option key={x} value={x}>{n + 1} · {x}</option>)}</select></label>}
      <label>Canal de suivi<select value={channel} disabled={busy} onChange={e => { clear(); setChannel(e.target.value); }}><option value="">Choisir le canal</option><option value="email">E-mail</option><option value="sms">SMS</option></select></label>
      <label>Règle d’historique<select value={history} disabled={busy} onChange={e => { clear(); setHistory(e.target.value); }}><option value="">Choisir la règle</option>
        <option value="review_only">Examiner l’historique sans exclure</option><option value="observed_care_required">Exiger un soin enregistré</option><option value="no_recorded_care_required">Exiger l’absence de soin enregistré</option></select></label>
      <label>Règle d’accord de suivi<select value={permission} disabled={busy} onChange={e => { clear(); setPermission(e.target.value); }}><option value="">Choisir la règle</option>
        <option value="review_only">Examiner l’accord sans exclure</option><option value="recorded_grant_required">Exiger un accord enregistré</option></select></label>
    </div>
    {!!date && !!time && !choices.length && zoneValid(timezone) && <p role="alert">Fin d’horizon inexistante ou invalide dans le fuseau de l’institut.</p>}
    <div className="revenue-guardian-period"><button disabled={busy || !ready || !selected} onClick={() => void load("selected")}>Examiner la liste sélectionnée</button>
      <button disabled={busy || !ready} onClick={() => void load("all")}>Détecter les créneaux des listes actives</button></div>
    {busy && <p role="status">Relecture des versions et de la capacité enregistrée…</p>}{error && <p role="alert">{error}</p>}
    {report && view(report)}
    {detection && <><p>Capture au {format(detection.captured_at)} : {detection.examined_roots} listes examinées · {detection.active} actives · {detection.cancelled} annulées.</p>
      <p>{detection.with_options} listes avec options conditionnelles · {detection.without_options} sans option. Ces nombres comptent les listes, pas les clientes ni les réservations.</p>
      {!!detection.without_options && <ul>{Object.entries(detection.unavailable_reasons).map(([reason, n]) => <li key={reason}>{reasons[reason]} : {n} listes.</li>)}</ul>}
      <p>{detection.reviews.length ? `${detection.offset + 1}–${detection.offset + detection.reviews.length}` : "0"} sur {detection.active} listes actives. Chaque page relit toutes les sources.</p>
      {detection.reviews.map(view)}<div className="revenue-guardian-period"><button disabled={busy || detection.offset === 0} onClick={() => void load("all", Math.max(0, detection.offset - 20))}>Détections précédentes</button>
        <button disabled={busy || detection.offset + detection.reviews.length >= detection.active} onClick={() => void load("all", detection.offset + 20)}>Détections suivantes</button></div></>}
  </section>;
}
