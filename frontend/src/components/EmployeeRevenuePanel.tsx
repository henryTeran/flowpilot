import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validEmployeeRevenue, type EmployeeRevenue } from "../employee-revenue-utils";
import { instituteSlot } from "../institute-calendar";
type Props = { institute: string; employee: string; day: string; start: string; end: string; timezone: string };
const amount = (value: string | null, currency: string | null) => value === null ? "Montant non renseigné" : `${value.replace(".", ",")} ${currency || "(devise non renseignée)"}`;
export function EmployeeRevenuePanel(props: Props) {
  if (getOperatorRole() !== "responsable_institut") return null;
  return <Revenue key={JSON.stringify([props.institute, props.employee, props.day, props.start, props.end, getAccessToken()])} {...props} />;
}
function Revenue({ institute, employee, day, start, end, timezone }: Props) {
  const token = getAccessToken(), [offset, page] = useState(0), [revision, refresh] = useState(0);
  const [result, setResult] = useState<EmployeeRevenue>(), [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  useEffect(() => {
    let disposed = false; const current = () => !disposed && token === getAccessToken();
    setResult(undefined); setError(undefined); setLoading(true);
    void apiGet<EmployeeRevenue>(`/workforce/institutes/${encodeURIComponent(institute)}/employees/${encodeURIComponent(employee)}/revenue?day=${day}&limit=50&offset=${offset}`)
      .then(value => { if (!current()) return; if (!validEmployeeRevenue(value, institute, employee, day, start, end, offset)) throw new Error("Lecture du CA attribué à vérifier."); setResult(value); })
      .catch(error => { if (current()) setError(error instanceof Error ? error.message : "CA attribué indisponible."); })
      .finally(() => { if (current()) setLoading(false); });
    return () => { disposed = true; };
  }, [offset, revision]);
  const visible = result?.page.offset === offset ? result : undefined;
  const display = (instant: string) => {
    const slot = instituteSlot(instant, timezone)!, minutes = Math.abs(slot.offset)/60000;
    return `${new Date(instant).toLocaleString("fr-CH", { timeZone: timezone })} (UTC${slot.offset < 0 ? "−" : "+"}${String(Math.floor(minutes/60)).padStart(2, "0")}:${String(minutes%60).padStart(2, "0")})`;
  };
  return <section aria-label="CA brut facturé attribué" className="employee-revenue">
    <header><h3>CA brut facturé attribué</h3><button disabled={loading} onClick={() => refresh(value => value+1)}>Actualiser le CA attribué</button></header>
    <p>Jour de clôture interne : {day} · exécutante enregistrée sur la ligne. Le règlement externe et l’attribution des remboursements restent distincts.</p>
    {loading && <p role="status">Lecture du CA attribué…</p>}{error && <p role="alert">{error}</p>}
    {visible && <><p>Lecture au {display(visible.generated_at)} · {timezone}</p>
      <ul>{visible.currencies.map(group => <li key={group.currency || "unknown"}><strong>{group.currency || "Devise non renseignée"}</strong> :
        {group.total !== null ? ` ${amount(group.total, group.currency)}` : " Total non déterminable"} · {group.line_count} lignes / {group.ticket_count} tickets
        {group.amount_missing_lines > 0 && <p>{group.amount_missing_lines} montants non renseignés{group.amount_known_total !== null && ` · sous-total connu : ${amount(group.amount_known_total, group.currency)}`}</p>}</li>)}</ul>
      {!visible.page.total && <p>Aucune ligne attribuée clôturée ce jour.</p>}
      {visible.institute_unattributed_lines > 0 && <p>{visible.institute_unattributed_lines} lignes clôturées sans exécutante enregistrée dans l’institut ce jour ; elles ne sont pas attribuées à cette collaboratrice.</p>}
      <ul className="absence-list">{visible.rows.map(line => <li key={line.id}><strong>{amount(line.amount, line.currency)}</strong>
        <p>Ticket {line.ticket_number} · quantité : {line.quantity}</p><p>Clôture interne : {display(line.paid_at)}</p>
        <details><summary>Provenance de la ligne</summary><p>Ligne {line.id} · prestation {line.service_id} · catégorie enregistrée : {line.category}</p></details></li>)}</ul>
      <div className="workforce-pages"><span>Lignes : {visible.rows.length ? offset+1 : 0}–{offset+visible.rows.length} / {visible.page.total}</span>
        <button disabled={loading || !offset} onClick={() => page(offset-50)}>Lignes de CA précédentes</button>
        <button disabled={loading || offset+50 >= visible.page.total} onClick={() => page(offset+50)}>Lignes de CA suivantes</button></div></>}
  </section>;
}
