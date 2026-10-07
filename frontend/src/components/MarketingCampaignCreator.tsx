import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { certificationInstant as instant } from "../certification-utils";
import { validAudienceCatalog, validAudienceOriginal, sameAudienceOriginal, type AudienceCatalog, type AudienceOriginal } from "../marketing-audience-utils";
import { validTemplateCatalog, validTemplateOriginal, sameTemplateOriginal, type TemplateCatalog, type TemplateOriginal } from "../marketing-template-utils";
import { validCampaignRequest, validCampaignOriginal, matchesCampaignReceipt, sameCampaignOriginal, type CampaignRequest, type CampaignOriginal } from "../marketing-campaign-utils";
type EditorProps = { institute: string; campaign?: string; original?: CampaignOriginal; onChanged?: () => void };
export function MarketingCampaignCreator({ institute, campaign, original, onChanged }: EditorProps) {
  if (!institute || getOperatorRole() !== "responsable_institut") return null;
  return <Creator key={JSON.stringify([institute, campaign, getAccessToken()])} institute={institute} campaign={campaign} original={original} onChanged={onChanged} />;
}
function Creator({ institute, campaign, original, onChanged }: EditorProps) {
  const token = getAccessToken(), actor = getOperatorSubject(), mounted = useRef(false), pending = useRef(false);
  const base = `/marketing/institutes/${encodeURIComponent(institute)}`, storage = campaign
    ? `flowpilot.marketing-campaign-edit-request:${JSON.stringify([institute, actor, campaign])}`
    : `flowpilot.marketing-campaign-create-request:${JSON.stringify([institute, actor])}`;
  const validTerms = (v: unknown): v is CampaignRequest => validCampaignRequest(v)
    && (campaign ? v.action === "edit" && v.campaign_id === campaign : v.action === "create");
  const [predecessor, setPredecessor] = useState<string | null>(null);
  const [saved, save] = useState<{ terms?: CampaignRequest; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storage); if (!raw) return {}; const v = JSON.parse(raw); return validTerms(v) ? { terms: v } : { invalid: true }; }
    catch { return { invalid: true }; }
  });
  const [open, setOpen] = useState(false), [channel, setChannel] = useState(""), [mode, setMode] = useState(""), [origin, setOrigin] = useState("");
  const [subject, setSubject] = useState(""), [body, setBody] = useState(""), [reason, setReason] = useState("");
  const [audiences, setAudiences] = useState<AudienceCatalog>(), [templates, setTemplates] = useState<TemplateCatalog>();
  const [audience, selectAudience] = useState<AudienceOriginal>(), [template, selectTemplate] = useState<TemplateOriginal>();
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>(), [receipt, setReceipt] = useState<CampaignOriginal>(), [rejected, setRejected] = useState(false);
  const current = () => mounted.current && token === getAccessToken();
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const frozen = busy || !!saved.terms || !!saved.invalid;
  async function prepare() {
    if (frozen || !current()) return;
    if (!campaign) { setOpen(true); setReceipt(undefined); return; }
    if (!original) return;
    setBusy(true); setOpen(false); setReceipt(undefined); setError(undefined); setPredecessor(null);
    try {
      const head = await apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(campaign)}/current`);
      if (!current()) return;
      if (!await validCampaignOriginal(head, institute) || head.revision.campaign_id !== campaign) throw new Error("Campagne courante à vérifier.");
      if (!current()) return;
      const [byId, source, selectedTemplate] = await Promise.all([
        apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(head.revision.id)}`),
        apiGet<unknown>(`${base}/audience-captures/${encodeURIComponent(head.revision.content.audience.id)}`),
        head.revision.content.template_original_id === null ? Promise.resolve(null)
          : apiGet<unknown>(`${base}/templates/${encodeURIComponent(head.revision.content.template_original_id)}`),
      ]);
      if (!current()) return;
      if (!await sameCampaignOriginal(head, byId, institute) || !validAudienceOriginal(source, institute)
        || source.id !== head.revision.content.audience.id || source.request.channel !== head.revision.content.channel
        || source.summary.eligible_count !== head.revision.content.audience.customer_ids.length
        || instant(source.captured_at) !== instant(head.revision.content.audience.captured_at)) throw new Error("Sources de correction à vérifier.");
      if (!current()) return;
      const sourceKey = await apiGet<unknown>(`${base}/audience-captures/original/${encodeURIComponent(source.request.idempotency_key)}`);
      if (!current()) return;
      if (!validAudienceOriginal(sourceKey, institute) || !sameAudienceOriginal(source, sourceKey)) throw new Error("Audience de correction à vérifier.");
      if (selectedTemplate !== null && (!validTemplateOriginal(selectedTemplate, institute)
        || selectedTemplate.id !== head.revision.content.template_original_id || instant(selectedTemplate.created_at)! > instant(head.revision.created_at)!
        || selectedTemplate.content.channel !== head.revision.content.channel || selectedTemplate.content.origin !== head.revision.content.origin
        || selectedTemplate.content.subject !== head.revision.content.subject || selectedTemplate.content.body !== head.revision.content.body)) throw new Error("Template de correction à vérifier.");
      setPredecessor(head.revision.id); selectAudience(source); selectTemplate(selectedTemplate === null ? undefined : selectedTemplate as TemplateOriginal);
      setChannel(head.revision.content.channel); setMode(selectedTemplate ? "template" : "literal"); setOrigin(head.revision.content.origin);
      setSubject(head.revision.content.subject || ""); setBody(head.revision.content.body); setReason(""); setAudiences(undefined); setTemplates(undefined); setOpen(true);
    } catch (e) { if (current()) setError(e instanceof Error ? e.message : "Correction à reprendre."); }
    finally { if (current()) setBusy(false); }
  }
  async function sources(kind: "audiences" | "templates", offset = 0) {
    if (frozen || !channel || !current()) return;
    setBusy(true); setError(undefined); if (kind === "audiences") setAudiences(undefined); else setTemplates(undefined);
    try {
      const v = await apiGet<unknown>(`${base}/${kind === "audiences" ? "audience-captures" : "templates"}?offset=${offset}&limit=20`); if (!current()) return;
      if (kind === "audiences") { if (!validAudienceCatalog(v, institute, offset, 20)) throw new Error("Catalogue d’audiences à vérifier."); setAudiences(v); }
      else { if (!validTemplateCatalog(v, institute, offset, 20)) throw new Error("Catalogue de templates à vérifier."); setTemplates(v); }
    } catch (e) { if (current()) setError(e instanceof Error ? e.message : "Sources à reprendre."); }
    finally { if (current()) setBusy(false); }
  }
  async function chooseAudience(o: AudienceOriginal) {
    if (frozen || o.request.channel !== channel || !o.summary.eligible_count || !current()) return;
    setBusy(true); setError(undefined); selectAudience(undefined);
    try {
      const [id, key] = await Promise.all([apiGet<unknown>(`${base}/audience-captures/${encodeURIComponent(o.id)}`),
        apiGet<unknown>(`${base}/audience-captures/original/${encodeURIComponent(o.request.idempotency_key)}`)]); if (!current()) return;
      if (!validAudienceOriginal(id, institute) || !validAudienceOriginal(key, institute) || !sameAudienceOriginal(o, id) || !sameAudienceOriginal(o, key)) throw new Error("Audience source à vérifier.");
      selectAudience(id);
    } catch (e) { if (current()) setError(e instanceof Error ? e.message : "Audience à reprendre."); }
    finally { if (current()) setBusy(false); }
  }
  async function chooseTemplate(o: TemplateOriginal) {
    if (frozen || o.content.channel !== channel || !current()) return;
    setBusy(true); setError(undefined); selectTemplate(undefined);
    try {
      const id = await apiGet<unknown>(`${base}/templates/${encodeURIComponent(o.id)}`); if (!current()) return;
      if (!validTemplateOriginal(id, institute) || !sameTemplateOriginal(o, id)) throw new Error("Template source à vérifier.");
      selectTemplate(id); setOrigin(id.content.origin); setSubject(id.content.subject || ""); setBody(id.content.body);
    } catch (e) { if (current()) setError(e instanceof Error ? e.message : "Template à reprendre."); }
    finally { if (current()) setBusy(false); }
  }
  async function run(terms: CampaignRequest) {
    if (!current() || pending.current || !actor || saved.invalid || !validTerms(terms)) return;
    pending.current = true; setBusy(true); setError(undefined); setReceipt(undefined); setRejected(false);
    let posting = false, returned = false;
    try {
      const raw = JSON.stringify(terms); sessionStorage.setItem(storage, raw); save({ terms });
      const path = `${base}/campaigns/original/${encodeURIComponent(terms.idempotency_key)}`;
      let result = await apiGet<CampaignOriginal | null>(path); if (!current()) return;
      if (result === null) { posting = true; result = await apiPost<CampaignOriginal>(`${base}/campaigns`, terms); returned = true; }
      if (!current()) return;
      if (!await validCampaignOriginal(result, institute) || !result || !matchesCampaignReceipt(result, terms, actor)) throw new Error("Brouillon original à vérifier.");
      if (!current()) return;
      const [key, id, head] = await Promise.all([apiGet<CampaignOriginal>(path), apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(result.revision.id)}`),
        apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(result.revision.campaign_id)}/current`)]); if (!current()) return;
      if (!await sameCampaignOriginal(result, key, institute) || !await sameCampaignOriginal(result, id, institute)
        || !await validCampaignOriginal(head, institute) || head.revision.campaign_id !== result.revision.campaign_id) throw new Error("Original ou campagne courante à vérifier.");
      if (!current()) return;
      if (sessionStorage.getItem(storage) !== raw) throw new Error("Demande conservée à vérifier.");
      sessionStorage.removeItem(storage); save({}); setReceipt(result); setOpen(false); setPredecessor(null); selectAudience(undefined); selectTemplate(undefined);
      setAudiences(undefined); setTemplates(undefined); setChannel(""); setMode(""); setOrigin(""); setSubject(""); setBody(""); setReason(""); onChanged?.();
    } catch (e) { if (current()) { setError(e instanceof Error ? e.message : "Brouillon à reprendre."); setRejected(posting && !returned && e instanceof ApiError && [400, 422].includes(e.status)); } }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  function submit(event: FormEvent) {
    event.preventDefault(); if (frozen || !actor || !audience || campaign && !predecessor || !["literal", "template"].includes(mode) || mode === "template" && !template) return;
    const terms = { action: campaign ? "edit" : "create", campaign_id: campaign || null, expected_revision_id: campaign ? predecessor : null, reason: reason.trim(), idempotency_key: crypto.randomUUID(),
      content: { channel, origin, subject: channel === "email" ? subject : null, body, audience_id: audience.id, template_original_id: template?.id || null } };
    if (!validTerms(terms)) { setError("Vérifiez le contenu, les sources et le motif."); return; } void run(terms);
  }
  return <section aria-label={campaign ? "Modifier la campagne" : "Créer une campagne"}><h3>{campaign ? "Modifier la campagne" : "Créer une campagne"}</h3>
    {error && <p role="alert">{error}</p>}{busy && <p role="status">Vérification des sources et du brouillon…</p>}
    {saved.invalid && <p role="alert">Demande conservée invalide : aucune écriture possible.</p>}
    {saved.terms && <><p>Brouillon conservé : {saved.terms.reason}</p><button disabled={busy} onClick={() => void run(saved.terms!)}>{campaign ? "Reprendre la correction conservée" : "Reprendre le brouillon conservé"}</button></>}
    {rejected && <button onClick={() => { if (!saved.terms || sessionStorage.getItem(storage) !== JSON.stringify(saved.terms)) return;
      sessionStorage.removeItem(storage); save({}); setRejected(false); }}>Corriger le brouillon refusé</button>}
    <button disabled={frozen || !!campaign && !original} onClick={() => void prepare()}>{campaign ? "Préparer une correction de campagne" : "Préparer une campagne"}</button>
    {open && <form onSubmit={submit}><fieldset className="marketing-audience-fields" disabled={frozen}><legend>Sources et contenu du brouillon</legend>
      <label>Canal de campagne<select required value={channel} onChange={e => { setChannel(e.target.value); selectAudience(undefined); selectTemplate(undefined); setAudiences(undefined); setTemplates(undefined); }}>
        <option value="">Choisir</option><option value="email">Email</option><option value="sms">SMS</option><option value="push">Push</option></select></label>
      <button type="button" disabled={!channel} onClick={() => void sources("audiences")}>Choisir une audience source</button>
      {audiences && <div className="marketing-source-options" style={{ gridColumn: "1 / -1" }}><p>{audiences.total} captures · page à partir de {audiences.offset + 1}</p>
        {audiences.items.map(o => <button type="button" key={o.id} disabled={o.request.channel !== channel || o.summary.eligible_count === 0}
          onClick={() => void chooseAudience(o)}>{o.request.reason} · {o.request.channel} · {o.summary.eligible_count} éligibles</button>)}
        <button type="button" disabled={audiences.offset === 0} onClick={() => void sources("audiences", Math.max(0, audiences.offset - 20))}>Sources audience précédentes</button>
        <button type="button" disabled={audiences.offset + audiences.items.length >= audiences.total} onClick={() => void sources("audiences", audiences.offset + 20)}>Sources audience suivantes</button></div>}
      {audience && <p>Audience sélectionnée : {audience.id} · {audience.summary.eligible_count} destinataires retenus</p>}
      <label>Source du texte<select required value={mode} onChange={e => { setMode(e.target.value); selectTemplate(undefined); setTemplates(undefined); }}>
        <option value="">Choisir</option><option value="literal">Texte explicite</option><option value="template">Template retenu</option></select></label>
      {mode === "template" && <button type="button" disabled={!channel} onClick={() => void sources("templates")}>Choisir un template source</button>}
      {templates && <div className="marketing-source-options" style={{ gridColumn: "1 / -1" }}><p>{templates.total} templates · page à partir de {templates.offset + 1}</p>
        {templates.items.map(o => <button type="button" key={o.template_id} disabled={o.content.channel !== channel} onClick={() => void chooseTemplate(o)}>{o.content.name} · {o.content.channel}</button>)}
        <button type="button" disabled={templates.offset === 0} onClick={() => void sources("templates", Math.max(0, templates.offset - 20))}>Sources template précédentes</button>
        <button type="button" disabled={templates.offset + templates.items.length >= templates.total} onClick={() => void sources("templates", templates.offset + 20)}>Sources template suivantes</button></div>}
      {template && <p>Template sélectionné : {template.content.name} · original {template.id}</p>}
      <label>Origine de campagne<select required disabled={mode === "template"} value={origin} onChange={e => setOrigin(e.target.value)}><option value="">Choisir</option><option value="human">Humaine</option><option value="ai">IA déclarée</option></select></label>
      {channel === "email" && <label>Objet de campagne<input required disabled={mode === "template"} value={subject} onChange={e => setSubject(e.target.value)} /></label>}
      <label className="marketing-template-body">Texte de campagne<textarea required disabled={mode === "template"} value={body} onChange={e => setBody(e.target.value)} /></label>
      <label>Motif du brouillon<input required minLength={3} maxLength={240} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <button disabled={!actor || !audience || !!campaign && !predecessor || mode === "template" && !template}>{campaign ? "Enregistrer la correction de campagne" : "Enregistrer le brouillon"}</button>
    </fieldset></form>}
    {receipt && <div role="status"><p>Brouillon original vérifié : {receipt.revision.id}</p><p>{receipt.revision.content.audience.customer_ids.length} destinataires retenus · DRAFT</p></div>}
    <p>Les sources sont historiques. Aucun envoi n’est réalisé lors de la création du brouillon.</p>
    {campaign && <p>La correction revient au brouillon et efface la revue et l’approbation précédentes. Une nouvelle validation est nécessaire.</p>}
  </section>;
}
