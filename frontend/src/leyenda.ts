/** Construye las etiquetas de los cortes numéricos de una leyenda como RANGOS, no como
 * "≥ umbral" repetido en cada fila.
 *
 * `color()` (escalas.ts) recorre `buckets` de mayor a menor umbral y devuelve el color
 * del primero que cumple `v >= umbral`. Eso significa que el corte de cada fila es su
 * cota INFERIOR, no un valor aislado — la fila del medio de una escala
 * `[[20,a],[5,b],[0,c],[-10,d]]` cubre `[0, 5)`, no "≥ 0". La leyenda anterior escribía
 * "≥ umbral" en las 6 filas por igual, así que la última clase de la capa de predicción
 * se leía "≥ -100%" cuando lo que significa es "por debajo de -20%": técnicamente
 * cierto, pero ilegible para cualquiera que no conozca el código.
 *
 * Función pura en su propio módulo (no en Leyenda.tsx) para que Vite/React Fast Refresh
 * no se queje de un fichero que exporta a la vez un componente y una función suelta.
 */
export function etiquetasRango(buckets: [number, string][], sufijo: string): string[] {
  const fmt = (n: number) => `${n.toLocaleString("es")}${sufijo}`;
  return buckets.map(([umbral], i) => {
    if (i === 0) return `≥ ${fmt(umbral)}`;
    if (i === buckets.length - 1) return `< ${fmt(buckets[i - 1][0])}`;
    return `${fmt(umbral)} – ${fmt(buckets[i - 1][0])}`;
  });
}
