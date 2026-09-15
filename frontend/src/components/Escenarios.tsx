import { RIESGO_COLORES } from "../escalas";
import type { FichaData } from "../types";

//: % de pérdida de población a 5 años que define el evento "despoblación fuerte".
//: Fijo en el backend (ml/riesgo.py::UMBRAL_PERDIDA = -10.0); si cambia ahí, cambia aquí.
const UMBRAL_PERDIDA_PCT = 10;
const HORIZONTE_DEFECTO = 5;

/** El riesgo, en frecuencias en vez de en porcentaje.
 *
 * Un porcentaje aislado ("23% de probabilidad") exige que quien lo lee haga la
 * conversión mental a algo tangible. El encuadre por frecuencias —cien círculos, unos
 * cuantos coloreados— es la forma que mejor entienden los lectores sin formación
 * estadística, y es la que recomienda la literatura sobre comunicación de
 * incertidumbre a público no experto.
 */
export default function Escenarios({
  riesgo,
  nombre,
  horizonteAnios,
}: {
  riesgo: FichaData["riesgo"];
  nombre: string;
  horizonteAnios?: number;
}) {
  if (!riesgo) return null;
  const n = Math.max(0, Math.min(100, Math.round(riesgo.prob)));
  const color = RIESGO_COLORES[riesgo.nivel];
  const horizonte = horizonteAnios ?? HORIZONTE_DEFECTO;

  return (
    <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
      <svg viewBox="0 0 100 100" style={{ width: 76, height: 76, flexShrink: 0 }} aria-hidden="true">
        {Array.from({ length: 100 }, (_, i) => {
          const x = (i % 10) * 10 + 5;
          const y = Math.floor(i / 10) * 10 + 5;
          return <circle key={i} cx={x} cy={y} r={3.1} fill={i < n ? color : "var(--track)"} />;
        })}
      </svg>
      <p style={{ margin: 0, fontSize: 12, lineHeight: 1.5, color: "var(--text-2)" }}>
        De cada 100 pueblos en la situación de <strong style={{ color: "var(--text)" }}>{nombre}</strong>, el
        modelo espera que <strong style={{ color }}>{n}</strong> pierdan más del {UMBRAL_PERDIDA_PCT}% de su
        población en los próximos {horizonte} años.
      </p>
    </div>
  );
}
