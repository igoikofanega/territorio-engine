/** Traduce los "drivers" del modelo (`paro↑ · tendencia↓`) a frases legibles.
 *
 * El backend (`ml/modelo.py::ETIQUETAS`) ya reduce el nombre técnico de cada feature
 * a una etiqueta corta ("paro_1000" → "paro"); esto va un paso más allá y convierte esa
 * etiqueta más su signo en una frase. Se hace en el cliente y no en el pipeline: cambiar
 * el texto no debe obligar a reentrenar el modelo ni a reescribir 8.217 filas.
 *
 * Las claves son exactamente los valores de `ETIQUETAS` (no las claves de `FEATURES`).
 * Si el diccionario del backend cambia, un driver con etiqueta desconocida cae al
 * fallback en `frase()` en vez de reventar: una frase genérica es mejor que una ficha
 * rota por un despliegue a medias entre servicios.
 */

type Direccion = "↑" | "↓";

const FRASES: Record<string, { up: string; down: string }> = {
  "tamaño": {
    up: "es de los municipios más grandes de su entorno",
    down: "es de los municipios más pequeños de su entorno",
  },
  densidad: { up: "tiene una densidad de población alta", down: "tiene una densidad de población baja" },
  paro: { up: "tiene un paro más alto de lo habitual", down: "tiene un paro más bajo de lo habitual" },
  renta: { up: "tiene una renta más alta de lo habitual", down: "tiene una renta más baja de lo habitual" },
  alquiler: { up: "el alquiler es caro en su entorno", down: "el alquiler es barato en su entorno" },
  "envejec.": { up: "está más envejecido de lo habitual", down: "está menos envejecido de lo habitual" },
  "temp.": { up: "tiene un clima más cálido de lo habitual", down: "tiene un clima más frío de lo habitual" },
  lluvia: { up: "recibe más lluvia de lo habitual", down: "recibe menos lluvia de lo habitual" },
  natalidad: { up: "su provincia tiene una natalidad alta", down: "su provincia tiene una natalidad baja" },
  mortalidad: { up: "su provincia tiene una mortalidad alta", down: "su provincia tiene una mortalidad baja" },
  tendencia: { up: "venía creciendo en los últimos años", down: "venía perdiendo población en los últimos años" },
  "sanidad lejos": { up: "está lejos de un centro de salud", down: "tiene un centro de salud cerca" },
  lejanía: { up: "está lejos de la capital de provincia", down: "está cerca de la capital de provincia" },
  sol: { up: "tiene más días despejados de lo habitual", down: "tiene menos días despejados de lo habitual" },
  frío: { up: "tiene inviernos más fríos de lo habitual", down: "tiene inviernos más suaves de lo habitual" },
  inmigración: {
    up: "tiene más población extranjera de lo habitual",
    down: "tiene menos población extranjera de lo habitual",
  },
  fibra: { up: "tiene buena cobertura de fibra", down: "tiene poca cobertura de fibra" },
};

export function frase(etiqueta: string, direccion: Direccion): string {
  const par = FRASES[etiqueta];
  if (!par) return etiqueta; // etiqueta desconocida: mejor mostrarla pelada que romper
  return direccion === "↑" ? par.up : par.down;
}

/** Versión corta (1-3 palabras) de la misma frase, para sitios sin espacio como un
 * chip. `ml/clustering.py::etiquetas` construye la etiqueta de cada arquetipo con el
 * MISMO formato que los drivers de predicción (`"{ETIQUETAS[f]}{↑|↓}"`), así que un
 * arquetipo hoy se enseñaba como "alquiler↑ · tamaño↑" — exactamente tan ilegible como
 * lo eran los drivers antes de esto. */
const CORTAS: Record<string, { up: string; down: string }> = {
  "tamaño": { up: "grande", down: "pequeño" },
  densidad: { up: "denso", down: "disperso" },
  paro: { up: "paro alto", down: "paro bajo" },
  renta: { up: "renta alta", down: "renta baja" },
  alquiler: { up: "alquiler caro", down: "alquiler barato" },
  "envejec.": { up: "envejecido", down: "joven" },
  "temp.": { up: "cálido", down: "frío" },
  lluvia: { up: "lluvioso", down: "seco" },
  natalidad: { up: "natalidad alta", down: "natalidad baja" },
  mortalidad: { up: "mortalidad alta", down: "mortalidad baja" },
  tendencia: { up: "en auge", down: "en declive" },
  "sanidad lejos": { up: "sanidad lejos", down: "sanidad cerca" },
  lejanía: { up: "aislado", down: "bien conectado" },
  sol: { up: "soleado", down: "nuboso" },
  frío: { up: "inviernos fríos", down: "inviernos suaves" },
  inmigración: { up: "con inmigración", down: "poca inmigración" },
  fibra: { up: "con fibra", down: "sin fibra" },
};

function fraseCorta(etiqueta: string, direccion: Direccion): string {
  const par = CORTAS[etiqueta];
  if (!par) return etiqueta;
  return direccion === "↑" ? par.up : par.down;
}

/** `"alquiler↑ · tamaño↑"` → `"alquiler caro · grande"`. Si la cadena no tiene el
 * formato esperado, se devuelve tal cual: mejor una etiqueta rara que una vacía. */
export function etiquetaArquetipo(cruda: string | null): string {
  if (!cruda) return "";
  const items = parsearDrivers(cruda);
  if (!items.length) return cruda;
  return items.map((d) => fraseCorta(d.etiqueta, d.direccion)).join(" · ");
}

export type Driver = { etiqueta: string; direccion: Direccion; texto: string };

/** `"paro↑ · tendencia↓"` → dos `Driver`. La flecha es siempre el último carácter del
 * token: contrato estable desde `ml/modelo.py::_drivers`. */
export function parsearDrivers(drivers: string | null): Driver[] {
  if (!drivers) return [];
  return drivers
    .split(" · ")
    .map((token) => {
      const direccion = token.slice(-1) as Direccion;
      const etiqueta = token.slice(0, -1);
      return { etiqueta, direccion, texto: frase(etiqueta, direccion) };
    })
    .filter((d) => d.direccion === "↑" || d.direccion === "↓");
}
