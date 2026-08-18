import { COLOR_CRECE, COLOR_DECAE } from "./escalas";
import type { FichaData } from "./types";

/** La respuesta a la pregunta bandera del proyecto: "¿hacia dónde va este pueblo?".
 *
 * Es una función pura, no un LLM: el ADR 0005 acota el LLM a la capa de noticias, y un
 * veredicto generado por un modelo de lenguaje no sería ni determinista ni auditable.
 * Esto es lo contrario: mismas reglas, mismo resultado, siempre.
 */
export type Tono = "crece" | "incierto" | "se-vacia" | "sin-datos";
export type Confianza = "alta" | "media" | "baja";

export type Veredicto = {
  tono: Tono;
  titular: string;
  /** `null` cuando no hay predicción o no hay banda de incertidumbre que medir. */
  confianza: Confianza | null;
  /** Comparación con la proyección cohorte-componente (ADR 0004), si existe. */
  contraste: string | null;
};

export const fmtPct = (n: number): string => `${n >= 0 ? "+" : ""}${n}%`;

/** `["a"] → "a"`, `["a","b"] → "a y b"`, `["a","b","c"] → "a, b y c"`. Sin esto, un
 * municipio al que le faltan los tres datos —existe, ver `Comunidad de Bascuñana y
 * Viloria de Rioja`, una entidad geográfica sin población propia— leía "le faltan
 * población y paro y renta", torpe en español. */
function listaEs(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  return `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`;
}

/** Mismo color en el titular y en `Trayectoria`: nunca pueden contradecirse sobre si
 * hay que afirmar una dirección. "incierto"/"sin-datos" usan el gris de texto — un
 * color aquí sería ya una afirmación. */
export function colorDeTono(tono: Tono): string {
  if (tono === "crece") return COLOR_CRECE;
  if (tono === "se-vacia") return COLOR_DECAE;
  return "var(--text-2)";
}

/** Sin predicción, el hueco se explica, no se deja en blanco.
 *
 * El motivo exacto (qué año usó el modelo y por qué este municipio no encajó) vive en
 * el backend y no llega al cliente. Lo que sí se puede comprobar aquí es si el dato más
 * reciente de la serie tiene los tres ingredientes que el modelo exige a la vez
 * (`ml/modelo.py::COLUMNAS_PRED`): población, paro y renta. Si falta alguno, se nombra;
 * si no falta ninguno, se dice la regla general en vez de inventar una causa que no se
 * puede verificar desde aquí.
 */
function motivoSinPrediccion(f: FichaData): string {
  const ultima = f.serie[f.serie.length - 1];
  if (!ultima) {
    return `El modelo no predice ${f.nombre}: no hay datos en la serie histórica.`;
  }
  const faltan: string[] = [];
  if (ultima.poblacion == null) faltan.push("población");
  if (ultima.paro == null) faltan.push("paro");
  if (ultima.renta == null) faltan.push("renta");
  if (faltan.length) {
    return (
      `El modelo no predice ${f.nombre}. Su dato más reciente es de ${ultima.anio} y le faltan ` +
      `${listaEs(faltan)}: el modelo solo predice cuando población, paro y renta coinciden en el mismo año.`
    );
  }
  return `El modelo no predice ${f.nombre}: no cumple los requisitos de datos del año que usa el modelo actualmente.`;
}

export function veredicto(f: FichaData): Veredicto {
  const pred = f.prediccion;
  if (!pred) {
    return { tono: "sin-datos", titular: motivoSinPrediccion(f), confianza: null, contraste: null };
  }

  const { cambio_pct, cambio_inf, cambio_sup, anio_horizonte } = pred;
  const tieneBanda = cambio_inf != null && cambio_sup != null;
  const cruzaCero = tieneBanda && cambio_inf < 0 && cambio_sup > 0;

  const cohorte = f.proyeccion_cohorte;
  const discrepan =
    cohorte != null &&
    Math.sign(cambio_pct) !== 0 &&
    Math.sign(cohorte.cambio_pct) !== 0 &&
    Math.sign(cambio_pct) !== Math.sign(cohorte.cambio_pct);

  // El desacuerdo entre los dos métodos (ADR 0004) es, en sí mismo, una forma de
  // incertidumbre: no tiene sentido afirmar una dirección que el otro modelo contradice.
  const esIncierto = cruzaCero || discrepan;
  const tono: Tono = esIncierto ? "incierto" : cambio_pct >= 0 ? "crece" : "se-vacia";

  let confianza: Confianza | null = null;
  if (tieneBanda) {
    const ancho = cambio_sup - cambio_inf;
    // Umbrales en puntos porcentuales del propio ancho de la banda, no relativos a la
    // población: son directamente lo que el usuario lee (cambio_inf/cambio_sup), así
    // que no hace falta una segunda escala para explicar la confianza.
    confianza = ancho <= 6 ? "alta" : ancho <= 14 ? "media" : "baja";
  }

  // El titular se construye SABIENDO ya si hay que ser prudente. La regla que no se
  // puede romper: cruzar cero, o que los dos métodos discrepen, nunca produce un
  // titular direccional ("crece"/"se vacía") — eso lo fija el test de este módulo.
  let titular: string;
  if (cruzaCero) {
    titular =
      `El modelo no distingue si ${f.nombre} crecerá o perderá población: su margen ` +
      `para ${anio_horizonte} va de ${fmtPct(cambio_inf)} a ${fmtPct(cambio_sup)}.`;
  } else if (discrepan) {
    titular =
      `El modelo estadístico y la proyección demográfica no coinciden sobre ${f.nombre}: ` +
      "trátalo como incierto.";
  } else if (tono === "crece") {
    titular =
      `${f.nombre} crece: el modelo espera ${fmtPct(cambio_pct)} para ${anio_horizonte}` +
      (tieneBanda ? `, entre ${fmtPct(cambio_inf)} y ${fmtPct(cambio_sup)}.` : ".");
  } else {
    titular =
      `${f.nombre} se vacía: el modelo espera ${fmtPct(cambio_pct)} para ${anio_horizonte}` +
      (tieneBanda ? `, entre ${fmtPct(cambio_inf)} y ${fmtPct(cambio_sup)}.` : ".");
  }

  const contraste = cohorte
    ? discrepan
      ? `Los dos métodos no coinciden: el estadístico ve ${fmtPct(cambio_pct)}, ` +
        `el demográfico ${fmtPct(cohorte.cambio_pct)}.`
      : `La proyección demográfica clásica llega a una conclusión parecida ` +
        `(${fmtPct(cohorte.cambio_pct)}).`
    : null;

  return { tono, titular, confianza, contraste };
}
