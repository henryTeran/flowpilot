import test from "node:test";
import assert from "node:assert/strict";
import {createHash,webcrypto} from "node:crypto";
import {validVoicePreview} from "../src/voice-utils";
Object.defineProperty(globalThis,"crypto",{value:webcrypto,configurable:true});
test("voice exact transcript routing rejects actor, scope and digest substitution",async()=>{
 const transcript="Consulter les stocks enregistres";const value={principal:{actor_id:"manager",institute_id:"own",role:"responsable_institut"},transcript,status:"review_required",effect:"transcript_intent_only_no_domain_action",route:{status:"routed",process_id:"stock",framework_version:"1.5.1",request_digest:createHash("sha256").update(transcript).digest("hex"),context_prepared:true}};
 assert.equal(await validVoicePreview(value,"own","manager"),true);
 assert.equal(await validVoicePreview(value,"other","manager"),false);
 assert.equal(await validVoicePreview(value,"own","peer"),false);
 assert.equal(await validVoicePreview({...value,transcript:transcript+"!"},"own","manager"),false);
 assert.equal(await validVoicePreview({...value,status:"silent"},"own","manager"),false);
 assert.equal(await validVoicePreview({...value,status:"silent",transcript:"",route:null},"own","manager"),true);
});
