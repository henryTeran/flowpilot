import { useEffect, useRef, useState } from "react";
import { MarketingDispatchPrepare } from "./MarketingDispatchPrepare";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { sameCampaignOriginal, type CampaignOriginal } from "../marketing-campaign-utils";
import { validContactOriginal, sameContactOriginal } from "../marketing-contact-utils";
import { validRecipientPage, type RecipientPage } from "../marketing-recipient-utils";
const reasons: Record<string, string> = { declared_eligible: "Accord et destination déclarés", campaign_not_approved: "Nouvelle approbation requise",
  future_campaign: "Date de campagne à vérifier", future_registration: "Date d’inscription à vérifier", declaration_absent: "Contacts non déclarés",
  future_declaration: "Date de déclaration à vérifier", permission_unknown: "Permission inconnue", permission_refused: "Refus déclaré", destination_absent: "Destination absente" };
export function MarketingRecipientPanel({ institute, original }: { institute: string; original?: CampaignOriginal }) {
  if (!original || original.revision.institute_id !== institute || getOperatorRole() !== "responsable_institut") return null;
  return <Reader key={JSON.stringify([institute, original.revision.id, getAccessToken()])} institute={institute} original={original} />;
}
function Reader({ institute, original }: { institute: string; original: CampaignOriginal }) {
  const token = getAccessToken(), mounted = useRef(false), sequence = useRef(0);
  const [page, setPage] = useState<RecipientPage>(), [offset, setOffset] = useState(0), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const base = `/marketing/institutes/${encodeURIComponent(institute)}`, root = original.revision.campaign_id;
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; sequence.current++; }; }, []);
  async function read(target = offset) {
    const request = ++sequence.current, current = () => mounted.current && token === getAccessToken() && request === sequence.current;
    setOffset(target); setBusy(true); setPage(undefined); setError(undefined);
    try {
      const p = await apiGet<RecipientPage>(`${base}/campaigns/${encodeURIComponent(root)}/recipient-observations?expected_revision_id=${encodeURIComponent(original.revision.id)}&offset=${target}&limit=20`);
      if (!current()) return;
      if (!await validRecipientPage(p, original, target, 20)) throw new Error("Invalid recipient observation");
      if (!current()) return;
      const [head, id] = await Promise.all([apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(root)}/current`),
        apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(original.revision.id)}`)]);
      if (!current()) return;
      if (!await sameCampaignOriginal(head, original, institute) || !await sameCampaignOriginal(id, original, institute)) throw new Error("Campaign changed");
      if (!current()) return;
      await Promise.all(p.items.map(async item => {
        const customerBase = `${base}/customers/${encodeURIComponent(item.customer.customer_id)}/contact-declarations`;
        const head = await apiGet<unknown>(customerBase + "/current"); if (!current()) return;
        if (item.original === null) { if (head !== null) throw new Error("Contact changed"); return; }
        const [id, key] = await Promise.all([apiGet<unknown>(`${customerBase}/${encodeURIComponent(item.original.id)}`),
          apiGet<unknown>(`${customerBase}/original/${encodeURIComponent(item.original.idempotency_key)}`)]);
        if (!current()) return;
        if (![head, id, key].every(v => validContactOriginal(v, institute, item.customer.customer_id)
          && sameContactOriginal(item.original!, v))) throw new Error("Contact original changed");
      }));
      if (current()) setPage(p);
    } catch { if (current()) setError("Destinataires à vérifier. Relisez la campagne et les contacts, puis réessayez."); }
    finally { if (current()) setBusy(false); }
  }
  return <section aria-label="Destinataires courants"><h4>Destinataires courants</h4>
    <button disabled={busy} onClick={() => void read()}>Vérifier les destinataires courants</button>
    {busy && <p role="status">Lecture des contacts courants…</p>}{error && <p role="alert">{error}</p>}
    {page && <><p>Lecture : {page.captured_at} · {page.items.length ? `${page.offset + 1}–${page.offset + page.items.length}` : "0"} sur {page.total} destinataires retenus</p>
      {page.items.map(i => <article key={i.customer.customer_id} style={{ overflowWrap: "anywhere" }}><p>Cliente {i.customer.customer_id}</p>
        <p>{reasons[i.reason]} · {i.eligible_by_current_declaration ? "Éligible selon la déclaration lue" : "Non éligible"}</p>
        <MarketingDispatchPrepare institute={institute} campaign={original} customer={i.customer.customer_id} contact={i.original} eligible={i.eligible_by_current_declaration} /></article>)}
      <button disabled={busy || page.offset === 0} onClick={() => void read(Math.max(0, page.offset - 20))}>Destinataires précédents</button>
      <button disabled={busy || page.offset + page.items.length >= page.total} onClick={() => void read(page.offset + 20)}>Destinataires suivants</button>
    </>}
    <p>Cette lecture décrit les permissions courantes. Les résultats fournisseur se vérifient séparément.</p>
  </section>;
}
