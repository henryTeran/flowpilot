import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { getAccessToken } from "../api/session";
import { validStockItem, stockUnits, type StockItem } from "../inventory-utils";
const base = (institute: string) => `/inventory/institutes/${encodeURIComponent(institute)}`;
const message = (error: unknown) => error instanceof Error ? error.message : "Articles indisponibles";
export function StockItemPicker({ institute, disabled, selected, onAdd, action = "recette" }: { institute: string; disabled: boolean; selected: string[]; onAdd: (item: StockItem) => void; action?: "recette" | "consommation" }) {
  const token = getAccessToken(), [items, setItems] = useState<StockItem[]>(), [offset, setOffset] = useState(0), [reload, setReload] = useState(0), [choice, choose] = useState("");
  const [error, setError] = useState<string>();
  useEffect(() => { let active = true; setItems(undefined); setError(undefined); choose(""); void apiGet<StockItem[]>(`${base(institute)}/items?limit=50&offset=${offset}`).then(rows => {
    if (!Array.isArray(rows) || rows.length > 50 || !rows.every(row => validStockItem(row, institute)) || new Set(rows.map(row => row.id)).size !== rows.length) throw new Error("Articles disponibles à vérifier");
    if (active && token === getAccessToken()) setItems(rows);
  }).catch(error => { if (active && token === getAccessToken()) setError(message(error)); }); return () => { active = false; }; }, [offset, reload]);
  const item = items?.find(row => row.id === choice);
  return <div><button type="button" disabled={disabled} onClick={() => setReload(reload + 1)}>Actualiser les articles de {action}</button>{error && <p role="alert">{error}</p>}<label>Article à ajouter<select disabled={disabled || !items} value={choice} onChange={event => choose(event.target.value)}><option value="">Choisir un article</option>{items?.filter(item => !selected.includes(item.id)).map(item => <option key={item.id} value={item.id}>{item.name} · {item.sku} · {stockUnits[item.unit]}</option>)}</select></label>
    <button type="button" disabled={disabled || !item || selected.includes(item.id)} onClick={() => { if (item) { onAdd(item); choose(""); } }}>Ajouter à la {action}</button>
    <div className="bm-stock-pages"><button type="button" disabled={disabled || !items || !offset} onClick={() => setOffset(offset - 50)}>Articles précédents pour la {action}</button><button type="button" disabled={disabled || items?.length !== 50} onClick={() => setOffset(offset + 50)}>Articles suivants pour la {action}</button></div>
  </div>;
}
