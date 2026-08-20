import { GitCompareArrows, PanelLeftClose, Wand2 } from "lucide-react";

import { ESCALAS, GRUPOS_MODOS } from "../escalas";
import type { Modo, Pesos, Prov } from "../types";
import Buscador from "./Buscador";
import PanelPesos from "./PanelPesos";
import Seccion from "./Seccion";

function ItemCapa({ modo, activo, onClick }: { modo: Modo; activo: boolean; onClick: () => void }) {
  const Icono = ESCALAS[modo].icono;
  return (
    <button className={`sidebar-item${activo ? " activo" : ""}`} onClick={onClick}>
      <Icono size={16} strokeWidth={1.75} className="sidebar-icono" />
      {ESCALAS[modo].etiqueta}
    </button>
  );
}

export default function Sidebar({
  provincias,
  prov,
  onProv,
  modo,
  onModo,
  anios,
  anioSel,
  onAnio,
  pesos,
  onPesos,
  onSelectMunicipio,
  onColapsar,
  onRecomendador,
  onComparar,
  vista,
  nMunicipios,
  error,
}: {
  provincias: Prov[];
  prov: string;
  onProv: (p: string) => void;
  modo: Modo;
  onModo: (m: Modo) => void;
  anios: number[];
  anioSel: number | null;
  onAnio: (a: number) => void;
  pesos: Pesos;
  onPesos: (p: Pesos) => void;
  onSelectMunicipio: (cod: string) => void;
  onColapsar: () => void;
  onRecomendador: () => void;
  onComparar: () => void;
  vista: "mapa" | "resumen";
  nMunicipios: number | null;
  error: string | null;
}) {
  const esc = ESCALAS[modo];
  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div className="sidebar-logo">TE</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="sidebar-marca">Sovereign Analytics</div>
            <div className="sidebar-sub">Territorio Engine</div>
          </div>
          <button className="btn-ghost" onClick={onColapsar} title="Ocultar panel">
            <PanelLeftClose size={16} strokeWidth={1.75} />
          </button>
        </div>

        <Buscador onSelect={onSelectMunicipio} />

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <button className="btn-primary" onClick={onRecomendador} style={{ width: "100%" }}>
            <Wand2 size={14} strokeWidth={2} />
            ¿Dónde debería vivir yo?
          </button>
          <button
            onClick={onComparar}
            style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6, width: "100%", padding: "8px 0", border: "1px solid var(--border)", borderRadius: "var(--radius)", background: "var(--panel)", color: "var(--text)", fontWeight: 500, fontSize: 13, cursor: "pointer" }}
          >
            <GitCompareArrows size={14} strokeWidth={1.75} />
            Comparar municipios
          </button>
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <select className="input" value={prov} onChange={(e) => onProv(e.target.value)}>
            {provincias.map((p) => (
              <option key={p.cod} value={p.cod}>{p.nombre}</option>
            ))}
          </select>
          {esc.anios && vista === "mapa" && (
            <select className="input" style={{ width: 92, flexShrink: 0 }} value={anioSel ?? ""} onChange={(e) => onAnio(Number(e.target.value))}>
              {anios.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          )}
        </div>
      </div>

      <div className="sidebar-body">
        <nav>
          {GRUPOS_MODOS.map((g) => (
            <div key={g.titulo}>
              <div className="grupo-titulo">{g.titulo}</div>
              {g.modos.map((m) => (
                <ItemCapa key={m} modo={m} activo={modo === m} onClick={() => onModo(m)} />
              ))}
              {g.secundarios && g.secundarios.length > 0 && (
                <Seccion
                  titulo="Más capas"
                  resumen={g.secundarios.includes(modo) ? ESCALAS[modo].etiqueta : `${g.secundarios.length}`}
                  abierta={g.secundarios.includes(modo)}
                >
                  <div style={{ display: "flex", flexDirection: "column", paddingTop: 2 }}>
                    {g.secundarios.map((m) => (
                      <ItemCapa key={m} modo={m} activo={modo === m} onClick={() => onModo(m)} />
                    ))}
                  </div>
                </Seccion>
              )}
            </div>
          ))}
        </nav>

        {modo === "indice" && <PanelPesos pesos={pesos} onChange={onPesos} />}

        {error && <div style={{ color: "#b91c1c", fontSize: 12 }}>{error}</div>}
      </div>

      <div className="sidebar-pie">
        {nMunicipios != null && <div>{nMunicipios.toLocaleString("es")} municipios en el mapa</div>}
        <div>INE · SEPE · AEAT · SERPAVI · AEMET · IGN · OSM · EEA · SETELECO</div>
      </div>
    </aside>
  );
}
