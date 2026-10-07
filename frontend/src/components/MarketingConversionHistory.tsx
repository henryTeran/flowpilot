import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { verifyConversionSources } from "../api/marketing-conversion-proof";
import { getAccessToken, getOperatorRole } from "../api/session";
import { certificationInstant as instant } from "../certification-utils";
import { validConversionAuditPage, validConversionOriginal, sameConversionOriginal, type ConversionOriginal } from "../marketing-conversion-utils";
import { type DispatchPage } from "../marketing-dispatch-utils";
export function MarketingConversionHistory({ institute, ticket }: { institute: string; ticket: string }) {
  if (!institute || !ticket || getOperatorRole() !== "responsable_institut") return null;
  return <Reader key={JSON.stringify([institute, ticket, getAccessToken()])} institute={institute} ticket={ticket} />;
}
function Reader({ institute, ticket }: { institute: string; ticket: string }) {
  const token = getAccessToken(), sequence = useRef(0);
  const [page, setPage] = useState<DispatchPage<ConversionOriginal>>(), [head, setHead] = useState<ConversionOriginal | null>();
  const [offset, setOffset] = useState(0), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const base = `/marketing/institutes/${encodeURIComponent(institute)}/conversions/tickets/${encodeURIComponent(ticket)}`;
  useEffect(() => () => { sequence.current++; }, []);
  async function read(target = offset) {
    const n = ++sequence.current, current = () => n === sequence.current && token === getAccessToken() && getOperatorRole() === "responsable_institut";
    setPage(undefined); setHead(undefined); setOffset(target); setBusy(true); setError(undefined);
    try {
      const [p, h] = await Promise.all([apiGet<DispatchPage<ConversionOriginal>>(`${base}/audit?offset=${target}&limit=20`), apiGet<ConversionOriginal | null>(base + "/current")]);
      if (!await validConversionAuditPage(p, institute, ticket, target, 20)
        || (h === null ? p.total !== 0 : p.total === 0 || !await validConversionOriginal(h, institute, ticket))) throw new Error();
      if (!current()) return;
      const originals = [...p.items];
      if (h) {
        const last = p.items[p.items.length - 1];
        if (last && instant(last.created_at)! > instant(h.created_at)!) throw new Error();
        const equal = p.items.find(o => o.id === h.id);
        if (equal && !await sameConversionOriginal(equal, h, institute) || p.items.some(o => o.request.expected_previous_id === h.id)) throw new Error();
        const prior = p.items.find(o => o.id === h.request.expected_previous_id);
        if (prior && (instant(prior.created_at)! > instant(h.created_at)! || h.request.action === "retracted"
          && (prior.request.action !== "linked" || prior.attribution_fingerprint !== h.attribution_fingerprint))) throw new Error();
        if (!equal) originals.push(h);
      }
      await Promise.all(originals.map(o => verifyConversionSources(o, institute, ticket)));
      const again = await apiGet<ConversionOriginal | null>(base + "/current");
      if (h === null ? again !== null : again === null || !await sameConversionOriginal(h, again, institute)) throw new Error();
      if (current()) { setPage(p); setHead(h); }
    } catch { if (current()) setError("Historique des conversions à vérifier. Relancez la lecture."); }
    finally { if (current()) setBusy(false); }
  }
  return <section aria-label="Historique des conversions" style={{ overflowWrap: "anywhere" }}>
    <h4>Historique du ticket</h4><button disabled={busy} onClick={() => void read()}>Vérifier l’historique des conversions</button>
    {busy && <p role="status">Lecture des originaux…</p>}{error && <p role="alert">{error}</p>}
    {page && <>
      <p>{head === null ? "Aucun lien conservé." : head?.request.action === "linked" ? "Lien courant actif." : "Lien courant rétracté."}</p>
      <p>{page.items.length ? `${page.offset + 1}–${page.offset + page.items.length}` : "0"} sur {page.total} décisions conservées</p>
      {page.items.map(o => <article key={o.id}>
        <h5>{o.request.action === "linked" ? "Lien déclaré" : "Rétractation"} · {o.attribution.intent.submission.account.mode === "test" ? "Mode test" : "Mode réel"}</h5>
        <p>{o.created_at} · {o.actor_id} · {o.request.reason}</p>
        <p>Campagne {o.attribution.intent.request.campaign_id} · original {o.id} · précédent {o.request.expected_previous_id || "Aucun"}</p>
        <p>Montant historique : {o.attribution.ticket.amount_minor === null ? o.attribution.ticket.amount_quality === "missing" ? "manquant" : "invalide"
          : `${BigInt(o.attribution.ticket.amount_minor) / 100n}.${(BigInt(o.attribution.ticket.amount_minor) % 100n).toString().padStart(2, "0")}`} {o.attribution.ticket.currency || "Devise inconnue"}</p>
      </article>)}
      <button disabled={busy || offset === 0} onClick={() => void read(Math.max(0, offset - 20))}>Décisions précédentes</button>
      <button disabled={busy || offset + page.items.length >= page.total} onClick={() => void read(offset + 20)}>Décisions suivantes</button>
      <p>Les montants de l’historique ne s’additionnent pas. Les versions précédentes et rétractations restent conservées ; les prédécesseurs hors de cette page sont vérifiés par le backend lors des lectures d’originaux.</p>
    </>}
  </section>;
}
