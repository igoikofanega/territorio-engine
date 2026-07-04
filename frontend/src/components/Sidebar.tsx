import { GitCompareArrows, PanelLeftClose, Wand2 } from "lucide-react";

import { ESCALAS, GRUPOS_MODOS } from "../escalas";
import type { Modo, Pesos, Prov } from "../types";
import Buscador from "./Buscador";
import PanelPesos from "./PanelPesos";

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
  nMunicipios: number | null;
  error: string | null;
}) {
  const esc = ESCALAS[modo];
  return (
    <aside className="sidebar">
      <div style={{ display: "flex", alignItems: "flex-start" }}>
        <div>
          <div className="sidebar-marca">territorio-engine</div>
          <div className="sidebar-sub">¿Dónde vivir en España? Datos por municipio.</div>
        </div>
        <button className="btn-ghost" onClick={onColapsar} title="Ocultar panel" style={{ marginLeft: "auto" }}>
          <PanelLeftClose size={16} strokeWidth={1.75} />
        </button>
      </div>

      <Buscador onSelect={onSelectMunicipio} />

      <button
        onClick={onRecomendador}
        style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6, width: "100%", padding: "7px 0", border: 0, borderRadius: 6, background: "var(--accent)", color: "white", fontWeight: 600, fontSize: 12, cursor: "pointer" }}
      >
        <Wand2 size={14} strokeWidth={2} />
        ¿Dónde debería vivir yo?
      </button>

      <button
        onClick={onComparar}
        style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6, width: "100%", padding: "6px 0", border: "1px solid var(--border)", borderRadius: 6, background: "white", color: "var(--text)", fontWeight: 500, fontSize: 12, cursor: "pointer", marginTop: -6 }}
      >
        <GitCompareArrows size={14} strokeWidth={1.75} />
        Comparar municipios
      </button>

      <div style={{ display: "flex", gap: 8 }}>
        <select className="input" value={prov} onChange={(e) => onProv(e.target.value)}>
          {provincias.map((p) => (
            <option key={p.cod} value={p.cod}>{p.nombre}</option>
          ))}
        </select>
        {esc.anios && (
          <select className="input" style={{ width: 90, flexShrink: 0 }} value={anioSel ?? ""} onChange={(e) => onAnio(Number(e.target.value))}>
            {anios.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        )}
      </div>

      <nav>
        {GRUPOS_MODOS.map((g) => (
          <div key={g.titulo}>
            <div className="grupo-titulo">{g.titulo}</div>
            {g.modos.map((m) => {
              const Icono = ESCALAS[m].icono;
              return (
                <button key={m} className={`sidebar-item${modo === m ? " activo" : ""}`} onClick={() => onModo(m)}>
                  <Icono size={15} strokeWidth={1.75} className="sidebar-icono" />
                  {ESCALAS[m].etiqueta}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {modo === "indice" && <PanelPesos pesos={pesos} onChange={onPesos} />}

      {error && <div style={{ color: "#b91c1c", fontSize: 12 }}>{error}</div>}

      <div className="sidebar-pie">
        {nMunicipios != null && <div>{nMunicipios.toLocaleString("es")} municipios en el mapa</div>}
        <div>INE · SEPE · AEAT · SERPAVI · AEMET · IGN · OSM · Wikidata</div>
      </div>
    </aside>
  );
}
