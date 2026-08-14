# db

PostgreSQL 16 + PostGIS 3.4. La imagen es **`imresamu/postgis`** (PostGIS oficial pero
multi-arquitectura: incluye `linux/arm64`), y ejecuta los `.sql` de `init/` al crear el
volumen por primera vez — **solo entonces**. Si cambias `init/`, hay que recrear el
volumen para que surta efecto.

## Esquema

Se gestiona con **Alembic** desde `services/orchestrator/migrations/` (28 revisiones
lineales, `0001_dim_municipio` → `0028_aire`). Se aplica con:

```bash
make migrate
```

21 tablas del proyecto (más `alembic_version` y las vistas de sistema de PostGIS),
agrupadas por función:

- **Dimensión**: `dim_municipio` (geometría en 4326 y 25830, superficie, códigos).
- **Hechos**: `fact_municipio_anual` (grano `municipio × año`, la matriz central),
  `fact_piramide` (cohortes de edad), `fact_provincia_anual` (tasas vitales).
- **Atributos casi-estáticos**: `municipio_wiki`, `municipio_servicios`,
  `municipio_aislamiento`, `municipio_conectividad`, `municipio_aire`.
- **Salidas de modelo**: `indice_municipio`, `prediccion_ml`, `riesgo_municipio`,
  `proyeccion_municipio`, `proyeccion_cohorte`, `arquetipo_municipio`,
  `lisa_municipio`, `inflexion_municipio`, `demografia_municipio`,
  `rendimiento_municipio`, `gemelo_municipio`, `similar_municipio`.

Especificación completa del modelo de datos: [`../docs/matrix-spec.md`](../docs/matrix-spec.md).

## Convenciones

- `cod_municipio` es **texto de 5 caracteres**; los ceros a la izquierda son
  significativos (`01001` no es `1001`).
- Nombres de columnas en español, espejo de las fuentes oficiales.

## Sistemas de referencia

- **4326** (WGS84) para servir geometría al frontend.
- **25830** (ETRS89 / UTM 30N) para cálculos métricos peninsulares — distancias,
  áreas, vecindad.
- Canarias cae fuera de la zona 30N: sus cálculos métricos tienen error creciente con
  la longitud. La zona correcta sería **25828** (UTM 28N). Limitación conocida.

## Extensiones

`init/01_extensions.sql` habilita `postgis`, `pg_trgm` y `unaccent`. La migración
`0018_unaccent` añade además un envoltorio inmutable `f_unaccent` y un índice funcional
sobre `dim_municipio.nombre`, necesario para que el buscador ignore acentos usando
índice en lugar de recorrer la tabla.
