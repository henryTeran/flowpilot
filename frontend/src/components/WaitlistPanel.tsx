import { useState } from "react";
import { WaitlistDemandWriter } from "./WaitlistDemandWriter";
import { WaitlistOriginalHistory } from "./WaitlistOriginalHistory";
import { WaitlistLifecycleHistory } from "./WaitlistLifecycleHistory";
import { WaitlistMatchingReview } from "./WaitlistMatchingReview";
import { WaitlistLifecycleWriter, type WaitlistLifecycleChoice } from "./WaitlistLifecycleWriter";
import { getAccessToken } from "../api/session";
import type { WaitlistLifecycleState } from "../waitlist-lifecycle-utils";
import type { Employee, Service } from "../types";

export function WaitlistPanel(props: { institute: string; timezone?: string; services: Service[]; employees: Employee[] }) {
  return <Panel key={JSON.stringify([props.institute, props.timezone, getAccessToken()])} {...props} />;
}
function Panel(props: { institute: string; timezone?: string; services: Service[]; employees: Employee[] }) {
  const [revision, setRevision] = useState(0);
  const [choice, setChoice] = useState<WaitlistLifecycleChoice>(), [context, setContext] = useState<WaitlistLifecycleState>();
  const [matching, setMatching] = useState<WaitlistLifecycleState>();
  return <><WaitlistDemandWriter {...props} onRetained={() => { setMatching(undefined); setRevision(n => n+1); }} />
    <WaitlistLifecycleWriter institute={props.institute} timezone={props.timezone} choice={choice} onContext={setContext} onRetained={() => { setMatching(undefined); setRevision(n => n+1); }} />
    <WaitlistMatchingReview key={`matching-${revision}`} {...props} selection={matching} />
    <WaitlistOriginalHistory key={`originals-${revision}`} institute={props.institute} timezone={props.timezone}
      onManage={envelope => setChoice({ kind: "root", envelope })} onRevise={envelope => setChoice({ kind: "target", envelope })}
      revisionFor={context?.state === "active" ? { customer: context.root.original.demand.customer_id, current: context.current_demand.original.id } : undefined} />
    <WaitlistLifecycleHistory key={`lifecycle-${revision}`} institute={props.institute} timezone={props.timezone} onManage={state => setChoice({ kind: "root", envelope: state.root })} onMatch={setMatching} /></>;
}
