import {expect as baseExpect,test} from "@playwright/test";
import {spawnSync} from "node:child_process";
const expect=baseExpect.configure({timeout:15000});test.setTimeout(180000);
test("native due rebooking review preserves original rules, permission uncertainty and existing-return suppression",async({page},info)=>{
  function setup(mode:string){const python=process.platform==="win32"?"../.venv/Scripts/python.exe":"../.venv/bin/python";
    const r=spawnSync(python,["browser-tests/rebooking_fixture.py",info.project.name,mode],{encoding:"utf8",env:process.env});expect(r.status,r.stderr+r.stdout).toBe(0);return JSON.parse(r.stdout.trim().split(/\r?\n/).at(-1)!);}
  const fixture=setup("seed");await page.goto("/");await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
  await page.getByRole("button",{name:"Se connecter",exact:true}).click();await expect(page.locator(".flow-session-exit")).toBeVisible();
  let reads=0,corrupt=false,result:any;const methods:string[]=[];
  await page.route("**/rebooking?**",async route=>{reads++;methods.push(route.request().method());const response=await route.fetch();result=await response.json();if(corrupt)result.delivery_authorized=true;await route.fulfill({response,json:result});});
  await page.getByRole("button",{name:"Pilotage",exact:true}).click();const panel=page.getByRole("region",{name:"Retours clients à examiner",exact:true});const read=panel.getByRole("button",{name:"Lire les retours à examiner",exact:true});
  // Desktop retains an additional active return; its candidate stays excluded
  // when the tablet profile adds another25 due candidates to the shared fixture.
  await expect(panel).toBeVisible();expect(reads).toBe(0);await read.click();await expect(panel).toContainText(info.project.name==="desktop"?"1–20 sur 25":"1–20 sur 49");
  const total=result.page.total,booked=result.already_booked_customers;expect(result.scheduled_customers).toBeGreaterThanOrEqual(1);expect(result.no_candidate_customers).toBeGreaterThanOrEqual(1);
  await expect(panel.getByRole("heading",{name:`Retour à examiner · Cliente ${fixture.booked}`,exact:true})).toHaveCount(0);
  await panel.getByRole("button",{name:"Retours suivants",exact:true}).click();await expect(panel).toContainText("21–");await panel.getByRole("button",{name:"Retours précédents",exact:true}).click();await expect(panel).toContainText("1–20");
  async function findOwn(id:string){await expect(read).toBeEnabled();await expect(panel.getByRole("status")).toHaveCount(0);const card=panel.locator("article").filter({has:page.getByRole("heading",{name:`Retour à examiner · Cliente ${id}`,exact:true})});
    while(!await card.count()){await panel.getByRole("button",{name:"Retours suivants",exact:true}).click();await expect(read).toBeEnabled();await expect(panel.getByRole("status")).toHaveCount(0);}return card;}
  const card=await findOwn(fixture.customer);await card.getByText("Voir le soin et la règle de retour",{exact:true}).click();await card.getByText("Voir les déclarations de contact",{exact:true}).click();
  await expect(card).toContainText("fixture-rule-manager");await expect(card).toContainText("fixture-permission-manager");await expect(card).toContainText("172800000000 microsecondes");
  await expect(card).toContainText("permission déclarée accordée");await expect(card).toContainText("permission déclarée refusée");await expect(card).toContainText("permission inconnue");await expect(card).toContainText("ne constituent pas une autorisation d’envoi");
  expect((await panel.boundingBox())!.width).toBeGreaterThanOrEqual(600);for(const c of await panel.locator("button,summary").all())expect((await c.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await card.screenshot({path:info.outputPath("native-rebooking-originals.png")});const unknown=await findOwn(fixture.unknown);await unknown.getByText("Voir les déclarations de contact",{exact:true}).click();await expect(unknown).toContainText("Aucune déclaration de contact conservée");
  await unknown.screenshot({path:info.outputPath("native-rebooking-unknown.png")});
  corrupt=true;await read.click();await expect(panel.getByRole("alert")).toBeVisible();await expect(panel.locator("article")).toHaveCount(0);corrupt=false;await read.click();await expect(panel.locator("article").first()).toBeVisible();
  setup("disabled");await read.click();await expect(panel).toContainText("0 sur 0");await expect(panel.locator("article")).toHaveCount(0);expect(result.disabled_customers).toBeGreaterThanOrEqual(27);
  setup("future");await read.click();await expect(panel).toContainText("0 sur 0");expect(result.scheduled_customers).toBeGreaterThanOrEqual(27);
  setup("restore");await read.click();await expect(panel.locator("article").first()).toBeVisible();expect(result.page.total).toBe(total);expect(setup("counts").counts).toEqual(fixture.counts);
  const afterBook=setup("book");await read.click();await expect(read).toBeEnabled();await expect(panel.getByRole("status")).toHaveCount(0);expect(result.page.total).toBe(total-1);expect(result.already_booked_customers).toBe(booked+1);
  while(true){await expect(panel.getByRole("heading",{name:`Retour à examiner · Cliente ${fixture.customer}`,exact:true})).toHaveCount(0);const next=panel.getByRole("button",{name:"Retours suivants",exact:true});if(await next.isDisabled())break;await next.click();await expect(read).toBeEnabled();await expect(panel.getByRole("status")).toHaveCount(0);}
  expect(setup("counts").counts).toEqual(afterBook.counts);expect(methods.every(m=>m==="GET")).toBe(true);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
