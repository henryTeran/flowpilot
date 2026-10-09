import {useEffect,useRef,useState} from "react";
import {apiGet,apiPost} from "../api/client";
import {getAccessToken,getOperatorInstitute,getOperatorRole,getOperatorSubject} from "../api/session";
import {validCreationDiscovery} from "../copilot-creation-utils";
import {validAudienceCatalog,type AudienceCatalog} from "../marketing-audience-utils";
import {validTemplateCatalog,type TemplateCatalog} from "../marketing-template-utils";
import {readMarketingSources} from "../copilot-marketing-sources";
import {validMarketingPreview,type MarketingPreview} from "../copilot-marketing-utils";
import {createMarketingIntent} from "../copilot-marketing-intent";
import type {CampaignContent,CampaignOriginal} from "../marketing-campaign-utils";
const storage={getItem:(k:string)=>sessionStorage.getItem(k),setItem:(k:string,v:string)=>sessionStorage.setItem(k,v),removeItem:(k:string)=>sessionStorage.removeItem(k)};
type Props={initialMessage?:string;institute:string};
export function CopilotMarketingPanel(props:Props){
  if(getOperatorRole()!=="responsable_institut" || props.institute!==getOperatorInstitute() || !getOperatorSubject())return null;
  return <Panel key={JSON.stringify([props.institute,getAccessToken()])} {...props}/>;
}
function Panel({initialMessage="",institute}:Props){
  const actor=getOperatorSubject()!,token=getAccessToken(),mounted=useRef(false),seq=useRef(0),flight=useRef(false);
  const current=()=>mounted.current && token===getAccessToken() && actor===getOperatorSubject() && institute===getOperatorInstitute() && getOperatorRole()==="responsable_institut";
  const [allowed,setAllowed]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState<string>();
  const [message,setMessage]=useState(initialMessage),[audience,setAudience]=useState(""),[template,setTemplate]=useState(""),[reason,setReason]=useState("");
  const [audiences,setAudiences]=useState<AudienceCatalog>(),[templates,setTemplates]=useState<TemplateCatalog>();
  const [preview,setPreview]=useState<MarketingPreview>(),[content,setContent]=useState<CampaignContent>(),[original,setOriginal]=useState<CampaignOriginal>();
  const [driver]=useState(()=>createMarketingIntent({institute,actor,storage,current,get:p=>apiGet(p),post:(p,b)=>apiPost(p,b)}));
  const [saved,setSaved]=useState(()=>driver.state());const frozen=saved.status!=="empty";
  const live=(n:number)=>current() && seq.current===n;
  function edit(){seq.current++;setPreview(undefined);setContent(undefined);setOriginal(undefined);setError(undefined);}
  useEffect(()=>{mounted.current=true;const n=++seq.current;setBusy(true);void apiGet<unknown>("/copilot/preparation-capabilities").then(v=>{if(!live(n))return;if(!validCreationDiscovery(v))throw Error("Invalid registration");setAllowed(true);}).catch(()=>{if(live(n))setError("Préparations autorisées à vérifier. Rouvrez le parcours pour les relire.");}).finally(()=>{if(live(n))setBusy(false);});return()=>{mounted.current=false;seq.current++;};},[]);
  async function catalogue(kind:"audiences"|"templates",offset=0){
    if(flight.current || frozen || !allowed)return;flight.current=true;const n=++seq.current;setBusy(true);setError(undefined);setPreview(undefined);setContent(undefined);setOriginal(undefined);
    try{const v=await apiGet<unknown>(`/marketing/institutes/${encodeURIComponent(institute)}/${kind==="audiences" ? "audience-captures" : "templates"}?offset=${offset}&limit=20`);if(!live(n))return;
      if(kind==="audiences"){if(!validAudienceCatalog(v,institute,offset,20))throw Error("Invalid audiences");setAudiences(v);}else{if(!validTemplateCatalog(v,institute,offset,20))throw Error("Invalid templates");setTemplates(v);}
    }catch{if(live(n))setError("Catalogue indisponible ou à vérifier.");}finally{flight.current=false;if(live(n))setBusy(false);}
  }
  async function review(){
    if(flight.current || frozen || !allowed || !message.trim())return;
    const a=audiences?.items.find(a=>a.id===audience),t=templates?.items.find(t=>t.id===template);
    if(!a || !t || a.request.channel!==t.content.channel || !a.summary.eligible_count){setError("Choisissez une audience admissible et un modèle du même canal.");return;}
    flight.current=true;const n=++seq.current;setBusy(true);setError(undefined);setPreview(undefined);setContent(undefined);setOriginal(undefined);
    try{const selection={audience_id:audience,template_original_id:template},sources=await readMarketingSources(institute,selection,p=>apiGet(p),()=>live(n));if(!sources || !live(n))return;
      const v=await apiPost<unknown>("/copilot/prepare-preview/marketing",{message:message.trim(),ui_context:selection});if(!live(n))return;
      if(!await validMarketingPreview(v,institute,selection,sources.content,actor))throw Error("Invalid preview");if(live(n)){setContent(sources.content);setPreview(v as MarketingPreview);}
    }catch{if(live(n))setError("Sources ou aperçu à vérifier. Relisez les sélections.");}finally{flight.current=false;if(live(n))setBusy(false);}
  }
  async function retain(correction=false){
    if(flight.current || !allowed || !current())return;
    if(saved.status==="empty" && (!preview || reason.trim()!==reason || Array.from(reason).length<3 || Array.from(reason).length>240 || /[\x00-\x1f]/.test(reason))){setError("Vérifiez le brouillon puis saisissez un motif exact de 3 à 240 caractères.");return;}
    flight.current=true;const n=++seq.current;setBusy(true);setError(undefined);setOriginal(undefined);
    try{const r=correction ? await driver.correct() : saved.status!=="empty" ? await driver.submit() : await driver.submit({message:message.trim(),ui_context:preview!.selection,expected_state_fingerprint:preview!.state_fingerprint,reason,idempotency_key:crypto.randomUUID()});if(!live(n))return;
      if(r.status==="confirmed"){setOriginal(r.original);setPreview(undefined);setContent(undefined);setReason("");}else if(r.status==="correctable"){setPreview(undefined);setContent(undefined);setError("Rejet vérifié. Relisez les sources avant une nouvelle demande.");}else if(r.status==="busy")setError("Une reprise est déjà en cours.");
    }catch{if(live(n))setError("Brouillon à vérifier. Reprenez la demande conservée avant une nouvelle préparation.");}finally{flight.current=false;if(live(n)){setSaved(driver.state());setBusy(false);}}
  }
  return <section className="copilot-panel" aria-label="Copilot"><h2>Préparer un brouillon marketing</h2><p>Choisissez une audience conservée et un modèle original. Ce parcours conserve un brouillon sans approbation ni envoi.</p>
    {saved.status==="invalid" && <p role="alert">Demande conservée illisible. Nouvelle préparation bloquée.</p>}
    {saved.status==="frozen" && <article aria-label="Demande de brouillon conservée"><h3>Brouillon à reprendre</h3><p>{saved.terms.reason} · audience {saved.terms.ui_context.audience_id} · modèle {saved.terms.ui_context.template_original_id}.</p><button disabled={busy || !allowed} onClick={()=>void retain()}>Reprendre le brouillon</button>{driver.canCorrect() && <button disabled={busy || !allowed} onClick={()=>void retain(true)}>Vérifier le rejet du brouillon et corriger</button>}</article>}
    <form onSubmit={e=>{e.preventDefault();void review();}}><fieldset disabled={busy || frozen || !allowed}>
      <label>Votre demande de brouillon<textarea maxLength={2000} value={message} onChange={e=>{edit();setMessage(e.target.value);}}/></label>
      <button type="button" onClick={()=>void catalogue("audiences")}>Lire les audiences conservées</button>
      {audiences && <><label>Audience sélectionnée<select value={audience} onChange={e=>{edit();setAudience(e.target.value);}}><option value="">Choisir une audience</option>{audiences.items.map(a=><option key={a.id} value={a.id}>{a.id} · {a.request.channel} · {a.summary.eligible_count} admissible(s)</option>)}</select></label><p>{audiences.total} audience(s), page de {audiences.offset+1} à {audiences.offset+audiences.items.length}.</p><button type="button" disabled={!audiences.offset} onClick={()=>void catalogue("audiences",Math.max(0,audiences.offset-20))}>Audiences précédentes</button><button type="button" disabled={audiences.offset+20>=audiences.total} onClick={()=>void catalogue("audiences",audiences.offset+20)}>Audiences suivantes</button></>}
      <button type="button" onClick={()=>void catalogue("templates")}>Lire les modèles originaux</button>
      {templates && <><label>Modèle sélectionné<select value={template} onChange={e=>{edit();setTemplate(e.target.value);}}><option value="">Choisir un modèle</option>{templates.items.map(t=><option key={t.id} value={t.id}>{t.content.name} · {t.content.channel}</option>)}</select></label><button type="button" disabled={!templates.offset} onClick={()=>void catalogue("templates",Math.max(0,templates.offset-20))}>Modèles précédents</button><button type="button" disabled={templates.offset+20>=templates.total} onClick={()=>void catalogue("templates",templates.offset+20)}>Modèles suivants</button></>}
      <button disabled={!message.trim()}>Vérifier le brouillon marketing</button></fieldset></form>
    {busy && <p role="status">Vérification en cours…</p>}{error && <p role="alert">{error}</p>}
    {preview && content && <article aria-label="Brouillon marketing vérifié"><h3>Texte du modèle vérifié</h3><p>Canal : {content.channel}. {preview.recipient_count} destinataire(s) dans l’audience conservée.</p>{content.subject && <p>{content.subject}</p>}<pre>{content.body}</pre><p>Les champs du modèle restent littéraux. Aucun brouillon conservé ni contact effectué à cette étape.</p><fieldset disabled={busy || frozen || !allowed}><label>Motif du brouillon<input maxLength={240} value={reason} onChange={e=>setReason(e.target.value)}/></label><button onClick={()=>void retain()}>Conserver le brouillon marketing</button></fieldset></article>}
    {original && <article aria-label="Brouillon marketing conservé"><h3>Brouillon conservé et relu</h3><p>Campagne : {original.revision.campaign_id}. Original : {original.revision.id}. État : DRAFT.</p><p>Auteur : {original.revision.actor_id}. Motif : {original.revision.reason}.</p>{original.revision.content.subject && <p>{original.revision.content.subject}</p>}<pre>{original.revision.content.body}</pre><p>{original.revision.content.audience.customer_ids.length} destinataire(s) dans l’audience historique. Aucun contact ni envoi autorisé par ce brouillon.</p></article>}
  </section>;
}
