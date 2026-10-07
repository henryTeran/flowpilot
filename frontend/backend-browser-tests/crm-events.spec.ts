import {expect,test} from "@playwright/test";
test.use({timezoneId:"America/Los_Angeles"});
test("signed native events recover lost reconciliation and retain targeted cancellation and processing history",async({page,request},info)=>{
 await page.goto("/");await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");await page.getByRole("button",{name:"Se connecter",exact:true}).click();await expect(page.locator(".flow-session-exit")).toBeVisible();
 const token=await page.evaluate(()=>sessionStorage.getItem("flowpilot.access_token")),headers={Authorization:`Bearer ${token}`},base="http://127.0.0.1:4198/api/v1",institute="demo-institute-geneve",name=`Events ${info.project.name}`;
 const created=await request.post(`${base}/customers/institutes/${institute}`,{headers,data:{display_name:name,idempotency_key:`events-${info.project.name}`}});expect(created.status()).toBe(200);const customer=await created.json(),path=`${base}/crm/institutes/${institute}/customers/${customer.id}`;
 const policies=`${base}/crm/institutes/${institute}/automation-policies`,before=await request.get(policies+"/current",{headers});expect(before.status()).toBe(200);const previous=await before.json();
 const rules=["birthday","post_service","rebooking","inactivity","package_expiry","subscription_renewal"].map(trigger=>({trigger,enabled:true,offset_us:["rebooking","inactivity"].includes(trigger)?"1":"0"}));
 const configured=await request.post(policies,{headers,data:{policy:{institute_id:institute,rules},previous_policy_id:previous?.id || null,reason:"Explicit native event fixture rules",idempotency_key:`events-policy-${info.project.name}`}});expect(configured.status(),await configured.text()).toBe(200);
 for(let i=0;i<2;i++){
  const ticketReply=await request.post(`${base}/tickets`,{headers,data:{institute_id:institute,service_id:"svc-aisselles",customer_id:customer.id}});expect(ticketReply.status()).toBe(200);const ticket=await ticketReply.json();
  const started=await request.post(`${base}/planning/sessions/start`,{headers,data:{ticket_id:ticket.id,employee_id:"emp-angela",service_id:"svc-aisselles"}});expect(started.status()).toBe(200);const session=await started.json();
  const finished=await request.patch(`${base}/planning/sessions/${session.id}/finish`,{headers});expect(finished.status()).toBe(200);
 }
 async function select(){await page.getByRole("button",{name:"Clientes",exact:true}).click();const directory=page.getByRole("region",{name:"Clientes et CRM",exact:true});await directory.getByLabel("Nom ou téléphone").fill(name);await directory.getByRole("button",{name:"Rechercher",exact:true}).click();await directory.getByRole("button",{name,exact:true}).click();await page.getByText("Consulter les événements internes",{exact:true}).click();}
 await select();const panel=page.getByRole("region",{name:"Événements CRM",exact:true});await expect(panel).toContainText("0 événements internes");
 let posts=0,first:any;await page.route("**/event-captures",async route=>{if(route.request().method()!=="POST")return route.continue();posts++;if(posts===1){const actual=await route.fetch();expect(actual.status()).toBe(200);first=await actual.json();return route.abort("failed");}return route.continue();});
 async function submit(reason:string){await panel.getByLabel("Motif de l'action",{exact:true}).fill(reason);await panel.getByRole("button",{name:"Enregistrer l'action interne",exact:true}).click();}
 await panel.getByRole("button",{name:"Réconcilier les sources",exact:true}).click();await submit("Explicit native reconciliation");await expect(panel.getByRole("button",{name:"Reprendre l'action conservée",exact:true})).toBeEnabled();
 await page.reload();await expect(page.locator(".flow-session-exit")).toBeVisible();await select();await panel.getByRole("button",{name:"Reprendre l'action conservée",exact:true}).click();await expect(panel).toContainText("Capture originale vérifiée");expect(posts).toBe(1);await expect(panel.locator("article")).toHaveCount(4);
 expect(first.source.delivery_authorized).toBe(false);expect(first.revisions).toHaveLength(4);expect(first.revisions.every((r:any)=>r.decision.state==="due")).toBe(true);
 expect(await page.evaluate(()=>Object.keys(sessionStorage).some(k=>k.startsWith("flowpilot.crm-event-request:")))).toBe(false);
 const cancelled=first.revisions[0],processed=first.revisions[1];
 await panel.locator("article").filter({hasText:cancelled.id}).getByRole("button",{name:"Annuler cette occurrence",exact:true}).click();await submit("Explicit occurrence cancellation");await expect(panel).toContainText("Capture originale vérifiée");expect(posts).toBe(2);
 await panel.locator("article").filter({hasText:processed.event_key}).getByRole("button",{name:"Traiter cette occurrence",exact:true}).click();await submit("Explicit occurrence internal processing");await expect(panel).toContainText("Capture originale vérifiée");expect(posts).toBe(3);
 await panel.getByRole("button",{name:"Traiter les échéances internes (20 maximum)",exact:true}).click();await submit("Explicit remaining internal processing");await expect(panel).toContainText("Capture originale vérifiée");expect(posts).toBe(4);
 const current=await request.get(path+"/events?offset=0&limit=20",{headers});expect(current.status()).toBe(200);const body=await current.json();expect(body.total).toBe(4);expect(body.revisions.filter((r:any)=>r.decision.state==="processed")).toHaveLength(3);expect(body.revisions.find((r:any)=>r.event_key===cancelled.event_key).decision.reason).toBe("explicit_cancellation");
 const retained=await request.get(path+"/event-captures/"+first.id,{headers});expect(await retained.json()).toEqual(first);
 for(const article of await panel.locator("article").all()){if((await article.textContent())?.includes("Traité en interne"))await expect(article.getByRole("button",{name:"Annuler cette occurrence",exact:true})).toBeDisabled();}
 for(const control of await panel.locator("button,input").all())expect((await control.boundingBox())!.height).toBeGreaterThanOrEqual(44);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1)).toBe(false);await panel.screenshot({path:info.outputPath("native-event-results.png")});
 for(let i=0;i<19;i++){
  const ticketReply=await request.post(`${base}/tickets`,{headers,data:{institute_id:institute,service_id:"svc-aisselles",customer_id:customer.id}});expect(ticketReply.status()).toBe(200);const ticket=await ticketReply.json();
  const started=await request.post(`${base}/planning/sessions/start`,{headers,data:{ticket_id:ticket.id,employee_id:"emp-angela",service_id:"svc-aisselles"}});expect(started.status()).toBe(200);const session=await started.json();
  const finished=await request.patch(`${base}/planning/sessions/${session.id}/finish`,{headers});expect(finished.status()).toBe(200);
 }
 await panel.getByRole("button",{name:"Réconcilier les sources",exact:true}).click();await submit("Explicit expanded occurrence reconciliation");await expect(panel).toContainText("Capture originale vérifiée");expect(posts).toBe(5);await expect(panel).toContainText("25 événements internes");await expect(panel.locator("article")).toHaveCount(20);
 await panel.getByRole("button",{name:"Événements suivants",exact:true}).click();await expect(panel.locator("article")).toHaveCount(5);await expect(panel).toContainText("affichage 21 à 25");
 await page.route("**/events?**",async route=>{const actual=await route.fetch();const data=await actual.json();data.total++;await route.fulfill({response:actual,json:data});});
 await panel.getByRole("button",{name:"Actualiser les événements",exact:true}).click();await expect(panel).toContainText("Page des événements à vérifier");await expect(panel.locator("article")).toHaveCount(0);
 await page.unroute("**/events?**");await panel.getByRole("button",{name:"Actualiser les événements",exact:true}).click();await expect(panel.locator("article")).toHaveCount(5);
 await panel.getByRole("button",{name:"Événements précédents",exact:true}).click();await expect(panel.locator("article")).toHaveCount(20);

});
