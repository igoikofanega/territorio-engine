import { COLOR_CRECE, COLOR_DECAE } from "../escalas";

/** Una fila del motor demográfico (vegetativo o migratorio): una barra centrada en
 * cero, con el brazo hacia un lado u otro según el signo.
 *
 * Reemplaza el párrafo de antes —dos números en negrita de color sin escala común—.
 * `max` es el mismo en las dos filas que la usan (vegetativo y migratorio): así el
 * lector compara los brazos entre sí, no solo el número.
 */
export default function BarraDivergente({
  etiqueta,
  valor,
  max,
  estimado,
}: {
  etiqueta: string;
  valor: number | null;
  max: number;
  estimado?: boolean;
}) {
  const v = valor ?? 0;
  const frac = max > 0 ? Math.min(1, Math.abs(v) / max) : 0;
  const color = v >= 0 ? COLOR_CRECE : COLOR_DECAE;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, margin: "5px 0" }}>
      <span style={{ width: 78, color: "var(--text-2)" }}>
        {etiqueta}
        {estimado && <sup title="Estimado con tasas provinciales, no medido municipio a municipio">≈</sup>}
      </span>
      <svg viewBox="0 0 100 10" style={{ flex: 1, height: 10, display: "block" }} aria-hidden="true">
        <line x1={50} x2={50} y1={0} y2={10} stroke="var(--border)" strokeWidth={1} />
        {v >= 0 ? (
          <rect x={50} y={2} width={frac * 48} height={6} rx={2} fill={color} />
        ) : (
          <rect x={50 - frac * 48} y={2} width={frac * 48} height={6} rx={2} fill={color} />
        )}
      </svg>
      <span
        style={{ width: 64, textAlign: "right", fontVariantNumeric: "tabular-nums", color: "var(--text)" }}
      >
        {valor == null ? "—" : `${v >= 0 ? "+" : ""}${v.toLocaleString("es")}`}
      </span>
    </div>
  );
}
