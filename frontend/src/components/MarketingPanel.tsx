import { useEffect, useRef, useState } from "react";
import { MarketingRecipientPanel } from "./MarketingRecipientPanel";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { MarketingCampaignActions } from "./MarketingCampaignActions";
import { MarketingAudiencePanel } from "./MarketingAudiencePanel";
import { MarketingAudienceCatalog } from "./MarketingAudienceCatalog";
import { MarketingTemplatePanel } from "./MarketingTemplatePanel";
import { MarketingCampaignCreator } from "./MarketingCampaignCreator";
import { validCampaignCatalog, validCampaignOriginal, validCampaignAuditPage, sameCampaignOriginal,
  type CampaignOriginal, type CampaignAuditPage } from "../marketing-campaign-utils";

type Catalog = { institute_id: string; total: number; offset: number; limit: number; items: CampaignOriginal[] };
const stages = { DRAFT: "Brouillon", REVIEW: "En revue", APPROVE: "Approuvée", SEND: "Envoi autorisé" };
export function MarketingPanel({ institute }: { institute: string }) {
  if (!institute || getOperatorRole() !== "responsable_institut") return null;
  return <CampaignDirectory key={JSON.stringify([institute, getAccessToken()])} institute={institute} />;
}
function CampaignDirectory({ institute }: { institute: string }) {
  const [audienceVersion, refreshAudiences] = useState(0);
  const token = getAccessToken(), sequence = useRef(0);
  const [page, setPage] = useState<Catalog>(), [selected, select] = useState<CampaignOriginal>();
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false), [error, setError] = useState<string>();
  const base = `/marketing/institutes/${encodeURIComponent(institute)}/campaigns`;
  async function load(offset = 0) {
    const request = ++sequence.current, current = () => request === sequence.current && token === getAccessToken();
    setOffset(offset); setLoading(true); setPage(undefined); select(undefined); setError(undefined);
    try {
      const result = await apiGet<Catalog>(`${base}?offset=${offset}&limit=20`);
      if (!await validCampaignCatalog(result, institute, offset, 20)) throw new Error("Invalid catalog");
      if (current()) setPage(result);
    } catch { if (current()) setError("Catalogue à vérifier. Relancez la lecture."); }
    finally { if (current()) setLoading(false); }
  }
  useEffect(() => { void load(); return () => { sequence.current++; }; }, []);
  return <section className="customer-crm" aria-label="Marketing">
    <h2>Campagnes marketing</h2>
    <MarketingAudiencePanel institute={institute} onCaptured={() => refreshAudiences(v => v + 1)} />
    <MarketingAudienceCatalog key={audienceVersion} institute={institute} />
    <MarketingTemplatePanel institute={institute} />
    <MarketingCampaignCreator institute={institute} onChanged={() => void load()} />
    <p>Consultez le contenu retenu, son audience et l’historique de revue et d’approbation.</p>
    <button onClick={() => void load(offset)} disabled={loading}>Actualiser les campagnes</button>
    {loading && <p role="status">Chargement des campagnes…</p>}{error && <p role="alert">{error}</p>}
    {page && <><p>{page.total === 0 ? "Aucune campagne enregistrée." : `${page.offset + 1}–${page.offset + page.items.length} sur ${page.total} campagnes`}</p>
      <ul>{page.items.map(o => <li key={o.revision.campaign_id} style={{ maxWidth: "100%" }}><button style={{ maxWidth: "100%", overflowWrap: "anywhere" }} aria-pressed={selected?.revision.campaign_id === o.revision.campaign_id}
        onClick={() => select(o)}>{o.revision.content.subject || o.revision.content.body.slice(0, 80)} · {stages[o.revision.state]} · {o.revision.content.channel}</button></li>)}</ul>
      <button disabled={page.offset === 0} onClick={() => void load(Math.max(0, page.offset - 20))}>Campagnes précédentes</button>
      <button disabled={page.offset + page.items.length >= page.total} onClick={() => void load(page.offset + 20)}>Campagnes suivantes</button>
    </>}
    {selected && <CampaignHistory key={selected.revision.campaign_id} institute={institute} selected={selected} />}
  </section>;
}
function CampaignHistory({ institute, selected }: { institute: string; selected: CampaignOriginal }) {
  const token = getAccessToken(), sequence = useRef(0), root = selected.revision.campaign_id;
  const [original, setOriginal] = useState<CampaignOriginal>(), [page, setPage] = useState<CampaignAuditPage>();
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false), [error, setError] = useState<string>();
  const base = `/marketing/institutes/${encodeURIComponent(institute)}/campaigns`;
  async function load(offset = 0) {
    const request = ++sequence.current, current = () => request === sequence.current && token === getAccessToken();
    setOffset(offset); setLoading(true); setOriginal(undefined); setPage(undefined); setError(undefined);
    try {
      const head = await apiGet<CampaignOriginal>(`${base}/${encodeURIComponent(root)}/current`);
      if (!await validCampaignOriginal(head, institute) || head.revision.campaign_id !== root) throw new Error("Invalid head");
      if (!current()) return;
      const [byId, audit] = await Promise.all([
        apiGet<CampaignOriginal>(`${base}/${encodeURIComponent(head.revision.id)}`),
        apiGet<CampaignAuditPage>(`${base}/${encodeURIComponent(root)}/audit?offset=${offset}&limit=20`),
      ]);
      if (!await sameCampaignOriginal(head, byId, institute) || !await validCampaignAuditPage(audit, institute, root, offset, 20)) throw new Error("Invalid history");
      if (current()) { setOriginal(head); setPage(audit); }
    } catch { if (current()) setError("Historique à vérifier. Relancez la lecture."); }
    finally { if (current()) setLoading(false); }
  }
  useEffect(() => { void load(); return () => { sequence.current++; }; }, []);
  return <section aria-label="Historique de campagne">
    <h3>Contenu et historique</h3><button disabled={loading} onClick={() => void load(offset)}>Actualiser l’historique</button>
    {loading && <p role="status">Chargement de l’historique…</p>}{error && <p role="alert">{error}</p>}
    {original && <><p>{stages[original.revision.state]} · {original.revision.content.channel} · origine {original.revision.content.origin === "ai" ? "IA déclarée" : "humaine"}</p>
      {original.revision.content.subject && <h4>{original.revision.content.subject}</h4>}
      <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{original.revision.content.body}</p>
      <p>{original.revision.content.audience.customer_ids.length} destinataires retenus · audience {original.revision.content.audience.id}</p>
      <p>Aucun envoi enregistré. Les permissions retenues ne constituent pas une autorisation d’envoi actuelle.</p></>}
    <MarketingCampaignActions institute={institute} campaign={root} original={original} onChanged={() => void load()} />
    <MarketingCampaignCreator institute={institute} campaign={root} original={original} onChanged={() => void load()} />
    <MarketingRecipientPanel institute={institute} original={original} />
    {page && <><p>{page.originals.length ? `${page.offset + 1}–${page.offset + page.originals.length}` : "0"} sur {page.total} révisions</p>
      {page.originals.map(o => <article key={o.revision.id} style={{ overflowWrap: "anywhere" }}><h4>{stages[o.revision.state]}</h4>
        <p>{o.revision.actor_id} · {o.revision.created_at} · {o.revision.reason}</p>
        <p>Révision {o.revision.id} · précédente : {o.revision.previous_id || "Aucune"}</p></article>)}
      <button disabled={page.offset === 0} onClick={() => void load(Math.max(0, page.offset - 20))}>Révisions précédentes</button>
      <button disabled={page.offset + page.originals.length >= page.total} onClick={() => void load(page.offset + 20)}>Révisions suivantes</button>
    </>}
  </section>;
}
