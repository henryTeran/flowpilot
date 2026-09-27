const navItems = [
  { label: "Accueil / Planning", badge: "MVP", active: true },
  { label: "Tickets", badge: "Soon", active: false },
  { label: "Abonnements", badge: "V2", active: false },
  { label: "Prestations", badge: "MVP", active: false },
  { label: "Rendez-vous", badge: "V2", active: false },
  { label: "Chiffres", badge: "V2", active: false },
  { label: "Admin", badge: "V2", active: false },
];

export function Sidebar() {
  return (
    <aside className="sidebar-shell">
      <div className="brand-card">
        <div className="brand-mark">BM</div>
        <div>
          <strong>FlowPilot</strong>
          <span>Institut Manager</span>
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="Navigation principale">
        {navItems.map((item) => (
          <button key={item.label} className={`sidebar-link ${item.active ? "active" : ""}`} type="button">
            <span>{item.label}</span>
            <small>{item.badge}</small>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer-card">
        <span>Mode pilote</span>
        <strong>Shadow mode actif</strong>
        <p>Le MVP fonctionne sans remplacer la caisse existante.</p>
      </div>
    </aside>
  );
}
