import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken, getOperatorRole } from "../api/session";
import { validAudienceCatalog, validAudienceOriginal, sameAudienceOriginal, validRetainedAudiencePage,
  type AudienceCatalog, type AudienceOriginal, type RetainedAudiencePage } from "../marketing-audience-utils";
const permissions = { granted: "Accord retenu", refused: "Refus retenu", unknown: "Inconnue",
  unsupported_channel: "Canal non pris en charge", future_declaration: "Déclaration postérieure à la capture" };

export function MarketingAudienceCatalog({ institute }: { institute: string }) {
  if (!institute || getOperatorRole() !== "responsable_institut") return null;
  return <Catalog key={JSON.stringify([institute, getAccessToken()])} institute={institute} />;
}
function Catalog({ institute }: { institute: string }) {
  const token = getAccessToken(), sequence = useRef(0);
  const [page, setPage] = useState<AudienceCatalog>(), [selected, select] = useState<AudienceOriginal>();
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const base = `/marketing/institutes/${encodeURIComponent(institute)}/audience-captures`;
  useEffect(() => () => { sequence.current++; }, []);
  async function load(offset = 0) {
    const request = ++sequence.current, current = () => request === sequence.current && token === getAccessToken();
    setBusy(true); setError(undefined); setPage(undefined); select(undefined);
    try { const result = await apiGet<unknown>(`${base}?offset=${offset}&limit=20`);
      if (!validAudienceCatalog(result, institute, offset, 20)) throw new Error("Invalid catalog");
      if (current()) setPage(result);
    } catch { if (current()) setError("Catalogue des audiences à vérifier. Relancez la lecture."); }
    finally { if (current()) setBusy(false); }
  }
  return <section aria-label="Audiences retenues"><h3>Audiences retenues</h3>
    <button disabled={busy} onClick={() => void load(page?.offset || 0)}>Consulter les audiences retenues</button>
    {busy && <p role="status">Lecture des audiences…</p>}{error && <p role="alert">{error}</p>}
    {page && <><p>{page.items.length ? `${page.offset + 1}–${page.offset + page.items.length}` : "0"} sur {page.total} captures</p>
      <ul>{page.items.map(o => <li key={o.id} style={{ maxWidth: "100%" }}><button style={{ maxWidth: "100%", overflowWrap: "anywhere" }}
        aria-pressed={selected?.id === o.id} onClick={() => select(o)}>{o.request.reason} · {o.request.channel} · {o.summary.eligible_count} éligibles · {o.captured_at}</button></li>)}</ul>
      <button disabled={page.offset === 0} onClick={() => void load(Math.max(0, page.offset - 20))}>Captures précédentes</button>
      <button disabled={page.offset + page.items.length >= page.total} onClick={() => void load(page.offset + 20)}>Captures suivantes</button>
    </>}
    {selected && <Retained key={selected.id} institute={institute} selected={selected} />}
  </section>;
}
function Retained({ institute, selected }: { institute: string; selected: AudienceOriginal }) {
  const token = getAccessToken(), sequence = useRef(0), cursors = useRef(new Map<number, string | null>([[0, null]]));
  const [page, setPage] = useState<RetainedAudiencePage>(), [index, setIndex] = useState(0);
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>();
  const base = `/marketing/institutes/${encodeURIComponent(institute)}/audience-captures`;
  async function load(target = 0) {
    const request = ++sequence.current, current = () => request === sequence.current && token === getAccessToken();
    setBusy(true); setError(undefined); setPage(undefined); setIndex(target);
    try {
      const after = cursors.current.get(target); if (after === undefined) throw new Error("Unknown predecessor cursor");
      const [byId, byKey, retained] = await Promise.all([
        apiGet<unknown>(`${base}/${encodeURIComponent(selected.id)}`),
        apiGet<unknown>(`${base}/original/${encodeURIComponent(selected.request.idempotency_key)}`),
        apiGet<unknown>(`${base}/${encodeURIComponent(selected.id)}/pages/${target}`),
      ]);
      if (!current()) return;
      if (!validAudienceOriginal(byId, institute) || !validAudienceOriginal(byKey, institute)
        || !sameAudienceOriginal(selected, byId) || !sameAudienceOriginal(selected, byKey)
        || !validRetainedAudiencePage(retained, byId, target, after)) throw new Error("Invalid retained page");
      if (retained.observation.next_after !== null) cursors.current.set(target + 1, retained.observation.next_after);
      setPage(retained);
    } catch { if (current()) setError("Page retenue à vérifier. Relancez la lecture."); }
    finally { if (current()) setBusy(false); }
  }
  useEffect(() => { void load(); return () => { sequence.current++; }; }, []);
  return <section aria-label="Détail de l’audience retenue"><h4>Audience historique</h4>
    <p style={{ overflowWrap: "anywhere" }}>{selected.id} · {selected.request.channel} · {selected.request.reason}</p>
    <p>Source retenue : {selected.request.permission_basis === "marketing_contact" ? "Déclarations de contacts marketing" : "Déclarations CRM"}</p>
    <p>{selected.summary.customer_count} clientes observées · {selected.summary.selected_count} sélectionnées · {selected.summary.eligible_count} éligibles à la capture.</p>
    <button disabled={busy} onClick={() => void load(index)}>Actualiser la page retenue</button>
    {busy && <p role="status">Lecture de la page retenue…</p>}{error && <p role="alert">{error}</p>}
    {page && <><p>Page {index + 1} sur {selected.summary.page_count} · {page.observation.items.length} clientes</p>
      {page.observation.items.map(item => <article key={item.customer_id} style={{ overflowWrap: "anywhere" }}>
        <p>Cliente {item.customer_id} · {item.profile.segment?.state || "Segment indéterminé"}</p>
        <p>{item.selected_segment ? "Segment sélectionné" : "Hors sélection"} · permission marketing : {permissions[item.marketing_permission]}
          · {item.eligible_by_recorded_permission ? "Éligible selon la permission retenue" : "Non éligible"}</p>
      </article>)}
      <button disabled={busy || index === 0} onClick={() => void load(index - 1)}>Clientes précédentes</button>
      <button disabled={busy || page.observation.next_after === null} onClick={() => void load(index + 1)}>Clientes suivantes</button>
    </>}
    <p>Ces données sont retenues à la capture ; elles ne prouvent pas la permission actuelle ni une autorisation d’envoi.</p>
  </section>;
}
