# ADR 0002 — Fuentes de datos, clave de cruce y trampas

- **Estado:** aceptado
- **Fecha:** 2026-06-25

## Decisión
- **Clave primaria territorial:** `cod_municipio` (5 dígitos INE, **texto**). Sección
  censal (10 dígitos) como grano fino futuro. El **código postal NO es administrativo**
  (relación muchos-a-muchos); si se usa, vía crosswalk como aproximación.
- **Ingesta:** el grano municipal del INE **no** sale por la API `wstempus`; viene como
  descarga masiva **`.px`/CSV** → parser `pyaxis`. Cada fuente tendrá su adaptador
  (REST / fichero masivo / WFS).

## Trampas verificadas (metodología oficial)
- **Renta ADRH:** publica a nivel municipio directamente; el Gini **no se agrega**
  promediando. El secreto estadístico acota rentas individuales a ±3M€ (despreciable a
  escala municipal) y las cotas de indicadores son percentílicas (p0,1/p99,5).
  → **No** hace falta regresión censurada (Tobit) en v1.
- **Afiliación SS / otros:** enmascaran valores `<5` → imputar **valor central + flag**.
- **MNP:** `0` es dato real en pueblos diminutos, no ausente.
- **Linaje municipal:** usar la tabla INE "Alteraciones de los municipios desde 1842";
  modelar como SCD2 / grafo para construir series temporales continuas.
- **AEMET:** datos por estación (no municipio) → interpolar; API con límite ~50 req/min
  → rate limiting + backoff dentro del pipeline (no microservicio Celery aparte en v1).

## Notas de herramientas
- SAE en Python: `samplics` se rebautizó a `svy` (`svy[sae]`, Fay-Herriot), módulo SAE
  "in progress" → plan B `statsmodels`/`PyMC`. `saeHB.spatial`/BYM son de R (decidir
  rpy2 vs equivalentes Python) — **todo esto es post-MVP**.
