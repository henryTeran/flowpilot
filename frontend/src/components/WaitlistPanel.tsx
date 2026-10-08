import { useState } from "react";
import { WaitlistDemandWriter } from "./WaitlistDemandWriter";
import { WaitlistOriginalHistory } from "./WaitlistOriginalHistory";
import { WaitlistLifecycleHistory } from "./WaitlistLifecycleHistory";
import type { Employee, Service } from "../types";

export function WaitlistPanel(props: { institute: string; timezone?: string; services: Service[]; employees: Employee[] }) {
  const [revision, setRevision] = useState(0);
  return <><WaitlistDemandWriter {...props} onRetained={() => setRevision(n => n+1)} />
    <WaitlistOriginalHistory key={revision} institute={props.institute} timezone={props.timezone} />
    <WaitlistLifecycleHistory institute={props.institute} timezone={props.timezone} /></>;
}
