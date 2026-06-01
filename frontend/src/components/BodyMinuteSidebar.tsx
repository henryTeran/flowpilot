const menuItems = [
  { label: "Accueil", badge: "Planning" },
  { label: "Tickets", badge: "" },
  { label: "Abonnement", badge: "" },
  { label: "Paramètres", badge: "" },
  { label: "Promos Institut", badge: "" },
  { label: "Chiffres", badge: "" },
  { label: "FAQ", badge: "" },
  { label: "Tuto / Challenge", badge: "" },
  { label: "Rechercher", badge: "" },
];

interface BodyMinuteSidebarProps {
  activeItem?: string;
  onOpenTickets: () => void;
  onOpenDashboard: () => void;
}

export function BodyMinuteSidebar({
  activeItem = "Accueil",
  onOpenTickets,
  onOpenDashboard,
}: BodyMinuteSidebarProps) {
  function handleClick(label: string) {
    if (label === "Tickets") onOpenTickets();
    if (label === "Chiffres") onOpenDashboard();
  }

  return (
    <aside className="bm-sidebar">
      <div className="bm-brand-panel">
        <div className="bm-logo-mark">BM</div>
        <div>
          <strong>BodyMinute</strong>
          <span>Workflow Manager</span>
        </div>
      </div>

      <nav className="bm-nav" aria-label="Navigation principale">
        {menuItems.map((item) => (
          <button
            key={item.label}
            type="button"
            className={`bm-nav-item ${activeItem === item.label ? "active" : ""}`}
            onClick={() => handleClick(item.label)}
          >
            <span>{item.label}</span>
            {item.badge && <small>{item.badge}</small>}
          </button>
        ))}
      </nav>

      <button type="button" className="bm-logout-button">
        Déconnexion
      </button>
    </aside>
  );
}
