import type { GeoJsonProperties } from "geojson";
import {
  Baby,
  Briefcase,
  CloudSun,
  Compass,
  Home,
  Hourglass,
  type LucideIcon,
  MapPinOff,
  Shapes,
  Sparkles,
  Store,
  Target,
  TrendingUp,
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
  envejecimiento: {
    endpoint: "envejecimiento.geojson", etiqueta: "Envejecimiento", icono: Hourglass, titulo: "Índice envejec.", campo: "indice", sufijo: "", anios: "envejecimiento/anios",
    buckets: [[400, "#800026"], [200, "#bd0026"], [120, "#e31a1c"], [80, "#fc4e2a"], [40, "#feb24c"], [0, "#ffffb2"]],
  },
  rendimiento: {
    endpoint: "rendimiento.geojson", etiqueta: "Contra pronóstico", icono: Target, titulo: "Residuo vs predicho (pp)", campo: "residuo", sufijo: " pp",
    // divergente RdBu: azul = sobre-rinde, rojo = bajo-rinde
    buckets: [[15, "#2166ac"], [5, "#67a9cf"], [-5, "#f7f7f7"], [-15, "#ef8a62"], [-1000, "#b2182b"]],
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
};

// agrupación de modos para la sidebar
export const GRUPOS_MODOS: { titulo: string; modos: Modo[] }[] = [
  { titulo: "Hoy", modos: ["poblacion", "renta", "alquiler", "paro", "servicios", "aislamiento", "clima", "envejecimiento"] },
  { titulo: "Síntesis", modos: ["indice", "arquetipos", "rendimiento"] },
  { titulo: "Futuro", modos: ["prediccion", "futuro", "futuro_cohorte"] },
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
