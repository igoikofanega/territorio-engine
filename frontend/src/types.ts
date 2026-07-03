export type Modo =
  | "indice"
  | "poblacion"
  | "renta"
  | "alquiler"
  | "paro"
  | "servicios"
  | "clima"
  | "envejecimiento"
  | "arquetipos"
  | "rendimiento"
  | "aislamiento"
  | "lisa_crecimiento"
  | "lisa_renta"
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
  aislamiento: { km_salud: number | null; km_educacion: number | null; km_capital: number | null } | null;
  similares: { cod: string; nombre: string; provincia: string }[];
};

export const CLAVES_INDICE = ["renta", "paro", "alquiler", "envejecimiento", "servicios"] as const;
export type ClaveIndice = (typeof CLAVES_INDICE)[number];
export type Pesos = Record<ClaveIndice, number>;
