import {useEffect,useRef,useState} from "react";
import {apiGet,apiPost} from "../api/client";
import {getAccessToken,getOperatorInstitute,getOperatorRole,getOperatorSubject} from "../api/session";
import {validCreationDiscovery} from "../copilot-creation-utils";
import {validSupplier,type Supplier} from "../supplier-utils";
import {validStockItem,type StockItem} from "../inventory-utils";
import {instituteMidnight} from "../outlook-utils";
import {validForecastSelection,type ForecastDraft} from "../copilot-forecast-utils";
import {readReorderSources,validReorderSources} from "../copilot-reorder-sources";
import {canonicalReorderSelection,validReorderSelection,validReorderPreview,type ReorderSelection,type ReorderPreview,type ReorderReceipt} from "../copilot-reorder-utils";
import {createReorderIntent} from "../copilot-reorder-intent";
import {revenueOriginalFingerprint as hash} from "../revenue-scenario-utils";
import {CopilotForecastSelection} from "./CopilotForecastSelection";
import type {Service} from "../types";
const storage={getItem:(k:string)=>sessionStorage.getItem(k),setItem:(k:string,v:string)=>sessionStorage.setItem(k,v),removeItem:(k:string)=>sessionStorage.removeItem(k)};
type Props={institute:string;timezone:string;services:Service[]};
export function CopilotReorderPanel(props:Props){
  if(getOperatorRole()!=="responsable_institut" || props.institute!==getOperatorInstitute() || !getOperatorSubject())return null;
  return <Panel key={JSON.stringify([props.institute,getAccessToken(),props.timezone])} {...props}/>;
}
function Panel({institute,timezone,services}:Props){
  const actor=getOperatorSubject()!,token=getAccessToken(),mounted=useRef(false),seq=useRef(0),flight=useRef(false);
  const current=()=>mounted.current && token===getAccessToken() && actor===getOperatorSubject() && institute===getOperatorInstitute() && getOperatorRole()==="responsable_institut";
  const live=(n:number)=>current() && seq.current===n;
  const [allowed,setAllowed]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState<string>();
  const [message,setMessage]=useState(""),[supplier,setSupplier]=useState(""),[selected,setSelected]=useState<string[]>([]),[reason,setReason]=useState("");
  const [assumption,setAssumption]=useState<ReorderSelection["pending_order_assumption"]|"">("");
  const [suppliers,setSuppliers]=useState<Supplier[]>(),[items,setItems]=useState<StockItem[]>(),[supplierOffset,setSupplierOffset]=useState(0),[itemOffset,setItemOffset]=useState(0);
  const [withScenario,setWithScenario]=useState(false),[forecast,setForecast]=useState<ForecastDraft>({start:"",end:"",rows:[]});
  const [preview,setPreview]=useState<ReorderPreview>(),[original,setOriginal]=useState<ReorderReceipt>();
  const [driver]=useState(()=>createReorderIntent({institute,actor,storage,current,get:p=>apiGet(p),post:(p,b)=>apiPost(p,b)}));
  const [saved,setSaved]=useState(()=>driver.state());const frozen=saved.status!=="empty";
  function edit(){seq.current++;setPreview(undefined);setOriginal(undefined);setError(undefined);}
  useEffect(()=>{mounted.current=true;const n=++seq.current;setBusy(true);void apiGet<unknown>("/copilot/preparation-capabilities").then(v=>{if(!live(n))return;if(!validCreationDiscovery(v))throw Error("Invalid registration");setAllowed(true);}).catch(()=>{if(live(n))setError("Préparations autorisées à vérifier. Rouvrez le parcours pour les relire.");}).finally(()=>{if(live(n))setBusy(false);});return()=>{mounted.current=false;seq.current++;};},[]);
  async function catalogue(kind:"suppliers"|"items",offset=0){
    if(flight.current || frozen || !allowed)return;flight.current=true;const n=++seq.current;setBusy(true);setError(undefined);setPreview(undefined);setOriginal(undefined);
    try{const v=await apiGet<unknown>(`/inventory/institutes/${encodeURIComponent(institute)}/${kind}?limit=20&offset=${offset}`);if(!live(n))return;
      if(!Array.isArray(v) || v.length>20 || new Set(v.map(r=>r?.id)).size!==v.length)throw Error("Invalid catalogue");
      if(kind==="suppliers"){if(!v.every(r=>validSupplier(r,institute)))throw Error("Invalid suppliers");setSuppliers(v);setSupplierOffset(offset);}else{if(!v.every(r=>validStockItem(r,institute)))throw Error("Invalid items");setItems(v);setItemOffset(offset);}
    }catch{if(live(n))setError("Catalogue indisponible ou à vérifier.");}finally{flight.current=false;if(live(n))setBusy(false);}
  }
  async function review(){
    if(flight.current || frozen || !allowed || !message.trim())return;
    const scenario=withScenario ? {starts_at:instituteMidnight(forecast.start,timezone),ends_at:instituteMidnight(forecast.end,timezone),demands:forecast.rows.map(r=>({service_id:r.service_id,recipe_id:r.recipe?.id??null,quantity:/^[1-9]\d{0,5}$/.test(r.quantity)?Number(r.quantity):0}))} : null;
    const selection={supplier_id:supplier,item_ids:selected,pending_order_assumption:assumption,scenario};
    if(!validReorderSelection(selection) || withScenario && !validForecastSelection({scenario})){setError("Choisissez un fournisseur, de 1 à 50 articles, une hypothèse et un scénario valide si activé.");return;}
    flight.current=true;const n=++seq.current;setBusy(true);setError(undefined);setPreview(undefined);setOriginal(undefined);
    try{const sources=await readReorderSources(institute,selection,p=>apiGet(p),(p,b)=>apiPost(p,b),()=>live(n));if(!sources || !live(n))return;
      const v=await apiPost<unknown>("/copilot/prepare-preview/reorder",{message:message.trim(),ui_context:selection});if(!live(n))return;
      if(!await validReorderPreview(v,institute) || await hash((v as ReorderPreview).selection)!==await hash(canonicalReorderSelection(selection)) || !await validReorderSources(v as ReorderPreview,institute,sources.supplier,sources.rows,sources.demands))throw Error("Invalid proposal sources");
      if(live(n))setPreview(v as ReorderPreview);
    }catch{if(live(n))setError("Sources ou aperçu à vérifier. Relisez les sélections.");}finally{flight.current=false;if(live(n))setBusy(false);}
  }
  async function retain(correction=false){
    if(flight.current || !allowed || !current())return;
    if(saved.status==="empty" && (!preview || reason.trim()!==reason || Array.from(reason).length<3 || Array.from(reason).length>240 || /[\x00-\x1f]/.test(reason))){setError("Vérifiez la proposition puis saisissez un motif exact de 3 à 240 caractères.");return;}
    flight.current=true;const n=++seq.current;setBusy(true);setError(undefined);setOriginal(undefined);
    try{const r=correction ? await driver.correct() : saved.status!=="empty" ? await driver.submit() : await driver.submit({message:message.trim(),proposal:{selection:preview!.selection,expected_state_fingerprint:preview!.state_fingerprint,reason,idempotency_key:crypto.randomUUID()}});if(!live(n))return;
      if(r.status==="confirmed"){setOriginal(r.original);setPreview(undefined);setReason("");}else if(r.status==="correctable"){setPreview(undefined);setError("Rejet vérifié. Relisez les sources avant une nouvelle demande.");}else if(r.status==="busy")setError("Une reprise est déjà en cours.");
    }catch{if(live(n))setError("Proposition à vérifier. Reprenez la demande conservée avant une nouvelle préparation.");}finally{flight.current=false;if(live(n)){setSaved(driver.state());setBusy(false);}}
  }
  const proposal=(p:ReorderPreview)=><><p>Fournisseur : {p.selection.supplier_id}. Couverture : {p.coverage==="not_applicable" ? "Stock enregistré sans scénario" : p.coverage==="complete_selected_norms" ? "Normes sélectionnées complètes" : "Normes sélectionnées partielles : besoins inconnus possibles"}. Hypothèse : {p.selection.pending_order_assumption==="ignore_pending_orders" ? "Commandes en attente ignorées" : "Toutes les commandes en attente reçues"}.</p><div className="copilot-table" role="region" aria-label="Quantités de réapprovisionnement" tabIndex={0}><table><thead><tr><th>Article</th><th>Stock</th><th>Seuil</th><th>En attente</th><th>Besoin connu</th><th>Quantité proposée</th></tr></thead><tbody>{p.items.map(i=><tr key={i.item_id}><td>{i.item_id}</td><td>{i.on_hand} {i.unit}</td><td>{i.threshold}</td><td>{i.pending_order_quantity}</td><td>{i.known_demand}</td><td>{i.proposed_quantity} {i.unit}</td></tr>)}</tbody></table></div><p>Proposition uniquement : aucun devis fournisseur, commande, contact, paiement, réception ou mouvement de stock.</p></>;
  return <section className="copilot-panel copilot-reorder" aria-label="Copilot"><h2>Préparer un réapprovisionnement</h2>
    {saved.status==="invalid" && <p role="alert">Demande conservée illisible. Nouvelle préparation bloquée.</p>}
    {saved.status==="frozen" && <article aria-label="Demande de réapprovisionnement conservée"><h3>Proposition à reprendre</h3><p>{saved.terms.proposal.reason} · fournisseur {saved.terms.proposal.selection.supplier_id}.</p><button disabled={busy || !allowed} onClick={()=>void retain()}>Reprendre le réapprovisionnement</button>{driver.canCorrect() && <button disabled={busy || !allowed} onClick={()=>void retain(true)}>Vérifier le rejet du réapprovisionnement et corriger</button>}</article>}
    <form onSubmit={e=>{e.preventDefault();void review();}}><fieldset disabled={busy || frozen || !allowed}>
      <label>Votre demande de réapprovisionnement<textarea maxLength={2000} value={message} onChange={e=>{edit();setMessage(e.target.value);}}/></label>
      <button type="button" onClick={()=>void catalogue("suppliers")}>Lire les fournisseurs</button>
      <label>Fournisseur sélectionné<select value={supplier} onChange={e=>{edit();setSupplier(e.target.value);}}><option value="">Choisir un fournisseur</option>{supplier && !suppliers?.some(s=>s.id===supplier) && <option value={supplier}>{supplier} · sélection conservée</option>}{suppliers?.map(s=><option key={s.id} value={s.id}>{s.name} · {s.reference}</option>)}</select></label>
      {suppliers && <><button type="button" disabled={!supplierOffset} onClick={()=>void catalogue("suppliers",supplierOffset-20)}>Fournisseurs précédents</button><button type="button" disabled={suppliers.length!==20 || supplierOffset>=100000} onClick={()=>void catalogue("suppliers",supplierOffset+20)}>Fournisseurs suivants</button></>}
      <button type="button" onClick={()=>void catalogue("items")}>Lire les articles</button>
      {items?.map(i=><label className="copilot-reorder-toggle" key={i.id}><input type="checkbox" checked={selected.includes(i.id)} disabled={!selected.includes(i.id) && selected.length>=50} onChange={e=>{edit();setSelected(e.target.checked?[...selected,i.id]:selected.filter(id=>id!==i.id));}}/>{i.name} · {i.sku} · {i.unit}</label>)}
      {items && <><button type="button" disabled={!itemOffset} onClick={()=>void catalogue("items",itemOffset-20)}>Articles précédents</button><button type="button" disabled={items.length!==20 || itemOffset>=100000} onClick={()=>void catalogue("items",itemOffset+20)}>Articles suivants</button></>}
      <p>{selected.length} article(s) sélectionné(s).</p>{selected.length>0 && <div className="copilot-reorder-selection" role="group" aria-label="Articles sélectionnés" tabIndex={0}>{selected.map(id=><button type="button" key={id} onClick={()=>{edit();setSelected(selected.filter(s=>s!==id));}}>Retirer {id}</button>)}</div>}
      <label>Hypothèse des commandes en attente<select value={assumption} onChange={e=>{edit();setAssumption(e.target.value as typeof assumption);}}><option value="">Choisir explicitement</option><option value="ignore_pending_orders">Ignorer les commandes en attente</option><option value="all_pending_orders_received">Supposer toutes les commandes en attente reçues</option></select></label>
      <label className="copilot-reorder-toggle"><input type="checkbox" checked={withScenario} onChange={e=>{edit();setWithScenario(e.target.checked);}}/>Inclure un scénario de prestations</label>
      {withScenario && <CopilotForecastSelection institute={institute} timezone={timezone} services={services} value={forecast} onChange={v=>{edit();setForecast(v);}}/>}
      <button disabled={!message.trim()}>Vérifier le réapprovisionnement</button></fieldset></form>
    {busy && <p role="status">Vérification en cours…</p>}{error && <p role="alert">{error}</p>}
    {preview && <article aria-label="Réapprovisionnement vérifié"><h3>Proposition vérifiée</h3>{proposal(preview)}<fieldset disabled={busy || frozen || !allowed}><label>Motif du réapprovisionnement<input maxLength={240} value={reason} onChange={e=>setReason(e.target.value)}/></label><button onClick={()=>void retain()}>Conserver la proposition de réapprovisionnement</button></fieldset></article>}
    {original && <article aria-label="Réapprovisionnement conservé"><h3>Proposition conservée et relue</h3><p>Original : {original.original.id}. Auteur : {original.original.actor_id}. Motif : {original.original.reason}.</p>{proposal(original.original.preview)}</article>}
  </section>;
}
