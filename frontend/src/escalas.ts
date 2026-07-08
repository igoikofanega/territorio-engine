import type { GeoJsonProperties } from "geojson";
import {
  Baby,
  Briefcase,
  CloudSun,
  Compass,
  Flame,
  Home,
  Hourglass,
  type LucideIcon,
  MapPinOff,
  Milestone,
  Shapes,
  Siren,
  Snowflake,
  Sparkles,
  Store,
  Sun,
  Target,
  Wifi,
  TrendingUp,
  UsersRound,
  Users,
  Wallet,
} from "lucide-react";

import { CLAVES_INDICE, type ClaveIndice, type Modo, type Pesos } from "./types";

const FUT_BUCKETS: [number, string][] = [[20, "#006837"], [5, "#1a9850"], [0, "#a6d96a"], [-10, "#fdae61"], [-20, "#f46d43"], [-100, "#a50026"]];
// paleta cualitativa para arquetipos (clusters)
export const PALETA_CAT = ["#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854", "#ffd92f", "#e5c494", "#b3b3b3"];

export const ESCALAS: Record<
  Modo,
  { endpoint: string; etiqueta: string; icono: LucideIcon; titulo: string; campo: string; sufijo: string; anios?: string; categorico?: boolean; buckets: [number, string][] }
> = {
  arquetipos: {
    endpoint: "arquetipos.geojson", etiqueta: "Arquetipos", icono: Shapes, titulo: "Arquetipos", campo: "cluster", sufijo: "", categorico: true, buckets: [],
  },
  indice: {
    endpoint: "indice.geojson", etiqueta: "¿Dónde vivir?", icono: Compass, titulo: "Índice 0-100", campo: "score", sufijo: "/100",
    buckets: [[70, "#006837"], [55, "#31a354"], [45, "#78c679"], [30, "#c2e699"], [0, "#ffffcc"]],
  },
  poblacion: {
    endpoint: "coropleta.geojson", etiqueta: "Población", icono: Users, titulo: "Habitantes", campo: "poblacion_total", sufijo: " hab", anios: "poblacion/anios",
    buckets: [[100000, "#08306b"], [20000, "#2171b5"], [5000, "#4292c6"], [1000, "#6baed6"], [500, "#9ecae1"], [100, "#c6dbef"], [0, "#deebf7"]],
  },
  renta: {
    endpoint: "renta.geojson", etiqueta: "Renta", icono: Wallet, titulo: "Renta €/persona", campo: "renta", sufijo: " €", anios: "renta/anios",
    buckets: [[20000, "#00441b"], [15000, "#238b45"], [12000, "#66c2a4"], [9000, "#b2e2e2"], [0, "#edf8fb"]],
  },
  alquiler: {
    endpoint: "alquiler.geojson", etiqueta: "Alquiler", icono: Home, titulo: "Alquiler €/m²", campo: "alquiler", sufijo: " €/m²", anios: "alquiler/anios",
    buckets: [[12, "#4a1486"], [9, "#6a51a3"], [7, "#9e9ac8"], [5, "#cbc9e2"], [0, "#f2f0f7"]],
  },
  paro: {
    endpoint: "paro.geojson", etiqueta: "Paro", icono: Briefcase, titulo: "Paro ‰ hab", campo: "paro_1000", sufijo: "‰", anios: "paro/anios",
    buckets: [[150, "#67000d"], [100, "#cb181d"], [60, "#fb6a4a"], [30, "#fcae91"], [0, "#fee5d9"]],
  },
  extranjeros: {
    endpoint: "extranjeros.geojson", etiqueta: "Extranjeros", icono: UsersRound, titulo: "% población extranjera", campo: "pct_extranjeros", sufijo: "%", anios: "extranjeros/anios",
    buckets: [[25, "#4a1486"], [15, "#6a51a3"], [10, "#807dba"], [5, "#bcbddc"], [0, "#f2f0f7"]],
  },
  fibra: {
    endpoint: "fibra.geojson", etiqueta: "Fibra / banda ancha", icono: Wifi, titulo: "% hogares con fibra (FTTH)", campo: "pct_fibra", sufijo: "%",
    buckets: [[95, "#08519c"], [80, "#3182bd"], [50, "#6baed6"], [20, "#bdd7e7"], [0, "#eff3ff"]],
  },
  servicios: {
    endpoint: "servicios.geojson", etiqueta: "Servicios", icono: Store, titulo: "Servicios ‰ hab (OSM)", campo: "serv_1000", sufijo: "‰",
    buckets: [[8, "#084594"], [4, "#2171b5"], [2, "#6baed6"], [1, "#c6dbef"], [0, "#f7fbff"]],
  },
  clima: {
    endpoint: "clima.geojson", etiqueta: "Clima", icono: CloudSun, titulo: "Temp. media °C", campo: "temp", sufijo: " °C",
    buckets: [[18, "#d73027"], [15, "#fc8d59"], [12, "#fee090"], [9, "#91bfdb"], [0, "#4575b4"]],
  },
  aislamiento: {
    endpoint: "aislamiento.geojson", etiqueta: "Aislamiento", icono: MapPinOff, titulo: "Km a sanidad", campo: "km_salud", sufijo: " km",
    buckets: [[20, "#54278f"], [10, "#756bb1"], [5, "#9e9ac8"], [2, "#cbc9e2"], [0, "#f2f0f7"]],
  },
  sol: {
    endpoint: "clima.geojson", etiqueta: "Días de sol", icono: Sun, titulo: "Días despejados/año", campo: "dias_despejados", sufijo: " días",
    buckets: [[120, "#b30000"], [90, "#e34a33"], [60, "#fc8d59"], [40, "#fdcc8a"], [0, "#fef0d9"]],
  },
  frio: {
    endpoint: "clima.geojson", etiqueta: "Frío invernal", icono: Snowflake, titulo: "Media de mínimas (°C)", campo: "temp_min_media", sufijo: " °C",
    buckets: [[12, "#fee5d9"], [8, "#c6dbef"], [5, "#9ecae1"], [2, "#4292c6"], [-100, "#08519c"]],
  },
  envejecimiento: {
    endpoint: "envejecimiento.geojson", etiqueta: "Envejecimiento", icono: Hourglass, titulo: "Índice envejec.", campo: "indice", sufijo: "", anios: "envejecimiento/anios",
    buckets: [[400, "#800026"], [200, "#bd0026"], [120, "#e31a1c"], [80, "#fc4e2a"], [40, "#feb24c"], [0, "#ffffb2"]],
  },
  lisa_crecimiento: {
    endpoint: "lisa.geojson?var=crecimiento", etiqueta: "Hot spots crecimiento", icono: Flame, titulo: "Clusters de crecimiento (LISA)", campo: "categoria", sufijo: "", categorico: true, buckets: [],
  },
  lisa_renta: {
    endpoint: "lisa.geojson?var=renta", etiqueta: "Hot spots renta", icono: Flame, titulo: "Clusters de renta (LISA)", campo: "categoria", sufijo: "", categorico: true, buckets: [],
  },
  rendimiento: {
    endpoint: "rendimiento.geojson", etiqueta: "Contra pronóstico", icono: Target, titulo: "Residuo vs predicho (pp)", campo: "residuo", sufijo: " pp",
    // divergente RdBu: azul = sobre-rinde, rojo = bajo-rinde
    buckets: [[15, "#2166ac"], [5, "#67a9cf"], [-5, "#f7f7f7"], [-15, "#ef8a62"], [-1000, "#b2182b"]],
  },
  inflexion: {
    endpoint: "inflexion.geojson", etiqueta: "Punto de inflexión", icono: Milestone, titulo: "¿Cómo cambió la tendencia?", campo: "tipo", sufijo: "", categorico: true, buckets: [],
  },
  demografia: {
    endpoint: "demografia.geojson", etiqueta: "Motor demográfico", icono: Baby, titulo: "¿Qué mueve la población?", campo: "tipo", sufijo: "", categorico: true, buckets: [],
  },
  prediccion: {
    endpoint: "prediccion.geojson", etiqueta: "Predicción ML", icono: Sparkles, titulo: "Cambio a 2028", campo: "cambio_pct", sufijo: "%",
    buckets: FUT_BUCKETS,
  },
  futuro: {
    endpoint: "futuro.geojson", etiqueta: "Futuro (tendencia)", icono: TrendingUp, titulo: "Cambio a 2035", campo: "cambio_pct", sufijo: "%",
    buckets: FUT_BUCKETS,
  },
  futuro_cohorte: {
    endpoint: "futuro-cohorte.geojson", etiqueta: "Futuro (cohorte)", icono: Baby, titulo: "Cambio a 2037", campo: "cambio_pct", sufijo: "%",
    buckets: FUT_BUCKETS,
  },
  riesgo: {
    endpoint: "riesgo.geojson", etiqueta: "Riesgo despoblación", icono: Siren, titulo: "P(pérdida fuerte) %", campo: "prob", sufijo: "%",
    // semáforo: verde <30, ámbar 30-60, rojo >=60
    buckets: [[60, "#b91c1c"], [30, "#f59e0b"], [0, "#16a34a"]],
  },
};

// colores LISA (convención: HH rojo, LL azul, outliers naranjas/celestes)
export const LISA_COLORES: Record<string, string> = {
  "alto-alto": "#d7191c",
  "bajo-bajo": "#2c7bb6",
  "alto-bajo": "#fdae61",
  "bajo-alto": "#abd9e9",
  ns: "#e8e8e8",
};
export const LISA_LEYENDA = [
  { color: "#d7191c", label: "Hot spot (alto entre altos)" },
  { color: "#2c7bb6", label: "Cold spot (bajo entre bajos)" },
  { color: "#fdae61", label: "Outlier alto entre bajos" },
  { color: "#abd9e9", label: "Outlier bajo entre altos" },
  { color: "#e8e8e8", label: "No significativo" },
];

// colores del tipo de giro (verde = mejora la trayectoria, rojo = empeora)
export const INFLEXION_COLORES: Record<string, string> = {
  remonta: "#1a9850",
  acelera: "#66bd63",
  "frena caída": "#a6d96a",
  frena: "#fee08b",
  "acelera caída": "#d73027",
  "se hunde": "#f46d43",
};
export const INFLEXION_LEYENDA = [
  { color: "#1a9850", label: "Remonta (caía y sube)" },
  { color: "#66bd63", label: "Acelera crecimiento" },
  { color: "#a6d96a", label: "Frena la caída" },
  { color: "#fee08b", label: "Frena crecimiento" },
  { color: "#f46d43", label: "Se hunde (subía y cae)" },
  { color: "#d73027", label: "Acelera la caída" },
  { color: "#e8e8e8", label: "Sin inflexión clara" },
];

// motor demográfico: verde = crece, rojo = declive; morado = sostenido por migración
export const DEMOGRAFIA_COLORES: Record<string, string> = {
  "doble motor": "#1a9850",
  "sostenido por migración": "#7b3294",
  "migración frena la caída": "#c2a5cf",
  "pierde por éxodo": "#fdae61",
  "doble declive": "#d7191c",
};
export const DEMOGRAFIA_LEYENDA = [
  { color: "#1a9850", label: "Doble motor (nace y llega gente)" },
  { color: "#7b3294", label: "Sostenido por migración" },
  { color: "#c2a5cf", label: "Migración frena la caída" },
  { color: "#fdae61", label: "Pierde por éxodo" },
  { color: "#d7191c", label: "Doble declive" },
  { color: "#e8e8e8", label: "Sin datos" },
];

// agrupación de modos para la sidebar
export const GRUPOS_MODOS: { titulo: string; modos: Modo[] }[] = [
  { titulo: "Hoy", modos: ["poblacion", "renta", "alquiler", "paro", "extranjeros", "servicios", "fibra", "aislamiento", "clima", "sol", "frio", "envejecimiento"] },
  { titulo: "Síntesis", modos: ["indice", "arquetipos", "rendimiento", "inflexion", "demografia", "lisa_crecimiento", "lisa_renta"] },
  { titulo: "Futuro", modos: ["prediccion", "riesgo", "futuro", "futuro_cohorte"] },
];

export const PESOS_DEFECTO: Pesos = { renta: 0.25, paro: 0.20, alquiler: 0.20, envejecimiento: 0.15, servicios: 0.20 };
const CAMPO_COMP: Record<ClaveIndice, string> = {
  renta: "c_renta", paro: "c_paro", alquiler: "c_alquiler", envejecimiento: "c_envejecimiento", servicios: "c_servicios",
};

export function combinaCustom(p: GeoJsonProperties, w: Pesos): number | null {
  const props = p ?? {};
  let num = 0, den = 0;
  for (const k of CLAVES_INDICE) {
    const v = props[CAMPO_COMP[k]] as number | null | undefined;
    if (v == null) continue;
    num += w[k] * v;
    den += w[k];
  }
  return den > 0 ? Math.round((num / den) * 10) / 10 : null;
}

export function color(buckets: [number, string][], v: number | null): string {
  if (v == null) return "#e2e8f0";
  for (const [umbral, c] of buckets) if (v >= umbral) return c;
  return buckets[buckets.length - 1][1];
}

export function tooltip(modo: Modo, p: GeoJsonProperties, pesos?: Pesos): string {
  const props = p ?? {};
  if (modo === "indice") {
    const f = (v: unknown) => (v == null ? "—" : Math.round(v as number));
    const score = pesos ? combinaCustom(p, pesos) : (props.score as number | null);
    return `${props.nombre}: ${score ?? "—"}/100 · renta ${f(props.c_renta)} · empleo ${f(props.c_paro)} · asequibilidad ${f(props.c_alquiler)} · vitalidad ${f(props.c_envejecimiento)} · servicios ${f(props.c_servicios)}`;
  }
  if (modo === "servicios") {
    return `${props.nombre}: ${props.serv_1000 ?? "—"}‰ hab · salud ${props.n_salud ?? 0} · educación ${props.n_educacion ?? 0} · comercio ${props.n_comercio ?? 0}`;
  }
  if (modo === "clima") {
    return `${props.nombre}: ${props.temp ?? "—"} °C · ${props.precip ?? "—"} mm/año`;
  }
  if (modo === "arquetipos") {
    return `${props.nombre}: arquetipo ${props.cluster ?? "—"} · ${props.etiqueta ?? ""}`;
  }
  if (modo === "aislamiento") {
    return `${props.nombre}: sanidad a ${props.km_salud ?? "—"} km · educación a ${props.km_educacion ?? "—"} km · capital a ${props.km_capital ?? "—"} km`;
  }
  if (modo === "rendimiento") {
    const r = props.residuo as number | null;
    const texto = r == null ? "sin datos" : r >= 0 ? `crece ${r} pp MÁS de lo predicho` : `crece ${Math.abs(r)} pp MENOS de lo predicho`;
    return `${props.nombre}: ${texto}`;
  }
  if (modo === "riesgo") {
    const niveles: Record<string, string> = { verde: "riesgo bajo", ambar: "riesgo medio", rojo: "riesgo ALTO" };
    return `${props.nombre}: ${niveles[(props.nivel as string) ?? ""] ?? "sin datos"} · P(pérdida fuerte a 5 años) = ${props.prob ?? "—"}%`;
  }
  if (modo.startsWith("lisa_")) {
    const cat = (props.categoria as string) ?? "—";
    const etiqueta = cat === "ns" ? "no significativo" : cat;
    const unidad = modo === "lisa_renta" ? " €" : "%";
    return `${props.nombre}: ${etiqueta} · valor ${props.valor ?? "—"}${unidad} (p=${props.p ?? "—"})`;
  }
  if (modo === "inflexion") {
    const tipo = props.tipo as string | null;
    if (!tipo) return `${props.nombre}: sin inflexión clara`;
    return `${props.nombre}: ${tipo} en ${props.anio_inflexion} (${props.pend_antes}→${props.pend_despues} hab/año)`;
  }
  if (modo === "demografia") {
    const tipo = props.tipo as string | null;
    if (!tipo) return `${props.nombre}: sin datos`;
    const veg = props.saldo_vegetativo as number, mig = props.saldo_migratorio as number;
    return `${props.nombre}: ${tipo} · vegetativo ${veg >= 0 ? "+" : ""}${veg}, migratorio ${mig >= 0 ? "+" : ""}${mig}`;
  }
  if (modo === "prediccion") {
    const c = props.cambio_pct;
    const signo = c != null && c > 0 ? "+" : "";
    const banda = props.cambio_inf != null ? ` [${props.cambio_inf}..${props.cambio_sup}]` : "";
    return `${props.nombre}: ${c != null ? signo + c + "%" : "—"}${banda} → ${props.pob_proyectada ?? "—"} hab (${props.anio_horizonte ?? ""}) · ${props.drivers ?? ""}`;
  }
  if (modo.startsWith("futuro")) {
    const c = props.cambio_pct;
    const signo = c != null && c > 0 ? "+" : "";
    return `${props.nombre}: ${props.trayectoria ?? "—"} (${c != null ? signo + c + "%" : "—"} → ${props.pob_proyectada ?? "—"} hab en ${props.anio_horizonte ?? ""})`;
  }
  const esc = ESCALAS[modo];
  return `${props.nombre}: ${props[esc.campo] ?? "—"}${esc.sufijo}`;
}
