import type { FichaData } from "../types";
import Sparkline from "./Sparkline";

function Componente({ nombre, valor }: { nombre: string; valor: number | null }) {
  const v = valor == null ? 0 : Math.round(valor);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, margin: "4px 0" }}>
      <span style={{ width: 90, color: "var(--text-2)" }}>{nombre}</span>
      <span style={{ flex: 1, background: valor == null ? "var(--border)" : "var(--accent-soft)", height: 8, borderRadius: 4, overflow: "hidden" }}>
        <span style={{ display: "block", width: `${v}%`, height: "100%", background: "var(--accent)", borderRadius: 4 }} />
      </span>
      <span style={{ width: 30, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{valor == null ? "—" : v}</span>
    </div>
  );
}

export default function Ficha({ ficha, onClose, onSelect }: { ficha: FichaData | null; onClose: () => void; onSelect: (cod: string) => void }) {
  if (!ficha) {
    return (
      <div className="ficha" style={{ padding: 16 }}>
        <button className="btn-ghost" onClick={onClose} style={{ float: "right", fontSize: 18 }}>×</button>
        <p style={{ color: "var(--text-2)" }}>Cargando…</p>
      </div>
    );
  }
  const pred = ficha.prediccion;
  const idx = ficha.indice;
  const foto = ficha.wiki?.imagen;
  return (
    <div className="ficha">
      {/* cabecera: foto con gradiente o bloque de color plano */}
      <div
        style={{
          position: "relative",
          height: foto ? 150 : 84,
          background: foto ? `url(${foto}) center/cover` : "linear-gradient(135deg, #1e3a8a, #2563eb)",
        }}
      >
        <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg, rgba(15,23,42,0) 30%, rgba(15,23,42,.75))" }} />
        <button
          className="btn-ghost"
          onClick={onClose}
          style={{ position: "absolute", top: 8, right: 8, fontSize: 18, color: "white", background: "rgba(15,23,42,.4)", width: 28, height: 28 }}
        >
          ×
        </button>
        <div style={{ position: "absolute", left: 16, right: 16, bottom: 10, color: "white" }}>
          <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.02em", textShadow: "0 1px 3px rgba(0,0,0,.5)" }}>{ficha.nombre}</div>
          <div style={{ fontSize: 11, opacity: 0.9 }}>
            {ficha.provincia.nombre}
            {ficha.wiki?.gentilicio ? ` · ${ficha.wiki.gentilicio}` : ""}
            {ficha.superficie_km2 ? ` · ${ficha.superficie_km2.toFixed(1)} km²` : ""}
            {ficha.wiki?.altitud ? ` · ${Math.round(ficha.wiki.altitud)} m` : ""}
          </div>
        </div>
      </div>

      <div style={{ padding: 16 }}>
        {ficha.wiki?.descripcion && (
          <p style={{ margin: "0 0 12px", lineHeight: 1.45, color: "var(--text)" }}>{ficha.wiki.descripcion}</p>
        )}

        <h3>Población</h3>
        <Sparkline serie={ficha.serie} />

        {idx && (
          <>
            <h3>
              ¿Dónde vivir?{" "}
              <span style={{ color: "var(--accent)", fontSize: 16, fontWeight: 700, textTransform: "none", letterSpacing: 0 }}>
                {idx.score ?? "—"}<span style={{ fontSize: 11, color: "var(--text-2)" }}>/100</span>
              </span>
            </h3>
            <Componente nombre="renta" valor={idx.componentes.renta} />
            <Componente nombre="empleo" valor={idx.componentes.paro} />
            <Componente nombre="asequibilidad" valor={idx.componentes.alquiler} />
            <Componente nombre="vitalidad" valor={idx.componentes.envejecimiento} />
            <Componente nombre="servicios" valor={idx.componentes.servicios} />
          </>
        )}

        {pred && (
          <>
            <h3>Predicción a {pred.anio_horizonte}</h3>
            <div>
              <strong style={{ color: pred.cambio_pct >= 0 ? "#15803d" : "#b91c1c", fontSize: 15 }}>
                {pred.cambio_pct >= 0 ? "+" : ""}{pred.cambio_pct}%
              </strong>
              {pred.cambio_inf != null && (
                <span style={{ color: "var(--text-2)" }}> [{pred.cambio_inf}%..{pred.cambio_sup}%]</span>
              )}
              <span style={{ color: "var(--text-2)" }}> → {pred.pob_proyectada.toLocaleString("es")} hab</span>
            </div>
            {pred.drivers && <div style={{ color: "var(--text-2)", fontSize: 11, marginTop: 2 }}>{pred.drivers}</div>}
          </>
        )}

        {ficha.arquetipo && (
          <div style={{ marginTop: 12 }}>
            <span className="chip" style={{ cursor: "default", background: "var(--bg)", color: "var(--text-2)" }}>
              Arquetipo #{ficha.arquetipo.cluster}: {ficha.arquetipo.etiqueta}
            </span>
          </div>
        )}

        {ficha.servicios && (
          <>
            <h3>Servicios (OSM)</h3>
            <div style={{ color: "var(--text-2)" }}>
              🏥 {ficha.servicios.salud ?? 0} · 🎓 {ficha.servicios.educacion ?? 0} · 🛒 {ficha.servicios.comercio ?? 0}
              <span style={{ opacity: 0.7 }}> (total {ficha.servicios.total ?? 0})</span>
            </div>
          </>
        )}

        {ficha.similares.length > 0 && (
          <>
            <h3>Pueblos como {ficha.nombre}</h3>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {ficha.similares.map((s) => (
                <button key={s.cod} className="chip" onClick={() => onSelect(s.cod)} title={s.provincia}>
                  {s.nombre}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
