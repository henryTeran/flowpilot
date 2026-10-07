import { useEffect, useRef, useState } from "react";
import { MarketingConversionWriter } from "./MarketingConversionWriter";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { instituteMidnight } from "../outlook-utils";
import { certificationInstant as instant } from "../certification-utils";
import { sameDispatchIntent, sameDispatchTerms, validDispatchOutcome, type DispatchIntent, type DispatchOutcome } from "../marketing-dispatch-utils";
import { validConversionTicketRead, type ConversionTicketRequest, type ConversionTicketRead, type Attribution } from "../marketing-conversion-utils";
export function MarketingConversionTickets({ institute, intent, accepted, timezone }: {
  institute: string; intent: DispatchIntent; accepted: DispatchOutcome; timezone?: string }) {
  if (getOperatorRole() !== "responsable_institut" || accepted.request.result.status !== "accepted") return null;
  return <Selector key={JSON.stringify([institute, intent.id, accepted.id, timezone, getAccessToken()])}
    institute={institute} intent={intent} accepted={accepted} timezone={timezone} />;
}
function Selector({ institute, intent, accepted, timezone }: { institute: string; intent: DispatchIntent; accepted: DispatchOutcome; timezone?: string }) {
  const token = getAccessToken(), sequence = useRef(0);
  const [start, setStart] = useState(""), [end, setEnd] = useState("");
  const [read, setRead] = useState<ConversionTicketRead>(), [selected, select] = useState<Attribution["ticket"]>();
  const [offset, setOffset] = useState(0), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  useEffect(() => () => { sequence.current++; }, []);
  const base = `/marketing/institutes/${encodeURIComponent(institute)}/dispatch-intents`;
  function change(field: "start" | "end", value: string) {
    sequence.current++; setRead(undefined); select(undefined); setBusy(false); setError(undefined);
    if (field === "start") setStart(value); else setEnd(value);
  }
  async function load(target = 0) {
    const n = ++sequence.current, current = () => n === sequence.current && token === getAccessToken() && getOperatorRole() === "responsable_institut";
    setRead(undefined); select(undefined); setError(undefined); setOffset(target);
    const from = timezone && instituteMidnight(start, timezone), until = timezone && instituteMidnight(end, timezone), observed = accepted.request.result.observed_at;
    if (!from || !until || instant(from) === undefined || instant(until) === undefined || instant(observed) === undefined) {
      setError("Choisissez deux dates et vérifiez le fuseau de l’institut."); return;
    }
    // The selected first day includes only times after the accepted observation.
    const period = { start: instant(from)! < instant(observed)! ? observed : from, end: until };
    if (instant(period.start)! >= instant(period.end)!) { setError("Choisissez une période après l’acceptation, dans l’ordre."); return; }
    const request: ConversionTicketRequest = { ...period, intent_id: intent.id, expected_fingerprint: intent.request_fingerprint, accepted_outcome_id: accepted.id };
    setBusy(true);
    try {
      const outcomes = `${base}/${encodeURIComponent(intent.id)}/outcomes`;
      const [id, key, outcomeId, outcomeKey] = await Promise.all([
        apiGet(`${base}/${encodeURIComponent(intent.id)}`), apiGet(`${base}/original/${encodeURIComponent(intent.request.idempotency_key)}`),
        apiGet(`${outcomes}/${encodeURIComponent(accepted.id)}`), apiGet(`${outcomes}/original/${encodeURIComponent(accepted.request.idempotency_key)}`),
      ]);
      if (!await sameDispatchIntent(intent, id, institute) || !await sameDispatchIntent(intent, key, institute)
        || !await validDispatchOutcome(outcomeId, intent, institute) || !await validDispatchOutcome(outcomeKey, intent, institute)
        || !sameDispatchTerms(accepted, outcomeId) || !sameDispatchTerms(accepted, outcomeKey)) throw new Error();
      if (!current()) return;
      const params = new URLSearchParams({ expected_fingerprint: request.expected_fingerprint, accepted_outcome_id: request.accepted_outcome_id,
        start: request.start, end: request.end, offset: String(target), limit: "20" });
      const result = await apiGet<ConversionTicketRead>(`${base}/${encodeURIComponent(intent.id)}/conversion-tickets?${params}`);
      if (!await validConversionTicketRead(result, institute, intent, accepted, request, target, 20)) throw new Error();
      if (current()) setRead(result);
    } catch { if (current()) setError("Tickets et sources à vérifier. Relancez la lecture."); }
    finally { if (current()) setBusy(false); }
  }
  return <section aria-label="Tickets pour conversion" style={{ overflowWrap: "anywhere" }}>
    <h4>Choisir un ticket payé</h4>
    <p>Journées de l’institut · {timezone || "Fuseau indisponible"}. Le début est limité à l’acceptation fournisseur ; la fin est exclue.</p>
    <label>Premier jour de facturation <input type="date" value={start} onChange={e => change("start", e.target.value)} /></label>
    <label>Dernier jour exclu <input type="date" value={end} onChange={e => change("end", e.target.value)} /></label>
    <button disabled={busy} onClick={() => void load()}>Lire les tickets payés</button>
    {busy && <p role="status">Lecture des tickets…</p>}{error && <p role="alert">{error}</p>}
    {read && <>
      <p>{read.page.items.length ? `${read.page.offset + 1}–${read.page.offset + read.page.items.length}` : "0"} sur {read.page.total} tickets payés</p>
      {read.page.items.map(t => <button key={t.ticket_id} aria-pressed={selected?.ticket_id === t.ticket_id} onClick={() => {
        if (token === getAccessToken() && getOperatorRole() === "responsable_institut") select(t);
      }}>
        Ticket {t.ticket_id} · {t.closed_at} · {t.currency || "Devise inconnue"} · {t.amount_quality === "known" ? `${BigInt(t.amount_minor!) / 100n}.${(BigInt(t.amount_minor!) % 100n).toString().padStart(2, "0")}` : t.amount_quality === "missing" ? "Montant manquant" : "Montant invalide"}
      </button>)}
      <button disabled={busy || offset === 0} onClick={() => void load(Math.max(0, offset - 20))}>Tickets précédents</button>
      <button disabled={busy || offset + read.page.items.length >= read.page.total} onClick={() => void load(offset + 20)}>Tickets suivants</button>
    </>}
    {selected && <p>Ticket sélectionné : {selected.ticket_id}. Aucun lien de conversion enregistré.</p>}
    {selected && read && <MarketingConversionWriter institute={institute} intent={intent} accepted={accepted} ticket={selected.ticket_id} period={read.window} />}
    <p>Ces données décrivent la facturation enregistrée du destinataire. Elles ne prouvent ni livraison, ni règlement bancaire, ni effet de la campagne.</p>
  </section>;
}
