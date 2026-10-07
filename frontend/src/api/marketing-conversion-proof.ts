import { apiGet } from "./client";
import { sameCampaignOriginal, type CampaignOriginal } from "../marketing-campaign-utils";
import { sameDispatchIntent, validDispatchOutcome, sameDispatchTerms } from "../marketing-dispatch-utils";
import { validConversionOriginal, sameConversionOriginal, type ConversionOriginal } from "../marketing-conversion-utils";
export async function verifyConversionSources(o: ConversionOriginal, institute: string, ticket: string) {
  const base = `/marketing/institutes/${encodeURIComponent(institute)}`, conversions = base + "/conversions";
    if (!await validConversionOriginal(o, institute, ticket)) throw new Error();
    const a = o.attribution, outcomeBase = `${base}/dispatch-intents/${encodeURIComponent(a.intent.id)}/outcomes`;
    const [id, key, sourceId, sourceKey, sendId, sendKey, outcomeId, outcomeKey] = await Promise.all([
      apiGet(`${conversions}/${encodeURIComponent(o.id)}`), apiGet(`${conversions}/original/${encodeURIComponent(o.request.idempotency_key)}`),
      apiGet(`${base}/dispatch-intents/${encodeURIComponent(a.intent.id)}`), apiGet(`${base}/dispatch-intents/original/${encodeURIComponent(a.intent.request.idempotency_key)}`),
      apiGet<CampaignOriginal>(`${base}/campaigns/${encodeURIComponent(a.authorization.revision.id)}`),
      apiGet<CampaignOriginal>(`${base}/campaigns/original/${encodeURIComponent(a.authorization.request.idempotency_key)}`),
      apiGet(`${outcomeBase}/${encodeURIComponent(a.accepted.id)}`), apiGet(`${outcomeBase}/original/${encodeURIComponent(a.accepted.request.idempotency_key)}`),
    ]);
    if (!await sameConversionOriginal(o, id, institute) || !await sameConversionOriginal(o, key, institute)
      || !await sameDispatchIntent(a.intent, sourceId, institute) || !await sameDispatchIntent(a.intent, sourceKey, institute)
      || !await sameCampaignOriginal(a.authorization, sendId, institute) || !await sameCampaignOriginal(a.authorization, sendKey, institute)
      || !await validDispatchOutcome(outcomeId, a.intent, institute) || !await validDispatchOutcome(outcomeKey, a.intent, institute)
      || !sameDispatchTerms(a.accepted, outcomeId) || !sameDispatchTerms(a.accepted, outcomeKey)) throw new Error();
  }
