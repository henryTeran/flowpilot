import { useState } from "react";
import { getAccessToken, getOperatorRole } from "../api/session";
import type { Employee, Service } from "../types";
import { SkillMatrixPanel } from "./SkillMatrixPanel";
import { AbsencePanel } from "./AbsencePanel";
import { EmployeeCalendarPanel } from "./EmployeeCalendarPanel";
import { CertificationPanel } from "./CertificationPanel";
import { SkillEditorPanel } from "./SkillEditorPanel";
import { ObjectivePanel } from "./ObjectivePanel";
import { WorkIntervalPanel } from "./WorkIntervalPanel";
import { RebookingPanel } from "./RebookingPanel";
import { CommissionRulePanel } from "./CommissionRulePanel";

type Props = { institute: string; timezone?: string; employees: Employee[]; services: Service[]; onChanged: () => Promise<boolean> };
export function WorkforcePanel(props: Props) {
  return <Sections key={JSON.stringify([props.institute, getAccessToken()])} {...props} />;
}
function Sections(props: Props) {
  const [section, select] = useState<"skills" | "absences" | "calendar" | "certifications" | "edit-skills" | "objectives" | "hours" | "rebooking" | "commissions">("skills");
  return <div>
    <nav className="workforce-sections" aria-label="Sections de l’équipe">
      <button aria-pressed={section === "skills"} onClick={() => select("skills")}>Compétences</button>
      {getOperatorRole() === "responsable_institut" && <button aria-pressed={section === "edit-skills"} onClick={() => select("edit-skills")}>Gérer les compétences</button>}
      {getOperatorRole() === "responsable_institut" && <button aria-pressed={section === "absences"} onClick={() => select("absences")}>Absences et congés</button>}
      {getOperatorRole() === "responsable_institut" && <button aria-pressed={section === "calendar"} onClick={() => select("calendar")}>Calendrier individuel</button>}
      {getOperatorRole() === "responsable_institut" && <button aria-pressed={section === "certifications"} onClick={() => select("certifications")}>Certifications</button>}
      {getOperatorRole() === "responsable_institut" && <button aria-pressed={section === "objectives"} onClick={() => select("objectives")}>Objectifs</button>}
      {getOperatorRole() === "responsable_institut" && <button aria-pressed={section === "hours"} onClick={() => select("hours")}>Heures effectives</button>}
      {getOperatorRole() === "responsable_institut" && <button aria-pressed={section === "rebooking"} onClick={() => select("rebooking")}>Déclarations de rebooking</button>}
      {getOperatorRole() === "responsable_institut" && <button aria-pressed={section === "commissions"} onClick={() => select("commissions")}>Règles de commission</button>}
    </nav>
    {section === "commissions" ? <CommissionRulePanel {...props} /> : section === "rebooking" ? <RebookingPanel {...props} /> : section === "hours" ? <WorkIntervalPanel {...props} /> :
    section === "skills" ? <SkillMatrixPanel instituteId={props.institute} timezone={props.timezone} /> : section === "absences" ? <AbsencePanel {...props} />
      : section === "calendar" ? <EmployeeCalendarPanel {...props} /> : section === "edit-skills" ? <SkillEditorPanel {...props} /> : section === "objectives" ? <ObjectivePanel {...props} /> : <CertificationPanel {...props} />}
  </div>;
}
