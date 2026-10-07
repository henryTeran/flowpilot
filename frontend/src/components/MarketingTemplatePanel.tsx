import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { validTemplateRequest, validTemplateOriginal, validTemplateCatalog, matchesTemplateReceipt, sameTemplateOriginal,
  type TemplateRequest, type TemplateOriginal, type TemplateCatalog } from "../marketing-template-utils";
export function MarketingTemplatePanel({ institute }: { institute: string }) {
  if (!institute || getOperatorRole() !== "responsable_institut") return null;
  return <Editor key={JSON.stringify([institute, getAccessToken()])} institute={institute} />;
}
function Editor({ institute }: { institute: string }) {
  const actor = getOperatorSubject(), token = getAccessToken(), mounted = useRef(false), pending = useRef(false), sequence = useRef(0);
  const storage = `flowpilot.marketing-template-request:${JSON.stringify([institute, actor])}`;
  const base = `/marketing/institutes/${encodeURIComponent(institute)}/templates`;
  const [saved, save] = useState<{ terms?: TemplateRequest; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storage); if (!raw) return {}; const value = JSON.parse(raw);
      return validTemplateRequest(value) ? { terms: value } : { invalid: true }; } catch { return { invalid: true }; }
  });
  const [draft, setDraft] = useState<{ root: string | null; previous: string | null; name: string; channel: string; origin: string; subject: string; body: string }>();
  const [reason, setReason] = useState(""), [busy, setBusy] = useState(false), [rejected, setRejected] = useState(false);
  const [error, setError] = useState<string>(), [original, setOriginal] = useState<TemplateOriginal>(), [catalog, setCatalog] = useState<TemplateCatalog>();
  const current = () => mounted.current && token === getAccessToken();
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; sequence.current++; }; }, []);
  const frozen = busy || !!saved.terms || !!saved.invalid;
  async function load(offset = 0) {
    const request = ++sequence.current; setCatalog(undefined); setError(undefined); setBusy(true);
    try { const result = await apiGet<unknown>(`${base}?offset=${offset}&limit=20`);
      if (!validTemplateCatalog(result, institute, offset, 20)) throw new Error("Catalogue de templates à vérifier.");
      if (current() && request === sequence.current) setCatalog(result);
    } catch (e) { if (current() && request === sequence.current) setError(e instanceof Error ? e.message : "Lecture à reprendre."); }
    finally { if (current() && request === sequence.current) setBusy(false); }
  }
  async function prepare(selected?: TemplateOriginal) {
    if (frozen || !current()) return;
    const request = ++sequence.current;
    setError(undefined); setOriginal(undefined); setDraft(undefined); setReason("");
    if (!selected) { setDraft({ root: null, previous: null, name: "", channel: "", origin: "", subject: "", body: "" }); return; }
    setBusy(true);
    try {
      const head = await apiGet<unknown>(`${base}/${encodeURIComponent(selected.template_id)}/current`); if (!current() || request !== sequence.current) return;
      if (!validTemplateOriginal(head, institute) || head.template_id !== selected.template_id) throw new Error("Template courant à vérifier.");
      const byId = await apiGet<unknown>(`${base}/${encodeURIComponent(head.id)}`); if (!current() || request !== sequence.current) return;
      if (!validTemplateOriginal(byId, institute) || !sameTemplateOriginal(head, byId)) throw new Error("Original de template à vérifier.");
      setOriginal(head); setDraft({ root: head.template_id, previous: head.id, ...head.content, subject: head.content.subject || "" });
    } catch (e) { if (current() && request === sequence.current) setError(e instanceof Error ? e.message : "Lecture à reprendre."); }
    finally { if (current() && request === sequence.current) setBusy(false); }
  }
  async function run(terms: TemplateRequest) {
    if (!current() || pending.current || !actor || saved.invalid || !validTemplateRequest(terms)) return;
    pending.current = true; setBusy(true); setOriginal(undefined); setError(undefined); setRejected(false);
    let posting = false, returned = false;
    try {
      const raw = JSON.stringify(terms); sessionStorage.setItem(storage, raw); save({ terms });
      const path = `${base}/original/${encodeURIComponent(terms.idempotency_key)}`;
      let receipt = await apiGet<unknown>(path); if (!current()) return;
      if (receipt === null) { posting = true; receipt = await apiPost<unknown>(base, terms); returned = true; }
      if (!current()) return;
      if (!validTemplateOriginal(receipt, institute) || !matchesTemplateReceipt(receipt, terms, actor)) throw new Error("Reçu de template à vérifier.");
      const [byKey, byId, head] = await Promise.all([apiGet<unknown>(path), apiGet<unknown>(`${base}/${encodeURIComponent(receipt.id)}`),
        apiGet<unknown>(`${base}/${encodeURIComponent(receipt.template_id)}/current`)]);
      if (!current()) return;
      if (!validTemplateOriginal(byKey, institute) || !validTemplateOriginal(byId, institute) || !sameTemplateOriginal(receipt, byKey)
        || !sameTemplateOriginal(receipt, byId) || !validTemplateOriginal(head, institute) || head.template_id !== receipt.template_id) throw new Error("Original ou sélection de template à vérifier.");
      if (sessionStorage.getItem(storage) !== raw) throw new Error("Demande conservée à vérifier.");
      sessionStorage.removeItem(storage); save({}); setOriginal(receipt); setDraft(undefined); setReason(""); setCatalog(undefined);
    } catch (e) { if (current()) { setError(e instanceof Error ? e.message : "Template à reprendre.");
      setRejected(posting && !returned && e instanceof ApiError && [400, 422].includes(e.status)); }
    } finally { pending.current = false; if (current()) setBusy(false); }
  }
  function submit(event: FormEvent) {
    event.preventDefault(); if (frozen || !draft || !actor) return;
    const terms = { template_id: draft.root, previous_id: draft.previous, reason: reason.trim(), idempotency_key: crypto.randomUUID(),
      content: { name: draft.name.trim(), channel: draft.channel, origin: draft.origin, subject: draft.channel === "email" ? draft.subject : null, body: draft.body } };
    if (!validTemplateRequest(terms)) { setError("Vérifiez le nom, le canal, l’origine, le contenu et le motif."); return; } void run(terms);
  }
  function field(key: "name" | "channel" | "origin" | "subject" | "body", value: string) { setDraft(d => d ? { ...d, [key]: value } : d); }
  return <section aria-label="Templates marketing"><h3>Templates marketing</h3>
    {error && <p role="alert">{error}</p>}{busy && <p role="status">Vérification des templates…</p>}
    {saved.invalid && <p role="alert">Demande conservée invalide : aucune écriture possible.</p>}
    {saved.terms && <><p>Template conservé : {saved.terms.content.name} · {saved.terms.reason}</p><button disabled={busy} onClick={() => void run(saved.terms!)}>Reprendre le template conservé</button></>}
    {rejected && <button onClick={() => { if (!saved.terms || sessionStorage.getItem(storage) !== JSON.stringify(saved.terms)) return;
      sessionStorage.removeItem(storage); save({}); setRejected(false); setDraft(undefined); }}>Corriger le template refusé</button>}
    <button disabled={frozen} onClick={() => void prepare()}>Créer un template</button>
    <button disabled={frozen} onClick={() => void load(catalog?.offset || 0)}>Consulter les templates</button>
    {catalog && <><p>{catalog.items.length ? `${catalog.offset + 1}–${catalog.offset + catalog.items.length}` : "0"} sur {catalog.total} templates</p>
      <ul>{catalog.items.map(o => <li key={o.template_id} style={{ maxWidth: "100%" }}><button style={{ maxWidth: "100%", overflowWrap: "anywhere" }} disabled={frozen} onClick={() => void prepare(o)}>{o.content.name} · {o.content.channel} · préparer une correction</button></li>)}</ul>
      <button disabled={frozen || catalog.offset === 0} onClick={() => void load(Math.max(0, catalog.offset - 20))}>Templates précédents</button>
      <button disabled={frozen || catalog.offset + catalog.items.length >= catalog.total} onClick={() => void load(catalog.offset + 20)}>Templates suivants</button></>}
    {draft && <form onSubmit={submit}><fieldset className="marketing-audience-fields" disabled={frozen}><legend>{draft.root ? "Correction du template" : "Nouveau template"}</legend>
      <label>Nom du template<input required maxLength={160} value={draft.name} onChange={e => field("name", e.target.value)} /></label>
      <label>Canal du template<select required value={draft.channel} onChange={e => field("channel", e.target.value)}><option value="">Choisir</option><option value="email">Email</option><option value="sms">SMS</option><option value="push">Push</option></select></label>
      <label>Origine du texte<select required value={draft.origin} onChange={e => field("origin", e.target.value)}><option value="">Choisir</option><option value="human">Humaine</option><option value="ai">IA déclarée</option></select></label>
      {draft.channel === "email" && <label>Objet du template<input required maxLength={240} value={draft.subject} onChange={e => field("subject", e.target.value)} /></label>}
      <label className="marketing-template-body">Texte du template<textarea required value={draft.body} onChange={e => field("body", e.target.value)} /></label>
      <label>Motif du template<input required minLength={3} maxLength={240} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <button disabled={!actor}>Enregistrer le template</button>
    </fieldset></form>}
    {original && <div role="status"><p>Original de template vérifié : {original.id}</p><p>{original.content.name} · {original.content.channel}</p>
      <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{original.content.body}</p></div>}
    <p>Le texte est conservé littéralement. Les placeholders ne sont pas remplacés et aucun message n’est envoyé.</p>
  </section>;
}
