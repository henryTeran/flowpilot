import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { validCampaignOriginal, sameCampaignOriginal, type CampaignOriginal } from "../marketing-campaign-utils";
import { validContactOriginal, sameContactOriginal, type ContactOriginal } from "../marketing-contact-utils";
import { validDispatchAccount, validDispatchAccountPage, validDispatchRequest, validDispatchIntent, sameDispatchIntent,
  matchesDispatchReceipt, sameDispatchTerms, type DispatchAccount, type DispatchIntent, type DispatchRequest, type DispatchPage } from "../marketing-dispatch-utils";
type Stored = { request: DispatchRequest; account: DispatchAccount };
type Props = { institute: string; campaign: CampaignOriginal; customer: string; contact: ContactOriginal | null; eligible: boolean };
export function MarketingDispatchPrepare(props: Props) {
  if (!props.institute || props.campaign.revision.institute_id !== props.institute || getOperatorRole() !== "responsable_institut") return null;
  return <Prepare key={JSON.stringify([props.institute, props.campaign.revision.campaign_id, props.customer, getAccessToken()])} {...props} />;
}
function Prepare({ institute, campaign, customer, contact, eligible }: Props) {
  const token = getAccessToken(), actor = getOperatorSubject(), root = campaign.revision.campaign_id, channel = campaign.revision.content.channel;
  const base = `/marketing/institutes/${encodeURIComponent(institute)}`, storage = `flowpilot.marketing-dispatch-request:${JSON.stringify([institute, actor, root, customer])}`;
  function validStored(v: unknown): v is Stored {
    const s = v as Stored;
    return !!s && typeof s === "object" && Object.keys(s).length === 2 && validDispatchRequest(s.request)
      && s.request.campaign_id === root && s.request.customer_id === customer && validDispatchAccount(s.account, institute)
      && s.account.account_id === s.request.account_id;
  }
  const [saved, save] = useState<{ terms?: Stored; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storage); if (!raw) return {}; const value = JSON.parse(raw);
      return validStored(value) ? { terms: value } : { invalid: true }; } catch { return { invalid: true }; }
  });
  const [accounts, setAccounts] = useState<DispatchPage<DispatchAccount>>(), [offset, setOffset] = useState(0);
  const [selected, select] = useState<DispatchAccount>(), [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>(), [receipt, setReceipt] = useState<DispatchIntent>();
  const [rejected, setRejected] = useState(false);
  const mounted = useRef(false), pending = useRef(false), sequence = useRef(0);
  const current = () => mounted.current && token === getAccessToken();
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; sequence.current++; }; }, []);
  const [absent, setAbsent] = useState(false);
  const frozen = busy || !!saved.terms || !!saved.invalid;
  async function verifyOriginal(original: DispatchIntent) {
    if (!await validDispatchIntent(original, institute) || original.request.campaign_id !== root || original.request.customer_id !== customer) throw new Error("Intention de destinataire à vérifier.");
    const r = original.request, contacts = `${base}/customers/${encodeURIComponent(customer)}/contact-declarations`;
    const [byKey, byId, approved, contactId, contactKey, head] = await Promise.all([
      apiGet<DispatchIntent>(`${base}/dispatch-intents/original/${encodeURIComponent(r.idempotency_key)}`), apiGet<DispatchIntent>(`${base}/dispatch-intents/${encodeURIComponent(original.id)}`),
      apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(r.expected_revision_id)}`),
      apiGet<ContactOriginal>(`${contacts}/${encodeURIComponent(r.expected_contact_id)}`),
      apiGet<ContactOriginal>(`${contacts}/original/${encodeURIComponent(original.submission.eligibility.original.idempotency_key)}`),
      apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(root)}/current`),
    ]);
    if (!current()) return false;
    if (!await sameDispatchIntent(original, byKey, institute) || !await sameDispatchIntent(original, byId, institute)
      || !await validCampaignOriginal(approved, institute) || approved.revision.campaign_id !== root
      || !sameDispatchTerms(approved.revision, original.submission.eligibility.campaign)
      || ![contactId, contactKey].every(value => validContactOriginal(value, institute, customer) && sameContactOriginal(original!.submission.eligibility.original, value))
      || !await validCampaignOriginal(head, institute) || head.revision.campaign_id !== root) throw new Error("Originaux de préparation à vérifier.");
    if (!current()) return false;
    return current();
  }
  const approvalId = campaign.revision.state === "APPROVE" ? campaign.revision.id : campaign.revision.state === "SEND" ? campaign.revision.previous_id : null;
  async function lookup() {
    if (!approvalId) throw new Error("Approbation de campagne à vérifier.");
    const original = await apiGet<DispatchIntent | null>(`${base}/campaigns/${encodeURIComponent(root)}/dispatch-intents/recipient/${encodeURIComponent(customer)}?expected_revision_id=${encodeURIComponent(approvalId)}`);
    if (!current()) return undefined;
    const head = await apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(root)}/current`);
    if (!current()) return undefined;
    if (!await sameCampaignOriginal(head, campaign, institute)) throw new Error("Campagne courante à relire.");
    if (original === null) return null;
    if (!await validDispatchIntent(original, institute) || original.request.expected_revision_id !== approvalId || !await verifyOriginal(original)) throw new Error("Intention conservée à vérifier.");
    return original;
  }
  async function discover() {
    if (!current() || pending.current || frozen || receipt || !approvalId) return;
    pending.current = true; sequence.current++; setBusy(true); setError(undefined); setAbsent(false); setAccounts(undefined); select(undefined);
    try {
      const original = await lookup();
      if (!current()) return;
      if (original) { setReceipt(original); setAccounts(undefined); select(undefined); setReason(""); }
      else if (original === null) setAbsent(true);
    } catch { if (current()) setError("Intention conserv\u00e9e \u00e0 v\u00e9rifier. R\u00e9essayez la lecture."); }
    finally { pending.current = false; if (current()) setBusy(false); }
  }

  async function loadAccounts(target = offset) {
    if (!current() || pending.current || frozen || !eligible || receipt) return;
    const request = ++sequence.current; setOffset(target); setBusy(true); setAccounts(undefined); select(undefined); setError(undefined);
    try {
      const original = await lookup();
      if (!current() || sequence.current !== request) return;
      if (original) { setReceipt(original); setReason(""); return; }
      if (original !== null) return;
      const page = await apiGet<DispatchPage<DispatchAccount>>(`${base}/dispatch-accounts?channel=${channel}&offset=${target}&limit=20`);
      if (!current() || sequence.current !== request) return;
      if (!validDispatchAccountPage(page, institute, channel, target, 20)) throw new Error("Comptes autorisés à vérifier.");
      if (current() && sequence.current === request) setAccounts(page);
    } catch (e) { if (current() && sequence.current === request) setError(e instanceof Error ? e.message : "Comptes à relire."); }
    finally { if (current() && sequence.current === request) setBusy(false); }
  }
  async function run(terms: Stored) {
    if (!current() || pending.current || !actor || saved.invalid || !validStored(terms)) return;
    pending.current = true; sequence.current++; setBusy(true); setError(undefined); setReceipt(undefined); setRejected(false);
    const hadStored = !!saved.terms;
    let posting = false, returned = false;
    try {
      const raw = JSON.stringify(terms); sessionStorage.setItem(storage, raw); save({ terms });
      const path = `${base}/dispatch-intents/original/${encodeURIComponent(terms.request.idempotency_key)}`;
      let original = await apiGet<DispatchIntent | null>(path); if (!current()) return;
      if (original === null) {
        if (!eligible || !contact) throw new Error("Relisez les contacts courants avant une nouvelle préparation.");
        const r = terms.request, contacts = `${base}/customers/${encodeURIComponent(customer)}/contact-declarations`;
        const [head, approved, currentContact, account] = await Promise.all([
          apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(root)}/current`),
          apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(r.expected_revision_id)}`),
          apiGet<ContactOriginal | null>(contacts + "/current"),
          apiGet<DispatchAccount>(`${base}/dispatch-accounts/${encodeURIComponent(r.account_id)}?channel=${terms.account.channel}`),
        ]);
        if (!current()) return;
        if (!await sameCampaignOriginal(head, campaign, institute) || !await validCampaignOriginal(approved, institute)
          || approved.revision.id !== r.expected_revision_id || approved.revision.campaign_id !== root || approved.revision.state !== "APPROVE"
          || !sameDispatchTerms(approved.revision.content, head.revision.content)
          || !(head.revision.state === "APPROVE" && head.revision.id === r.expected_revision_id || head.revision.state === "SEND" && head.revision.previous_id === r.expected_revision_id)
          || !validContactOriginal(currentContact, institute, customer) || currentContact.id !== r.expected_contact_id || !sameContactOriginal(contact, currentContact)
          || !validDispatchAccount(account, institute, terms.account.channel) || !sameDispatchTerms(account, terms.account)) throw new Error("Campagne, contact ou compte courant à relire.");
        const [contactId, contactKey] = await Promise.all([apiGet<ContactOriginal>(`${contacts}/${encodeURIComponent(currentContact.id)}`),
          apiGet<ContactOriginal>(`${contacts}/original/${encodeURIComponent(currentContact.idempotency_key)}`)]);
        if (!current()) return;
        if (![contactId, contactKey].every(value => validContactOriginal(value, institute, customer) && sameContactOriginal(currentContact, value))) throw new Error("Contact d’origine à vérifier.");
        posting = true; original = await apiPost<DispatchIntent>(base + "/dispatch-intents", terms.request); returned = true;
      }
      if (!current()) return;
      if (!await validDispatchIntent(original, institute) || !original || !matchesDispatchReceipt(original, terms.request, actor, terms.account)) throw new Error("Intention d’origine à vérifier.");
      if (!await verifyOriginal(original)) return;
      if (sessionStorage.getItem(storage) !== raw) throw new Error("Demande conservée à vérifier.");
      sessionStorage.removeItem(storage); save({}); setReason(""); select(undefined); setAccounts(undefined); setReceipt(original);
    } catch (e) { if (current()) {
      // A newly generated request has never attempted POST; retain every older/uncertain request.
      if (!hadStored && !posting && sessionStorage.getItem(storage) === JSON.stringify(terms)) { sessionStorage.removeItem(storage); save({}); }
      setError(e instanceof Error ? e.message : "Préparation à reprendre.");
      setRejected(posting && !returned && e instanceof ApiError && [400, 422].includes(e.status)); } }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  const applicationMismatch = !!selected && channel === "push" && selected.push_application !== contact?.declaration.communications.find(value => value.channel === "push")?.destination?.push_application;
  function prepare() {
    if (frozen || !actor || !selected || !contact || !eligible || receipt || applicationMismatch) return;
    const approval = campaign.revision.state === "APPROVE" ? campaign.revision.id : campaign.revision.state === "SEND" ? campaign.revision.previous_id : null;
    if (!approval) return;
    const terms: Stored = { account: selected, request: { campaign_id: root, expected_revision_id: approval, customer_id: customer,
      expected_contact_id: contact.id, account_id: selected.account_id, reason: reason.trim(), idempotency_key: crypto.randomUUID() } };
    if (!validStored(terms)) { setError("Déclarez un motif de 3 à 240 caractères."); return; } void run(terms);
  }
  return <section aria-label="Préparation de destinataire"><h5>Préparer le destinataire</h5>
    {error && <p role="alert">{error}</p>}{busy && <p role="status">Vérification de la préparation…</p>}
    {saved.invalid && <p role="alert">Demande conservée invalide : aucune écriture possible.</p>}
    {saved.terms && <><p>Préparation conservée : {saved.terms.request.reason}</p>
      <button disabled={busy} onClick={() => void run(saved.terms!)}>Reprendre la préparation conservée</button></>}
    {rejected && <button onClick={() => { if (!saved.terms || sessionStorage.getItem(storage) !== JSON.stringify(saved.terms)) return;
      sessionStorage.removeItem(storage); save({}); setRejected(false); }}>Corriger la préparation refusée</button>}
    <button disabled={frozen || !!receipt || !approvalId} onClick={() => void discover()}>Retrouver l'intention de ce destinataire</button>
    {absent && !receipt && <p>Aucune intention conservée pour cette approbation.</p>}
    {receipt && <p role="status">Intention originale vérifiée : {receipt.id}. Cette action ne déclenche aucun envoi.</p>}
    <button disabled={frozen || !eligible || !!receipt} onClick={() => void loadAccounts()}>Choisir un compte autorisé</button>
    {accounts && <><p>{accounts.total} comptes · page à partir de {accounts.offset + 1}</p>
      {accounts.total === 0 && <p>Aucun compte autorisé pour ce canal.</p>}
      <label>Compte de préparation<select value={selected?.account_id || ""} disabled={frozen} onChange={e => select(accounts.items.find(account => account.account_id === e.target.value))}>
        <option value="">Choisir</option>{accounts.items.map(account => <option key={account.account_id} value={account.account_id}>{account.provider} · {account.account_id} · {account.mode === "test" ? "test" : "réel"}</option>)}</select></label>
      <button disabled={frozen || accounts.offset === 0} onClick={() => void loadAccounts(Math.max(0, accounts.offset - 20))}>Comptes précédents</button>
      <button disabled={frozen || accounts.offset + accounts.items.length >= accounts.total} onClick={() => void loadAccounts(accounts.offset + 20)}>Comptes suivants</button>
    </>}
    {selected && <p>Expéditeur : {selected.sender_id}{selected.push_application ? ` · application ${selected.push_application}` : ""}</p>}
    {applicationMismatch && <p role="alert">Ce compte ne correspond pas à l’application déclarée.</p>}
    <label>Motif de préparation<input value={reason} maxLength={240} disabled={frozen || !eligible || !!receipt} onChange={e => setReason(e.target.value)} /></label>
    <button disabled={frozen || !eligible || !selected || !actor || !!receipt || applicationMismatch} onClick={prepare}>Conserver l’intention</button>
  </section>;
}
