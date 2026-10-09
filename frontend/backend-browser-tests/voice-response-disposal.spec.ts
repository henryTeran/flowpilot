import {test,expect} from "@playwright/test";

test("voice refuses altered transcript and discards a valid reply after navigation",async({page})=>{
 await page.goto("/");
 await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");
 await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");
 await page.getByRole("button",{name:"Se connecter",exact:true}).click();
 await expect(page.locator(".flow-session-exit")).toBeVisible();
 await page.getByRole("button",{name:"Copilot",exact:true}).click();
 const open=()=>page.getByRole("button",{name:"Demande vocale",exact:true}).click();
 await open();
 const panel=page.getByRole("region",{name:"Copilot vocal",exact:true});
 const submit=panel.getByRole("button",{name:/^Transcrire/});
 let mode:"damaged"|"native"|"late"="damaged",pending=false,delivered=false;
 let release:()=>void=()=>{};
 const posts:string[]=[];
 page.on("request",r=>{if(r.method()==="POST")posts.push(r.url());});
 await page.route("**/copilot/voice/preview?language=fr",async route=>{
   const response=await route.fetch();expect(response.status()).toBe(200);
   const body=await response.json();
   if(mode==="damaged")body.transcript="Texte substitue sans digest correspondant";
   if(mode==="late"){await new Promise<void>(resolve=>{release=resolve;pending=true;});}
   await route.fulfill({response,json:body});delivered=true;
 });
 await panel.getByLabel("Fichier audio").setInputFiles({name:"voice.wav",mimeType:"audio/wav",buffer:Buffer.from("fixture audio")});
 await submit.click();
 await expect(panel.getByRole("alert")).toContainText("Transcription indisponible");
 await expect(panel.getByRole("article",{name:"Transcription relue",exact:true})).toHaveCount(0);
 await expect(panel.getByRole("button",{name:/^Utiliser ce texte/})).toHaveCount(0);
 mode="native";await submit.click();
 await expect(panel.getByRole("article",{name:"Transcription relue",exact:true})).toContainText("Consulter les stocks enregistres");
 mode="late";delivered=false;await submit.click();
 await expect.poll(()=>pending).toBe(true);
 await page.getByRole("button",{name:"Consulter avec le Copilot",exact:true}).click();
 release();await expect.poll(()=>delivered).toBe(true);
 await open();
 await expect(panel.getByRole("article",{name:"Transcription relue",exact:true})).toHaveCount(0);
 await expect(submit).toBeDisabled();
 expect(posts).toHaveLength(3);
 expect(posts.every(url=>url.includes("/copilot/voice/preview?language=fr"))).toBe(true);
});
