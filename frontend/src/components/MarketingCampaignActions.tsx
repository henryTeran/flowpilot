import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { validCampaignRequest, validCampaignOriginal, matchesCampaignReceipt, sameCampaignOriginal,
  type CampaignRequest, type CampaignOriginal } from "../marketing-campaign-utils";

export function MarketingCampaignActions({ institute, campaign, original, onChanged }: {
  institute: string; campaign: string; original?: CampaignOriginal; onChanged: () => void;
}) {
  if (!institute || !campaign || getOperatorRole() !== "responsable_institut") return null;
  return <Actions key={JSON.stringify([institute, campaign, getAccessToken()])} institute={institute} campaign={campaign} original={original} onChanged={onChanged} />;
}
function Actions({ institute, campaign, original, onChanged }: {
  institute: string; campaign: string; original?: CampaignOriginal; onChanged: () => void;
}) {
  const token = getAccessToken(), actor = getOperatorSubject();
  const storage = `flowpilot.marketing-campaign-request:${JSON.stringify([institute, actor, campaign])}`;
  const base = `/marketing/institutes/${encodeURIComponent(institute)}/campaigns`;
  const validTerms = (value: unknown): value is CampaignRequest => validCampaignRequest(value)
    && value.campaign_id === campaign && ["review", "approve"].includes(value.action);
  const [saved, save] = useState<{ terms?: CampaignRequest; invalid?: boolean }>(() => {
    try {
      const raw = sessionStorage.getItem(storage); if (!raw) return {};
      const value = JSON.parse(raw); return validTerms(value) ? { terms: value } : { invalid: true };
    } catch { return { invalid: true }; }
  });
  const [reason, setReason] = useState(""), [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>(), [success, setSuccess] = useState<string>();
  const [rejected, setRejected] = useState(false);
  const mounted = useRef(false), pending = useRef(false);
  const current = () => mounted.current && token === getAccessToken();
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function run(terms: CampaignRequest) {
    if (!current() || pending.current || !actor || saved.invalid || !validTerms(terms)) return;
    pending.current = true; setBusy(true); setError(undefined); setSuccess(undefined); setRejected(false);
    let posting = false, returned = false;
    try {
      const raw = JSON.stringify(terms); sessionStorage.setItem(storage, raw); save({ terms });
      const path = `${base}/original/${encodeURIComponent(terms.idempotency_key)}`;
      let receipt = await apiGet<CampaignOriginal | null>(path); if (!current()) return;
      if (receipt === null) { posting = true; receipt = await apiPost<CampaignOriginal>(base, terms); returned = true; }
      if (!current()) return;
      if (!await validCampaignOriginal(receipt, institute) || !receipt || !matchesCampaignReceipt(receipt, terms, actor)) throw new Error("Reçu de campagne à vérifier.");
      if (!current()) return;
      const [byKey, byId, head] = await Promise.all([
        apiGet<CampaignOriginal>(path), apiGet<CampaignOriginal>(`${base}/${encodeURIComponent(receipt.revision.id)}`),
        apiGet<CampaignOriginal>(`${base}/${encodeURIComponent(campaign)}/current`),
      ]);
      if (!current()) return;
      if (!await sameCampaignOriginal(receipt, byKey, institute) || !await sameCampaignOriginal(receipt, byId, institute)
        || !await validCampaignOriginal(head, institute) || head.revision.campaign_id !== campaign) throw new Error("Original ou sélection courante à vérifier.");
      if (!current()) return;
      if (sessionStorage.getItem(storage) !== raw) throw new Error("Demande conservée à vérifier.");
      sessionStorage.removeItem(storage); save({}); setReason(""); setSuccess("Original vérifié et campagne courante relue.");
      onChanged();
    } catch (e) {
      if (current()) { setError(e instanceof Error ? e.message : "Demande à reprendre.");
        setRejected(posting && !returned && e instanceof ApiError && [400, 422].includes(e.status)); }
    } finally { pending.current = false; if (current()) setBusy(false); }
  }
  function stage(action: "review" | "approve") {
    if (!original || busy || saved.terms || saved.invalid || !actor || original.revision.campaign_id !== campaign
      || original.revision.state !== (action === "review" ? "DRAFT" : "REVIEW")) return;
    const terms: CampaignRequest = { action, campaign_id: campaign, expected_revision_id: original.revision.id, content: null,
      reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    if (!validTerms(terms)) { setError("Déclarez un motif de 3 à 240 caractères."); return; }
    void run(terms);
  }
  const frozen = busy || !!saved.terms || !!saved.invalid;
  return <section aria-label="Validation de campagne"><h3>Revue et approbation</h3>
    {error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
    {saved.invalid && <p role="alert">Demande conservée invalide : aucune écriture possible.</p>}
    {saved.terms && <><p>Demande conservée : {saved.terms.action === "review" ? "revue" : "approbation"} · {saved.terms.reason}</p>
      <button disabled={busy} onClick={() => void run(saved.terms!)}>Reprendre la validation conservée</button></>}
    {rejected && <button onClick={() => {
      if (!saved.terms || sessionStorage.getItem(storage) !== JSON.stringify(saved.terms)) return;
      sessionStorage.removeItem(storage); save({}); setRejected(false); onChanged();
    }}>Corriger la validation refusée</button>}
    <label>Motif de validation<input value={reason} maxLength={240} disabled={frozen || !original}
      onChange={e => setReason(e.target.value)} /></label>
    <button disabled={frozen || !actor || original?.revision.state !== "DRAFT"} onClick={() => stage("review")}>Soumettre en revue</button>
    <button disabled={frozen || !actor || original?.revision.state !== "REVIEW"} onClick={() => stage("approve")}>Approuver le contenu et l’audience</button>
  </section>;
}
