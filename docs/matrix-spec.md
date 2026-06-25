# Especificación de la matriz `municipio × año`

Plano de datos del MVP: qué columnas, de dónde sale cada una, cómo se transforma y
cómo se tratan los huecos. Diseñado para alimentar el modelo bandera (trayectoria
poblacional por cohorte-componente). **Ventana temporal: 2015 → último disponible.**

## Claves
- `cod_municipio`: 5 dígitos INE, **tipo TEXTO** (los ceros a la izquierda importan:
  `"01001"`). ~8.131 municipios.
- `anio`: entero (referencia a 1 de enero).
- Grano de la tabla de hechos: **`(cod_municipio, anio)`**.

## `dim_municipio` (SCD Tipo 2 — resuelve el linaje desde 1842)
| Columna | Tipo | Fuente | Notas |
|---|---|---|---|
| `cod_municipio` | text(5) | INE | PK lógica |
| `nombre` | text | INE | |
| `cod_provincia` | text(2) | derivado | `cod_municipio[:2]` |
| `cod_ccaa` | text(2) | INE | |
| `valido_desde` / `valido_hasta` | date | INE Alteraciones | Vigencia (vintage) |
| `cod_sucesor` / `cod_predecesores` | text / text[] | INE Alteraciones | Grafo de linaje |
| `superficie_km2` | float | IGN | De la geometría |
| `altitud_media_m` | float | DEM (zonal stats) | Corrige interpolación de clima |
| `geom_25830` | geometry(MultiPolygon,25830) | IGN/CNIG | Cálculos métricos |
| `geom_4326` | geometry(MultiPolygon,4326) | derivado | Frontend |

Tabla auxiliar `municipio_vecinos(cod_municipio, cod_vecino)` — derivada con
`ST_Touches`. Necesaria para el suavizado espacial de la migración.

## `fact_municipio_anual` — PK `(cod_municipio, anio)`

### Demografía — Padrón (INE) · core
`poblacion_total`, `poblacion_hombres`, `poblacion_mujeres`, `pob_0_15`,
`pob_16_64`, `pob_65_mas` (directo, `.px`→pyaxis). Derivadas: `densidad_hab_km2`,
`indice_envejecimiento` (= `pob_65_mas/pob_0_15*100`), `tasa_dependencia`.

### `fact_piramide` (tabla aparte) · core
Grano `(cod_municipio, anio, sexo, grupo_edad)` → `poblacion`. Cohortes quinquenales
(0-4 … 85+). **Insumo del cohorte-componente.**

### Flujos vitales — MNP (INE) · core
`nacimientos`, `defunciones` (directo; 0 real ≠ NULL en pueblos diminutos),
`crecimiento_vegetativo` (= nac − def).

### Migración — residuo (o EVR) · core
`migracion_neta` (= Δpoblacion − crecimiento_vegetativo, o EVR directo),
`migracion_neta_suavizada` (suavizado espacial con vecinos).

### Economía — Atlas de Renta ADRH (INE/AEAT) · core
`renta_neta_media_persona`, `renta_neta_media_hogar`, `indice_gini`,
`ratio_s80_s20`. **Tomar el dato a nivel MUNICIPIO directamente** (no agregar desde
sección; el Gini no se promedia). Secreto estadístico: rentas individuales acotadas a
±3M€ (irrelevante a escala municipal); cotas de indicadores por percentiles p0,1/p99,5.

### Empleo — Paro registrado SEPE · core
`paro_media_anual` (media de 12 meses), `paro_diciembre`, `paro_hombres`,
`paro_mujeres`, opcional por sector. `tasa_paro_proxy` (= paro/pob_16_64*100,
**proxy, no oficial**). Scraping defensivo de CSV → pivot → media.

### Clima — AEMET (estación → municipio) · core
`temp_media_anual`, `precip_anual_mm`, `dias_calor_>35`. Interpolación: MVP =
estación más cercana con corrección por altitud; fase 2 = Kriging Universal con DEM.
Trazabilidad: `metodo_interpol`, `n_estaciones`.

### Banderas de calidad · core
`flag_imputado_paro` (valor `<5` imputado con **valor central + flag**),
`flag_renta_secreto`, `flag_alteracion_municipal`, `n_secciones`.

## Reglas transversales (contrato del ETL)
1. Códigos siempre como **texto** (ceros a la izquierda).
2. Extensivas (población, paro, nacimientos) → **suma**; intensivas (renta, temp) →
   media **ponderada por población** (si hubiera que agregar).
3. Enmascarado `<5` → imputar **valor central + flag**. Nunca NaN silencioso.
4. **Cero real ≠ ausente** (MNP en pueblos diminutos).
5. Renta de sección negativa → excluida (metodología INE).
6. Linaje: para series continuas, proyectar hacia atrás sumando (extensivas) /
   promediando ponderado (intensivas) los municipios predecesores.
7. **Crudo inmutable primero** en `raw/`; validar esquema entrante (Pydantic).

## Fuera de v1
SAE bayesiano fino, Kriging Universal, NDVI/Copernicus, SERPAVI, GDELT, sección
censal como grano operativo, los cruces avanzados. Entran como capas posteriores.
