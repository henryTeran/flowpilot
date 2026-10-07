import { MarketingConversionTickets } from "./MarketingConversionTickets";
import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { certificationInstant } from "../certification-utils";
import { validCampaignOriginal, sameCampaignOriginal, type CampaignOriginal } from "../marketing-campaign-utils";
import { validContactOriginal, sameContactOriginal } from "../marketing-contact-utils";
import { validDispatchIntentPage, sameDispatchIntent, sameDispatchTerms, validDispatchOutcome, validDispatchOutcomePage,
  type DispatchIntent, type DispatchOutcome, type DispatchPage } from "../marketing-dispatch-utils";
export function MarketingDispatchHistory({ institute, campaign, timezone }: { institute: string; campaign: CampaignOriginal; timezone?: string }) {
  if (getOperatorRole() !== "responsable_institut" || campaign.revision.institute_id !== institute) return null;
  return <Reader key={JSON.stringify([institute, campaign.revision.id, getAccessToken()])} institute={institute} campaign={campaign} timezone={timezone} />;
}
function Reader({ institute, campaign, timezone }: { institute: string; campaign: CampaignOriginal; timezone?: string }) {
  const token = getAccessToken(), mounted = useRef(false), pending = useRef(false);
  const [page, setPage] = useState<DispatchPage<DispatchIntent>>(), [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const base = `/marketing/institutes/${encodeURIComponent(institute)}`, root = campaign.revision.campaign_id;
  const current = () => mounted.current && token === getAccessToken();
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function read(target = offset) {
    if (!current() || pending.current) return;
    pending.current = true; setBusy(true); setOffset(target); setPage(undefined); setError(undefined);
    try {
      const p = await apiGet<DispatchPage<DispatchIntent>>(`${base}/campaigns/${encodeURIComponent(root)}/dispatch-intents?offset=${target}&limit=20`);
      if (!current()) return;
      if (!await validDispatchIntentPage(p, institute, root, target, 20)) throw new Error();
      const head = await apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(root)}/current`);
      if (!await sameCampaignOriginal(head, campaign, institute)) throw new Error();
      await Promise.all(p.items.map(async intent => {
        const r = intent.request, contact = intent.submission.eligibility.original;
        const contacts = `${base}/customers/${encodeURIComponent(r.customer_id)}/contact-declarations`;
        const [id, key, approved, contactId, contactKey] = await Promise.all([
          apiGet(`${base}/dispatch-intents/${encodeURIComponent(intent.id)}`),
          apiGet(`${base}/dispatch-intents/original/${encodeURIComponent(r.idempotency_key)}`),
          apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(r.expected_revision_id)}`),
          apiGet(`${contacts}/${encodeURIComponent(contact.id)}`), apiGet(`${contacts}/original/${encodeURIComponent(contact.idempotency_key)}`),
        ]);
        if (!await sameDispatchIntent(intent, id, institute) || !await sameDispatchIntent(intent, key, institute)
          || !await validCampaignOriginal(approved, institute) || !sameDispatchTerms(approved.revision, intent.submission.eligibility.campaign)
          || ![contactId, contactKey].every(v => validContactOriginal(v, institute, r.customer_id) && sameContactOriginal(contact, v))) throw new Error();
      }));
      if (current()) setPage(p);
    } catch { if (current()) setError("Intentions conservées à vérifier. Réessayez la lecture."); }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  return <section aria-label="Intentions conservées"><h4>Intentions conservées</h4>
    <button disabled={busy} onClick={() => void read()}>Vérifier les intentions conservées</button>
    {busy && <p role="status">Vérification des originaux…</p>}{error && <p role="alert">{error}</p>}
    {page && <><p>{page.items.length ? `${page.offset + 1}–${page.offset + page.items.length}` : "0"} sur {page.total} intentions</p>
      {page.items.map(intent => <article key={intent.id} style={{ overflowWrap: "anywhere" }}><p>Intention {intent.id} · cliente {intent.request.customer_id}</p>
        <p>{intent.submission.account.channel} · {intent.submission.account.provider} · {intent.submission.account.account_id} · {intent.submission.account.mode === "test" ? "test" : "réel"}</p>
        <p>{intent.created_at} · {intent.submission.actor_id} · {intent.request.reason}</p>
        <Outcomes key={JSON.stringify([intent.id, token])} institute={institute} intent={intent} timezone={timezone} /></article>)}
      <button disabled={busy || page.offset === 0} onClick={() => void read(Math.max(0, page.offset - 20))}>Intentions précédentes</button>
      <button disabled={busy || page.offset + page.items.length >= page.total} onClick={() => void read(page.offset + 20)}>Intentions suivantes</button></>}
    <p>Une intention conservée ne prouve aucun envoi. Les permissions courantes se vérifient séparément.</p>
  </section>;
}
function Outcomes({ institute, intent, timezone }: { institute: string; intent: DispatchIntent; timezone?: string }) {
  const token = getAccessToken(), mounted = useRef(false), pending = useRef(false);
  const [page, setPage] = useState<DispatchPage<DispatchOutcome>>(), [head, setHead] = useState<DispatchOutcome | null>();
  const [offset, setOffset] = useState(0), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const base = `/marketing/institutes/${encodeURIComponent(institute)}/dispatch-intents/${encodeURIComponent(intent.id)}/outcomes`;
  const current = () => mounted.current && token === getAccessToken();
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function read(target = offset) {
    if (!current() || pending.current) return;
    pending.current = true; setBusy(true); setOffset(target); setPage(undefined); setHead(undefined); setError(undefined);
    try {
      const [p, h] = await Promise.all([apiGet<DispatchPage<DispatchOutcome>>(`${base}?offset=${target}&limit=20`), apiGet<DispatchOutcome | null>(base + "/current")]);
      if (!current()) return;
      if (!await validDispatchOutcomePage(p, intent, institute, target, 20) || (h === null ? p.total !== 0 : !await validDispatchOutcome(h, intent, institute) || p.total === 0)) throw new Error();
      const last = p.items[p.items.length - 1];
      if (h && last && certificationInstant(h.created_at)! < certificationInstant(last.created_at)!) throw new Error();
      const originals = [...p.items]; if (h && !originals.some(o => o.id === h.id)) originals.push(h);
      if (h && p.items.some(o => o.id === h.id && !sameDispatchTerms(o, h))) throw new Error();
      if (h && p.items.some(o => o.request.expected_previous_id === h.id)) throw new Error();
      const prior = h && p.items.find(o => o.id === h.request.expected_previous_id);
      if (h && prior && (prior.request.result.status !== "unknown"
        || certificationInstant(prior.created_at)! > certificationInstant(h.created_at)!
        || certificationInstant(prior.request.result.observed_at)! > certificationInstant(h.request.result.observed_at)!
        || prior.request.result.provider_message_id !== null && prior.request.result.provider_message_id !== h.request.result.provider_message_id)) throw new Error();
      await Promise.all(originals.map(async o => {
        const [id, key] = await Promise.all([apiGet(`${base}/${encodeURIComponent(o.id)}`), apiGet(`${base}/original/${encodeURIComponent(o.request.idempotency_key)}`)]);
        if (!await validDispatchOutcome(id, intent, institute) || !await validDispatchOutcome(key, intent, institute)
          || !sameDispatchTerms(o, id) || !sameDispatchTerms(o, key)) throw new Error();
      }));
      const again = await apiGet<DispatchOutcome | null>(base + "/current");
      if (!sameDispatchTerms(h, again)) throw new Error();
      if (current()) { setPage(p); setHead(h); }
    } catch { if (current()) setError("Résultats conservés à vérifier. Réessayez la lecture."); }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  const label = (o: DispatchOutcome) => o.request.result.status === "accepted" ? "Accepté par le fournisseur" : o.request.result.status === "rejected" ? "Refusé par le fournisseur" : "Résultat incertain";
  return <section aria-label="Résultats conservés"><button disabled={busy} onClick={() => void read()}>Vérifier les résultats conservés</button>
    {busy && <p role="status">Vérification des résultats…</p>}{error && <p role="alert">{error}</p>}
    {page && <><p>{head ? `Dernier résultat : ${label(head)}` : "Aucun résultat conservé. Aucun envoi prouvé."}</p>
      <p>{page.items.length ? `${page.offset + 1}–${page.offset + page.items.length}` : "0"} sur {page.total} observations</p>
      {page.items.map(o => <div key={o.id}><p>{label(o)} · {o.request.result.observed_at} · {o.request.reason}</p>
        <p>Original {o.id} · précédent {o.request.expected_previous_id || "Aucun"} · référence {o.request.result.provider_message_id || "Absente"}</p></div>)}
      <button disabled={busy || page.offset === 0} onClick={() => void read(Math.max(0, page.offset - 20))}>Résultats précédents</button>
      <button disabled={busy || page.offset + page.items.length >= page.total} onClick={() => void read(page.offset + 20)}>Résultats suivants</button>
      <p>Acceptation fournisseur ne signifie pas livraison. Cette page ne vérifie pas les prédécesseurs hors de sa tranche et ne déclenche aucun envoi.</p></>}
    {head?.request.result.status === "accepted" && <MarketingConversionTickets institute={institute} intent={intent} accepted={head} timezone={timezone} />}
  </section>;
}
