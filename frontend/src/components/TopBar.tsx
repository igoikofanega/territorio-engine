import { BookOpen, Download, LayoutDashboard, Map as MapIcon, PanelLeftOpen } from "lucide-react";

import type { Vista } from "../types";

/** Barra superior: pestañas de vista, título de ámbito y acción de exportar. */
export default function TopBar({
  vista,
  onVista,
  ambito,
  sidebarAbierta,
  onAbrirSidebar,
  onExport,
}: {
  vista: Vista;
  onVista: (v: Vista) => void;
  ambito: string;
  sidebarAbierta: boolean;
  onAbrirSidebar: () => void;
  onExport: () => void;
}) {
  return (
    <header className="topbar">
      {!sidebarAbierta && (
        <button className="btn-ghost" onClick={onAbrirSidebar} title="Mostrar panel" style={{ color: "var(--text)" }}>
          <PanelLeftOpen size={18} strokeWidth={1.75} />
        </button>
      )}
      <button className={`topbar-tab${vista === "mapa" ? " activo" : ""}`} onClick={() => onVista("mapa")}>
        <MapIcon size={16} strokeWidth={1.75} /> Mapa
      </button>
      <button className={`topbar-tab${vista === "resumen" ? " activo" : ""}`} onClick={() => onVista("resumen")}>
        <LayoutDashboard size={16} strokeWidth={1.75} /> Resumen
      </button>
      <button
        className={`topbar-tab${vista === "metodologia" ? " activo" : ""}`}
        onClick={() => onVista("metodologia")}
      >
        <BookOpen size={16} strokeWidth={1.75} /> Metodología
      </button>

      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
        <span style={{ fontSize: 13, color: "var(--text-2)" }}>{ambito}</span>
        <button className="btn-primary" onClick={onExport} style={{ padding: "7px 12px" }}>
          <Download size={14} strokeWidth={2} /> Exportar
        </button>
      </div>
    </header>
  );
}
