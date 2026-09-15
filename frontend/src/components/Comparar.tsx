import { X } from "lucide-react";
import { m } from "motion/react";
import type { CSSProperties } from "react";
import { useEffect, useState } from "react";

import type { FichaData } from "../types";
import Buscador from "./Buscador";
import Sparkline from "./Sparkline";

const API = "/api";

/** Última observación no nula de un campo de la serie. */
function ultimo(f: FichaData | null, campo: "poblacion" | "renta" | "alquiler"): number | null {
  if (!f) return null;
  const rows = f.serie.filter((r) => r[campo] != null);
  return rows.length ? (rows[rows.length - 1][campo] as number) : null;
}

/** Una fila comparativa: etiqueta + los dos valores, resaltando el "mejor". */
function Fila({
  label,
  a,
  b,
  fmt = (v) => (v == null ? "—" : String(v)),
  mejor = "alto",
}: {
  label: string;
  a: number | null;
  b: number | null;
  fmt?: (v: number | null) => string;
  mejor?: "alto" | "bajo" | "ninguno";
}) {
  let ganaA = false, ganaB = false;
  if (mejor !== "ninguno" && a != null && b != null && a !== b) {
    const aGana = mejor === "alto" ? a > b : a < b;
    ganaA = aGana;
    ganaB = !aGana;
  }
  const cell = (gana: boolean): CSSProperties => ({
    flex: 1,
    textAlign: "center",
    fontVariantNumeric: "tabular-nums",
    fontWeight: gana ? 700 : 500,
    color: gana ? "var(--accent)" : "var(--text)",
  });
  return (
    <div style={{ display: "flex", alignItems: "center", padding: "7px 0", borderBottom: "1px solid var(--border)" }}>
      <span style={cell(ganaA)}>{fmt(a)}</span>
      <span style={{ width: 150, textAlign: "center", fontSize: 11, color: "var(--text-2)", textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</span>
      <span style={cell(ganaB)}>{fmt(b)}</span>
    </div>
  );
}

function Cabecera({ f, lado, onBuscar }: { f: FichaData | null; lado: "izq" | "der"; onBuscar: (cod: string) => void }) {
  return (
    <div style={{ flex: 1, textAlign: "center" }}>
      {f ? (
        <>
          <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.01em" }}>{f.nombre}</div>
          <div style={{ fontSize: 11, color: "var(--text-2)", marginBottom: 8 }}>{f.provincia.nombre}</div>
          <div style={{ maxWidth: 260, margin: "0 auto" }}><Sparkline serie={f.serie} /></div>
        </>
      ) : (
        <div style={{ maxWidth: 240, margin: "0 auto", paddingTop: 20 }}>
          <div style={{ fontSize: 12, color: "var(--text-2)", marginBottom: 6 }}>
            Elige el municipio {lado === "izq" ? "A" : "B"}
          </div>
          <Buscador onSelect={onBuscar} />
        </div>
      )}
    </div>
  );
}

export default function Comparar({ codA, codB, onClose }: { codA: string | null; codB: string | null; onClose: () => void }) {
  const [a, setA] = useState<FichaData | null>(null);
  const [b, setB] = useState<FichaData | null>(null);
  const [selA, setSelA] = useState(codA);
  const [selB, setSelB] = useState(codB);

  useEffect(() => {
    if (!selA) { setA(null); return; }
    fetch(`${API}/municipio/${selA}`).then((r) => r.json()).then(setA).catch(() => setA(null));
  }, [selA]);
  useEffect(() => {
    if (!selB) { setB(null); return; }
    fetch(`${API}/municipio/${selB}`).then((r) => r.json()).then(setB).catch(() => setB(null));
  }, [selB]);

  const eur = (v: number | null) => (v == null ? "—" : `${Math.round(v).toLocaleString("es")} €`);
  const num = (v: number | null) => (v == null ? "—" : v.toLocaleString("es"));
  const pct = (v: number | null) => (v == null ? "—" : `${v}%`);

  return (
    <m.div
      style={{ position: "absolute", inset: 0, zIndex: 1300, background: "rgba(15,23,42,.35)", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
    >
      <m.div
        className="panel"
        style={{ width: "100%", maxWidth: 720, maxHeight: "100%", overflowY: "auto", padding: 20, boxShadow: "var(--shadow-lg)" }}
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.97 }}
        transition={{ duration: 0.18, ease: "easeOut" }}
      >
        <div style={{ display: "flex", alignItems: "center", marginBottom: 12 }}>
          <strong style={{ fontSize: 15 }}>Comparar municipios</strong>
          <button className="btn-ghost" onClick={onClose} style={{ marginLeft: "auto" }}><X size={16} /></button>
        </div>

        <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
          <Cabecera f={a} lado="izq" onBuscar={setSelA} />
          <Cabecera f={b} lado="der" onBuscar={setSelB} />
        </div>

        {a && b && (
          <div>
            <Fila label="Población" a={ultimo(a, "poblacion")} b={ultimo(b, "poblacion")} fmt={num} />
            <Fila label="¿Dónde vivir?" a={a.indice?.score ?? null} b={b.indice?.score ?? null} fmt={(v) => (v == null ? "—" : `${v}/100`)} />
            <Fila label="Renta €/pers" a={ultimo(a, "renta")} b={ultimo(b, "renta")} fmt={eur} />
            <Fila label="Alquiler €/m²" a={ultimo(a, "alquiler")} b={ultimo(b, "alquiler")} fmt={(v) => (v == null ? "—" : `${v} €`)} mejor="bajo" />
            <Fila label="Predicción" a={a.prediccion?.cambio_pct ?? null} b={b.prediccion?.cambio_pct ?? null} fmt={(v) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${v}%`)} />
            <Fila label="Riesgo despob." a={a.riesgo?.prob ?? null} b={b.riesgo?.prob ?? null} fmt={pct} mejor="bajo" />
            <Fila label="Servicios" a={a.servicios?.total ?? null} b={b.servicios?.total ?? null} fmt={num} />
            <Fila label="Sanidad (km)" a={a.aislamiento?.km_salud ?? null} b={b.aislamiento?.km_salud ?? null} fmt={(v) => (v == null ? "—" : `${v} km`)} mejor="bajo" />
            <div style={{ display: "flex", padding: "8px 0", fontSize: 11, color: "var(--text-2)" }}>
              <span style={{ flex: 1, textAlign: "center" }}>{a.inflexion ? `${a.inflexion.tipo} en ${a.inflexion.anio}` : "sin inflexión"}</span>
              <span style={{ width: 150, textAlign: "center", textTransform: "uppercase", letterSpacing: "0.04em" }}>Inflexión</span>
              <span style={{ flex: 1, textAlign: "center" }}>{b.inflexion ? `${b.inflexion.tipo} en ${b.inflexion.anio}` : "sin inflexión"}</span>
            </div>
            <div style={{ fontSize: 10, color: "var(--text-2)", textAlign: "center", marginTop: 8 }}>
              En azul y negrita, el municipio mejor posicionado en cada indicador.
            </div>
          </div>
        )}
      </m.div>
    </m.div>
  );
}
