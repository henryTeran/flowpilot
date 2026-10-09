import {validSupplier,type Supplier} from "./supplier-utils";
import {validOutlook,validOutlookItems,type OutlookItem,type Outlook} from "./outlook-utils";
import {revenueOriginalFingerprint as hash} from "./revenue-scenario-utils";
import {validReorderSelection,validReorderPreview,type ReorderPreview,type ReorderSelection} from "./copilot-reorder-utils";
import {validRecipe} from "./recipe-utils";
import {validForecastOriginals,type ForecastRow} from "./copilot-forecast-utils";
// Recorded-stock reads only: scenario sources require independently checked recipe originals.
export async function readRecordedReorderSources(institute:string,selection:ReorderSelection,get:(path:string)=>Promise<unknown>,current:()=>boolean):Promise<{supplier:Supplier;rows:OutlookItem[];demands:Outlook["demands"]}|undefined>{
  if(!validReorderSelection(selection) || selection.scenario!==null || !current())return;
  return readReorderSources(institute,selection,get,async()=>{throw Error("Unexpected scenario read");},current);
}
export async function readReorderSources(institute:string,selection:ReorderSelection,get:(path:string)=>Promise<unknown>,post:(path:string,body:unknown)=>Promise<unknown>,current:()=>boolean):Promise<{supplier:Supplier;rows:OutlookItem[];demands:Outlook["demands"]}|undefined>{
  if(!validReorderSelection(selection) || !current())return;
  const base=`/inventory/institutes/${encodeURIComponent(institute)}`;
  const supplier=await get(`${base}/suppliers/${encodeURIComponent(selection.supplier_id)}`);
  if(!current())return;
  if(!validSupplier(supplier,institute) || supplier.id!==selection.supplier_id)throw Error("Invalid selected supplier original");
  const originals:ForecastRow[]=[];
  for(const demand of selection.scenario?.demands??[]){
    const recipe=demand.recipe_id===null ? null : await get(`${base}/recipes/${encodeURIComponent(demand.recipe_id)}`);
    if(!current())return;
    if(recipe!==null && (!validRecipe(recipe,institute,demand.service_id) || recipe.id!==demand.recipe_id))throw Error("Invalid selected recipe original");
    if(demand.recipe_id!==null && recipe===null)throw Error("Selected recipe original missing");
    originals.push({service_id:demand.service_id,quantity:String(demand.quantity),recipe});
  }
  let demands:Outlook["demands"]|undefined;
  const rows:OutlookItem[]=[],seen=new Set<string>(),skus=new Set<string>();
  for(let offset=0;offset<=100000;offset+=50){
    if(!current())return;
    const page=selection.scenario===null ? await get(`${base}/outlook?limit=50&offset=${offset}`) : await post(`${base}/forecast?limit=50&offset=${offset}`,selection.scenario);
    if(!current())return;
    if(!validOutlook(page,institute,offset,selection.scenario??undefined,50) || selection.scenario!==null && !validForecastOriginals(page,originals,institute))throw Error("Invalid stock source page or selected recipe projection");
    if(demands!==undefined && await hash(demands)!==await hash(page.demands))throw Error("Scenario demand sources changed across pages");
    demands=page.demands;
    if(!current())return;
    for(const row of page.items){
      if(seen.has(row.item_id) || skus.has(row.item_sku))throw Error("Repeated stock source across pages");
      seen.add(row.item_id);skus.add(row.item_sku);
      if(selection.item_ids.includes(row.item_id))rows.push(row);
    }
    if(page.items.length<50){
      if(rows.length!==selection.item_ids.length)throw Error("Selected stock source missing");
      return {supplier,rows,demands};
    }
  }
  throw Error("Recorded stock pagination did not finish");
}
// Bind the compact proposal to the supplier and full original stock projection read by the UI.
export async function validReorderSources(preview:ReorderPreview,institute:string,supplier:Supplier,rows:OutlookItem[],demands:Outlook["demands"]):Promise<boolean>{
  try{
    if(!await validReorderPreview(preview,institute) || !validSupplier(supplier,institute) || supplier.id!==preview.selection.supplier_id || !validOutlookItems(rows,preview.coverage==="complete_selected_norms",preview.selection.scenario===null,50) || rows.length!==preview.selection.item_ids.length || new Set(rows.map(r=>r.item_id)).size!==rows.length || !rows.every(r=>preview.selection.item_ids.includes(r.item_id)) || !Array.isArray(demands))return false;
    if(preview.selection.scenario===null && demands.length!==0)return false;
    if(preview.selection.scenario!==null && (demands.length!==preview.selection.scenario.demands.length || new Set(demands.map(d=>d.service_id)).size!==demands.length || !demands.every(d=>{
      const selected=preview.selection.scenario!.demands.find(s=>s.service_id===d.service_id);return !!selected && selected.recipe_id===d.recipe_id && selected.quantity===d.quantity;
    })))return false;
    for(let i=0;i<rows.length;i++){
      const r=rows[i],p=preview.items[i];if(p.item_id!==r.item_id || p.unit!==r.unit || p.on_hand!==r.on_hand || p.threshold!==r.threshold || p.pending_order_quantity!==r.pending_order_quantity || p.known_demand!==r.known_demand || p.complete_demand!==r.complete_demand || p.proposed_quantity!==(preview.selection.pending_order_assumption==="ignore_pending_orders" ? r.known_demand_shortfall : r.conditional_shortfall_after_all_orders))return false;
    }
    return preview.source_digest===await hash({supplier,demands,items:rows});
  }catch{return false;}
}
