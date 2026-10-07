import { verifyConversionSources } from "../api/marketing-conversion-proof";
import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { validCampaignOriginal, sameCampaignOriginal, type CampaignOriginal } from "../marketing-campaign-utils";
import { sameDispatchTerms, type DispatchIntent, type DispatchOutcome } from "../marketing-dispatch-utils";
import { validConversionRequest, matchesConversionReceipt, sameConversionOriginal,
  type ConversionOriginal, type ConversionRequest, type ConversionWindow } from "../marketing-conversion-utils";
type Props = { institute: string; intent: DispatchIntent; accepted: DispatchOutcome; ticket: string; period: ConversionWindow; onChanged?: () => void };
export function MarketingConversionWriter(props: Props) {
  if (!getOperatorSubject() || getOperatorRole() !== "responsable_institut") return null;
  return <Writer key={JSON.stringify([props.institute, props.intent.id, props.accepted.id, props.ticket, props.period, getAccessToken()])} {...props} />;
}
function Writer({ institute, intent, accepted, ticket, period, onChanged }: Props) {
  const actor = getOperatorSubject()!, token = getAccessToken(), root = intent.request.campaign_id;
  const base = `/marketing/institutes/${encodeURIComponent(institute)}`, conversions = base + "/conversions";
  const storage = `flowpilot.conversion-request:${JSON.stringify([institute, actor, ticket])}`;
  function stored(v: unknown): v is { campaign: string; request: ConversionRequest } {
    const s = v as { campaign: string; request: ConversionRequest };
    return !!s && typeof s === "object" && Object.keys(s).length === 2 && s.campaign === root && validConversionRequest(s.request)
      && s.request.ticket_id === ticket && (s.request.selection === null || s.request.selection.intent_id === intent.id
        && s.request.selection.expected_fingerprint === intent.request_fingerprint && s.request.selection.accepted_outcome_id === accepted.id);
  }
  const [saved, save] = useState<{ terms?: { campaign: string; request: ConversionRequest }; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storage); if (!raw) return {}; const s = JSON.parse(raw); return stored(s) ? { terms: s } : { invalid: true }; }
    catch { return { invalid: true }; }
  });
  const [head, setHead] = useState<ConversionOriginal | null>(), [receipt, setReceipt] = useState<ConversionOriginal>();
  const [reason, setReason] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const [rejected, setRejected] = useState(false);
  const mounted = useRef(false), pending = useRef(false);
  const current = () => mounted.current && token === getAccessToken() && actor === getOperatorSubject() && getOperatorRole() === "responsable_institut";
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const verify = (o: ConversionOriginal) => verifyConversionSources(o, institute, ticket);
  async function readHead() {
    if (!current() || pending.current || saved.terms || saved.invalid) return;
    pending.current = true; setBusy(true); setHead(undefined); setError(undefined);
    try {
      const h = await apiGet<ConversionOriginal | null>(`${conversions}/tickets/${encodeURIComponent(ticket)}/current`);
      if (h) await verify(h);
      if (current()) setHead(h);
    } catch { if (current()) setError("Lien courant à vérifier. Relancez la lecture."); }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  async function accept(o: ConversionOriginal, request: ConversionRequest) {
    if (!matchesConversionReceipt(o, request, actor)) throw new Error();
    await verify(o);
    if (!current()) return;
    const raw = sessionStorage.getItem(storage);
    if (!raw || !stored(JSON.parse(raw)) || !sameDispatchTerms(JSON.parse(raw).request, request)) throw new Error();
    sessionStorage.removeItem(storage); save({}); setReceipt(o); setHead(o); onChanged?.();
  }
  async function retain(action?: "linked" | "retracted") {
    if (!current() || pending.current || saved.invalid || receipt) return;
    pending.current = true; setBusy(true); setError(undefined); setRejected(false);
    let request = saved.terms?.request;
    try {
      // Original-key recovery always precedes current sources and every POST.
      if (request) {
        const original = await apiGet<ConversionOriginal | null>(`${conversions}/original/${encodeURIComponent(request.idempotency_key)}`);
        if (original) { await accept(original, request); return; }
      } else {
        if (!action || head === undefined || action === "retracted" && head?.request.action !== "linked") throw new Error();
        const latest = await apiGet<ConversionOriginal | null>(`${conversions}/tickets/${encodeURIComponent(ticket)}/current`);
        if (head === null ? latest !== null : latest === null || !await sameConversionOriginal(head, latest, institute)) throw new Error();
        const key = crypto.randomUUID();
        let authorization: CampaignOriginal | undefined;
        if (action === "linked") {
          authorization = await apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(root)}/current`);
          if (!await validCampaignOriginal(authorization, institute) || authorization.revision.campaign_id !== root
            || authorization.revision.state !== "SEND" || authorization.revision.previous_id !== intent.request.expected_revision_id
            || !sameDispatchTerms(authorization.revision.content, intent.submission.eligibility.campaign.content)) throw new Error();
          const original = await apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(authorization.revision.id)}`);
          if (!await sameCampaignOriginal(authorization, original, institute)) throw new Error();
        }
        request = { action, ticket_id: ticket, expected_previous_id: head?.id || null, reason: reason.trim(), idempotency_key: key,
          selection: action === "linked" ? { intent_id: intent.id, expected_fingerprint: intent.request_fingerprint,
            authorization_id: authorization!.revision.id, accepted_outcome_id: accepted.id, ticket_id: ticket,
            start: period.start, end: period.end, reason: reason.trim(), idempotency_key: key } : null };
        if (!validConversionRequest(request) || !current()) throw new Error();
        const terms = { campaign: root, request };
        if (sessionStorage.getItem(storage) !== null) throw new Error();
        sessionStorage.setItem(storage, JSON.stringify(terms)); save({ terms });
        const original = await apiGet<ConversionOriginal | null>(`${conversions}/original/${encodeURIComponent(key)}`);
        if (original) { await accept(original, request); return; }
      }
      if (!current()) return;
      await accept(await apiPost<ConversionOriginal>(conversions, request), request);
    } catch (e) {
      if (current() && e instanceof ApiError && [400, 422].includes(e.status)) setRejected(true);
      if (current()) setError(e instanceof ApiError && [400, 422].includes(e.status)
        ? "Opération refusée. Les termes protégés restent disponibles pour vérification."
        : "Opération à vérifier. Récupérez les mêmes termes avant toute nouvelle décision.");
    } finally { pending.current = false; if (current()) setBusy(false); }
  }
  async function correct() {
    if (!current() || pending.current || !rejected || !saved.terms) return;
    pending.current = true; setBusy(true); setError(undefined);
    try {
      const request = saved.terms.request;
      const original = await apiGet<ConversionOriginal | null>(`${conversions}/original/${encodeURIComponent(request.idempotency_key)}`);
      if (original) { await accept(original, request); return; }
      if (!current()) return;
      const raw = sessionStorage.getItem(storage);
      if (!raw || !stored(JSON.parse(raw)) || !sameDispatchTerms(JSON.parse(raw), saved.terms)) throw new Error();
      sessionStorage.removeItem(storage); save({}); setHead(undefined); setRejected(false);
    } catch { if (current()) setError("Original à vérifier. Les termes restent protégés."); }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  const frozen = busy || !!saved.terms || !!saved.invalid || !!receipt;
  return <section aria-label="Enregistrer une conversion">
    <h4>Lien de conversion déclaré</h4>
    <p>Ticket {ticket}. Le lien retient la facturation actuelle lors de l’enregistrement ; il ne prouve pas un effet de la campagne.</p>
    <button disabled={frozen} onClick={() => void readHead()}>Vérifier le lien courant</button>
    {head !== undefined && <p>{head === null ? "Aucun lien courant." : head.request.action === "linked" ? "Ticket déjà lié. Une nouvelle attribution remplacera le lien courant." : "Lien rétracté conservé dans l’historique."}</p>}
    {head && <p>Campagne du lien courant : {head.attribution.intent.request.campaign_id}{head.attribution.intent.request.campaign_id !== root ? " · autre campagne : la décision concerne le lien courant de ce ticket." : ""}</p>}
    <label>Motif du lien ou de la rétractation <input value={saved.terms?.request.reason || reason} disabled={frozen} maxLength={240} onChange={e => setReason(e.target.value)} /></label>
    <button disabled={frozen || head === undefined || reason.trim().length < 3} onClick={() => void retain("linked")}>Enregistrer le lien de conversion</button>
    <button disabled={frozen || head?.request.action !== "linked" || reason.trim().length < 3} onClick={() => void retain("retracted")}>Rétracter le lien courant</button>
    {saved.terms && <button disabled={busy} onClick={() => void retain()}>Récupérer ou réessayer la même opération</button>}
    {saved.terms && rejected && <button disabled={busy} onClick={() => void correct()}>Corriger après le refus</button>}
    {saved.invalid && <p role="alert">Termes protégés à vérifier. Aucune nouvelle opération autorisée pour ce ticket.</p>}
    {busy && <p role="status">Vérification de l’opération…</p>}{error && <p role="alert">{error}</p>}
    {receipt && <p>Original conservé : {receipt.id} · {receipt.request.action === "linked" ? "Lien enregistré" : "Lien rétracté"}. La vente et ses données restent conservées.</p>}
    {receipt && <button disabled={busy} onClick={() => { if (current()) { setReceipt(undefined); setHead(undefined); setReason(""); } }}>Nouvelle décision pour ce ticket</button>}
  </section>;
}
