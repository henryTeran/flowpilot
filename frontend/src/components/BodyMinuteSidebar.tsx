import type { ReactNode } from "react";

type MenuItem = {
  label: string;
  icon: ReactNode;
};

const menuItems: MenuItem[] = [
  { label: "Accueil", icon: <HomeIcon /> },
  { label: "Tickets", icon: <TicketIcon /> },
  { label: "Abonnement", icon: <CardIcon /> },
  { label: "Paramètres", icon: <SettingsIcon /> },
  { label: "Promos Institut", icon: <TagIcon /> },
  { label: "Chiffres", icon: <GridIcon /> },
  { label: "FAQ", icon: <HelpIcon /> },
  { label: "Tuto/Challenge", icon: <ScreenIcon /> },
  { label: "Rechercher", icon: <SearchIcon /> },
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
    <aside className="bm-sidebar" aria-label="Navigation BodyMinute">
      <div className="bm-brand-panel" aria-label="BodyMinute">
        <div className="bm-real-logo">
          <span>body</span>
          <span>minute</span>
        </div>
      </div>

      <nav className="bm-nav" aria-label="Navigation principale">
        {menuItems.map((item) => (
          <button
            key={item.label}
            type="button"
            className={`bm-nav-item ${activeItem === item.label ? "active" : ""}`}
            onClick={() => handleClick(item.label)}
            aria-label={item.label}
          >
            <span className="bm-nav-icon">{item.icon}</span>
            <span className="bm-nav-label">{item.label}</span>
          </button>
        ))}
      </nav>

      <button type="button" className="bm-logout-button" aria-label="Déconnexion">
        <PowerIcon />
      </button>
    </aside>
  );
}

function Svg({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {children}
    </svg>
  );
}

function HomeIcon() {
  return (
    <Svg>
      <path d="M4 11.5 12 5l8 6.5" />
      <path d="M6.5 10.5V20h11V10.5" />
      <path d="M10 20v-5h4v5" />
    </Svg>
  );
}

function TicketIcon() {
  return (
    <Svg>
      <path d="M5 7h14v3a2 2 0 0 0 0 4v3H5v-3a2 2 0 0 0 0-4V7Z" />
      <path d="M9 9.5h6" />
      <path d="M9 14.5h4" />
    </Svg>
  );
}

function CardIcon() {
  return (
    <Svg>
      <rect x="4" y="6" width="16" height="12" rx="1.5" />
      <path d="M4 10h16" />
      <path d="M8 14h4" />
    </Svg>
  );
}

function SettingsIcon() {
  return (
    <Svg>
      <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
      <path d="M19 12a7.7 7.7 0 0 0-.1-1l2-1.5-2-3.3-2.4 1a7.2 7.2 0 0 0-1.7-1L14.5 3h-5l-.3 3.2a7.2 7.2 0 0 0-1.7 1l-2.4-1-2 3.3 2 1.5a7.7 7.7 0 0 0 0 2l-2 1.5 2 3.3 2.4-1a7.2 7.2 0 0 0 1.7 1l.3 3.2h5l.3-3.2a7.2 7.2 0 0 0 1.7-1l2.4 1 2-3.3-2-1.5c.1-.3.1-.7.1-1Z" />
    </Svg>
  );
}

function TagIcon() {
  return (
    <Svg>
      <path d="M4 13.5 12.5 5H20v7.5L11.5 21 4 13.5Z" />
      <path d="M16.5 8.5h.01" />
    </Svg>
  );
}

function GridIcon() {
  return (
    <Svg>
      <rect x="4" y="4" width="6" height="6" rx="1" />
      <rect x="14" y="4" width="6" height="6" rx="1" />
      <rect x="4" y="14" width="6" height="6" rx="1" />
      <rect x="14" y="14" width="6" height="6" rx="1" />
    </Svg>
  );
}

function HelpIcon() {
  return (
    <Svg>
      <circle cx="12" cy="12" r="8" />
      <path d="M9.8 9.5A2.4 2.4 0 0 1 12 8c1.5 0 2.6.9 2.6 2.2 0 1.7-1.7 2.1-2.3 3.2" />
      <path d="M12 17h.01" />
    </Svg>
  );
}

function ScreenIcon() {
  return (
    <Svg>
      <rect x="5" y="5" width="14" height="11" rx="1.5" />
      <path d="M9 20h6" />
      <path d="M12 16v4" />
    </Svg>
  );
}

function SearchIcon() {
  return (
    <Svg>
      <circle cx="11" cy="11" r="5.5" />
      <path d="m15.2 15.2 4 4" />
    </Svg>
  );
}

function PowerIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M12 4v8" />
      <path d="M7.2 7.8a7 7 0 1 0 9.6 0" />
    </svg>
  );
}
