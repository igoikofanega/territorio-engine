import { PESOS_DEFECTO } from "../escalas";
import { CLAVES_INDICE, type Pesos } from "../types";

const ETIQUETA: Record<(typeof CLAVES_INDICE)[number], string> = {
  renta: "Renta",
  paro: "Empleo",
  alquiler: "Asequibilidad",
  envejecimiento: "Vitalidad",
  servicios: "Servicios",
};

/** Sliders de pesos del índice; vive dentro de la sidebar cuando modo = índice. */
export default function PanelPesos({ pesos, onChange }: { pesos: Pesos; onChange: (p: Pesos) => void }) {
  const suma = CLAVES_INDICE.reduce((s, k) => s + pesos[k], 0);
  const norm: Pesos = { ...pesos };
  if (suma > 0) for (const k of CLAVES_INDICE) norm[k] = pesos[k] / suma;
  const dirty = CLAVES_INDICE.some((k) => Math.abs(pesos[k] - PESOS_DEFECTO[k]) > 0.001);
  return (
    <div>
      <div className="grupo-titulo" style={{ display: "flex", alignItems: "center" }}>
        Pesos del índice
        {dirty && (
          <button
            className="btn-ghost"
            onClick={() => onChange(PESOS_DEFECTO)}
            style={{ marginLeft: "auto", fontSize: 10, color: "var(--accent)", textTransform: "none", letterSpacing: 0 }}
          >
            restablecer
          </button>
        )}
      </div>
      {CLAVES_INDICE.map((k) => (
        <label key={k} style={{ display: "flex", alignItems: "center", gap: 8, margin: "4px 0", fontSize: 12 }}>
          <span style={{ width: 86, color: "var(--text-2)" }}>{ETIQUETA[k]}</span>
          <input
            type="range" min={0} max={1} step={0.05}
            value={pesos[k]}
            onChange={(e) => onChange({ ...pesos, [k]: Number(e.target.value) })}
            style={{ flex: 1, accentColor: "var(--accent)" }}
          />
          <span style={{ width: 34, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{Math.round(norm[k] * 100)}%</span>
        </label>
      ))}
    </div>
  );
}
