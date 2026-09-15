import { etiquetasRango } from "../leyenda";

export default function Leyenda({
  titulo,
  buckets,
  sufijo = "",
  categorias,
  lectura,
  nota,
}: {
  titulo: string;
  buckets: [number, string][];
  sufijo?: string;
  categorias?: { color: string; label: string }[] | null;
  /** Línea corta bajo la leyenda, para cuando el color no se explica por sí solo
   * (escalas divergentes, o un hue que no sigue "oscuro = más"). */
  lectura?: string | null;
  nota?: string | null;
}) {
  const items =
    categorias ?? etiquetasRango(buckets, sufijo).map((label, i) => ({ color: buckets[i][1], label }));
  return (
    <div className="panel" style={{ position: "absolute", bottom: 20, right: 16, zIndex: 1000, padding: "10px 12px", fontSize: 12, maxWidth: 230 }}>
      <div style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-2)", marginBottom: 6 }}>
        {titulo}
      </div>
      {items.map((it, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, margin: "2px 0" }}>
          <span style={{ width: 14, height: 14, background: it.color, display: "inline-block", flexShrink: 0, borderRadius: 3 }} />
          <span style={{ color: "var(--text-2)" }}>{it.label}</span>
        </div>
      ))}
      {lectura && (
        <div style={{ marginTop: 6, paddingTop: 6, borderTop: "1px solid var(--border)", fontSize: 10, color: "var(--text-2)", lineHeight: 1.4 }}>
          {lectura}
        </div>
      )}
      {nota && <div style={{ marginTop: 6, fontSize: 10, color: "var(--accent)" }}>{nota}</div>}
    </div>
  );
}
