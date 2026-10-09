import {validScenario,validOutlook,type Scenario,type Outlook} from "./outlook-utils";
import {certificationInstant as instant} from "./certification-utils";
import {validRecipe,type Recipe} from "./recipe-utils";
import {stockMilli} from "./inventory-utils";
export type ForecastRow={service_id:string;recipe:Recipe|null;quantity:string};
export type ForecastDraft={start:string;end:string;rows:ForecastRow[]};
export function validForecastOriginals(value:Outlook,rows:ForecastRow[],institute:string):boolean{
  if(!rows.length || rows.length>50 || new Set(rows.map(r=>r.service_id)).size!==rows.length || value.demands.length!==rows.length || rows.some(r=>!id(r.service_id) || !/^[1-9]\d{0,5}$/.test(r.quantity) || Number(r.quantity)>100000 || r.recipe && !validRecipe(r.recipe,institute,r.service_id)))return false;
  if(!value.demands.every(d=>{const row=rows.find(r=>r.service_id===d.service_id);return !!row && d.recipe_id===(row.recipe?.id??null) && d.quantity===Number(row.quantity) && d.recipe_revision===(row.recipe?.revision??null) && d.state===(row.recipe ? row.recipe.enabled ? "enabled" : "disabled" : "missing_selected_norm");}))return false;
  return value.items.every(item=>{
    let expected=0n;
    for(const row of rows)if(row.recipe?.enabled)for(const entry of row.recipe.entries)if(entry.item_id===item.item_id){if(entry.unit!==item.unit)return false;expected+=stockMilli(entry.quantity)*BigInt(row.quantity);}
    return stockMilli(item.known_demand)===expected;
  });
}
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
