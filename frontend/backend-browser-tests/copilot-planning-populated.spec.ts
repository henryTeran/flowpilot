import {expect,test} from "@playwright/test";
import {formatWorkDuration} from "../src/work-hours-utils";

test("BASE capacity and conflict consultations preserve exact recorded activity and half-open overlaps",async({page,request},info)=>{
  test.setTimeout(120000);
  test.skip(process.env.FLOWPILOT_BROWSER_PLANNING_FIXTURE!=="1","Explicit owned planning fixture required");
  const api="http://127.0.0.1:4198/api/v1",institute="demo-institute-geneve",snapshotUrl="http://127.0.0.1:4198/_fixture/planning";
  const seedReply=await request.get(snapshotUrl);expect(seedReply.status()).toBe(200);const before=await seedReply.json(),fixture=before.manifest;
  const auth=await request.post(`${api}/auth/login`,{data:{email:"manager@browser.example.com",password:"Browser-test-only-2026"}});expect(auth.status()).toBe(200);const headers={Authorization:`Bearer ${(await auth.json()).access_token}`};
  async function get(path:string){const r=await request.get(api+path,{headers});expect(r.status(),await r.text()).toBe(200);return r.json();}
  const employees=await get(`/employees?institute_id=${institute}&offset=0&limit=50`);expect(employees.length).toBeLessThan(20);
  for(const employee of employees){
    const r=await request.post(`${api}/workforce/institutes/${institute}/work-intervals`,{headers,data:{employee_id:employee.id,start_time:"2025-10-26T00:00:00Z",end_time:"2025-10-26T02:00:00Z",reason:"Explicit owned historical work interval",idempotency_key:`copilot-work-shared-${employee.id}`}});expect(r.status(),await r.text()).toBe(200);
  }
  const capacityPath=`/revenue/institutes/${institute}/capacity?day=${fixture.activity_day}&limit=20`,original=await get(capacityPath);
  const declared=String(BigInt(employees.length)*7200000000n),unoccupied=String(BigInt(declared)-2700000000n);
  expect(original.known_declared_union_duration_us).toBe(declared);expect(original.known_covered_busy_duration_us).toBe("2700000000");expect(original.known_outside_declared_work_duration_us).toBe("900000000");expect(original.recorded_unoccupied_duration_us).toBe(unoccupied);
  await page.goto("/");await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");await page.getByRole("button",{name:"Se connecter",exact:true}).click();await expect(page.locator(".flow-session-exit")).toBeVisible();await page.getByRole("button",{name:"Copilot",exact:true}).click();
  const panel=page.getByRole("region",{name:"Copilot",exact:true}),writes:string[]=[];page.on("request",r=>{if(!["GET","HEAD","OPTIONS"].includes(r.method()))writes.push(r.url());});
  async function consult(){const pending=page.waitForResponse(r=>r.url().endsWith("/copilot/query")&&r.request().method()==="POST");await panel.getByRole("button",{name:"Consulter",exact:true}).click();const response=await pending;expect(response.status()).toBe(200);const value=(await response.json()).evidence.result;await expect(panel.getByRole("alert")).toHaveCount(0);return value;}
  await panel.getByRole("combobox",{name:"Consultation",exact:true}).selectOption("EMPLOYEE_CAPACITY");await panel.getByLabel("Journée terminée").fill(fixture.activity_day);await panel.getByRole("textbox",{name:"Votre question",exact:true}).fill("Mesurer la capacite enregistree des collaboratrices");
  const capacity=await consult();expect(capacity.day).toBe(fixture.activity_day);expect(capacity.window.start).toBe("2025-10-25T22:00:00Z");expect(capacity.window.end).toBe("2025-10-26T23:00:00Z");expect(capacity.known_declared_union_duration_us).toBe(declared);expect(capacity.known_covered_busy_duration_us).toBe("2700000000");expect(capacity.known_outside_declared_work_duration_us).toBe("900000000");expect(capacity.recorded_unoccupied_duration_us).toBe(unoccupied);expect(capacity.complete_activity).toBe(false);expect(capacity.complete_attendance).toBe(false);expect(capacity.bookable_capacity).toBeNull();
  const angela=capacity.rows.find((row:any)=>row.employee_id===fixture.employee_id);expect(angela.evidence.diagnostics.retained).toBe(3);expect(angela.evidence.known_busy_duration_us).toBe("3600000000");expect(angela.recorded_unoccupied_duration_us).toBe("4500000000");
  const facts=panel.getByRole("region",{name:"Réponse du Copilot",exact:true});await expect(facts).toContainText(formatWorkDuration("2700000000"));await expect(facts).toContainText(formatWorkDuration(unoccupied));await expect(facts).toContainText("capacité réservable ne sont pas établies");await page.screenshot({path:info.outputPath("copilot-capacity-populated.png"),fullPage:true});
  await panel.getByRole("combobox",{name:"Consultation",exact:true}).selectOption("PLANNING_CONFLICTS");await panel.getByLabel("Journée à examiner").fill(fixture.conflict_day);await panel.getByRole("textbox",{name:"Votre question",exact:true}).fill("Examiner les conflits du planning");
  for(const kind of ["employee","resource"]){
    if(kind==="resource")await panel.getByRole("button",{name:"Lire les ressources",exact:true}).click();
    await panel.getByRole("combobox",{name:"Collaboratrice ou ressource",exact:true}).selectOption(`${kind}:${fixture[kind+"_id"]}`);
    const value=await consult();expect(value[kind+"_id"]).toBe(fixture[kind+"_id"]);expect(value.source_count).toBe(3);expect(value.overlap_count).toBe(1);expect(value.invalid_source_count).toBe(0);expect(value.physical_activity_proven).toBe(false);expect(value.overlaps).toHaveLength(1);expect(value.overlaps[0]).toMatchObject({start_at:"2027-11-14T09:30:00Z",end_at:"2027-11-14T10:00:00Z",duration_us:"1800000000"});
    expect([value.overlaps[0].left.id,value.overlaps[0].right.id].sort()).toEqual(kind==="employee"?["browser-conflict-0","browser-conflict-1"]:["browser-reservation-0","browser-reservation-1"]);
    await expect(facts).toContainText("1 conflit(s) observé(s)");await expect(facts).toContainText(formatWorkDuration("1800000000"));await expect(facts).toContainText("activité physique ne sont pas établies");await page.screenshot({path:info.outputPath(`copilot-${kind}-overlap.png`),fullPage:true});
  }
  expect(writes).toEqual(Array(3).fill(api+"/copilot/query"));const after=await request.get(snapshotUrl);expect(after.status()).toBe(200);expect(await after.json()).toEqual(before);
  const final=await get(capacityPath);expect(final.rows.map((r:any)=>({id:r.employee_id,hours:r.evidence.work_hours.recorded_duration_us,busy:r.evidence.known_busy_duration_us}))).toEqual(original.rows.map((r:any)=>({id:r.employee_id,hours:r.evidence.work_hours.recorded_duration_us,busy:r.evidence.known_busy_duration_us})));
});
