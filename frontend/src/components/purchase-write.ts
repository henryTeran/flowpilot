import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, ApiError } from "../api/client";
import { getAccessToken, getOperatorSubject } from "../api/session";
import { validOrder, validReceipt, validPurchaseIntent, validPurchaseEntries, purchaseText, purchaseReference, matchesPurchase, purchaseTerms, orderSignature, type Order, type OrderEntry, type Receipt, type PurchaseIntent } from "../order-utils";
export type PurchaseSaved = { payload: PurchaseIntent; label: string; entries: OrderEntry[]; supplier_name?: string; supplier_reference?: string; order?: Order };
const namedTerms = (rows: OrderEntry[]) => JSON.stringify([...rows].sort((a, b) => a.item_id.localeCompare(b.item_id)));
export function usePurchaseWrite(institute: string, kind: "order" | "receipt", order: Order | undefined, ready: boolean, onRefresh: (original: Order | Receipt) => Promise<boolean>, onInvalidate: () => void, onRecorded?: (id: string) => void) {
  const token = getAccessToken(), actor = getOperatorSubject(), key = `flowpilot.purchase-request:${JSON.stringify([institute, actor, kind, order?.id || "create"])}`;
  function validSaved(value: unknown): value is PurchaseSaved {
    const row = value as PurchaseSaved;
    if (!row || !validPurchaseIntent(row.payload, kind) || !purchaseText(row.label, 240) || !validPurchaseEntries(row.entries) || !row.entries.every(entry => purchaseText(entry.item_name, 120) && purchaseReference(entry.item_sku)) || purchaseTerms(row.entries) !== purchaseTerms(row.payload.entries)) return false;
    return kind === "receipt" ? validOrder(row.order, institute) && row.order.id === order?.id && orderSignature(row.order) === orderSignature(order!) && row.entries.every(entry => { const original = order!.entries.find(item => item.item_id === entry.item_id); return original && original.unit === entry.unit && original.item_name === entry.item_name && original.item_sku === entry.item_sku; }) : purchaseText(row.supplier_name, 120) && purchaseReference(row.supplier_reference);
  }
  const [recovery, setRecovery] = useState<{ saved?: PurchaseSaved; problem?: string }>(() => { try { const raw = sessionStorage.getItem(key); if (raw === null) return {}; const value = JSON.parse(raw); return validSaved(value) ? { saved: value } : { problem: "Demande conservée illisible : aucune nouvelle demande ne peut la remplacer." }; } catch { return { problem: "Lecture de la demande conservée indisponible." }; } });
  const saved = recovery.saved, retain = (value: PurchaseSaved | undefined) => setRecovery({ saved: value });
  const [busy, setBusy] = useState(false), [error, setError] = useState<string>(), [success, setSuccess] = useState<string>(), [rejected, reject] = useState(false);
  const mounted = useRef(false), pending = useRef(false), callbacks = useRef({ onRefresh, onInvalidate, onRecorded }); callbacks.current = { onRefresh, onInvalidate, onRecorded };
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const current = () => mounted.current && token === getAccessToken();
  const base = `/inventory/institutes/${encodeURIComponent(institute)}`;
  async function run(value: PurchaseSaved) {
    if (!current() || !ready || recovery.problem || pending.current || !actor || !validSaved(value)) return false;
    pending.current = true; setBusy(true); setError(undefined); setSuccess(undefined); reject(false);
    let postReturned = false;
    try {
      sessionStorage.setItem(key, JSON.stringify(value)); retain(value);
      if (kind === "receipt") callbacks.current.onInvalidate();
      const path = kind === "order" ? `${base}/orders` : `${base}/orders/${encodeURIComponent(order!.id)}/receipts`;
      const reply = await apiPost<Order | Receipt>(path, value.payload); postReturned = true;
      if (!current()) return false;
      const validate = (row: unknown) => kind === "order" ? validOrder(row, institute) && matchesPurchase(row, value.payload, actor) && row.supplier_name === value.supplier_name && row.supplier_reference === value.supplier_reference && namedTerms(row.entries) === namedTerms(value.entries) : validReceipt(row, value.order!) && matchesPurchase(row, value.payload, actor);
      if (!validate(reply)) throw new Error("Résultat original à vérifier");
      const original = await apiGet<Order | Receipt>(kind === "order" ? `${base}/orders/${encodeURIComponent(reply.id)}` : `${base}/purchase-receipts/${encodeURIComponent(reply.id)}`);
      if (!current()) return false;
      if (!validate(original) || original.id !== reply.id || (kind === "order" ? orderSignature(original as Order) !== orderSignature(reply as Order) : JSON.stringify(original) !== JSON.stringify(reply))) throw new Error("Lecture originale à vérifier");
      if (!await callbacks.current.onRefresh(original) || !current()) throw new Error("Actualisez les lectures avant de poursuivre");
      sessionStorage.removeItem(key); retain(undefined); setSuccess(kind === "order" ? `Commande enregistrée : ${value.label}` : `Réception enregistrée : ${value.label}`);
      callbacks.current.onRecorded?.(original.id);
      return true;
    } catch (error) { if (current()) { setError(error instanceof Error ? error.message : "Demande indisponible"); reject(!postReturned && error instanceof ApiError && [400, 422].includes(error.status)); } return false; }
    finally { pending.current = false; if (current()) setBusy(false); }
  }
  function correct() { if (!current() || !rejected || busy) return; try { sessionStorage.removeItem(key); retain(undefined); reject(false); setError(undefined); } catch (error) { setError(String(error)); } }
  return { saved, busy, error: error || recovery.problem, blocked: !!recovery.problem, ready, success, rejected, run, correct };
}
