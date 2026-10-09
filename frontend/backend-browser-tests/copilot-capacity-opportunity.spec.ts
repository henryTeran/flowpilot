import {expect,test} from "@playwright/test";

test("BASE conditional slot projection follows room availability without reserving capacity",async({page,request},info)=>{
  test.setTimeout(120000);test.skip(process.env.FLOWPILOT_BROWSER_PLANNING_FIXTURE!=="1","Explicit owned planning fixture required");
  const api="http://127.0.0.1:4198/api/v1",institute="demo-institute-geneve",snapshotUrl="http://127.0.0.1:4198/_fixture/planning";
  const auth=await request.post(api+"/auth/login",{data:{email:"manager@browser.example.com",password:"Browser-test-only-2026"}});expect(auth.status()).toBe(200);const headers={Authorization:`Bearer ${(await auth.json()).access_token}`};
  async function get(path:string){const r=await request.get(api+path,{headers});expect(r.status(),await r.text()).toBe(200);return r.json();}
  async function snapshot(){const r=await request.get(snapshotUrl);expect(r.status()).toBe(200);return r.json();}
  const before=await snapshot(),resourcesPath=`/resources/institutes/${institute}`,resourceBefore=await get(resourcesPath);
  const day=new Date(Date.now()+48*3600000).toISOString().slice(0,10),horizon=day+"T12:00";
  await page.goto("/");await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");await page.getByRole("button",{name:"Se connecter",exact:true}).click();await expect(page.locator(".flow-session-exit")).toBeVisible();await page.getByRole("button",{name:"Copilot",exact:true}).click();
  const panel=page.getByRole("region",{name:"Copilot",exact:true}),writes:string[]=[];page.on("request",r=>{if(!["GET","HEAD","OPTIONS"].includes(r.method()))writes.push(r.url());});
  await panel.getByRole("combobox",{name:"Consultation",exact:true}).selectOption("REVENUE_OPPORTUNITIES");await panel.getByRole("combobox",{name:"Source des opportunités",exact:true}).selectOption("capacity");await panel.getByRole("combobox",{name:"Prestation sélectionnée",exact:true}).selectOption("browser-capacity-care");await panel.getByLabel("Horizon local").fill(horizon);await panel.getByRole("textbox",{name:"Votre question",exact:true}).fill("Examiner les opportunites de revenus");
  async function consult(available:boolean,label:string){
    const sources=await snapshot(),resources=await get(resourcesPath),pending=page.waitForResponse(r=>r.url().endsWith("/copilot/query")&&r.request().method()==="POST");await panel.getByRole("button",{name:"Consulter",exact:true}).click();const response=await pending;expect(response.status()).toBe(200);const evidence=(await response.json()).evidence,value=evidence.result;
    expect(evidence.capability).toBe("REVENUE_OPPORTUNITIES");expect(value.service_id).toBe("browser-capacity-care");
    const local=new Intl.DateTimeFormat("sv-SE",{timeZone:"Europe/Zurich",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).format(new Date(value.horizon_end)).replace(" ","T");expect(local).toBe(horizon);
    const original=await get(`/revenue/institutes/${institute}/capacity-opportunity?service_id=browser-capacity-care&horizon_end=${encodeURIComponent(value.horizon_end)}`);expect(original.unavailable_reason).toBe(value.unavailable_reason);
    const facts=panel.getByRole("region",{name:"Réponse du Copilot",exact:true});await expect(panel.getByRole("alert")).toHaveCount(0);
    if(available){
      expect(value.unavailable_reason).toBeNull();expect(value.opportunity.capacity_reserved).toBe(false);expect(value.opportunity.action_executed).toBe(false);expect(value.opportunity.estimated_value).toBeNull();expect(value.opportunity.confidence).toBe("conditional_current_queue_projection");
      const projection=value.opportunity.evidence;expect(projection.resource_needs).toEqual([{kind:"room",capability:"browser-capacity",quantity:1}]);expect(projection.duration_minutes).toBe(50);expect(new Date(projection.projected_end).getTime()-new Date(projection.projected_start).getTime()).toBe(50*60000);expect(new Date(projection.projected_start).getTime()).toBeGreaterThanOrEqual(new Date(value.captured_at).getTime());expect(new Date(projection.projected_end).getTime()).toBeLessThanOrEqual(new Date(value.horizon_end).getTime());
      for(const field of ["employee_id","duration_minutes","required_skills","resource_needs","prior_queue_count","unprojectable_prior_queue_count"])expect(projection[field]).toEqual(original.opportunity.evidence[field]);
      await expect(facts.getByRole("heading",{name:"Créneau à examiner",exact:true})).toBeVisible();await expect(facts).toContainText("Ce créneau n’est pas réservé");await expect(facts).toContainText("Vérifiez les horaires d’ouverture");
    }else{expect(value.opportunity).toBeNull();expect(value.unavailable_reason).toBe("capacity_unknown");await expect(facts).toContainText("Capacité non établie");await expect(facts).toContainText("Opportunité de capacité indisponible : capacité non établie");await expect(facts).not.toContainText("capacity_unknown");await expect(facts.getByRole("heading",{name:"Créneau à examiner",exact:true})).toHaveCount(0);}
    await expect(facts).toContainText("Aucun revenu estimé ni affectation effectuée");expect(await snapshot()).toEqual(sources);expect(await get(resourcesPath)).toEqual(resources);await page.screenshot({path:info.outputPath(`copilot-capacity-${label}.png`),fullPage:true});
  }
  async function room(status:string){const r=await request.patch(api+resourcesPath+"/browser-capacity-room",{headers,data:{status}});expect(r.status(),await r.text()).toBe(200);}
  try{await consult(true,"available");await room("maintenance");await consult(false,"maintenance");}finally{await room("active");}
  await consult(true,"restored");expect(await snapshot()).toEqual(before);expect(await get(resourcesPath)).toEqual(resourceBefore);expect(writes).toEqual(Array(3).fill(api+"/copilot/query"));
});
