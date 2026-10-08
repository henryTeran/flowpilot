import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { createBaseOperationIntent, createBaseDecisionIntent, createBaseExecutionIntent } from "../base-cancellation-intent";
import { validBasePreview, validBaseOperationEnvelope, validBaseApprovalState, validBaseExecutionEnvelope,
  validBaseOperationRequest, validBaseDecisionRequest, validBaseExecutionRequest,
  type BasePreview, type BaseOperationEnvelope, type BaseApprovalState, type BaseExecutionEnvelope } from "../base-cancellation-utils";
import type { Appointment, Employee, Service } from "../types";
const storage = { getItem: (k: string) => sessionStorage.getItem(k), setItem: (k: string, v: string) => sessionStorage.setItem(k, v), removeItem: (k: string) => sessionStorage.removeItem(k) };
type Props = { institute: string; timezone?: string; appointments: Appointment[]; employees?: Employee[]; services?: Service[]; onExecuted?: () => void };
type Mode = "operation" | "decision" | "execution";
export function BaseCancellationPanel(props: Props) {
  if (!props.institute || getOperatorRole() !== "responsable_institut" || !getOperatorSubject()) return null;
  return <Panel key={JSON.stringify([props.institute, props.timezone, getAccessToken()])} {...props} />;
}
function Panel({ institute, timezone = "UTC", appointments, employees = [], services = [], onExecuted }: Props) {
  const actor = getOperatorSubject()!, token = getAccessToken(), mounted = useRef(false), flight = useRef(false), sequence = useRef(0);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; sequence.current++; }; }, []);
  const current = () => mounted.current && token === getAccessToken() && actor === getOperatorSubject() && getOperatorRole() === "responsable_institut";
  const [drivers] = useState(() => {
    const options = { institute, actor, storage, current, get: (path: string) => apiGet(path), post: (path: string, terms: unknown) => apiPost(path, terms) };
    return { operation: createBaseOperationIntent(options), decision: createBaseDecisionIntent(options), execution: createBaseExecutionIntent(options) };
  });
  const [saved, setSaved] = useState(() => ({ operation: drivers.operation.state(), decision: drivers.decision.state(), execution: drivers.execution.state() }));
  const [appointment, setAppointment] = useState(""), [reason, setReason] = useState(""), [deadline, setDeadline] = useState(""), [identifier, setIdentifier] = useState("");
  const [preview, setPreview] = useState<BasePreview>(), [operation, setOperation] = useState<BaseOperationEnvelope>();
  const [history, setHistory] = useState<BaseApprovalState>(), [execution, setExecution] = useState<BaseExecutionEnvelope>();
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const base = `/base/institutes/${encodeURIComponent(institute)}`;
  const pending = Object.values(saved).some(s => s.status !== "empty");
  const refreshSaved = () => setSaved({ operation: drivers.operation.state(), decision: drivers.decision.state(), execution: drivers.execution.state() });
  function date(value: string) { try { return new Intl.DateTimeFormat("fr-CH", { timeZone: timezone, dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); } catch { return value; } }
  function snapshot(value: BasePreview) {
    const a = value.appointment;
    return <><p>{date(a.start_time)} – {date(a.end_time)} ({timezone}) · {{ scheduled: "planifié", confirmed: "confirmé", arrived: "cliente arrivée" }[a.status]}.</p>
      <p>Prestation : {services.find(s => s.id === a.service_id)?.name || "référence conservée"} ({a.service_id}). Collaboratrice : {employees.find(e => e.id === a.employee_id)?.first_name || "référence conservée"} ({a.employee_id}).</p></>;
  }
  async function readOperation(id: string, live: () => boolean) {
    const value = await apiGet(`${base}/sensitive-operations/${encodeURIComponent(id)}`);
    if (!await validBaseOperationEnvelope(value, institute)) throw new Error("Invalid operation");
    const op = value as BaseOperationEnvelope;
    const state = await apiGet(`${base}/sensitive-operations/${encodeURIComponent(id)}/approval-state`);
    if (!await validBaseApprovalState(state, institute, op)) throw new Error("Invalid history");
    const receipt = await apiGet(`${base}/sensitive-operations/${encodeURIComponent(id)}/execution`);
    if (receipt !== null && !await validBaseExecutionEnvelope(receipt, institute, state as BaseApprovalState)) throw new Error("Invalid execution");
    if (live()) { setOperation(op); setHistory(state as BaseApprovalState); setExecution(receipt as BaseExecutionEnvelope | undefined ?? undefined); setIdentifier(op.original.id); }
  }
  async function read(kind: "preview" | "operation") {
    if (!current() || flight.current) return;
    flight.current = true; setBusy(true); setError(undefined); const seq = ++sequence.current, live = () => current() && seq === sequence.current;
    setPreview(undefined); setOperation(undefined); setHistory(undefined); setExecution(undefined);
    try {
      if (kind === "preview") {
        if (!appointments.some(a => a.id === appointment && a.institute_id === institute && ["scheduled", "confirmed", "arrived"].includes(a.status))) throw new Error("Select appointment");
        const value = await apiPost(`${base}/sensitive-previews/appointment-cancel`, { appointment_id: appointment });
        if (!await validBasePreview(value, institute, appointment) || (value as BasePreview).principal.actor_id !== actor) throw new Error("Invalid preview");
        if (live()) setPreview(value as BasePreview);
      } else {
        if (!identifier || identifier !== identifier.trim() || Array.from(identifier).length > 80 || /[\x00-\x1f]/.test(identifier)) throw new Error("Invalid selection");
        await readOperation(identifier, live);
      }
    } catch { if (live()) setError("Lecture à vérifier. Choisissez une référence exacte et relisez son état."); }
    finally { flight.current = false; if (current()) setBusy(false); }
  }
  async function write(mode: Mode, decision?: "approve" | "decline" | "revoke", correction = false) {
    if (!current() || flight.current) return;
    flight.current = true; setBusy(true); setError(undefined); const seq = ++sequence.current, live = () => current() && seq === sequence.current;
    try {
      const driver = drivers[mode]; let result;
      if (correction) result = await driver.correct();
      else if (driver.state().status !== "empty") result = await driver.submit();
      else {
        const common = { reason: reason.trim(), idempotency_key: crypto.randomUUID() };
        if (mode === "operation") {
          if (!preview || preview.appointment_id !== appointment || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(deadline)) throw new Error("Explicit review required");
          const validUntil = new Date(`${deadline}:00Z`).toISOString().replace(".000Z", "Z");
          if (validUntil.slice(0, 16) !== deadline || Date.parse(validUntil) <= Date.now()) throw new Error("Future deadline required");
          const terms = { ...common, capability: "APPOINTMENT_CANCEL" as const, selection: { appointment_id: appointment }, expected_state_fingerprint: preview.state_fingerprint, valid_until: validUntil };
          if (!validBaseOperationRequest(terms)) throw new Error("Invalid request"); result = await drivers.operation.submit(terms);
        } else {
          if (!operation || !history || execution || !await validBaseApprovalState(history, institute, operation)) throw new Error("Review required");
          const last = history.decisions[history.decisions.length - 1];
          if (mode === "decision") {
            if (!decision || !(history.status === "pending" && ["approve", "decline"].includes(decision) || history.status === "approved" && decision === "revoke")
              || decision === "approve" && (history.expired || Date.parse(operation.original.valid_until) <= Date.now())) throw new Error("Invalid transition");
            const terms = { ...common, operation_id: operation.original.id, operation_fingerprint: operation.fingerprint, previous_id: last?.original.id ?? null, previous_fingerprint: last?.fingerprint ?? null, decision };
            if (!validBaseDecisionRequest(terms)) throw new Error("Invalid decision"); result = await drivers.decision.submit(terms);
          } else {
            if (history.status !== "approved" || history.expired || !last || Date.parse(operation.original.valid_until) <= Date.now()) throw new Error("Approval required");
            const terms = { ...common, operation_id: operation.original.id, operation_fingerprint: operation.fingerprint, approval_id: last.original.id, approval_fingerprint: last.fingerprint };
            if (!validBaseExecutionRequest(terms)) throw new Error("Invalid execution"); result = await drivers.execution.submit(terms);
          }
        }
      }
      if (!live()) return;
      if (result.status === "confirmed") {
        const opId = "operation_id" in result.receipt.original ? result.receipt.original.operation_id : result.receipt.original.id;
        setIdentifier(opId);
        setPreview(undefined); setOperation(undefined); setHistory(undefined); setExecution(undefined); setReason("");
        await readOperation(opId, live);
        if (live() && mode === "execution") onExecuted?.();
      } else if (result.status === "busy") setError("Une reprise est déjà en cours. Conservez la même demande.");
    } catch { if (live()) { setHistory(undefined); setExecution(undefined); setError("Demande à vérifier. Les termes envoyés restent figés ; reprenez la preuve ou relisez l’état avant une nouvelle action."); } }
    finally { flight.current = false; if (current()) { refreshSaved(); setBusy(false); } }
  }
  return <section className="base-cancellation-panel" aria-label="Annulation avec approbation BASE">
    <h3>Annulation avec approbation</h3>
    <p>Relisez le rendez-vous, conservez la préparation puis approuvez explicitement. L’exécution annule le rendez-vous et libère ses réservations ; elle n’envoie aucun message et ne rembourse rien.</p>
    {busy && <p role="status">Vérification en cours…</p>}{error && <p role="alert">{error}</p>}
    <label>Motif de l’action<input disabled={busy || pending} value={reason} onChange={e => setReason(e.target.value)} maxLength={240} /></label>
    {Object.entries(saved).filter(([, state]) => state.status !== "empty").map(([mode, state]) => <article key={mode}>
      <h4>Demande conservée — {mode === "operation" ? "préparation" : mode === "decision" ? "décision" : "exécution"}</h4>
      {state.status === "invalid" ? <p role="alert">Stockage illisible. Nouvelle écriture bloquée ; vérifiez la preuve conservée.</p> : state.status === "frozen" && <><p>Motif : {state.value.terms.reason}</p><p>Clé : {state.value.terms.idempotency_key}</p>
        <button type="button" disabled={busy} onClick={() => void write(mode as Mode)}>Reprendre {mode === "operation" ? "la préparation" : mode === "decision" ? "la décision" : "l’exécution"}</button>
        {drivers[mode as Mode].canCorrect() && <button type="button" disabled={busy} onClick={() => void write(mode as Mode, undefined, true)}>Vérifier le rejet et corriger</button>}</>}
    </article>)}
    <fieldset disabled={busy || pending}><legend>Préparer une annulation</legend>
      <label>Rendez-vous à relire<select aria-label="Rendez-vous à relire" value={appointment} onChange={e => { sequence.current++; setAppointment(e.target.value); setPreview(undefined); setOperation(undefined); setHistory(undefined); setExecution(undefined); }}><option value="">Choisir un rendez-vous</option>
        {appointments.filter(a => a.institute_id === institute && ["scheduled", "confirmed", "arrived"].includes(a.status)).map(a => <option key={a.id} value={a.id}>{date(a.start_time)} · {a.customer_name}</option>)}</select></label>
      <button type="button" onClick={() => void read("preview")}>Relire avant préparation</button>
      {preview && <article><h4>État relu</h4><p>Rendez-vous {preview.appointment_id}.</p>{snapshot(preview)}<p>Capture {date(preview.captured_at)}. Cet état sera vérifié de nouveau par le serveur.</p></article>}
      <label>Validité jusqu’au (UTC)<input type="datetime-local" value={deadline} onChange={e => setDeadline(e.target.value)} /></label>
      <button type="button" disabled={!preview} onClick={() => void write("operation")}>Conserver la préparation</button>
    </fieldset>
    <fieldset disabled={busy || pending}><legend>Relire une préparation conservée</legend><label>Référence de préparation<input value={identifier} onChange={e => { setIdentifier(e.target.value); setOperation(undefined); setHistory(undefined); setExecution(undefined); }} /></label><button type="button" onClick={() => void read("operation")}>Relire préparation et décisions</button></fieldset>
    {operation && <article><h4>Préparation conservée</h4><p>Référence {operation.original.id} · rendez-vous {operation.original.selection.appointment_id}</p>{snapshot(operation.original.preview)}<p>Motif : {operation.original.reason}</p><p>Auteur {operation.original.actor_id} · validité {date(operation.original.valid_until)}</p></article>}
    {history && <article><h4>Décisions relues</h4><p>État : {{ pending: "en attente", approved: "approuvée", declined: "refusée", revoked: "révoquée" }[history.status]}{history.expired ? " · validité expirée" : ""}. Capture {date(history.captured_at)}.</p>
      <p>L’historique ne garantit pas que le rendez-vous est encore inchangé. Le serveur le vérifiera avant approbation et exécution.</p>
      <ol>{history.decisions.map(d => <li key={d.original.id}>{({ approve: "Approbation", decline: "Refus", revoke: "Révocation" })[d.original.decision]} · {d.original.actor_id} · {date(d.original.created_at)} · {d.original.reason}</li>)}</ol>
      {!execution && <div className="appointment-actions">{history.status === "pending" && <><button type="button" disabled={busy || pending || history.expired} onClick={() => void write("decision", "approve")}>Approuver cette préparation</button><button type="button" disabled={busy || pending} onClick={() => void write("decision", "decline")}>Refuser cette préparation</button></>}
        {history.status === "approved" && <><button type="button" disabled={busy || pending} onClick={() => void write("decision", "revoke")}>Révoquer l’approbation</button><button type="button" disabled={busy || pending || history.expired} onClick={() => void write("execution")}>Exécuter l’annulation approuvée</button></>}</div>}
    </article>}
    {execution && <article><h4>Annulation exécutée et preuve relue</h4><p>Rendez-vous {execution.original.before.appointment_id} annulé · {date(execution.original.created_at)} · auteur {execution.original.actor_id}.</p><p>Aucun message ni remboursement effectué.</p></article>}
  </section>;
}
