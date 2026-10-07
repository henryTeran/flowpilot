import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { verifyConversionSources } from "../api/marketing-conversion-proof";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validCurrentConversionPage, sameConversionOriginal, type ConversionOriginal, type ConversionWindow } from "../marketing-conversion-utils";
import { type DispatchPage } from "../marketing-dispatch-utils";
import { MarketingConversionHistory } from "./MarketingConversionHistory";
import { MarketingConversionWriter } from "./MarketingConversionWriter";
export function MarketingCurrentConversions({ institute, campaign, period }: { institute: string; campaign: string; period: ConversionWindow }) {
  if (getOperatorRole() !== "responsable_institut") return null;
  return <Reader key={JSON.stringify([institute, campaign, period.start, period.end, getAccessToken()])} institute={institute} campaign={campaign} period={period} />;
}
function Reader({ institute, campaign, period }: { institute: string; campaign: string; period: ConversionWindow }) {
  const token = getAccessToken(), sequence = useRef(0);
  const [page, setPage] = useState<DispatchPage<ConversionOriginal>>(), [selected, select] = useState<ConversionOriginal>();
  const [offset, setOffset] = useState(0), [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const [historyVersion, refreshHistory] = useState(0);
  useEffect(() => () => { sequence.current++; }, []);
  async function read(target = offset) {
    const n = ++sequence.current, current = () => n === sequence.current && token === getAccessToken() && getOperatorRole() === "responsable_institut";
    setPage(undefined); select(undefined); setOffset(target); setBusy(true); setError(undefined);
    try {
      const params = new URLSearchParams({ ...period, offset: String(target), limit: "20" });
      const p = await apiGet<DispatchPage<ConversionOriginal>>(`/marketing/institutes/${encodeURIComponent(institute)}/campaigns/${encodeURIComponent(campaign)}/conversions/current?${params}`);
      if (!await validCurrentConversionPage(p, institute, campaign, period, target, 20)) throw new Error();
      if (!current()) return;
      await Promise.all(p.items.map(async o => {
        await verifyConversionSources(o, institute, o.request.ticket_id);
        const head = await apiGet<ConversionOriginal | null>(`/marketing/institutes/${encodeURIComponent(institute)}/conversions/tickets/${encodeURIComponent(o.request.ticket_id)}/current`);
        if (!await sameConversionOriginal(o, head, institute)) throw new Error();
      }));
      if (current()) setPage(p);
    } catch { if (current()) setError("Liens courants à vérifier. Relancez la lecture."); }
    finally { if (current()) setBusy(false); }
  }
  return <section aria-label="Liens de conversion courants" style={{ overflowWrap: "anywhere" }}>
    <h4>Tickets liés à cette campagne</h4><button disabled={busy} onClick={() => void read()}>Voir les liens courants</button>
    {busy && <p role="status">Lecture des liens…</p>}{error && <p role="alert">{error}</p>}
    {page && <>
      <p>{page.items.length ? `${page.offset + 1}–${page.offset + page.items.length}` : "0"} sur {page.total} liens courants dans la période</p>
      {page.items.map(o => <button key={o.id} aria-pressed={selected?.id === o.id} onClick={() => {
        if (token === getAccessToken() && getOperatorRole() === "responsable_institut") select(o);
      }}>Ticket {o.request.ticket_id} · {o.attribution.intent.submission.account.mode === "test" ? "Test" : "Réel"}</button>)}
      <button disabled={busy || offset === 0} onClick={() => void read(Math.max(0, offset - 20))}>Liens précédents</button>
      <button disabled={busy || offset + page.items.length >= page.total} onClick={() => void read(offset + 20)}>Liens suivants</button>
    </>}
    {selected && <>
      <MarketingConversionWriter institute={institute} intent={selected.attribution.intent} accepted={selected.attribution.accepted}
        ticket={selected.request.ticket_id} period={selected.attribution.window} onChanged={() => { sequence.current++; setPage(undefined); setBusy(false); refreshHistory(v => v + 1); }} />
      <MarketingConversionHistory key={JSON.stringify([selected.request.ticket_id, historyVersion])} institute={institute} ticket={selected.request.ticket_id} />
    </>}
  </section>;
}
