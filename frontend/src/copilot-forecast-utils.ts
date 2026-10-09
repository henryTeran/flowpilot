import {validScenario,validOutlook,type Scenario,type Outlook} from "./outlook-utils";
import {certificationInstant as instant} from "./certification-utils";
const keys=(v:unknown,names:string):v is Record<string,unknown>=>!!v && typeof v==="object" && !Array.isArray(v) && Object.keys(v).sort().join(" ")===names.split(" ").sort().join(" ");
const id=(v:unknown):v is string=>typeof v==="string" && !!v && v.trim()===v && Array.from(v).length<=80 && !/[\x00-\x1f]/.test(v);
export function validForecastSelection(v:unknown):v is {scenario:Scenario}{
  if(!keys(v,"scenario") || !keys(v.scenario,"starts_at ends_at demands") || !validScenario(v.scenario))return false;
  const s=v.scenario,first=instant(s.starts_at),last=instant(s.ends_at);
  return first!==undefined && last!==undefined && first<last && last-first<=366n*86400000000n
    && s.demands.every(d=>keys(d,"service_id recipe_id quantity") && id(d.service_id) && (d.recipe_id===null || id(d.recipe_id)));
}
export function validForecastFacts(v:unknown,institute:string,selection:unknown,capture:string):v is Outlook{
  if(!validForecastSelection(selection) || !keys(v,"institute_id generated_at starts_at ends_at source coverage demands limit offset items")
    || instant(capture)===undefined || !validOutlook(v,institute,0,selection.scenario,50) || instant(v.generated_at)!==instant(capture)
    || instant(v.starts_at)!==instant(selection.scenario.starts_at) || instant(v.ends_at)!==instant(selection.scenario.ends_at))return false;
  return v.demands.every(d=>keys(d,"service_id recipe_id quantity service_name recipe_revision state"));
}
