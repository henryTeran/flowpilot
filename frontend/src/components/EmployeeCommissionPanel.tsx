import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validCommissionDay, commissionStates, type CommissionDay, type CommissionState } from "../commission-utils";
import { instituteSlot } from "../institute-calendar";
type Props = { institute: string; employee: string; day: string; start: string; end: string; timezone: string };
const labels: Record<CommissionState, string> = { recorded: "Commissions enregistrées", cancelled: "Commissions annulées",
  future_recording: "Enregistrements datés après la lecture", future_cancellation: "Annulations datées après la lecture" };
export function commissionAmount(minor: string, currency: string) {
  const cents = BigInt(minor); return `${cents/100n},${String(cents%100n).padStart(2, "0")} ${currency}`;
}
export function EmployeeCommissionPanel(props: Props) {
  if (getOperatorRole() !== "responsable_institut") return null;
  return <Reading key={JSON.stringify([props, getAccessToken()])} {...props} />;
}
function Reading({ institute, employee, day, start, end, timezone }: Props) {
  const token = getAccessToken(), [offset, page] = useState(0), [revision, refresh] = useState(0);
  const [result, setResult] = useState<CommissionDay>(), [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  useEffect(() => {
    let disposed = false; const current = () => !disposed && token === getAccessToken();
    setResult(undefined); setError(undefined); setLoading(true);
    void apiGet<CommissionDay>(`/workforce/institutes/${encodeURIComponent(institute)}/employees/${encodeURIComponent(employee)}/commission-day?day=${encodeURIComponent(day)}&limit=20&offset=${offset}`)
      .then(v => { if (!current()) return; if (!validCommissionDay(v, institute, employee, day, start, end, timezone, offset)) throw new Error("Lecture des commissions à vérifier."); setResult(v); })
      .catch(e => { if (current()) setError(e instanceof Error ? e.message : "Commissions indisponibles."); })
      .finally(() => { if (current()) setLoading(false); });
    return () => { disposed = true; };
  }, [offset, revision]);
  const visible = result?.page.offset === offset ? result : undefined;
  const display = (value: string) => {
    const slot = instituteSlot(value, timezone)!, minutes = Math.abs(slot.offset)/60000;
    return `${new Date(value).toLocaleString("fr-CH", { timeZone: timezone })} (UTC${slot.offset < 0 ? "−" : "+"}${String(Math.floor(minutes/60)).padStart(2, "0")}:${String(minutes%60).padStart(2, "0")})`;
  };
  return <section aria-label="Commissions enregistrées" className="employee-commissions">
    <header><h3>Commissions enregistrées</h3><button disabled={loading} onClick={() => refresh(v => v+1)}>Actualiser les commissions</button></header>
    <p>Journal des commissions enregistrées le {day} · {timezone}. La journée porte sur leur enregistrement, indépendamment du jour de clôture de la prestation.</p>
    <p>Les droits complets et le total à payer restent inconnus. Les devises sont conservées séparément, sans conversion.</p>
    {loading && <p role="status">Lecture des commissions…</p>}{error && <p role="alert">{error}</p>}
    {visible && <><p>Lecture au {display(visible.generated_at)} · journal complet de ce jour : {visible.page.total} commissions.</p>
      {commissionStates.filter(k => visible.counts[k] > 0 || k === "recorded" || k === "cancelled").map(k => <p key={k}>{labels[k]} : {visible.counts[k]}</p>)}
      {!visible.page.total && <p>Aucune commission enregistrée ce jour. Cela ne détermine pas les droits de cette collaboratrice.</p>}
      {visible.currencies.map(c => <section key={c.currency} aria-label={`Montants enregistrés en ${c.currency}`}>
        <h4>{c.currency} · montants du journal complet</h4>
        {commissionStates.filter(k => c.counts[k] > 0 || k === "recorded" || k === "cancelled").map(k => <p key={k}>{labels[k]} : {commissionAmount(c.amounts_minor[k], c.currency)} · {c.counts[k]} commissions</p>)}
      </section>)}
      <ul className="absence-list">{visible.rows.map(row => { const o = row.original, r = o.rule_capture, s = o.calculation.source;
        return <li key={o.id}><strong>{labels[row.state]} · {commissionAmount(o.calculation.amount_minor, s.currency)}</strong>
          <p>{r.title} · {r.rate_basis_points/100} % · clôture de la prestation : {display(s.paid_at)}</p>
          <p>Montant brut complet de la ligne : {commissionAmount(s.gross_minor, s.currency)} · quantité : {s.quantity}, déjà incluse dans ce montant.</p>
          <details><summary>Provenance de la commission</summary><p>Original {o.id} · règle {o.rule_id} · ticket {o.ticket_id} · ligne {o.line_id}</p>
            <p>Enregistré : {o.created_at} · acteur {o.actor_id} · motif : {o.reason}</p><p>Collaboratrice attribuée : {s.employee_id} · prestation {s.service_id} · catégorie {s.category}</p>
            <p>Règle originale : {r.first_day} → {r.last_day} inclus · {r.timezone} · période UTC {r.period_start} → {r.period_end}, fin exclue.</p>
            <p>Arrondi : {r.rounding === "half_up" ? "Demi-cent vers le haut" : r.rounding === "half_even" ? "Demi-cent vers le cent pair" : "Cent inférieur"} · calcul entier original : {o.calculation.unrounded_numerator} / 10000 · reste {o.calculation.rounding_remainder}.</p>
            <p>Arrivée originale : {s.arrival_at} · clôture : {s.paid_at} · capture : {s.captured_at}</p>
            {o.cancellation && <p>Annulation {o.cancellation.id} · {o.cancellation.created_at} · acteur {o.cancellation.actor_id} · motif : {o.cancellation.reason}</p>}</details></li>;
      })}</ul>
      <div className="workforce-pages"><span>Commissions : {visible.rows.length ? offset+1 : 0}–{offset+visible.rows.length} / {visible.page.total}</span>
        <button disabled={loading || !offset} onClick={() => page(offset-20)}>Commissions précédentes</button><button disabled={loading || offset+20 >= visible.page.total} onClick={() => page(offset+20)}>Commissions suivantes</button></div></>}
  </section>;
}
