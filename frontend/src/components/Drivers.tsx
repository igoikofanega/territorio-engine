import { ArrowDown, ArrowUp } from "lucide-react";

import { parsearDrivers } from "../motivos";

/** Los factores que el modelo asocia a la predicción, en frases en vez de en la cadena
 * cruda `paro↑ · tendencia↓`.
 *
 * La flecha se pinta en gris neutro a propósito, no en el color de crece/decrece: la
 * dirección de una feature (más paro, menos fibra) no es en sí misma buena o mala,
 * solo está asociada con la predicción. Colorearla como "crece"/"decae" insinuaría un
 * juicio que el modelo no hace.
 */
export default function Drivers({ drivers }: { drivers: string | null }) {
  const items = parsearDrivers(drivers);
  if (!items.length) return null;

  return (
    <div>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 6 }}>
        {items.map((d) => (
          <li key={d.etiqueta} style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 12 }}>
            {d.direccion === "↑" ? (
              <ArrowUp size={13} strokeWidth={2} style={{ color: "var(--text-2)", flexShrink: 0, marginTop: 1 }} />
            ) : (
              <ArrowDown size={13} strokeWidth={2} style={{ color: "var(--text-2)", flexShrink: 0, marginTop: 1 }} />
            )}
            <span style={{ color: "var(--text)" }}>{d.texto}</span>
          </li>
        ))}
      </ul>
      <div style={{ fontSize: 10, color: "var(--text-2)", marginTop: 8 }}>
        Factores asociados a la predicción, no causas.
      </div>
    </div>
  );
}
