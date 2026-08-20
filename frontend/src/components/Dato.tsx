/** Un valor con su procedencia declarada.
 *
 * Centraliza el principio de honestidad sobre los datos (AGENTS.md): "medido",
 * "estimado", "imputado", "no consultado" y "ausente" son afirmaciones distintas, y hoy
 * viven repartidas en prosa por quince secciones de la ficha. Aquí es un único punto.
 *
 * `"no-consultado"` renderiza el texto "no consultado", NUNCA `0`: confundirlos es
 * exactamente el error que este componente existe para evitar (el caso de la capa de
 * noticias, regional, frente a un municipio fuera de su ámbito).
 */
type Origen = "medido" | "estimado" | "imputado" | "no-consultado" | "ausente";

const GLIFOS: Record<Origen, { simbolo: string; titulo: string }> = {
  medido: { simbolo: "", titulo: "Dato medido" },
  estimado: { simbolo: "≈", titulo: "Estimado: derivado de tasas o proxies, no medido directamente" },
  imputado: { simbolo: "†", titulo: "Imputado: el valor original estaba enmascarado o incompleto" },
  "no-consultado": { simbolo: "", titulo: "Esta capa no cubre este municipio: no es que el valor sea cero" },
  ausente: { simbolo: "", titulo: "Sin dato" },
};

export default function Dato({
  valor,
  unidad,
  anio,
  origen,
  nota,
}: {
  valor: number | string | null;
  unidad?: string;
  anio?: number;
  origen: Origen;
  nota?: string;
}) {
  if (origen === "no-consultado") {
    return (
      <span style={{ color: "var(--text-2)" }} title={nota ?? GLIFOS[origen].titulo}>
        no consultado
      </span>
    );
  }
  if (origen === "ausente" || valor == null) {
    return <span style={{ color: "var(--text-2)" }}>—</span>;
  }
  const glifo = GLIFOS[origen];
  return (
    <span title={nota ?? glifo.titulo}>
      {typeof valor === "number" ? valor.toLocaleString("es") : valor}
      {unidad && <span style={{ marginLeft: 2 }}>{unidad}</span>}
      {glifo.simbolo && (
        <sup style={{ marginLeft: 2, fontSize: "0.8em", color: "var(--text-2)" }}>{glifo.simbolo}</sup>
      )}
      {anio != null && <span style={{ marginLeft: 4, fontSize: "0.85em", color: "var(--text-2)" }}>{anio}</span>}
    </span>
  );
}

export type { Origen };
