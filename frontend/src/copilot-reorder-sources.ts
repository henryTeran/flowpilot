import {validSupplier,type Supplier} from "./supplier-utils";
import {validOutlookItems,type OutlookItem,type Outlook} from "./outlook-utils";
import {revenueOriginalFingerprint as hash} from "./revenue-scenario-utils";
import {validReorderPreview,type ReorderPreview} from "./copilot-reorder-utils";
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
