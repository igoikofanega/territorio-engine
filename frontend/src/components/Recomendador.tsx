import { Wand2, X } from "lucide-react";
import { useState } from "react";

import { CLAVES_INDICE, type Pesos } from "../types";

const API = "/api";

type Resultado = {
  cod: string;
  nombre: string;
  provincia: string;
  score: number;
  razones: string[];
  pob: number | null;
  alquiler: number | null;
  temp: number | null;
  riesgo_pct: number | null;
  cambio_pct: number | null;
};

const TAMANOS = [
  { label: "Pueblo", desc: "hasta 5.000", pob_min: undefined, pob_max: 5000 },
  { label: "Medio", desc: "5.000-50.000", pob_min: 5000, pob_max: 50000 },
  { label: "Ciudad", desc: "más de 50.000", pob_min: 50000, pob_max: undefined },
  { label: "Da igual", desc: "", pob_min: undefined, pob_max: undefined },
] as const;

const CLIMAS = [
  { label: "Fresco", desc: "<12 °C", temp_min: undefined, temp_max: 12 },
  { label: "Templado", desc: "12-17 °C", temp_min: 12, temp_max: 17 },
  { label: "Cálido", desc: ">17 °C", temp_min: 17, temp_max: undefined },
  { label: "Da igual", desc: "", temp_min: undefined, temp_max: undefined },
] as const;

export default function Recomendador({
  pesos,
  onSelect,
  onClose,
}: {
  pesos: Pesos;
  onSelect: (cod: string) => void;
  onClose: () => void;
}) {
  const [tamano, setTamano] = useState(3);
  const [clima, setClima] = useState(3);
  const [alquilerMax, setAlquilerMax] = useState("");
  const [saludCerca, setSaludCerca] = useState(false);
  const [resultados, setResultados] = useState<Resultado[] | null>(null);
  const [cargando, setCargando] = useState(false);

  const buscar = () => {
    setCargando(true);
    const p = new URLSearchParams();
    const t = TAMANOS[tamano];
    const c = CLIMAS[clima];
    if (t.pob_min != null) p.set("pob_min", String(t.pob_min));
    if (t.pob_max != null) p.set("pob_max", String(t.pob_max));
    if (c.temp_min != null) p.set("temp_min", String(c.temp_min));
    if (c.temp_max != null) p.set("temp_max", String(c.temp_max));
    if (alquilerMax.trim()) p.set("alquiler_max", alquilerMax.trim());
    if (saludCerca) p.set("km_salud_max", "5");
    for (const k of CLAVES_INDICE) p.set(`w_${k}`, pesos[k].toFixed(2));
    fetch(`${API}/recomendar?${p.toString()}`)
      .then((r) => r.json())
      .then((d: Resultado[]) => setResultados(d))
      .catch(() => setResultados([]))
      .finally(() => setCargando(false));
  };

  const grupoChips = (
    opciones: readonly { label: string; desc: string }[],
    valor: number,
    onCambio: (i: number) => void,
  ) => (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
      {opciones.map((o, i) => (
        <button
          key={o.label}
          className="chip"
          onClick={() => onCambio(i)}
          title={o.desc}
          style={valor === i ? { background: "var(--accent)", color: "white" } : undefined}
        >
          {o.label}
        </button>
      ))}
    </div>
  );

  return (
    <div
      className="panel"
      style={{ position: "absolute", top: 12, left: 12, zIndex: 1150, width: 340, maxHeight: "calc(100% - 24px)", overflowY: "auto", padding: 16 }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <Wand2 size={16} strokeWidth={1.75} style={{ color: "var(--accent)" }} />
        <strong>¿Dónde debería vivir yo?</strong>
        <button className="btn-ghost" onClick={onClose} style={{ marginLeft: "auto" }}>
          <X size={15} />
        </button>
      </div>

      <div className="grupo-titulo">Tamaño del municipio</div>
      {grupoChips(TAMANOS, tamano, setTamano)}

      <div className="grupo-titulo">Clima (temp. media)</div>
      {grupoChips(CLIMAS, clima, setClima)}

      <div className="grupo-titulo">Alquiler máximo (€/m², opcional)</div>
      <input
        className="input"
        type="number"
        min={0}
        step={0.5}
        value={alquilerMax}
        onChange={(e) => setAlquilerMax(e.target.value)}
        placeholder="p. ej. 8"
      />

      <label style={{ display: "flex", alignItems: "center", gap: 8, margin: "10px 0", fontSize: 12, cursor: "pointer" }}>
        <input type="checkbox" checked={saludCerca} onChange={(e) => setSaludCerca(e.target.checked)} style={{ accentColor: "var(--accent)" }} />
        Sanidad a menos de 5 km
      </label>

      <div style={{ fontSize: 11, color: "var(--text-2)", marginBottom: 10 }}>
        El ranking usa tus pesos del índice (ajústalos en el modo «¿Dónde vivir?»).
      </div>

      <button
        onClick={buscar}
        disabled={cargando}
        style={{ width: "100%", padding: "8px 0", border: 0, borderRadius: 6, background: "var(--accent)", color: "white", fontWeight: 600, fontSize: 13, cursor: "pointer", opacity: cargando ? 0.6 : 1 }}
      >
        {cargando ? "Buscando…" : "Buscar mi sitio"}
      </button>

      {resultados != null && (
        <div style={{ marginTop: 12 }}>
          {resultados.length === 0 && (
            <div style={{ fontSize: 12, color: "var(--text-2)" }}>Ningún municipio cumple esos filtros. Prueba a relajarlos.</div>
          )}
          {resultados.map((r, i) => (
            <button
              key={r.cod}
              onClick={() => onSelect(r.cod)}
              style={{ display: "block", width: "100%", textAlign: "left", padding: "8px 10px", margin: "4px 0", border: "1px solid var(--border)", borderRadius: 6, background: "white", cursor: "pointer", font: "inherit" }}
            >
              <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                <span style={{ color: "var(--text-2)", fontSize: 11, width: 18 }}>{i + 1}.</span>
                <strong style={{ fontSize: 13 }}>{r.nombre}</strong>
                <span style={{ color: "var(--text-2)", fontSize: 11 }}>{r.provincia}</span>
                <span style={{ marginLeft: "auto", color: "var(--accent)", fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{r.score}</span>
              </div>
              <div style={{ fontSize: 11, color: "var(--text-2)", marginTop: 2, paddingLeft: 24 }}>
                {r.razones.join(" · ")}
                {r.pob != null && <> · {r.pob.toLocaleString("es")} hab</>}
                {r.alquiler != null && <> · {r.alquiler} €/m²</>}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
