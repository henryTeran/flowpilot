import { API_BASE_URL } from "../api/client";
import type { Institute } from "../types";

interface TopBarProps {
  institutes: Institute[];
  selectedInstituteId: string;
  realtimeStatus: "connected" | "connecting" | "disconnected";
  onInstituteChange: (id: string) => void;
  onRefresh: () => void;
}

export function TopBar({
  institutes,
  selectedInstituteId,
  realtimeStatus,
  onInstituteChange,
  onRefresh,
}: TopBarProps) {
  const statusLabel = {
    connected: "Temps réel connecté",
    connecting: "Connexion temps réel...",
    disconnected: "Temps réel déconnecté",
  }[realtimeStatus];

  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">BodyMinute Flow Manager</p>
        <h1>Planning temps réel</h1>
      </div>

      <div className="topbar-actions">
        <select value={selectedInstituteId} onChange={(event) => onInstituteChange(event.target.value)}>
          {institutes.map((institute) => (
            <option key={institute.id} value={institute.id}>
              {institute.name} · {institute.city}
            </option>
          ))}
        </select>

        <button className="secondary-button" onClick={onRefresh}>Rafraîchir</button>

        <div className={`live-pill ${realtimeStatus}`} title={API_BASE_URL}>
          <span /> {statusLabel}
        </div>
      </div>
    </header>
  );
}
