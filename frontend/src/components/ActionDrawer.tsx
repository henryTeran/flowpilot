import type { ReactNode } from "react";

interface ActionDrawerProps {
  open: boolean;
  title: string;
  subtitle?: string;
  children: ReactNode;
  onClose: () => void;
}

export function ActionDrawer({ open, title, subtitle, children, onClose }: ActionDrawerProps) {
  if (!open) return null;

  return (
    <div className="action-drawer-layer" role="dialog" aria-modal="true">
      <button className="action-drawer-backdrop" type="button" aria-label="Fermer" onClick={onClose} />
      <aside className="action-drawer">
        <header className="action-drawer-header">
          <div>
            <p className="eyebrow">Action</p>
            <h2>{title}</h2>
            {subtitle && <span>{subtitle}</span>}
          </div>
          <button type="button" className="drawer-close-button" onClick={onClose}>
            Fermer
          </button>
        </header>
        <div className="action-drawer-body">{children}</div>
      </aside>
    </div>
  );
}
