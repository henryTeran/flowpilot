import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { validContactRequest, validContactOriginal, matchesContactReceipt, sameContactOriginal, sameContactRequest,
  type ContactChannel, type ContactRequest, type ContactOriginal, type ContactCommunication } from "../marketing-contact-utils";

type Fields = { channel: ContactChannel; permission: ContactCommunication["permission"]; evidence: string;
  destination: boolean; address: string; application: string; destinationEvidence: string };
const channels: ContactChannel[] = ["email", "sms", "push"];
const labels = { email: "Email", sms: "SMS", push: "Push" };
const fields = (original: Pick<ContactRequest, "declaration"> | null): Fields[] => channels.map(channel => {
  const c = original?.declaration.communications.find(c => c.channel === channel), d = c?.destination;
  return { channel, permission: c?.permission || "unknown", evidence: c?.permission_evidence || "", destination: !!d,
    address: d?.email || d?.phone || d?.push_token || "", application: d?.push_application || "", destinationEvidence: d?.evidence || "" };
});
export function MarketingContactEditor({ institute, customer }: { institute: string; customer: string }) {
  if (!institute || !customer || getOperatorRole() !== "responsable_institut") return null;
  return <Editor key={JSON.stringify([institute, customer, getAccessToken()])} institute={institute} customer={customer} />;
}
function Editor({ institute, customer }: { institute: string; customer: string }) {
  const token = getAccessToken(), actor = getOperatorSubject(), mounted = useRef(false), pending = useRef(false);
  const storage = `flowpilot.marketing-contact-request:${JSON.stringify([institute, customer, actor])}`;
  const base = `/marketing/institutes/${encodeURIComponent(institute)}/customers/${encodeURIComponent(customer)}/contact-declarations`;
  const [saved, save] = useState<{ terms?: ContactRequest; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storage); if (!raw) return {}; const v = JSON.parse(raw);
      return validContactRequest(v, institute, customer) ? { terms: v } : { invalid: true }; } catch { return { invalid: true }; }
  });
  const [open, setOpen] = useState(false), [predecessor, setPredecessor] = useState<string | null>(null);
  const [values, setValues] = useState<Fields[]>(fields(null)), [reason, setReason] = useState("");
  const [verified, setVerified] = useState<ContactRequest>(), [receipt, setReceipt] = useState<ContactOriginal>();
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>(), [rejected, setRejected] = useState(false);
  const current = () => mounted.current && token === getAccessToken();
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const frozen = busy || !!saved.terms || !!saved.invalid;
  async function prepare() {
    if (frozen || !current()) return;
    setBusy(true); setOpen(false); setVerified(undefined); setReceipt(undefined); setError(undefined);
    try {
      const head = await apiGet<unknown>(base + "/current"); if (!current()) return;
      if (head !== null) {
        if (!validContactOriginal(head, institute, customer)) throw new Error("Contacts courants à vérifier.");
        const id = await apiGet<unknown>(`${base}/${encodeURIComponent(head.id)}`); if (!current()) return;
        if (!validContactOriginal(id, institute, customer) || !sameContactOriginal(head, id)) throw new Error("Original de contacts à vérifier.");
      }
      setPredecessor(head === null ? null : (head as ContactOriginal).id);
      setValues(fields(head as ContactOriginal | null)); setReason(""); setOpen(true);
    } catch (e) { if (current()) setError(e instanceof Error ? e.message : "Contacts à reprendre."); }
    finally { if (current()) setBusy(false); }
  }
  async function verify(event: FormEvent) {
    event.preventDefault(); if (frozen || !current()) return;
    const terms: ContactRequest = { declaration: { institute_id: institute, customer_id: customer, purpose: "marketing", communications: values.map(v => ({
      channel: v.channel, permission: v.permission, permission_evidence: v.permission === "unknown" ? null : v.evidence.trim(),
      destination: !v.destination ? null : { channel: v.channel, email: v.channel === "email" ? v.address : null, phone: v.channel === "sms" ? v.address : null,
        push_application: v.channel === "push" ? v.application : null, push_token: v.channel === "push" ? v.address : null, evidence: v.destinationEvidence.trim() } })) },
      previous_id: predecessor, reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    if (!validContactRequest(terms, institute, customer)) { setError("Vérifiez les contacts, leurs preuves et le motif."); return; }
    setBusy(true); setError(undefined);
    try {
      // Server validates/normalizes email without recording a declaration. The
      // canonical values are shown for explicit confirmation before any write.
      const canonical = await apiPost<unknown>(base + "/validate", terms); if (!current()) return;
      if (!validContactRequest(canonical, institute, customer) || canonical.previous_id !== terms.previous_id
        || canonical.idempotency_key !== terms.idempotency_key || canonical.reason !== terms.reason) throw new Error("Déclaration vérifiée à contrôler.");
      const withoutEmail = (r: ContactRequest) => ({ ...r, declaration: { ...r.declaration, communications: r.declaration.communications.map(c => ({ ...c,
        destination: c.destination === null ? null : { ...c.destination, email: null } })) } });
      if (!sameContactRequest(withoutEmail(canonical), withoutEmail(terms))) throw new Error("Termes vérifiés à contrôler.");
      setVerified(canonical); setOpen(false);
    } catch (e) { if (current()) setError(e instanceof Error ? e.message : "Vérification à reprendre."); }
    finally { if (current()) setBusy(false); }
  }
  async function run(terms: ContactRequest) {
    if (!current() || pending.current || !actor || saved.invalid || !validContactRequest(terms, institute, customer)) return;
    pending.current = true; setBusy(true); setReceipt(undefined); setError(undefined); setRejected(false);
    let posting = false, returned = false;
    try {
      const raw = JSON.stringify(terms); sessionStorage.setItem(storage, raw); save({ terms });
      const path = `${base}/original/${encodeURIComponent(terms.idempotency_key)}`;
      let original = await apiGet<unknown>(path); if (!current()) return;
      if (original === null) { posting = true; original = await apiPost<unknown>(base, terms); returned = true; }
      if (!current()) return;
      if (!validContactOriginal(original, institute, customer) || !matchesContactReceipt(original, terms, actor)) throw new Error("Déclaration originale à vérifier.");
      const [key, id, head] = await Promise.all([apiGet<unknown>(path), apiGet<unknown>(`${base}/${encodeURIComponent(original.id)}`), apiGet<unknown>(base + "/current")]);
      if (!current()) return;
      if (!validContactOriginal(key, institute, customer) || !validContactOriginal(id, institute, customer)
        || !sameContactOriginal(original, key) || !sameContactOriginal(original, id) || !validContactOriginal(head, institute, customer)) throw new Error("Original ou contacts courants à vérifier.");
      if (sessionStorage.getItem(storage) !== raw) throw new Error("Demande conservée à vérifier.");
      sessionStorage.removeItem(storage); save({}); setReceipt(original); setVerified(undefined); setOpen(false); setReason("");
    } catch (e) { if (current()) { setError(e instanceof Error ? e.message : "Déclaration à reprendre.");
      setRejected(posting && !returned && e instanceof ApiError && [400, 422].includes(e.status)); } }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  const change = (channel: ContactChannel, patch: Partial<Fields>) => setValues(old => old.map(v => v.channel === channel ? { ...v, ...patch } : v));
  return <section aria-label="Contacts marketing"><h3>Contacts marketing</h3>
    <p>Déclarez les permissions et les destinations pour cette cliente. Aucun envoi n’est effectué.</p>
    {busy && <p role="status">Vérification des contacts…</p>}{error && <p role="alert">{error}</p>}
    {saved.invalid && <p role="alert">Demande conservée invalide : aucune écriture possible.</p>}
    {saved.terms && <><p>Déclaration conservée : {saved.terms.reason}</p><button disabled={busy} onClick={() => void run(saved.terms!)}>Reprendre les contacts conservés</button></>}
    {rejected && <button onClick={() => { if (!saved.terms || sessionStorage.getItem(storage) !== JSON.stringify(saved.terms)) return;
      sessionStorage.removeItem(storage); save({}); setRejected(false); }}>Corriger la déclaration refusée</button>}
    <button disabled={frozen} onClick={() => void prepare()}>Préparer les contacts marketing</button>
    {open && <form onSubmit={verify}><fieldset disabled={frozen} className="marketing-audience-fields"><legend>Déclaration de contacts</legend>
      {values.map(v => <fieldset key={v.channel} style={{ gridColumn: "1 / -1", minWidth: 0 }}><legend>{labels[v.channel]}</legend>
        <label>Permission marketing {labels[v.channel]}<select value={v.permission} onChange={e => change(v.channel, { permission: e.target.value as Fields["permission"] })}>
          <option value="unknown">Inconnue</option><option value="granted">Accord déclaré</option><option value="refused">Refus déclaré</option></select></label>
        {v.permission !== "unknown" && <label>Preuve de permission {labels[v.channel]}<input required minLength={3} maxLength={240} value={v.evidence} onChange={e => change(v.channel, { evidence: e.target.value })} /></label>}
        <label className="marketing-segment-option"><input type="checkbox" style={{ width: 44 }} checked={v.destination} onChange={e => change(v.channel, { destination: e.target.checked })} />Déclarer une destination {labels[v.channel]}</label>
        {v.destination && <><label>Destination {labels[v.channel]}<input required type={v.channel === "email" ? "email" : v.channel === "push" ? "password" : "text"}
          autoComplete="off" value={v.address} onChange={e => change(v.channel, { address: e.target.value })} /></label>
          {v.channel === "push" && <label>Application Push<input required maxLength={160} value={v.application} onChange={e => change(v.channel, { application: e.target.value })} /></label>}
          <label>Preuve de destination {labels[v.channel]}<input required minLength={3} maxLength={240} value={v.destinationEvidence} onChange={e => change(v.channel, { destinationEvidence: e.target.value })} /></label></>}
      </fieldset>)}
      <label>Motif des contacts<input required minLength={3} maxLength={240} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <button>Vérifier la déclaration de contacts</button>
    </fieldset></form>}
    {verified && !saved.terms && <div><p>Déclaration vérifiée : {verified.reason}</p>
      {verified.declaration.communications.map(c => <p key={c.channel} style={{ overflowWrap: "anywhere" }}>{labels[c.channel]} : {c.permission === "granted" ? "Accord déclaré" : c.permission === "refused" ? "Refus déclaré" : "Inconnue"}
        {c.destination ? ` · ${c.destination.email || c.destination.phone || `Application ${c.destination.push_application} · jeton masqué`}` : " · destination absente"}</p>)}
      <button disabled={frozen} onClick={() => void run(verified)}>Conserver la déclaration vérifiée</button>
      <button disabled={frozen} onClick={() => { setValues(fields(verified)); setVerified(undefined); setOpen(true); }}>Modifier la déclaration vérifiée</button>
    </div>}
    {receipt && <div role="status"><p>Contacts originaux vérifiés : {receipt.id}</p><p>{receipt.actor_id} · {receipt.reason} · {receipt.created_at}</p></div>}
  </section>;
}
