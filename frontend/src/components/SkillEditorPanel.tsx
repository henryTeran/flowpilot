import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorRole, getOperatorSubject } from "../api/session";
import { certificationInstant } from "../certification-utils";
import type { Employee } from "../types";

type Terms = { employee_id: string; expected_skills: string[]; skills: string[]; reason: string; idempotency_key: string };
type Original = Terms & { id: string; institute_id: string; actor_id: string; created_at: string };
const text = (value: unknown, max: number): value is string => typeof value === "string" && value.trim() === value && value.length > 0 && value.length <= max;
export const validSkillCodes = (value: unknown): value is string[] => Array.isArray(value) && value.length <= 100
  && value.every(code => text(code, 64)) && new Set(value).size === value.length;
export function validSkillTerms(value: unknown): value is Terms {
  const row = value as Terms;
  return !!row && text(row.employee_id, 80) && validSkillCodes(row.expected_skills) && validSkillCodes(row.skills)
    && text(row.reason, 240) && text(row.idempotency_key, 120);
}
const same = (a: string[], b: string[]) => a.length === b.length && a.every(code => b.includes(code));
const errorText = (error: unknown) => error instanceof Error ? error.message : "Compétences indisponibles.";
export function SkillEditorPanel(props: { institute: string; employees: Employee[]; onChanged: () => Promise<boolean> }) {
  if (!props.institute || getOperatorRole() !== "responsable_institut") return null;
  return <Editor key={JSON.stringify([props.institute, getAccessToken()])} {...props} />;
}
function Editor({ institute, employees, onChanged }: { institute: string; employees: Employee[]; onChanged: () => Promise<boolean> }) {
  const token = getAccessToken(), actor = getOperatorSubject(), storage = `flowpilot.skill-change:${JSON.stringify([institute, actor])}`;
  const [saved, save] = useState<{ terms?: Terms; invalid?: boolean }>(() => {
    try { const raw = sessionStorage.getItem(storage); if (!raw) return {}; const value = JSON.parse(raw);
      return validSkillTerms(value) ? { terms: value } : { invalid: true };
    } catch { return { invalid: true }; }
  });
  const [employee, select] = useState(saved.terms?.employee_id || ""), [reading, setCurrent] = useState<{ employee: string; skills: string[] }>();
  const currentCodes = reading?.employee === employee ? reading.skills : undefined;
  const [draft, setDraft] = useState<string[]>([]), [code, setCode] = useState(""), [reason, setReason] = useState("");
  const [error, setError] = useState<string>(), [success, setSuccess] = useState<string>(), [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false), [rejected, reject] = useState(false);
  const mounted = useRef(false), scope = useRef(employee), sequence = useRef(0), pending = useRef(false); scope.current = employee;
  const current = () => mounted.current && token === getAccessToken() && scope.current === employee;
  const path = `/workforce/institutes/${encodeURIComponent(institute)}/skill-changes`;
  async function read() {
    const request = ++sequence.current; setCurrent(undefined); setLoading(!!employee);
    if (!employee) return false;
    try {
      const result = await apiGet<{ skills: string[] }>(`/resources/institutes/${encodeURIComponent(institute)}/employees/${encodeURIComponent(employee)}/skills`);
      if (!current() || request !== sequence.current) return false;
      if (!result || !validSkillCodes(result.skills)) throw new Error("Lecture des compétences à vérifier.");
      setCurrent({ employee, skills: result.skills }); setDraft(result.skills); return true;
    } catch (error) { if (current() && request === sequence.current) setError(errorText(error)); return false; }
    finally { if (current() && request === sequence.current) setLoading(false); }
  }
  useEffect(() => { mounted.current = true; setError(undefined); setSuccess(undefined); setReason(""); setCode(""); void read();
    return () => { mounted.current = false; sequence.current++; }; }, [employee]);
  const frozen = busy || !!saved.terms || !!saved.invalid, locked = frozen || loading || !currentCodes || !actor;
  const matches = (value: unknown, terms: Terms): value is Original => {
    const row = value as Original;
    return validSkillTerms(row) && row.institute_id === institute && row.employee_id === employee && row.actor_id === actor
      && text(row.id, 80) && certificationInstant(row.created_at) !== undefined && row.reason === terms.reason
      && row.idempotency_key === terms.idempotency_key && same(row.expected_skills, terms.expected_skills) && same(row.skills, terms.skills);
  };
  async function run(terms: Terms) {
    if (pending.current || !current() || !actor || !currentCodes || loading || saved.invalid || terms.employee_id !== employee) return;
    pending.current = true; setBusy(true); setError(undefined); setSuccess(undefined); reject(false);
    let posting = false, returned = false;
    try {
      sessionStorage.setItem(storage, JSON.stringify(terms)); save({ terms });
      const originalPath = `${path}/original/${encodeURIComponent(terms.idempotency_key)}`;
      let original = await apiGet<Original | null>(originalPath);
      if (!current()) return;
      if (original === null) { posting = true; original = await apiPost<Original>(path, terms); returned = true; }
      if (!current()) return;
      if (!matches(original, terms)) throw new Error("Modification originale des compétences à vérifier.");
      const verified = await apiGet<Original | null>(originalPath);
      if (!current()) return;
      if (!matches(verified, terms) || verified.id !== original.id || verified.created_at !== original.created_at) throw new Error("Lecture originale des compétences à vérifier.");
      if (!await read() || !current()) throw new Error("Relisez les compétences avant de poursuivre.");
      if (!await onChanged() || !current()) throw new Error("Actualisez l’équipe avant de poursuivre.");
      sessionStorage.removeItem(storage); save({}); setReason("");
      setSuccess("Modification originale vérifiée ; compétences actuelles relues.");
    } catch (error) { if (current()) { setError(errorText(error)); reject(posting && !returned && error instanceof ApiError && [400, 422].includes(error.status)); } }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  function submit(event: FormEvent) {
    event.preventDefault(); if (locked || !employee || !currentCodes) return;
    const terms = { employee_id: employee, expected_skills: currentCodes, skills: draft, reason: reason.trim(), idempotency_key: crypto.randomUUID() };
    if (validSkillTerms(terms)) void run(terms);
  }
  return <section className="workforce-panel absence-panel skill-editor-panel" aria-label="Gestion des compétences">
    <h2>Gérer les compétences</h2><p>Codes déclarés utilisés par la matrice et l’affectation. Une certification ne crée pas automatiquement une compétence.</p>
    <label>Collaboratrice des compétences<select disabled={frozen} value={employee} onChange={event => select(event.target.value)}>
      <option value="">Choisir une collaboratrice</option>{employees.filter(row => row.institute_id === institute).map(row => <option key={row.id} value={row.id}>{row.first_name}</option>)}</select></label>
    {loading && <p role="status">Lecture des compétences…</p>}
    {employee && <button disabled={busy || loading || !!saved.invalid} onClick={() => { setError(undefined); void read(); }}>Relire les compétences</button>}
    {currentCodes && <><p>Compétences actuelles : {currentCodes.join(" · ") || "Aucune"}</p>
      <form aria-label="Modifier les compétences" onSubmit={submit}><fieldset disabled={locked}>
        <div className="skill-editor-add"><label>Ajouter un code de compétence<input maxLength={64} value={code} onChange={event => setCode(event.target.value)} /></label>
        <button type="button" disabled={!text(code.trim(), 64) || draft.includes(code.trim()) || draft.length >= 100} onClick={() => { setDraft([...draft, code.trim()]); setCode(""); }}>Ajouter le code</button></div>
        <ul className="skill-editor-codes">{draft.map(value => <li key={value}><span>{value}</span> <button type="button" aria-label={`Retirer ${value}`} onClick={() => setDraft(draft.filter(row => row !== value))}>Retirer</button></li>)}</ul>
        <label>Motif de modification des compétences<input required maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /></label>
        <button type="submit">Enregistrer les compétences</button>
      </fieldset></form></>}
    {saved.terms && <><p>Demande conservée : {saved.terms.skills.join(" · ") || "Aucune compétence"} · {saved.terms.reason}</p>
      <button disabled={busy || loading || !currentCodes} onClick={() => void run(saved.terms!)}>Reprendre la modification conservée</button></>}
    {rejected && saved.terms && <button disabled={busy} onClick={() => { try { sessionStorage.removeItem(storage); save({}); reject(false); setError(undefined); void read(); } catch (error) { setError(errorText(error)); } }}>Corriger la modification refusée</button>}
    {saved.invalid && <p role="alert">La demande conservée doit être vérifiée avant une nouvelle modification.</p>}
    {error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
  </section>;
}
