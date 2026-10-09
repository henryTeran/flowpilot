import {test,expect} from "@playwright/test";
test("audio import with disabled transcription remains retryable and performs no domain action",async({page},info)=>{
 await page.goto("/");await page.getByLabel("Adresse e-mail").fill("manager@browser.example.com");await page.getByLabel("Mot de passe").fill("Browser-test-only-2026");await page.getByRole("button",{name:"Se connecter",exact:true}).click();await expect(page.locator(".flow-session-exit")).toBeVisible();
 await page.getByRole("button",{name:"Copilot",exact:true}).click();await page.getByRole("button",{name:"Demande vocale",exact:true}).click();const panel=page.getByRole("region",{name:"Copilot vocal",exact:true});
 const posts:string[]=[];page.on("request",r=>{if(r.method()==="POST")posts.push(r.url());});
 await expect(panel.getByRole("button",{name:"Transcrire l’audio",exact:true})).toBeDisabled();await panel.getByLabel("Fichier audio").setInputFiles({name:"voice.wav",mimeType:"audio/wav",buffer:Buffer.from("fixture audio")});
 const waiting=page.waitForResponse(r=>r.url().includes("/copilot/voice/preview"));await panel.getByRole("button",{name:"Transcrire l’audio",exact:true}).click();expect((await waiting).status()).toBe(503);await expect(panel.getByRole("alert")).toContainText("Transcription indisponible");await expect(panel.getByRole("button",{name:"Transcrire l’audio",exact:true})).toBeEnabled();await expect(panel.getByRole("article",{name:"Transcription relue",exact:true})).toHaveCount(0);expect(posts).toHaveLength(1);expect(posts[0]).toContain("/copilot/voice/preview?language=fr");
 await page.screenshot({path:info.outputPath("voice-disabled.png"),fullPage:true});
});
