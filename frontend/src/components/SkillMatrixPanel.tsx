import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { instituteTimeZone } from "../institute-time";
import { validSkillMatrix, type SkillMatrix } from "../workforce-utils";

const employeeLimit = 10, serviceLimit = 5;
export function SkillMatrixPanel({ instituteId, timezone }: { instituteId: string; timezone?: string }) {
  if (!instituteId || !["accueil", "responsable_institut"].includes(getOperatorRole() || "")) return null;
  return <Matrix key={JSON.stringify([instituteId, getAccessToken()])} institute={instituteId} timezone={timezone} />;
}
function Matrix({ institute, timezone }: { institute: string; timezone?: string }) {
  const token = getAccessToken();
  const [employeeOffset, setEmployeeOffset] = useState(0), [serviceOffset, setServiceOffset] = useState(0);
  const [revision, setRevision] = useState(0), [matrix, setMatrix] = useState<SkillMatrix>();
  const [loading, setLoading] = useState(true), [error, setError] = useState<string>();
  const sequence = useRef(0);
  useEffect(() => {
    const request = ++sequence.current;
    let disposed = false;
    const current = () => !disposed && request === sequence.current && token === getAccessToken();
    setMatrix(undefined); setError(undefined); setLoading(true);
    void apiGet<SkillMatrix>(`/workforce/institutes/${encodeURIComponent(institute)}/skill-matrix?employee_offset=${employeeOffset}&employee_limit=${employeeLimit}&service_offset=${serviceOffset}&service_limit=${serviceLimit}`)
      .then(value => {
        if (!current()) return;
        if (!validSkillMatrix(value, institute, employeeOffset, serviceOffset)) throw new Error("Lecture des compétences incohérente.");
        setMatrix(value);
      }).catch(error => { if (current()) setError(error instanceof Error ? error.message : "Lecture des compétences impossible."); })
      .finally(() => { if (current()) setLoading(false); });
    return () => { disposed = true; };
  }, [employeeOffset, serviceOffset, revision]);
  const pages = (kind: "employee" | "service") => {
    if (!matrix) return null;
    const page = kind === "employee" ? matrix.employee_page : matrix.service_page;
    const setOffset = kind === "employee" ? setEmployeeOffset : setServiceOffset;
    const label = kind === "employee" ? "Collaboratrices" : "Prestations";
    const count = kind === "employee" ? matrix.employees.length : matrix.services.length;
    return <div className="workforce-pages" aria-label={`Pages ${label.toLowerCase()}`}>
      <span>{label} : {count ? page.offset + 1 : 0}–{count ? page.offset + count : 0} / {page.total}</span>
      <button disabled={loading || page.offset === 0} onClick={() => setOffset(Math.max(0, page.offset - page.limit))}>{label} précédentes</button>
      <button disabled={loading || page.offset + page.limit >= page.total} onClick={() => setOffset(page.offset + page.limit)}>{label} suivantes</button>
    </div>;
  };
  return <main className="workforce-panel" aria-label="Compétences de l’équipe">
    <header><h2>Matrice des compétences</h2><button disabled={loading} onClick={() => setRevision(value => value + 1)}>Actualiser les compétences</button></header>
    <p>Compétences enregistrées face aux exigences des prestations actives. La couverture ne confirme ni une certification ni la disponibilité pour un créneau.</p>
    {loading && <p role="status">Lecture des compétences…</p>}
    {error && <p role="alert">{error} <button onClick={() => setRevision(value => value + 1)}>Réessayer</button></p>}
    {matrix && <>
      <p>Lecture au {new Date(matrix.generated_at).toLocaleString("fr-CH", { timeZone: instituteTimeZone(timezone) })} · {instituteTimeZone(timezone)}</p>
      {pages("employee")}{pages("service")}
      {!matrix.employees.length && <p>Aucune collaboratrice sur cette page.</p>}
      {!matrix.services.length && <p>Aucune prestation active sur cette page.</p>}
      {!!matrix.employees.length && !!matrix.services.length && <div className="workforce-table-scroll" tabIndex={0} role="region" aria-label="Tableau des compétences, défilement horizontal">
        <table><caption>Couverture des exigences enregistrées</caption><thead><tr><th scope="col">Collaboratrice</th>
          {matrix.services.map(service => <th scope="col" key={service.id}>{service.name}<small>{service.required_skills.length ? `Exigences : ${service.required_skills.join(", ")}` : "Aucune exigence enregistrée"}</small></th>)}
        </tr></thead><tbody>{matrix.employees.map(employee => <tr key={employee.id}>
          <th scope="row">{employee.first_name}<small>Compétences : {employee.skills.join(", ") || "Aucune enregistrée"}</small></th>
          {matrix.services.map(service => {
            const cell = matrix.cells.find(value => value.employee_id === employee.id && value.service_id === service.id)!;
            return <td key={service.id} aria-label={`${employee.first_name} · ${service.name}`}>
              {!service.required_skills.length ? <span className="skill-unspecified">Aucune exigence enregistrée</span>
                : cell.meets_recorded_requirements ? <span className="skill-covered">Exigences couvertes</span>
                  : <span className="skill-missing">Manque : {cell.missing_skills.join(", ")}</span>}
            </td>;
          })}</tr>)}</tbody></table>
      </div>}
    </>}
  </main>;
}
