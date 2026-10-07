import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validCommissionSourceOptions, type CommissionSourceOptions } from "../commission-options";
import type { CommissionRule, CommissionCalculation } from "../commission-utils";
import type { Service } from "../types";
import { commissionAmount } from "./EmployeeCommissionPanel";
type Props = { institute: string; rule: CommissionRule; day: string; start: string; end: string; timezone: string; services: Service[];
  disabled?: boolean; onSelection: (value: CommissionCalculation | undefined) => void };
const labels = { rule_cancelled: "Règle annulée", future_rule: "Règle datée après la lecture", already_attributed: "Commission déjà enregistrée",
  future_cancellation: "Annulation datée après la lecture", future_closing: "Clôture datée après la lecture", currency_mismatch: "Devise différente ou inconnue",
  outside_period: "Clôture hors période de la règle", invalid_source: "Montant, quantité ou chronologie incomplets ou incohérents" };
export function CommissionChoices(props: Props) {
  if (getOperatorRole() !== "responsable_institut") return null;
  return <Choices key={JSON.stringify([props.institute, props.rule, props.day, props.start, props.end, props.timezone, getAccessToken()])} {...props} />;
}
function Choices({ institute, rule, day, start, end, timezone, services, disabled, onSelection }: Props) {
  const token = getAccessToken(), [offset, paginate] = useState(0), [revision, refresh] = useState(0);
  const [result, setResult] = useState<CommissionSourceOptions>(), [selected, select] = useState<CommissionCalculation>();
  const [loading, setLoading] = useState(false), [error, setError] = useState<string>();
  const scope = useRef({ offset, revision, disabled }); scope.current = { offset, revision, disabled };
  useEffect(() => {
    let disposed = false; const current = () => !disposed && token === getAccessToken() && scope.current.offset === offset
      && scope.current.revision === revision && scope.current.disabled === disabled;
    setResult(undefined); select(undefined); setError(undefined); setLoading(false); onSelection(undefined);
    if (disabled) return;
    setLoading(true);
    void apiGet<CommissionSourceOptions>(`/workforce/institutes/${encodeURIComponent(institute)}/commission-rules/${encodeURIComponent(rule.id)}/sources?day=${encodeURIComponent(day)}&limit=20&offset=${offset}`)
      .then(v => { if (!current()) return; if (!validCommissionSourceOptions(v, institute, rule, day, start, end, timezone, offset)) throw new Error("Choix de commission à vérifier."); setResult(v); })
      .catch(e => { if (current()) setError(e instanceof Error ? e.message : "Sources indisponibles."); })
      .finally(() => { if (current()) setLoading(false); });
    return () => { disposed = true; };
  }, [offset, revision, disabled]);
  const visible = result?.page.offset === offset ? result : undefined;
  return <section className="commission-choices" aria-label="Sources de commission">
    <p>Lignes clôturées le {day} · {timezone}. Le calcul porte sur le montant brut complet de la ligne, avec sa quantité déjà incluse.</p>
    <button type="button" disabled={disabled || loading} onClick={() => { select(undefined); setResult(undefined); onSelection(undefined); refresh(v => v+1); }}>Actualiser les sources de commission</button>
    {loading && <p role="status">Lecture des lignes clôturées…</p>}{error && <p role="alert">{error}</p>}
    {visible && <><p>Lecture : {visible.generated_at} · couverture complète des sources inconnue.</p>
      <label>Ligne clôturée<select required disabled={disabled || loading} value={selected?.source.line_id || ""} onChange={event => {
        if (disabled || token !== getAccessToken()) return;
        const row = visible.rows.find(r => r.line_id === event.target.value), calculation = row?.exclusion === null ? row.calculation || undefined : undefined;
        select(calculation); onSelection(calculation);
      }}><option value="">Choisir une ligne clôturée</option>{visible.rows.map(row => <option key={row.line_id} value={row.line_id} disabled={row.exclusion !== null}>
        {row.ticket_number} · {services.find(s => s.id === row.service_id)?.name || "Prestation conservée"} · {new Date(row.paid_at).toLocaleString("fr-CH", { timeZone: timezone })} · {row.exclusion ? labels[row.exclusion] : commissionAmount(row.calculation!.amount_minor, row.calculation!.source.currency)}
      </option>)}</select></label>
      {!visible.rows.length && <p>Aucune ligne clôturée sur cette page pour le périmètre de cette règle.</p>}
      <div className="workforce-pages"><span>Lignes : {visible.rows.length ? offset+1 : 0}–{offset+visible.rows.length} / {visible.page.total}</span>
        <button type="button" disabled={disabled || loading || !offset} onClick={() => { onSelection(undefined); select(undefined); setResult(undefined); paginate(offset-20); }}>Lignes précédentes</button>
        <button type="button" disabled={disabled || loading || offset+20 >= visible.page.total} onClick={() => { onSelection(undefined); select(undefined); setResult(undefined); paginate(offset+20); }}>Lignes suivantes</button></div></>}
    {visible && selected && !disabled && <details open><summary>Aperçu de la commission</summary><p>Ticket {visible.rows.find(r => r.line_id === selected.source.line_id)!.ticket_number}</p><p>{commissionAmount(selected.amount_minor, selected.source.currency)} · taux {selected.terms.rate_basis_points/100} % · brut {commissionAmount(selected.source.gross_minor, selected.source.currency)} · quantité {selected.source.quantity}, déjà incluse.</p>
      <p>Arrondi : {selected.terms.rounding === "half_up" ? "Demi-cent vers le haut" : selected.terms.rounding === "half_even" ? "Demi-cent vers le cent pair" : "Cent inférieur"}. Cet aperçu ne crée pas de commission ; la source sera vérifiée lors de l’enregistrement.</p></details>}
  </section>;
}
