/// <reference types="vite/client" />

/** Variables de entorno del frontend. Tipadas para que `tsc` valide su uso. */
interface ImportMetaEnv {
  /** URL de teselas del mapa base. Vacía = OpenStreetMap (no pide clave). */
  readonly VITE_TILES_URL?: string;
  /** Atribución del mapa base, obligatoria por la licencia de la fuente de teselas. */
  readonly VITE_TILES_ATTR?: string;
  /** Opacidad del mapa base (0-1). Va atenuado para no competir con el coroplético. */
  readonly VITE_TILES_OPACIDAD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
