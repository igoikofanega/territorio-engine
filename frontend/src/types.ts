export type Modo =
  | "indice"
  | "poblacion"
  | "renta"
  | "alquiler"
  | "paro"
  | "extranjeros"
  | "servicios"
  | "fibra"
  | "aire"
  | "clima"
  | "sol"
  | "frio"
  | "envejecimiento"
  | "arquetipos"
  | "rendimiento"
  | "inflexion"
  | "demografia"
  | "aislamiento"
  | "lisa_crecimiento"
  | "lisa_renta"
  | "riesgo"
  | "prediccion"
  | "futuro"
  | "futuro_cohorte";

export type Prov = { cod: string; nombre: string; piramide: boolean };

export type Sugerencia = { cod: string; nombre: string; provincia: string; cod_provincia: string };

export type SerieRow = {
  anio: number;
  poblacion: number | null;
  paro: number | null;
  renta: number | null;
  alquiler: number | null;
  temp: number | null;
  precip: number | null;
  pct_extranjeros: number | null;
};

export type FichaData = {
  cod: string;
  nombre: string;
  provincia: { cod: string; nombre: string };
  superficie_km2: number | null;
  wiki: {
    descripcion: string | null;
    gentilicio: string | null;
    altitud: number | null;
    web: string | null;
    imagen: string | null;
    escudo: string | null;
    wiki_titulo: string | null;
  } | null;
  serie: SerieRow[];
  indice: {
    anio: number;
    score: number | null;
    componentes: {
      renta: number | null;
      paro: number | null;
      alquiler: number | null;
      envejecimiento: number | null;
      servicios: number | null;
    };
  } | null;
  prediccion: {
    anio_base: number;
    anio_horizonte: number;
    pob_base: number;
    pob_proyectada: number;
    cambio_pct: number;
    cambio_inf: number | null;
    cambio_sup: number | null;
    drivers: string | null;
  } | null;
  arquetipo: { cluster: number; etiqueta: string } | null;
  rendimiento: { residuo: number | null; z: number | null; clasificacion: string | null } | null;
  /** Proyección cohorte-componente (Hamilton-Perry): el "contraste metodológico" del
   * ADR 0004 frente al modelo estadístico de `prediccion`. */
  proyeccion_cohorte: {
    anio_horizonte: number;
    pob_proyectada: number;
    cambio_pct: number;
    trayectoria: string;
  } | null;
  gemelo: {
    cod: string;
    nombre: string;
    provincia: string;
    distancia: number | null;
    crec_propio: number | null;
    crec_gemelo: number | null;
    divergencia: number | null;
  } | null;
  servicios: {
    salud: number | null;
    educacion: number | null;
    comercio: number | null;
    total: number | null;
  } | null;
  riesgo: { prob: number; nivel: "verde" | "ambar" | "rojo" } | null;
  inflexion: {
    anio: number;
    pend_antes: number | null;
    pend_despues: number | null;
    tipo: string;
    magnitud: number | null;
  } | null;
  demografia: {
    saldo_vegetativo: number | null;
    saldo_migratorio: number | null;
    cambio_total: number | null;
    dominante: string | null;
    tipo: string;
  } | null;
  aislamiento: { km_salud: number | null; km_educacion: number | null; km_capital: number | null } | null;
  conectividad: { pct_fibra: number | null; pct_100mbps: number | null; pct_5g: number | null } | null;
  aire: { pm25: number | null; no2: number | null; pm10: number | null; o3: number | null } | null;
  clima: {
    temp: number | null;
    precip: number | null;
    temp_max_media: number | null;
    temp_min_media: number | null;
    temp_min_abs: number | null;
    dias_despejados: number | null;
    humedad_media: number | null;
  } | null;
  similares: { cod: string; nombre: string; provincia: string }[];
};

export type Noticia = {
  titular: string;
  medio: string | null;
  url: string;
  fecha: string | null;
  tema: string | null;
  signo: number | null;
};

/** `consultado: false` = municipio fuera del ámbito de la capa, NO "sin noticias". */
export type NoticiasData = {
  consultado: boolean;
  ambito: string;
  noticias: Noticia[];
};

export const CLAVES_INDICE = ["renta", "paro", "alquiler", "envejecimiento", "servicios"] as const;
export type ClaveIndice = (typeof CLAVES_INDICE)[number];
export type Pesos = Record<ClaveIndice, number>;
