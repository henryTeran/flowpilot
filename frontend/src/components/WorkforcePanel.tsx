import { useState } from "react";
import { getAccessToken, getOperatorRole } from "../api/session";
import type { Employee } from "../types";
import { SkillMatrixPanel } from "./SkillMatrixPanel";
import { AbsencePanel } from "./AbsencePanel";

type Props = { institute: string; timezone?: string; employees: Employee[]; onChanged: () => Promise<boolean> };
export function WorkforcePanel(props: Props) {
  return <Sections key={JSON.stringify([props.institute, getAccessToken()])} {...props} />;
}
function Sections(props: Props) {
  const [section, select] = useState<"skills" | "absences">("skills");
  return <div>
    <nav className="workforce-sections" aria-label="Sections de l’équipe">
      <button aria-pressed={section === "skills"} onClick={() => select("skills")}>Compétences</button>
      {getOperatorRole() === "responsable_institut" && <button aria-pressed={section === "absences"} onClick={() => select("absences")}>Absences et congés</button>}
    </nav>
    {section === "skills" ? <SkillMatrixPanel instituteId={props.institute} timezone={props.timezone} /> : <AbsencePanel {...props} />}
  </div>;
}
