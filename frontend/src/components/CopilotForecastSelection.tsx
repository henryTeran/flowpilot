import {useEffect,useRef,useState} from "react";
import {apiGet} from "../api/client";
import {getAccessToken,getOperatorInstitute} from "../api/session";
import {validRecipe,type Recipe} from "../recipe-utils";
import type {ForecastDraft} from "../copilot-forecast-utils";
import type {Service} from "../types";

export function CopilotForecastSelection({institute,timezone,services,value,onChange}:{institute:string;timezone:string;services:Service[];value:ForecastDraft;onChange:(v:ForecastDraft)=>void}){
  const token=getAccessToken(),mounted=useRef(false),sequence=useRef(0);
  const [service,setService]=useState(""),[recipes,setRecipes]=useState<Recipe[]>(),[choice,setChoice]=useState(""),[offset,setOffset]=useState(0),[busy,setBusy]=useState(false),[error,setError]=useState<string>();
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;sequence.current++;};},[]);
  const current=(seq:number)=>mounted.current && sequence.current===seq && token===getAccessToken() && institute===getOperatorInstitute();
  function selectService(id:string){sequence.current++;setService(id);setRecipes(undefined);setChoice("");setOffset(0);setBusy(false);setError(undefined);}
  async function read(page:number){
    if(busy || !services.some(s=>s.id===service))return;
    const seq=++sequence.current;setBusy(true);setError(undefined);setRecipes(undefined);setChoice("");
    try{
      const rows=await apiGet<unknown>(`/inventory/institutes/${encodeURIComponent(institute)}/services/${encodeURIComponent(service)}/recipes?limit=10&offset=${page}`);
      if(!current(seq))return;
      if(!Array.isArray(rows) || rows.length>10 || !rows.every(r=>validRecipe(r,institute,service)) || new Set(rows.map(r=>r.id)).size!==rows.length)throw Error("Invalid originals");
      setRecipes(rows);setOffset(page);
    }catch{if(current(seq))setError("Normes indisponibles ou à vérifier. Relancez la lecture.");}finally{if(current(seq))setBusy(false);}
  }
  function add(){
    const recipe=choice==="missing" ? null : recipes?.find(r=>r.id===choice);
    if(recipe===undefined || !services.some(s=>s.id===service) || value.rows.length>=50 || value.rows.some(r=>r.service_id===service))return;
    onChange({...value,rows:[...value.rows,{service_id:service,recipe,quantity:""}]});selectService("");
  }
  return <div aria-label="Scénario de projection"><p>Volumes choisis pour la période ; aucune prévision de fréquentation. Dates à minuit dans le fuseau {timezone}.</p>
    <label>Premier jour du scénario<input type="date" value={value.start} onChange={e=>onChange({...value,start:e.target.value})}/></label>
    <label>Fin du scénario exclue<input type="date" value={value.end} onChange={e=>onChange({...value,end:e.target.value})}/></label>
    <label>Prestation du scénario<select value={service} onChange={e=>selectService(e.target.value)}><option value="">Choisir une prestation</option>{services.filter(s=>!value.rows.some(r=>r.service_id===s.id)).map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
    {service && <><button type="button" disabled={busy} onClick={()=>void read(0)}>Lire les normes originales</button>
      <label>Norme du scénario<select value={choice} onChange={e=>setChoice(e.target.value)}><option value="">Choisir explicitement une norme</option><option value="missing">Aucune norme sélectionnée : besoins inconnus</option>{recipes?.map(r=><option key={r.id} value={r.id}>Version {r.revision} · {r.enabled ? "Active" : "Désactivée"}</option>)}</select></label>
      <button type="button" disabled={busy || !choice || value.rows.length>=50} onClick={add}>Ajouter au scénario</button>
      {recipes && <><button type="button" disabled={busy || !offset} onClick={()=>void read(offset-10)}>Normes précédentes</button><button type="button" disabled={busy || recipes.length!==10} onClick={()=>void read(offset+10)}>Normes suivantes</button></>}
    </>}{busy && <p role="status">Lecture des normes…</p>}{error && <p role="alert">{error}</p>}
    {value.rows.map(row=>{const name=services.find(s=>s.id===row.service_id)?.name || "Prestation enregistrée";return <div key={row.service_id}><p>{name} · {row.recipe ? `Norme originale v${row.recipe.revision} · ${row.recipe.enabled ? "active" : "désactivée"}` : "Norme non sélectionnée : besoins inconnus"}</p><label>Volume de {name}<input inputMode="numeric" value={row.quantity} onChange={e=>onChange({...value,rows:value.rows.map(r=>r===row ? {...r,quantity:e.target.value} : r)})}/></label><button type="button" onClick={()=>onChange({...value,rows:value.rows.filter(r=>r!==row)})}>Retirer {name} du scénario</button></div>;})}
    <p>Jusqu’à 50 prestations distinctes, volumes entiers de 1 à 100000 et horizon maximal de 366 jours.</p>
  </div>;
}
